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

    @property
    def url(self) -> str:
        return (f"https://www.sec.gov/Archives/edgar/data/{int(self.cik)}/"
                f"{self.accession.replace('-', '')}/{self.document}")

    def to_dict(self) -> dict[str, Any]:
        return {"ticker": self.ticker, "cik": self.cik, "form": self.form,
                "filed": self.filed, "accession": self.accession, "url": self.url}


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
    rows = zip(rec.get("form") or [], rec.get("filingDate") or [],
               rec.get("accessionNumber") or [], rec.get("primaryDocument") or [])
    out: list[Filing] = []
    for form, filed, acc, primary in rows:
        if form.upper() not in wanted or not primary:
            continue
        if since and filed < since:
            # The list is newest-first, so the first filing older than the
            # bound means every one after it is too.
            break
        out.append(Filing(ticker.upper(), cik, form, filed, acc, primary))
        if len(out) >= limit:
            break
    return out


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
                  focus: bool = True) -> dict[str, Any]:
    """The filing as text, with truncation reported rather than hidden."""
    try:
        raw = _throttled_get(filing.url, timeout=120.0)
    except Exception as e:  # noqa: BLE001
        return {**filing.to_dict(), "text": None,
                "error": f"{type(e).__name__}: {e}"[:200]}
    text = _to_text(raw)
    full_chars = len(text)
    section = None
    if focus:
        text, section = focus_section(text)
    truncated = len(text) > max_chars
    return {
        **filing.to_dict(),
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
