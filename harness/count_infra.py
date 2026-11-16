#!/usr/bin/env python3
"""Infrastructure footprint of the two stacks -> results/infra.csv (paper/PLAN.md R5).

Counts only (lines, files, services); no file content is interpreted beyond docker-compose service names.
  Skills:   skills/<name>/{SKILL.md, scripts/, tests/}
  PMxAgent: pmxagent-main/ (their repo, local only), grouped by top-level directory and file type.
Non-blank, non-comment lines for code files; non-blank lines for Markdown/YAML.
Usage: count_infra.py [--pmxagent pmxagent-main]
"""
import argparse, csv, os, re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE = {".R": "#", ".r": "#", ".py": "#", ".sh": "#", ".js": "//", ".ts": "//", ".tsx": "//"}
TEXT = {".md", ".yml", ".yaml", ".toml", ".json", ".txt"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "renv", "dist", "build"}


def kind(path):
    base = os.path.basename(path)
    if base.startswith("Dockerfile") or base.startswith("docker-compose"):
        return "container"
    ext = os.path.splitext(base)[1]
    if ext in CODE:
        return "code" + ext.lower()
    if ext in TEXT:
        return "text" + ext.lower()
    return None


def sloc(path):
    ext = os.path.splitext(path)[1]
    c = CODE.get(ext)
    n = 0
    try:
        for line in open(path, encoding="utf-8", errors="replace"):
            s = line.strip()
            if s and not (c and s.startswith(c)):
                n += 1
    except OSError:
        pass
    return n


def walk(top):
    for d, dirs, files in os.walk(top):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            p = os.path.join(d, f)
            k = kind(p)
            if k:
                yield p, k


def compose_services(top):
    names = set()
    for p, k in walk(top):
        if os.path.basename(p).startswith("docker-compose") and p.endswith((".yml", ".yaml")):
            inside = False
            for line in open(p, encoding="utf-8", errors="replace"):
                if re.match(r"^services:\s*$", line):
                    inside = True; continue
                if inside and re.match(r"^\S", line):
                    inside = False
                m = re.match(r"^  ([A-Za-z0-9_.-]+):\s*$", line) if inside else None
                if m:
                    names.add(m.group(1))
    return sorted(names)


def tally(top, group_depth):
    agg = defaultdict(lambda: [0, 0])
    for p, k in walk(top):
        rel = os.path.relpath(p, top).split(os.sep)
        grp = "/".join(rel[:min(group_depth, len(rel) - 1)]) or "(root)"
        agg[(grp, k)][0] += 1
        agg[(grp, k)][1] += sloc(p)
    return agg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pmxagent", default=os.path.join(ROOT, "pmxagent-main"))
    a = ap.parse_args()
    rows = []
    for (grp, k), (nf, nl) in sorted(tally(os.path.join(ROOT, "skills"), 2).items()):
        rows.append({"stack": "Skills", "group": grp, "kind": k, "files": nf, "lines": nl})
    if os.path.isdir(a.pmxagent):
        for (grp, k), (nf, nl) in sorted(tally(a.pmxagent, 2).items()):
            rows.append({"stack": "PMxAgent", "group": grp, "kind": k, "files": nf, "lines": nl})
        svc = compose_services(a.pmxagent)
        rows.append({"stack": "PMxAgent", "group": "docker-compose services", "kind": "services",
                     "files": len(svc), "lines": ";".join(svc)})
    else:
        print(f"PMxAgent repo not found at {a.pmxagent}; counting Skills only")
    rows.append({"stack": "Skills", "group": "runtime services", "kind": "services", "files": 0, "lines": ""})
    out = os.path.join(ROOT, "results", "infra.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["stack", "group", "kind", "files", "lines"]); w.writeheader(); w.writerows(rows)
    tot = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["kind"] != "services":
            tot[(r["stack"], r["kind"].split(".")[0])][0] += r["files"]
            tot[(r["stack"], r["kind"].split(".")[0])][1] += r["lines"]
    for (s, k), (nf, nl) in sorted(tot.items()):
        print(f"{s:9s} {k:10s} files={nf:4d} lines={nl}")
    print("wrote", os.path.relpath(out, ROOT))


if __name__ == "__main__":
    main()
