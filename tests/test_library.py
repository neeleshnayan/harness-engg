"""THE READING ROOM — a shelf that can be reached, and cannot be walked out of.

CEO, 2026-08-27, verbatim: *"I thought we gave dedicated reading rooms aka like
a file vault to teams generating research or actual work product that I could
go in and read"*. Six house-styled PDFs had been rendering to ``data/library/``
since 2026-08-23 and nothing in the studio linked to one.

Two things are defended here and the second is the one that bites:

  1. AN UNREADABLE SHELF IS NOT AN EMPTY ONE. A missing directory, a listing
     that raises, and a file that cannot be stat'd all report as faults with
     their reason. An empty shelf and a shelf you cannot open look identical
     to a reader, and only one of them is fine.
  2. THE FENCE IS A RESOLVE. ``resolve_document`` is asked to escape by
     traversal, by absolute path, by symlink, by extension and by type, and
     every refusal returns the SAME answer — a distinguishable refusal is a
     directory listing for anyone patient.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.fund import library


@pytest.fixture()
def shelf(tmp_path: Path) -> Path:
    d = tmp_path / "data" / "library"
    d.mkdir(parents=True)
    (d / "GOLD_DOSSIER_V1_2026-08-24.pdf").write_bytes(b"%PDF-1.4 gold")
    (d / "ETH_DOSSIER_V1_2026-08-23.pdf").write_bytes(b"%PDF-1.4 eth")
    (d / "LEADS_SHELF_2026-08-23_v2.pdf").write_bytes(b"%PDF-1.4 leads")
    return tmp_path


# ------------------------------------------------------------ the titles ----

def test_a_filename_becomes_a_title_a_person_would_say():
    t = library.title_of("GOLD_DOSSIER_V1_2026-08-24.pdf")
    assert t["title"] == "Gold dossier"
    assert t["version"] == "v1"
    assert t["date"] == "2026-08-24"
    assert t["date_display"] == "Aug 24"
    assert t["display"] == "Gold dossier v1 — Aug 24"
    assert t["parsed"] is True


def test_a_trailing_revision_marker_is_read_as_a_version():
    t = library.title_of("LEADS_SHELF_2026-08-23_v2.pdf")
    assert t["title"] == "Leads shelf"
    assert t["version"] == "v2"
    assert t["date_display"] == "Aug 23"


def test_an_ALL_CAPS_name_is_not_SHOUTED_on_the_shelf():
    """Sentence case, deliberately: an all-caps row reads as an alarm, and
    nothing on this shelf is one."""
    assert library.title_of("META_DOSSIER_V1_2026-08-23.pdf")["title"] \
        == "Meta dossier"


def test_an_ACRONYM_is_not_turned_into_a_different_word():
    """Sentence case makes "PIT universe" into "Pit universe" — and PIT is
    point-in-time, not a hole. A NAMED set, never a heuristic: "is it
    all-caps" is true of every word in every one of these filenames."""
    assert library.title_of("PIT_UNIVERSE_FREE_2026-08-23.pdf")["title"] \
        == "PIT universe free"
    assert library.title_of("ETH_DOSSIER_V1_2026-08-23.pdf")["title"] \
        == "ETH dossier"
    # An acronym FIRST still wins over the capitalise-the-first rule.
    assert library.title_of("SEC_FILINGS_2026-08-23.pdf")["title"] \
        == "SEC filings"
    # ...and an ordinary word that merely looks shouty is not promoted.
    assert library.title_of("GOLD_NOTES_2026-08-23.pdf")["title"] == "Gold notes"


def test_a_name_with_no_date_still_gets_a_title_and_says_so():
    t = library.title_of("SOMETHING_ELSE.pdf")
    assert t["title"] == "Something else"
    assert t["date"] is None
    assert t["date_display"] is None
    assert t["display"] == "Something else"


def test_an_UNPARSEABLE_name_degrades_to_the_stem_and_flags_it():
    """A degraded title, never a blank one — and `parsed` lets the surface
    show the filename instead of a title we invented."""
    t = library.title_of("2026-08-24.pdf")
    assert t["parsed"] is False
    assert t["display"]


def test_an_impossible_month_is_not_rendered_as_a_date():
    assert library.title_of("X_2026-13-01.pdf")["date_display"] is None


# ------------------------------------------------------------- the shelf ----

def test_the_shelf_lists_every_pdf_newest_first(shelf: Path):
    s = library.shelf(str(shelf))
    assert s["readable"] is True
    assert s["count"] == 3
    assert [d["name"] for d in s["documents"]][0] \
        == "GOLD_DOSSIER_V1_2026-08-24.pdf"
    assert s["documents"][0]["size_bytes"] == len(b"%PDF-1.4 gold")


def test_a_MISSING_directory_is_a_fault_not_an_empty_library(tmp_path: Path):
    s = library.shelf(str(tmp_path))
    assert s["readable"] is False
    assert s["documents"] == []
    assert "not an empty library" in s["note"]


def test_a_READABLE_and_EMPTY_shelf_says_exactly_that(tmp_path: Path):
    (tmp_path / "data" / "library").mkdir(parents=True)
    s = library.shelf(str(tmp_path))
    assert s["readable"] is True
    assert s["count"] == 0
    assert "holds no documents yet" in s["note"]


def test_a_directory_that_RAISES_reports_the_fault_and_not_a_zero(
        tmp_path: Path, monkeypatch):
    (tmp_path / "data" / "library").mkdir(parents=True)

    def boom(self):
        raise PermissionError("nope")

    monkeypatch.setattr(Path, "iterdir", boom)
    s = library.shelf(str(tmp_path))
    assert s["readable"] is False
    assert "unknown, not nothing" in s["note"]
    assert "PermissionError" in s["note"]


def test_a_file_that_cannot_be_STATTED_is_COUNTED_not_dropped(
        shelf: Path, monkeypatch):
    """A shelf that quietly shortens itself is the failure this module's first
    rule is about."""
    real = Path.stat

    def flaky(self, *a, **k):
        if self.name.startswith("GOLD"):
            raise OSError("gone")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "stat", flaky)
    s = library.shelf(str(shelf))
    assert s["count"] == 2
    assert s["unreadable"] == 1
    assert "a fault rather than an absence" in s["note"]


def test_non_pdfs_are_not_on_the_shelf(shelf: Path):
    (shelf / "data" / "library" / "notes.md").write_text("x")
    (shelf / "data" / "library" / "sub").mkdir()
    assert library.shelf(str(shelf))["count"] == 3


def test_a_DIRECTORY_named_like_a_pdf_is_not_a_document(shelf: Path):
    (shelf / "data" / "library" / "trap.pdf").mkdir()
    s = library.shelf(str(shelf))
    assert "trap.pdf" not in [d["name"] for d in s["documents"]]


# -------------------------------------------------------------- the fence ---

def test_a_real_document_resolves(shelf: Path):
    p = library.resolve_document("GOLD_DOSSIER_V1_2026-08-24.pdf", str(shelf))
    assert p is not None
    assert p.read_bytes() == b"%PDF-1.4 gold"


@pytest.mark.parametrize("attack", [
    "../../secrets.pdf",
    "..\\..\\secrets.pdf",
    "sub/../../secrets.pdf",
    "./../../secrets.pdf",
    "/etc/passwd.pdf",
    "C:/Windows/win.pdf",
    "....//....//secrets.pdf",
])
def test_NOTHING_ESCAPES_THE_LIBRARY_DIRECTORY(shelf: Path, attack: str):
    """The fence is a RESOLVE, not a blocklist. Every one of these is refused
    because the resolved path is not inside the library, which is an answer
    rather than a guess about escape encodings."""
    outside = shelf / "secrets.pdf"
    outside.write_bytes(b"%PDF secret")
    assert library.resolve_document(attack, str(shelf)) is None


def test_a_SIBLING_DIRECTORY_WITH_A_SHARED_PREFIX_is_outside(tmp_path: Path):
    """`.../library2/x.pdf` starts with `.../library` as a STRING. A prefix
    check would let it through; `is_relative_to` does not."""
    (tmp_path / "data" / "library").mkdir(parents=True)
    sibling = tmp_path / "data" / "library2"
    sibling.mkdir()
    (sibling / "x.pdf").write_bytes(b"%PDF")
    assert library.resolve_document("../library2/x.pdf", str(tmp_path)) is None


@pytest.mark.skipif(os.name == "nt" and not hasattr(os, "symlink"),
                    reason="symlinks unavailable")
def test_a_SYMLINK_POINTING_OUT_OF_THE_TREE_is_refused(tmp_path: Path):
    """No string check can see this one; the resolve does."""
    d = tmp_path / "data" / "library"
    d.mkdir(parents=True)
    outside = tmp_path / "secret.pdf"
    outside.write_bytes(b"%PDF secret")
    try:
        (d / "innocent.pdf").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("this host refuses to create symlinks")
    assert library.resolve_document("innocent.pdf", str(tmp_path)) is None


@pytest.mark.parametrize("bad", ["notes.md", "GOLD_DOSSIER_V1_2026-08-24",
                                 "", "   ", "shelf.PDF.txt"])
def test_anything_that_is_not_a_pdf_is_refused(shelf: Path, bad: str):
    assert library.resolve_document(bad, str(shelf)) is None


def test_a_non_string_name_is_refused_rather_than_raising(shelf: Path):
    for junk in [None, 7, ["a"], {"a": 1}]:
        assert library.resolve_document(junk, str(shelf)) is None  # type: ignore[arg-type]


def test_a_MISSING_document_and_a_FORBIDDEN_one_are_indistinguishable(shelf: Path):
    """Both return None, so the route returns one 404 with one sentence. A
    refusal that can be told apart from an absence is a directory listing for
    anyone patient enough to enumerate."""
    assert library.resolve_document("NOT_HERE_2026-01-01.pdf", str(shelf)) is None
    assert library.resolve_document("../../secrets.pdf", str(shelf)) is None


def test_an_UPPERCASE_extension_is_still_a_pdf(shelf: Path):
    (shelf / "data" / "library" / "SHOUTY_2026-08-25.PDF").write_bytes(b"%PDF")
    assert library.resolve_document("SHOUTY_2026-08-25.PDF", str(shelf)) is not None


# ------------------------------------------------------- the live shelf -----

def test_the_REAL_shelf_is_readable_and_holds_the_documents_it_claims():
    """Against the repository's own ``data/library``. This is the one test that
    would have caught the original defect — six documents on disk and nothing
    able to reach them — and it fails if the directory is ever moved."""
    s = library.shelf()
    assert s["readable"] is True, s["note"]
    # A COUNT IS NOT ASSERTED: the shelf grows, and a test that pinned six
    # would go red the next time a dossier is filed — which is the wrong
    # direction to be brittle in. What IS asserted is that every row the shelf
    # claims can actually be fetched, which is the property the room exists
    # for, and the DOMAIN is printed so a pass over an empty shelf cannot be
    # mistaken for a pass over a full one.
    assert s["count"] >= 1, (
        f"the real shelf reported {s['count']} documents at {s['directory']} — "
        "this test proved nothing")
    for row in s["documents"]:
        assert library.resolve_document(row["name"]) is not None, row["name"]
        assert row["display"], row["name"]


# ------------------------------------------------------------- the doors ----

@pytest.fixture()
def client(monkeypatch, shelf: Path):
    """The two routes, mounted on a bare app.

    Pointed at a TEMPORARY shelf rather than the repository's, so a test that
    fetches bytes proves the door works without the repo's real PDFs deciding
    the assertion.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1 import fund as fundapi
    from app.fund import library as lib

    real_dir = lib.library_dir

    monkeypatch.setattr(lib, "library_dir",
                        lambda root=None: real_dir(root or str(shelf)))
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    return TestClient(app)


def test_GET_library_lists_the_shelf(client):
    r = client.get("/api/v1/fund/library")
    assert r.status_code == 200
    body = r.json()
    assert body["readable"] is True
    assert body["count"] == 3
    assert body["documents"][0]["display"] == "Gold dossier v1 — Aug 24"


def test_GET_a_document_serves_its_bytes_as_a_pdf_INLINE(client):
    r = client.get("/api/v1/fund/library/GOLD_DOSSIER_V1_2026-08-24.pdf")
    assert r.status_code == 200
    assert r.content == b"%PDF-1.4 gold"
    assert r.headers["content-type"] == "application/pdf"
    # `inline`, not `attachment`: the room is for reading and the tab is the
    # reading surface. The filename still rides so a save keeps its name.
    assert r.headers["content-disposition"].startswith("inline;")
    assert "GOLD_DOSSIER_V1_2026-08-24.pdf" in r.headers["content-disposition"]


@pytest.mark.parametrize("attack", [
    "..%2F..%2Fsecrets.pdf",
    "....//....//secrets.pdf",
    "NOT_A_REAL_DOC.pdf",
    "notes.md",
    "%2Fetc%2Fpasswd.pdf",
])
def test_NO_ATTACK_REACHES_A_FILE(client, attack: str):
    """The property that matters: none of these returns bytes. 404, always."""
    r = client.get(f"/api/v1/fund/library/{attack}")
    assert r.status_code == 404


@pytest.mark.parametrize("refused", ["NOT_A_REAL_DOC.pdf", "notes.md",
                                     "GOLD_DOSSIER_V1_2026-08-24",
                                     "..secrets.pdf", "sub.pdf"])
def test_EVERY_HANDLER_REFUSAL_IS_THE_SAME_SENTENCE(client, refused: str):
    """A 403 that can be told apart from a 404 is a directory listing for
    anyone patient enough to enumerate. One code, one sentence — for every
    refusal the HANDLER makes.

    THE LIMIT ON THAT CLAIM, MEASURED rather than assumed — the first version
    of this test asserted it of every attack and THREE of them failed, in two
    rounds, which is exactly how much this claim was worth guessing at. **Any
    name whose decoded form contains a slash never reaches this handler**:
    literal (``....//....//``), single-encoded (``..%2F..%2F``) and
    double-encoded (``..%252F..%252F``) all end up as multi-segment paths, and
    Starlette's router answers its own generic ``{"detail": "Not Found"}`` —
    which IS distinguishable from the sentence below. The parametrised
    counterpart below pins all three.

    That is left as it is, and said out loud rather than papered over with a
    catch-all route. What it leaks is that the path contained a slash, which
    the sender already knows; what a catch-all would add is a second door onto
    the same directory, written to make a test pass. A narrower claim that is
    true beats a uniform one that is false in two cases.
    """
    r = client.get(f"/api/v1/fund/library/{refused}")
    assert r.status_code == 404
    assert r.json()["detail"] == "No such document on the reading room's shelf."


@pytest.mark.parametrize("slashed", ["....//....//secrets.pdf",
                                     "..%2F..%2Fsecrets.pdf",
                                     "..%252F..%252Fsecrets.pdf",
                                     "%2Fetc%2Fpasswd.pdf"])
def test_a_path_with_SLASHES_is_refused_by_the_ROUTER_not_the_handler(
        client, slashed: str):
    """The measured counterpart to the test above — pinned so that the day
    somebody adds a catch-all route this goes RED and the uniformity claim is
    re-read, rather than quietly becoming true or quietly becoming worse."""
    r = client.get(f"/api/v1/fund/library/{slashed}")
    assert r.status_code == 404
    assert r.json()["detail"] == "Not Found"


def test_a_document_that_is_PRESENT_and_UNREADABLE_is_a_FAULT_not_a_404(
        client, monkeypatch):
    """Present-and-unreadable is a permissions problem, and a 404 would send
    the reader looking for a file that is right there."""
    from pathlib import Path as P

    real = P.read_bytes

    def flaky(self, *a, **k):
        if self.name.startswith("GOLD"):
            raise PermissionError("nope")
        return real(self, *a, **k)

    monkeypatch.setattr(P, "read_bytes", flaky)
    r = client.get("/api/v1/fund/library/GOLD_DOSSIER_V1_2026-08-24.pdf")
    assert r.status_code == 503
    assert "could not be read" in r.json()["detail"]
