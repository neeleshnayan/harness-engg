import json
import logging
import os

import firebase_admin

_log = logging.getLogger(__name__)

# Set FUND_ENV=production on the real fund's project. Anything else is treated
# as staging, so the safe default is the one you get by forgetting.
PRODUCTION = "production"

#: The Firebase project that IS the fund, named rather than inferred (desk
#: 09e49ae5). Two service accounts sit in this working directory and the code's
#: default used to be the WRONG one: ``firebase_service_account.json`` is
#: krypton-auth-e8653, a stale auth project which ALSO carries a
#: ``fund_events`` collection, so a script that reached it would not fail — it
#: would quietly read and write a plausible-looking ledger that is not the
#: fund's. ``.env`` pointed at the right file, which meant the defect was
#: invisible to everything that loaded ``.env`` and live for everything that
#: did not: exactly the standalone repair scripts that call
#: ``initialize_firebase()`` directly.
#:
#: This is the same shape as ``FUND_STORE``'s "firestore" default, fixed the
#: same way in this diff: a default that silently selects a ledger is a
#: trapdoor, not a convenience.
FUND_FIREBASE_PROJECT = "hedgefund-ae96c"

#: Projects that are NOT the fund but resemble it closely enough to be
#: mistaken for it. Named so a refusal can say WHICH mistake this is.
KNOWN_WRONG_PROJECTS = {
    "krypton-auth-e8653":
        "a stale auth project that also contains a fund_events collection, "
        "which is why reaching it fails silently instead of loudly",
}

#: The service account for the project above. The default is now the FUND's
#: file, so forgetting the variable selects the right book rather than a
#: convincing wrong one.
DEFAULT_SERVICE_ACCOUNT = "firebase_service_account.hedgefund.json"


class WrongFirebaseProject(RuntimeError):
    """The credentials point at a project that is not the fund's."""

_active: dict[str, str] = {}


def _is_test_mode() -> bool:
    """Is this process running the fund's ``test`` mode?

    Replaces ``USE_FAKE_FIRESTORE`` as the key for the interlock below. The
    flag is gone; THE MODE IT WAS PROTECTING IS NOT — it was renamed ``test``
    and made persistent — so the interlock is re-keyed rather than deleted.
    Removing a guard along with its flag is only correct when the state it
    guards against stops existing, and here it did not.

    Deliberately tolerant: any failure to resolve a mode answers False, so an
    unconfigured process is treated as NOT test mode and gets the loud refusal
    from every other guard instead of a quiet exemption from this one.
    """
    try:
        from app.fund.mode import FundMode, current, resolve
        spec = current()
        if spec is None:
            spec = resolve()
        return spec.mode is FundMode.TEST
    except Exception:  # noqa: BLE001 — see the docstring
        return False


def initialize_firebase() -> None:
    """Initialize Firebase Admin once, from a service-account JSON.

    Path comes from FIREBASE_SERVICE_ACCOUNT_JSON (defaults to
    ``DEFAULT_SERVICE_ACCOUNT``, the FUND's service account). The resulting
    project is then checked against ``FUND_FIREBASE_PROJECT`` and a mismatch
    refuses — see the constants above for the defect that earned the check.

    The fund's ledger is append-only, so connecting to the wrong project is not
    an undoable mistake — it is a permanent one. The project id is therefore
    recorded and logged loudly at boot, and exposed via ``active_book()`` so the
    running book can always be identified from outside.
    """
    if firebase_admin._apps:
        return

    service_account_path = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_JSON", DEFAULT_SERVICE_ACCOUNT
    )

    project_id = "unknown"
    try:
        with open(service_account_path, encoding="utf-8") as fh:
            project_id = json.load(fh).get("project_id", "unknown")
    except Exception as e:  # surfaced below; credentials.Certificate will raise properly
        _log.warning("Could not read project_id from %s (%s)", service_account_path, e)

    # THE PROJECT MUST BE THE FUND'S, AND IT IS CHECKED, NOT ASSUMED.
    #
    # Expected is the fund's project unless someone names a different one
    # explicitly — which is the whole point: the wrong book stays reachable for
    # a deliberate migration and becomes unreachable by omission. An unreadable
    # service account is NOT treated as "probably fine": unknown is not the
    # fund, so it refuses here rather than opening a client and finding out.
    expected = (os.getenv("FUND_FIREBASE_PROJECT") or FUND_FIREBASE_PROJECT).strip()
    if project_id != expected:
        why = KNOWN_WRONG_PROJECTS.get(project_id)
        raise WrongFirebaseProject(
            f"{service_account_path!r} is project {project_id!r}, but this "
            f"process expects the fund's project {expected!r}"
            + (f" — {project_id!r} is {why}" if why else "")
            + ". The fund's ledger is append-only, so opening the wrong book "
              "is a permanent mistake. Point FIREBASE_SERVICE_ACCOUNT_JSON at "
              f"{DEFAULT_SERVICE_ACCOUNT!r}, or set FUND_FIREBASE_PROJECT "
              "if you genuinely mean to operate on another project."
        )

    env = os.getenv("FUND_ENV", "staging").strip().lower()
    if _is_test_mode():
        # A test-mode process is never the fund, whatever FUND_ENV claims.
        env = "test"
    _active.update({"project_id": project_id, "env": env,
                    "service_account": service_account_path,
                    "database_id": os.getenv("FIRESTORE_DATABASE_ID", "(default)")})

    from firebase_admin import credentials

    cred = credentials.Certificate(service_account_path)
    firebase_admin.initialize_app(cred)

    banner = "PRODUCTION — REAL MONEY" if env == PRODUCTION else "staging"
    _log.warning("Fund book: project=%s env=%s (%s)", project_id, env, banner)


def db():
    """The Firestore client for the configured database.

    FIRESTORE_DATABASE_ID selects which database to use. It defaults to
    "(default)", but a project may legitimately have a *named* database instead
    (the fund's production project has one called "default"), and the SDK will
    404 looking for "(default)" if that id is not passed through.
    """
    # FUND_MODE=test means "this process must not touch the real ledger".
    # The app honours that by choosing the store before anything calls db(),
    # but a STANDALONE SCRIPT only calls initialize_firebase() — which happily
    # labelled itself env="test" while handing back a client wired to the
    # production project. A repair script run with --apply under that illusion
    # would write to the real, append-only fund ledger.
    #
    # Reaching here in test mode is therefore a bug, not a fallback: fail
    # loudly rather than quietly connect to production. The app installs an
    # in-memory Firestore before importing anything that calls db() and that
    # path is legitimate — it reports project "in-memory". A standalone script
    # does NOT install it, so it reaches here still pointing at the real
    # project while believing it is isolated. That is the case to stop.
    if (_is_test_mode()
            and _active.get("project_id") not in (None, "", "in-memory")):
        raise RuntimeError(
            "refusing to open a REAL Firestore client while FUND_MODE=test — "
            f"the in-memory store was never installed, so this would reach project "
            f"{_active.get('project_id')!r}. Run this through the API against a "
            "test-mode spine, or declare the mode you actually mean if you "
            "genuinely intend to touch the real book."
        )

    from firebase_admin import firestore
    database_id = os.getenv("FIRESTORE_DATABASE_ID", "").strip()
    if database_id and database_id != "(default)":
        return firestore.client(database_id=database_id)
    return firestore.client()


def active_book() -> dict[str, str]:
    """Which Firestore project this process is reading and writing."""
    return dict(_active) or {"project_id": "unknown", "env": "unknown"}


def is_production() -> bool:
    return _active.get("env") == PRODUCTION
