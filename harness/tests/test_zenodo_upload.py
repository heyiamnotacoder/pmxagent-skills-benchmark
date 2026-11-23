"""Tests for the Zenodo new-version deposit (zenodo_upload.py, paper/SPEC.md slice S12, issue #14). No network:
the HTTP call is a fake that records every request.  Run: python3 -m unittest discover -s harness/tests"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import zenodo_upload as zu

API = "https://zenodo.example/api"


class FakeZenodo:
    """Answers the deposit API the way Zenodo does for a published record 100 (concept 99) with two files."""
    def __init__(self):
        self.requests = []
        self.draft = {"id": 101, "conceptdoi": "10.5281/zenodo.99",
                      "links": {"self": f"{API}/deposit/depositions/101", "bucket": f"{API}/files/b101",
                                "html": "https://zenodo.example/deposit/101"},
                      "files": [{"id": "f-old-tgz", "filename": "old.tar.gz"}, {"id": "f-old-man", "filename": "MANIFEST.sha256"}],
                      "metadata": {"title": "old title", "doi": "10.5281/zenodo.100",
                                   "creators": [{"name": "Pandya, Dhruvik"}, {"name": "Singh, Surjit"}],
                                   "license": "cc-by-nc-4.0", "prereserve_doi": {"doi": "10.5281/zenodo.101"}}}

    def __call__(self, method, url, data=None, ctype="application/json"):
        body = json.loads(data) if ctype == "application/json" and data else None
        name = getattr(data, "name", None)
        self.requests.append((method, url, body if body is not None else name))
        if url.endswith("/actions/newversion"):
            return {"id": 100, "links": {"latest_draft": f"{API}/deposit/depositions/101"}}
        if method == "GET":
            return self.draft
        if method == "PUT" and url == self.draft["links"]["self"]:
            return {**self.draft, "metadata": {**body["metadata"], "prereserve_doi": {"doi": "10.5281/zenodo.101"}}}
        return {}


class NewVersion(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.files = []
        for n in ("new.tar.gz", "MANIFEST.sha256"):
            p = os.path.join(d, n)
            with open(p, "w") as fh:
                fh.write(n)
            self.files.append(p)
        self.z = FakeZenodo()
        self.out = zu.new_version(self.z, API, 100, self.files, {"title": "v2 title", "version": "2"})

    def test_versions_the_existing_record(self):
        self.assertEqual(self.z.requests[0][:2], ("POST", f"{API}/deposit/depositions/100/actions/newversion"))
        self.assertEqual(self.z.requests[1][:2], ("GET", f"{API}/deposit/depositions/101"))

    def test_inherited_files_removed_then_new_files_uploaded(self):
        reqs = [(m, u) for m, u, _ in self.z.requests]
        dels = [i for i, (m, _) in enumerate(reqs) if m == "DELETE"]
        puts = [i for i, (m, u) in enumerate(reqs) if m == "PUT" and "/files/b101/" in u]
        self.assertEqual([reqs[i][1] for i in dels], [f"{API}/deposit/depositions/101/files/f-old-tgz",
                                                     f"{API}/deposit/depositions/101/files/f-old-man"])
        self.assertEqual([reqs[i][1] for i in puts], [f"{API}/files/b101/new.tar.gz", f"{API}/files/b101/MANIFEST.sha256"])
        self.assertLess(max(dels), min(puts))   # MANIFEST.sha256 keeps its name: delete before upload

    def test_metadata_updated_but_creators_kept(self):
        meta = [b for m, u, b in self.z.requests if m == "PUT" and u == f"{API}/deposit/depositions/101"][-1]["metadata"]
        self.assertEqual(meta["title"], "v2 title")
        self.assertEqual(meta["version"], "2")
        self.assertEqual([c["name"] for c in meta["creators"]], ["Pandya, Dhruvik", "Singh, Surjit"])
        self.assertNotIn("doi", meta)   # the previous version's DOI must not be sent with the new version

    def test_reports_both_dois_and_never_publishes(self):
        self.assertEqual(self.out["reserved_doi"], "10.5281/zenodo.101")
        self.assertEqual(self.out["concept_doi"], "10.5281/zenodo.99")
        self.assertFalse(self.out["published"])
        self.assertFalse([u for _, u, _ in self.z.requests if u.endswith("/actions/publish")])


if __name__ == "__main__":
    unittest.main()
