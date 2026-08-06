"""Exact money & unit arithmetic.

Money and units are ``Decimal`` everywhere accounting happens — never ``float``,
whose binary rounding drifts through NAV/unit, ownership %, and payouts.

Boundaries:
  * **Storage** — Firestore can't store ``Decimal``, so ``encode()`` serializes it
    to a string on write; readers wrap fields in ``D()`` (which parses strings).
  * **Venues** — connectors speak the broker's ``float``; convert at ingestion with
    ``D(str(x))`` so we don't inherit the float's binary error.
  * **JSON edge** — responses downcast with ``f()`` for display only. Display
    rounding is not accounting.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

CENTS = Decimal("0.01")
UNIT_Q = Decimal("0.000001")
PRICE_Q = Decimal("0.0001")


def D(x: Any) -> Decimal:
    """Coerce to Decimal without inheriting float binary error (via str)."""
    if isinstance(x, Decimal):
        return x
    if isinstance(x, float):
        return Decimal(str(x))
    return Decimal(x)  # int or str


def money(x: Any) -> Decimal:
    return D(x).quantize(CENTS, rounding=ROUND_HALF_UP)


def units(x: Any) -> Decimal:
    return D(x).quantize(UNIT_Q, rounding=ROUND_HALF_UP)


def price(x: Any) -> Decimal:
    return D(x).quantize(PRICE_Q, rounding=ROUND_HALF_UP)


def f(x: Optional[Decimal]) -> Optional[float]:
    """Downcast to float at the JSON/display edge. Never used for accounting."""
    return None if x is None else float(x)


def encode(obj: Any) -> Any:
    """Recursively serialize Decimals to strings for Firestore storage."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, dict):
        return {k: encode(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [encode(v) for v in obj]
    return obj
