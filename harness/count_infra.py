#!/usr/bin/env python3
"""Infrastructure footprint of the two stacks -> results/infra.csv (paper/SPEC.md slice S9, issue #11).

One row per counted item, columns stack, category, item, lines:
  file rows      category tool | serving | tests | instructions | other (see category()); item = path; lines =
                 non-blank, non-comment lines (Markdown and JSON: non-blank lines)
  container/port the docker-compose services and host port mappings
  service        what must be running before the agent starts: the container engine plus each container
  setup          the steps from a clean machine with the client installed to a working stack (SETUP, with sources)
  source         the version counted (PMxAgent git tag + commit; SHA-256 of skills/FROZEN.sha256)
summary() turns the rows into the table's numbers (paper/tables.py).
Reads only line counts, file paths and docker-compose service names and ports: no tool code is interpreted.
  Skills:   skills/<name>/{SKILL.md, scripts/, tests/}
  PMxAgent: pmxagent-main/ (their repo at v1.0.0, local only)
Usage: count_infra.py [--pmxagent pmxagent-main]
"""
import argparse, csv, hashlib, os, re, subprocess
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "infra.csv")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "renv", "dist", "build"}
# comment marker per counted file type; None = count every non-blank line; types not listed are not counted
EXT = {".R": "#", ".r": "#", ".py": "#", ".sh": "#", ".yml": "#", ".yaml": "#", ".toml": "#", ".txt": "#", ".ini": "#",
       ".cpp": "//", ".c": "//", ".h": "//", ".js": "//", ".ts": "//",
       ".md": None, ".json": None, ".cff": None, ".sha256": None}
NAME = {"Dockerfile": "#", "Makevars": "#", ".dockerignore": "#", ".gitignore": "#"}   # basename prefixes

PMX_TOOL = ("apis/endpoints/", "apis/models/", "apis/utils/")
PMX_TESTS = ("apis/tests/", "tests/")
PMX_TESTS_FILES = {"pytest.ini", "requirements-dev.txt"}
PMX_SERVING = ("docker/", ".github/")
PMX_SERVING_FILES = {"server.py", "apis/rapi.R", ".mcp.json", ".dockerignore", "requirements.txt"}

ENGINE = "Docker engine (README prerequisite: Docker Desktop, running)"
SETUP = {   # from a machine with Claude Code installed; PMxAgent from its README "Quick Start" and "Connect an AI Agent"
    "PMxAgent": ["Install and start Docker Desktop",
                 "Clone the repository",
                 "Build or pull the images and start the containers (docker compose up)",
                 "Connect the client to the MCP endpoint (.mcp.json in the repository, or the client's MCP settings)",
                 "Approve the one-time OAuth prompt on first connection"],
    "Skills": ["Install R and the R packages the scripts load",
               "Clone the repository",
               "Copy the skill folders into .claude/skills/"],
}
MEASURES = ["service", "container", "port", "setup", "tool", "serving", "tests", "instructions"]
LINES = {"tool", "serving", "tests", "instructions"}


def category(stack, rel):
    """Table row a maintained file belongs to: tool (analysis code), serving (API router, MCP server, containers,
    deployment and CI config), tests, instructions (what the agent reads), or other (docs, licences, bookkeeping:
    listed in infra.csv, not counted in the table). PMxAgent's endpoint modules count as tool code although they also
    carry the Plumber route annotations."""
    if stack == "Skills":
        parts = rel.split("/")
        if len(parts) == 2 and parts[1] == "SKILL.md":
            return "instructions"
        if len(parts) > 2 and parts[1] in ("scripts", "tests"):
            return {"scripts": "tool", "tests": "tests"}[parts[1]]
        return "other"
    if rel.startswith(PMX_TOOL):
        return "tool"
    if rel.startswith(PMX_TESTS) or rel in PMX_TESTS_FILES:
        return "tests"
    if rel.startswith(PMX_SERVING) or rel in PMX_SERVING_FILES or os.path.basename(rel).startswith("docker-compose"):
        return "serving"
    if rel == "CLAUDE.md":
        return "instructions"
    return "other"


def comment_marker(path):
    """(counted, marker): whether the file type is counted, and its line-comment marker (None: none)."""
    base = os.path.basename(path)
    for prefix, c in NAME.items():
        if base.startswith(prefix):
            return True, c
    ext = os.path.splitext(base)[1]
    return (ext in EXT), EXT.get(ext)


def sloc(path, marker):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return sum(1 for line in fh if line.strip() and not (marker and line.strip().startswith(marker)))


def files(top):
    """(relative path, lines) for every counted file under top, sorted."""
    out = []
    for d, dirs, names in os.walk(top):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
        for f in names:
            p = os.path.join(d, f)
            counted, marker = comment_marker(p)
            if counted:
                out.append((os.path.relpath(p, top).replace(os.sep, "/"), sloc(p, marker)))
    return sorted(out)


def compose(top):
    """Containers (compose service names) and host port mappings over every docker-compose file at the repo root
    (an overlay file names the same services again). Reads only the `services:` block's names and `ports:` lists."""
    names, ports = set(), set()
    for f in sorted(os.listdir(top)):
        if not (f.startswith("docker-compose") and f.endswith((".yml", ".yaml"))):
            continue
        inside = in_ports = False
        with open(os.path.join(top, f), encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        for line in lines:
            if re.match(r"^services:\s*$", line):
                inside = True; continue
            if inside and re.match(r"^\S", line):
                inside = False
            if not inside:
                continue
            m = re.match(r"^  ([A-Za-z0-9_.-]+):\s*$", line)
            if m:
                names.add(m.group(1)); in_ports = False; continue
            if re.match(r"^    ports:\s*$", line):
                in_ports = True; continue
            m = re.match(r"^\s+-\s*[\"']?([^\"'\s]+)[\"']?\s*$", line) if in_ports else None
            if m:
                ports.add(m.group(1))
            elif in_ports and line.strip() and not line.lstrip().startswith("#"):
                in_ports = False
    return {"container": sorted(names), "port": sorted(ports)}


def git_version(top):
    """`<tag> <commit>` of a git checkout, or '' when top is not one."""
    try:
        run = lambda *a: subprocess.run(["git", "-C", top, *a], capture_output=True, text=True, check=True).stdout.strip()
        return f"{run('describe', '--tags', '--always')} {run('rev-parse', 'HEAD')}"
    except (OSError, subprocess.CalledProcessError):
        return ""


def rows(skills_dir, pmx_dir):
    """Every counted item of both stacks (PMxAgent only when its repo is present)."""
    out = []
    add = lambda stack, cat, item, lines="": out.append({"stack": stack, "category": cat, "item": item, "lines": lines})
    frozen = os.path.join(skills_dir, "FROZEN.sha256")
    if os.path.exists(frozen):
        with open(frozen, "rb") as fh:
            add("Skills", "source", "FROZEN.sha256 sha256:" + hashlib.sha256(fh.read()).hexdigest())
    for rel, n in files(skills_dir):
        add("Skills", category("Skills", rel), rel, n)
    for step in SETUP["Skills"]:
        add("Skills", "setup", step)
    if not os.path.isdir(pmx_dir):
        return out
    add("PMxAgent", "source", git_version(pmx_dir))
    for rel, n in files(pmx_dir):
        add("PMxAgent", category("PMxAgent", rel), rel, n)
    dc = compose(pmx_dir)
    for kind in ("container", "port"):
        for item in dc[kind]:
            add("PMxAgent", kind, item)
    for item in ([ENGINE] if dc["container"] else []) + dc["container"]:
        add("PMxAgent", "service", item)
    for step in SETUP["PMxAgent"]:
        add("PMxAgent", "setup", step)
    return out


def summary(rs):
    """{stack: {measure: number}}: item counts for service/container/port/setup, summed lines for the file
    categories (MEASURES); category `other` and `source` are not counted."""
    out = {}
    for r in rs:
        s = out.setdefault(r["stack"], dict.fromkeys(MEASURES, 0))
        if r["category"] in LINES:
            s[r["category"]] += int(r["lines"])
        elif r["category"] in s:
            s[r["category"]] += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pmxagent", default=os.path.join(ROOT, "pmxagent-main"))
    a = ap.parse_args()
    rs = rows(os.path.join(ROOT, "skills"), a.pmxagent)
    if not os.path.isdir(a.pmxagent):
        print(f"PMxAgent repo not found at {a.pmxagent}; counting Skills only")
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["stack", "category", "item", "lines"]); w.writeheader(); w.writerows(rs)
    for stack, m in summary(rs).items():
        print(f"{stack:9s} " + " ".join(f"{k}={v}" for k, v in m.items()))
    print("wrote", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
