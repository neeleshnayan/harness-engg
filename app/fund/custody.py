"""Custody events — what the broker does to the book without us ordering it.

Dividends, interest and splits change the fund's cash and share counts, and none
of them come from an order. Until this existed the ledger could only explain
what our own fills produced, so every dividend widened the gap between our NAV
and broker equity permanently — a leak whose only symptom is drift that never
resolves and has no event to point at.

Three rules make this safe to run against the real book:

**Idempotent by the venue's own id.** Every activity carries an ``id`` from
Alpaca. That id becomes the event's aggregate id, so re-running the ingest — on
a schedule, after a crash, twice by accident — appends nothing new. This is the
same guarantee ``client_order_id`` gives the order path.

**Unknown types are surfaced, never assumed.** An activity type we do not model
is reported as unhandled rather than being guessed at or dropped. A silently
ignored corporate action is exactly the bug this module exists to prevent.

**Dry run by default.** The caller has to ask for writes. Ingest appends to an
append-only ledger, so a mistake here is not undoable.
"""

from __future__ import annotations

from typing import Any

from app.fund.events import Event, EventStore, EventType

#: Alpaca activity types we understand. Anything else is reported unhandled.
#: - DIV / DIVCGL / DIVNRA / DIVTXEX : cash dividends and their tax variants
#: - INT / INTNRA                    : interest on idle cash
#: - SPLIT / SC                      : share split / stock consolidation
DIVIDEND_TYPES = {"DIV", "DIVCGL", "DIVCGS", "DIVNRA", "DIVROC", "DIVTXEX"}
INTEREST_TYPES = {"INT", "INTNRA"}
SPLIT_TYPES = {"SPLIT", "SC", "REVERSE_SPLIT"}

#: Activity types that are the ORDER path's business, not ours. Named explicitly
#: so they are skipped as "already handled elsewhere" rather than "unrecognised".
TRADE_TYPES = {"FILL", "PTC", "PTR"}


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class CustodyIngest:
    """Folds broker account activities into fund events, exactly once each."""

    def __init__(self, connector, store: EventStore | None = None):
        self._connector = connector
        self._store = store or EventStore()

    def _already_ingested(self, activity_id: str) -> bool:
        try:
            return bool(self._store.by_aggregate(str(activity_id)))
        except Exception:  # noqa: BLE001 — an unreadable log means DO NOT write
            raise

    def plan(self, after: str | None = None) -> dict[str, Any]:
        """What would be ingested. Reads the venue, writes nothing."""
        return self._run(after=after, apply=False, actor="system")

    def apply(self, after: str | None = None, actor: str = "system") -> dict[str, Any]:
        """Append events for activities not already in the log."""
        return self._run(after=after, apply=True, actor=actor)

    def _run(self, after: str | None, apply: bool, actor: str) -> dict[str, Any]:
        activities = self._connector.activities(after=after)

        new: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        unhandled: list[dict[str, Any]] = []

        for a in activities or []:
            aid = a.get("id")
            atype = (a.get("activity_type") or "").upper()

            if not aid:
                unhandled.append({**a, "reason": "activity has no id — cannot be made idempotent"})
                continue
            if atype in TRADE_TYPES:
                skipped.append({"id": aid, "activity_type": atype,
                                "reason": "trade activity — owned by the order path"})
                continue

            built = self._build(a, atype)
            if built is None:
                unhandled.append({
                    **a,
                    "reason": f"activity type {atype!r} is not modelled — it is NOT "
                              "being applied, and the book will disagree with the "
                              "venue until it is handled",
                })
                continue

            if self._already_ingested(aid):
                skipped.append({"id": aid, "activity_type": atype,
                                "reason": "already in the event log"})
                continue

            etype, payload = built
            row = {"id": aid, "activity_type": atype, "event": etype.value,
                   "payload": payload}
            if apply:
                self._store.append(Event(
                    aggregate_id=str(aid),
                    aggregate_type="custody",
                    type=etype,
                    payload={**payload, "activity_id": str(aid), "source": "alpaca"},
                    actor=actor,
                ))
            new.append(row)

        return {
            "applied": apply,
            "scanned": len(activities or []),
            "new": new,
            "skipped": skipped,
            "unhandled": unhandled,
            "counts": {"new": len(new), "skipped": len(skipped),
                       "unhandled": len(unhandled)},
            "note": ("events appended" if apply else
                     "dry run — nothing was written"),
        }

    def _build(self, a: dict[str, Any], atype: str):
        """Map one activity to an event type and payload, or None if unmodelled."""
        symbol = (a.get("symbol") or "").upper() or None
        amount = _f(a.get("net_amount"))
        date = a.get("date") or None

        if atype in DIVIDEND_TYPES:
            if amount is None:
                return None      # a dividend with no amount is not usable
            return EventType.DIVIDEND_RECEIVED, {
                "symbol": symbol, "usd_amount": amount, "date": date,
                "per_share_amount": _f(a.get("per_share_amount")),
                "qty": _f(a.get("qty")),
                "description": a.get("description"),
            }

        if atype in INTEREST_TYPES:
            if amount is None:
                return None
            return EventType.INTEREST_RECEIVED, {
                "usd_amount": amount, "date": date,
                "description": a.get("description"),
            }

        if atype in SPLIT_TYPES:
            # A split needs both share counts to be applied safely. Alpaca's
            # split activities report the CHANGE in quantity, which alone cannot
            # tell us the resulting position — so anything ambiguous is refused
            # rather than applied on a guess about the ratio.
            return None

        return None
