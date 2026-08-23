"""Which STATEMENT in SCHEMA is the one that wedges? Measured, not guessed."""
import sys
import time

import psycopg

DSN = "postgresql://krypton:krypton_local@127.0.0.1:5433/krypton_fund_kgtest"
sys.path.insert(0, ".")

STMTS = {
    "CREATE TABLE IF NOT EXISTS kg_outcome (x int)":
        "CREATE TABLE IF NOT EXISTS kg_outcome (x int)",
    "CREATE INDEX IF NOT EXISTS kg_outcome_hyp_idx":
        "CREATE INDEX IF NOT EXISTS kg_outcome_hyp_idx ON kg_outcome (hypothesis_id, at)",
    "CREATE OR REPLACE FUNCTION kg_outcome_guard":
        "CREATE OR REPLACE FUNCTION kg_outcome_guard() RETURNS trigger AS $g$ "
        "BEGIN RETURN NEW; END; $g$ LANGUAGE plpgsql",
    "DROP TRIGGER IF EXISTS kg_outcome_immutable":
        "DROP TRIGGER IF EXISTS kg_outcome_immutable ON kg_outcome",
}

blocker = psycopg.connect(DSN, autocommit=False)
with blocker.cursor() as cur:
    cur.execute("SELECT count(*) FROM kg_outcome")

for label, sql in STMTS.items():
    t0 = time.time()
    try:
        with psycopg.connect(DSN) as c:
            with c.cursor() as cur:
                cur.execute("SET statement_timeout = '2s'")
                cur.execute(sql)
            c.rollback()
        print(f"  free    ({time.time()-t0:.2f}s)  {label}")
    except Exception as e:  # noqa: BLE001
        print(f"  BLOCKED ({time.time()-t0:.2f}s)  {label} -> {type(e).__name__}")

blocker.rollback()
blocker.close()
