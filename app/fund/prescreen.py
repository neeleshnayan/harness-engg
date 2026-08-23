"""Kill 95% of a population before a container starts, and never approve anything.

The unlock for population search. The binding constraint was never the design — it
was one LEAN container on 15.2 GB at ~20 engine runs per candidate, which puts a
50-organism population across 20 generations at roughly 230 hours. This module
evaluates the same idea vectorised on the same bars in about a millisecond, so a
population of a thousand costs a second instead of a fortnight.

The precedent is `scripts/gate_power_audit.py`, which drove the REAL
`walkforward.retention()` and the real fold geometry with synthetic series and
measured thousands of draws per second. Point that machinery at actual prices
instead of synthetic ones and it stops being an audit and becomes a sieve.

THE ONE RULE, AND IT IS NOT NEGOTIABLE

**A pre-screen may only ever REJECT. It must never approve, and it never renders a
verdict.** It has no LEAN fidelity, no fills, no capacity model, and only a crude
cost haircut. If it could approve, it would be a second gate — quietly disagreeing
with the real one, and eventually cited as though it had been the real one. So the
output vocabulary is deliberately two words: `worth_a_container` or `rejected`, and
even a passing candidate carries no claim beyond "not obviously dead".

WHICH MEANS THE NUMBER THAT MATTERS IS THE FALSE-NEGATIVE RATE

A pre-screen that wrongly rejects a real edge destroys it silently and forever —
nothing downstream will ever look at it again. That is a far worse failure than
wasting a container on a dud, so the bar here is deliberately much looser than the
gate's, and `scripts/prescreen_audit.py` measures how often it discards something
the gate would have passed. That measurement is the whole licence to use this.

SPECS, NOT CODE

Vectorising arbitrary LEAN Python is not possible, so a pre-screenable candidate is
a declarative SPEC that both this module and a LEAN template can execute. That is a
real architectural commitment: candidates become data. Today only the two
cross-sectional families the fund actually researches are expressible, and a spec
this module cannot express is REFUSED rather than guessed at — a pre-screen that
silently approximated a rule it did not understand would be worse than no
pre-screen, because its rejections would look just as authoritative.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional, Sequence

logger = logging.getLogger(__name__)

#: Signal families this module can evaluate exactly. Anything else is REFUSED.
KINDS = ("xs_momentum", "xs_meanrev")

#: Round-trip cost haircut, in basis points, applied on every rebalance. Crude on
#: purpose: the real cost sweep lives in the belt, and a pre-screen pretending to
#: model execution would be claiming fidelity it does not have. 10bps is roughly
#: double the fund's measured 5.95bps/side, so it errs toward pessimism — which is
#: the wrong direction for a sieve whose false negatives are the expensive error,
#: and is therefore compensated by the deliberately loose thresholds below.
COST_BPS_PER_REBALANCE = 10.0

#: The sieve's bar. NOT the gate's, and much looser on every axis, because the
#: expensive mistake here is rejecting something real. A candidate clearing these
#: has earned a container, nothing more.
#: Chosen by measurement, not by feel. `scripts/prescreen_audit.py` swept the floor
#: against the worst false-negative rate over Sharpe 0.0-1.5, and against the kill
#: rate on a real 196-organism momentum grid:
#:
#:     floor   worst FN   kill rate   LEAN hours for a 1000-organism population
#:      0.15       0.0%       35.7%      150
#:      0.30       3.0%       44.4%      130
#:      0.45       4.2%       56.6%      101   <- chosen
#:      0.60      12.1%       70.4%       69
#:      0.80      33.3%       85.7%       33
#:
#: 0.45 is the last row under the 5% false-negative line, which was set BEFORE
#: looking at the table. 0.60 is tempting and wrong: losing one real edge in eight,
#: permanently and silently, is not worth 32 container-hours.
MIN_SHARPE = 0.45          # on EXCESS return; the gate asks ~1.0+ via PSR 65%
MIN_TRADES = 8             # gate asks 20
MIN_FOLD_SHARE = 0.25      # gate asks a strict majority
MIN_OBS = 120              # below this the estimate is not worth acting on


class SpecError(ValueError):
    """A spec this module cannot evaluate exactly. Refused, never approximated."""


def validate(spec: dict[str, Any]) -> dict[str, Any]:
    kind = spec.get("kind")
    if kind not in KINDS:
        raise SpecError(
            f"kind must be one of {KINDS}, got {kind!r}. A spec this module cannot "
            f"express is refused rather than approximated — a silently guessed "
            f"rule would produce rejections that look just as authoritative as "
            f"measured ones")
    look = int(spec.get("lookback_days") or 0)
    hold = int(spec.get("hold_days") or 0)
    top_n = int(spec.get("top_n") or 0)
    if look < 2:
        raise SpecError("lookback_days must be >= 2")
    if hold < 1:
        raise SpecError("hold_days must be >= 1")
    if top_n < 1:
        raise SpecError("top_n must be >= 1")
    return {"kind": kind, "lookback_days": look, "hold_days": hold,
            "top_n": top_n, "long_short": bool(spec.get("long_short"))}


def _equity_curve(spec: dict[str, Any], symbols: Sequence[str],
                  closes: Any, np_mod: Any) -> tuple[Any, int]:
    """Vectorised cross-sectional rule over a (T x N) close matrix.

    Returns daily EXCESS returns over the equal-weight universe (scaled by net
    exposure) and the number of rebalances. Positions are formed on day t from
    information available UP TO t and earn the return from t to t+1 — the one-bar
    shift is what keeps this out of look-ahead, and it is the single most important
    line in the module.

    Excess rather than raw, because raw made the sieve useless: see the comment at
    the subtraction below.
    """
    np = np_mod
    look = spec["lookback_days"]
    hold = spec["hold_days"]
    top_n = min(spec["top_n"], len(symbols))

    rets = closes[1:] / closes[:-1] - 1.0            # (T-1, N) simple returns
    T = rets.shape[0]
    if T <= look + hold:
        return np.zeros(0), 0

    # Trailing signal: cumulative return over `look` days, ending at t.
    logp = np.log(np.maximum(closes, 1e-12))
    sig = logp[look:] - logp[:-look]                  # (T+1-look, N)
    # Align the signal to the RETURN index: sig row i is known at close of
    # bar (i + look), and earns rets[i + look] which spans that close to the next.
    sig = sig[:-1] if sig.shape[0] > T - look else sig

    weights = np.zeros_like(rets)
    rebalances = 0
    t = look
    while t < T:
        row = sig[t - look] if (t - look) < sig.shape[0] else None
        if row is None:
            break
        ok = np.isfinite(row)
        if ok.sum() >= max(2, top_n):
            order = np.argsort(np.where(ok, row, -np.inf))
            winners = order[-top_n:] if spec["kind"] == "xs_momentum" \
                else order[:top_n][::-1]
            w = np.zeros(rets.shape[1])
            w[winners] = 1.0 / top_n
            if spec["long_short"]:
                losers = order[:top_n] if spec["kind"] == "xs_momentum" \
                    else order[-top_n:]
                w[losers] -= 1.0 / top_n
            weights[t:t + hold] = w
            rebalances += 1
        t += hold

    port = np.nansum(weights * rets, axis=1)
    # Cost on each rebalance day only. Turnover is approximated as full, which is
    # true for a top-N rule that reconstitutes its whole book.
    if rebalances:
        cost = COST_BPS_PER_REBALANCE / 10_000.0
        for i in range(look, T, hold):
            if i < port.shape[0]:
                port[i] -= cost

    # EXCESS over the equal-weight universe, scaled by net exposure.
    #
    # Measured, and it is the difference between a sieve and a decoration: screening
    # on RAW return killed only 16% of a real momentum grid, because in a rising
    # market almost any long-only rule shows a positive Sharpe. The sieve was
    # measuring beta and calling it edge — the exact error `must_beat_benchmark`
    # exists in the gate to prevent, which the sieve then had to learn separately.
    #
    # Scaling by net exposure is what makes one formula correct for both families:
    # a long-only book nets 1.0 and has the whole benchmark removed, while a
    # market-neutral book nets ~0 and keeps its return, since it never took the beta
    # in the first place. Subtracting a full benchmark from a long-short rule would
    # have penalised it for exposure it does not hold.
    bench = np.nanmean(rets, axis=1)
    net = np.nansum(weights, axis=1)
    excess = port - net * bench
    return excess[look:], rebalances


def _sharpe(port: Any, np_mod: Any) -> Optional[float]:
    np = np_mod
    if port.shape[0] < 20:
        return None
    sd = float(np.std(port))
    if sd <= 1e-12:
        return None
    return float(np.mean(port)) / sd * math.sqrt(252.0)


def _cum_pct(port: Any, np_mod: Any) -> float:
    return float((np_mod.prod(1.0 + port) - 1.0) * 100.0)


def screen(spec: dict[str, Any], symbols: Sequence[str],
           closes_by_symbol: dict[str, Sequence[float]],
           train_days: int = 252) -> dict[str, Any]:
    """One candidate, sieved. Returns `rejected` with a reason, or `worth_a_container`.

    Runs the fund's REAL `walkforward.retention()` on the folds, so the sieve and
    the gate agree about what retention means. Everything else here is looser than
    the gate on purpose.
    """
    import numpy as np

    from app.fund.walkforward import (RETENTION_FLOOR, decisions_per_test_leg,
                                      retention)

    s = validate(spec)
    syms = [x for x in symbols if x in closes_by_symbol]
    if len(syms) < 2:
        return _reject("fewer than two symbols with price history, so a "
                       "cross-sectional rule has nothing to rank", s)

    n = min(len(closes_by_symbol[x]) for x in syms)
    if n < MIN_OBS:
        return _reject(f"only {n} aligned observations; {MIN_OBS} is the minimum "
                       f"before an estimate is worth acting on", s)
    closes = np.array([list(closes_by_symbol[x])[-n:] for x in syms],
                      dtype=float).T

    port, rebalances = _equity_curve(s, syms, closes, np)
    if port.shape[0] < 40:
        return _reject("not enough history left after the lookback to form a "
                       "series", s, rebalances=rebalances)
    if rebalances < MIN_TRADES:
        return _reject(f"only {rebalances} rebalances; {MIN_TRADES} is the "
                       f"minimum before a Sharpe describes anything", s,
                       rebalances=rebalances)

    sharpe = _sharpe(port, np)
    if sharpe is None:
        return _reject("no measurable volatility, so no Sharpe", s,
                       rebalances=rebalances)
    if sharpe < MIN_SHARPE:
        return _reject(f"excess-return Sharpe {sharpe:.2f} (over the equal-weight "
                       f"universe) is below the sieve floor of {MIN_SHARPE} — it "
                       f"may still have made money, but not more than owning the "
                       f"universe", s, rebalances=rebalances, sharpe=sharpe)

    # Folds, using the REAL retention rule so the sieve cannot disagree with the
    # gate about the meaning of the word.
    decisions = decisions_per_test_leg()
    test_days = s["hold_days"] * decisions
    measurable = retained = 0
    k = 0
    while (k + 1) * test_days + train_days <= port.shape[0]:
        t0 = k * test_days
        t1 = t0 + train_days
        got = retention(_cum_pct(port[t0:t1], np),
                        _cum_pct(port[t1:t1 + test_days], np),
                        test_orders=decisions,
                        train_days=train_days, test_days=test_days)
        if got["measurable"]:
            measurable += 1
            if (got["retention"] or 0.0) >= RETENTION_FLOOR:
                retained += 1
        k += 1

    share = (retained / measurable) if measurable else None
    if measurable and share is not None and share < MIN_FOLD_SHARE:
        return _reject(f"kept its edge in {retained} of {measurable} folds "
                       f"({share:.0%}), below the sieve floor of "
                       f"{MIN_FOLD_SHARE:.0%}", s, rebalances=rebalances,
                       sharpe=sharpe, measurable=measurable, retained=retained)

    return {
        "verdict": "worth_a_container",
        "spec": s, "sharpe": round(sharpe, 3), "rebalances": rebalances,
        "folds_measurable": measurable, "folds_retained": retained,
        "obs": int(port.shape[0]),
        "claim": "NOT a pass. This says only that the candidate is not obviously "
                 "dead and is worth an engine run. The pre-screen cannot approve "
                 "anything — no fills, no capacity, only a crude cost haircut — "
                 "and a verdict comes from the gate or from nowhere.",
    }


def _reject(reason: str, spec: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"verdict": "rejected", "reason": reason, "spec": spec,
            "claim": "Rejected before a container started. A wrong rejection here "
                     "destroys a real edge silently, which is why the thresholds "
                     "are far looser than the gate's — see "
                     "scripts/prescreen_audit.py for the measured false-negative "
                     "rate that licenses using this at all.",
            **extra}


def population(specs: Sequence[dict[str, Any]], symbols: Sequence[str],
               closes_by_symbol: dict[str, Sequence[float]],
               train_days: int = 252) -> dict[str, Any]:
    """Sieve a whole population. Bars are loaded once by the caller, on purpose.

    Reloading price history per organism is what made the naive version slow for
    reasons that had nothing to do with LEAN.
    """
    kept, killed, refused = [], [], []
    for spec in specs:
        try:
            got = screen(spec, symbols, closes_by_symbol, train_days=train_days)
        except SpecError as e:
            refused.append({"spec": spec, "reason": str(e)})
            continue
        except Exception as e:  # noqa: BLE001
            # An organism that CRASHED the sieve is not an organism the sieve
            # rejected. Collapsing the two would quietly convert bugs into
            # verdicts, which is how a sieve starts lying.
            refused.append({"spec": spec,
                            "reason": f"sieve error, NOT a rejection: "
                                      f"{type(e).__name__}: {e}"})
            continue
        (kept if got["verdict"] == "worth_a_container" else killed).append(got)
    total = len(kept) + len(killed)
    return {
        "worth_a_container": kept,
        "rejected": killed,
        "refused": refused,
        "population": len(specs),
        "kill_rate_pct": round(100.0 * len(killed) / total, 1) if total else None,
        "note": (f"{len(kept)} of {len(specs)} organisms earned an engine run; "
                 f"{len(killed)} were sieved out and {len(refused)} could not be "
                 f"evaluated — refused is NOT rejected, and mixing them would "
                 f"convert bugs into verdicts."),
    }


def grid_to_specs(kind: str, lookbacks: Sequence[int], holds: Sequence[int],
                  top_ns: Sequence[int],
                  long_short: Sequence[bool] = (False,)) -> list[dict[str, Any]]:
    """The population, as data. This is the 'variation' rung made concrete."""
    out = []
    for lb in lookbacks:
        for h in holds:
            for tn in top_ns:
                for ls in long_short:
                    out.append({"kind": kind, "lookback_days": lb, "hold_days": h,
                                "top_n": tn, "long_short": ls})
    return out
