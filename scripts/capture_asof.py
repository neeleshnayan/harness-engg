"""Capture point-in-time listing membership and the names that vanished.

Run once per as-of date you want to reason about. Rate-limited by the vendor's
free tier (four calls a minute, blocking), so this takes minutes, not seconds —
run it in the background and read the log.
"""
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("FUND_STORE", "postgres")

from app.fund.asof import AsOfUniverse  # noqa: E402

AS_OF = sys.argv[1] if len(sys.argv) > 1 else "2025-01-01"

u = AsOfUniverse()
print(f"capturing listing membership as of {AS_OF} ...", flush=True)
print(json.dumps(u.snapshot(AS_OF), indent=1), flush=True)

print(f"\ncapturing names delisted since {AS_OF} ...", flush=True)
print(json.dumps(u.capture_delisted(AS_OF), indent=1), flush=True)

print("\nsnapshots held:", json.dumps(u.snapshots(), indent=1), flush=True)
vanished = u.vanished_since(AS_OF)
print(f"\nlisted on {AS_OF} but absent from today's reference: {len(vanished)}",
      flush=True)
for v in vanished[:15]:
    print(f"  {v['ticker']:8s} {str(v['name'])[:44]:44s} "
          f"delisted {str(v['delisted_utc'])[:10]}", flush=True)
