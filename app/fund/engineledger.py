"""The engine ledger — what an external engine raised, and what became of it.

Two questions this module answers, both read-only, neither of them a control:

  1. **What is the fate of every signal an engine raised?** A signal enters at
     ``POST /fund/signals/external`` and becomes an ordinary proposal in the
     approval queue. From there it is approved or declined, submitted or not,
     filled or failed — and all of that lands in the event log as ordinary
     order events with nothing marking them as engine-born except the actor
     string on the proposal. Nothing rendered that. ``signal_ledger`` does.

  2. **Does the engine's book agree with the fund's book?** It does not have to,
     and that is the point. A live LEAN session keeps its OWN paper book: when
     the algorithm places an order, LEAN's paper brokerage fills it internally
     whatever the fund decides, while the spine only moves the fund's book on an
     approved, filled order. **The first declined signal makes them diverge**,
     and from then on the engine reasons about a position the fund does not
     hold — eventually proposing an exit for stock that is not there, which the
     propose path refuses. That divergence already happened once on this fund's
     record (order ``e035957c``, GLD, declined at seq 158) and nothing noticed.

**THIS MODULE INTRODUCES NO THRESHOLD AND NOTHING ACTS ON IT.** It produces a
number and a sentence. Whether a divergence is tolerable is a human call, and
the day it becomes a control it will be a versioned change with a written
reason — not a constant that appeared in a reporting module.

**THE ENGINE'S OWN BOOK CANNOT BE READ TODAY, AND THIS SAYS SO RATHER THAN
GUESSING.** ``LeanRunner`` holds live sessions in an in-memory dict
(``leanrunner.py`` ``_live``) whose entries carry state, container name and a
log tail — no holdings, no bar clock, nothing about positions. So the direct
comparison the name promises is UNREADABLE, and it is reported ``UNKNOWN``: an
engine that cannot be read and an engine holding nothing are different facts,
and this fund has paid for confusing them before. What CAN be computed is the
book the engine's own signals IMPLY, and that is offered as a clearly-labelled
model, never as a reading.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from app.fund.events import ORDER_ANNOTATION_EVENTS, EventStore, EventType
from app.fund.money import D, f

#: Bumped when the shape of what this emits changes, so a stored reading can be
#: told apart from a live one by whoever reads it later.
ENGINE_LEDGER_VERSION = "v1"

#: The actor prefix ``POST /fund/signals/external`` stamps on its proposal
#: (``fund.py::external_signal`` → ``propose_order(actor=f"external:{source}")``).
#: This is the ONLY mark an engine-born order carries; there is no field for it.
ENGINE_ACTOR_PREFIX = "external:"

#: How far back the fold reads. The store's own folds use 100_000
#: (``projections/orders.py``, ``projections/strategy.py``); matching it means
#: this leg and the book it compares against see the same events or neither
#: does. ``domain`` publishes whether the window actually bound.
SIGNAL_SCAN_LIMIT = 100_000

#: Quantities below this are flat. Folding every fill leaves ~1e-15 residue on
#: closed symbols, so an "is it held" test on ``!= 0`` reports phantom holdings.
_TOL = Decimal("1e-9")

#: The lifecycle event → the word for it. Deliberately the same vocabulary as
#: ``OrdersProjection._STATUS`` with ONE rename: ``pending`` becomes
#: ``awaiting_approval``, because the brief this was built for names the exact
#: confusion to avoid — a signal still in the queue must not read as failed,
#: and "pending" beside "failed" in a fate column invites precisely that.
_STATUS = {
    EventType.ORDER_PROPOSED.value: "awaiting_approval",
    EventType.ORDER_APPROVED.value: "approved",
    EventType.ORDER_SUBMITTED.value: "working",
    EventType.ORDER_PARTIALLY_FILLED.value: "partial",
    EventType.ORDER_FILLED.value: "filled",
    EventType.ORDER_FAILED.value: "failed",
    EventType.ORDER_REJECTED.value: "rejected",
    EventType.ORDER_DECLINED.value: "declined",
}

#: The grouping a reader actually wants: five buckets, and the two that are
#: easiest to conflate are separated by construction. ``awaiting`` is not a
#: failure — nobody has decided yet; ``refused`` is a decision that was taken.
_OUTCOME = {
    "filled": "filled",
    "partial": "in_flight",
    "working": "in_flight",
    "approved": "in_flight",
    "awaiting_approval": "awaiting",
    "declined": "refused",
    "rejected": "refused",
    "failed": "failed",
}

#: Outcomes nobody will change without a new event.
_TERMINAL = {"filled", "declined", "rejected", "failed"}


def _plural(n: int, word: str, plural: str | None = None) -> str:
    """``1 symbol`` / ``2 symbols``. Not cosmetic: these sentences are the
    surface the CEO reads, and "1 symbol(s)" is the tell of a number that was
    formatted by a machine that did not look at it."""
    return f"{n} {word if n == 1 else (plural or word + 's')}"


def _split_rationale(rationale: str | None) -> tuple[str | None, str | None]:
    """``"[lean:gld_sma_filter] GLD crossed above its 100-day SMA"`` → the algo
    id and the engine's own words.

    The intake builds this string and there is no structured field for either
    part, so it is parsed back out — defensively. A rationale that does not
    match the shape yields ``(None, <the whole string>)``: the algo id is
    ABSENT, which is a different claim from ``"unknown"`` and a very different
    one from a guess.
    """
    text = (rationale or "").strip()
    if not text.startswith("["):
        return None, text or None
    close = text.find("]")
    if close < 0:
        return None, text
    inside = text[1:close]
    reason = text[close + 1:].strip() or None
    # ``source:algo`` — the source is already known from the actor, so only the
    # algo half is new information here.
    algo = inside.split(":", 1)[1].strip() if ":" in inside else None
    return (algo or None), reason


def _fold(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """One pass over the log; every consumer below reads this fold.

    Materialised in one place because a generator argument iterated twice is a
    silent zero, and because two folds over the same fills are how two surfaces
    start disagreeing about one book.
    """
    engine: dict[str, dict[str, Any]] = {}
    #: order_id → (strategy_id, symbol, signed filled qty) for EVERY filled
    #: order, engine-born or not. The engine leg needs to say whether a drift
    #: it is showing could have come from somewhere else.
    fills: list[dict[str, Any]] = []
    seq_first: int | None = None
    seq_last: int | None = None
    scanned = 0

    for e in events:
        scanned += 1
        seq = e.get("seq")
        if seq is not None:
            if seq_first is None:
                seq_first = seq
            seq_last = seq
        if e.get("aggregate_type") != "order":
            continue
        oid = e.get("aggregate_id")
        etype = e.get("type")
        payload = e.get("payload") or {}

        if etype == EventType.ORDER_PROPOSED.value:
            actor = (e.get("actor") or "")
            if not actor.startswith(ENGINE_ACTOR_PREFIX):
                continue          # a human/PM proposal — not this ledger's row
            algo, reason = _split_rationale(payload.get("rationale"))
            engine[oid] = {
                "order_id": oid,
                "seq": seq,
                "raised_at": e.get("ts"),
                "source": actor[len(ENGINE_ACTOR_PREFIX):] or None,
                "algo_id": algo,
                "reason": reason,
                "strategy_id": payload.get("strategy_id"),
                "symbol": payload.get("symbol"),
                "side": payload.get("side"),
                "qty": payload.get("qty"),
                "limit_price": payload.get("limit_price"),
                "venue": payload.get("venue"),
                "_last": etype,
                "_last_at": e.get("ts"),
                "reached_venue": False,
                "decided_at": None,
                "decided_by": None,
                "filled_qty": None,
                "avg_price": None,
                "filled_at": None,
                "failure_reason": None,
                "annotations": [],
            }
            continue

        if etype == EventType.ORDER_FILLED.value:
            fills.append({
                "order_id": oid,
                "strategy_id": payload.get("strategy_id"),
                "symbol": payload.get("symbol"),
            })

        rec = engine.get(oid)
        if rec is None:
            continue

        # AN ANNOTATION IS NOT A LIFECYCLE STEP — the same classification the
        # orders projection uses, read from the same frozenset rather than
        # re-listed here. Folding an ApprovalRefused into ``last`` would take a
        # signal that is still legitimately awaiting the CEO and print it as
        # refused; that mistake has already been made twice in this codebase
        # (see projections/orders.py). The annotation is still SHOWN, because a
        # refused approval attempt on an engine signal is exactly the kind of
        # thing this ledger exists to surface — it is just not the fate.
        if etype in ORDER_ANNOTATION_EVENTS:
            rec["annotations"].append({
                "type": etype,
                "at": e.get("ts"),
                "actor": e.get("actor"),
                "reason": payload.get("reason"),
            })
            continue

        if etype == EventType.ORDER_SUBMITTED.value:
            rec["reached_venue"] = True
            rec["venue"] = payload.get("venue") or rec["venue"]
        elif etype in (EventType.ORDER_APPROVED.value,
                       EventType.ORDER_DECLINED.value):
            rec["decided_at"] = e.get("ts")
            rec["decided_by"] = payload.get("approver") or e.get("actor")
        elif etype == EventType.ORDER_REJECTED.value:
            rec["decided_at"] = e.get("ts")
            rec["decided_by"] = "risk gate"
            rec["failure_reason"] = payload.get("reason")
        elif etype == EventType.ORDER_PARTIALLY_FILLED.value:
            rec["filled_qty"] = float(payload.get("cumulative_qty", 0) or 0)
        elif etype == EventType.ORDER_FILLED.value:
            rec["filled_qty"] = float(payload.get("filled_qty", 0) or 0)
            rec["avg_price"] = float(payload.get("avg_price", 0) or 0)
            rec["filled_at"] = e.get("ts")
        elif etype == EventType.ORDER_FAILED.value:
            rec["failure_reason"] = payload.get("reason") or payload.get("error")

        rec["_last"] = etype
        rec["_last_at"] = e.get("ts")

    return {"engine": engine, "fills": fills, "scanned": scanned,
            "seq_first": seq_first, "seq_last": seq_last}


def _row(rec: dict[str, Any]) -> dict[str, Any]:
    status = _STATUS.get(rec["_last"], rec["_last"])
    outcome = _OUTCOME.get(status, "unknown")
    row = {k: v for k, v in rec.items() if not k.startswith("_")}
    row["status"] = status
    row["outcome"] = outcome
    row["terminal"] = status in _TERMINAL
    row["last_event"] = rec["_last"]
    row["last_event_at"] = rec["_last_at"]
    return row


def signal_ledger(store: EventStore | None = None,
                  limit: int = 200,
                  events: Iterable[dict[str, Any]] | None = None
                  ) -> dict[str, Any]:
    """Every signal an engine raised, newest first, with what became of it.

    ``counts`` buckets by outcome and ALWAYS carries all five keys, zero
    included: a bucket that disappears when it is empty makes "no signal was
    refused" and "this reading does not report refusals" the same rendering.

    ``domain`` is what the reading covers, because a count without its domain
    is not a result. It names the scan window's edges and whether the window
    bound — an engine signal older than the window is not absent, it is
    unread, and the two must not print the same.
    """
    store = store or EventStore()
    if events is None:
        events = store.stream(since_seq=0, limit=SIGNAL_SCAN_LIMIT)
    folded = _fold(events)

    rows = [_row(r) for r in folded["engine"].values()]
    rows.sort(key=lambda r: (r.get("seq") is None, -(r.get("seq") or 0)))

    counts = {"filled": 0, "in_flight": 0, "awaiting": 0, "refused": 0,
              "failed": 0}
    for r in rows:
        if r["outcome"] in counts:
            counts[r["outcome"]] += 1

    sources = sorted({r["source"] for r in rows if r.get("source")})
    return {
        "version": ENGINE_LEDGER_VERSION,
        "signals": rows[:limit],
        "counts": counts,
        "total": len(rows),
        "returned": len(rows[:limit]),
        "sources": sources,
        "last_signal_at": rows[0]["raised_at"] if rows else None,
        "domain": {
            "events_scanned": folded["scanned"],
            "seq_first": folded["seq_first"],
            "seq_last": folded["seq_last"],
            "scan_limit": SIGNAL_SCAN_LIMIT,
            # Three-valued on purpose: True means the window bound and older
            # signals exist unread; False means the whole log was read.
            "window_bound": folded["scanned"] >= SIGNAL_SCAN_LIMIT,
        },
    }


def engine_leg(store: EventStore | None = None,
               attribution: Any = None,
               sessions: list[dict[str, Any]] | None = None,
               events: Iterable[dict[str, Any]] | None = None
               ) -> dict[str, Any]:
    """The third reconciliation leg: what the ENGINE holds vs what the BOOK folds.

    The existing leg (``Reconciler.drift``) compares BOOK against BROKER. This
    is the comparison nobody had, and it uses that leg's vocabulary on purpose
    — ``per_symbol`` rows of ``{symbol, book_qty, …, drift, in_sync}`` plus
    ``symbols_out_of_sync`` — because a second word for "in sync" is how two
    folds start disagreeing about one book.

    **TWO SUB-READINGS, and only one of them is a reading.**

    ``direct`` is what the engine says it holds. It is UNREADABLE today and
    reports so: ``LeanRunner``'s session record carries no positions, and there
    is no session running in any case. Its rows are absent, not zero.

    ``implied`` is what the engine's own signals imply it holds, and it is a
    MODEL of LEAN's live-paper behaviour, not a call into it: the algorithm's
    order is filled by LEAN's internal paper brokerage whatever the fund
    decides, so every RAISED signal moves the engine's book while only a FILLED
    one moves the fund's. Netting the raised signals is therefore the engine's
    book under that model. The model is stated rather than assumed because it
    is the thing that would be wrong if LEAN ever declined its own order.

    ``book_qty`` comes from ``StrategyAttribution`` — the same per-strategy fold
    the desk and the risk monitor read — scoped to the strategy the engine's
    signals are tagged with, because a fund-wide symbol total would mix in
    positions the engine never asked for and report them as its divergence.
    ``other_fills`` says how many fills on that (strategy, symbol) came from
    somewhere other than this engine, so a reader can see when the story is not
    only about signals.
    """
    store = store or EventStore()
    if events is None:
        events = list(store.stream(since_seq=0, limit=SIGNAL_SCAN_LIMIT))
    else:
        events = list(events)
    folded = _fold(events)
    rows = [_row(r) for r in folded["engine"].values()]

    # --- the engine's own book: unreadable, and named so -------------------
    sessions = list(sessions or [])
    running = [s for s in sessions if s.get("state") in ("starting", "running")]
    direct = {
        "readable": False,
        "qty_basis": "UNKNOWN",
        "sessions": len(sessions),
        "sessions_running": len(running),
        "reason": (
            "a live LEAN session publishes no holdings — its session record "
            "carries state, container and a log tail only (leanrunner.py). "
            "With no session running there is additionally nothing to ask."
            if not running else
            "a live LEAN session publishes no holdings — its session record "
            "carries state, container and a log tail only (leanrunner.py)."
        ),
        "would_need": (
            "the algorithm posting its own holdings alongside its signals, or "
            "the spine reading the session's LEAN results folder"
        ),
    }

    # --- the engine's implied book: computed, and labelled a model ---------
    implied: dict[tuple[str, str], Decimal] = {}
    signals_by_key: dict[tuple[str, str], dict[str, int]] = {}
    for r in rows:
        sid = r.get("strategy_id") or ""
        # STRIP BEFORE THE TRUTHINESS TEST. `"   ".upper()` is truthy, so a
        # whitespace-only symbol was becoming a per-symbol row named "   " that
        # nothing holds and nothing can hold — a phantom divergence. The intake
        # strips at propose time, but this fold reads HISTORY, and history
        # contains whatever was written then. Found by the test written to
        # close mutation survivor M16.
        sym = (r.get("symbol") or "").strip().upper()
        if not sym:
            continue
        key = (sid, sym)
        qty = D(str(r.get("qty") or 0))
        signed = qty if r.get("side") == "buy" else -qty
        implied[key] = implied.get(key, Decimal("0")) + signed
        bucket = signals_by_key.setdefault(
            key, {"raised": 0, "filled": 0, "awaiting": 0, "refused": 0,
                  "in_flight": 0, "failed": 0})
        bucket["raised"] += 1
        if r["outcome"] in bucket:
            bucket[r["outcome"]] += 1

    if attribution is None:
        from app.fund.projections.strategy import StrategyAttribution
        attribution = StrategyAttribution(store)
    try:
        book = attribution.positions_by_strategy()
        book_readable = True
        book_reason = None
    except Exception as e:  # noqa: BLE001 — an unreadable book is not an empty one
        book, book_readable, book_reason = {}, False, f"{type(e).__name__}: {e}"

    other_fills: dict[tuple[str, str], int] = {}
    engine_order_ids = set(folded["engine"])
    for fill in folded["fills"]:
        key = (fill.get("strategy_id") or "",
               (fill.get("symbol") or "").strip().upper())
        if key in implied and fill["order_id"] not in engine_order_ids:
            other_fills[key] = other_fills.get(key, 0) + 1

    per_symbol = []
    for key in sorted(implied):
        sid, sym = key
        eng_qty = implied[key]
        # ABSENCE INSIDE A COMPLETE FOLD IS ZERO; ABSENCE OF THE FOLD IS NOT.
        # StrategyAttribution folds EVERY fill, so a (strategy, symbol) with no
        # entry means the fund never filled anything there — a measured zero,
        # and the whole finding when the engine thinks it holds something. The
        # unreadable case above is the other fact and stays None. Getting these
        # two the same way round is what makes this leg worth reading: the
        # first version of this line returned None for both and printed "the
        # book could not be read" over a book it had just read.
        b_qty = (book.get(sid, {}).get(sym, Decimal("0"))
                 if book_readable else None)
        drift = (eng_qty - b_qty) if b_qty is not None else None
        per_symbol.append({
            "strategy_id": sid or None,
            "symbol": sym,
            # The book side, in the broker leg's own word.
            "book_qty": f(b_qty) if b_qty is not None else None,
            # UNKNOWN, always, until the engine can be asked.
            "engine_qty": None,
            "engine_implied_qty": f(eng_qty),
            "drift": f(drift) if drift is not None else None,
            # THREE-VALUED. ``None`` is "cannot tell", and it is what an
            # unreadable book gives — never ``True``, which would read as
            # agreement nobody measured.
            "in_sync": (abs(drift) <= _TOL) if drift is not None else None,
            "signals": signals_by_key.get(key, {}),
            "other_fills": other_fills.get(key, 0),
        })

    out_of_sync = sum(1 for p in per_symbol if p["in_sync"] is False)
    undetermined = sum(1 for p in per_symbol if p["in_sync"] is None)
    unfilled = sum(1 for r in rows if r["outcome"] != "filled")

    return {
        "version": ENGINE_LEDGER_VERSION,
        "direct": direct,
        "implied": {
            "basis": "signals",
            "is_model": True,
            "model": (
                "every signal the engine RAISED moves the engine's own paper "
                "book, because LEAN's live-paper brokerage fills the "
                "algorithm's order internally whatever the fund decides; only "
                "an approved and FILLED signal moves the fund's book"
            ),
            "per_symbol": per_symbol,
            "symbols_out_of_sync": out_of_sync,
            "symbols_undetermined": undetermined,
            "book_readable": book_readable,
            "book_unreadable_reason": book_reason,
        },
        "signals_raised": len(rows),
        "signals_not_filled": unfilled,
        "verdict": _verdict(rows, per_symbol, out_of_sync, undetermined),
        "domain": {
            "events_scanned": folded["scanned"],
            "seq_first": folded["seq_first"],
            "seq_last": folded["seq_last"],
            "scan_limit": SIGNAL_SCAN_LIMIT,
            "window_bound": folded["scanned"] >= SIGNAL_SCAN_LIMIT,
        },
    }


def _verdict(rows: list[dict[str, Any]], per_symbol: list[dict[str, Any]],
             out_of_sync: int, undetermined: int) -> dict[str, Any]:
    """One word and one sentence — the thing a human reads first.

    ``state`` is deliberately four-valued and never collapses "nothing to
    compare" into "in sync". A fund with no engine signals at all has NOT
    reconciled its engine against its book; it has nothing to reconcile, and
    saying so is the honest reading.
    """
    if not rows:
        return {"state": "no_signals",
                "sentence": "No engine has raised a signal on this record, so "
                            "there is nothing to reconcile — which is not the "
                            "same as agreement."}
    if not per_symbol:
        return {"state": "unknown",
                "sentence": f"{_plural(len(rows), 'signal')} "
                            f"{'was' if len(rows) == 1 else 'were'} raised but "
                            "none names a symbol, so no position comparison is "
                            "possible."}
    if undetermined and not out_of_sync:
        return {"state": "unknown",
                "sentence": f"{_plural(undetermined, 'symbol')} cannot be "
                            "compared — the fund's own per-strategy book could "
                            "not be read."}
    if out_of_sync:
        parts = [f"{p['symbol']} engine {p['engine_implied_qty']} vs book "
                 f"{p['book_qty']}" for p in per_symbol if p["in_sync"] is False]
        return {"state": "diverged",
                "sentence": ("The engine's signals and the fund's book "
                             f"disagree on {_plural(out_of_sync, 'symbol')}: "
                             + "; ".join(parts) + "."),
                "symbols": [p["symbol"] for p in per_symbol
                            if p["in_sync"] is False]}
    return {"state": "in_sync",
            "sentence": f"All {_plural(len(per_symbol), 'symbol')} the engine "
                        "has signalled on agree with the fund's book."}


def engine_status(sessions: list[dict[str, Any]] | None,
                  ledger: dict[str, Any] | None = None) -> dict[str, Any]:
    """Is a LEAN session running, and when did it last say anything?

    Written for one question the CEO asked and the stack could not answer:
    *what is happening on LEAN right now.* Three facts are separated because
    they are separately absent.

    **NO SESSION IS NOT AN ALARM.** ``GET /fund/lean/live`` returns
    ``{"sessions": []}`` and has returned that for the whole life of this fund,
    because a live session has never been started. Rendering that as a fault
    would train its reader to ignore the one time it is a fault.

    **SILENCE IS NOT EVIDENCE, IN EITHER DIRECTION.** On daily bars a healthy
    algorithm speaks once a day at most and may legitimately say nothing for
    weeks. So a running session's liveness is reported UNPROVABLE, with what it
    would take to prove it — never inferred from the gap since the last signal.

    **A RUNNING SESSION'S LOG TAIL IS EMPTY BY CONSTRUCTION.** ``_run_live``
    captures ``log_tail`` from the completed subprocess, so the field only fills
    once the session has ENDED. An empty tail on a running session means the
    tail has not been captured yet, not that nothing has happened, and the flag
    below says so rather than leaving a reader to conclude the engine is idle.
    """
    sessions = list(sessions if sessions is not None else [])
    running = [s for s in sessions if s.get("state") in ("starting", "running")]
    failed = [s for s in sessions if s.get("state") == "failed"]

    if not sessions:
        state, note = "no_session", (
            "No LEAN session has ever been started on this fund. This is a "
            "fact about the fund, not a fault in the engine.")
    elif running:
        state, note = "running", (
            f"{_plural(len(running), 'session')} running. Liveness cannot be "
            "proven from here: on daily bars a healthy algorithm can be silent "
            "for days, so a quiet engine and a dead one look identical.")
    elif failed:
        state, note = "failed", (
            f"{_plural(len(failed), 'session')} ended in failure — the "
            "session's own state says so, so this one IS readable.")
    else:
        state, note = "stopped", (
            "Sessions exist on this record but none is running.")

    last_signal_at = (ledger or {}).get("last_signal_at")
    return {
        "version": ENGINE_LEDGER_VERSION,
        "state": state,
        "note": note,
        "sessions": [
            {
                "session_id": s.get("session_id"),
                "algorithm": s.get("algorithm"),
                "strategy_id": s.get("strategy_id") or None,
                "state": s.get("state"),
                "started_at": s.get("started_at"),
                "stopped_at": s.get("stopped_at"),
                "signal_configured": s.get("signal_configured"),
                "error": s.get("error"),
                "log_tail": list(s.get("log_tail") or []),
                # See the docstring: the tail is captured at process exit.
                "log_tail_pending": (s.get("state") in ("starting", "running")
                                     and not s.get("log_tail")),
            }
            for s in sessions
        ],
        # Fund-wide, NOT per session: a signal carries no session id, so it
        # cannot be attributed to the session that raised it. Saying "the
        # running session last spoke at X" would be a claim the record does
        # not support.
        "last_signal_at": last_signal_at,
        "last_signal_scope": "any engine, ever — signals carry no session id",
        # Named absences, each with what would close it.
        "last_bar_seen": None,
        "last_bar_seen_note": (
            "UNKNOWN — the session record carries no bar clock. Closing this "
            "needs the algorithm to report the bar it last processed, or the "
            "spine to read the session's LEAN results folder."),
        # THREE-VALUED. ``None`` is "the question does not arise" (nothing is
        # running); ``False`` is "something is running and we cannot tell";
        # ``True`` is "the session reached a terminal state the record shows".
        "liveness_provable": (False if running else (None if not sessions else True)),
        "liveness_note": (
            "A running session's health is not observable from the spine: "
            "silence is the normal state of a daily-bar algorithm, so a quiet "
            "engine and a dead one cannot be told apart from here."
            if running else
            ("Nothing has ever run, so there is no liveness question to answer."
             if not sessions else
             "Nothing is running; the sessions on record reached a state the "
             "record shows.")),
    }


def attach_strategy_names(payload: dict[str, Any],
                          resolver: Any) -> dict[str, Any]:
    """Add ``strategy_name`` beside every ``strategy_id`` this payload carries.

    A uuid is not a name, and the page this feeds is read by a human deciding
    whether to care. ``resolver`` is called once per distinct id and is allowed
    to fail: an id whose strategy cannot be looked up gets ``None``, which the
    surface renders as the raw id — never as a blank, which would read as a
    signal belonging to nothing.

    Mutates and returns ``payload`` so it can be used inline at the endpoint.
    """
    seen: dict[str, str | None] = {}

    def name(sid: str | None) -> str | None:
        if not sid:
            return None
        if sid not in seen:
            try:
                seen[sid] = resolver(sid)
            except Exception:  # noqa: BLE001 — an unresolvable id is not an error
                seen[sid] = None
        return seen[sid]

    for row in payload.get("signals") or []:
        row["strategy_name"] = name(row.get("strategy_id"))
    for row in (payload.get("implied") or {}).get("per_symbol") or []:
        row["strategy_name"] = name(row.get("strategy_id"))
    return payload
