"use client";

import React, { useEffect, useState } from "react";
import { KT } from "../theme";
import { readPdt } from "./pdtRule";
import { inFlightCount } from "../orderCounts";
import {
  ComplianceStatus, MarketSessionResponse, OrderHistoryRow, PendingOrder,
} from "@/lib/fund_api";

/**
 * The operator's verdict, in one line — the sentence the whole page exists to
 * let them assemble, pre-assembled.
 *
 * The header's RiskBar already owns the risk half (halt, drawdown, breaches),
 * so this line deliberately covers only the OPERATIONAL half: is anything
 * waiting on a decision, is anything mid-flight, how much day-trade budget is
 * left, and does our book still agree with the broker. Duplicating drawdown
 * here would teach the eye to skip one of the two places it appears.
 *
 * Every segment is nullable. A segment whose source failed says "unreadable"
 * in warn tone rather than vanishing — a missing chip reads as "nothing to
 * report", which is exactly the false all-clear this studio refuses to give.
 *
 * DEFECT C2, fixed 2026-08-20: `orders` used to arrive as `OrderHistoryRow[]`,
 * with the caller catching a failed fetch into `[]`. The in-flight segment then
 * counted zero rows and printed "nothing in flight" — a positive operational
 * all-clear assembled from an order history nobody had managed to read. It is
 * `OrderHistoryRow[] | null` now, and the null branch says so in warn tone,
 * exactly like the four segments beside it that already got this right.
 */

export function MonitorVerdict({
  pending, orders, compliance, session, driftCount, lastLoaded, onJumpToQueue,
}: {
  pending: PendingOrder[] | null;
  /** null = the order history could not be read. NOT an empty book. */
  orders: OrderHistoryRow[] | null;
  compliance: ComplianceStatus | null;
  session: MarketSessionResponse | null;
  /** symbols_out_of_sync from the reconciler; null = reconciler unreachable. */
  driftCount: number | null;
  /** ms epoch of the last successful page load — the freshness anchor. */
  lastLoaded: number | null;
  onJumpToQueue?: () => void;
}) {
  // Re-render on a slow tick so "checked Ns ago" stays true without a fetch.
  const [, setBeat] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setBeat((b) => b + 1), 10000);
    return () => clearInterval(t);
  }, []);

  // null = unknown. Counted in ../orderCounts.ts, where a test asserts that
  // `null` does not collapse to `0` — `orders?.filter(...).length ?? 0` would
  // quietly rebuild the very defect this signature change exists to remove.
  const working = inFlightCount(orders);
  const marketShut = session ? session.is_open === false : null;

  const seg: React.ReactNode[] = [];

  // 1 — waiting on the human. The one segment that may raise its voice.
  if (pending === null) {
    seg.push(<span key="q" className={KT.sev.warn}>approval queue unreadable</span>);
  } else if (pending.length > 0) {
    seg.push(
      <button key="q" onClick={onJumpToQueue}
              className={`font-medium ${KT.accent} underline-offset-2 hover:underline`}>
        {pending.length} order{pending.length === 1 ? "" : "s"} await your approval
      </button>,
    );
  } else {
    seg.push(<span key="q">nothing waiting on you</span>);
  }

  // 2 — in flight, with the context that decides whether it is news.
  //     "unreadable" and "nothing" are different sentences (C2).
  seg.push(
    orders === null ? (
      <span key="w" className={KT.sev.warn}>order history unreadable</span>
    ) : (
      <span key="w">
        {working === 0 ? "nothing in flight" : (
          <>
            <span className="font-mono tabular-nums">{working}</span> working
            {marketShut === true && <span className={KT.muted}> (market closed)</span>}
          </>
        )}
      </span>
    ),
  );

  // 3 — the cliff, IF there is one. One more day trade than budgeted restricted
  //     the account for ninety days, which is why it belonged in the first line
  //     read rather than row seven of a panel at the bottom. The rule was
  //     RETIRED 2026-08-27 (it ended 2026-06-04), so on today's payload this
  //     segment does not render at all — a retired rule is not a constraint and
  //     the one-line verdict is where the fund's LIVE constraints go.
  //
  //     Switched from `pdt.applies` to `readPdt(...).live`. The two agree today
  //     and they are not the same question: `applies` is a field, `live` is
  //     "can this stop a trade right now", and the shared reading is what keeps
  //     this line, SystemStatus and ClarkConsole from drifting apart the way
  //     they did when the rule was retired.
  const pdt = readPdt(compliance);
  if (pdt.live) {
    const left = pdt.remaining;
    seg.push(
      <span key="dt" className={left == null ? KT.sev.warn : left <= 0 ? KT.down : left === 1 ? KT.sev.warn : undefined}>
        {/* An unreadable count is a WORD, never a comfortable zero: "0 day
            trades left" and "we could not read the budget" are opposite
            facts, and the old `?? 0` rendered the second as the first. */}
        {left == null
          ? "day-trade budget UNKNOWN"
          : <><span className="font-mono tabular-nums">{left}</span> day trade{left === 1 ? "" : "s"} left</>}
      </span>,
    );
  } else if (pdt.state === "unreadable") {
    seg.push(<span key="dt" className={KT.sev.warn}>day-trade budget unreadable</span>);
  }

  // 4 — is our book still the broker's book.
  if (driftCount === null) {
    seg.push(<span key="r" className={KT.sev.warn}>reconciler unreachable</span>);
  } else if (driftCount > 0) {
    seg.push(
      <span key="r" className={KT.down}>
        book disagrees with broker ({driftCount})
      </span>,
    );
  } else {
    seg.push(<span key="r">book agrees with broker</span>);
  }

  const ageS = lastLoaded ? Math.max(0, Math.round((Date.now() - lastLoaded) / 1000)) : null;

  return (
    <div className={`mb-4 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-[12px] ${KT.body}`}>
      <span className={`h-1.5 w-1.5 self-center rounded-full ${
        (pending?.length ?? 0) > 0 ? "bg-[var(--kt-accent)]" : "bg-[var(--kt-text-dim)]"}`} />
      {seg.map((s, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span className={KT.muted}>·</span>}
          {s}
        </React.Fragment>
      ))}
      {ageS != null && (
        <span className={`ml-auto font-mono text-[10px] tabular-nums ${KT.muted}`}>
          checked {ageS < 5 ? "just now" : `${ageS}s ago`}
        </span>
      )}
    </div>
  );
}
