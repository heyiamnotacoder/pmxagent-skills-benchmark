"""Token pool: several subscription accounts share the runs; a rep uses the first account not at its usage limit
(paper/SPEC.md decisions 2026-11-20; logs/deviations.md §19). Run: python3 -m unittest discover -s harness/tests"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tokens


def make_pool(d, labels):
    tok_dir = os.path.join(d, "tokens"); os.makedirs(tok_dir)
    for lab in labels:
        open(os.path.join(tok_dir, lab), "w").write(f"tok-{lab}\n")
    return tokens.Pool.load(tokens_dir=tok_dir, single_file=os.path.join(d, "absent"),
                            limits_file=os.path.join(d, "limits.json"))


class Pool(unittest.TestCase):
    def test_picks_first_free_account_and_skips_limited_until_reset(self):
        with tempfile.TemporaryDirectory() as d:
            pool = make_pool(d, ["acct2", "acct1"])
            self.assertEqual(pool.pick(now=100), ("acct1", "tok-acct1"))
            pool.mark_limited("acct1", resets_at=500)
            self.assertEqual(pool.pick(now=100), ("acct2", "tok-acct2"))
            self.assertEqual(pool.pick(now=500), ("acct1", "tok-acct1"))   # reset passed

    def test_limits_are_shared_through_the_file_and_all_limited_gives_none(self):
        with tempfile.TemporaryDirectory() as d:
            pool = make_pool(d, ["acct1", "acct2"])
            pool.mark_limited("acct1", resets_at=900)
            other = tokens.Pool.load(tokens_dir=os.path.join(d, "tokens"), single_file=os.path.join(d, "absent"),
                                     limits_file=os.path.join(d, "limits.json"))   # e.g. the other lane
            other.mark_limited("acct2", resets_at=700)
            self.assertIsNone(pool.pick(now=100))
            self.assertEqual(pool.next_free(now=100), 700)
            self.assertNotIn("tok-", open(os.path.join(d, "limits.json")).read())   # no token in the state file

    def test_falls_back_to_the_single_token_file_then_to_no_pool(self):
        with tempfile.TemporaryDirectory() as d:
            single = os.path.join(d, "oauth_token"); open(single, "w").write("solo\n")
            pool = tokens.Pool.load(tokens_dir=os.path.join(d, "none"), single_file=single,
                                    limits_file=os.path.join(d, "limits.json"))
            self.assertEqual(pool.pick(now=0), ("default", "solo"))
            empty = tokens.Pool.load(tokens_dir=os.path.join(d, "none"), single_file=os.path.join(d, "absent"),
                                     limits_file=os.path.join(d, "limits.json"))
            self.assertFalse(empty)                    # no accounts: keychain login (T1 mode)
            self.assertIsNone(empty.pick(now=0))


class ResetTime(unittest.TestCase):
    def test_latest_resets_at_in_transcript_or_none(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "transcript.jsonl")
            ev = {"type": "assistant", "error": "rate_limit",
                  "api_error_params": {"rate_limit_info": {"status": "rejected", "resetsAt": 1795210800}}}
            open(p, "w").write(json.dumps(ev) + "\n" + '{"resetsAt":1795200000}\n')
            self.assertEqual(tokens.reset_time(p), 1795210800)
            open(p, "w").write('{"type": "result"}\n')
            self.assertIsNone(tokens.reset_time(p))


if __name__ == "__main__":
    unittest.main()
