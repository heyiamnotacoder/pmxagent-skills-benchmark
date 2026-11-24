#!/usr/bin/env python3
"""Is the built manuscript ready for bioRxiv? (paper/SPEC.md slice S14, issue #16)

Fails if main.tex still has a \\TODO outside comments, if line numbers are off, if an \\includegraphics file is missing,
or if the LaTeX log reports an undefined reference or citation, stale cross-references or a missing file.
Usage: check_biorxiv.py [paper_dir]   (default: this file's folder; reads main.tex and main.log). Exit 1 on any problem.
"""
import os, re, sys

LOG_PROBLEMS = [
    (re.compile(r"Reference `[^']+' on page \d+ undefined"), "undefined reference"),
    (re.compile(r"Citation `[^']+' on page \d+ undefined"), "undefined citation"),
    (re.compile(r"There were undefined (references|citations)"), "undefined references"),
    (re.compile(r"Rerun to get cross-references right"), "cross-references not settled (rerun LaTeX)"),
    (re.compile(r"LaTeX Error: File `[^']+' not found"), "missing file"),
]


def strip_comments(tex):
    """Drop %-comments (an escaped \\% is kept)."""
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in tex.splitlines())


def problems(tex, log, paper_dir):
    """Every reason the PDF built from `tex` (with LaTeX log `log`, figures under `paper_dir`) is not ready."""
    body = strip_comments(tex)
    out = []
    if "\\TODO" in body:
        out.append("main.tex: \\TODO left in the text")
    if not re.search(r"^\s*\\linenumbers\b", body, re.M):
        out.append("main.tex: line numbers are off (\\linenumbers missing)")
    for fig in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", body):
        if not os.path.exists(os.path.join(paper_dir, fig)):
            out.append(f"main.tex: figure file missing: {fig}")
    for line in log.splitlines():
        for pat, what in LOG_PROBLEMS:
            if pat.search(line):
                out.append(f"main.log: {what}: {line.strip()}")
    return out


def main(argv):
    d = argv[0] if argv else os.path.dirname(os.path.abspath(__file__))
    tex = open(os.path.join(d, "main.tex")).read()
    log = open(os.path.join(d, "main.log"), errors="replace").read()
    found = problems(tex, log, d)
    for p in found:
        print("NOT READY:", p)
    if not found:
        print("ready: no TODOs, no undefined references, all figures present, line numbers on")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
