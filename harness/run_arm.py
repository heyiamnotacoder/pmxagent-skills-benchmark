#!/usr/bin/env python3
"""Run one arm x task x reps headlessly with Claude Code, each rep in a fresh git worktree.

Isolation
  - each arm has its own repo at ~/pmxbench_runs/<arm>/base holding only `ws/<task>` branches
    (task inputs + that arm's skills). Nothing from this project repo is reachable from it.
  - each rep = `git worktree add --detach` of ws/<task>; outputs are copied back to
    results/raw/ here and never committed to the arm repo, so later reps cannot see earlier ones.
  - finished reps are moved (git worktree move) to ~/pmxbench_archive/<arm>/ (dirs mode 0300: not listable), and
    A1's /data/<runid> host folder with them, so a running agent has no sibling run folders to browse.
  - claude flags: --setting-sources project (no user settings/plugins/hooks), --strict-mcp-config,
    git/web tools disallowed. `preflight` checks what actually leaks into context.

Usage
  run_arm.py setup   <arm>                      build/refresh the arm repo + ws branches
  run_arm.py run     <arm> <task> <reps> <model> [--timeout-min 90]
  run_arm.py preflight <arm> <model>            one cheap probe run: lists skills/MCP/instructions seen
Arms: A0 plain | A1 PMxAgent MCP | A2 knowledge-only skills | A3 skills+scripts | A4 = A3 (small model)
"""
import argparse, csv, fcntl, datetime, hashlib, json, os, re, shutil, subprocess, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.expanduser("~/pmxbench_runs")
PMX = os.path.join(RUNS, "_pmxagent")
ARCHIVE = os.path.expanduser("~/pmxbench_archive")
SKILLS = os.path.join(ROOT, "skills")
TASKS = os.path.join(ROOT, "tasks")
RAW = os.path.join(ROOT, "results", "raw")
LEDGER = os.path.join(ROOT, "results", "runs.csv")
ARMS = {"A0": None, "A1": None, "A2": "knowledge", "A3": "scripts", "A4": "scripts"}
MCP_TOKEN = "pmxagent-ci-token"   # PMxAgent's documented CI token (docker-compose.yml MCP_TEST_TOKEN)

SUFFIX = ("\n\n---\nWork autonomously in the current directory and do not ask questions. "
          "Input files are in `inputs/`. Save all output files in `output/`.")
SUFFIX_A1 = ("\nThe input files are also available to the PMxAgent tools at `/data/{runid}/`. Files the tools "
             "write under `/data/` appear on this machine under `{host}/`.")


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw).stdout


def skill_tree(kind, dest):
    """Copy skills into dest/.claude/skills. kind=scripts: SKILL.md + scripts/; knowledge: SKILL.md minus script sections."""
    for name in sorted(os.listdir(SKILLS)):
        src = os.path.join(SKILLS, name)
        if not os.path.isfile(os.path.join(src, "SKILL.md")):
            continue
        out = os.path.join(dest, ".claude", "skills", name)
        os.makedirs(out, exist_ok=True)
        md = open(os.path.join(src, "SKILL.md")).read()
        if kind == "knowledge":
            md = re.sub(r"<!-- scripts:start -->.*?<!-- scripts:end -->\n?", "", md, flags=re.S)
        else:
            md = md.replace("<!-- scripts:start -->\n", "").replace("<!-- scripts:end -->\n", "")
            shutil.copytree(os.path.join(src, "scripts"), os.path.join(out, "scripts"), dirs_exist_ok=True)
            md = md.replace("<skill_dir>", f".claude/skills/{name}")
        open(os.path.join(out, "SKILL.md"), "w").write(md)


def setup(arm):
    base = os.path.join(RUNS, arm, "base")
    os.makedirs(base, exist_ok=True)
    if not os.path.isdir(os.path.join(base, ".git")):
        sh(["git", "init", "-q", "-b", "empty", base])
        sh(["git", "-C", base, "commit", "-q", "--allow-empty", "-m", "empty"])
    for task in sorted(os.listdir(TASKS)):
        tdir = os.path.join(TASKS, task)
        if not os.path.isfile(os.path.join(tdir, "prompt.md")):
            continue
        sh(["git", "-C", base, "checkout", "-q", "--orphan", "tmp_build"])
        sh(["git", "-C", base, "rm", "-rq", "--cached", "--ignore-unmatch", "."])
        for p in os.listdir(base):
            if p != ".git":
                q = os.path.join(base, p)
                shutil.rmtree(q) if os.path.isdir(q) else os.remove(q)
        shutil.copytree(os.path.join(tdir, "inputs"), os.path.join(base, "inputs"))
        os.makedirs(os.path.join(base, "output"))
        open(os.path.join(base, "output", ".gitkeep"), "w").close()
        if ARMS[arm]:
            skill_tree(ARMS[arm], base)
        sh(["git", "-C", base, "add", "-A"])
        sh(["git", "-C", base, "-c", "user.name=pmxbench", "-c", "user.email=pmxbench@local", "commit", "-q",
            "-m", f"{arm} workspace for {task}"])
        sh(["git", "-C", base, "branch", "-f", f"ws/{task}"])
        sh(["git", "-C", base, "checkout", "-q", "empty"])
        sh(["git", "-C", base, "branch", "-D", "tmp_build"])
        for p in os.listdir(base):
            if p != ".git":
                q = os.path.join(base, p)
                shutil.rmtree(q) if os.path.isdir(q) else os.remove(q)
    print(sh(["git", "-C", base, "branch", "-v"]))


def pmx_healthy():
    try:
        req = urllib.request.Request("http://localhost:5762/__docs__/")
        return urllib.request.urlopen(req, timeout=5).status == 200
    except Exception:
        return False


def claude_cmd(arm, model, wt):
    cmd = ["claude", "-p", "--model", model, "--output-format", "stream-json", "--verbose",
           "--setting-sources", "project", "--strict-mcp-config", "--no-chrome",
           "--permission-mode", "bypassPermissions",
           "--disallowedTools", "WebSearch", "WebFetch", "Bash(git:*)", "Bash(gh:*)"]
    if arm == "A1":
        cfg = os.path.join(wt, "..", f"{os.path.basename(wt)}.mcp.json")
        json.dump({"mcpServers": {"pmxagent": {"type": "http", "url": "http://localhost:8000/mcp",
                                               "headers": {"Authorization": f"Bearer {MCP_TOKEN}"}}}},
                  open(cfg, "w"))
        cmd += ["--mcp-config", os.path.abspath(cfg)]
    return cmd


def sha_dir(d):
    out = {}
    for dp, _, fs in os.walk(d):
        for f in sorted(fs):
            p = os.path.join(dp, f)
            out[os.path.relpath(p, d)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def archive(arm, runid):
    """Move a finished rep (worktree, A1 data + mcp config) out of the live runs area; nothing is deleted."""
    dest = os.path.join(ARCHIVE, arm)
    os.makedirs(dest, exist_ok=True)
    os.chmod(ARCHIVE, 0o300); os.chmod(dest, 0o300)   # enter/write but not list
    wt = os.path.join(RUNS, arm, "runs", runid)
    if os.path.isdir(wt):
        sh(["git", "-C", os.path.join(RUNS, arm, "base"), "worktree", "move", wt, os.path.join(dest, runid)])
    for src, name in ((os.path.join(PMX, "data", runid), runid + ".pmxagent_data"),
                      (wt + ".mcp.json", runid + ".mcp.json")):
        if os.path.exists(src):
            shutil.move(src, os.path.join(dest, name))


def valid(r):
    return r["status"] == "ok" and r["is_error"] != "True"


def run_once(arm, task, rep, model, prompt, timeout_min, suffix=True):
    base = os.path.join(RUNS, arm, "base")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    runid = f"{arm}_{task}_r{rep:02d}_{stamp}"
    wt = os.path.join(RUNS, arm, "runs", runid)
    os.makedirs(os.path.dirname(wt), exist_ok=True)
    sh(["git", "-C", base, "worktree", "add", "-q", "--detach", wt, f"ws/{task}"])
    head = sh(["git", "-C", wt, "rev-parse", "HEAD"]).strip()
    full_prompt = prompt + (SUFFIX if suffix else "")
    if arm == "A1" and suffix:
        host = os.path.join(PMX, "data", runid)
        if os.path.isdir(os.path.join(wt, "inputs")):
            shutil.copytree(os.path.join(wt, "inputs"), host)
        else:   # task without input files (git does not track the empty dir)
            os.makedirs(host)
        full_prompt += SUFFIX_A1.format(runid=runid, host=host)
    raw = os.path.join(RAW, arm, task if suffix else "_preflight", runid)
    os.makedirs(raw)
    open(os.path.join(raw, "prompt.txt"), "w").write(full_prompt)
    t0 = time.time()
    status = "ok"
    with open(os.path.join(raw, "transcript.jsonl"), "w") as tr, open(os.path.join(raw, "stderr.txt"), "w") as er:
        try:
            p = subprocess.run(claude_cmd(arm, model, wt), input=full_prompt, cwd=wt, stdout=tr, stderr=er,
                               text=True, timeout=timeout_min * 60, env={**os.environ, "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"})
            if p.returncode != 0:
                status = f"exit{p.returncode}"
        except subprocess.TimeoutExpired:
            status = "timeout"
    wall = time.time() - t0
    shutil.copytree(os.path.join(wt, "output"), os.path.join(raw, "output"), dirs_exist_ok=True)
    if arm == "A1" and suffix:
        shutil.copytree(os.path.join(PMX, "data", runid), os.path.join(raw, "pmxagent_data"), dirs_exist_ok=True)
    hashes = sha_dir(os.path.join(raw, "output"))
    json.dump(hashes, open(os.path.join(raw, "output_sha256.json"), "w"), indent=1)
    res, tools, tool_err = {}, 0, 0
    for line in open(os.path.join(raw, "transcript.jsonl")):
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "result":
            res = ev
        if ev.get("type") == "assistant":
            tools += sum(1 for c in ev.get("message", {}).get("content", []) if c.get("type") == "tool_use")
        if ev.get("type") == "user":
            c = ev.get("message", {}).get("content", [])
            tool_err += sum(1 for x in c if isinstance(x, dict) and x.get("type") == "tool_result" and x.get("is_error"))
    u = res.get("usage", {})
    row = {"runid": runid, "arm": arm, "task": task, "rep": rep, "model": model,
           "model_seen": ",".join(sorted((res.get("modelUsage") or {}).keys())), "status": status,
           "is_error": res.get("is_error"), "cost_usd": res.get("total_cost_usd"), "num_turns": res.get("num_turns"),
           "duration_s": round(wall, 1), "api_duration_s": (res.get("duration_api_ms") or 0) / 1000,
           "input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"),
           "cache_read_tokens": u.get("cache_read_input_tokens"), "cache_write_tokens": u.get("cache_creation_input_tokens"),
           "cache_write_1h_tokens": (u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens"),
           "cache_write_5m_tokens": (u.get("cache_creation") or {}).get("ephemeral_5m_input_tokens"),
           "thinking_tokens": (u.get("output_tokens_details") or {}).get("thinking_tokens"),
           "model_usage_json": json.dumps({m: {k: v.get(k) for k in ("inputTokens", "outputTokens", "cacheReadInputTokens",
                                               "cacheCreationInputTokens", "costUSD")}
                                           for m, v in (res.get("modelUsage") or {}).items()}, separators=(",", ":")),
           "tool_calls": tools, "tool_errors": tool_err, "n_output_files": len(hashes), "ws_commit": head[:12],
           "claude_version": sh(["claude", "--version"]).strip().split()[0]}
    new = not os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="") as f:
        fcntl.flock(f, fcntl.LOCK_EX)   # arms run in parallel
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)
    if suffix:
        archive(arm, runid)
    row["_limited"] = res.get("api_error_status") == 429   # not in ledger
    print(json.dumps(row), flush=True)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["setup", "run", "preflight"])
    ap.add_argument("arm", choices=list(ARMS))
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--timeout-min", type=int, default=90)
    ap.add_argument("--until", action="store_true",
                    help="treat <reps> as the target number of valid reps; run only the shortfall")
    a = ap.parse_args()
    if a.cmd == "setup":
        return setup(a.arm)
    frozen = os.path.join(SKILLS, "FROZEN.sha256")
    if a.arm in ("A2", "A3", "A4"):
        chk = subprocess.run(["shasum", "-a", "256", "-c", frozen], cwd=SKILLS, capture_output=True, text=True)
        if chk.returncode != 0:
            sys.exit("skills changed since freeze (skills/FROZEN.sha256) - log in logs/skill_changes.md and re-freeze")
    if a.arm == "A1" and not pmx_healthy():
        sys.exit("PMxAgent stack not reachable on :5762 - start it (see harness/pmxagent.sh up)")
    if a.cmd == "preflight":
        model = a.rest[0]
        prompt = ("Do not use any tools. List, as short bullet lists: (1) every skill available to you, (2) every MCP "
                  "server and MCP tool available, (3) any CLAUDE.md, rules or memory instructions in your context "
                  "(quote their first line), (4) your exact model id.")
        return run_once(a.arm, "T1_nca", 0, model, prompt, 5, suffix=False)
    task, reps, model = a.rest[0], int(a.rest[1]), a.rest[2]
    prompt = open(os.path.join(TASKS, task, "prompt.md")).read().strip()
    if not a.until:
        for rep in range(1, reps + 1):
            run_once(a.arm, task, rep, model, prompt, a.timeout_min)
        return
    def state():   # re-read each time: another session may be topping up the same arm
        rows = [r for r in csv.DictReader(open(LEDGER)) if r["arm"] == a.arm and r["task"] == task and r["rep"] != "0"]
        live = [d for d in os.listdir(os.path.join(RUNS, a.arm, "runs")) if d.startswith(f"{a.arm}_{task}_r")
                and not d.endswith(".mcp.json")] if os.path.isdir(os.path.join(RUNS, a.arm, "runs")) else []
        reps_used = [int(r["rep"]) for r in rows] + [int(d.split("_r")[-1][:2]) for d in live]
        return sum(valid(r) for r in rows) + len(live), max(reps_used or [0])
    limited = 0
    have, rep = state()
    print(f"{a.arm} {task}: {have} valid or in-progress reps, target {reps}", flush=True)
    while have < reps:
        row = run_once(a.arm, task, rep + 1, model, prompt, a.timeout_min)
        have, rep = state()
        if valid({k: str(v) for k, v in row.items()}):
            limited = 0
        elif row["_limited"] or not row["cost_usd"]:   # usage limit (429) or instant API failure
            limited += 1
            if row["_limited"] or limited >= 2:
                sys.exit(f"{a.arm} {task}: usage limit / API failure - stopping at {have}/{reps} valid reps")


if __name__ == "__main__":
    main()
