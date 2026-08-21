"""The secretary's archive index — and its three distinct absences.

Exists so the Studio never reads the filesystem: the spine owns what is on
disk, the browser owns what is on screen, and a page that stats files breaks
the moment it is served from anywhere but this machine.

The property under test throughout is that "no dailies" has THREE causes and a
caller must be able to tell them apart. Reporting a permissions error as an
empty list is how a missing backup becomes a green dashboard.
"""

from pathlib import Path

import pytest

from app.fund import desk


@pytest.fixture
def archives_dir(tmp_path, monkeypatch):
    d = tmp_path / "docs" / "archives"
    monkeypatch.setattr(desk, "ARCHIVES", d)
    return d


def _daily(d: Path, date: str, title: str = "THE DAILY", pdf: bool = False):
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{date}.md").write_text(f"# {title} · {date}\n\nbody\n", encoding="utf-8")
    if pdf:
        (d / f"{date}.pdf").write_bytes(b"%PDF-1.4\n")


def test_a_missing_directory_is_NEVER_and_says_so(archives_dir):
    out = desk.archives()
    assert out["exists"] is False
    assert out["readable"] is True
    assert out["archives"] == []
    assert "has never filed" in out["note"]


def test_an_empty_directory_is_NOT_the_same_as_a_missing_one(archives_dir):
    archives_dir.mkdir(parents=True)
    out = desk.archives()
    assert out["exists"] is True
    assert out["archives"] == []
    assert "filed nothing yet" in out["note"]
    assert "never having run" in out["note"]


def test_an_unreadable_directory_is_UNKNOWN_not_empty(archives_dir, monkeypatch):
    """A permissions error reported as 'no dailies' is a missing record showing
    up as a clean one."""
    archives_dir.mkdir(parents=True)

    def boom(*a, **k):
        raise OSError("permission denied")
    monkeypatch.setattr(type(archives_dir), "glob", boom, raising=False)
    out = desk.archives()
    assert out["readable"] is False
    assert "UNKNOWN" in out["note"]
    assert "not none" in out["note"]


def test_dailies_are_listed_newest_first(archives_dir):
    for d in ("2026-08-18", "2026-08-20", "2026-08-19"):
        _daily(archives_dir, d)
    got = [r["date"] for r in desk.archives()["archives"]]
    assert got == ["2026-08-20", "2026-08-19", "2026-08-18"]


def test_the_pdf_is_reported_when_present_and_null_when_not(archives_dir):
    _daily(archives_dir, "2026-08-20", pdf=True)
    _daily(archives_dir, "2026-08-19", pdf=False)
    rows = {r["date"]: r for r in desk.archives()["archives"]}
    assert rows["2026-08-20"]["pdf_path"].endswith("2026-08-20.pdf")
    # Absent, not an error: the PDF is a RENDER of the markdown, and a day
    # filed before that step existed has only the first.
    assert rows["2026-08-19"]["pdf_path"] is None
    assert desk.archives()["with_pdf"] == 1


def test_the_title_is_read_from_the_file_not_from_the_name(archives_dir):
    _daily(archives_dir, "2026-08-20", title="THE DAILY")
    assert "THE DAILY" in desk.archives()["archives"][0]["title"]


def test_a_non_dated_filename_is_still_listed_and_flagged(archives_dir):
    """Hiding it would make the index disagree with the directory."""
    archives_dir.mkdir(parents=True)
    (archives_dir / "notes.md").write_text("# stray\n", encoding="utf-8")
    rows = desk.archives()["archives"]
    assert len(rows) == 1
    assert rows[0]["date"] is None
    assert "not a YYYY-MM-DD date" in rows[0]["note"]


def test_a_pdf_without_its_markdown_is_not_invented_as_a_daily(archives_dir):
    """The index is of .md files; a stray PDF is not a Daily."""
    archives_dir.mkdir(parents=True)
    (archives_dir / "2026-08-20.pdf").write_bytes(b"%PDF-1.4\n")
    assert desk.archives()["archives"] == []
