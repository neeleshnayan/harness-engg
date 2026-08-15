"""Query parser for investment thesis requests."""

from __future__ import annotations

import re
from typing import Optional
from pydantic import BaseModel

from app.fund.thesis_generator.models import Direction


class ParsedQuery(BaseModel):
    raw_query: str
    ticker: str
    direction: Direction = Direction.LONG
    theme_hint: Optional[str] = None


class QueryParser:
    """Parses natural language prompts and command strings into structured thesis query targets."""

    # Common ticker overrides/aliases if typed as company names
    NAME_TO_TICKER = {
        "NVIDIA": "NVDA",
        "APPLE": "AAPL",
        "MICROSOFT": "MSFT",
        "TESLA": "TSLA",
        "AMAZON": "AMZN",
        "ALPHABET": "GOOGL",
        "GOOGLE": "GOOGL",
        "META": "META",
        "FACEBOOK": "META",
        "ADVANCED MICRO DEVICES": "AMD",
        "INTEL": "INTC",
        "BROADCOM": "AVGO",
        "TAIWAN SEMICONDUCTOR": "TSM",
        "SUPER MICRO": "SMCI",
        "PALANTIR": "PLTR",
        "NETFLIX": "NFLX",
    }

    @classmethod
    def parse(cls, query_str: str) -> ParsedQuery:
        q = (query_str or "").strip()
        if not q:
            raise ValueError("Query string cannot be empty")

        # 1. Pattern: "Create thesis (Long|Short) [TICKER] on [THEME_HINT]"
        m = re.search(r"(?:create\s+thesis\s+)?(long|short)\s+([A-Za-z0-9\.\-]+)\s+(?:on|for)\s+(.+)", q, re.IGNORECASE)
        if m:
            side_str, sym, hint = m.groups()
            direction = Direction.SHORT if side_str.upper() == "SHORT" else Direction.LONG
            ticker = cls._normalize_ticker(sym)
            return ParsedQuery(raw_query=q, ticker=ticker, direction=direction, theme_hint=hint.strip())

        # 2. Pattern: "Create thesis (Long|Short) [TICKER]"
        m = re.search(r"(?:create\s+thesis\s+)?(long|short)\s+([A-Za-z0-9\.\-]+)", q, re.IGNORECASE)
        if m:
            side_str, sym = m.groups()
            direction = Direction.SHORT if side_str.upper() == "SHORT" else Direction.LONG
            ticker = cls._normalize_ticker(sym)
            return ParsedQuery(raw_query=q, ticker=ticker, direction=direction)

        # 3. Pattern: "Thesis on [TICKER]" or "Analyze [TICKER]"
        m = re.search(r"(?:thesis\s+(?:on|for)\s+|analyze\s+|research\s+)([A-Za-z0-9\.\-]+)", q, re.IGNORECASE)
        if m:
            sym = m.group(1)
            ticker = cls._normalize_ticker(sym)
            return ParsedQuery(raw_query=q, ticker=ticker, direction=Direction.LONG)

        # 4. Pattern: Short [TICKER] or Long [TICKER]
        tokens = [t.strip(",.!?") for t in q.split() if t.strip(",.!?")]
        direction = Direction.LONG
        if tokens and tokens[0].upper() in ("SHORT", "BEAR", "BEARISH"):
            direction = Direction.SHORT
            tokens = tokens[1:]
        elif tokens and tokens[0].upper() in ("LONG", "BULL", "BULLISH"):
            direction = Direction.LONG
            tokens = tokens[1:]

        # Look for the best ticker token
        for token in tokens:
            cleaned = re.sub(r"[^A-Za-z0-9\.\-]", "", token).upper()
            if cleaned in cls.NAME_TO_TICKER:
                return ParsedQuery(raw_query=q, ticker=cls.NAME_TO_TICKER[cleaned], direction=direction)
            if 1 <= len(cleaned) <= 6 and cleaned.isalpha():
                # Avoid keywords
                if cleaned not in ("CREATE", "THESIS", "STOCK", "SHARE", "TRADE", "BUY", "SELL", "HOLD", "THE", "FOR", "AND"):
                    return ParsedQuery(raw_query=q, ticker=cleaned, direction=direction)

        # Fallback: first alphabetic token
        fallback_sym = re.sub(r"[^A-Za-z]", "", q.split()[0] if q.split() else "NVDA").upper()
        return ParsedQuery(raw_query=q, ticker=fallback_sym or "NVDA", direction=direction)

    @classmethod
    def _normalize_ticker(cls, raw: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9\.\-]", "", raw).upper()
        if cleaned in cls.NAME_TO_TICKER:
            return cls.NAME_TO_TICKER[cleaned]
        return cleaned
