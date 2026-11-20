#!/usr/bin/env python3
"""Subscription accounts for benchmark reps (paper/SPEC.md decisions 2026-11-20; logs/deviations.md §19).

Each account's `claude setup-token` token is one file in TOKENS_DIR, named by a label (`acct1`, `acct2`, ...; the label
is recorded in the ledger, the token never is). A rep uses the first account, in label order, that is not at its usage
limit. When a rep stops on HTTP 429, its account is marked limited until the reset time the API reported, in
LIMITS_FILE (labels and epochs only, locked: both lanes share it). No TOKENS_DIR: the single TOKEN_FILE of the T1/T2
setup is the pool, as `default`. Neither: an empty pool, and reps use the keychain login (T1 mode, user CLAUDE.md loads).

  tokens.py status      accounts and when each is free
  tokens.py next-free   epoch when an account is next free (now if one is)
Stdlib only.
"""
import fcntl, json, os, re, sys, time

CONF = os.path.expanduser("~/.config/pmxbench")
TOKENS_DIR = os.path.expanduser(os.environ.get("PMXBENCH_TOKENS_DIR", os.path.join(CONF, "tokens")))
TOKEN_FILE = os.path.expanduser(os.environ.get("PMXBENCH_OAUTH_TOKEN_FILE", os.path.join(CONF, "oauth_token")))
LIMITS_FILE = os.path.expanduser(os.environ.get("PMXBENCH_LIMITS_FILE", os.path.join(CONF, "limits.json")))
DEFAULT_WAIT_S = 3600   # a 429 without a reported reset time


class Pool:
    def __init__(self, paths, limits_file):
        self.paths = dict(sorted(paths.items()))   # label -> token file
        self.limits_file = limits_file

    @classmethod
    def load(cls, tokens_dir=TOKENS_DIR, single_file=TOKEN_FILE, limits_file=LIMITS_FILE):
        paths = {}
        if os.path.isdir(tokens_dir):
            paths = {f: os.path.join(tokens_dir, f) for f in os.listdir(tokens_dir)
                     if not f.startswith(".") and os.path.isfile(os.path.join(tokens_dir, f))}
        if not paths and os.path.isfile(single_file):
            paths = {"default": single_file}
        return cls(paths, limits_file)

    def __bool__(self):
        return bool(self.paths)

    def _limits(self):
        try:
            with open(self.limits_file) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def pick(self, now=None):
        """(label, token) of the first account not at its usage limit, or None."""
        now = time.time() if now is None else now
        limits = self._limits()
        for label, path in self.paths.items():
            if limits.get(label, 0) <= now:
                return label, open(path).read().strip()
        return None

    def mark_limited(self, label, resets_at):
        os.makedirs(os.path.dirname(self.limits_file) or ".", exist_ok=True)
        with open(self.limits_file, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.seek(0)
            try:
                limits = json.loads(f.read() or "{}")
            except ValueError:
                limits = {}
            limits[label] = max(int(resets_at), limits.get(label, 0))
            f.seek(0); f.truncate()
            json.dump(limits, f)

    def next_free(self, now=None):
        """Epoch when an account is next free: now if one already is."""
        now = time.time() if now is None else now
        limits = self._limits()
        return min(max(limits.get(lab, 0), now) for lab in self.paths) if self.paths else now


def reset_time(transcript):
    """Latest `resetsAt` (epoch) a usage-limit response reported in a rep's transcript, or None."""
    try:
        found = re.findall(r'"resetsAt"\s*:\s*(\d+)', open(transcript, errors="replace").read())
    except OSError:
        return None
    return max(map(int, found)) if found else None


def main():
    pool, now = Pool.load(), time.time()
    if sys.argv[1:] == ["next-free"]:
        print(int(pool.next_free(now)))
    elif sys.argv[1:] == ["status"]:
        limits = pool._limits()
        for label in pool.paths or ["(none: keychain login)"]:
            until = limits.get(label, 0)
            print(f"{label}: " + (f"limited until {time.ctime(until)}" if until > now else "free"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
