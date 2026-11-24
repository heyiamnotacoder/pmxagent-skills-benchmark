#!/usr/bin/env python3
"""Deposit the evidence archive on Zenodo and reserve its DOI, or edit a published record's creators. Does NOT publish (publishing is permanent).

Token: $ZENODO_TOKEN or ~/.zenodo_token (scopes deposit:write, deposit:actions).
Usage: zenodo_upload.py --new-version RECORD_ID [--sandbox]
                                      -> new version of a published record (same concept DOI): inherits its metadata
                                         (creators, licence, links), replaces its files with the current archive,
                                         MANIFEST.sha256 and provenance.json, updates title/description/version;
                                         prints the new version's reserved DOI, the concept DOI and the edit URL
       zenodo_upload.py --drop-creator ID "Family, Given" [--sandbox]
                                      -> opens published deposition ID for a metadata edit and removes that creator;
                                         files and DOI are unchanged; the edit stays unpublished until --publish ID
       zenodo_upload.py --publish ID [--sandbox]
                                      -> publishes that deposition (irreversible)
The T1 archive is record 23019418 (concept 10.5281/zenodo.23019417); issue #14 deposits T1-T3 as its next version.
Stdlib only.
"""
import datetime, functools, hashlib, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV = os.path.join(ROOT, "results", "evidence")
USER_AGENT = "pmxbench-zenodo-upload/1.0"

# What the T1-T3 version changes; everything else is inherited from the previous version.
V2 = {
    "title": "Evidence archive: Agent Skills vs PMxAgent on pharmacometrics agent tasks (NCA, simulation case study, "
             "NCA stress tests)",
    "version": "2",
    "description": (
        "<p>Raw evidence for the preprint <i>Do agentic pharmacometrics tools need server infrastructure? A controlled "
        "benchmark of an MCP platform versus Agent Skills for noncompartmental analysis</i>, which compares PMxAgent "
        "(Bloomingdale &amp; Khot, CPT Pharmacometrics Syst Pharmacol 2026;15(10):e70325) with Claude Code and Agent "
        "Skills.</p>"
        "<p>Version 2 adds the simulation case study (T2) and the NCA stress tasks (T3a messy workbook, T3b explicit "
        "BLQ, T3c units, T3d oral one-compartment, T3e large) to the Task 1 NCA runs of version 1, and the secondary "
        "arm A1b. The archive holds every benchmark run, including runs cut off by usage limits and runs excluded for "
        "a protocol reason. Each run has the full Claude Code transcript (stream-JSON), the prompt, stderr, the output "
        "files and their SHA-256. The archive also contains the run ledger, the exclusion list, per-run scores, "
        "summaries and statistics, the isolation audit, the protocol deviation log, scorer calibration and pinned "
        "versions. <code>MANIFEST.sha256</code> lists the hash of every file, and <code>provenance.json</code> gives the "
        "git commit, the Claude Code version of the scored runs per task, model IDs and PMxAgent container digests. "
        "Code and skills: https://github.com/heyiamnotacoder/pmxagent-skills-benchmark.</p>"
        "<p>Benchmark input data derive from the Supporting Information of the article above (Creative Commons "
        "Attribution-NonCommercial).</p>"),
}
@functools.cache
def token():
    return os.environ.get("ZENODO_TOKEN") or open(os.path.expanduser("~/.zenodo_token")).read().strip()


def http(method, url, data=None, ctype="application/json"):
    """One authenticated request; `data` is bytes or an open binary file (streamed, sized from the file)."""
    headers = {"Authorization": f"Bearer {token()}", "Content-Type": ctype, "User-Agent": USER_AGENT}
    if hasattr(data, "fileno"):
        headers["Content-Length"] = str(os.fstat(data.fileno()).st_size)
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b"{}")


def upload(call, bucket, files):
    for f in files:
        with open(f, "rb") as fh:
            call("PUT", f"{bucket}/{os.path.basename(f)}", fh, "application/octet-stream")


def summary(dep, files):
    return {"deposition_id": dep["id"], "reserved_doi": dep["metadata"]["prereserve_doi"]["doi"],
            "concept_doi": dep.get("conceptdoi"), "edit_url": dep["links"]["html"],
            "files": [os.path.basename(f) for f in files], "published": False}


def new_version(call, api, record_id, files, changes):
    """Draft the next version of published record `record_id` with `files`; metadata = previous version's + `changes`.
    The draft is left unpublished. Returns its id, reserved DOI, concept DOI and edit URL."""
    orig = call("POST", f"{api}/deposit/depositions/{record_id}/actions/newversion")
    draft = call("GET", orig["links"]["latest_draft"])
    for f in draft.get("files", []):   # the draft starts with a copy of the previous version's files
        call("DELETE", f"{api}/deposit/depositions/{draft['id']}/files/{f['id']}")
    upload(call, draft["links"]["bucket"], files)
    meta = {k: v for k, v in draft["metadata"].items() if k != "doi"}   # the previous version's DOI
    meta.update(changes, publication_date=datetime.date.today().isoformat())
    if not isinstance(meta.get("prereserve_doi"), dict):   # no version DOI reserved yet: ask for one
        meta["prereserve_doi"] = True
    return summary(call("PUT", draft["links"]["self"], json.dumps({"metadata": meta}).encode()), files)


def drop_creator(call, api, dep_id, name):
    """Stage a metadata edit of published deposition `dep_id` that removes creator `name`; leaves it unpublished.
    Refuses (before changing anything) if `name` is not a creator or is the only one."""
    url = f"{api}/deposit/depositions/{dep_id}"
    creators = call("GET", url)["metadata"]["creators"]
    kept = [c for c in creators if c["name"] != name]
    if len(kept) == len(creators):
        sys.exit(f"{name!r} is not a creator of {dep_id}: {[c['name'] for c in creators]}")
    if not kept:
        sys.exit(f"{name!r} is the only creator of {dep_id}; a record needs at least one")
    call("POST", f"{url}/actions/edit")
    meta = call("GET", url)["metadata"]
    meta["creators"] = [c for c in meta["creators"] if c["name"] != name]
    dep = call("PUT", url, json.dumps({"metadata": meta}).encode())
    return {"deposition_id": dep["id"], "doi": dep["metadata"].get("doi"), "edit_url": dep["links"]["html"],
            "creators": [c["name"] for c in dep["metadata"]["creators"]], "published": False}


def evidence_files():
    """The archive named in provenance.json (refused unless its SHA-256 matches), the manifest and provenance."""
    prov = json.load(open(os.path.join(EV, "provenance.json")))
    tgz = os.path.expanduser(f"~/pmxbench_evidence/{prov['archive']['file']}")
    h = hashlib.sha256()
    with open(tgz, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    if h.hexdigest() != prov["archive"]["sha256"]:
        sys.exit(f"{tgz}: SHA-256 does not match results/evidence/provenance.json; re-run harness/make_evidence.py")
    return [tgz, os.path.join(EV, "MANIFEST.sha256"), os.path.join(EV, "provenance.json")]


def main(argv):
    api = "https://sandbox.zenodo.org/api" if "--sandbox" in argv else "https://zenodo.org/api"
    arg = lambda flag: argv[argv.index(flag) + 1]
    if "--publish" in argv:
        r = http("POST", f"{api}/deposit/depositions/{arg('--publish')}/actions/publish")
        print("published:", r.get("doi"), r.get("links", {}).get("html"))
    elif "--drop-creator" in argv:
        i = argv.index("--drop-creator")
        print(json.dumps(drop_creator(http, api, argv[i + 1], argv[i + 2]), indent=1))
    elif "--new-version" in argv:
        print(json.dumps(new_version(http, api, arg("--new-version"), evidence_files(), V2), indent=1))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
