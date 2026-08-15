"""Risk history — the time dimension the risk page lacked.

Every number on the risk page is a snapshot; risk that is DRIFTING — book vol
creeping up, effective bets bleeding away as positions converge — is invisible
until it breaches something. This keeps a compact point per fresh engine
compute so the page can draw the drift.

Telemetry, not fund state: rows live in their own collection, never the event
log. Losing them costs a chart, not a fact. Appends are deduped so a nervous
operator clicking Recompute does not turn the series into noise.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

COLLECTION = "fund_risk_history"

#: A fresh compute within this window of the last stored point, with the same
#: book fingerprint, refines the same picture rather than adding information.
MIN_GAP_SECONDS = 600


class RiskHistory:
    def __init__(self, db=None):
        if db is None:
            from app.core.firebase import db as _db
            db = _db()
        self._db = db

    def append(self, point: dict[str, Any], fingerprint: str = "") -> bool:
        """Store one point; returns False when deduped or unwritable."""
        try:
            ts = datetime.now(timezone.utc)
            last = self.recent(limit=1)
            if last:
                prev = last[-1]
                try:
                    prev_ts = datetime.fromisoformat(str(prev.get("ts")))
                    same_book = (prev.get("fingerprint") or "") == fingerprint
                    if same_book and (ts - prev_ts).total_seconds() < MIN_GAP_SECONDS:
                        return False
                except (ValueError, TypeError):
                    pass
            row = {**point, "ts": ts.isoformat(), "fingerprint": fingerprint}
            # Doc id carries a suffix: Windows clock granularity can stamp two
            # appends with the same microsecond, and a same-id set() silently
            # overwrites the earlier point.
            doc_id = f"{row['ts']}_{uuid4().hex[:6]}"
            self._db.collection(COLLECTION).document(doc_id).set(row)
            return True
        except Exception as e:  # noqa: BLE001 — a chart must never break the compute
            logger.warning("risk history append failed: %s", e)
            return False

    def recent(self, limit: int = 180) -> list[dict[str, Any]]:
        """Newest-last (chart order)."""
        try:
            from firebase_admin import firestore

            q = (self._db.collection(COLLECTION)
                 .order_by("ts", direction=firestore.Query.DESCENDING)
                 .limit(limit)
                 .stream())
            rows = [d.to_dict() for d in q]
            # Local ascending sort rather than reversed(): two points can share
            # a timestamp (coarse Windows clock), and reversing a stable
            # descending sort flips such pairs.
            rows.sort(key=lambda r: str(r.get("ts", "")))
            return rows
        except Exception as e:  # noqa: BLE001
            logger.warning("risk history read failed: %s", e)
            return []
