"""`GET /fund/desk/archives/memo` — the route the CEO's memo card was reading.

THE INCIDENT (2026-08-22). Donna's memo card on the CEO's desk has rendered a
permanent absence since the day it merged. The card, the `ArchiveMemo`
TypeScript type and its five-way absence vocabulary were all shipped; the route
was not, so `GET /fund/desk/archives/memo` was a live 404 and the card
faithfully reported "no memo" about a memo that existed on disk. The CEO saw it
and asked. **A control that reports an absence it manufactures itself is the
unwired-kill-switch pattern with a friendly face**, and it is the pattern this
firm names in its own doctrine.

RE-DERIVED FROM THE TWO REAL FILES, NOT FROM AN EARLIER DRAFT — and the
derivation earned itself immediately, because the two archives on disk are NOT
the same shape:

    docs/archives/2026-08-21.md      docs/archives/2026-08-20.md
    ```                              TL;DR
    TL;DR                            ```
    <five lines>                     <ten lines>
    ```                              ```

The TL;DR label is INSIDE the fence in one and OUTSIDE it in the other. A
parser written against either file alone gets the other wrong: it returns the
literal word "TL;DR" as the memo's first line, or finds no headline at all.
Both real files are parsed here as fixtures, byte-for-byte from disk, and
`test_both_real_archives_parse` is the regression that fails if either shape
stops working.
"""

import json
from pathlib import Path

import pytest

from app.fund import desk as desk_mod

REAL_ARCHIVES = Path(__file__).resolve().parents[1] / "docs" / "archives"


@pytest.fixture
def fake_archives(tmp_path, monkeypatch):
    """Point the module at a temp directory. Returns it."""
    d = tmp_path / "archives"
    d.mkdir()
    monkeypatch.setattr(desk_mod, "ARCHIVES", d)
    return d


def write(d: Path, name: str, body: str) -> Path:
    p = d / name
    p.write_text(body, encoding="utf-8", newline="\n")
    return p


# --------------------------------------------------- the two real shapes ----

class TestTheRealArchives:
    def test_both_real_archives_parse(self):
        """THE REGRESSION. Both shipped shapes, from the files themselves.

        Not a hand-written fixture: a hand-written fixture is the author's
        BELIEF about the format, and the belief here was wrong — the two files
        disagree with each other.
        """
        found = sorted(p.stem for p in REAL_ARCHIVES.glob("*.md"))
        assert len(found) >= 2, (
            "this regression needs both real archive shapes on disk; it is "
            f"reading {REAL_ARCHIVES} and found {found}")

        for day in found:
            m = desk_mod.archive_memo(day)
            assert m["available"] is True, f"{day}: {m['note']}"
            assert m["reason"] is None
            assert m["date"] == day
            assert m["daily_markdown"], f"{day} has no Daily section"
            assert m["daily_markdown"].startswith("# "), (
                f"{day}: the Daily must begin at its own heading")

    def test_the_tldr_never_contains_its_own_label(self):
        """The defect a one-file parser ships: `TL;DR` returned as the CEO's
        first line. It is the sixty-second read — the one paragraph he is
        promised he can act on — and starting it with a label is starting it
        with noise."""
        for day in sorted(p.stem for p in REAL_ARCHIVES.glob("*.md")):
            m = desk_mod.archive_memo(day)
            assert m["tldr"], f"{day}: no headline was found at all"
            first = m["tldr"].splitlines()[0]
            assert "TL;DR" not in first.upper().replace(" ", ""), (
                f"{day}: the headline begins with its own label: {first!r}")
            assert not first.startswith("```"), (
                f"{day}: the fence leaked into the headline: {first!r}")
            assert "```" not in m["tldr"], (
                f"{day}: the closing fence leaked into the headline")

    def test_the_daily_stops_before_the_long_record(self):
        """The client's type promises "`# THE DAILY` through to (and never
        including) `# THE RECORD`". The long record is nine sections; leaking
        it into the card would put the whole day on the CEO's desk under a
        heading that says it is the short version."""
        for day in sorted(p.stem for p in REAL_ARCHIVES.glob("*.md")):
            m = desk_mod.archive_memo(day)
            if not m["has_long_record"]:
                continue
            assert "# THE RECORD" not in m["daily_markdown"], (
                f"{day}: the long record leaked into the Daily")

    def test_utf8_survives_the_read(self):
        """The titles carry a MIDDLE DOT (U+00B7, two bytes in UTF-8). Read
        under the platform default on Windows (cp1252) it becomes `Â·` — which
        is exactly what the LIVE spine was serving from
        `/fund/desk/archives` on 2026-08-22, because the running process
        predates its own repo's fix. Pinned so the memo route can never
        acquire the same defect."""
        m = desk_mod.archive_memo("2026-08-21")
        assert m["title"] is not None
        assert "Â" not in m["title"], (
            f"mojibake in the title: {m['title']!r} — the file was read as "
            "cp1252, not UTF-8")
        assert "Â" not in (m["daily_markdown"] or "")


# ------------------------------------------------------- the five absences --

class TestTheAbsencesAreKeptApart:
    """Five different facts. A surface that collapses them sends the reader
    somewhere useless — the CEO chasing the secretary for a memo she filed, or
    ignoring a permissions error because it rendered as a quiet day."""

    def test_never_filed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(desk_mod, "ARCHIVES", tmp_path / "nope")
        m = desk_mod.archive_memo()
        assert m["available"] is False
        assert m["reason"] == "never_filed"
        assert m["date"] is None

    def test_none_yet_is_not_never_filed(self, fake_archives):
        """The directory exists and holds nothing: she has run zero times,
        which is a different fact from her never having been seated."""
        m = desk_mod.archive_memo()
        assert m["reason"] == "none_yet"

    def test_no_such_day_is_not_an_empty_day(self, fake_archives):
        write(fake_archives, "2026-08-21.md", "# THE DAILY\nbody\n")
        m = desk_mod.archive_memo("2026-08-19")
        assert m["reason"] == "no_such_day"
        assert m["date"] == "2026-08-19", (
            "the day asked for must come back, or the client cannot say WHICH "
            "day it could not find")
        assert "no session was live" in m["note"] or "not an empty day" in m["note"]

    def test_unreadable_is_unknown_not_absent(self, fake_archives, monkeypatch):
        """A file on disk that cannot be read is UNKNOWN. This fund has
        answered an unmeasurable with a zero four separate times."""
        write(fake_archives, "2026-08-21.md", "# THE DAILY\nbody\n")
        real = Path.read_text

        def boom(self, *a, **k):
            if self.suffix == ".md" and "2026-08-21" in self.name:
                raise OSError("permission denied")
            return real(self, *a, **k)

        monkeypatch.setattr(Path, "read_text", boom)
        m = desk_mod.archive_memo("2026-08-21")
        assert m["available"] is False
        assert m["reason"] == "unreadable"
        assert m["date"] == "2026-08-21"
        assert "UNKNOWN" in m["note"]

    def test_no_memo_section_points_at_the_artifact(self, fake_archives):
        """Filed, readable, and carrying neither section. That is a defect in
        the DOCUMENT and the note must say so — it points at the secretary,
        not at the plumbing, and confusing the two wastes a dispatch."""
        write(fake_archives, "2026-08-21.md", "just some prose, no headings\n")
        m = desk_mod.archive_memo("2026-08-21")
        assert m["available"] is False
        assert m["reason"] == "no_memo_section"
        assert m["path"], "the path must be reported — the file DOES exist"
        assert "secretary" in m["note"]

    def test_a_headline_with_no_daily_is_not_available(self, fake_archives):
        """A fragment is not a Daily. Five unanchored lines presented as the
        day's memo would say the day was documented when it was not — but the
        headline that WAS read is still returned, because withholding a fact
        because a neighbouring one is missing is its own dishonesty."""
        write(fake_archives, "2026-08-21.md", "TL;DR\n```\nfive lines\n```\n")
        m = desk_mod.archive_memo("2026-08-21")
        assert m["available"] is False
        assert m["reason"] == "no_memo_section"
        assert m["tldr"] == "five lines"


# ------------------------------------------------------------- the parser ---

class TestTheParser:
    def test_the_label_inside_the_fence(self, fake_archives):
        write(fake_archives, "2026-08-21.md",
              "```\nTL;DR\nline one\nline two\n```\n\n# THE DAILY\nbody\n")
        m = desk_mod.archive_memo("2026-08-21")
        assert m["tldr"] == "line one\nline two"

    def test_the_label_above_the_fence(self, fake_archives):
        write(fake_archives, "2026-08-21.md",
              "TL;DR\n```\nline one\nline two\n```\n\n# THE DAILY\nbody\n")
        m = desk_mod.archive_memo("2026-08-21")
        assert m["tldr"] == "line one\nline two"

    def test_label_spellings(self, fake_archives):
        """Donna is a model writing markdown; the label will not be
        byte-stable forever. Bold, colon, lowercase and the unpunctuated
        spelling all mean the same thing to a reader and must mean the same
        thing here."""
        for label in ("TL;DR", "TLDR", "tl;dr", "**TL;DR**", "TL;DR:"):
            write(fake_archives, "2026-08-21.md",
                  f"{label}\n```\nheadline\n```\n\n# THE DAILY\nbody\n")
            m = desk_mod.archive_memo("2026-08-21")
            assert m["tldr"] == "headline", f"label {label!r} was not recognised"

    def test_an_unlabelled_fence_is_NOT_reported_as_the_headline(
            self, fake_archives):
        """THE DELIBERATE REFUSAL, and the reason is in the desk's own history.

        A fenced block before the first heading is *probably* the TL;DR by
        convention. Convention-matching over prose is what the CEO's desk was
        being repaired FROM the same week — six rows found by grepping their
        text for "EXECUTED" — and this is the sixty-second read. The wrong
        five lines on his desk is worse than none, so an unlabelled block is
        reported absent AND the note says a fence was seen and not identified.
        """
        write(fake_archives, "2026-08-21.md",
              "```\nsome random preamble\n```\n\n# THE DAILY\nbody\n")
        m = desk_mod.archive_memo("2026-08-21")
        assert m["available"] is True, "the Daily is still a Daily"
        assert m["tldr"] is None
        assert "no TL;DR label" in m["note"], (
            "the absence must explain itself; a silent null here reads as "
            "'she wrote no headline' when the truth is 'one may be there and "
            "this could not identify it'")

    def test_a_fence_AFTER_the_first_heading_is_not_the_headline(
            self, fake_archives):
        """A code block inside the Daily's body is body. Scanning the whole
        file for a fence would lift a fragment of section IX onto the top of
        his desk."""
        write(fake_archives, "2026-08-21.md",
              "# THE DAILY\nbody\n\n```\nTL;DR\nnot the headline\n```\n")
        m = desk_mod.archive_memo("2026-08-21")
        assert m["tldr"] is None

    def test_an_unclosed_fence_says_so(self, fake_archives):
        write(fake_archives, "2026-08-21.md",
              "```\nTL;DR\nnever closed\n\n# THE DAILY\nbody\n")
        m = desk_mod.archive_memo("2026-08-21")
        assert m["tldr"] is None
        assert "never closed" in m["note"]

    def test_a_renamed_heading_degrades_and_SAYS_it_degraded(
            self, fake_archives):
        """A renamed heading is still a memo. Reporting `no_memo_section` for
        a file that plainly has one is the collapse the five reasons exist to
        prevent — so it reads the first section and says out loud that it
        did."""
        write(fake_archives, "2026-08-21.md", "# THE BRIEFING\nbody here\n")
        m = desk_mod.archive_memo("2026-08-21")
        assert m["available"] is True
        assert "THE BRIEFING" in m["daily_markdown"]
        assert "heading convention changed" in m["note"]

    def test_has_long_record_is_measured_not_assumed(self, fake_archives):
        write(fake_archives, "2026-08-21.md", "# THE DAILY\nbody\n")
        assert desk_mod.archive_memo("2026-08-21")["has_long_record"] is False
        write(fake_archives, "2026-08-21.md",
              "# THE DAILY\nbody\n# THE RECORD\nlots\n")
        m = desk_mod.archive_memo("2026-08-21")
        assert m["has_long_record"] is True
        assert m["daily_markdown"] == "# THE DAILY\nbody"


# ----------------------------------------------------------- the boundary ---

class TestTheQueryParameterIsNotAPath:
    """This route reads a file chosen by a query parameter. That is a
    directory traversal until it is not."""

    @pytest.mark.parametrize("bad", [
        "../../../etc/passwd", "..\\..\\secrets", "2026-08-21/../../x",
        "2026-08-21.md", "*", "", "   ", "2026-8-1", "20260821",
    ])
    def test_a_non_date_reads_nothing_from_disk(self, fake_archives, bad,
                                                monkeypatch):
        write(fake_archives, "2026-08-21.md", "# THE DAILY\nbody\n")
        reads: list[str] = []
        real = Path.read_text

        def watched(self, *a, **k):
            reads.append(str(self))
            return real(self, *a, **k)

        monkeypatch.setattr(Path, "read_text", watched)
        m = desk_mod.archive_memo(bad)
        assert m["available"] is False
        assert m["date"] is None
        assert "not a YYYY-MM-DD date" in m["note"]
        assert reads == [], (
            f"a malformed date touched the filesystem: {reads}")

    def test_a_malformed_date_is_told_apart_from_a_missing_one(
            self, fake_archives):
        """Both are `no_such_day` in the closed enum the client already ships,
        and the NOTE distinguishes them: a malformed parameter is a broken
        client, a missing day is a quiet day. Answering the first with the
        second hides a bug in the caller."""
        write(fake_archives, "2026-08-21.md", "# THE DAILY\nbody\n")
        malformed = desk_mod.archive_memo("not-a-date")
        missing = desk_mod.archive_memo("2026-08-19")
        assert malformed["reason"] == missing["reason"] == "no_such_day"
        assert malformed["note"] != missing["note"]
        assert "Nothing was read from disk" in malformed["note"]


# ---------------------------------------------------------------- the route -

class TestTheRoute:
    def test_the_route_exists_and_answers_200(self):
        """THE ASSERTION THAT WOULD HAVE CAUGHT THE ORIGINAL DEFECT. The card
        and the type merged and the route did not; nothing anywhere asserted
        that the URL the client fetches resolves."""
        from fastapi.testclient import TestClient

        from app.main import app
        r = TestClient(app).get("/api/v1/fund/desk/archives/memo")
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body) == {
            "available", "reason", "date", "path", "pdf_path", "title",
            "tldr", "daily_markdown", "has_long_record", "note"}, (
            "the payload keys must match the merged ArchiveMemo type exactly; "
            "three bugs this week came from reading keys an endpoint never "
            "returned")

    def test_every_absence_is_still_a_200(self):
        """The five absences are DATA, not statuses. An HTTP code can only say
        "no", and the client must tell "she has never run" from "no session
        was live that day" from "the file is unreadable"."""
        from fastapi.testclient import TestClient

        from app.main import app
        r = TestClient(app).get(
            "/api/v1/fund/desk/archives/memo", params={"date": "1999-01-01"})
        assert r.status_code == 200
        assert r.json()["reason"] == "no_such_day"

    def test_the_route_serves_the_real_memo(self):
        from fastapi.testclient import TestClient

        from app.main import app
        r = TestClient(app).get("/api/v1/fund/desk/archives/memo")
        body = r.json()
        assert body["available"] is True, body["note"]
        assert body["tldr"], "the CEO's sixty-second read must be on the wire"
        # It must be JSON-clean: the client renders it as markdown.
        json.dumps(body)
