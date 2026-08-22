#!/usr/bin/env bash
# Start the spine in TEST mode — simulated fills at REAL prices, on a
# SEPARATE but fully PERSISTENT ledger.
#
# Renamed from run_local.sh on 2026-08-22, and the rename is the point.
# "Local" described where the data was; the thing that mattered was that the
# data was DISPOSABLE. USE_FAKE_FIRESTORE isolated test work from the real
# ledger — correct — by making the record ephemeral, which is how 552 events
# (seq 161-712) came to live in memory while the status endpoint reported
# successful mirroring hourly.
#
# Isolation and durability are orthogonal, and the old flag treated them as one
# thing. Test mode now writes to krypton_fund_test on the SAME Postgres
# instance: same schema, same append-only discipline, same fold code, same
# durability monitoring. What differs is which store, and nothing else.
#
# That matters beyond tidiness. A persistent test ledger makes a test run a
# RECORD rather than exhaust — you can ask what a test did last week, and you
# can compare a replay of 2020-03 run today against the same replay run after a
# harness change. An ephemeral test ledger makes the replay engine measure
# nothing twice, and the whole value of replaying history is the comparison.
#
#   ./scripts/run_test.sh
#
set -euo pipefail

cd "$(dirname "$0")/.."

# ONE switch, both dimensions: simulated venue + krypton_fund_test.
export FUND_MODE=test
export FUND_STORE=postgres          # no default exists; this must be said
# Anything but "production" so nothing can label this book the real fund.
# app/core/firebase.py additionally REFUSES to open a real Firestore client
# while the mode is test — the interlock USE_FAKE_FIRESTORE used to key, kept
# and re-keyed rather than deleted with the flag, because the state it guards
# against did not stop existing.
export FUND_ENV=test
# Fills are simulated; the prices they fill at are real.
export FUND_LIVE_MARKS=true
# The demo seeder must never invent positions on a book with real fills in it.
export DISABLE_DEMO_SEED=1

PY=./venv/Scripts/python.exe
[ -x "$PY" ] || PY=python

echo "spine: mode=test | orders -> simulated (real prices) | events -> krypton_fund_test"
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8090}"
