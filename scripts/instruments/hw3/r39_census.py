"""THE R39 CENSUS — how many times was one decision decided, and on how many rows.

The measurement behind ``app/fund/ticketguard.py`` and the acceptance test
``tests/test_ticket_decision_ref.py``. Shelved rather than left in a session
scratchpad, because a register citation must outlive the session that made it
(builder D41; the same rule that promoted ``scripts/instruments/d41/clocks.py``).

Two questions, deliberately separate, because the phrase "one decision, eight
rows" collapses them and they have different fixes:

  RE-DECISION      how many DeskRecommendationDecided events name the SAME
                   (run_id, rec_id) identity — one row, decided N times.
  RE-PRESENTATION  how many DISTINCT (run_id, rec_id) identities carry the
                   same subject — N rows, one decision.

REFUSES ON AN EMPTY POPULATION. An unreachable spine and a spine with no
matching events produce the same clean table otherwise, and a min/median/max
over nothing looks exactly like a min/median/max over a uniform corpus.

Usage:
    python scripts/instruments/hw3/r39_census.py --subject R39
    python scripts/instruments/hw3/r39_census.py --subject R39 --dump out.json
    python scripts/instruments/hw3/r39_census.py --null      # the domain check
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.request
from collections import Counter

DEFAULT_URL = "http://127.0.0.1:8090/api/v1/fund/events?limit=1000"


def pull(url: str) -> list[dict]:
    with urllib.request.urlopen(url, timeout=30) as r:
        body = json.loads(r.read().decode("utf-8"))
    return body["events"] if isinstance(body, dict) else body


def census(events: list[dict], subject: str) -> dict:
    hits = [e for e in events
            if subject in json.dumps(e.get("payload") or {})]
    decided = [e for e in hits if e.get("type") == "DeskRecommendationDecided"]
    ident = Counter()
    for e in decided:
        p = e.get("payload") or {}
        ident[(p.get("run_id"), p.get("rec_id"))] += 1
    worst = ident.most_common(1)[0] if ident else (None, 0)
    return {
        # THE DOMAIN, always, beside every count. A zero here without the
        # population size it was found in is not a result (builder D41).
        "events_scanned": len(events),
        "events_mentioning_subject": len(hits),
        "decision_events": len(decided),
        "distinct_identities": len(ident),
        "worst_identity": list(worst[0]) if worst[0] else None,
        "worst_identity_decisions": worst[1],
        "worst_identity_seqs": sorted(
            e.get("seq") for e in decided
            if ((e.get("payload") or {}).get("run_id"),
                (e.get("payload") or {}).get("rec_id")) == worst[0]),
        "identities": [{"run_id": k[0], "rec_id": k[1], "decisions": n}
                       for k, n in ident.most_common()],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", default="R39")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--dump")
    ap.add_argument("--null", action="store_true",
                    help="run against a subject that cannot appear; the "
                         "expected answer is 0 over a NON-zero domain")
    a = ap.parse_args()
    try:
        events = pull(a.url)
    except Exception as e:  # noqa: BLE001
        print(f"REFUSING: the event feed at {a.url} is unreadable ({e}). "
              "An unreachable spine and an empty record produce identical "
              "tables, and only one of them is a measurement.")
        return 2
    if not events:
        print("REFUSING: the feed returned zero events. Nothing was compared.")
        return 2
    subject = ("__NO_SUCH_SUBJECT_" + "ZZZQ__") if a.null else a.subject
    out = census(events, subject)
    out["subject"] = subject
    if a.null and out["events_mentioning_subject"] != 0:
        print("NULL TEST FAILED: a subject that cannot exist was found.")
        return 1
    print(json.dumps(out, indent=2))
    if a.null:
        print(f"NULL TEST PASSED: 0 hits over a domain of "
              f"{out['events_scanned']} events.")
    if a.dump:
        with io.open(a.dump, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
