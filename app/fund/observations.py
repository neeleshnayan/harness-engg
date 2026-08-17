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
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
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
                doc["accession"], doc["url"],
                cat if cat in CATEGORIES else "other",
                obs, quote, True, bool(doc.get("truncated")),
            ))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO fund_observations (observation_id, ticker, form, "
                    "filed, accession, url, category, observation, quote, "
                    "quote_verified, truncated) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", rows)
            conn.commit()
        return len(rows)

    # --- reading ------------------------------------------------------------

    def recent(self, ticker: Optional[str] = None, category: Optional[str] = None,
               limit: int = 50) -> list[dict[str, Any]]:
        where, params = [], []
        if ticker:
            where.append("ticker = %s")
            params.append(ticker.upper())
        if category:
            where.append("category = %s")
            params.append(category.lower())
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        params.append(limit)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ticker, form, filed, url, category, observation, "
                    "       quote, truncated, extracted_at "
                    f"FROM fund_observations {clause} "
                    "ORDER BY filed DESC, extracted_at DESC LIMIT %s", params)
                rows = cur.fetchall()
        return [{
            "ticker": r[0], "form": r[1], "filed": r[2].isoformat(),
            "url": r[3], "category": r[4], "observation": r[5],
            "quote": r[6], "read_partial_filing": r[7],
            "extracted_at": r[8].isoformat(),
        } for r in rows]

    def seen_accessions(self, ticker: str) -> set[str]:
        """Filings already read, so a sweep does not pay for them twice."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT accession FROM fund_observations "
                            "WHERE ticker = %s", (ticker.upper(),))
                return {r[0] for r in cur.fetchall()}

    def coverage(self) -> dict[str, Any]:
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
        return {"observations": int(n or 0), "tickers": int(tickers or 0),
                "filings_read": int(filings or 0),
                "last_extracted_at": last.isoformat() if last else None,
                "by_category": by_cat}


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
