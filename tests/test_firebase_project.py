"""The fund's Firebase project is checked, not assumed.

Desk 09e49ae5, 2026-08-21: two service accounts sit in the working directory
and the code's DEFAULT was the wrong one. ``firebase_service_account.json`` is
``krypton-auth-e8653`` — a stale auth project which ALSO carries a
``fund_events`` collection, so a process that reached it did not crash. It read
and wrote a plausible ledger that was not the fund's. ``.env`` pointed at the
correct file, so the defect was invisible to anything that loaded ``.env`` and
live for every standalone script that did not.

Both project ids in this file were read out of the two real service-account
files on 2026-08-22 (``project_id`` field), not invented.

These tests fail if the silent default or the missing check ever returns.
"""

import json

import pytest

from app.core import firebase as fb


FUND = "hedgefund-ae96c"
STALE_AUTH = "krypton-auth-e8653"


@pytest.fixture(autouse=True)
def _restore_active_book():
    """``firebase._active`` is MODULE state and these tests write to it.

    Learned the expensive way in this file's own first run: the override test
    below deliberately gets PAST the project check, so it reaches
    ``_active.update()`` and leaves a foreign ``project_id`` behind. Every
    later test that called ``db()`` then tripped the test-mode interlock —
    **124 errors and 4 failures across the suite, none of them in this file**,
    all from one dictionary this file forgot to put back.

    The irony is the point and it is worth keeping: the module under test
    exists to stop a process from silently operating against the wrong book,
    and the test for it silently left the wrong book configured.
    """
    saved = dict(fb._active)
    yield
    fb._active.clear()
    fb._active.update(saved)


def _account(tmp_path, project_id, name="sa.json"):
    p = tmp_path / name
    p.write_text(json.dumps({"project_id": project_id, "type": "service_account"}),
                 encoding="utf-8")
    return str(p)


class TestTheDefaultIsTheFund:
    def test_default_service_account_is_the_fund_not_the_auth_project(self):
        """The constant that used to name the wrong file."""
        assert fb.DEFAULT_SERVICE_ACCOUNT == "firebase_service_account.hedgefund.json"

    def test_the_fund_project_is_named_explicitly(self):
        assert fb.FUND_FIREBASE_PROJECT == FUND

    def test_the_stale_auth_project_is_named_as_known_wrong(self):
        """Named so the refusal can say WHICH mistake this is."""
        assert STALE_AUTH in fb.KNOWN_WRONG_PROJECTS
        assert "fund_events" in fb.KNOWN_WRONG_PROJECTS[STALE_AUTH]


class TestTheWrongProjectIsUnreachableByAccident:
    def test_the_stale_auth_project_refuses(self, tmp_path, monkeypatch):
        """THE INCIDENT ITSELF: credentials for krypton-auth-e8653 must refuse."""
        monkeypatch.setattr(fb.firebase_admin, "_apps", {}, raising=False)
        monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_JSON",
                           _account(tmp_path, STALE_AUTH))
        monkeypatch.delenv("FUND_FIREBASE_PROJECT", raising=False)
        with pytest.raises(fb.WrongFirebaseProject) as e:
            fb.initialize_firebase()
        msg = str(e.value)
        assert STALE_AUTH in msg and FUND in msg
        # It must say why this particular wrong project is dangerous.
        assert "fund_events" in msg

    def test_an_unreadable_service_account_refuses_rather_than_assuming(
            self, tmp_path, monkeypatch):
        """Unreadable is not 'probably the fund'. Absence is never assent."""
        monkeypatch.setattr(fb.firebase_admin, "_apps", {}, raising=False)
        monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_JSON",
                           str(tmp_path / "does_not_exist.json"))
        monkeypatch.delenv("FUND_FIREBASE_PROJECT", raising=False)
        with pytest.raises(fb.WrongFirebaseProject) as e:
            fb.initialize_firebase()
        assert "unknown" in str(e.value)

    def test_an_unrelated_project_refuses_without_a_known_wrong_note(
            self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb.firebase_admin, "_apps", {}, raising=False)
        monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_JSON",
                           _account(tmp_path, "somebody-elses-project"))
        monkeypatch.delenv("FUND_FIREBASE_PROJECT", raising=False)
        with pytest.raises(fb.WrongFirebaseProject):
            fb.initialize_firebase()


class TestADeliberateOverrideIsStillPossible:
    def test_naming_the_project_explicitly_passes_the_check(
            self, tmp_path, monkeypatch):
        """Reachable on purpose, unreachable by omission — that is the design.

        The check must not make a genuine migration impossible; it must make an
        ACCIDENT impossible. Asserted as "not WrongFirebaseProject" rather than
        "no exception": the suite's fake ``firebase_admin`` has no
        ``credentials`` submodule, so this call always fails LATER, and the
        distinction between the two failures is the whole assertion.
        """
        monkeypatch.setattr(fb.firebase_admin, "_apps", {}, raising=False)
        monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_JSON",
                           _account(tmp_path, STALE_AUTH))
        monkeypatch.setenv("FUND_FIREBASE_PROJECT", STALE_AUTH)
        try:
            fb.initialize_firebase()
        except fb.WrongFirebaseProject:
            raise AssertionError(
                "an explicitly named project was still refused — the override "
                "is what keeps this a guard rather than a wall")
        except Exception:
            pass  # got past the project check; the fake has no credentials

    def test_the_override_must_be_named_and_does_not_accept_anything(
            self, tmp_path, monkeypatch):
        """An override for project A does not open the door to project B."""
        monkeypatch.setattr(fb.firebase_admin, "_apps", {}, raising=False)
        monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_JSON",
                           _account(tmp_path, STALE_AUTH))
        monkeypatch.setenv("FUND_FIREBASE_PROJECT", "some-third-project")
        with pytest.raises(fb.WrongFirebaseProject):
            fb.initialize_firebase()
