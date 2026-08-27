"""ClarkHarness — the Krypton Fund harness service.

Standalone FastAPI app hosting the fund spine (event store, connectors,
projections, risk, command pipeline). Deliberately independent of the
KryptonPay payments stack: v0 has no wallets, no on-chain rail, and no
money-transmission surface — deposits are recorded off-platform.

See docs/architecture.md for the full design.
"""

import asyncio
import datetime as _dt
import logging
import os
import pathlib
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core.firebase import initialize_firebase

# Without this there is no handler on the root logger and no level set, so
# Python's default of WARNING applies and every _log.info() in the service is
# silently discarded. That is how "no strike — market closed", "scheduler lease
# ACQUIRED" and every settlement warning came to be written, shipped, and never
# once seen. The scheduler's decisions are the main window into what the
# deterministic worker is doing between ticks; dropping them leaves the
# operator inferring behaviour from side effects.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(levelname)s:     %(name)s | %(message)s",
)

_log = logging.getLogger("clarkharness")

_WEB_DIR = pathlib.Path(__file__).resolve().parents[1] / "web"

load_dotenv()

# THE MODE IS RESOLVED FIRST, BEFORE ANYTHING ELSE, and a process that cannot
# determine its mode does not start. This is the whole design in one statement:
# a fund that cannot say where its orders go and where its events land must
# refuse to construct an order path at all, loudly, at startup.
#
# It is deliberately NOT wrapped in a try/except. The failure this replaces —
# USE_FAKE_FIRESTORE, FUND_REAL_BROKER and the mere presence of an API key,
# three implicit switches across two files — never once produced an error; it
# produced a fund quietly doing something other than what its operator
# believed. An exception here is the improvement.
from app.fund import mode as fundmode  # noqa: E402

_mode_spec = fundmode.activate(fundmode.resolve())
_log.warning("FUND MODE: %s | orders -> %s | events -> %s | real money: %s",
             _mode_spec.mode.value, _mode_spec.venue_label,
             _mode_spec.pg_database, _mode_spec.real_money)

# Firebase must be ready before importing routers that build Firestore clients.
# In test mode there is no service account and no real project: an in-memory
# Firestore stands in for the parts of the harness that still speak Firestore
# (the paper venue's own book, the snapshot store). The fund's EVENT LOG in
# test mode is NOT in memory — it is Postgres, krypton_fund_dev, persistent
# and append-only exactly like the real one. Isolation and durability are
# orthogonal, and the flag this replaces treated them as one thing.
if _mode_spec.mode is fundmode.FundMode.TEST:
    _log.warning("TEST MODE — simulated fills at real prices. NOT the fund. "
                 "The record is persistent and separate (%s).",
                 _mode_spec.pg_database)
    from app.core.dev_firestore import install_fake
    install_fake()
    from app.core import firebase as _fb
    _fb._active.update({"project_id": "in-memory", "env": "test",
                        "service_account": "(none)", "database_id": "(memory)"})
else:
    try:
        initialize_firebase()
    except Exception as e:
        # Falling back to a local file is a reasonable thing to do while
        # developing and a catastrophic thing to do on the real book: the fund
        # would come up looking healthy, accept orders, and write fills into a
        # JSON file that no reconciliation, backup or audit trail knows about.
        # Every event written during the outage would be invisible to the
        # ledger it is supposed to live in, and the hash chain — whose whole
        # purpose is to make missing events loud — would be perfectly intact,
        # because the events were never in that chain to begin with.
        #
        # So production refuses to start. An outage that stops the fund is a
        # problem you find out about immediately; one that silently relocates
        # the ledger is a problem you find out about at the audit.
        if os.getenv("FUND_ENV", "").lower() == "production":
            _log.error("Firebase init failed (%s) and FUND_ENV=production — "
                       "refusing to start on a local ledger.", e)
            raise RuntimeError(
                f"cannot reach the production ledger ({e}). Refusing to fall "
                f"back to a local file: fills written there would be invisible "
                f"to reconciliation and to the audit trail. Fix connectivity, "
                f"or run FUND_MODE=test deliberately to work offline."
            ) from e
        _log.warning("Firebase init failed (%s) — falling back to local dev Firestore.", e)
        from app.core.dev_firestore import install_fake
        install_fake()

from app.api.v1 import fund as fund_router  # noqa: E402
from app.fund import heartbeat
from app.fund import schedule  # noqa: E402
from app.fund.demo_seed import seed_if_empty  # noqa: E402
from app.fund.lease import SchedulerLease  # noqa: E402
from app.fund.schedule import StrikeWindow  # noqa: E402


def _newest_strike():
    """The fund's newest struck-NAV payload, ``None``, or ``schedule.UNREADABLE``.

    A READER AND NOTHING ELSE. It performs the IO and classifies the ONE thing
    only the caller can know — that the read itself failed — and hands the raw
    answer to ``schedule.resume_strike_clock``, which computes every field of
    the verdict from it. Nothing here interprets the payload, so there is no
    second place for the interpretation to drift.

    NEVER RAISES, and that is not politeness. This runs inside ``_scheduler``'s
    lease-acquisition path, and an exception there is not one lost tick: a
    coroutine started with ``asyncio.create_task`` surfaces its exception only
    when awaited, at shutdown, so the whole deterministic worker would go quiet
    with nothing in the log.

    COST, MEASURED HERE rather than inherited: ``latest()`` folds the event log
    and takes **35–52 ms at 1,654 events**, with no cold/warm split worth the
    name (2026-08-27, two fresh processes, cold 51.8 and 35.4 ms against a warm
    range of 34–58 ms). A neighbouring figure of ~1.3s cold belongs to
    ``navgap.completeness``, which does far more work, and applying it here
    would have overstated this call by thirty-fold.

    It runs ONCE per lease acquisition, never per tick, and it is synchronous
    like every other call in this loop — ``run_universe_refresh`` in the same
    body blocks for up to 50 SECONDS when it is due, which is three orders of
    magnitude more.

    WHAT TO WATCH: the fold is linear in the log, so the 35–52 ms is a function
    of 1,654 events and nothing pins it there. The reason to care is that the
    host watchdog polls ``GET /fund/liveness`` on an 8-second timeout and
    restarts Docker, Postgres and the spine on a non-200 — and to that watchdog
    a slow event loop is the same event as a failed one.
    """
    try:
        return fund_router._nav.latest()
    except Exception as e:  # noqa: BLE001
        _log.warning("the last struck NAV could not be read (%s)", e)
        return schedule.UNREADABLE


def _venue_session():
    """The venue's session, or a simulated stand-in.

    A connector with no clock is a simulated venue, which has no exchange
    session and trades whenever asked — reporting it open keeps mock mode
    behaving the way it always has rather than silently freezing NAV history.
    """
    from app.fund.session import PHASE_REGULAR, MarketSession, STATE_OPEN, unknown

    probe = getattr(fund_router._connector, "session", None)
    if probe is None:
        return MarketSession(state=STATE_OPEN, phase=PHASE_REGULAR,
                             note="simulated venue — always open")
    try:
        return probe()
    except Exception as e:  # noqa: BLE001
        return unknown(str(e))


#: The running scheduler's lease, so shutdown can hand it back rather than
#: leaving the next process to wait out the TTL.
_lease: SchedulerLease | None = None


async def _scheduler():
    """Deterministic worker: settle fills often; strike NAV + reconcile on the session.

    Runs only while holding the scheduler lease. Losing it is not a failure —
    it means another process is doing this work, which is the point — so the
    loser goes quiet and keeps asking rather than exiting, and picks the work
    back up if that process dies.
    """
    settle_every = int(os.getenv("SETTLE_INTERVAL_SECONDS", "30"))
    strike_every = int(os.getenv("STRIKE_INTERVAL_SECONDS", "1800"))
    # READ ONCE, HERE, AND DEFENSIVELY. Every tick in the loop below is wrapped
    # in its own ``try`` for the same reason: an exception must cost one tick,
    # never the worker. An import at this level is NOT covered by those, and a
    # coroutine that raises inside ``asyncio.create_task`` surfaces its
    # exception only when it is awaited — at shutdown. The whole deterministic
    # worker would go quiet with nothing in the log until the process ended,
    # which is the unwired-kill-switch shape wearing an import statement.
    #
    # ``reconcile_every`` falsy DISABLES the tick, and that is a supported
    # setting (``LEAN_RECONCILE_INTERVAL=0``) as well as the failure path.
    try:
        from app.fund import leanrunner as _lr
        from app.fund import leansessions as _ls
        reconcile_every = _lr.RECONCILE_INTERVAL_SECONDS
    except Exception as e:  # noqa: BLE001
        _lr = _ls = None
        reconcile_every = 0
        _log.error("LEAN session reconciliation is UNWIRED in this process "
                   "(%s) — orphan detection now runs ONLY at start-up, and "
                   "the window between start-ups is open again", e)
    # The lease must outlive several ticks. One that expires between two ticks
    # of its own holder hands the work back and forth and produces exactly the
    # double-execution it exists to prevent.
    global _lease
    lease = _lease = SchedulerLease(ttl_seconds=max(180, settle_every * 4))
    _log.info("scheduler identity: %s", lease.owner)
    if strike_every <= 0:
        # SAID OUT LOUD RATHER THAN INFERRED. ``advance`` treats a non-positive
        # period as never due, so this configuration stops NAV being struck at
        # all — which is a legitimate thing to want and an illegitimate thing to
        # discover from a flat NAV chart three days later.
        _log.warning("STRIKE_INTERVAL_SECONDS is %s — the NAV strike tick is "
                     "DISABLED in this process and no NAV will be struck",
                     strike_every)
    since_strike = 0.0
    # START AT THE INTERVAL, NOT AT ZERO — so the first worker pass happens on
    # the first tick after the lease is held rather than five minutes later.
    # The start-up pass has already run by then; this makes the WORKER's
    # freshness reading true immediately instead of reporting a stale
    # never-ticked state for the first interval of every process.
    since_reconcile = float(reconcile_every)
    window = StrikeWindow()
    was_held = None
    # THE ACCUMULATORS COUNT MEASURED TIME, NOT TICKS. See the long note above
    # ``schedule.advance``: adding the NOMINAL sleep constant assumes the loop
    # body is free, and the fund's own strike series measured that assumption
    # costing between 1.6% and 20.0% of the strike interval, worsening as the
    # loop gained work. ``last_tick`` is taken AFTER the sleep so the delta is
    # the full loop period — sleep plus the work of the previous pass — which
    # is the quantity the interval is supposed to be measured in.
    last_tick = time.monotonic()
    while True:
        await asyncio.sleep(settle_every)
        now_mono = time.monotonic()
        elapsed = now_mono - last_tick
        last_tick = now_mono

        state = lease.acquire()
        if state.held != was_held:
            # Log only on change: at a 20s tick, saying this every time would
            # bury everything else in the log.
            _log.info("scheduler lease %s — %s",
                      "ACQUIRED" if state.held else "NOT HELD", state.reason)
            was_held = state.held
            if state.held:
                # RESUME THE STRIKE CLOCK FROM THE DURABLE RECORD, on every
                # acquisition — the first one after start-up and every handoff
                # after that, because they are the same event from the clock's
                # point of view. Without this a restart bought a full interval
                # of silence however long it had already been since the last
                # strike, and a worker that lost the lease came back believing
                # it had just struck. Both are measured causes of the fund's
                # over-budget strike gaps, not hypotheticals.
                #
                # It is SAFE against a restart loop because the record is the
                # thing being read: once a strike is written the newest event is
                # seconds old, so the next process resumes at ~0 and waits.
                resumed = schedule.resume_strike_clock(
                    _newest_strike(), strike_every,
                    _dt.datetime.now(_dt.timezone.utc))
                since_strike = resumed.seconds_served
                _log.info("strike clock: %s", resumed.note)
        if not state.held:
            continue

        # DUE-NESS IS DECIDED ONCE, HERE, and the accumulator resets the moment
        # it is due — whether or not a strike is written. That was already the
        # behaviour (the reset was the first line of the strike block) and it is
        # preserved deliberately: it is what makes a strike that fails cost one
        # interval rather than putting the loop into a retry burst against the
        # permanent record.
        #
        # THE OPEN CONSEQUENCE, stated here because nothing else states it: a
        # tick that ran and whose ``run_strike`` RAISED is indistinguishable in
        # the durable record from a tick that decided not to strike. Both leave
        # no NavStruck and both beat the heartbeat. Two of the fund's ten
        # over-budget in-session strike gaps have exactly that signature (the
        # accumulator's phase was preserved across them, so the loop was
        # running and the write produced nothing). Making that visible means
        # deciding what a failed official-NAV write should do, which is not a
        # decision this loop should take on its own.
        since_strike, strike_due = schedule.advance(
            since_strike, elapsed, strike_every)
        # Settlement stays unconditional. It is read-mostly, idempotent, and an
        # order submitted near the bell can fill after it — refusing to poll
        # while closed would leave that fill unrecorded until the next open.
        try:
            fund_router.run_settlement()
            heartbeat.beat("settlement")
        except Exception as e:  # noqa: BLE001
            _log.warning("settlement tick failed: %s", e)
        # Intraday NAV telemetry. Self-throttling and in-memory, so a fast
        # settle interval cannot flood it and it never touches the event log.
        try:
            fund_router.sample_intraday_nav()
        except Exception as e:  # noqa: BLE001
            _log.debug("intraday sample skipped: %s", e)
        # The universe screen, re-measured when it goes stale. Almost always a
        # no-op — it checks the age first and only spends the 50 seconds when
        # actually due, which it has to, because this tick runs every 30s.
        #
        # Under the lease with everything else, so one process measures rather
        # than three racing. And it writes no event: the universe is a
        # measurement of the market, not a fact about the fund.
        try:
            fund_router.run_universe_refresh()
        except Exception as e:  # noqa: BLE001
            _log.warning("universe refresh skipped: %s", e)
        # Durability. Built long before it was scheduled, which meant the fund
        # had a backup in the same sense that an unplugged smoke alarm is a
        # smoke alarm. Self-throttling like the universe tick, and it writes no
        # event: a copy must never be able to disturb what it is copying.
        try:
            fund_router.run_snapshot()
            heartbeat.beat("snapshot")
        except Exception as e:  # noqa: BLE001
            _log.warning("snapshot skipped: %s", e)
        # The kill switches. RiskMonitor.run() is the ONLY code that raises
        # alarms and trips the drawdown and daily-loss halts, and until now it
        # had ZERO callers — reachable from an endpoint nothing hit and from one
        # post-fill path swallowing its own exceptions. So the documented
        # "kill switches that will act without asking" would not have acted: a
        # position could have held for 21 days with the -10% halt never once
        # evaluated. Same class of bug as the snapshot two blocks up, which is
        # why that comment about the unplugged smoke alarm is still there.
        try:
            fund_router.run_risk_monitor_tick(actor="worker")
            heartbeat.beat("risk_monitor")
        except Exception as e:  # noqa: BLE001
            _log.warning("risk monitor tick failed: %s", e)
        # The pre-committed exits. Evaluates every committed rule against current
        # marks and, for one that fires, appends EXIT_RULE_TRIGGERED and raises a
        # closing SELL into the approval queue with the rule quoted. It never
        # closes anything: the pre-trade gate still runs and a human still clicks.
        try:
            fund_router.run_exit_check_tick(actor="worker")
            heartbeat.beat("exit_check")
        except Exception as e:  # noqa: BLE001
            _log.warning("exit check tick failed: %s", e)
        # Candidates whose runner died with a previous process. Their rows say
        # `running` and nothing will ever finish them, so they sat in the
        # scoreboard as neither judged nor failed and quietly made the survival
        # rate wrong. Marked `orphaned` — an absence, never a verdict.
        try:
            fund_router.run_factory_reconcile_tick()
        except Exception as e:  # noqa: BLE001
            _log.warning("factory reconcile tick failed: %s", e)
        # Stale proposals. Approval already refuses them; this keeps the queue
        # honest BETWEEN refusals. The one time it mattered, the stale proposal
        # was a take-profit on a position that had since fallen 8% - the guard
        # protected the trade, and this tick protects the operator from a queue
        # of buttons that can only error.
        try:
            fund_router.run_proposal_expiry_tick()
        except Exception as e:  # noqa: BLE001
            _log.warning("proposal expiry tick failed: %s", e)
        # The auto-approval envelope (CEO amendment 2026-08-20): deterministic,
        # versioned, v1 = exit-rule SELLs only, and only while the heartbeats
        # above prove the controls are alive. Runs AFTER the exit tick that
        # raises such proposals, so a fired stop can close in the same cycle.
        try:
            # The RETURN IS READ as of 2026-08-23 (PM R41). It used to be
            # discarded outright, which is how a tick that refused the fund's
            # own exit could complete "successfully" with nothing anywhere
            # saying so. The per-decline AutopolicyDeclined event is the
            # durable record; this line is the operator-visible summary of the
            # tick that produced them, and it is deliberately quiet when the
            # envelope refused nothing.
            _ap = fund_router.run_autopolicy_tick() or {}
            _skipped = _ap.get("skipped") or []
            if _skipped:
                _log.warning(
                    "autopolicy tick: %d order(s) DECLINED by the envelope and "
                    "left pending for the CEO (%d newly recorded as events): %s",
                    len(_skipped),
                    sum(1 for s in _skipped if s.get("recorded")),
                    "; ".join(
                        f"{s.get('symbol')} {s.get('order_id')} "
                        f"[{', '.join(s.get('failed_checks') or []) or 'no checks named'}]"
                        for s in _skipped))
            heartbeat.beat("auto_policy")
        except Exception as e:  # noqa: BLE001
            _log.warning("autopolicy tick failed: %s", e)
        # Engine output older than the retention window. Cheap: it lists one
        # directory and returns immediately when nothing is due. Unbounded growth
        # on disk is the same class of problem as the unbounded `running` rows
        # above — nothing was wrong with any single write, and nothing removed them.
        try:
            fund_router.run_results_prune_tick()
        except Exception as e:  # noqa: BLE001
            _log.warning("results prune tick failed: %s", e)
        # LEAN live containers, reconciled against the registry BETWEEN
        # start-ups. The start-up pass (in ``lifespan`` below) closed the
        # restart case; this closes the one that is actually normal — a session
        # whose container dies mid-run, or a container still running whose row
        # something retired. Until this existed, ``engineledger.ORPHAN_NOTE``
        # published that window as an unclosed limit on what the engine fence
        # proves, and the window was as long as the spine's uptime.
        #
        # SELF-THROTTLING, like the universe and snapshot ticks above: this
        # runs every 30 seconds and the reconciliation every five minutes, so
        # the common case is one integer comparison. It shells out to
        # ``docker ps`` when it is due, which is why it is not on every tick.
        #
        # Measured time, like the strike accumulator and for the same reason:
        # a five-minute reconcile that advances by the nominal 20s stretches by
        # whatever the loop body costs. ``advance`` also keeps the DISABLE path
        # intact — a non-positive interval is never due — and the explicit
        # ``reconcile_every and`` below is kept as well, because the setting is
        # supported and a reader should not have to open another module to see
        # that zero means off.
        since_reconcile, reconcile_due = schedule.advance(
            since_reconcile, elapsed, reconcile_every)
        if reconcile_every and reconcile_due:
            try:
                # THE GRACE IS WHAT MAKES A PERIODIC PASS SAFE. ``start_live``
                # writes its registry row before launching ``docker run``, so a
                # pass landing in that window would see a live row with no
                # container and retire a session that is starting correctly.
                # The start-up pass cannot race a start and passes no grace.
                rep = fund_router._lean().reconcile_containers(
                    trigger="worker",
                    grace_seconds=_lr.RECONCILE_GRACE_SECONDS) or {}
                # COUNTED FROM WHAT WAS PERFORMED, NOT FROM WHAT WAS PLANNED,
                # and REATTACH is excluded from "acted" deliberately. A live
                # session's row and its container agree on every single pass,
                # so a reattach is the STEADY STATE of a healthy fund — counting
                # it would put a warning in the log every five minutes for as
                # long as anything is running, which is how a log stops being
                # read. The three that remain are the three that CHANGE
                # something: a container stopped, a row retired, a contradiction
                # adopted.
                acted = sum(1 for a in (rep.get("actions") or [])
                            if a.get("done") is True
                            and a.get("action") != _ls.REATTACH)
                # QUIET WHEN IT FOUND NOTHING AND LOUD WHEN IT ACTED, the same
                # rule the autopolicy tick follows: at one pass every five
                # minutes, an unconditional line would bury everything else.
                # ``checked`` false is its own case — a pass that compared
                # nothing is not a pass that found nothing.
                if acted or rep.get("checked") is not True:
                    _log.warning("LEAN session reconciliation (worker): %s",
                                 rep.get("note"))
                else:
                    _log.info("LEAN session reconciliation (worker): %s",
                              rep.get("note"))
            except Exception as e:  # noqa: BLE001
                _log.warning("LEAN session reconciliation tick failed: %s — "
                             "any orphaned live container is still "
                             "unaccounted for", e)
        if strike_due:
            # Both of these WRITE to the permanent log — a NAV_STRUCK snapshot
            # and any RECONCILIATION_MISMATCH — and both read prices to do it.
            # Off-session those prices are the previous close, so an unguarded
            # tick writes an invented mark and reports a divergence that only
            # exists because the book was valued twice at the same stale price.
            session = _venue_session()
            decision = window.evaluate(session.is_open)
            if not decision.strike:
                # Named rather than silent: an operator looking at a NAV series
                # that stopped advancing needs to see that it was a decision.
                _log.info("no strike — %s (%s)", decision.reason, session.phase)
                # Beat anyway, with the reason. A deliberate no-strike is the job
                # WORKING; leaving it silent would make "market closed" read
                # identical to "the strike loop died", which is the exact
                # ambiguity this heartbeat exists to remove.
                heartbeat.beat("nav_strike", note=f"no strike — {decision.reason}")
                continue
            _log.info("strike/reconcile: %s (%s)", decision.reason, session.phase)
            for fn in (fund_router.run_strike, fund_router.run_reconcile):
                try:
                    fn()
                except Exception as e:  # noqa: BLE001
                    _log.warning("%s failed: %s", fn.__name__, e)
            heartbeat.beat("nav_strike", note=decision.reason)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-seed demo state if empty on server start.
    # DISABLE_DEMO_SEED=1 leaves the book empty so it can be built deliberately
    # — mock mode is more useful mirroring the real fund than showing invented
    # strategies with fabricated backtest numbers.
    if os.getenv("DISABLE_DEMO_SEED", "").lower() in ("1", "true", "yes"):
        _log.warning("DISABLE_DEMO_SEED set — starting with an empty book.")
    else:
        try:
            seed_if_empty(fund_router._store, fund_router._nav._db)
        except Exception as e:
            _log.warning("Auto-seed error (%s) — proceeding with existing state.", e)

    # RECONCILE LIVE LEAN SESSIONS AGAINST DOCKER, BEFORE ANYTHING ELSE RUNS.
    #
    # A LEAN live container is started with `docker run` from a daemon thread,
    # so it lives in the docker daemon and OUTLIVES this process. Until
    # 2026-08-27 the session table was in memory, so after a restart the fund
    # could neither see such a container nor stop it, and
    # `engineledger.ORPHAN_NOTE` published that as an unclosed limit on what the
    # engine fence proves. Sessions are rows now, and this is the other half:
    # a container the registry knows is re-attached (stoppable again), one it
    # does not know is stopped and recorded, and a row with no container is
    # marked vanished so its strategy is not locked out forever.
    #
    # NEVER FATAL. A reconciliation that cannot run must not stop the spine from
    # starting — it reports what it could not compare and the counts say so.
    try:
        report = fund_router._lean().reconcile_containers()
        _log.info("LEAN session reconciliation: %s", report.get("note"))
    except Exception as e:  # noqa: BLE001
        _log.warning("LEAN session reconciliation did not run (%s) — any "
                     "orphaned live container is still unaccounted for", e)

    task = None
    if os.getenv("ENABLE_SCHEDULER", "true").lower() != "false":
        task = asyncio.create_task(_scheduler())

    # Live fill events. OFF by default: the settlement poller is what the fund
    # has always run on, and this only removes the delay — it is not load-bearing
    # until it has proved itself against a real session. Turning it on adds a
    # second, faster observer; every path it takes is idempotent, so the poller
    # keeps running underneath as the backstop.
    stream_task = None
    if os.getenv("ENABLE_TRADE_STREAM", "false").lower() in ("1", "true", "yes"):
        stream_task = fund_router.start_trade_stream()

    yield

    for t in (stream_task, task):
        if not t:
            continue
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
    fund_router.stop_trade_stream()

    # Hand the lease back rather than leaving the next process to wait out the
    # TTL. On a redeploy that is the difference between the new container
    # working immediately and the fund having no scheduler for three minutes.
    if _lease is not None:
        try:
            _lease.release()
            _log.info("scheduler lease released")
        except Exception as e:  # noqa: BLE001
            _log.warning("could not release the scheduler lease (%s) — "
                         "it will expire on its own", e)


app = FastAPI(
    title="ClarkHarness — Krypton Fund",
    description="Agentic operator + LP interface for the Krypton Fund: "
    "event-sourced command spine, unit ledger, NAV, risk, and audit.",
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "fund",
            "description": "Fund spine: propose/approve orders, NAV, positions, and the audit event log.",
        }
    ],
)

# localhost and 127.0.0.1 are the same machine and a different ORIGIN, and the
# browser does not care that they resolve identically. Allowing only one means
# the cockpit works or silently fails depending on which the operator typed —
# every panel reporting "spine unreachable" while curl against the same port
# answers instantly. Both are listed so that choice stops mattering.
_DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://.*\.kryptonfund\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def _database_error_handler(request: Request, exc: Exception):
    """Say what actually went wrong.

    A bare 500 sent the UI to "is ClarkHarness running?" — which sends the
    operator to check a service that is running and a config that is correct,
    while the real cause (the datastore refusing reads) goes unnamed. These are
    infrastructure faults, not bugs in the request, so they answer 503 with a
    cause the interface can show verbatim.
    """
    from fastapi.responses import JSONResponse

    name = type(exc).__name__
    if name in ("ResourceExhausted", "PermissionDenied", "ServiceUnavailable",
                "DeadlineExceeded", "Unauthenticated"):
        cause = {
            "ResourceExhausted": "The fund database is over its read/write quota. "
                                 "Free-tier quota resets daily; upgrading the plan lifts it.",
            "PermissionDenied": "The fund database refused access — check the service "
                                "account's permissions and that Firestore is enabled.",
            "Unauthenticated": "The fund database rejected our credentials.",
            "ServiceUnavailable": "The fund database is unreachable.",
            "DeadlineExceeded": "The fund database did not respond in time.",
        }[name]
        _log.error("datastore fault (%s): %s", name, exc)
        return JSONResponse(
            status_code=503,
            content={"detail": cause, "cause": name, "retryable": True},
        )
    _log.exception("unhandled error")
    return JSONResponse(status_code=500, content={"detail": f"{name}: {exc}"})


app.include_router(fund_router.router, prefix="/api/v1", tags=["fund"])


@app.get("/health")
def health():
    return {"status": "healthy", "service": "clarkharness", "version": "0.1.0"}


@app.get("/lp", include_in_schema=False)
def lp_view():
    """Serve the LP-facing managed-fund view (reads /api/v1/fund/* client-side)."""
    return FileResponse(_WEB_DIR / "lp.html")


@app.get("/ops", include_in_schema=False)
def ops_view():
    """Serve the operator cockpit (reads /api/v1/fund/* client-side)."""
    return FileResponse(_WEB_DIR / "ops.html")


@app.get("/strategies", include_in_schema=False)
def strategies_view():
    """Serve the strategies workbench (reads /api/v1/fund/strategies/* client-side)."""
    return FileResponse(_WEB_DIR / "strategies.html")
