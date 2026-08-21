"""Filings, fetched at breadth — the one edge agents have over headcount.

Reading every 8-K and 10-Q across thousands of names is analyst-hours at a real
fund and compute for us. That asymmetry is the whole reason this exists, and it
only pays if the reading is WIDE: one filing read carefully is what a person
already does better.

A thin client on purpose. There is a SEC collector in the thesis package, and
it is not reusable here — it returns thesis-shaped EvidenceItems, hardcodes
about thirty CIKs, and belongs to someone else's design. Coupling research
throughput to a module we must not edit would make his refactor our outage. So
this fetches, and nothing more: no scoring, no narrative, no opinion.

The SEC asks for two things and both are honoured: a User-Agent that identifies
who is calling, and no more than ten requests a second. Being rate-limited off
EDGAR would cost more than the throttle does.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import threading
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

#: SEC requires a contact address. A generic agent gets blocked, and rightly.
USER_AGENT = os.getenv(
    "SEC_USER_AGENT", "Krypton Fund research neelesh.nayan17@gmail.com")

#: SEC's published ceiling is 10 requests/second. We sit under it deliberately:
#: the cost of being throttled off entirely dwarfs the seconds this spends.
MIN_INTERVAL_S = float(os.getenv("SEC_MIN_INTERVAL", "0.15"))

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

#: Forms worth reading, and why.
#:   8-K  material events — the highest signal per byte, and small
#:   10-Q quarterly detail, where a margin inflection actually shows up
#:   10-K annual, including the risk factors that change year to year
DEFAULT_FORMS = ("8-K", "10-Q", "10-K")

#: Documents run to megabytes. A model reading 4MB of exhibits is expensive and
#: no better than one reading the front of the filing, which is where the
#: substance is. Truncation is REPORTED so nothing quietly reasons over a
#: fragment believing it saw the whole.
#: Sized to the model's context, not to the document. 120k characters is about
#: 30k tokens against a 24,576-token window — the 10-Q that exposed this came
#: back as unparseable nothing, because the input never fit. 60k leaves room
#: for the system prompt and the reply.
MAX_CHARS = int(os.getenv("SEC_MAX_DOC_CHARS", "60000"))

_lock = threading.Lock()
_last_call = 0.0
_tickers: Optional[dict[str, dict[str, Any]]] = None


def _throttled_get(url: str, timeout: float = 60.0) -> bytes:
    global _last_call
    with _lock:
        wait = MIN_INTERVAL_S - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout).read()


@dataclass
class Filing:
    ticker: str
    cik: str
    form: str
    filed: str
    accession: str
    document: str
    #: EDGAR's acceptance stamp, stored as the UTC it declares itself to be.
    #:
    #: MEASURED 2026-08-21, because the dispatch brief asserted this field is ET
    #: mislabelled as Z and asked for a -4h shift. It is not, and the shift would
    #: have manufactured the sub-daily lookahead it was meant to remove. Two
    #: independent tests against live EDGAR:
    #:   * hour histogram (n=2,400): activity 10:00-02:00, DEAD 03:00-09:00 —
    #:     exactly EDGAR's 06:00-22:00 ET window read as UTC;
    #:   * decisive — the next-business-day roll-over (EDGAR dates a filing the
    #:     following business day after 17:30 ET) begins at raw hour 21 and
    #:     dominates at 22-23 over n=30,732 filings, with ZERO roll-overs at
    #:     hours 10-20. 21:30 UTC is 17:30 EDT. Under the ET reading the
    #:     roll-over would sit at raw hour 17, where 1,723 filings are same-day
    #:     and none roll over.
    #: None when the feed omitted it — absent, never back-filled from `filed`,
    #: which would invent a time of day.
    accepted_at: Optional[str] = None
    #: The fiscal period the filing REPORTS on (EDGAR reportDate). A different
    #: question from when it was filed. Often absent on an 8-K.
    period: Optional[str] = None
    #: 8-K item codes, comma separated ("2.02,9.01"). Free on the feed and the
    #: cheapest possible filter for "is this an earnings release" (item 2.02).
    items: Optional[str] = None

    @property
    def url(self) -> str:
        return (f"https://www.sec.gov/Archives/edgar/data/{int(self.cik)}/"
                f"{self.accession.replace('-', '')}/{self.document}")

    @property
    def base_url(self) -> str:
        """The filing's directory — where its exhibits live."""
        return (f"https://www.sec.gov/Archives/edgar/data/{int(self.cik)}/"
                f"{self.accession.replace('-', '')}")

    def to_dict(self) -> dict[str, Any]:
        return {"ticker": self.ticker, "cik": self.cik, "form": self.form,
                "filed": self.filed, "accession": self.accession,
                "url": self.url, "accepted_at": self.accepted_at,
                "period": self.period, "items": self.items}


def ticker_map(refresh: bool = False) -> dict[str, dict[str, Any]]:
    """Every ticker the SEC knows, mapped to its CIK.

    Ten thousand companies, not the thirty a hardcoded table can hold — which
    is the difference between reading the market and reading the mega-caps.
    """
    global _tickers
    if _tickers is None or refresh:
        raw = json.loads(_throttled_get(TICKERS_URL).decode())
        _tickers = {
            str(row["ticker"]).upper(): {
                "cik": str(row["cik_str"]).zfill(10),
                "title": row.get("title"),
            }
            for row in raw.values() if row.get("ticker")
        }
        logger.info("EDGAR ticker map loaded: %d companies", len(_tickers))
    return _tickers


def cik_for(ticker: str) -> Optional[str]:
    return (ticker_map().get((ticker or "").strip().upper()) or {}).get("cik")


def recent_filings(ticker: str, forms: Iterable[str] = DEFAULT_FORMS,
                   limit: int = 10, since: Optional[str] = None) -> list[Filing]:
    """The most recent filings for a ticker, newest first.

    ``since`` (YYYY-MM-DD) bounds how far back to look, which is what makes a
    daily sweep cheap: yesterday's filings, not the last five years of them.
    """
    cik = cik_for(ticker)
    if not cik:
        return []
    wanted = {f.upper() for f in forms}
    try:
        doc = json.loads(_throttled_get(SUBMISSIONS_URL.format(cik=cik)).decode())
    except Exception as e:  # noqa: BLE001
        logger.warning("EDGAR submissions failed for %s: %s", ticker, e)
        return []

    rec = (doc.get("filings") or {}).get("recent") or {}
    forms = rec.get("form") or []
    # Parallel arrays, and they are NOT guaranteed to be the same length —
    # `items` in particular is absent on older feeds. `_col` pads with None so a
    # short array degrades to "not stated" rather than truncating the whole
    # result at its length, which a bare zip() would do silently.
    n = len(forms)
    fileds = _col(rec, "filingDate", n)
    accs = _col(rec, "accessionNumber", n)
    primaries = _col(rec, "primaryDocument", n)
    accepted = _col(rec, "acceptanceDateTime", n)
    periods = _col(rec, "reportDate", n)
    items = _col(rec, "items", n)

    out: list[Filing] = []
    for i, form in enumerate(forms):
        primary = primaries[i]
        filed = fileds[i]
        if form.upper() not in wanted or not primary:
            continue
        if since and filed and filed < since:
            # The list is newest-first, so the first filing older than the
            # bound means every one after it is too.
            break
        out.append(Filing(
            ticker.upper(), cik, form, filed, accs[i], primary,
            accepted_at=_utc(accepted[i]),
            period=periods[i] or None,
            items=(items[i] or None)))
        if len(out) >= limit:
            break
    return out


#: EX-99.1 under every naming convention EDGAR filers actually use.
#:
#: Measured on a real 8-K index (SRPT 0001193125-26-335056): the exhibit is
#: `srpt-ex99_1.htm`. Others in the wild use `ex-99_1`, `ex991`, and the
#: DFIN-style `d123456dex991.htm`. The `(?![0-9])` tail is what stops `ex99_10`
#: and `ex99_11` matching as 99.1 — an exhibit-numbering collision would attach
#: the wrong document to an earnings read and nothing downstream would notice.
_EX991_RE = re.compile(r"ex[-_]?99[-_.]?1(?![0-9])", re.I)

#: The 8-K item code for "Results of Operations and Financial Condition" — the
#: earnings release. Free on the submissions feed.
ITEM_EARNINGS = "2.02"


def exhibit_url(filing: "Filing", timeout: float = 60.0) -> dict[str, Any]:
    """The EX-99.1 for a filing, or a stated reason there is none.

    THE DEFECT THIS CLOSES (analyst cycle 2, confirmed on the live API): the
    reader follows `primaryDocument`, which on an 8-K is the COVER PAGE. 83% of
    8-K reads returned zero observations because the cover page contains no
    content — the earnings text lives in exhibit 99.1, which is reachable only
    through the filing index. Measured on SRPT's 2026-08-05 8-K: the cover page
    is 47,594 bytes and `srpt-ex99_1.htm` is 887,797.

    Returns a dict rather than a bare string because the FALLBACK MATTERS: when
    no exhibit is found the caller gets the primary document AND is told that is
    what it is, so a zero-yield read can be attributed to the filing rather than
    to us reading the wrong file. Never raises — a network failure degrades to
    the primary document with the reason attached.
    """
    try:
        raw = _throttled_get(f"{filing.base_url}/index.json", timeout=timeout)
        items = (json.loads(raw.decode()).get("directory") or {}).get("item") or []
    except Exception as e:  # noqa: BLE001
        logger.info("EDGAR index unavailable for %s: %s", filing.accession, e)
        return {"url": filing.url, "document": filing.document, "is_exhibit": False,
                "reason": f"the filing index could not be read ({type(e).__name__}) — "
                          f"fell back to the primary document, which on an 8-K is "
                          f"the cover page"}

    cands = []
    for it in items:
        name = str(it.get("name") or "")
        if not name.lower().endswith((".htm", ".html", ".txt")):
            continue
        if _EX991_RE.search(name):
            try:
                size = int(it.get("size") or 0)
            except (TypeError, ValueError):
                size = 0
            cands.append((size, name))
    if not cands:
        return {"url": filing.url, "document": filing.document, "is_exhibit": False,
                "reason": "no EX-99.1 in this filing's index — the primary "
                          "document is what there is"}
    # Largest wins: a filer occasionally includes a stub alongside the real
    # exhibit, and the content is in the big one.
    cands.sort(reverse=True)
    size, name = cands[0]
    return {"url": f"{filing.base_url}/{name}", "document": name,
            "is_exhibit": True, "bytes": size, "reason": None}


def _col(rec: dict[str, Any], key: str, n: int) -> list[Any]:
    """One parallel column, padded to length. A missing column is all-None."""
    col = rec.get(key) or []
    return list(col) + [None] * max(0, n - len(col))


def _utc(stamp: Optional[str]) -> Optional[str]:
    """EDGAR's acceptance stamp, normalised to an explicit UTC offset.

    NO TIMEZONE SHIFT — see the Filing.accepted_at note. The `Z` is truthful;
    this only rewrites it to `+00:00` so downstream `fromisoformat` on older
    Pythons and Postgres both read it as aware rather than naive. A naive
    timestamp landing in a TIMESTAMPTZ column is interpreted in the SERVER's
    zone, which is how a stamp silently moves by whatever the container is set
    to.
    """
    if not stamp:
        return None
    s = str(stamp).strip()
    if not s:
        return None
    return s[:-1] + "+00:00" if s.endswith("Z") else s


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_NL_RE = re.compile(r"\n{3,}")


#: Inline-XBRL machine tags. A modern 10-Q opens with thousands of these —
#: "0001529274 2026-01-01 2026-06-30 xbrli:shares iso4217:USD" — which survive
#: tag stripping because they are TEXT, not markup. Left in, they eat most of
#: the character budget before a model reaches a sentence, and they are
#: unreadable by design: they exist for parsers, not people.
_XBRL_TOKEN_RE = re.compile(
    r"\b(?:xbrli?|iso4217|utr|srt|us-gaap|dei):[A-Za-z0-9_\-]+")
_BARE_NUM_RE = re.compile(r"^[\d\s.,:\-+%$()/]*$")


def _looks_like_xbrl(line: str) -> bool:
    """A line that is machine context rather than disclosure.

    Two signatures: explicit XBRL namespaces, or a line made only of digits,
    dates and punctuation — which is what a stripped context block leaves
    behind. Prose about money contains words; a context row does not.
    """
    if _XBRL_TOKEN_RE.search(line):
        return True
    stripped = line.strip()
    if len(stripped) > 40 and _BARE_NUM_RE.match(stripped):
        return True
    return False


def _drop_xbrl(text: str) -> str:
    kept = [ln for ln in text.splitlines() if not _looks_like_xbrl(ln)]
    return _NL_RE.sub("\n\n", "\n".join(kept)).strip()


def _to_text(raw: bytes) -> str:
    """Filing HTML to readable text.

    Deliberately crude — no parser dependency for what is mostly tag stripping.
    Script and style blocks go first, because their CONTENTS survive tag
    removal and would otherwise arrive as pages of stylesheet for a model to
    read as though it were disclosure.
    """
    s = raw.decode("utf-8", errors="replace")
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", s)
    s = _TAG_RE.sub(" ", s)
    s = html.unescape(s)
    s = _WS_RE.sub(" ", s)
    s = _NL_RE.sub("\n\n", s)
    s = "\n".join(line.strip() for line in s.splitlines()).strip()
    return _drop_xbrl(s)


#: Where the substance is. In a 10-Q or 10-K the numbers are in the financial
#: statements, but the EXPLANATION — margin direction, guidance language, what
#: management blames — is in Management's Discussion and Analysis. Reading from
#: there beats reading the first N characters, which is mostly cover page,
#: signature blocks and the table of contents.
_MDA_RE = re.compile(
    r"(?is)\bitem\s*[27][\.\s]{0,4}\s*management.{0,5}s\s+discussion")
#: The MD&A ends where the market-risk or controls item begins.
_MDA_END_RE = re.compile(
    r"(?is)\bitem\s*[3489][\.\s]{0,4}\s*(quantitative|controls|legal|other)")


def focus_section(text: str) -> tuple[str, Optional[str]]:
    """Narrow to MD&A when the document has one.

    Returns the text and which section it is, so a reader knows whether it saw
    the discussion or the whole filing. The last match wins for the start: the
    phrase appears in the table of contents first, and anchoring there would
    "find" the section and return the contents page.
    """
    starts = list(_MDA_RE.finditer(text))
    if not starts:
        return text, None
    begin = starts[-1].start()
    tail = text[begin:]
    end = _MDA_END_RE.search(tail, pos=200)
    return (tail[:end.start()] if end else tail), "MD&A"


def document_text(filing: Filing, max_chars: int = MAX_CHARS,
                  focus: bool = True, follow_exhibit: bool = True) -> dict[str, Any]:
    """The filing as text, with truncation reported rather than hidden.

    ON AN 8-K THIS FOLLOWS THE INDEX TO EX-99.1 (analyst cycle 2, 2026-08-21).
    `primaryDocument` on an 8-K is the cover page: 83% of 8-K reads returned
    zero observations because the content a reader wants — the item 2.02
    earnings release — is an exhibit. Measured on SRPT's 2026-08-05 8-K, the
    cover page is 47,594 bytes against 887,797 for `srpt-ex99_1.htm`.

    Which document was actually read is REPORTED (`document_read`,
    `is_exhibit`, `exhibit_note`), so a zero-yield read is attributable to the
    filing rather than to us having read the wrong file. `follow_exhibit=False`
    restores the old behaviour for a caller that genuinely wants the cover page.
    """
    url, exhibit = filing.url, None
    if follow_exhibit and filing.form.upper().startswith("8-K"):
        exhibit = exhibit_url(filing)
        url = exhibit["url"]
    try:
        raw = _throttled_get(url, timeout=120.0)
    except Exception as e:  # noqa: BLE001
        return {**filing.to_dict(), "text": None,
                "document_read": (exhibit or {}).get("document") or filing.document,
                "error": f"{type(e).__name__}: {e}"[:200]}
    text = _to_text(raw)
    full_chars = len(text)
    section = None
    if focus:
        text, section = focus_section(text)
    truncated = len(text) > max_chars
    return {
        **filing.to_dict(),
        # WHICH document this text came from. Without it, "the 8-K said nothing"
        # and "we read the cover page" are the same row.
        "document_read": (exhibit or {}).get("document") or filing.document,
        "url_read": url,
        "is_exhibit": bool((exhibit or {}).get("is_exhibit")),
        "exhibit_note": (exhibit or {}).get("reason"),
        "text": text[:max_chars],
        "chars": len(text),
        "full_chars": full_chars,
        "section": section,
        "truncated": truncated,
        # Stated so no downstream reader believes it saw the whole filing. A
        # model reasoning over the first third of a 10-K and one reasoning over
        # all of it should not be indistinguishable in the record.
        "truncation_note": (f"read the first {max_chars:,} of {len(text):,} "
                            f"characters" if truncated else None),
    }
