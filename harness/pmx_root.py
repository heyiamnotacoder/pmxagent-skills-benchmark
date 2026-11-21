"""The shared top level of A1's PMxAgent folders (logs/deviations.md §20).

PMxAgent's tools write their outputs to the top of its `/data/` and `/figures/` mounts, not into the rep's own
`/data/<runid>/` folder. On this machine those mounts are one pair of folders shared by every A1 rep, so files an
earlier rep's tools wrote stayed visible to later reps. The harness therefore, per A1 rep (one at a time, under
`exclusive`): moves anything left at that top level out of reach before the agent starts (`move_leftovers` into the
archive's `_stray/` folder), moves what the rep's tools wrote there into the rep's own archive after it ends, and
writes `RECORD` into the rep's raw folder. Nothing is ever deleted or overwritten. Stdlib only.
"""
import contextlib, fcntl, json, os, shutil

SHARED = ("data", "figures")   # PMxAgent's host-mounted output folders (docker-compose.yml volumes)
KEEP = {".gitkeep"}
RECORD = "pmx_root.json"
LOCK = ".a1_rep.lock"


class Busy(Exception):
    """Another A1 rep holds the PMxAgent folders: two A1 reps at once would move each other's files."""


def leftovers(pmx, own):
    """Top-level entries of the shared folders, as "data/<name>" paths, except .gitkeep and the rep's own folder."""
    out = []
    for sub in SHARED:
        d = os.path.join(pmx, sub)
        if os.path.isdir(d):
            out += [f"{sub}/{n}" for n in sorted(os.listdir(d)) if n not in KEEP and n != own]
    return out


def move_leftovers(pmx, own, dest):
    """Move every `leftovers` entry to dest/<same path>; refuse (moving nothing) if any target already exists."""
    moved = leftovers(pmx, own)
    clash = [p for p in moved if os.path.lexists(os.path.join(dest, p))]
    if clash:
        raise FileExistsError(f"would overwrite in {dest}: {clash}")
    for p in moved:
        os.makedirs(os.path.dirname(os.path.join(dest, p)), exist_ok=True)
        shutil.move(os.path.join(pmx, p), os.path.join(dest, p))
    return moved


@contextlib.contextmanager
def exclusive(pmx):
    """Hold the A1 rep lock for the PMxAgent folders; Busy if another rep holds it."""
    f = open(os.path.join(pmx, LOCK), "a")
    try:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Busy(f"another A1 rep is using {pmx} (lock {LOCK})") from None
        yield
    finally:
        f.close()


def write_record(raw, stray, collected):
    """Evidence for the audit: the shared folders were emptied before the agent started."""
    json.dump({"emptied_before_start": True, "stray_at_start": stray, "collected_after": collected},
              open(os.path.join(raw, RECORD), "w"), indent=1)


def started_clean(raw):
    """True if the run in raw folder `raw` started with the shared PMxAgent folders emptied (RECORD present)."""
    try:
        return json.load(open(os.path.join(raw, RECORD))).get("emptied_before_start") is True
    except (OSError, ValueError):
        return False
