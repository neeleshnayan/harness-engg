import json
import logging
import os

import firebase_admin
from firebase_admin import credentials

_log = logging.getLogger(__name__)

# Set FUND_ENV=production on the real fund's project. Anything else is treated
# as staging, so the safe default is the one you get by forgetting.
PRODUCTION = "production"

_active: dict[str, str] = {}


def initialize_firebase() -> None:
    """Initialize Firebase Admin once, from a service-account JSON.

    Path comes from FIREBASE_SERVICE_ACCOUNT_JSON (defaults to
    ``firebase_service_account.json`` in the working directory).

    The fund's ledger is append-only, so connecting to the wrong project is not
    an undoable mistake — it is a permanent one. The project id is therefore
    recorded and logged loudly at boot, and exposed via ``active_book()`` so the
    running book can always be identified from outside.
    """
    if firebase_admin._apps:
        return

    service_account_path = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_JSON", "firebase_service_account.json"
    )

    project_id = "unknown"
    try:
        with open(service_account_path, encoding="utf-8") as fh:
            project_id = json.load(fh).get("project_id", "unknown")
    except Exception as e:  # surfaced below; credentials.Certificate will raise properly
        _log.warning("Could not read project_id from %s (%s)", service_account_path, e)

    env = os.getenv("FUND_ENV", "staging").strip().lower()
    _active.update({"project_id": project_id, "env": env,
                    "service_account": service_account_path})

    cred = credentials.Certificate(service_account_path)
    firebase_admin.initialize_app(cred)

    banner = "PRODUCTION — REAL MONEY" if env == PRODUCTION else "staging"
    _log.warning("Fund book: project=%s env=%s (%s)", project_id, env, banner)


def active_book() -> dict[str, str]:
    """Which Firestore project this process is reading and writing."""
    return dict(_active) or {"project_id": "unknown", "env": "unknown"}


def is_production() -> bool:
    return _active.get("env") == PRODUCTION
