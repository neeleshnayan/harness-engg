# -*- coding: utf-8 -*-
"""Doc's 5-URL Tiingo probe (run-analyst-pituniverse spec), in the stated order.
Key supplied by the CEO 2026-08-23; read from env, never committed."""
import json, os, urllib.request, urllib.error

KEY = os.environ["TIINGO_KEY"]

def get(url):
    req = urllib.request.Request(url + f"&token={KEY}" if "?" in url else url + f"?token={KEY}",
                                 headers={"User-Agent": "krypton-probe"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]

def bars_summary(body):
    if not isinstance(body, list) or not body:
        return f"EMPTY/NON-LIST: {str(body)[:120]}"
    first, last = body[0], body[-1]
    return (f"{len(body)} bars | first {first.get('date','')[:10]} close {first.get('close')} "
            f"| last {last.get('date','')[:10]} close {last.get('close')}")

print("=== PROBE 1 (THE DECIDER): APC 2019-07-01..2019-09-01 — Anadarko ending 2019-08-08 ~\\$70, or ARKO/empty? ===")
s, b = get("https://api.tiingo.com/tiingo/daily/apc/prices?startDate=2019-07-01&endDate=2019-09-01")
print(s, "|", bars_summary(b))

print("=== PROBE 2: EMC 2016-08-01..2016-09-30 — EMC Corp ~\\$29 ending ~09-06, or Global X ETF? ===")
s, b = get("https://api.tiingo.com/tiingo/daily/emc/prices?startDate=2016-08-01&endDate=2016-09-30")
print(s, "|", bars_summary(b))

print("=== PROBE 3: CELG 2019-10-01..2019-12-31 — bars ending 2019-11-20..22 ~\\$108 (Yahoo 404s this) ===")
s, b = get("https://api.tiingo.com/tiingo/daily/celg/prices?startDate=2019-10-01&endDate=2019-12-31")
print(s, "|", bars_summary(b))

print("=== PROBE 4 (metadata control): TWX — expect startDate 1992-03-19, endDate 2018-06-15 ===")
s, b = get("https://api.tiingo.com/tiingo/daily/twx")
if isinstance(b, dict):
    print(s, "|", {k: b.get(k) for k in ("ticker", "name", "startDate", "endDate", "exchangeCode")})
else:
    print(s, "|", str(b)[:150])

print("=== PROBE 5 (ABSENCE CONTROL): BNI 2009-11-01..2010-02-28 — expect a clean 404, NOT a silent empty 200 ===")
s, b = get("https://api.tiingo.com/tiingo/daily/bni/prices?startDate=2009-11-01&endDate=2010-02-28")
print(s, "|", bars_summary(b) if isinstance(b, list) else str(b)[:150])
