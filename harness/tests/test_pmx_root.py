"""Tests for the A1 shared PMxAgent folder (pmx_root) and the ledger validity rule (ledger), deviations §20.
Run: python3 -m unittest discover -s harness/tests"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ledger, pmx_root, run_arm


def touch(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text)


def pmx_tree(d):
    """A PMxAgent deployment as the harness sees it: data/ and figures/ with a .gitkeep each."""
    for sub in pmx_root.SHARED:
        touch(os.path.join(d, sub, ".gitkeep"), "")
    return d


class Leftovers(unittest.TestCase):
    def test_lists_everything_but_gitkeep_and_the_own_run_folder(self):
        with tempfile.TemporaryDirectory() as d:
            pmx_tree(d)
            touch(os.path.join(d, "data", "pk_simulation_1.csv"))
            touch(os.path.join(d, "data", "A1_T2_case_r03_x", "pk.csv"))
            touch(os.path.join(d, "data", "A1_T2_case_r04_own", "pk.csv"))
            touch(os.path.join(d, "figures", "A1_T2_case_r08_x", "fig.png"))
            self.assertEqual(pmx_root.leftovers(d, own="A1_T2_case_r04_own"),
                             ["data/A1_T2_case_r03_x", "data/pk_simulation_1.csv", "figures/A1_T2_case_r08_x"])

    def test_clean_tree_and_missing_subfolder_give_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            touch(os.path.join(d, "data", ".gitkeep"), "")   # no figures/ at all
            self.assertEqual(pmx_root.leftovers(d, own="r"), [])


class MoveLeftovers(unittest.TestCase):
    def test_moves_keeping_layout_and_leaves_own_folder_and_gitkeep(self):
        with tempfile.TemporaryDirectory() as d:
            pmx, dest = pmx_tree(os.path.join(d, "pmx")), os.path.join(d, "dest")
            touch(os.path.join(pmx, "data", "a.csv"), "A")
            touch(os.path.join(pmx, "figures", "run_x", "f.png"), "F")
            touch(os.path.join(pmx, "data", "own", "in.csv"))
            moved = pmx_root.move_leftovers(pmx, "own", dest)
            self.assertEqual(moved, ["data/a.csv", "figures/run_x"])
            self.assertEqual(open(os.path.join(dest, "data", "a.csv")).read(), "A")
            self.assertTrue(os.path.isfile(os.path.join(dest, "figures", "run_x", "f.png")))
            self.assertEqual(pmx_root.leftovers(pmx, "own"), [])
            self.assertTrue(os.path.isfile(os.path.join(pmx, "data", "own", "in.csv")))
            self.assertTrue(os.path.isfile(os.path.join(pmx, "data", ".gitkeep")))

    def test_nothing_to_move_creates_no_destination(self):
        with tempfile.TemporaryDirectory() as d:
            pmx = pmx_tree(os.path.join(d, "pmx"))
            self.assertEqual(pmx_root.move_leftovers(pmx, "own", os.path.join(d, "dest")), [])
            self.assertFalse(os.path.exists(os.path.join(d, "dest")))

    def test_never_overwrites_an_existing_destination(self):
        with tempfile.TemporaryDirectory() as d:
            pmx, dest = pmx_tree(os.path.join(d, "pmx")), os.path.join(d, "dest")
            touch(os.path.join(pmx, "data", "a.csv"), "new")
            touch(os.path.join(dest, "data", "a.csv"), "old")
            with self.assertRaises(FileExistsError):
                pmx_root.move_leftovers(pmx, "own", dest)
            self.assertEqual(open(os.path.join(dest, "data", "a.csv")).read(), "old")
            self.assertEqual(open(os.path.join(pmx, "data", "a.csv")).read(), "new")


class ExclusiveLock(unittest.TestCase):
    def test_second_holder_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with pmx_root.exclusive(d):
                with self.assertRaises(pmx_root.Busy):
                    with pmx_root.exclusive(d):
                        pass
            with pmx_root.exclusive(d):   # released again
                pass


class LedgerValidity(unittest.TestCase):
    def test_excluded_runs_are_not_valid_but_still_completed(self):
        ok = {"runid": "A1_T2_case_r03_x", "status": "ok", "is_error": "False"}
        self.assertTrue(ledger.completed(ok))
        self.assertTrue(ledger.valid(ok, frozenset()))
        self.assertFalse(ledger.valid(ok, {"A1_T2_case_r03_x"}))
        self.assertFalse(ledger.valid({"runid": "y", "status": "failed_ratelimit_midrun", "is_error": "True"}, set()))

    def test_exclusions_file_is_read_and_a_missing_file_excludes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "exclusions.csv")
            self.assertEqual(ledger.exclusions(p), frozenset())
            open(p, "w").write("runid,reason,deviation\nA1_T2_case_r03_x,shared PMxAgent folder,§20\n")
            self.assertEqual(ledger.exclusions(p), frozenset({"A1_T2_case_r03_x"}))


class RepStateExclusions(unittest.TestCase):
    def test_excluded_rows_do_not_count_but_keep_the_rep_numbering(self):
        rows = [{"runid": f"A1_T2_case_r0{i}_x", "arm": "A1", "task": "T2_case", "rep": str(i), "status": "ok",
                 "is_error": "False"} for i in (1, 2, 3)]
        self.assertEqual(run_arm.rep_state("A1", "T2_case", rows, [], excluded={"A1_T2_case_r01_x",
                                                                                  "A1_T2_case_r02_x"}), (1, 3))


class RootRecord(unittest.TestCase):
    """pmx_root.json in a run's raw folder says the shared folder was emptied before the agent started."""
    def test_record_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            pmx_root.write_record(d, stray=["data/a.csv"], collected=["figures/f"])
            self.assertEqual(json.load(open(os.path.join(d, pmx_root.RECORD))),
                             {"emptied_before_start": True, "stray_at_start": ["data/a.csv"],
                              "collected_after": ["figures/f"]})
            self.assertTrue(pmx_root.started_clean(d))
            self.assertFalse(pmx_root.started_clean(os.path.join(d, "nope")))


if __name__ == "__main__":
    unittest.main()
