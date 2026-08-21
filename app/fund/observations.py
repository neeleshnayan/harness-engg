"""What the filings actually said, with the receipts.

The output here is deliberately NOT trade ideas. An observation is a checkable
statement about a document — "gross margin fell for a third consecutive quarter
while management described the pressure as transitory" — and the leap from that
to a position is a separate step a person takes, in the open. Collapsing the two
would produce a machine that recommends trades from prose nobody verified, which
is the opposite of everything else in this system.

The load-bearing mechanism is the QUOTE. Every observation must carry a verbatim
span from the filing, and every span is checked against the source text before
the observation is stored. A model that invents a plausible sentence gets caught
by string matching rather than by a reader's memory, and an observation whose
citation cannot be found is discarded rather than flagged — a "probably real"
finding in a research pipeline is worse than none, because it will be quoted
later without the caveat.

That check is cheap and it is the whole difference between reading at breadth
and hallucinating at breadth.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS fund_observations (
    observation_id TEXT PRIMARY KEY,
    ticker         TEXT        NOT NULL,
    form           TEXT        NOT NULL,
    filed          DATE        NOT NULL,
    accession      TEXT        NOT NULL,
    url            TEXT        NOT NULL,
    category       TEXT,
    observation    TEXT        NOT NULL,
    quote          TEXT        NOT NULL,
    quote_verified BOOLEAN     NOT NULL DEFAULT FALSE,
    truncated      BOOLEAN     NOT NULL DEFAULT FALSE,
    extracted_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fund_observations_ticker_idx
    ON fund_observations (ticker, filed DESC);
CREATE INDEX IF NOT EXISTS fund_observations_accession_idx
    ON fund_observations (accession);

-- POINT-IN-TIME (analyst cycle 2, 2026-08-21). `filed` is a DATE, so every
-- observation from one day is indistinguishable in time from every other — and
-- 55.9% of this corpus shares a filing date with another observation on the
-- same name. A backtest that reads them in id order is reading the future
-- inside a day.
--
-- `accepted_at` is EDGAR's own acceptance stamp, which resolves that ordering
-- to the second. `period` is the fiscal period the filing REPORTS on, which is
-- a different question from when it was filed and the one most ratio work
-- actually wants.
ALTER TABLE fund_observations ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMPTZ;
ALTER TABLE fund_observations ADD COLUMN IF NOT EXISTS period DATE;
ALTER TABLE fund_observations ADD COLUMN IF NOT EXISTS items TEXT;
CREATE INDEX IF NOT EXISTS fund_observations_accepted_idx
    ON fund_observations (ticker, accepted_at DESC);

-- THE TIMEZONE, MEASURED RATHER THAN ASSUMED — and the brief was wrong.
--
-- The dispatch brief stated that `acceptanceDateTime` "carries a Z suffix but is
-- ET = the stamp minus 4 hours" and asked for it to be shifted on the way in.
-- Two independent measurements against the live EDGAR API on 2026-08-21 refute
-- that, so NO SHIFT IS APPLIED and the stamp is stored as the UTC it says it is:
--
--   1. Hour histogram, n=2,400 acceptance stamps across six issuers: activity
--      runs 10:00-02:00 with a DEAD ZONE at 03:00-09:00. EDGAR's dissemination
--      window is 06:00-22:00 ET, which under a genuine-UTC reading maps to
--      exactly 10:00-02:00 UTC. Under the ET reading, 43.6% of filings would
--      have been accepted while EDGAR was closed.
--   2. Decisive: EDGAR dates a filing the NEXT business day when it is accepted
--      after 17:30 ET. Over n=30,732 filings the next-day roll-over begins at
--      raw hour 21 (443 rows), dominates at 22 (1,045) and 23 (1,087), and is
--      ZERO at hours 10-20. 21:30 UTC IS 17:30 EDT. Were the stamp ET, the
--      roll-over would appear at raw hour 17 — where there are 1,723 same-day
--      filings and none rolled over.
--
-- Had the -4h shift been applied, every stamp at hours 22-23 (2,132 of 30,732
-- in that sample) would have moved to the previous evening, manufacturing the
-- sub-daily ordering error this column exists to remove.
COMMENT ON COLUMN fund_observations.accepted_at IS
    'EDGAR acceptanceDateTime, stored as genuine UTC. Measured 2026-08-21: the '
    'Z suffix is truthful. The next-business-day roll-over appears at 21:00-23:00 '
    'in the raw stamp (= 17:30 ET), not at 17:00, over n=30,732 filings. NO '
    'timezone shift is applied and none should be added without repeating that '
    'measurement.';
COMMENT ON COLUMN fund_observations.period IS
    'EDGAR reportDate - the fiscal period the filing REPORTS on, which is not '
    'when it was filed. NULL where the feed carried none (common on 8-K).';
COMMENT ON COLUMN fund_observations.items IS
    'EDGAR 8-K item codes, comma separated (e.g. "2.02,9.01"). Free on the '
    'submissions feed. NULL/empty on forms that do not use them.';
"""

#: Categories worth separating. Not a taxonomy of everything — a short list of
#: the things that actually move a small-cap and that a filing states plainly.
CATEGORIES = (
    "margin", "guidance", "segment", "liquidity", "customer_concentration",
    "insider", "litigation", "going_concern", "dilution", "other",
)

SYSTEM_PROMPT = f"""You read SEC filings and extract CHECKABLE OBSERVATIONS.

You are NOT an analyst and you do NOT recommend trades. You do not say a stock
is cheap, attractive, a buy, a sell, or a risk worth taking. Someone else makes
that judgement, later, in the open, and your job is to give them facts they can
verify.

Return STRICT JSON, an object with one key "observations", whose value is a list
of at most 6 items. Each item:

  {{"category": one of {list(CATEGORIES)},
    "observation": "one sentence, specific, containing the actual numbers",
    "quote": "a VERBATIM span copied exactly from the filing, 10-40 words"}}

Rules that matter more than completeness:

1. The quote must be copied EXACTLY from the text given to you, character for
   character. Do not paraphrase, do not tidy, do not join two sentences. Every
   quote is checked against the source and any that cannot be found is thrown
   away along with its observation.
2. If the filing says nothing notable, return an empty list. An empty list is a
   correct and useful answer. Inventing something to fill the space is not.
3. Prefer specifics with numbers over characterisations. "Gross margin fell to
   61.2% from 64.8%" is worth something; "margins were pressured" is not.
4. Never infer. If the filing does not say it, it is not an observation.

Return only the JSON object. No preamble, no explanation, no markdown fence."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


_WS = re.compile(r"\s+")


def _normalise(s: str) -> str:
    """Whitespace-insensitive comparison text.

    A quote that differs only in line breaks or double spaces IS the filing's
    sentence — the document is reflowed HTML, and holding a model to byte
    equality across that would reject honest citations.
    """
    return _WS.sub(" ", (s or "")).strip().lower()


def verify_quote(quote: str, source: str, min_words: int = 6) -> bool:
    """Does this span actually appear in the filing?

    Whitespace-insensitive, case-insensitive, and it refuses very short quotes:
    a four-word fragment appears in almost any document by chance, so accepting
    one would make the check pass without proving anything.
    """
    q = _normalise(quote)
    if len(q.split()) < min_words:
        return False
    return q in _normalise(source)


class Observations:
    """Extracted findings, and the receipts that let someone check them."""

    def __init__(self, dsn_str: Optional[str] = None):
        from app.fund.pgstore import dsn
        self._dsn = dsn_str or dsn()
        self._ensure_schema()

    def _connect(self):
        import psycopg
        return psycopg.connect(self._dsn, autocommit=False)

    def _ensure_schema(self) -> None:
        # The reviews table is owned by provenance, but `recent()` now joins it
        # to report what a human already decided. Created here too, so reading
        # observations never depends on whether anything has reviewed one yet.
        from app.fund.provenance import SCHEMA as PROVENANCE_SCHEMA

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
                cur.execute(PROVENANCE_SCHEMA)
            conn.commit()

    # --- extraction ---------------------------------------------------------

    def extract(self, doc: dict[str, Any], model_fn=None) -> dict[str, Any]:
        """Read one filing and store what survives verification.

        ``model_fn`` takes (system_prompt, user_text) and returns the model's
        reply. Injectable so this is testable without a model, and so the
        provider can change without touching the verification logic — which is
        the part that must never be skipped.
        """
        text = doc.get("text")
        if not text:
            return {"stored": 0, "error": doc.get("error") or "no text"}

        if model_fn is None:
            model_fn = _default_model

        try:
            reply = model_fn(SYSTEM_PROMPT, _user_prompt(doc, text))
        except Exception as e:  # noqa: BLE001
            return {"stored": 0, "error": f"{type(e).__name__}: {e}"[:300]}

        items = _parse(reply)
        if items is None:
            return {"stored": 0, "error": "model did not return usable JSON"}

        kept, rejected = [], []
        for it in items:
            quote = str(it.get("quote") or "")
            obs = str(it.get("observation") or "").strip()
            if not obs or not quote:
                continue
            if verify_quote(quote, text):
                kept.append((it, quote, obs))
            else:
                # Discarded, not flagged. A "probably real" finding gets quoted
                # later without its caveat, which is worse than never having it.
                rejected.append(obs[:120])

        stored = self._store(doc, kept)
        if rejected:
            logger.info("%s %s: %d observation(s) dropped, citation not found "
                        "in the filing", doc.get("ticker"), doc.get("form"),
                        len(rejected))
        return {
            "ticker": doc.get("ticker"), "form": doc.get("form"),
            "stored": stored,
            "rejected_unverifiable": len(rejected),
            "rejected_examples": rejected[:3],
            "truncated": bool(doc.get("truncated")),
        }

    def _store(self, doc: dict[str, Any], kept: list) -> int:
        if not kept:
            return 0
        rows = []
        for it, quote, obs in kept:
            cat = str(it.get("category") or "other").lower()
            rows.append((
                uuid.uuid4().hex[:16], doc["ticker"], doc["form"], doc["filed"],
                doc["accession"],
                # The URL ACTUALLY READ, which on an 8-K is now the EX-99.1
                # exhibit rather than the cover page. Storing `url` here would
                # cite a document the observation did not come from — a quote
                # that cannot be found at its own citation.
                doc.get("url_read") or doc["url"],
                cat if cat in CATEGORIES else "other",
                obs, quote, True, bool(doc.get("truncated")),
                # Point-in-time (analyst cycle 2). None stays None: an absent
                # acceptance stamp must never be back-filled from `filed`, which
                # would invent a time of day and re-create the intra-day
                # ordering error these columns exist to remove.
                doc.get("accepted_at"), doc.get("period") or None,
                doc.get("items") or None,
            ))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO fund_observations (observation_id, ticker, form, "
                    "filed, accession, url, category, observation, quote, "
                    "quote_verified, truncated, accepted_at, period, items) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", rows)
            conn.commit()
        return len(rows)

    # --- reading ------------------------------------------------------------

    def recent(self, ticker: Optional[str] = None, category: Optional[str] = None,
               limit: int = 50) -> list[dict[str, Any]]:
        where, params = [], []
        if ticker:
            where.append("o.ticker = %s")
            params.append(ticker.upper())
        if category:
            where.append("o.category = %s")
            params.append(category.lower())
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        params.append(limit)
        with self._connect() as conn:
            with conn.cursor() as cur:
                # observation_id is not decoration: it is the handle every
                # downstream action needs. Without it a reader can see an
                # observation but cannot record a judgement about it or attach it
                # to a candidate — which is why the provenance report had nothing
                # to work with and could never answer whether a category pays.
                # The loop was unclosable, and this column is the reason.
                cur.execute(
                    "SELECT o.ticker, o.form, o.filed, o.url, o.category, "
                    "       o.observation, o.quote, o.truncated, o.extracted_at, "
                    "       o.observation_id, r.outcome "
                    "FROM fund_observations o "
                    "LEFT JOIN fund_observation_reviews r "
                    "       ON r.observation_id = o.observation_id "
                    f"{clause} "
                    "ORDER BY o.filed DESC, o.extracted_at DESC LIMIT %s", params)
                rows = cur.fetchall()
        return [{
            "ticker": r[0], "form": r[1], "filed": r[2].isoformat(),
            "url": r[3], "category": r[4], "observation": r[5],
            "quote": r[6], "read_partial_filing": r[7],
            "extracted_at": r[8].isoformat(),
            "observation_id": r[9],
            # What a human already decided about this, so the UI can show a
            # judgement rather than asking for it twice.
            "reviewed": r[10],
        } for r in rows]

    def since(self, when: datetime) -> list[dict[str, Any]]:
        """Observations extracted after a moment in time.

        By EXTRACTION time, not filing date: the digest asks "what did the
        machine read while I was asleep", and a filing published last quarter
        that we only read last night is overnight news to this fund. Sorting on
        `filed` would answer a different question and quietly report nothing.
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT observation_id, ticker, form, filed, url, category, "
                    "       observation, quote, extracted_at "
                    "FROM fund_observations WHERE extracted_at >= %s "
                    "ORDER BY extracted_at DESC", (when,))
                rows = cur.fetchall()
        return [{"observation_id": r[0], "ticker": r[1], "form": r[2],
                 "filed": r[3].isoformat(), "url": r[4], "category": r[5],
                 "observation": r[6], "quote": r[7],
                 "extracted_at": r[8].isoformat()} for r in rows]

    def seen_accessions(self, ticker: str) -> set[str]:
        """Filings already read, so a sweep does not pay for them twice."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT accession FROM fund_observations "
                            "WHERE ticker = %s", (ticker.upper(),))
                return {r[0] for r in cur.fetchall()}

    def coverage(self, adv_lo: Optional[float] = None,
                 adv_hi: Optional[float] = None) -> dict[str, Any]:
        """How much has been read — against the market, and against OUR band.

        Whole-market coverage was the headline and it flattered us in the most
        misleading direction available: it made the denominator every listed
        company, when the fund's entire thesis is that its edge lives in one
        narrow ADV band. Reading a thousand mega-caps would move that number and
        mean nothing. Reading forty band names would barely move it and be the
        whole job.

        So band coverage is reported alongside, with its own denominator. When
        the band bounds are not supplied the band figures are absent rather than
        guessed — a coverage ratio computed against an assumed band would be a
        number about nothing.
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*), count(DISTINCT ticker), "
                    "       count(DISTINCT accession), max(extracted_at) "
                    "FROM fund_observations")
                n, tickers, filings, last = cur.fetchone()
                cur.execute("SELECT category, count(*) FROM fund_observations "
                            "GROUP BY category ORDER BY count(*) DESC")
                by_cat = dict(cur.fetchall())

                band: dict[str, Any] = {
                    "measured": False,
                    "note": ("band coverage needs the ADV bounds to have a "
                             "denominator; without them it is not reported "
                             "rather than assumed"),
                }
                if adv_lo is not None and adv_hi is not None:
                    # Operating companies only, matching the hunting ground: the
                    # band's own definition excludes ETFs, so counting them in
                    # the denominator would understate coverage of the ground we
                    # actually fish.
                    cur.execute("""
                        SELECT count(*) FROM fund_universe u
                        JOIN fund_ticker_reference r ON r.ticker = u.symbol
                        WHERE u.adv_usd BETWEEN %s AND %s
                          AND r.type = ANY(%s)
                    """, (adv_lo, adv_hi, list(_OPERATING_TYPES())))
                    band_total = int(cur.fetchone()[0] or 0)
                    cur.execute("""
                        SELECT count(DISTINCT o.ticker) FROM fund_observations o
                        JOIN fund_universe u ON u.symbol = o.ticker
                        JOIN fund_ticker_reference r ON r.ticker = o.ticker
                        WHERE u.adv_usd BETWEEN %s AND %s
                          AND r.type = ANY(%s)
                    """, (adv_lo, adv_hi, list(_OPERATING_TYPES())))
                    band_read = int(cur.fetchone()[0] or 0)
                    band = {
                        "measured": True,
                        "adv_band_usd": [adv_lo, adv_hi],
                        "names_in_band": band_total,
                        "names_read": band_read,
                        "coverage_pct": (round(100.0 * band_read / band_total, 2)
                                         if band_total else None),
                        "note": _band_note(band_read, band_total, int(tickers or 0)),
                    }
        return {"observations": int(n or 0), "tickers": int(tickers or 0),
                "filings_read": int(filings or 0),
                "last_extracted_at": last.isoformat() if last else None,
                "by_category": by_cat,
                "band": band}



def _OPERATING_TYPES():
    from app.fund.tickerref import OPERATING_TYPES
    return OPERATING_TYPES


def _band_note(read: int, total: int, read_anywhere: int) -> str:
    """Says plainly whether the reading went where the edge is claimed.

    The gap between these two numbers was the finding that prompted this: 84
    names read, of which one was in the tested universe. Breadth across the wrong
    population is not coverage, and a single percentage hid that completely.
    """
    if not total:
        return ("no band names are measured yet, so there is no denominator — "
                "refresh the universe before reading this as coverage")
    if read == 0:
        return (f"none of the {total} band names have been read, while "
                f"{read_anywhere} names have been read elsewhere — the reading "
                f"is not going where the edge is claimed to be")
    off_band = max(0, read_anywhere - read)
    return (f"{read} of {total} band names read ({100.0 * read / total:.1f}%); "
            f"{off_band} of the names read are outside the band and do not bear "
            f"on the thesis")

def _user_prompt(doc: dict[str, Any], text: str) -> str:
    head = (f"{doc.get('ticker')} {doc.get('form')} filed {doc.get('filed')}."
            + (f" NOTE: {doc.get('truncation_note')}."
               if doc.get("truncation_note") else ""))
    return f"{head}\n\n---FILING TEXT---\n{text}"


_FENCE = re.compile(r"```(?:json)?\s*\n(.*?)```", re.DOTALL)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _parse(reply: str) -> Optional[list[dict[str, Any]]]:
    """The observations list, dug out of whatever the model wrapped it in."""
    s = _THINK.sub("", reply or "")
    fenced = _FENCE.findall(s)
    for candidate in (fenced + [s]):
        c = candidate.strip()
        start = c.find("{")
        if start < 0:
            continue
        try:
            obj = json.loads(c[start:c.rfind("}") + 1])
        except Exception:  # noqa: BLE001
            continue
        items = obj.get("observations") if isinstance(obj, dict) else None
        if isinstance(items, list):
            return items
    return None


def _default_model(system: str, user: str) -> str:
    """Local model via Ollama, thinking off.

    Extraction is transcription with judgement, not deliberation, and a
    reasoning model left to itself spends its budget narrating before it
    reaches the JSON.
    """
    import httpx
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    body = {
        "model": os.getenv("OLLAMA_MODEL", "qwen3.5:9b"),
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False, "think": False,
        "format": "json",
        "options": {"temperature": 0.1,
                    "num_ctx": int(os.getenv("OLLAMA_NUM_CTX", "24576")),
                    "num_predict": 2048},
    }
    with httpx.Client(timeout=600.0) as client:
        r = client.post(f"{host}/api/chat", json=body)
        if r.status_code == 400:
            body.pop("think", None)
            r = client.post(f"{host}/api/chat", json=body)
        r.raise_for_status()
        return str((r.json().get("message") or {}).get("content") or "")


def sweep(tickers: list[str], forms: tuple = ("10-Q", "8-K"),
          since: Optional[str] = None, per_ticker: int = 2,
          store: Optional["Observations"] = None,
          model_fn=None) -> dict[str, Any]:
    """Read filings across many names — the breadth this whole module is for.

    Skips filings already read, so a daily sweep costs only what is new. That
    is what makes reading five thousand names a routine rather than an event:
    the second run is nearly free.

    One name failing must never stop the sweep. A delisted ticker, a company
    that files in a format the parser chokes on, a network blip — each is
    recorded and stepped over, because a sweep that aborts on the first
    awkward filing reads the alphabet up to the first bankruptcy.
    """
    from app.fund.edgar import document_text, recent_filings

    obs = store or Observations()
    read = skipped = failed = stored = 0
    per_name: list[dict[str, Any]] = []

    for ticker in tickers:
        try:
            seen = obs.seen_accessions(ticker)
            filings = recent_filings(ticker, forms=forms, limit=per_ticker,
                                     since=since)
            fresh = [f for f in filings if f.accession not in seen]
            skipped += len(filings) - len(fresh)
            for f in fresh:
                doc = document_text(f)
                out = obs.extract(doc, model_fn=model_fn)
                read += 1
                stored += out.get("stored", 0)
                per_name.append({"ticker": ticker, "form": f.form,
                                 "filed": f.filed, **out})
        except Exception as e:  # noqa: BLE001
            failed += 1
            logger.warning("sweep: %s failed, continuing: %s", ticker, e)
            per_name.append({"ticker": ticker, "error": f"{type(e).__name__}: {e}"[:200]})

    return {
        "tickers": len(tickers), "filings_read": read,
        "already_read": skipped, "tickers_failed": failed,
        "observations_stored": stored,
        "detail": per_name,
        "note": ("observations are checkable statements with verified quotes, "
                 "not trade ideas — turning one into a position is a separate, "
                 "human step"),
    }
