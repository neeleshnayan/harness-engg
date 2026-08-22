#!/usr/bin/env bash
# Start the spine in ALPACA-PAPER mode — the fund's operating configuration.
#
# One switch now, not three. `FUND_MODE` decides BOTH dimensions of what this
# process is: where orders go (the Alpaca paper account) and where events land
# (krypton_fund on Postgres). The three flags this replaces —
# USE_FAKE_FIRESTORE, FUND_REAL_BROKER, and the mere presence of
# ALPACA_API_KEY — are gone; two of them selected a simulator silently.
#
#   ./scripts/run.sh
#
# For deliberate offline work use ./scripts/run_test.sh — it is explicit about
# being a rehearsal, and it writes to a DIFFERENT, PERSISTENT database.
#
# The safety property this script relies on is in app/main.py and
# app/fund/mode.py: nothing has a default. An unset FUND_MODE or FUND_STORE
# refuses to start. A fund that stops is a problem you notice; a fund that
# silently relocates its ledger or its venue is one you notice at the audit —
# and both of those happened on 2026-08-21.
set -euo pipefail

cd "$(dirname "$0")/.."

# Everything below is the .env default; stated here so the configuration is
# visible at the point of use rather than only in a file nobody opens.
export FUND_MODE=alpaca-paper
export FUND_STORE=postgres          # no default exists; this must be said
export FUND_ENV=production
export DISABLE_DEMO_SEED=1          # never invent positions on a real book
export ENABLE_TRADE_STREAM=${ENABLE_TRADE_STREAM:-true}

PY=./venv/Scripts/python.exe
[ -x "$PY" ] || PY=python

echo "spine: mode=alpaca-paper | orders -> Alpaca paper | events -> krypton_fund"
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8090}"
