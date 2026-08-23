# -*- coding: utf-8 -*-
"""Backfill the 125 USABLE delisted S&P leavers from Tiingo (free tier discipline).

- Throttle: 74s between requests (<50/hr). ~2.6h for 125 names.
- Checkpointed: skips names already saved; safe to re-run.
- Probe-5 lesson: an empty-200 is recorded as UNKNOWN in the manifest, never as
  "no data existed". Absence is never zero.
- License: Internal Use Only (CEO-created key, internal research). Data lands in
  ClarkHarness/data/research/delisted_tiingo/ (private repo). The key comes from
  env and is never written to disk.
"""
import json, os, pathlib, time, urllib.request, urllib.error

KEY = os.environ["TIINGO_KEY"]
PIT = pathlib.Path(__file__).parent / "pit"
OUT = pathlib.Path(r"C:\Users\user\Documents\Krypton Fund\ClarkHarness\data\research\delisted_tiingo")
OUT.mkdir(parents=True, exist_ok=True)

usable = json.load(open(PIT / "tiingo_cls.json"))["USABLE"]
manifest_path = OUT / "_manifest.json"
manifest = json.load(open(manifest_path)) if manifest_path.exists() else {}

done = 0
for row in usable:
    tkr = row[0]
    safe = tkr.replace(".", "_")
    f = OUT / f"{safe}.json"
    if f.exists():
        continue
    url = (f"https://api.tiingo.com/tiingo/daily/{tkr.lower()}/prices"
           f"?startDate=1990-01-01&endDate=2026-08-23&token={KEY}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "krypton-backfill"})
        with urllib.request.urlopen(req, timeout=60) as r:
            body = json.loads(r.read().decode())
        if isinstance(body, list) and body:
            f.write_text(json.dumps(body))
            manifest[tkr] = {"bars": len(body), "first": body[0]["date"][:10],
                             "last": body[-1]["date"][:10], "status": "OK"}
            print(f"{tkr}: {len(body)} bars {body[0]['date'][:10]}..{body[-1]['date'][:10]}", flush=True)
        else:
            manifest[tkr] = {"status": "UNKNOWN-EMPTY-200",
                             "note": "empty 200 - absence is UNKNOWN, never zero (probe-5 lesson)"}
            print(f"{tkr}: UNKNOWN (empty 200)", flush=True)
    except urllib.error.HTTPError as e:
        manifest[tkr] = {"status": f"HTTP-{e.code}"}
        print(f"{tkr}: HTTP {e.code}", flush=True)
        if e.code == 429:
            print("RATE LIMITED - backing off 1h", flush=True)
            time.sleep(3600)
    except Exception as e:
        manifest[tkr] = {"status": f"ERROR: {e}"}
        print(f"{tkr}: ERROR {e}", flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=1))
    done += 1
    time.sleep(74)

ok = sum(1 for v in manifest.values() if v.get("status") == "OK")
unk = sum(1 for v in manifest.values() if v.get("status", "").startswith("UNKNOWN"))
print(f"BACKFILL COMPLETE: {ok} OK, {unk} UNKNOWN, {len(manifest)} total of {len(usable)} usable", flush=True)
