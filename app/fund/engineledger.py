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

#: The bucket for a lifecycle event this fold has no word for. It exists so
#: that ``sum(counts.values()) == total`` HOLDS: without it a new order
#: EventType would land, classify as neither of the five, and disappear from
#: the strip while still being counted in the header — a signal the page shows
#: a total for and no row about. Absence discipline applied to our own
#: vocabulary: the fold says when it does not have a word, rather than
#: quietly dropping what it cannot name.
_UNCLASSIFIED = "unclassified"


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


def _num(v: Any) -> float | None:
    """A number, or ``None`` — never a substituted zero. ``float(x or 0)``
    turns an absent field into a measured value, which is the one thing this
    fund's non-negotiables forbid outright."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


#: Bumped when the FENCING RULE changes — separately from the payload shape,
#: because a stored reading whose verdict was produced under a different rule
#: about what counts as live is not comparable to a current one.
FENCE_VERSION = "v1"

#: The three liveness states of a raised signal. Not two: "we cannot tell" is
#: an answer this fund is required to be able to give.
LIVE = "live"
FENCED = "fenced"

#: The bases a liveness verdict can rest on, each one a fact read from the
#: record rather than a judgement. Published on the payload so a reader can
#: see WHY a row was or was not counted, and so a test can assert on the
#: basis rather than on the sentence.
BASIS_SESSIONS_UNREADABLE = "sessions_unreadable"
BASIS_CLAIMED_BY_LIVE_SESSION = "claimed_by_live_session"
BASIS_RAISED_AT_UNREADABLE = "raised_at_unreadable"
BASIS_KNOWN_SINCE_UNREADABLE = "sessions_known_since_unreadable"
BASIS_RAISED_DURING_THIS_PROCESS = "raised_during_this_process"
BASIS_PREDATES_SESSION_MEMORY = "predates_session_memory"

_SESSION_ALIVE = ("starting", "running")


class EngineContext:
    """Everything the fence needs to know about the world OUTSIDE the log.

    ONE OBJECT, BUILT ONCE, BECAUSE THE FIELDS DESCRIBE ONE CONDITION. The
    predecessor of this class was three separate arguments, and the endpoint
    that assembled them passed an empty session list and then patched two of
    the five fields that depend on it — shipping a payload that contradicted
    itself on the one path no test covered. A caller cannot produce half of
    this state: it hands over what it read, and every field derived from it is
    computed here.

    **Each input is THREE-VALUED and the unreadable case is its own value, not
    the empty one.** ``sessions=None`` is "the list could not be read", which
    is a different fact from ``sessions=[]`` ("nothing is running") and leads
    to the OPPOSITE fence decision.
    """

    __slots__ = ("sessions", "sessions_readable", "known_since",
                 "archived_strategy_ids", "archived_readable")

    def __init__(self,
                 sessions: list[dict[str, Any]] | None = None,
                 known_since: str | None = None,
                 archived_strategy_ids: Iterable[str] | None = None):
        self.sessions_readable = sessions is not None
        self.sessions = list(sessions or [])
        #: The instant the runner's in-memory session table began
        #: (``leanrunner.LeanRunner.sessions_known_since``). ``None`` means the
        #: runner could not be asked, and the fence then proves nothing.
        self.known_since = (known_since or "").strip() or None
        self.archived_readable = archived_strategy_ids is not None
        self.archived_strategy_ids = set(archived_strategy_ids or ())

    @property
    def live_sessions(self) -> list[dict[str, Any]]:
        return [s for s in self.sessions if s.get("state") in _SESSION_ALIVE]

    def describe(self) -> dict[str, Any]:
        """The fence's own domain — what it could and could not read."""
        return {
            "version": FENCE_VERSION,
            "sessions_readable": self.sessions_readable,
            "sessions": len(self.sessions) if self.sessions_readable else None,
            "sessions_running": (len(self.live_sessions)
                                 if self.sessions_readable else None),
            "sessions_known_since": self.known_since,
            "archived_readable": self.archived_readable,
            "archived_strategies": (len(self.archived_strategy_ids)
                                    if self.archived_readable else None),
        }


def _claiming_session(row: dict[str, Any],
                      ctx: EngineContext) -> dict[str, Any] | None:
    """The live session this signal could have come from, or ``None``.

    GENEROUS ON PURPOSE, IN THE SAFE DIRECTION. A claimed signal is never
    fenced, so every ambiguity here must resolve toward "claimed": the cost of
    a false claim is a divergence reported that a human then dismisses; the
    cost of a false REFUSAL to claim is a live divergence silently fenced,
    which is the failure this whole mechanism could otherwise introduce.

    A signal carries no session id — the record has no field for one — so the
    match is on the identities both sides DO carry: the strategy the session
    was started for, and the algorithm it is running. Either matching is
    enough. A session that declares NEITHER claims everything, because a
    session we cannot identify cannot be ruled out.

    The time test is the other half and it is physical rather than
    conventional: a LEAN container starts FLAT, so a signal raised before this
    session began moved a book that no longer exists. An unreadable timestamp
    on either side cannot establish that, and so does not.
    """
    sid = (row.get("strategy_id") or "").strip()
    algo = (row.get("algo_id") or "").strip()
    raised = (row.get("raised_at") or "").strip()
    for s in ctx.live_sessions:
        s_sid = (s.get("strategy_id") or "").strip()
        s_algo = (s.get("algorithm") or "").strip()
        if s_sid or s_algo:
            if not ((s_sid and sid and s_sid == sid)
                    or (s_algo and algo and s_algo == algo)):
                continue
        started = (s.get("started_at") or "").strip()
        # Strictly before the session began => a different, dead book. Equal
        # or after => this session's own. String comparison is correct here
        # only because both sides are ISO-8601 UTC from ``_now()``; a
        # timestamp that is not both is treated as unreadable below.
        if raised and started and _iso_lt(raised, started):
            continue
        return s
    return None


def _iso_lt(a: str, b: str) -> bool:
    """``a`` is strictly earlier than ``b``, or ``False`` if either cannot be
    parsed. An unparseable instant proves no ordering, and the caller's safe
    direction is "did not predate"."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(a) < datetime.fromisoformat(b)
    except (TypeError, ValueError):
        return False


def signal_liveness(row: dict[str, Any], ctx: EngineContext) -> dict[str, Any]:
    """Does this signal testify about a LIVE engine's book, or a dead one's?

    **WHY THIS EXISTS.** The implied-book model folds every ``external:``
    signal ever recorded into one verdict. But an engine's paper book lives
    inside its LEAN container: when the container dies the book dies with it,
    and the next session starts flat. So a signal from a session that no longer
    exists is testimony about a book nobody holds — real history, and not a
    live divergence. On this fund's record that is exactly one signal (GLD,
    2026-08-16, from a session that has not existed for ten days and a strategy
    the CEO archived), and it was printing DIVERGED on the CEO's engine page.

    **FENCING IS THE PERMISSIVE DIRECTION AND IS TREATED AS ONE.** A fenced
    signal stops counting toward the divergence verdict, so a fence is only
    ever a POSITIVE PROOF read from the record. Everything unproven stays LIVE.
    The five ways this returns LIVE are each one of those failures to prove,
    named:

      1. the session list could not be read — absence of evidence;
      2. a live session claims it — the strongest possible live evidence;
      3. the signal's own timestamp is unreadable — it cannot be placed;
      4. the runner could not say when its session memory began — there is no
         line to place it against;
      5. **it was raised DURING this runner's session memory and yet no
         session on record accounts for it.** That is not evidence of death;
         it is evidence that something raised a signal which the session list
         cannot see — an orphaned container outliving the spine restart that
         forgot it. Fencing on "no session" alone would hide precisely that.

    Only when all five fail does the signal fence, on the one thing the record
    can actually prove: it was raised before any session record could exist.
    ``archived`` never fences on its own — it enriches the reason, because a
    strategy the CEO retired is why the reader stopped caring, but an archived
    strategy whose orphan is still signalling is a fact we must not bury.
    """
    if not ctx.sessions_readable:
        return {"state": LIVE, "basis": BASIS_SESSIONS_UNREADABLE, "reason": None}

    claim = _claiming_session(row, ctx)
    if claim is not None:
        return {"state": LIVE, "basis": BASIS_CLAIMED_BY_LIVE_SESSION,
                "reason": None,
                "session_id": claim.get("session_id"),
                "session_algorithm": claim.get("algorithm")}

    raised = (row.get("raised_at") or "").strip()
    if not raised:
        return {"state": LIVE, "basis": BASIS_RAISED_AT_UNREADABLE, "reason": None}
    if not ctx.known_since:
        return {"state": LIVE, "basis": BASIS_KNOWN_SINCE_UNREADABLE, "reason": None}
    if not _iso_lt(raised, ctx.known_since):
        return {"state": LIVE, "basis": BASIS_RAISED_DURING_THIS_PROCESS,
                "reason": None}

    archived = (ctx.archived_readable
                and (row.get("strategy_id") or "") in ctx.archived_strategy_ids)
    # ENDS WITH A PERIOD BECAUSE IT IS A SENTENCE AND EVERY CONSUMER
    # CONCATENATES IT. Found by looking at the rendered page: the engine
    # page joins this reason to its own follow-up sentence, and without the
    # stop it read "...the paper book it moved, are gone The dead session had
    # asked for 0.1". A fold that emits half-sentences makes punctuation the
    # caller's problem, and the caller will get it wrong.
    reason = ("no session on this record has survived to now — it was raised "
              f"before the engine runner's session memory began ({ctx.known_since}), "
              "so the container that raised it, and the paper book it moved, "
              "are gone.")
    if archived:
        reason = ("the strategy is ARCHIVED and " + reason)
    return {"state": FENCED, "basis": BASIS_PREDATES_SESSION_MEMORY,
            "reason": reason, "strategy_archived": archived}


def _fold(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """One pass over the log; every consumer below reads this fold.

    Materialised in one place because a generator argument iterated twice is a
    silent zero, and because two folds over the same fills are how two surfaces
    start disagreeing about one book.
    """
    engine: dict[str, dict[str, Any]] = {}
    #: One ``{order_id, strategy_id, symbol}`` per ORDER_FILLED event, engine-
    #: born or not — no quantity, because the only question asked of it is
    #: "did a fill on this (strategy, symbol) come from somewhere other than
    #: the engine". A list, not a mapping: one order can fill more than once.
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
            rec["filled_qty"] = _num(payload.get("cumulative_qty"))
        elif etype == EventType.ORDER_FILLED.value:
            # A fill event missing its numbers is a fill nobody can quantify.
            # ``or 0`` turned that into "filled 0 @ 0", which reads on the page
            # as a real, measured, zero-size fill at a zero price.
            rec["filled_qty"] = _num(payload.get("filled_qty"))
            rec["avg_price"] = _num(payload.get("avg_price"))
            rec["filled_at"] = e.get("ts")
        elif etype == EventType.ORDER_FAILED.value:
            rec["failure_reason"] = payload.get("reason") or payload.get("error")

        rec["_last"] = etype
        rec["_last_at"] = e.get("ts")

    return {"engine": engine, "fills": fills, "scanned": scanned,
            "seq_first": seq_first, "seq_last": seq_last}


def _row(rec: dict[str, Any]) -> dict[str, Any]:
    status = _STATUS.get(rec["_last"], rec["_last"])
    outcome = _OUTCOME.get(status, _UNCLASSIFIED)
    row = {k: v for k, v in rec.items() if not k.startswith("_")}
    row["status"] = status
    row["outcome"] = outcome
    row["terminal"] = status in _TERMINAL
    row["last_event"] = rec["_last"]
    row["last_event_at"] = rec["_last_at"]
    return row


def signal_ledger(store: EventStore | None = None,
                  limit: int = 200,
                  events: Iterable[dict[str, Any]] | None = None,
                  context: EngineContext | None = None
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
              "failed": 0, _UNCLASSIFIED: 0}
    for r in rows:
        counts[r["outcome"] if r["outcome"] in counts else _UNCLASSIFIED] += 1
    assert sum(counts.values()) == len(rows)   # the invariant the bucket buys

    # THE FENCE IS A SECOND AXIS, NOT A SIXTH BUCKET. ``counts`` partitions by
    # FATE and carries an invariant that its buckets sum to the total; liveness
    # is orthogonal (a fenced signal still filled or was still refused), so
    # folding it in would break the invariant and, worse, make "refused" and
    # "fenced" look like alternatives to a reader.
    #
    # WITHOUT A CONTEXT THE COUNT IS ABSENT, NOT ZERO. A ledger read with no
    # way to ask what is running has not established that nothing is fenced;
    # it has not asked. ``None`` says so.
    if context is not None:
        for r in rows:
            r["liveness"] = signal_liveness(r, context)
            r["fenced"] = r["liveness"]["state"] == FENCED
        fenced = sum(1 for r in rows if r["fenced"])
        fence = context.describe()
    else:
        fenced, fence = None, None

    sources = sorted({r["source"] for r in rows if r.get("source")})
    return {
        "version": ENGINE_LEDGER_VERSION,
        "signals": rows[:limit],
        "counts": counts,
        "fenced": fenced,
        "live": None if fenced is None else len(rows) - fenced,
        "fence": fence,
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
               context: EngineContext | None = None,
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
    # An ABSENT context is not an empty one. ``EngineContext()`` built with no
    # arguments says every input was unreadable, which is exactly what a caller
    # that supplied nothing has told us — and it fences nothing, because a
    # fence needs proof and this context has none.
    ctx = context if context is not None else EngineContext()
    sessions_readable = ctx.sessions_readable
    sessions = ctx.sessions
    running = ctx.live_sessions
    if not sessions_readable:
        direct_reason = (
            "a live LEAN session publishes no holdings — and the session "
            "list itself could not be read, so whether one is running is "
            "UNKNOWN too.")
    elif running:
        direct_reason = (
            "a live LEAN session publishes no holdings — its session record "
            "carries state, container and a log tail only (leanrunner.py).")
    else:
        direct_reason = (
            "a live LEAN session publishes no holdings — its session record "
            "carries state, container and a log tail only (leanrunner.py). "
            "With no session running there is additionally nothing to ask.")
    direct = {
        "readable": False,
        "qty_basis": "UNKNOWN",
        "sessions_readable": sessions_readable,
        "sessions": len(sessions) if sessions_readable else None,
        "sessions_running": len(running) if sessions_readable else None,
        "reason": direct_reason,
        "would_need": (
            "the algorithm posting its own holdings alongside its signals, or "
            "the spine reading the session's LEAN results folder"
        ),
    }

    # --- the engine's implied book: computed, and labelled a model ---------
    # THE FENCE RUNS FIRST, AND IT RUNS PER SIGNAL, NOT PER SYMBOL. A signal's
    # liveness is a fact about the session that raised it, and one (strategy,
    # symbol) can carry signals from a dead container and a live one. Netting
    # them together would let ten-day-old history from a destroyed paper book
    # move the number a live engine is judged against.
    for r in rows:
        r["liveness"] = signal_liveness(r, ctx)
        r["fenced"] = r["liveness"]["state"] == FENCED

    #: The LIVE implied book — the only one a divergence verdict may rest on.
    implied: dict[tuple[str, str], Decimal] = {}
    #: The FENCED implied book, kept beside it. Never deleted and never merged:
    #: it is the historical fact, and it is what the page shows in the fenced
    #: row so a reader can still see what the dead engine had asked for.
    fenced_implied: dict[tuple[str, str], Decimal] = {}
    #: Keys carrying at least one LIVE signal whose quantity the record does not
    #: state. Their implied position is UNKNOWN, never the partial sum.
    unquantified: set[tuple[str, str]] = set()
    live_signals: dict[tuple[str, str], int] = {}
    fenced_signals: dict[tuple[str, str], int] = {}
    fence_reason: dict[tuple[str, str], str] = {}
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
        is_fenced = r["fenced"]
        # AN ABSENT QUANTITY IS NOT A ZERO ONE. ``qty or 0`` netted a malformed
        # signal in as "no position change" — a measured claim about a signal
        # nobody can measure, and indistinguishable from an engine that asked
        # for nothing. One unquantified signal makes the whole (strategy,
        # symbol) UNDETERMINED: a sum with an unknown term is unknown, not the
        # sum of its known terms.
        raw_qty = r.get("qty")
        side = fenced_implied if is_fenced else implied
        if raw_qty is None:
            if not is_fenced:
                unquantified.add(key)
        else:
            qty = D(str(raw_qty))
            signed = qty if r.get("side") == "buy" else -qty
            side[key] = side.get(key, Decimal("0")) + signed
        side.setdefault(key, Decimal("0"))
        if is_fenced:
            fenced_signals[key] = fenced_signals.get(key, 0) + 1
            fence_reason.setdefault(key, r["liveness"].get("reason") or "")
        else:
            live_signals[key] = live_signals.get(key, 0) + 1
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
    #: Every key either book carries. A key that exists ONLY in the fenced book
    #: still gets a row: fencing hides a signal from the VERDICT, never from
    #: the page. Dropping it would be the deletion this mechanism is one
    #: mistake away from being.
    all_keys = set(implied) | set(fenced_implied)
    for fill in folded["fills"]:
        key = (fill.get("strategy_id") or "",
               (fill.get("symbol") or "").strip().upper())
        if key in all_keys and fill["order_id"] not in engine_order_ids:
            other_fills[key] = other_fills.get(key, 0) + 1

    per_symbol = []
    for key in sorted(all_keys):
        sid, sym = key
        n_live = live_signals.get(key, 0)
        n_fenced = fenced_signals.get(key, 0)
        # A KEY WITH NO LIVE SIGNAL IS FENCED HISTORY, AND ITS LIVE IMPLIED
        # QUANTITY IS ABSENT RATHER THAN ZERO. Zero would be a measured claim
        # that a live engine holds nothing here; there is no live engine to
        # hold anything, which is a different fact and the one the reader
        # needs. Absence discipline, applied to the number this fence creates.
        fenced_row = n_live == 0
        eng_qty = (None if (fenced_row or key in unquantified)
                   else implied.get(key, Decimal("0")))
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
        drift = ((eng_qty - b_qty)
                 if (b_qty is not None and eng_qty is not None) else None)
        in_sync = (abs(drift) <= _TOL) if drift is not None else None
        # ONE FIELD, FOUR VALUES, COMPUTED HERE. ``in_sync`` alone cannot carry
        # this: its ``None`` already means "the book could not be read", and a
        # fenced row would have collapsed into that same null — two different
        # reasons printing one word, which is the absence-collapse this module
        # exists to prevent.
        sync_state = ("fenced_history" if fenced_row
                      else "diverged" if in_sync is False
                      else "in_sync" if in_sync is True
                      else "undetermined")
        per_symbol.append({
            "strategy_id": sid or None,
            "symbol": sym,
            # The book side, in the broker leg's own word.
            "book_qty": f(b_qty) if b_qty is not None else None,
            # UNKNOWN, always, until the engine can be asked.
            "engine_qty": None,
            "engine_implied_qty": f(eng_qty) if eng_qty is not None else None,
            # Named, so a null implied quantity is never read as "the engine
            # has not signalled on this symbol" — it has, and we cannot size it.
            "implied_unquantified": key in unquantified,
            "drift": f(drift) if drift is not None else None,
            # THREE-VALUED. ``None`` is "cannot tell", and it is what an
            # unreadable book gives — never ``True``, which would read as
            # agreement nobody measured. See ``sync_state`` for the four-valued
            # discriminator a renderer should switch on.
            "in_sync": in_sync,
            "sync_state": sync_state,
            "fenced": fenced_row,
            "fence_reason": fence_reason.get(key) or None if fenced_row else None,
            # What the DEAD engine had asked for, preserved beside the live
            # reading exactly as the clean-field rule requires: annotate the
            # contaminated figure, never erase it.
            "fenced_implied_qty": (f(fenced_implied[key])
                                   if key in fenced_implied else None),
            "signals_live": n_live,
            "signals_fenced": n_fenced,
            "signals": signals_by_key.get(key, {}),
            "other_fills": other_fills.get(key, 0),
        })

    out_of_sync = sum(1 for p in per_symbol if p["sync_state"] == "diverged")
    undetermined = sum(1 for p in per_symbol if p["sync_state"] == "undetermined")
    fenced_symbols = sum(1 for p in per_symbol if p["sync_state"] == "fenced_history")
    # COUNTED DIRECTLY, ALL FOUR, RATHER THAN ONE AS A REMAINDER. A partition
    # computed as "everything else" makes its own exhaustiveness test a
    # tautology that cannot fail however badly the other legs classify (HW1).
    in_sync_symbols = sum(1 for p in per_symbol if p["sync_state"] == "in_sync")
    assert (out_of_sync + undetermined + fenced_symbols + in_sync_symbols
            == len(per_symbol))
    unfilled = sum(1 for r in rows if r["outcome"] != "filled")
    signals_fenced = sum(1 for r in rows if r["fenced"])

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
                "an approved and FILLED signal moves the fund's book. A LEAN "
                "container starts FLAT, so only signals raised by a session "
                "that still exists move the book a live engine holds today"
            ),
            "per_symbol": per_symbol,
            "symbols_out_of_sync": out_of_sync,
            "symbols_undetermined": undetermined,
            "symbols_in_sync": in_sync_symbols,
            "symbols_fenced": fenced_symbols,
            "book_readable": book_readable,
            "book_unreadable_reason": book_reason,
        },
        "signals_raised": len(rows),
        "signals_not_filled": unfilled,
        "signals_fenced": signals_fenced,
        "signals_live": len(rows) - signals_fenced,
        "fence": ctx.describe(),
        "verdict": _verdict(rows, per_symbol, out_of_sync, undetermined,
                            fenced_symbols),
        "domain": {
            "events_scanned": folded["scanned"],
            "seq_first": folded["seq_first"],
            "seq_last": folded["seq_last"],
            "scan_limit": SIGNAL_SCAN_LIMIT,
            "window_bound": folded["scanned"] >= SIGNAL_SCAN_LIMIT,
        },
    }

def _verdict(rows: list[dict[str, Any]], per_symbol: list[dict[str, Any]],
             out_of_sync: int, undetermined: int,
             fenced_symbols: int = 0) -> dict[str, Any]:
    """One word and one sentence — the thing a human reads first.

    ``state`` is deliberately FIVE-valued and never collapses any of them into
    another. A fund with no engine signals at all has NOT reconciled its engine
    against its book; it has nothing to reconcile. A fund whose only signals
    came from a session that no longer exists has not reconciled either — it
    has HISTORY, and calling that "in sync" would be agreement nobody measured,
    while calling it "diverged" would raise a live alarm about a dead engine.

    THE ORDER IS THE MECHANISM. Live divergence outranks everything below it,
    so a fenced row can never suppress one: ``fenced_history`` is reachable
    only when there is no live disagreement and no live undetermined row left
    to report.
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
    # The fenced count rides on every sentence below rather than only its own,
    # because a reader who is told "1 symbol diverges" while three sit fenced
    # has been given a number without its domain.
    tail = ("" if not fenced_symbols else
            f" {_plural(fenced_symbols, 'symbol')} "
            f"{'is' if fenced_symbols == 1 else 'are'} FENCED HISTORY and "
            f"{'is' if fenced_symbols == 1 else 'are'} not counted here.")
    if undetermined and not out_of_sync:
        return {"state": "unknown",
                "sentence": f"{_plural(undetermined, 'symbol')} cannot be "
                            "compared — the fund's own per-strategy book could "
                            "not be read." + tail}
    if out_of_sync:
        parts = [f"{p['symbol']} engine {p['engine_implied_qty']} vs book "
                 f"{p['book_qty']}" for p in per_symbol
                 if p["sync_state"] == "diverged"]
        return {"state": "diverged",
                "sentence": ("The engine's signals and the fund's book "
                             f"disagree on {_plural(out_of_sync, 'symbol')}: "
                             + "; ".join(parts) + "." + tail),
                "symbols": [p["symbol"] for p in per_symbol
                            if p["sync_state"] == "diverged"]}
    live_rows = [p for p in per_symbol if not p["fenced"]]
    if fenced_symbols and not live_rows:
        return {"state": "fenced_history",
                "sentence": (
                    f"Nothing live to reconcile. Every symbol the engine has "
                    f"signalled on — {_plural(fenced_symbols, 'symbol')} — was "
                    "signalled by a session that no longer exists, so it "
                    "describes a paper book that is gone rather than a "
                    "disagreement now. The rows are kept below with their "
                    "reasons."),
                "symbols": [p["symbol"] for p in per_symbol if p["fenced"]]}
    return {"state": "in_sync",
            "sentence": f"All {_plural(len(live_rows), 'symbol')} the engine "
                        "has signalled on agree with the fund's book." + tail}


def _liveness_provable(readable: bool, running: list[Any],
                       sessions: list[Any]) -> bool | None:
    """FOUR inputs, three answers, and ``None`` carries TWO different reasons
    that are both honestly "no answer": the question does not arise (nothing
    has ever run) and the question cannot be reached (the list is unreadable).
    ``_liveness_note`` is what tells them apart — never this flag alone."""
    if not readable:
        return None       # cannot even ask
    if running:
        return False      # something runs and we cannot tell if it is alive
    if not sessions:
        return None       # the question does not arise
    return True           # a terminal state the record shows


def _liveness_note(readable: bool, running: list[Any],
                   sessions: list[Any]) -> str:
    if not readable:
        return ("Whether anything is alive cannot be answered: the session "
                "list itself could not be read.")
    if running:
        return ("A running session's health is not observable from the spine: "
                "silence is the normal state of a daily-bar algorithm, so a "
                "quiet engine and a dead one cannot be told apart from here.")
    if not sessions:
        return "Nothing has ever run, so there is no liveness question to answer."
    return ("Nothing is running; the sessions on record reached a state the "
            "record shows.")


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

    **``sessions=None`` MEANS UNREADABLE AND IS ITS OWN STATE.** It used to
    mean "treat as empty", with the caller patching ``state`` and ``note``
    afterwards — and the caller did not patch ``liveness_provable`` or
    ``liveness_note``, so the payload said "the session list could not be read"
    in one field and "nothing has ever run, so there is no liveness question to
    answer" in another. That is exactly the absence-collapsing defect this
    module exists to prevent, reproduced inside the module. The state is
    computed HERE, in one place, from one input, so no caller can produce half
    of it.
    """
    readable = sessions is not None
    sessions = list(sessions or [])
    running = [s for s in sessions if s.get("state") in ("starting", "running")]
    failed = [s for s in sessions if s.get("state") == "failed"]

    if not readable:
        state, note = "unknown", (
            "The live-session list could not be read. This is NOT the same as "
            "no session running — an engine we cannot ask about may be doing "
            "anything.")
    elif not sessions:
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
        "sessions_readable": readable,
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
        "liveness_provable": _liveness_provable(readable, running, sessions),
        "liveness_note": _liveness_note(readable, running, sessions),
    }


#: The definition key that marks a strategy as engine-run, and the reason it is
#: a key rather than a name convention: ``"LEAN - GLD 100d SMA filter"`` starts
#: with the engine's name and ``"TEST - Fast Intraday (5m SMA)"`` does not, and
#: neither fact is a contract. ``definition.engine`` is what the registrar
#: actually writes.
ENGINE_DEFINITION_KEY = "engine"


def _assets_of(row: dict[str, Any]) -> tuple[list[str], str | None]:
    """The symbols a strategy trades, and WHICH field said so.

    Three sources exist on the live record and they disagree — measured
    2026-08-26/27: the HYG probe carries ``assets: ["HYG"]`` on the row AND
    ``definition.universe: ["HYG"]``; the GLD filter carries ``assets: []`` and
    only ``definition.symbol: "GLD"``. A reader shown "no assets" for GLD would
    be shown a falsehood the record contradicts two fields away.

    The basis is returned beside the list because a symbol read out of a
    strategy's own ``assets`` field is a different quality of fact from one
    parsed out of a free-form definition, and the page says which it got.
    """
    assets = [str(a).strip().upper() for a in (row.get("assets") or [])
              if str(a).strip()]
    if assets:
        return sorted(set(assets)), "strategy.assets"
    d = row.get("definition") or {}
    uni = d.get("universe")
    if isinstance(uni, (list, tuple)):
        out = [str(a).strip().upper() for a in uni if str(a).strip()]
        if out:
            return sorted(set(out)), "definition.universe"
    sym = d.get("symbol")
    if isinstance(sym, str) and sym.strip():
        return [sym.strip().upper()], "definition.symbol"
    return [], None


def engine_strategies(strategies: list[dict[str, Any]] | None,
                      ledger: dict[str, Any] | None = None,
                      context: EngineContext | None = None,
                      algorithm_source: Any = None,
                      datasource_reader: Any = None) -> dict[str, Any]:
    """One card per engine-run strategy: what it trades, on what data, saying what.

    **THE QUESTION, VERBATIM (CEO, 2026-08-26):** *"I would like to see the
    Lean engine's strategy in allocate + in the engine page; I would like to
    see which datasource; which asset; which strategy which signals etc etc to
    get a quick sense and imo most of our early work will be algorithmic."*

    Four facts about one strategy lived in four places and no surface joined
    them: the registry knows its name, state and allocation; the strategy's
    ``definition`` knows the rule and the algorithm; the ALGORITHM FILE is the
    only thing that knows the datasource; and the event log knows what it has
    actually said. This joins them, reads nothing it cannot verify, and names
    every join it could not make.

    **``strategies=None`` MEANS THE REGISTRY COULD NOT BE READ**, which is not
    an empty bench. The payload says so and carries no cards, rather than
    rendering a fund with no algorithms.

    **THE DATASOURCE IS READ FROM THE ALGORITHM, NEVER ASSUMED.** Both live
    algorithms subscribe a custom ``SpineBars`` daily feed, and they ask that
    feed for DIFFERENT windows (700 days and 2000). A panel that hardcoded the
    shared half would have been right about the class and wrong about the
    window, in a way no test would catch because the wrong number is plausible.

    ``algorithm_source`` is ``name -> code|None`` and is allowed to fail: an
    algorithm whose file is missing gets an UNREADABLE datasource with the
    reason, never a blank that reads as "no data".
    """
    if strategies is None:
        return {"version": ENGINE_LEDGER_VERSION,
                "readable": False,
                "reason": "the strategy registry could not be read, so which "
                          "strategies are engine-run is UNKNOWN — not none",
                "strategies": [], "total": None, "archived": None,
                "engines": [], "sessions_unmatched": []}

    ctx = context if context is not None else EngineContext()
    read_ds = datasource_reader
    if read_ds is None:
        from app.fund.leanrunner import declared_datasource as read_ds
    from app.fund.leanrunner import declared_algorithm_class

    #: Newest-first already (``signal_ledger`` sorts by seq descending), so the
    #: first hit per strategy IS the last signal. Relying on that rather than
    #: re-sorting keeps one ordering rule in one place.
    signals = (ledger or {}).get("signals") or []

    cards = []
    for row in strategies:
        definition = row.get("definition") or {}
        engine = definition.get(ENGINE_DEFINITION_KEY)
        if not (isinstance(engine, str) and engine.strip()):
            continue
        sid = row.get("strategy_id")
        algorithm = definition.get("algorithm")
        algorithm = algorithm.strip() if isinstance(algorithm, str) else None

        code = None
        code_error = None
        if algorithm and algorithm_source is not None:
            try:
                code = algorithm_source(algorithm)
            except Exception as e:  # noqa: BLE001 — a missing file is not a crash
                code_error = f"{type(e).__name__}: {e}"
        datasource = read_ds(code)
        if code_error:
            datasource = {**datasource,
                          "reason": f"the algorithm file could not be read "
                                    f"({code_error}), so its feed is UNKNOWN"}
        elif algorithm is None:
            datasource = {**datasource,
                          "reason": "this strategy's definition names no "
                                    "algorithm, so there is no file to read a "
                                    "feed from"}

        assets, assets_basis = _assets_of(row)
        mine = [s for s in signals if s.get("strategy_id") == sid]
        sessions = [s for s in ctx.sessions
                    if (s.get("strategy_id") or "") == (sid or "\0")
                    or (algorithm and (s.get("algorithm") or "") == algorithm)]
        running = [s for s in sessions if s.get("state") in _SESSION_ALIVE]

        counts = {"raised": len(mine), "filled": 0, "in_flight": 0,
                  "awaiting": 0, "refused": 0, "failed": 0,
                  _UNCLASSIFIED: 0}
        for s in mine:
            counts[s["outcome"] if s["outcome"] in counts else _UNCLASSIFIED] += 1
        assert sum(v for k, v in counts.items() if k != "raised") == len(mine)

        cards.append({
            "strategy_id": sid,
            "name": row.get("name"),
            "engine": engine.strip(),
            "state": row.get("state"),
            "archived": bool(row.get("archived")),
            "allocation_pct": row.get("allocation_pct"),
            "algorithm": algorithm,
            # THE CLASS LEAN WILL ACTUALLY INSTANTIATE, read from the file —
            # ``_run_live`` passes exactly this string to
            # ``--algorithm-type-name``. ``definition.class`` is a note
            # somebody typed and is carried separately, unmerged, so that a
            # definition drifting from its file is visible instead of being
            # papered over by an ``or``.
            "class_name": declared_algorithm_class(code),
            "class_in_definition": definition.get("class"),
            "rule": definition.get("rule"),
            "purpose": definition.get("purpose"),
            "claim_type": definition.get("claim_type"),
            "signal_only": definition.get("signal_only"),
            "assets": assets,
            "assets_basis": assets_basis,
            "datasource": datasource,
            # THREE-VALUED, like everything else here: ``None`` is "the session
            # list could not be read", which is not "no session".
            "session_state": (None if not ctx.sessions_readable
                              else "running" if running
                              else "stopped" if sessions
                              else "none"),
            "sessions": sessions,
            "signals": counts,
            "signals_fenced": sum(1 for s in mine if s.get("fenced")),
            "last_signal": mine[0] if mine else None,
            # Everything else the definition declares, named rather than shown,
            # so a reader can see that this card is not the whole record.
            "definition_keys": sorted(str(k) for k in definition),
        })

    cards.sort(key=lambda c: (c["archived"], (c["name"] or "").lower()))
    matched = {s.get("session_id") for c in cards for s in c["sessions"]}
    unmatched = [s for s in ctx.sessions if s.get("session_id") not in matched]
    return {
        "version": ENGINE_LEDGER_VERSION,
        "readable": True,
        "reason": None,
        "strategies": cards,
        "total": len(cards),
        "archived": sum(1 for c in cards if c["archived"]),
        "engines": sorted({c["engine"] for c in cards}),
        # A LIVE SESSION NO CARD ACCOUNTS FOR IS THE LOUDEST THING ON THIS
        # PAYLOAD. It means something is running that the strategy registry
        # cannot explain — and it is the same evidence the fence refuses to
        # treat as death. Empty is the normal case; a non-empty list is a
        # finding, so it is a named field rather than a silent omission.
        "sessions_unmatched": unmatched,
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
