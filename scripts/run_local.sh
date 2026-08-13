#!/usr/bin/env bash
# Start the spine against the LOCAL event log, with orders going to the real
# paper venue.
#
# Why this file exists: `.env` carries USE_FAKE_FIRESTORE=0 and
# FUND_ENV=production, because that is the deployed fund's configuration. The
# local session ran safely only because someone exported USE_FAKE_FIRESTORE=1 in
# the shell at launch — a setting that existed nowhere on disk. The first
# restart lost it and the spine came up pointing at the production ledger.
#
# A safe configuration that lives only in a running process is not a
# configuration, it is a memory. This is that setting, written down.
#
#   ./scripts/run_local.sh
#
set -euo pipefail

cd "$(dirname "$0")/.."

# The local, file-backed event log — NOT the production Firestore project.
export USE_FAKE_FIRESTORE=1
# Anything but "production" so nothing can label this book the real fund.
export FUND_ENV=local
# Orders DO go to the Alpaca paper venue. This is the deliberate split: where
# state lives (local) is a separate decision from where orders go (real paper).
export FUND_REAL_BROKER=1
# The demo seeder must never invent positions on a book with real fills in it.
export DISABLE_DEMO_SEED=1

PY=./venv/Scripts/python.exe
[ -x "$PY" ] || PY=python

echo "spine: local ledger (.firestore_local_db.json), orders -> Alpaca paper"
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8090}"
