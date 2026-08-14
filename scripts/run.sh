#!/usr/bin/env bash
# Start the spine against the PRODUCTION ledger.
#
# This is the normal way to run the fund now. The local file-backed ledger was
# retired on 2026-08-14 when its 52 events were promoted into Firestore, so
# every event — proposals, approvals, fills, NAV strikes — lands in one
# auditable place with a hash chain over it.
#
# The safety property this script relies on is in app/main.py: with
# FUND_ENV=production, a Firebase init failure REFUSES to start rather than
# falling back to a local file. A fund that stops is a problem you notice; a
# fund that silently relocates its ledger is one you notice at the audit.
#
#   ./scripts/run.sh
#
# For deliberate offline work, use ./scripts/run_local.sh instead — it is
# explicit about being a rehearsal.
set -euo pipefail

cd "$(dirname "$0")/.."

# Everything below is the .env default; stated here so the configuration is
# visible at the point of use rather than only in a file nobody opens.
export USE_FAKE_FIRESTORE=0
export FUND_ENV=production
export DISABLE_DEMO_SEED=1          # never invent positions on a real book
# Orders go to the Alpaca PAPER venue. Where state lives and where orders go
# stay separate decisions, and this is the pairing the fund actually runs:
# a real ledger and a paper venue.
export FUND_REAL_BROKER=1
export ENABLE_TRADE_STREAM=${ENABLE_TRADE_STREAM:-true}

PY=./venv/Scripts/python.exe
[ -x "$PY" ] || PY=python

echo "spine: PRODUCTION ledger (Firestore), orders -> Alpaca paper"
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8090}"
