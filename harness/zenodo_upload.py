#!/usr/bin/env python3
"""Deposit the evidence archive on Zenodo and reserve its DOI. Does NOT publish (publishing is permanent).

Token: $ZENODO_TOKEN or ~/.zenodo_token (scopes deposit:write, deposit:actions).
Usage: zenodo_upload.py [--sandbox]      -> prints deposition id, reserved DOI, edit URL
       zenodo_upload.py --publish ID     -> publishes that deposition (irreversible)
Stdlib only.
"""
import glob, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SANDBOX = "--sandbox" in sys.argv
API = "https://sandbox.zenodo.org/api" if SANDBOX else "https://zenodo.org/api"
TOKEN = os.environ.get("ZENODO_TOKEN") or open(os.path.expanduser("~/.zenodo_token")).read().strip()

META = {
    "upload_type": "dataset",
    "title": "Evidence archive: Agent Skills vs PMxAgent on the CPT:PSP NCA benchmark",
    "creators": [{"name": "Pandya, Dhruvik", "affiliation": "Department of Pharmacology, AIIMS Jodhpur, India"}],
    "description": (
        "<p>Raw evidence for a Letter to the Editor on Bloomingdale &amp; Khot, <i>PMxAgent: an agentic platform for "
        "pharmacometrics</i>, CPT Pharmacometrics Syst Pharmacol 2026;15(10):e70325.</p>"
        "<p>The archive holds every benchmark run, including runs that failed because of usage limits. Each run has "
        "the full Claude Code transcript (stream-JSON), the prompt, stderr, the output files and their SHA-256. The "
        "archive also contains the run ledger, per-run scores, the isolation audit, the protocol deviation log, scorer "
        "calibration and pinned versions. <code>MANIFEST.sha256</code> lists the hash of every file, and "
        "<code>provenance.json</code> gives the git commit, model IDs, Claude Code version and PMxAgent container "
        "digests. Code and skills: https://github.com/heyiamnotacoder/pmxagent-skills-benchmark.</p>"
        "<p>Benchmark input data derive from the Supporting Information of the article above (Creative Commons "
        "Attribution-NonCommercial).</p>"),
    "access_right": "open",
    "license": "cc-by-nc-4.0",
    "keywords": ["pharmacometrics", "noncompartmental analysis", "AI agents", "agent skills", "MCP", "reproducibility"],
    "related_identifiers": [
        {"identifier": "10.1002/psp4.70325", "relation": "references", "scheme": "doi"},
        {"identifier": "https://github.com/heyiamnotacoder/pmxagent-skills-benchmark", "relation": "isSupplementTo",
         "scheme": "url"},
    ],
    "prereserve_doi": True,
}


def call(method, url, data=None, ctype="application/json"):
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": ctype})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b"{}")


def main():
    if "--publish" in sys.argv:
        dep = sys.argv[sys.argv.index("--publish") + 1]
        r = call("POST", f"{API}/deposit/depositions/{dep}/actions/publish")
        print("published:", r.get("doi"), r.get("links", {}).get("html"))
        return
    prov = json.load(open(os.path.join(ROOT, "results", "evidence", "provenance.json")))
    tgz = os.path.expanduser(f"~/pmxbench_evidence/{prov['archive']['file']}")
    dep = call("POST", f"{API}/deposit/depositions", json.dumps({}).encode())
    bucket = dep["links"]["bucket"]
    files = [tgz, os.path.join(ROOT, "results", "evidence", "MANIFEST.sha256"),
             os.path.join(ROOT, "results", "evidence", "provenance.json")]
    for f in files:
        with open(f, "rb") as fh:
            call("PUT", f"{bucket}/{os.path.basename(f)}", fh.read(), "application/octet-stream")
    dep = call("PUT", f"{API}/deposit/depositions/{dep['id']}", json.dumps({"metadata": META}).encode())
    doi = dep["metadata"]["prereserve_doi"]["doi"]
    print(json.dumps({"deposition_id": dep["id"], "reserved_doi": doi, "edit_url": dep["links"]["html"],
                      "files": [os.path.basename(f) for f in files], "published": False}, indent=1))


if __name__ == "__main__":
    main()
