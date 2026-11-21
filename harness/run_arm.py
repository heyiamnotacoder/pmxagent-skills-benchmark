#!/usr/bin/env python3
"""Run one arm x task x reps headlessly with Claude Code, each rep in a fresh git worktree.

Isolation
  - each arm has its own repo at RUNS/<arm>/base holding only `ws/<task>` branches. RUNS must be outside the user's
    home: Claude Code reads CLAUDE.md and .claude/rules/ from every ancestor of its working directory, so a workspace
    under ~ loads ~/.claude/CLAUDE.md and ~/.claude/rules/ as ancestor project instructions, whatever
    --setting-sources says (this was T1's accepted leak).
    (task inputs + that arm's skills). Nothing from this project repo is reachable from it.
  - each rep = `git worktree add --detach` of ws/<task>; outputs are copied back to
    results/raw/ here and never committed to the arm repo, so later reps cannot see earlier ones.
  - finished reps are moved (git worktree move) to ~/pmxbench_archive/<arm>/ (dirs mode 0300: not listable), and
    A1's /data/<runid> host folder with them, so a running agent has no sibling run folders to browse.
  - A1: PMxAgent's tools write to the top of its shared /data/ and /figures/ folders, not to /data/<runid>/. Each A1
    rep holds a lock (one A1 rep at a time), finds those folders emptied before it starts (leftovers go to
    ~/pmxbench_archive/A1/_stray/<runid>/), and what its tools wrote there is moved into its own archived data
    folder (_pmx_root/) when it ends; raw/pmx_root.json records both (pmx_root.py, logs/deviations.md §20).
  - claude flags: --setting-sources project (no user settings/plugins/hooks), --strict-mcp-config, an explicit
    --allowedTools list (allowed_tools; the scrub below forces permission mode `default`), git/web tools disallowed.
    `preflight` checks what actually leaks into context and that a tool really runs.
  - user config: `--setting-sources project` still loads ~/.claude/CLAUDE.md and ~/.claude/rules/. If a subscription
    token from `claude setup-token` is in the account pool (tokens.py), each rep instead gets its own empty HOME (with the Claude
    config dir inside it; archived with the rep): CLAUDE_CONFIG_DIR alone is not enough, user CLAUDE.md/rules are
    found via HOME. So no user instructions load and no earlier session files are reachable. PATH is inherited; R and
    Python libraries are system-wide (none under HOME).
  - environment: each rep gets only ENV_KEEP from the launcher's environment (plus HOME/auth). A launcher that is
    itself a Claude Code session (desktop app, IDE) exports ~35 CLAUDE_*/ANTHROPIC_* variables, including a proxy
    base URL that injects the host session's instructions into child sessions; none of these reach a rep. The ledger's
    `claude_config` column records which mode a run used. The token is passed by environment only, never logged,
    and CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 keeps it out of the agent's own Bash/R/Python subprocesses.

Accounts (tokens.py)
  - a rep uses the first pool account not at its usage limit (ledger `auth_label`). A rep stopped by HTTP 429 marks its
    account limited until the reported reset; with --until the arm goes on with the next free account and stops only
    when every account is limited. Rate-limited reps never count (deviations §1), whichever account ran them.

Usage
  run_arm.py setup   <arm>                      build/refresh the arm repo + ws branches
  run_arm.py run     <arm> <task> <reps> <model> [--timeout-min 90] [--until] [--allow-version-drift]
  run_arm.py preflight <arm> <model> [<task>]   one cheap probe run on <task>'s pinned Claude Code (default T1_nca):
                                                lists skills/MCP/instructions seen; exits non-zero unless one Bash
                                                call ran, nothing was denied and every tool shown is allowed
Exit codes: 0 done · 75 (EXIT_LIMIT) stopped on a usage limit / API failure, re-run later · other: broken, needs a human
Arms: A0 plain | A1 PMxAgent MCP | A1b PMxAgent MCP + shipped CLAUDE.md (§21) | A2 knowledge-only skills | A3 skills+scripts | A4 = A3 (small model)
"""
import argparse, csv, fcntl, datetime, hashlib, json, os, re, shutil, subprocess, sys, time, urllib.request
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger, pmx_root, tokens

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.environ.get("PMXBENCH_RUNS", "/Users/Shared/pmxbench_runs")   # outside ~ (see Isolation)
PMX = os.path.expanduser("~/pmxbench_runs/_pmxagent")   # under ~: colima only mounts the home folder
ARCHIVE = os.path.expanduser("~/pmxbench_archive")
SKILLS = os.path.join(ROOT, "skills")
TASKS = os.path.join(ROOT, "tasks")
RAW = os.path.join(ROOT, "results", "raw")
LEDGER = os.path.join(ROOT, "results", "runs.csv")
VERSIONS = os.path.join(ROOT, "env", "versions.txt")   # pinned toolchain; `claude-code-pin <task>:` lines
CLAUDE_DIR = os.path.expanduser(os.environ.get("PMXBENCH_CLAUDE_DIR", "~/.local/share/pmxbench/claude"))
ARMS = {"A0": None, "A1": None, "A1b": "pmx_docs", "A2": "knowledge", "A3": "scripts", "A4": "scripts"}
PMX_ARMS = frozenset({"A1", "A1b"})   # arms wired to the live PMxAgent MCP server and its shared /data/+/figures/
PMX_CLAUDE_MD_SHA256 = "1ebc55d43c4a3142ed50b2c78efcea22c67bed522f3bc4d81a6bf379e295be8c"   # PMxAgent v1.0.0 CLAUDE.md
ENV_KEEP = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TMPDIR", "USER", "LOGNAME", "SHELL")
MCP_TOKEN = "pmxagent-ci-token"   # PMxAgent's documented CI token (docker-compose.yml MCP_TEST_TOKEN)
# Tool permissions (see allowed_tools). BUILTIN_TOOLS = the init-event tool list of the valid T2 reps (2.1.310).
BUILTIN_TOOLS = ("Bash", "CronCreate", "CronDelete", "CronList", "DesignSync", "Edit", "EnterWorktree", "ExitWorktree",
                 "ListAgents", "Monitor", "NotebookEdit", "PushNotification", "Read", "RemoteTrigger", "ReportFindings",
                 "ScheduleWakeup", "SendMessage", "Skill", "Task", "TaskCreate", "TaskGet", "TaskList", "TaskStop",
                 "TaskUpdate", "ToolSearch", "Workflow", "Write")
MCP_TOOLS = ("mcp__pmxagent", "ListMcpResourcesTool", "ReadMcpResourceTool", "ReadMcpResourceDirTool")
DISALLOWED = ("WebSearch", "WebFetch", "Bash(git:*)", "Bash(gh:*)")
PREFLIGHT_FILE = "preflight.txt"
PREFLIGHT_DENIED = "git --version"   # must be denied by DISALLOWED, proving deny rules beat the allow-list
FORCED_MODE_WARNING = "Permission mode forced"

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


def pmx_claude_md_path():
    """Path to PMxAgent v1.0.0's shipped CLAUDE.md (used by secondary arm A1b, deviations §21)."""
    for p in (os.path.join(PMX, "CLAUDE.md"), os.path.join(ROOT, "pmxagent-main", "CLAUDE.md")):
        if os.path.isfile(p):
            return p
    sys.exit(f"PMxAgent CLAUDE.md not found under {PMX} or {os.path.join(ROOT, 'pmxagent-main')}")


def verify_pmx_claude_md(path=None):
    """Verify PMxAgent's shipped CLAUDE.md matches the pinned v1.0.0 SHA-256; return its path."""
    p = path or pmx_claude_md_path()
    have = hashlib.sha256(open(p, "rb").read()).hexdigest()
    if have != PMX_CLAUDE_MD_SHA256:
        sys.exit(f"PMxAgent CLAUDE.md SHA-256 mismatch at {p}: got {have}, expected {PMX_CLAUDE_MD_SHA256}")
    return p


def setup(arm):
    base = os.path.join(RUNS, arm, "base")
    os.makedirs(base, exist_ok=True)
    if not os.path.isdir(os.path.join(base, ".git")):
        sh(["git", "init", "-q", "-b", "empty", base])
        sh(["git", "-C", base, "commit", "-q", "--allow-empty", "-m", "empty"])
    pmx_doc = verify_pmx_claude_md() if ARMS[arm] == "pmx_docs" else None
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
        if os.path.isdir(os.path.join(tdir, "inputs")):   # T2/T3d have none (git does not track empty dirs)
            shutil.copytree(os.path.join(tdir, "inputs"), os.path.join(base, "inputs"))
        os.makedirs(os.path.join(base, "output"))
        open(os.path.join(base, "output", ".gitkeep"), "w").close()
        if ARMS[arm] in ("knowledge", "scripts"):
            skill_tree(ARMS[arm], base)
        elif pmx_doc:
            shutil.copyfile(pmx_doc, os.path.join(base, "CLAUDE.md"))
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


def allowed_tools(arm):
    """Explicit allow-list for one arm: every built-in tool plus, for PMxAgent arms (A1/A1b), the PMxAgent MCP server.

    CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 (run_env) forces the permission mode to `default`, so bypassPermissions is
    ignored and a headless run denies every tool that is not allowed here (logs/deviations.md §16). The list is the
    tool set the valid reps so far were shown (init event, 2.1.310), so allowing all of it keeps the earlier
    bypassPermissions behaviour; DISALLOWED still wins. `preflight` fails if the agent is shown a tool not covered."""
    return BUILTIN_TOOLS + (MCP_TOOLS if arm in PMX_ARMS else ())


def uncovered_tools(tools, allowed):
    """Tools the agent is shown that no allow rule covers (an `mcp__<server>` rule covers that server's tools)."""
    return [t for t in tools if t not in allowed and not any(t.startswith(a + "__") for a in allowed
                                                             if a.startswith("mcp__"))]


def claude_cmd(arm, model, wt, exe="claude"):
    cmd = [exe, "-p", "--model", model, "--output-format", "stream-json", "--verbose",
           "--setting-sources", "project", "--strict-mcp-config", "--no-chrome",
           "--permission-mode", "default",   # what the scrub forces anyway; stated so the command says what runs
           "--allowedTools", *allowed_tools(arm),
           "--disallowedTools", *DISALLOWED]
    if arm in PMX_ARMS:
        cfg = os.path.join(wt, "..", f"{os.path.basename(wt)}.mcp.json")
        json.dump({"mcpServers": {"pmxagent": {"type": "http", "url": "http://localhost:8000/mcp",
                                               "headers": {"Authorization": f"Bearer {MCP_TOKEN}"}}}},
                  open(cfg, "w"))
        cmd += ["--mcp-config", os.path.abspath(cfg)]
    return cmd


def check_run_root(root=None):
    """Refuse to run unless no ancestor of RUNS can inject instructions and RUNS is private to this user.

    Claude Code reads CLAUDE.md / .claude/ from every ancestor of a rep's working directory, and RUNS sits under a
    world-writable parent (/Users/Shared), so this is checked before every run, not once."""
    root = os.path.realpath(root or RUNS)
    os.makedirs(root, mode=0o700, exist_ok=True)
    st = os.stat(root)
    if st.st_uid != os.getuid() or st.st_mode & 0o077:
        sys.exit(f"{root} must be owned by you with mode 0700 (chmod 700 {root})")
    d = root
    while True:
        d = os.path.dirname(d)
        bad = [n for n in ("CLAUDE.md", "CLAUDE.local.md", ".claude") if os.path.lexists(os.path.join(d, n))]
        if bad:
            sys.exit(f"instruction files in an ancestor of {root}: {[os.path.join(d, n) for n in bad]}")
        if d == os.path.dirname(d):
            return root


def run_env(wt, auth):
    """Environment for one rep. auth = tokens.Account from the pool: isolated mode, fresh HOME + config dir next to
    the worktree. auth None (no pool): keychain login, user mode."""
    env = {k: os.environ[k] for k in ENV_KEEP if k in os.environ}
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    env["DISABLE_AUTOUPDATER"] = "1"   # a rep must not update the pinned binary under itself
    env["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"] = "1"   # the agent's Bash/R/Python never see Anthropic credentials
    if auth is None:
        env["HOME"] = os.environ["HOME"]   # keychain login, user CLAUDE.md loads (T1 mode)
        return env, "user"
    home = wt + ".home"
    os.makedirs(os.path.join(home, ".claude"), mode=0o700)
    env.update(HOME=home, CLAUDE_CONFIG_DIR=os.path.join(home, ".claude"),
               CLAUDE_CODE_OAUTH_TOKEN=auth.token)
    return env, "isolated"


def append_ledger(row):
    """Append under a lock; if the row brings new columns, rewrite the file with the union header."""
    with open(LEDGER, "a+", newline="") as f:
        fcntl.flock(f, fcntl.LOCK_EX)   # arms run in parallel
        f.seek(0)
        old = list(csv.DictReader(f))
        cols = list(old[0]) if old else []
        if not old or any(k not in cols for k in row):
            cols += [k for k in row if k not in cols]
            f.seek(0); f.truncate()
            w = csv.DictWriter(f, fieldnames=cols, restval="")
            w.writeheader(); w.writerows(old)
        else:
            w = csv.DictWriter(f, fieldnames=cols, restval="")
        w.writerow(row)


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
                      (wt + ".mcp.json", runid + ".mcp.json"), (wt + ".home", runid + ".home")):
        if os.path.exists(src):
            shutil.move(src, os.path.join(dest, name))


def pinned_claude_version(task):
    """Claude Code version pinned for `task`: `claude-code-pin <task>:` line, else `claude-code-pin default:`.
    Every arm of one task runs on one version (logs/deviations.md §15)."""
    pins = {}
    with open(VERSIONS) as f:
        for line in f:
            m = re.match(r"\s*claude-code-pin\s+(\S+):\s*(\S+)", line)
            if m:
                pins[m.group(1)] = m.group(2)
    pin = pins.get(task) or pins.get("default")
    if not pin:
        sys.exit(f"no 'claude-code-pin {task}:' or 'claude-code-pin default:' line in {os.path.relpath(VERSIONS, ROOT)}")
    return pin


def claude_exe(version):
    """Harness-owned pinned binary if installed (immune to the native installer's updates and clean-up), else PATH."""
    for rel in ("claude", os.path.join("node_modules", ".bin", "claude")):
        p = os.path.join(CLAUDE_DIR, version, rel)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return "claude"


def check_claude_version(task, allow_drift=False):
    """Resolve the Claude Code binary for `task` and refuse it unless it reports the pinned version.
    Called before anything is created or written, so a refused run leaves no trace. Returns the binary to use."""
    pin = pinned_claude_version(task)
    exe = claude_exe(pin)
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as e:
        sys.exit(f"cannot run `{exe} --version`: {e}")
    have = out.split()[0] if out else "(unknown)"
    if have == pin:
        return exe
    msg = f"Claude Code {have} ({exe}) found, but {task} runs are pinned to {pin} (env/versions.txt)."
    if not allow_drift:
        sys.exit(f"{msg}\nInstall the pinned version privately: npm install --prefix {os.path.join(CLAUDE_DIR, pin)} "
                 f"@anthropic-ai/claude-code@{pin}, or pass --allow-version-drift and log the drift in "
                 f"logs/deviations.md.")
    print(f"WARNING: {msg} Proceeding because of --allow-version-drift: log this in logs/deviations.md.",
          file=sys.stderr, flush=True)
    return exe


def rep_state(arm, task, ledger_rows, live_names, excluded=frozenset()):
    """(valid + in-progress reps, highest rep number used) for arm x task. Rep 0 is a preflight probe: its ledger
    row and any leftover worktree folder never count toward --until. Excluded runs (results/exclusions.csv) do not
    count either, but keep their rep numbers, so new reps never reuse one."""
    rows = [r for r in ledger_rows if r["arm"] == arm and r["task"] == task and r["rep"] != "0"]
    live = [d for d in live_names if d.startswith(f"{arm}_{task}_r") and not d.endswith((".mcp.json", ".home"))]
    live_reps = [int(d[len(f"{arm}_{task}_r"):][:2]) for d in live]
    live_reps = [r for r in live_reps if r != 0]
    return sum(ledger.valid(r, excluded) for r in rows) + len(live_reps), max([int(r["rep"]) for r in rows] + live_reps or [0])


def rate_limited(status):
    """A usage-limit (HTTP 429) stop, mid-run or instant (ledger status labels, deviations §1)."""
    return ledger.rate_limited({"status": status})


def run_status(proc_status, res):
    """Ledger status: a usage-limit (HTTP 429) stop gets the deviations-§1 label, not the bare exit code."""
    if res.get("api_error_status") == 429:
        return "failed_ratelimit_midrun" if res.get("total_cost_usd") else "failed_ratelimit"
    return proc_status


EXIT_LIMIT = 75   # EX_TEMPFAIL: stopped on a usage limit / API failure; resume_lanes.sh waits and re-runs


def limit_stop(msg):
    """Stop because of a usage limit or API failure, with the exit code the lane scripts treat as "try again later"."""
    print(msg, file=sys.stderr, flush=True)
    sys.exit(EXIT_LIMIT)


class AccountsLimited(Exception):
    """Every pool account is at its usage limit; the message says until when."""


def pick_account(pool):
    """tokens.Account for the next rep; None without a pool; AccountsLimited if every account is limited."""
    if not pool:
        return None
    auth = pool.pick()
    if auth is None:
        raise AccountsLimited(f"every account is at its usage limit until {time.ctime(pool.next_free())}")
    return auth


def next_step(row, limited, switches, pool):
    """--until after one rep -> (action, limited, switches). action: "go" (next rep), "switch" (this account is now
    limited or unusable and another is free: next rep on it), "stop" (all limited, or two instant API failures).
    switches is bounded by the pool size, so a stale reset time can never make the loop spin."""
    r = {k: str(v) for k, v in row.items()}
    if ledger.completed(r) or ledger.arm_failure(r):   # a counted rep, the arm's own failure included (§22)
        return "go", 0, 0
    hit = rate_limited(row["status"])
    bad_account = row.get("api_error_status") in tokens.AUTH_FAIL_STATUS
    if not (hit or bad_account or not row["cost_usd"]):   # timeout / crash after real work: not an account problem
        return "go", limited, switches
    limited += 1
    if (hit or bad_account) and pool and pool.has_free() and switches < len(pool.paths):
        return "switch", limited, switches + 1
    return ("stop" if hit or bad_account or limited >= 2 else "go"), limited, switches


def run_once(arm, task, rep, model, prompt, timeout_min, suffix=True, exe="claude", pool=None):
    if arm not in PMX_ARMS:
        return run_rep(arm, task, rep, model, prompt, timeout_min, suffix, exe, pool)
    with pmx_root.exclusive(PMX):   # the shared PMxAgent folders belong to one PMxAgent rep at a time (§20)
        return run_rep(arm, task, rep, model, prompt, timeout_min, suffix, exe, pool)


def run_rep(arm, task, rep, model, prompt, timeout_min, suffix, exe, pool):
    auth = pick_account(pool)   # before any worktree exists, so an all-limited stop leaves nothing behind
    base = os.path.join(RUNS, arm, "base")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    runid = f"{arm}_{task}_r{rep:02d}_{stamp}"
    if arm in PMX_ARMS:   # before the agent can see anything: an earlier rep's PMxAgent outputs go out of reach
        stray = pmx_root.move_leftovers(PMX, runid, os.path.join(ARCHIVE, arm, "_stray", runid))
        if stray:
            os.chmod(os.path.join(ARCHIVE, arm, "_stray"), 0o300)   # like the archive: enter/write but not list
    wt = os.path.join(RUNS, arm, "runs", runid)
    os.makedirs(os.path.dirname(wt), exist_ok=True)
    sh(["git", "-C", base, "worktree", "add", "-q", "--detach", wt, f"ws/{task}"])
    head = sh(["git", "-C", wt, "rev-parse", "HEAD"]).strip()
    full_prompt = prompt + (SUFFIX if suffix else "")
    if arm in PMX_ARMS and suffix:
        host = os.path.join(PMX, "data", runid)
        if os.path.isdir(os.path.join(wt, "inputs")):
            shutil.copytree(os.path.join(wt, "inputs"), host)
        else:   # task without input files (git does not track the empty dir)
            os.makedirs(host)
        full_prompt += SUFFIX_A1.format(runid=runid, host=host)
    raw = raw_dir(arm, task, runid, preflight=not suffix)
    os.makedirs(raw)
    open(os.path.join(raw, "prompt.txt"), "w").write(full_prompt)
    env, config_mode = run_env(wt, auth)
    t0 = time.time()
    status = "ok"
    with open(os.path.join(raw, "transcript.jsonl"), "w") as tr, open(os.path.join(raw, "stderr.txt"), "w") as er:
        try:
            p = subprocess.run(claude_cmd(arm, model, wt, exe), input=full_prompt, cwd=wt, stdout=tr, stderr=er,
                               text=True, timeout=timeout_min * 60, env=env)
            if p.returncode != 0:
                status = f"exit{p.returncode}"
        except subprocess.TimeoutExpired:
            status = "timeout"
    wall = time.time() - t0
    shutil.copytree(os.path.join(wt, "output"), os.path.join(raw, "output"), dirs_exist_ok=True)
    if arm in PMX_ARMS:   # what the tools wrote at the shared top level joins the rep's own data folder
        collected = pmx_root.move_leftovers(PMX, runid, os.path.join(PMX, "data", runid, "_pmx_root"))
        pmx_root.write_record(raw, stray, collected)
        if os.path.isdir(os.path.join(PMX, "data", runid)):
            shutil.copytree(os.path.join(PMX, "data", runid), os.path.join(raw, "pmxagent_data"), dirs_exist_ok=True)
    hashes = sha_dir(os.path.join(raw, "output"))
    json.dump(hashes, open(os.path.join(raw, "output_sha256.json"), "w"), indent=1)
    tr = parse_transcript(os.path.join(raw, "transcript.jsonl"))
    res = tr.result
    u = res.get("usage", {})
    row = {"runid": runid, "arm": arm, "task": task, "rep": rep, "model": model,
           "model_seen": ",".join(sorted((res.get("modelUsage") or {}).keys())), "status": run_status(status, res),
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
           "tool_calls": tr.tool_calls, "tool_errors": tr.tool_errors, "n_output_files": len(hashes),
           "ws_commit": head[:12], "claude_version": sh([exe, "--version"]).strip().split()[0],
           "claude_config": config_mode, "permission_mode": tr.init.get("permissionMode"),
           "permission_denials": tr.permission_denials, "auth_label": auth.label if auth else "",
           "api_error_status": res.get("api_error_status")}
    append_ledger(row)
    archive(arm, runid)   # preflights too: a leftover worktree must not look like a rep in progress
    if pool:
        pool.after_rep(row["auth_label"], rate_limited(row["status"]), row["api_error_status"],
                       os.path.join(raw, "transcript.jsonl"))
    print(json.dumps(row), flush=True)
    if tr.denied and suffix:   # recorded, never an exclusion (SPEC.md); a run of these means the permissions broke
        print(f"WARNING {runid}: {tr.permission_denials} permission denial(s): {tr.denied}", file=sys.stderr, flush=True)
    return row


def raw_dir(arm, task, runid, preflight=False):
    """Where a run's transcript, stderr and output copies live (preflights apart, so they never look like reps)."""
    return os.path.join(RAW, arm, "_preflight" if preflight else task, runid)


class Transcript(NamedTuple):
    init: dict                # the system/init event: tools shown, permissionMode, ...
    result: dict              # the final result event: usage, cost, is_error, ...
    tool_calls: int
    tool_errors: int
    denied: list              # one entry per permission denial: the Bash command, else the tool name

    @property
    def permission_denials(self):
        return len(self.denied)


def parse_transcript(path):
    """Counts and the init/result events of one stream-json transcript (unparseable lines are skipped)."""
    init, result, calls, errors = {}, {}, 0, 0
    for line in open(path):
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            init = ev
        if ev.get("type") == "result":
            result = ev
        if ev.get("type") == "assistant":
            calls += sum(1 for c in ev.get("message", {}).get("content", []) if c.get("type") == "tool_use")
        if ev.get("type") == "user":
            c = ev.get("message", {}).get("content", [])
            errors += sum(1 for x in c if isinstance(x, dict) and x.get("type") == "tool_result" and x.get("is_error"))
    denied = [(d.get("tool_name") == "Bash" and (d.get("tool_input") or {}).get("command")) or d.get("tool_name")
              for d in result.get("permission_denials") or []]
    return Transcript(init, result, calls, errors, denied)


def preflight_problems(arm, raw):
    """Why the preflight probe in folder `raw` shows the arm cannot run its tools (empty list = fine)."""
    tr = parse_transcript(os.path.join(raw, "transcript.jsonl"))
    stderr = open(os.path.join(raw, "stderr.txt")).read()
    problems = []
    if not tr.init:
        problems.append("no init event in the transcript")
    if missing := uncovered_tools(tr.init.get("tools", []), allowed_tools(arm)):
        problems.append(f"tools shown to the agent but not allowed: {missing} (update BUILTIN_TOOLS and log it)")
    if unexpected := [d for d in tr.denied if d != PREFLIGHT_DENIED]:
        problems.append(f"permission denied: {unexpected}")
    if PREFLIGHT_DENIED not in tr.denied:
        problems.append(f"`{PREFLIGHT_DENIED}` was not denied: the --disallowedTools git rule no longer wins")
    if FORCED_MODE_WARNING in stderr:   # Claude Code's wording; the denial and probe-file checks do not depend on it
        problems.append("stderr: " + next(l for l in stderr.splitlines() if FORCED_MODE_WARNING in l).strip())
    if not os.path.isfile(os.path.join(raw, "output", PREFLIGHT_FILE)):
        problems.append(f"probe file output/{PREFLIGHT_FILE} was not written")
    return problems


def preflight(arm, model, task, exe):
    """One cheap probe on `task`'s pinned binary: a Bash call that must run, one that must be denied (git), then
    what the agent sees in context. Exits non-zero unless the first ran, only the git call was denied and every tool
    shown is allowed."""
    prompt = (f"Use the Bash tool twice, once for each command: (a) mkdir -p output && echo ok > output/{PREFLIGHT_FILE}"
              f"  (b) {PREFLIGHT_DENIED}\n"
              "Then, without using any other tool, list as short bullet lists: (1) every skill available to you, "
              "(2) every MCP server and MCP tool available, (3) any CLAUDE.md, rules or memory instructions in "
              "your context (quote their first line), (4) your exact model id.")
    row = run_once(arm, task, 0, model, prompt, 5, suffix=False, exe=exe, pool=tokens.Pool.load())
    if rate_limited(row["status"]):   # the probe itself hit a 429: not a broken setup, try again later
        limit_stop(f"preflight {arm}: usage limit on account {row['auth_label'] or '(keychain)'}")
    if problems := preflight_problems(arm, raw_dir(arm, task, row["runid"], preflight=True)):
        sys.exit(f"PREFLIGHT FAILED {row['runid']}:\n  " + "\n  ".join(problems))
    print(f"preflight ok: {arm} on Claude Code {row['claude_version']}: a tool ran, only `{PREFLIGHT_DENIED}` was "
          f"denied, every tool shown is allowed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["setup", "run", "preflight"])
    ap.add_argument("arm", choices=list(ARMS))
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--timeout-min", type=int, default=90)
    ap.add_argument("--until", action="store_true",
                    help="treat <reps> as the target number of valid reps; run only the shortfall")
    ap.add_argument("--allow-version-drift", action="store_true",
                    help="run even if Claude Code differs from env/versions.txt (log it in logs/deviations.md)")
    a = ap.parse_args()
    os.umask(0o077)   # rep worktrees, homes and raw copies private to this user
    check_run_root()
    if a.cmd == "setup":
        return setup(a.arm)
    probe_task = (a.rest[1] if len(a.rest) > 1 else "T1_nca") if a.cmd == "preflight" else None
    exe = check_claude_version(probe_task or a.rest[0], a.allow_version_drift)
    frozen = os.path.join(SKILLS, "FROZEN.sha256")
    if a.arm in ("A2", "A3", "A4"):
        chk = subprocess.run(["shasum", "-a", "256", "-c", frozen], cwd=SKILLS, capture_output=True, text=True)
        if chk.returncode != 0:
            sys.exit("skills changed since freeze (skills/FROZEN.sha256) - log in logs/skill_changes.md and re-freeze")
    if ARMS[a.arm] == "pmx_docs":
        verify_pmx_claude_md()
    if a.arm in PMX_ARMS and not pmx_healthy():
        sys.exit("PMxAgent stack not reachable on :5762 - start it (see harness/pmxagent.sh up)")
    if a.cmd == "preflight":
        try:
            return preflight(a.arm, a.rest[0], probe_task, exe)
        except AccountsLimited as e:
            limit_stop(f"preflight {a.arm}: usage limit - {e}")
    task, reps, model = a.rest[0], int(a.rest[1]), a.rest[2]
    prompt = open(os.path.join(TASKS, task, "prompt.md")).read().strip()
    pool = tokens.Pool.load()
    if not pool:
        print("WARNING: no account token (harness/tokens.py): reps use the keychain login and load user instructions",
              file=sys.stderr, flush=True)
    if not a.until:
        try:
            for rep in range(1, reps + 1):
                run_once(a.arm, task, rep, model, prompt, a.timeout_min, exe=exe, pool=pool)
        except AccountsLimited as e:
            limit_stop(f"{a.arm} {task}: usage limit / API failure - {e}")
        return
    def state():   # re-read each time: another session may be topping up the same arm
        live_dir = os.path.join(RUNS, a.arm, "runs")
        return rep_state(a.arm, task, list(csv.DictReader(open(LEDGER))),
                         os.listdir(live_dir) if os.path.isdir(live_dir) else [], ledger.exclusions())
    limited = switches = 0
    have, rep = state()
    print(f"{a.arm} {task}: {have} valid or in-progress reps, target {reps}", flush=True)
    while have < reps:
        try:
            row = run_once(a.arm, task, rep + 1, model, prompt, a.timeout_min, exe=exe, pool=pool)
        except AccountsLimited as e:
            limit_stop(f"{a.arm} {task}: usage limit / API failure - stopping at {have}/{reps} valid reps; {e}")
        have, rep = state()
        step, limited, switches = next_step(row, limited, switches, pool)
        if step == "switch":
            print(f"{a.arm} {task}: account {row['auth_label']} limited or unusable - switching account", flush=True)
        elif step == "stop":
            limit_stop(f"{a.arm} {task}: usage limit / API failure - stopping at {have}/{reps} valid reps")


if __name__ == "__main__":
    main()
