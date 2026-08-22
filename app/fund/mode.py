"""Fund mode — the ONE explicit switch, over TWO dimensions.

A mode is *(where orders go)* x *(where events land)*. Those are two decisions
and this module keeps them two, because conflating them is the original sin
this file exists to end: on 2026-08-21 a DURABILITY fix (moving the ledger to
Postgres) silently re-routed ORDER EXECUTION to a real Alpaca account, because
both decisions hung off one flag named for the ledger.

Before this module the fund had THREE accidental switches and no deliberate
one:

  * ``USE_FAKE_FIRESTORE``  — named for the ledger, also selected the venue;
  * ``FUND_REAL_BROKER``    — named for the venue, gated on a key being present;
  * the mere PRESENCE of ``ALPACA_API_KEY`` — a config value acting as a mode.

Two of the three reached a simulator SILENTLY (``app/api/v1/fund.py:151-163``
at 4e2d3a1: the final ``else`` handed back a ``PaperConnector`` whenever the
key was absent, typo-d, or dropped by a restart that did not carry the
environment). A fund that cannot reach its broker must know it cannot reach
its broker.

THE THREE MODES (CEO, 2026-08-21, verbatim: "lets have 1. test 2. alpaca-paper
3. alpaca-prod [this is for actual trading with real $$$]"):

    ==============  =========================  =========================
    mode            orders go to               events land in
    ==============  =========================  =========================
    test            simulated fills, REAL      krypton_fund_test
                    prices (live_pricer)
    alpaca-paper    the Alpaca paper account   krypton_fund
    alpaca-prod     the Alpaca LIVE account    krypton_fund_prod
    ==============  =========================  =========================

All three are in the enum from the first commit, and only two are wired.
A two-mode design encodes assumptions that break when the third arrives.

**ISOLATED, NOT EPHEMERAL.** ``test`` writes to a persistent Postgres
database, same schema, same append-only discipline, same fold code, same
durability monitoring. ``USE_FAKE_FIRESTORE`` was not wrong to isolate; it was
wrong to isolate by making the record DISPOSABLE — 552 events (seq 161-712)
lived in memory while the status endpoint reported successful mirroring hourly.
Isolation and durability are orthogonal and the old flag treated them as one.
The whole value of replaying 2020-03 twice is the comparison, and a comparison
needs both runs to still exist.

**THREE MODES, THREE STORES, NEVER JOINED.** Paper NAV and real NAV must never
be foldable together: *"which of these dollars are real"* is not a question
that should be answered by a tag on a row. The live log already carries 73
venue-labelled events in ONE store — 42 ``paper``, 31 ``alpaca`` (measured
against ``krypton_fund`` 2026-08-22) — distinguished only by a self-declared
string we have PROVEN can lie (see ``VENUE_FORGERY_RECEIPT`` below).

**UNSET MUST FAIL.** No default, no fallback, in either dimension. This is not
defensiveness; it is the specific lesson of ``events.store_backend()``, which
defaulted to ``"firestore"`` and relocated the whole fund's ledger on a restart
that did not carry a shell variable. A default that relocates the ledger is a
trapdoor, and a default that picks a venue is worse.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

#: The live proof that a venue label can lie, and the reason mode and venue are
#: stamped by the spine rather than declared by the proposer.
#:
#: Order ``17d64dcd-0f39-4ce1-9632-ff27f0907964`` — DBA, 5.314306 shares at
#: $28.38, the CEO-authorised experimental deployment of 2026-08-21, whose
#: entire learning goal was to produce the fund's first informative
#: execution-cost observations. Read out of ``krypton_fund`` on 2026-08-22:
#:
#:     seq 588  OrderProposed   payload.venue = "alpaca"   <- the PROPOSER said
#:     seq 593  OrderSubmitted  payload.venue = "paper"    <- the CONNECTOR did
#:     seq 594  OrderFilled     payload.venue = "alpaca"   <- the FILL believed
#:                                                            the proposer
#:
#: The fill executed on the PaperConnector and was stamped ``alpaca``, so TCA
#: counted it among its 10 "informative" orders when it carries exactly zero
#: cost information — the paper venue fills at its own quote, so its execution
#: cost is identically 0.00bps by construction. The experiment produced nothing
#: and said it had. ``pipeline._emit_fill`` wrote ``order.venue``; the submit
#: leg wrote ``ref.venue``, which is the connector's own answer. One of those
#: two is a fact and the other is a wish.
VENUE_FORGERY_RECEIPT = "17d64dcd-0f39-4ce1-9632-ff27f0907964"


class ModeError(RuntimeError):
    """Base: the fund cannot determine or honour its own mode."""


class ModeUnset(ModeError):
    """No mode was declared. There is no default and there must not be one."""


class ModeUnknown(ModeError):
    """A mode was declared and it is not one of the three."""


class ModeConflict(ModeError):
    """Two authorities declared different modes. Refuse rather than pick."""


class ProdLocked(ModeError):
    """``alpaca-prod`` was selected and is structurally unreachable."""


class VenueNotPermitted(ModeError):
    """A connector was offered to a mode that may not execute on it."""


class StoreCrossing(ModeError):
    """A second, DIFFERENT mode was activated in one process."""


class VenueKind(str, Enum):
    """WHERE ORDERS GO. Deliberately separate from where events land."""

    SIMULATED = "simulated"          # PaperConnector, real prices, fake fills
    ALPACA_PAPER = "alpaca_paper"    # the real broker, its paper account
    ALPACA_LIVE = "alpaca_live"      # the real broker, real money


class FundMode(str, Enum):
    TEST = "test"
    ALPACA_PAPER = "alpaca-paper"
    ALPACA_PROD = "alpaca-prod"


@dataclass(frozen=True)
class ModeSpec:
    """One mode, both dimensions, and everything derived from it.

    Frozen because a mode that can be mutated after activation is a mode that
    can be mutated by the thing it constrains.
    """

    mode: FundMode

    # --- dimension 1: where orders go --------------------------------------
    venue_kind: VenueKind
    #: The label stamped on fills and submits. The ONLY value this mode may
    #: write, and the reason a mock venue is INCAPABLE of emitting an
    #: alpaca-labelled fill rather than merely discouraged from it.
    venue_label: str
    #: Connector ``name`` values this mode will accept at wiring time.
    #: Anything else raises rather than being tolerated.
    permitted_connectors: tuple[str, ...]
    #: True only where a fill can move the CEO's actual money.
    real_money: bool
    #: True where the venue is a real broker account (paper or live). Alpaca
    #: paper fills carry cost information; simulated fills never can.
    real_broker: bool

    # --- dimension 2: where events land ------------------------------------
    #: The Postgres database this mode's event log lives in. Three modes,
    #: three databases, never joined.
    pg_database: str

    # --- presentation -------------------------------------------------------
    label: str
    caution: str
    wired: bool

    @property
    def value(self) -> str:
        return self.mode.value

    def permits_connector(self, connector: Any) -> bool:
        return str(getattr(connector, "name", "")) in self.permitted_connectors

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "label": self.label,
            "caution": self.caution,
            "wired": self.wired,
            "venue": {
                "kind": self.venue_kind.value,
                "label": self.venue_label,
                "permitted_connectors": list(self.permitted_connectors),
                "real_broker": self.real_broker,
                "real_money": self.real_money,
            },
            "store": {"pg_database": self.pg_database},
        }


#: All three, defined once. ``alpaca-prod`` is here so that every consumer is
#: written against a three-member enum from day one; ``wired=False`` says
#: plainly that nothing has ever run on it.
MODES: dict[FundMode, ModeSpec] = {
    FundMode.TEST: ModeSpec(
        mode=FundMode.TEST,
        venue_kind=VenueKind.SIMULATED,
        venue_label="paper",
        permitted_connectors=("paper",),
        real_money=False,
        real_broker=False,
        pg_database="krypton_fund_test",
        label="TEST — simulated fills at real prices",
        caution="Nothing here is the fund. Fills are simulated; the prices they "
                "fill at are real. The record is persistent and separate.",
        wired=True,
    ),
    FundMode.ALPACA_PAPER: ModeSpec(
        mode=FundMode.ALPACA_PAPER,
        venue_kind=VenueKind.ALPACA_PAPER,
        venue_label="alpaca",
        permitted_connectors=("alpaca",),
        real_money=False,
        real_broker=True,
        pg_database="krypton_fund",
        label="ALPACA PAPER — the fund's live book",
        caution="Real broker, paper money. This is the fund's operating book: "
                "NAV, the unit ledger and every control run against it.",
        wired=True,
    ),
    FundMode.ALPACA_PROD: ModeSpec(
        mode=FundMode.ALPACA_PROD,
        venue_kind=VenueKind.ALPACA_LIVE,
        # A DISTINCT label even though the connector is the same class. Two
        # stores already keep the histories apart; this keeps them apart in a
        # row someone copies between them by hand.
        venue_label="alpaca-live",
        permitted_connectors=("alpaca",),
        real_money=True,
        real_broker=True,
        pg_database="krypton_fund_prod",
        label="ALPACA PROD — REAL MONEY",
        caution="Real broker, real money. Structurally unreachable until every "
                "precondition below is MET, not argued.",
        wired=False,
    ),
}


# --- the alpaca-prod gate ----------------------------------------------------
# Two independent locks, and BOTH must open. A precondition list on its own is
# prose; a code constant on its own is a number someone flips in a hurry.
#
# This constant is the first lock. Changing it is a versioned change with a
# written reason and a human's name on it, exactly like a threshold — because
# that is what it is.
PROD_UNLOCKED = False

#: What the CEO agreed must be true before real money moves (desk request
#: 0999b6a9, 2026-08-21). Each carries an evaluator or says plainly that it
#: has none.
#:
#: THE STATUS VOCABULARY MATTERS, and it is the register's own hard-won lesson:
#: a precondition with no evaluator renders ``unchecked``, NEVER ``met`` and
#: never a silent ``unmet``. 17 of the fund's 19 registered decisions carry a
#: review trigger no code evaluates while the endpoint reported
#: ``triggers_unchecked: []`` — absence rendered as zero, at the level of the
#: decision register itself. An unchecked precondition BLOCKS here, so the
#: honest answer and the safe answer are the same answer.
@dataclass(frozen=True)
class Precondition:
    key: str
    text: str
    #: ``callable(store) -> tuple[bool, str]`` or None when nothing can
    #: evaluate it yet. None is reported, never treated as satisfied.
    evaluator: Optional[Callable[[Any], tuple[bool, str]]] = None
    #: Why there is no evaluator, when there is none.
    unevaluable_reason: Optional[str] = None

    def evaluate(self, store: Any) -> dict[str, Any]:
        if self.evaluator is None:
            return {"key": self.key, "text": self.text, "status": "unchecked",
                    "detail": self.unevaluable_reason or
                              "no evaluator exists for this precondition"}
        if store is None:
            return {"key": self.key, "text": self.text, "status": "unchecked",
                    "detail": "no event store was supplied to evaluate against"}
        try:
            ok, detail = self.evaluator(store)
        except Exception as e:  # noqa: BLE001 — an unreadable log is UNCHECKED
            # Unreadable is not unchanged and it is certainly not satisfied.
            return {"key": self.key, "text": self.text, "status": "unchecked",
                    "detail": f"could not evaluate ({type(e).__name__}: {e})"}
        return {"key": self.key, "text": self.text,
                "status": "met" if ok else "unmet", "detail": detail}


def _controls_have_fired(store: Any) -> tuple[bool, str]:
    """Precondition 1: every control has FIRED at least once and been seen.

    Fired, not registered. A kill switch with zero callers is the pattern this
    firm names most often, and 'the code exists' has never been evidence that
    it runs.
    """
    from app.fund.events import EventType

    want = {
        "risk alarm raised": EventType.RISK_ALARM_RAISED.value,
        "trading halted": EventType.TRADING_HALTED.value,
        "an approval refused": EventType.APPROVAL_REFUSED.value,
        "an exit rule triggered": EventType.EXIT_RULE_TRIGGERED.value,
    }
    seen: set[str] = set()
    seq = 0
    while True:
        batch = store.stream(since_seq=seq, limit=1000)
        if not batch:
            break
        for ev in batch:
            seq = max(seq, ev.get("seq") or seq)
            seen.add(str(ev.get("type")))
        if len(batch) < 1000:
            break
    missing = sorted(n for n, t in want.items() if t not in seen)
    if missing:
        return False, "never observed in this store: " + ", ".join(missing)
    return True, "all four observed in this store's own log"


#: How many fills that can actually measure execution cost the model needs
#: before a backtest's cost assumption stops being an assumption.
#:
#: IMPORTED, not copied. This is not a new threshold — it is the fund's
#: existing sample bar (``costassumption.RELIABLE_SAMPLE``, the number TCA's
#: own verdict already says "20 is the bar" against), reused so that the prod
#: precondition and the cost model cannot come to disagree about what a
#: trustworthy sample is. Two copies of one belief is exactly how
#: ASSUMED_COST_BPS_PER_SIDE and the backtester's CostModel drifted apart, and
#: the comment recording that is four files away in tca.py.
from app.fund.costassumption import RELIABLE_SAMPLE as PROD_MIN_INFORMATIVE_FILLS


def _informative_fills(store: Any) -> tuple[bool, str]:
    """Precondition 5: N real informative fills exist in the cost model.

    Counted through ``tca``, which is where the executed-venue rule lives, so
    a paper fill wearing an ``alpaca`` label cannot pad this number — which is
    the exact way this precondition would otherwise have been satisfied by the
    receipt above.
    """
    from app.fund.tca import TransactionCosts

    rows = TransactionCosts(store).costs()
    n = len([r for r in rows if r.informative and r.execution_bps is not None])
    ok = n >= PROD_MIN_INFORMATIVE_FILLS
    return ok, (f"{n} informative fills with a measurable execution leg, "
                f"against {PROD_MIN_INFORMATIVE_FILLS} required")


PROD_PRECONDITIONS: tuple[Precondition, ...] = (
    Precondition(
        key="controls_fired",
        text="Every control has FIRED at least once in alpaca-paper and been "
             "observed doing it — the envelope declining, the drawdown halt "
             "halting, the drift alarm alarming.",
        evaluator=_controls_have_fired,
    ),
    Precondition(
        key="book_venue_reconciled",
        text="Book and venue reconcile clean, or the divergence is explained "
             "and fenced.",
        unevaluable_reason=(
            "requires a live broker round trip and a human's judgement on "
            "whether an explained divergence is acceptable; there is no "
            "reading of the log alone that settles it"),
    ),
    Precondition(
        key="exit_sign_fixed",
        text="The sign-inverted exit trigger is fixed (desk 34338ef6). "
             "Non-negotiable before anything can be short.",
        unevaluable_reason=(
            "a property of the code, not of the log — verified by the test "
            "that fails if the inversion returns, not by an event"),
    ),
    Precondition(
        key="kill_switch_wired_and_tested",
        text="A kill switch that is WIRED AND TESTED, not registered.",
        unevaluable_reason=(
            "'wired' is a property of the scheduler's call graph and 'tested' "
            "of the suite; neither leaves an event behind"),
    ),
    Precondition(
        key="informative_fills",
        text=f"At least {PROD_MIN_INFORMATIVE_FILLS} real informative fills "
             "exist in the cost model, so a backtest's cost assumption has "
             "been validated against a real fill.",
        evaluator=_informative_fills,
    ),
)


def prod_gate_report(store: Any = None) -> dict[str, Any]:
    """Why ``alpaca-prod`` is unreachable, in full, for a human to read."""
    checks = [p.evaluate(store) for p in PROD_PRECONDITIONS]
    unmet = [c for c in checks if c["status"] != "met"]
    return {
        "mode": FundMode.ALPACA_PROD.value,
        "code_lock": {
            "constant": "app.fund.mode.PROD_UNLOCKED",
            "value": PROD_UNLOCKED,
            "open": bool(PROD_UNLOCKED),
        },
        "preconditions": checks,
        "n_preconditions": len(checks),
        "n_met": len(checks) - len(unmet),
        "n_blocking": len(unmet),
        # BOTH locks. Reported as one boolean because the caller's question is
        # "can real money move", and the answer is no if either lock holds.
        "reachable": bool(PROD_UNLOCKED) and not unmet,
    }


# --- resolution --------------------------------------------------------------
#: The durable record of the operator's choice. A live toggle that a restart
#: silently reverts is the same trapdoor as a defaulting ledger flag, so the
#: switch writes here and startup reads here.
MODE_FILE_ENV = "FUND_MODE_FILE"
DEFAULT_MODE_FILE = ".fund_mode"


def mode_file_path(env: Optional[dict] = None) -> str:
    env = os.environ if env is None else env
    return env.get(MODE_FILE_ENV) or DEFAULT_MODE_FILE


def read_mode_file(env: Optional[dict] = None) -> Optional[dict[str, Any]]:
    """The persisted choice, or None. An unreadable file is NOT 'no file'."""
    path = mode_file_path(env)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or not data.get("mode"):
        raise ModeUnknown(
            f"{path} exists but declares no mode — refusing to guess. Either "
            f"write a valid mode into it or delete it.")
    return data


def write_mode_file(mode: FundMode, actor: str, reason: str,
                    env: Optional[dict] = None) -> dict[str, Any]:
    """Persist the choice, with who and why. Returns what was written."""
    payload = {
        "mode": mode.value,
        "set_by": actor,
        "set_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
    }
    path = mode_file_path(env)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    os.replace(tmp, path)
    return payload


def parse_mode(raw: str) -> FundMode:
    text = (raw or "").strip().lower()
    if not text:
        raise ModeUnset("no mode given")
    try:
        return FundMode(text)
    except ValueError:
        raise ModeUnknown(
            f"unknown fund mode {raw!r} — it must be one of "
            f"{[m.value for m in FundMode]}. There is no default: a fund that "
            f"cannot determine its own mode must refuse to construct an order "
            f"path at all."
        ) from None


def resolve(env: Optional[dict] = None, *, allow_prod: bool = False) -> ModeSpec:
    """The declared mode, or an exception. Never a guess.

    Two authorities, and they must AGREE:

      * ``FUND_MODE`` in the environment — how a process is launched;
      * the mode file — what the last deliberate switch chose.

    Either alone is sufficient. Both present and disagreeing raises, rather
    than one silently winning: a precedence rule is exactly how the durability
    fix moved the venue, and the operator who set the loser is entitled to
    know their instruction was discarded. Neither present raises.
    """
    env = os.environ if env is None else env

    from_env = (env.get("FUND_MODE") or "").strip().lower()
    record = read_mode_file(env)
    from_file = (str(record.get("mode")) if record else "").strip().lower()

    if from_env and from_file and from_env != from_file:
        raise ModeConflict(
            f"FUND_MODE={from_env!r} in the environment disagrees with "
            f"{mode_file_path(env)} which says {from_file!r}. Refusing to "
            f"pick a winner: one of these is somebody's instruction being "
            f"silently discarded. Make them agree."
        )

    chosen = from_env or from_file
    if not chosen:
        raise ModeUnset(
            "no fund mode declared. Set FUND_MODE to one of "
            f"{[m.value for m in FundMode]}, or write "
            f"{mode_file_path(env)} through the mode switch. There is NO "
            "default and there must not be one: the last default in this "
            "position (FUND_STORE -> 'firestore') relocated the entire "
            "ledger on a restart that did not carry a shell variable."
        )

    mode = parse_mode(chosen)
    spec = MODES[mode]

    if mode is FundMode.ALPACA_PROD and not allow_prod:
        report = prod_gate_report()
        raise ProdLocked(
            "alpaca-prod is structurally unreachable. "
            f"PROD_UNLOCKED={PROD_UNLOCKED} (app/fund/mode.py), and "
            f"{report['n_blocking']} of {report['n_preconditions']} "
            "CEO-agreed preconditions are not met: "
            + "; ".join(f"{c['key']}={c['status']}"
                        for c in report["preconditions"]
                        if c["status"] != "met")
        )
    return spec


# --- process activation ------------------------------------------------------
#: The mode this process is running. Set once by the spine's wiring; read by
#: the pipeline when it stamps a fill.
_ACTIVE: Optional[ModeSpec] = None


def activate(spec: ModeSpec, *, force: bool = False) -> ModeSpec:
    """Declare the process's mode. A SECOND, DIFFERENT mode is refused.

    This is the "never joined or unioned" rule made structural rather than
    remembered. One process folds one store. Switching modes for real goes
    through the switch path, which passes ``force=True`` only after it has
    established that nothing is in flight.
    """
    global _ACTIVE
    if _ACTIVE is not None and _ACTIVE.mode is not spec.mode and not force:
        raise StoreCrossing(
            f"this process is already running {_ACTIVE.mode.value!r} against "
            f"{_ACTIVE.pg_database!r}; activating {spec.mode.value!r} against "
            f"{spec.pg_database!r} would put two ledgers in one process. Paper "
            f"NAV and real NAV must never be foldable together."
        )
    _ACTIVE = spec
    return spec


def current() -> Optional[ModeSpec]:
    """The active mode, or None if this process never declared one.

    None is returned rather than raised, and rather than defaulted to
    anything. A unit test that builds a pipeline by hand has genuinely not
    declared a mode, and the honest answer to "which mode is this" is that
    there isn't one — an ABSENCE, which callers then report as absent instead
    of stamping a mode nobody chose.
    """
    return _ACTIVE


def current_label() -> Optional[str]:
    spec = current()
    return spec.mode.value if spec else None


def deactivate() -> None:
    """Clear the process mode. Tests and the switch path only."""
    global _ACTIVE
    _ACTIVE = None


# --- derived configuration ---------------------------------------------------
def pg_dsn_for(spec: ModeSpec, base_dsn: str) -> str:
    """The base DSN pointed at this mode's database.

    One credential, three databases. The database name is the LAST path
    segment of a libpq URI; everything before it (user, password, host, port)
    and everything after it (query parameters) is carried through untouched,
    so a change of host or an added ``sslmode`` needs no change here.
    """
    head, sep, tail = base_dsn.partition("?")
    if "/" not in head:
        raise ModeError(
            f"cannot place a database name into {base_dsn!r}: it has no path "
            f"component. Expected postgresql://user:pass@host:port/dbname")
    prefix = head.rsplit("/", 1)[0]
    return f"{prefix}/{spec.pg_database}{sep}{tail}"


def assert_connector_permitted(spec: ModeSpec, connector: Any) -> None:
    """A mock venue must be INCAPABLE of wearing another venue's name.

    Checked at wiring time, against the connector's own ``name``, before a
    single order can be constructed. Not discouraged — refused.
    """
    name = getattr(connector, "name", None)
    if name is None:
        raise VenueNotPermitted(
            f"the connector offered to mode {spec.mode.value!r} declares no "
            f"name, so its venue cannot be established. A venue that cannot "
            f"identify itself does not execute this fund's orders.")
    if str(name) not in spec.permitted_connectors:
        raise VenueNotPermitted(
            f"mode {spec.mode.value!r} permits connectors "
            f"{list(spec.permitted_connectors)} and was handed {str(name)!r}. "
            f"This is the check that makes a mock venue INCAPABLE of emitting "
            f"a fill labelled for a real broker, rather than merely unlikely "
            f"to (see VENUE_FORGERY_RECEIPT)."
        )


def report(store: Any = None, env: Optional[dict] = None) -> dict[str, Any]:
    """Everything a human or a UI needs to know about the fund's mode."""
    active = current()
    record = None
    file_error = None
    try:
        record = read_mode_file(env)
    except Exception as e:  # noqa: BLE001 — an unreadable file is NOT absence
        file_error = f"{type(e).__name__}: {e}"

    return {
        "active": active.to_dict() if active else None,
        # Absent is absent. A UI that reads a null here must say "the spine
        # has not declared a mode", never render a default.
        "declared": {
            "env": (os.environ if env is None else env).get("FUND_MODE") or None,
            "file": record,
            "file_path": mode_file_path(env),
            "file_error": file_error,
        },
        "modes": [MODES[m].to_dict() for m in FundMode],
        "prod_gate": prod_gate_report(store),
        "receipt": {
            "order_id": VENUE_FORGERY_RECEIPT,
            "note": "the fill that wore an alpaca label off the paper "
                    "connector — why mode and venue are stamped by the spine",
        },
    }
