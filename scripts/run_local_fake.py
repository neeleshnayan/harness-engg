"""Run the live spine against the in-memory Firestore fake — no real Firebase.

For local end-to-end testing when you don't have a `firebase_service_account.json`
handy. Boots the full FastAPI app (`app.main:app`) over HTTP on :8090, backed by
the same in-memory store the test suite uses (`scripts/_fake_firestore.py`).

    python scripts/run_local_fake.py            # port 8090
    PORT=8095 python scripts/run_local_fake.py

WARNING: state is in-memory and ephemeral — it vanishes when the process exits.
This is for exercising the fund loop and the frontend against a live spine, NOT
for anything that must persist. For a real run, set FIREBASE_SERVICE_ACCOUNT_JSON
and use `uvicorn app.main:app --port 8090`.
"""

import os
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import _fake_firestore  # noqa: E402

_fake_firestore.install()

# Augment the fake `firebase_admin` so app.core.firebase imports + initializes
# harmlessly (the fake only provides `firestore`; the real init path also touches
# `credentials`, `initialize_app`, and `_apps`).
import firebase_admin  # noqa: E402  (this is the fake injected above)

firebase_admin._apps = {}
firebase_admin.initialize_app = lambda *a, **k: None
firebase_admin.credentials = types.SimpleNamespace(Certificate=lambda *a, **k: None)

# Belt-and-suspenders: make the app's initializer a no-op before app.main imports it.
import app.core.firebase as _fb  # noqa: E402

_fb.initialize_firebase = lambda: None

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8090"))
    print(f"[run_local_fake] spine on http://127.0.0.1:{port} (in-memory fake Firestore)")
    # reload=False so the fake stays in this process's sys.modules.
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")
