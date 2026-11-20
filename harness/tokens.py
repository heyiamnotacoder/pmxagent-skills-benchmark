#!/usr/bin/env python3
"""Subscription accounts for benchmark reps (paper/SPEC.md decisions 2026-11-20; logs/deviations.md §19).

Each account's `claude setup-token` token is one file in TOKENS_DIR named `acct<N>` (the label goes into the ledger and
the published evidence, the token never does; other file names are ignored, so no personal name or e-mail can become a
label). A rep uses the first account, in label order, that is free. When a rep stops on HTTP 429 its account is marked
limited until the reset time the API reported (clamped to 1 min .. 7 days ahead); a 401/403 marks it unusable for a day.
State is LIMITS_FILE (labels and epochs only), replaced atomically under a lock file, so the two lanes share it safely.
No `acct<N>` file: the single TOKEN_FILE of the T1/T2 setup is the pool, as `default`. Neither: an empty pool, and reps
use the keychain login (T1 mode, user CLAUDE.md loads).

  tokens.py status      accounts and when each is free
  tokens.py next-free   epoch when an account is next free (now if one is)
Stdlib only.
"""
import fcntl, json, os, re, sys, tempfile, time
from typing import NamedTuple, Optional

CONF = os.path.expanduser("~/.config/pmxbench")
TOKENS_DIR = os.path.expanduser(os.environ.get("PMXBENCH_TOKENS_DIR", os.path.join(CONF, "tokens")))
TOKEN_FILE = os.path.expanduser(os.environ.get("PMXBENCH_OAUTH_TOKEN_FILE", os.path.join(CONF, "oauth_token")))
LIMITS_FILE = os.path.expanduser(os.environ.get("PMXBENCH_LIMITS_FILE", os.path.join(CONF, "limits.json")))
LABEL = re.compile(r"acct\d+")
MIN_WAIT_S, DEFAULT_WAIT_S, MAX_WAIT_S = 60, 3600, 7 * 86400
AUTH_FAIL_WAIT_S = 86400   # a revoked or expired token: skip the account for a day
AUTH_FAIL_STATUS = (401, 403)


class Account(NamedTuple):
    label: str
    token: str


class Pool:
    def __init__(self, paths: dict, limits_file: str):
        self.paths = dict(sorted(paths.items(), key=lambda kv: (len(kv[0]), kv[0])))   # acct2 before acct10
        self.limits_file = limits_file

    @classmethod
    def load(cls, tokens_dir: str = TOKENS_DIR, single_file: str = TOKEN_FILE, limits_file: str = LIMITS_FILE) -> "Pool":
        paths = {}
        if os.path.isdir(tokens_dir):
            paths = {f: os.path.join(tokens_dir, f) for f in os.listdir(tokens_dir)
                     if LABEL.fullmatch(f) and os.path.isfile(os.path.join(tokens_dir, f))}
        if not paths and os.path.isfile(single_file):
            paths = {"default": single_file}
        return cls(paths, limits_file)

    def __bool__(self) -> bool:
        return bool(self.paths)

    def _limits(self) -> dict:
        try:
            with open(self.limits_file) as f:   # replaced atomically, so never seen half-written
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _free_labels(self, now: float) -> list:
        limits = self._limits()
        return [lab for lab in self.paths if limits.get(lab, 0) <= now]

    def has_free(self, now: Optional[float] = None) -> bool:
        return bool(self._free_labels(time.time() if now is None else now))

    def pick(self, now: Optional[float] = None) -> Optional[Account]:
        """The first free account with a non-empty token, or None."""
        for label in self._free_labels(time.time() if now is None else now):
            token = open(self.paths[label]).read().strip()
            if token:
                return Account(label, token)
        return None

    def mark_limited(self, label: str, until: float) -> None:
        os.makedirs(os.path.dirname(self.limits_file) or ".", exist_ok=True)
        with open(self.limits_file + ".lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            limits = self._limits()
            limits[label] = max(int(until), limits.get(label, 0))
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.limits_file) or ".", prefix=".limits.")
            with os.fdopen(fd, "w") as f:
                json.dump(limits, f)
            os.replace(tmp, self.limits_file)

    def after_rep(self, label: str, rate_limited: bool, api_status: Optional[int], transcript: str,
                  now: Optional[float] = None) -> None:
        """Record what a finished rep showed about its account: usage limit until the reported reset, or a bad token."""
        if not label:
            return
        now = time.time() if now is None else now
        if rate_limited:
            reported = reset_time(transcript)
            if reported and reported > 10 ** 12:   # milliseconds
                reported //= 1000
            until = reported if reported else now + DEFAULT_WAIT_S
            self.mark_limited(label, min(max(until, now + MIN_WAIT_S), now + MAX_WAIT_S))
        elif api_status in AUTH_FAIL_STATUS:
            self.mark_limited(label, now + AUTH_FAIL_WAIT_S)

    def next_free(self, now: Optional[float] = None) -> float:
        """Epoch when an account is next free: now if one already is."""
        now = time.time() if now is None else now
        limits = self._limits()
        return min(max(limits.get(lab, 0), now) for lab in self.paths) if self.paths else now


def reset_time(transcript: str) -> Optional[int]:
    """Latest `resetsAt` of a *rejected* rate-limit response in a rep's transcript, or None."""
    try:
        text = open(transcript, errors="replace").read()
    except OSError:
        return None
    found = [int(m.group(2)) for m in re.finditer(r'"status"\s*:\s*"(rejected)"[^{}]*?"resetsAt"\s*:\s*(\d+)', text)]
    return max(found) if found else None


def main() -> None:
    pool, now = Pool.load(), time.time()
    if sys.argv[1:] == ["next-free"]:
        print(int(pool.next_free(now)))
    elif sys.argv[1:] == ["status"]:
        limits = pool._limits()
        for label in pool.paths or ["(none: keychain login, user instructions load)"]:
            until = limits.get(label, 0)
            print(f"{label}: " + (f"limited until {time.ctime(until)}" if until > now else "free"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
