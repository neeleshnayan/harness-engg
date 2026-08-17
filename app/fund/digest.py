"""What happened overnight, and the short list of things only a human can decide.

The loop is built and barely lived in. 376 observations carry exactly one review,
and that review was made by the person testing the review button. A map, an
evidence panel and a provenance report are only as honest as their daily use;
unused they are a museum with excellent signage.

Nothing here is new capability. It is a READING ORDER over what the fund already
knows, on the theory that the loop's missing piece is not another surface but a
reason to come back tomorrow. So this answers, in one page, the four questions an
operator actually has in the morning:

  1. Is the machine healthy and is the ledger intact?
  2. What did it read while I was asleep?
  3. What did it judge, and what died — in the gate's own sentences?
  4. What needs my click today?

Two rules it inherits from everything else here. Every number is the system's own
or absent — a digest that filled a gap with a plausible figure would be the most
dangerous surface in the fund, because it is the one nobody double-checks. And
silence is reported as silence: "nothing was read overnight" is a finding worth
seeing, not an empty section to skip past.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: Algorithms that exist to MEASURE the harness, not to be traded. The null audit
#: puts random-entry strategies down the same belt real candidates use — which is
#: the point, since a calibration on a gentler path would measure the wrong
#: process — but three of them cleared gate v1, and the digest promptly asked a
#: human to review them as opportunities. An instrument that can be mistaken for
#: a proposal is a bad instrument.
CALIBRATION_ALGORITHMS = ("null_random_smallcap", "oracle_calibration_only")


def is_calibration(algorithm: Optional[str]) -> bool:
    return str(algorithm or "") in CALIBRATION_ALGORITHMS


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build(store: Any = None, observations: Any = None, factory: Any = None,
          universe: Any = None, runner: Any = None, provenance: Any = None,
          nav: Any = None, approvals: Any = None,
          adv_band: Optional[tuple] = None, deployed: Any = None,
          since_hours: float = 24.0) -> dict[str, Any]:
    """Assemble the morning read. Every section degrades to a stated absence.

    Each block is wrapped: one unavailable subsystem must not blank the page.
    A digest that fails closed teaches the operator to stop opening it, and an
    operator who stops opening it is the failure mode this exists to prevent.
    """
    since = _now() - timedelta(hours=since_hours)
    out: dict[str, Any] = {
        "generated_at": _now().isoformat(),
        "window_hours": since_hours,
    }
    for name, fn in (
        ("health", lambda: _health(store, nav)),
        ("read", lambda: _read(observations, universe, since, adv_band)),
        ("judged", lambda: _judged(factory, since)),
        ("needs_you", lambda: _needs_you(factory, observations, provenance,
                                         approvals, deployed)),
    ):
        try:
            out[name] = fn()
        except Exception as e:  # noqa: BLE001
            logger.warning("digest section %s unavailable: %s", name, e)
            out[name] = {"unavailable": f"{type(e).__name__}: {e}"[:200]}
    out["headline"] = _headline(out)
    return out


def _health(store: Any, nav: Any) -> dict[str, Any]:
    """The two facts that decide whether anything else on the page is worth
    reading: does the chain verify, and does NAV still fold from the log."""
    block: dict[str, Any] = {}
    if store is not None:
        try:
            v = store.verify_chain()
            block["chain_ok"] = bool(v.get("ok"))
            block["events_checked"] = v.get("checked")
        except Exception as e:  # noqa: BLE001
            block["chain_ok"] = None
            block["chain_note"] = f"could not verify: {e}"[:160]
    # NAV arrives already computed, for the same reason approvals do: the digest
    # is a reading order over facts, not a second place that knows how to value
    # the book. A page that recomputed NAV could disagree with the page that
    # reports it, and then there would be two answers.
    if isinstance(nav, dict):
        block["nav_usd"] = nav.get("total_nav_usd")
    return block


def _read(observations: Any, universe: Any, since: datetime,
          adv_band: Optional[tuple] = None) -> dict[str, Any]:
    """What the reader covered, measured against the band rather than the market."""
    if observations is None:
        return {"unavailable": "observations need FUND_STORE=postgres"}
    fresh = observations.since(since) if hasattr(observations, "since") else None
    cov = (observations.coverage(adv_lo=adv_band[0], adv_hi=adv_band[1])
           if adv_band else observations.coverage())
    block: dict[str, Any] = {
        "observations_total": cov.get("observations"),
        "band": cov.get("band"),
    }
    if fresh is None:
        block["overnight"] = None
        block["note"] = ("cannot tell what arrived overnight — no time-windowed "
                         "read available, so this is unknown rather than zero")
        return block
    block["overnight"] = len(fresh)
    block["overnight_tickers"] = sorted({o["ticker"] for o in fresh})
    block["by_category"] = _counts(o.get("category") for o in fresh)
    block["note"] = (
        f"{len(fresh)} new observation(s) across "
        f"{len(block['overnight_tickers'])} name(s)"
        if fresh else
        "nothing was read overnight — which is a finding about the schedule, "
        "not about the market")
    return block


def _judged(factory: Any, since: datetime) -> dict[str, Any]:
    """Verdicts, not ideas. The gate's own sentences, verbatim.

    Paraphrasing a verdict would be the one place a summary could do real harm:
    the wording IS the evidence, and a tidier version of "kept only −21% of its
    edge out of sample" is a weaker claim than the gate actually made.
    """
    if factory is None:
        return {"unavailable": "the factory needs FUND_STORE=postgres"}
    rows = factory.history(limit=50) if hasattr(factory, "history") else []
    fresh = [r for r in rows
             if _at(r.get("finished_at") or r.get("started_at")) >= since]
    # Counted separately, never silently dropped: hiding them would make the
    # belt look quieter than it was, and the audit's whole value is that it ran.
    calibration = [r for r in fresh if is_calibration(r.get("algorithm"))]
    fresh = [r for r in fresh if not is_calibration(r.get("algorithm"))]
    passed = [r for r in fresh if r.get("passed") is True]
    failed = [r for r in fresh if r.get("passed") is False]
    unjudged = [r for r in fresh if r.get("passed") is None]
    return {
        "candidates": len(fresh),
        "passed": len(passed),
        "failed": len(failed),
        # Distinct from failed, always: a candidate that crashed was never
        # examined, and folding it into the failures would inflate the appearance
        # of rigour with runs nobody scored.
        "unjudged": len(unjudged),
        "deaths": [{"candidate_id": r.get("candidate_id"),
                    "algorithm": r.get("algorithm"),
                    "because": r.get("failures") or []}
                   for r in failed],
        "passes": [{"candidate_id": r.get("candidate_id"),
                    "algorithm": r.get("algorithm"),
                    "winner": r.get("winner")} for r in passed],
        "calibration_runs": len(calibration),
        "note": _judged_note(len(fresh), len(passed), len(failed),
                             len(unjudged), len(calibration)),
    }


def _needs_you(factory: Any, observations: Any, provenance: Any,
               approvals: Any, deployed: Any = None) -> dict[str, Any]:
    """The only section that asks for anything. Kept short on purpose.

    A list of forty things is a list nobody works through, and the fund's whole
    approval model depends on the human actually reading the few items that
    genuinely need a decision.
    """
    items: list[dict[str, Any]] = []
    live = set(deployed or ())
    seen_failing: set[str] = set()
    if factory is not None:
        try:
            for r in (factory.history(limit=50) if hasattr(factory, "history") else []):
                if is_calibration(r.get("algorithm")):
                    # A null that cleared the bar is a finding about the GATE,
                    # not an opportunity. Asking a human to review it would put
                    # a random strategy on the same page as a real proposal.
                    continue
                algo = str(r.get("algorithm") or "")
                # A strategy the fund is ACTUALLY HOLDING that fails the bar is
                # the most decision-shaped thing this page can contain, and the
                # digest used to report "nothing needs a decision" on exactly the
                # morning three of them failed. A passing candidate is an
                # opportunity; a failing deployed one is live money governed by
                # something that just did not survive its own test.
                if (r.get("passed") is False and algo in live
                        and algo not in seen_failing):
                    seen_failing.add(algo)
                    items.append({
                        "kind": "deployed_strategy_failed",
                        "what": f"{algo} is DEPLOYED and failed the gate "
                                f"({r.get('candidate_id')})",
                        "why_you": "the fund holds a position on this. Keeping "
                                   "it, flattening it, or keeping the exposure "
                                   "without the strategy are all your call — "
                                   "nothing here changes a position",
                    })
                if r.get("passed") is True:
                    items.append({
                        "kind": "candidate_passed",
                        "what": f"{r.get('algorithm')} cleared the gate "
                                f"({r.get('candidate_id')})",
                        "why_you": "passing is not deploying — promotion is a "
                                   "human decision, and nothing in the system "
                                   "will make it for you",
                    })
        except Exception as e:  # noqa: BLE001
            items.append({"kind": "unavailable",
                          "what": f"could not read candidates: {e}"[:160]})
    # The approval desk. Passed in already-resolved rather than reached for,
    # because the digest must not know how approvals are stored — that is the
    # one coupling that would make this page break every time the queue moves.
    if isinstance(approvals, dict) and approvals.get("pending_count"):
        items.append({
            "kind": "approvals_pending",
            "what": f"{store['pending_count']} proposal(s) waiting at the "
                    f"approval desk",
            "why_you": "no agent path executes without this click",
        })
    return {"count": len(items), "items": items,
            "note": ("nothing needs a decision today"
                     if not items else
                     f"{len(items)} item(s) need a human")}


def _counts(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        k = v or "other"
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def _at(raw: Any) -> datetime:
    """Parse a timestamp, or return the epoch so a row with no time sorts out
    rather than crashing the page."""
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(raw))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _judged_note(n: int, passed: int, failed: int, unjudged: int,
                 calibration: int = 0) -> str:
    tail = (f"; {calibration} calibration run(s) also went down the belt and are "
            f"NOT proposals" if calibration else "")
    if not n:
        return ("nothing went down the belt — the research loop did not run, "
                "which is a fact about us and not about the market" + tail)
    bits = [f"{n} candidate(s) judged"]
    if passed:
        bits.append(f"{passed} cleared the gate and need a human look")
    if failed:
        bits.append(f"{failed} died")
    if unjudged:
        bits.append(f"{unjudged} could not be scored at all — not evidence "
                    f"either way")
    return "; ".join(bits) + tail


def _headline(out: dict[str, Any]) -> str:
    """One sentence for the top of the page, worst news first.

    Ordered by what should change the reader's next five minutes: a broken chain
    outranks a good backtest, and an idle loop outranks a tidy one.
    """
    health = out.get("health") or {}
    if health.get("chain_ok") is False:
        return ("THE EVENT CHAIN DOES NOT VERIFY — stop and investigate before "
                "trusting any number on this page")
    judged = out.get("judged") or {}
    needs = out.get("needs_you") or {}
    read = out.get("read") or {}
    failing_live = [i for i in (needs.get("items") or [])
                    if i.get("kind") == "deployed_strategy_failed"]
    if failing_live:
        return (f"{len(failing_live)} DEPLOYED strategy(s) failed the gate — the "
                f"fund holds positions on them")
    if needs.get("count"):
        return f"{needs['count']} item(s) need your decision today"
    if judged.get("passed"):
        return f"{judged['passed']} candidate(s) cleared the gate overnight"
    if judged.get("candidates"):
        return (f"{judged.get('failed', 0)} candidate(s) died overnight and "
                f"nothing needs a click")
    if read.get("overnight"):
        return (f"{read['overnight']} observation(s) read overnight, nothing "
                f"judged yet")
    return ("the loop was idle — nothing read, nothing judged, nothing waiting "
            "on you")
