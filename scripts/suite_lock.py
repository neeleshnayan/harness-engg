"""Run a pytest suite under an EXCLUSIVE cross-process lock.

Why this exists (2026-08-24, measured, not cautious). The constitution already
requires that two concurrent builders SERIALIZE their full test-suite runs.
Nothing enforced it, so builders serialized on a free-RAM window instead — and
**a RAM window does not serialize Postgres**. On 2026-08-24 builder HW3 saw 36
tests go red across three Postgres-backed modules with NO defect behind any of
them: `assert count() == 0` immediately after a `TRUNCATE`, while a second
builder's process truncated the same database.

The shared resource is a NAME. `krypton_fund_test` is a constant in ten test
modules; two builders create the same database and wreck each other's rows.
The structural fix is to namespace the database per worktree (ticketed). This
is the cheap, correct one: make the serialization the rule already demands
actually happen.

Usage (builders call this INSTEAD of pytest for a full-suite run):

    python scripts/suite_lock.py -- tests/ -q
    python scripts/suite_lock.py --timeout 3600 -- tests/ -q

It prints who holds the lock while waiting, so a blocked suite is legible
rather than mysterious. The lock is released even if pytest fails; a stale
lock older than `--stale-after` seconds is broken with a loud warning, because
a crashed builder must not block the fund's test suite forever.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

LOCK = Path(os.getenv("TEMP", "/tmp")) / "krypton_suite.lock"


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception:
        return "(unreadable)"


def acquire(timeout: int, stale_after: int, who: str) -> bool:
    """Exclusive create, or wait. Returns True when held."""
    start = time.time()
    announced = False
    while True:
        try:
            fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as f:
                f.write(f"{who}\npid={os.getpid()}\nat={time.time():.0f}\n")
            return True
        except FileExistsError:
            held = _read(LOCK)
            age = time.time() - LOCK.stat().st_mtime if LOCK.exists() else 0
            if age > stale_after:
                print(f"WARNING: breaking a stale suite lock ({age:.0f}s old), "
                      f"held by:\n{held}", flush=True)
                try:
                    LOCK.unlink()
                except FileNotFoundError:
                    pass
                continue
            if not announced:
                print(f"waiting for the suite lock ({age:.0f}s old), held by:\n"
                      f"{held}", flush=True)
                announced = True
            if time.time() - start > timeout:
                print(f"TIMED OUT after {timeout}s waiting for the suite lock. "
                      f"NOT running the suite — a result taken beside another "
                      f"builder's Postgres truncations is uninterpretable, "
                      f"which is the whole reason this lock exists.")
                return False
            time.sleep(5)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=2700,
                    help="seconds to wait for the lock (default 45 min)")
    ap.add_argument("--stale-after", type=int, default=3600,
                    help="break a lock older than this (default 60 min)")
    ap.add_argument("--who", default=os.getenv("KF_BUILDER", "unnamed"),
                    help="who is running, for the waiter's message")
    ap.add_argument("rest", nargs=argparse.REMAINDER,
                    help="-- then the pytest arguments")
    a = ap.parse_args()
    args = [x for x in a.rest if x != "--"] or ["tests/", "-q"]

    who = f"{a.who} in {Path.cwd()}"
    if not acquire(a.timeout, a.stale_after, who):
        return 3
    print(f"suite lock HELD by {who}", flush=True)
    try:
        return subprocess.call([sys.executable, "-m", "pytest", *args])
    finally:
        try:
            LOCK.unlink()
            print("suite lock released", flush=True)
        except FileNotFoundError:
            print("suite lock was already gone (broken as stale?)", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
