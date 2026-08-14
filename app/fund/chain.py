"""Tamper evidence for the event log.

Append-only is a property of how the fund *writes*, not of what the ledger
*is*. Nothing stops someone holding the service account from editing a filled
price, deleting an inconvenient order, or backdating a subscription — and
because every projection folds obediently from the log, the resulting NAV would
be internally consistent and completely false. "Append-only" was a description
of our own discipline, and an auditor has no reason to take our word for it.

So each event carries the hash of the one before it. Changing any field of any
event changes its hash, which breaks every link after it, and the break is
visible without knowing what the original said. That does not make the log
unfalsifiable — someone with write access could recompute the whole chain — but
it converts silent edits into loud ones, and rewriting an entire history is a
different kind of act from adjusting one number.

Two honest limits, stated because a security property nobody understands the
edges of is worse than none:

  1. Events written before the chain existed cannot be retroactively proved.
     They verify as ``unchained``, never as ``valid``. Claiming otherwise would
     be the exact dishonesty this module exists to prevent.

  2. A break is not proof of tampering. The seq counter and the chain tip
     advance together inside one Firestore transaction, which serialises
     concurrent appends correctly — two processes writing at once is NOT a
     hazard here, contrary to what this note used to claim.

     The real window is a crash: the event document is written after the
     transaction commits, so a process that dies in between leaves the tip
     pointing at an event that does not exist, and the next append chains onto
     a phantom. verify() reports that as a break, which is the intended
     behaviour — a missing event should be loud — but the operator reading the
     break needs to know a crash produces the same signature as an edit.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

#: The link a first event points at. All zeroes, so genesis is recognisable.
GENESIS_HASH = "0" * 64

#: Fields that are hashed. Deliberately explicit rather than "everything except
#: hash": a field added later must be a considered decision to protect it, not
#: an accident of iteration order. `hash` is excluded because it is the output.
HASHED_FIELDS = (
    "seq", "event_id", "aggregate_id", "aggregate_type",
    "type", "payload", "actor", "ts", "prev_hash",
)


def canonical(event: dict[str, Any], prev_hash: str) -> str:
    """A byte-stable rendering of an event, for hashing.

    ``sort_keys`` and a fixed separator matter more than they look: dict order
    is not guaranteed across a Firestore round trip, and a hash that depends on
    key order would report tampering every time the SDK changed its mind.
    """
    body = {k: event.get(k) for k in HASHED_FIELDS if k != "prev_hash"}
    body["prev_hash"] = prev_hash
    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)


def event_hash(event: dict[str, Any], prev_hash: str) -> str:
    return hashlib.sha256(canonical(event, prev_hash).encode("utf-8")).hexdigest()


@dataclass
class ChainVerification:
    ok: bool
    checked: int = 0
    chained: int = 0
    unchained: int = 0
    #: The first event whose hash does not match its contents, if any.
    first_break: Optional[dict[str, Any]] = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checked": self.checked,
            "chained": self.chained,
            "unchained": self.unchained,
            "first_break": self.first_break,
            "notes": self.notes,
        }


def verify(events: list[dict[str, Any]]) -> ChainVerification:
    """Walk the log and report the first link that does not hold.

    Events are expected in seq order. An unchained prefix is tolerated and
    counted — a ledger that predates the chain is not evidence of tampering —
    but once an event carries a hash, every event after it must too. A chain
    that stops halfway is exactly what deleting the tail would look like.
    """
    out = ChainVerification(ok=True)
    prev = GENESIS_HASH
    seen_chained = False

    for e in events:
        out.checked += 1
        stored = e.get("hash")

        if not stored:
            if seen_chained:
                out.ok = False
                out.first_break = {
                    "seq": e.get("seq"), "event_id": e.get("event_id"),
                    "type": e.get("type"),
                    "reason": "event has no hash, but earlier events in the log do "
                              "— the chain cannot stop and restart",
                }
                return out
            out.unchained += 1
            continue

        expected = event_hash(e, e.get("prev_hash") or GENESIS_HASH)

        if not seen_chained:
            # First chained event. Its prev_hash is whatever it was written
            # with — genesis for a fresh ledger, or the last unchained event's
            # absence for a retrofit. Either way we start following from here.
            seen_chained = True
            prev = e.get("prev_hash") or GENESIS_HASH

        if e.get("prev_hash") != prev:
            out.ok = False
            out.first_break = {
                "seq": e.get("seq"), "event_id": e.get("event_id"),
                "type": e.get("type"),
                "reason": f"prev_hash points at {str(e.get('prev_hash'))[:12]}… "
                          f"but the previous event hashes to {prev[:12]}… — an "
                          f"event was altered, inserted or removed before this one",
            }
            return out

        if stored != expected:
            out.ok = False
            out.first_break = {
                "seq": e.get("seq"), "event_id": e.get("event_id"),
                "type": e.get("type"),
                "reason": "stored hash does not match the event's contents — "
                          "this event was altered after it was written",
            }
            return out

        out.chained += 1
        prev = stored

    if out.unchained:
        out.notes.append(
            f"{out.unchained} event(s) predate the hash chain and cannot be "
            f"verified — their integrity is not proved, only unchallenged"
        )
    if not out.chained:
        out.notes.append("no event in this log is chained — there is no tamper evidence")
    return out


def rechain(events: list[dict[str, Any]], start_hash: str = GENESIS_HASH) -> list[dict[str, Any]]:
    """Compute a fresh chain over events, in the order given.

    For building a NEW ledger — a migration, or a replay into a clean
    collection — where the events are known-good and the chain is being laid
    down for the first time.

    Deliberately NOT usable to "repair" a broken chain in place: it would
    happily re-seal a tampered log and report success. Anything that calls this
    must be writing somewhere that had no chain to begin with.
    """
    prev = start_hash
    out: list[dict[str, Any]] = []
    for e in events:
        row = dict(e)
        row["prev_hash"] = prev
        row["hash"] = event_hash(row, prev)
        prev = row["hash"]
        out.append(row)
    return out
