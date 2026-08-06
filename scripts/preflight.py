"""Go-live preflight — verify Firebase + Alpaca connectivity from the deploy env.

Run this in the environment where the service will run, with the real env vars
set. Read-only: it does not place any orders.

    python3 scripts/preflight.py
"""

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


def check_firebase() -> str:
    from app.core.firebase import initialize_firebase
    initialize_firebase()
    from firebase_admin import firestore
    db = firestore.client()
    list(db.collection("fund_meta").limit(1).stream())  # trivial read
    return "ok"


def check_alpaca() -> str:
    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not (key and secret):
        return "not configured — the in-Firestore paper connector will be used"
    paper = os.getenv("ALPACA_PAPER", "true").lower() != "false"
    from alpaca.trading.client import TradingClient
    acct = TradingClient(key, secret, paper=paper).get_account()
    return (f"ok — paper={paper} status={acct.status} "
            f"cash={acct.cash} buying_power={acct.buying_power}")


def main() -> int:
    ok = True
    for name, fn in (("Firebase", check_firebase), ("Alpaca", check_alpaca)):
        try:
            print(f"[PASS] {name}: {fn()}")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"[FAIL] {name}: {type(e).__name__}: {e}")
    print("\nPREFLIGHT " + ("OK ✅" if ok else "FAILED ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
