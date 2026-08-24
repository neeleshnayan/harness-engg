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

#: The feed's HARD CAP, not a page size we chose: `GET /fund/events`
#: declares `limit: int = Query(300, ge=1, le=1000)` and slices
#: `raw[-limit:]`, so 1000 is the most any caller can ever see and what
#: it sees is the NEWEST 1000. Named here so the census can say which
#: side of it a reading sits on instead of calling a window a domain.
FEED_CAP = 1000
DEFAULT_URL = "http://127.0.0.1:8090/api/v1/fund/events?limit={}".format(FEED_CAP)


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
    seqs = [e.get("seq") for e in events if e.get("seq") is not None]
    return {
        # THE DOMAIN, always, beside every count. A zero here without the
        # population size it was found in is not a result (builder D41).
        #
        # AND THE DOMAIN IS A **WINDOW**, NOT THE POPULATION — this distinction
        # was missing until the Gauntlet's null-test pass found it, and it is
        # the same defect as HW1's unnamed run cap one layer up. `GET
        # /fund/events` caps `limit` at 1000 and serves the NEWEST N
        # (`raw[-limit:]`), so `events_scanned: 1000` means "the newest 1000",
        # never "all of them". Measured while writing this: the returned window
        # spanned seq 543-1542, so at least 542 older events were invisible to
        # every run of this script and nothing said so.
        #
        # So the window's own edges ride the payload, and `covers_whole_log` is
        # a THREE-VALUED field: True when the window is shorter than the cap
        # (we saw everything the feed had), False when it is exactly the cap
        # (we are pinned against it and older events certainly exist if
        # min_seq > 1), and None when there are no seqs to reason from.
        "events_scanned": len(events),
        "feed_cap": FEED_CAP,
        "window_min_seq": min(seqs) if seqs else None,
        "window_max_seq": max(seqs) if seqs else None,
        "covers_whole_log": (None if not seqs else
                             len(events) < FEED_CAP or min(seqs) <= 1),
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
        print(f"NULL TEST PASSED: 0 hits over a WINDOW of "
              f"{out['events_scanned']} events "
              f"(seq {out['window_min_seq']}-{out['window_max_seq']}; "
              f"covers_whole_log={out['covers_whole_log']}).")
    if out["covers_whole_log"] is False:
        print("NOTE: this reading is PINNED AGAINST THE FEED CAP of "
              f"{FEED_CAP}. Events older than seq {out['window_min_seq']} were "
              "not compared. Every count above is a lower bound.")
    if a.dump:
        with io.open(a.dump, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
