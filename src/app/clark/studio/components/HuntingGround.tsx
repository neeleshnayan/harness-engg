"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Compass, Loader2 } from "lucide-react";
import { KT } from "../theme";
import { fundApi } from "@/lib/fund_api";

/**
 * Where a fund this size has an advantage instead of an apology.
 *
 * Every position the fund holds sits in the handful of names with billions of
 * capacity — SPY, NVDA, MSFT — which is the one water where being small buys
 * nothing at all. This is the other water: names a multi-billion fund cannot
 * build a position in without moving the price against itself.
 *
 * Two numbers, and keeping them apart is the whole point of this panel.
 * CAPACITY is a property of a strategy at a turnover: how much money the idea
 * can carry. ACCESS is a property of the name: whether a large fund could get
 * in at all. They diverge badly — at 5% turnover a $250m-ADV name reports only
 * $50m of capacity, which reads as small, while a $5bn fund holds it in a
 * morning. Showing capacity alone had us calling S&P 500 large caps
 * "uninvestable by big funds".
 */

interface Name {
  symbol: string;
  /** What the business IS. A screen of bare tickers reads as a list; the same
   *  rows with names on them read as territory you can actually judge. */
  name?: string | null;
  security_type?: string | null;
  cik?: string | null;
  exchange?: string | null;
  adv_usd: number;
  median_close: number;
  capacity_usd: number;
  closed_to_big_funds?: boolean | null;
  big_fund_days_to_build?: number | null;
}

interface Ground {
  count: number;
  closed_to_big_funds_count?: number;
  identity_source?: string;
  excluded?: { not_operating?: number; unclassified?: number; note?: string };
  turnover_pct: number;
  capacity_band_usd: number[];
  caveat?: string;
  names: Name[];
}

const usd = (n?: number | null) =>
  n == null ? "—"
    : n >= 1e9 ? `$${(n / 1e9).toFixed(1)}bn`
    : n >= 1e6 ? `$${(n / 1e6).toFixed(1)}m`
    : `$${(n / 1e3).toFixed(0)}k`;

export function HuntingGround({ onPick }: { onPick?: (symbol: string) => void }) {
  const [turnover, setTurnover] = useState(1);
  const [onlyClosed, setOnlyClosed] = useState(true);
  const [data, setData] = useState<Ground | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      const d = (await fundApi.get("/api/v1/fund/universe/hunting-ground", {
        params: { turnover_pct: turnover, limit: 100 },
      })).data as Ground;
      setData(d);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setErr(detail ?? String(e));
    } finally {
      setBusy(false);
    }
  }, [turnover]);

  useEffect(() => { load(); }, [load]);

  const rows = (data?.names ?? []).filter(
    (n) => !onlyClosed || n.closed_to_big_funds);

  return (
    <div className={`mt-6 ${KT.panel}`}>
      <div className="flex flex-wrap items-center gap-3 border-b border-[var(--kt-border)] px-5 py-3">
        <div className="min-w-0">
          <span className={KT.label}>Hunting ground</span>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            Names a multi-billion fund cannot build a position in. Everything
            the fund holds today sits outside this list.
          </div>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <label className={`flex items-center gap-2 text-[11px] ${KT.muted}`}>
            <input type="checkbox" checked={onlyClosed}
                   onChange={(e) => setOnlyClosed(e.target.checked)}
                   className="accent-[var(--kt-accent)]" />
            closed to big funds only
          </label>
          <div className="flex items-center gap-2">
            <span className={`text-[10px] ${KT.muted}`}>turnover %</span>
            <input type="number" min={0.1} max={50} step={0.5} value={turnover}
                   onChange={(e) => setTurnover(Number(e.target.value))}
                   className={`w-20 ${KT.input} py-1`} aria-label="Daily turnover" />
          </div>
          <button onClick={load} disabled={busy}
                  className={`flex h-9 items-center gap-1.5 ${KT.btn} disabled:opacity-40`}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Compass size={14} />}
            Screen
          </button>
        </div>
      </div>

      {err && <div className={`px-5 py-3 text-sm ${KT.down}`}>{err}</div>}

      {data && (
        <>
          {/* "N of N" was a lie of omission: `count` is the length of the PAGE
              we asked for, not the size of the band, so a 100-row request always
              reported "100 of 100" and made a screen look exhaustive when it was
              showing the top slice of thousands. Say what the number is. */}
          <div className={`px-5 pt-3 text-[11px] ${KT.muted}`}>
            {data.closed_to_big_funds_count ?? 0} of the {data.count} shown here
            are genuinely closed to a $5bn fund at {data.turnover_pct}% daily
            turnover — this is the most liquid slice of the band, not all of it.
          </div>
          {data.excluded?.note && (
            <p className={`px-5 pt-1 text-[10px] ${KT.muted}`}>
              <span className="font-mono text-[9px] uppercase tracking-wider">
                identity
              </span>{" "}
              {data.excluded.note}
            </p>
          )}
          {data.caveat && (
            <p className={`px-5 pt-1 text-[10px] ${KT.muted}`}>{data.caveat}</p>
          )}
          <div className="max-h-[380px] overflow-auto px-2 py-3">
            <table className="w-full text-[11px]">
              <thead className="sticky top-0 bg-[var(--kt-surface)]">
                <tr className={KT.label}>
                  <th className="px-3 py-1 text-left font-normal">Symbol</th>
                  <th className="px-3 py-1 text-left font-normal">Business</th>
                  <th className="px-3 py-1 text-right font-normal">ADV</th>
                  <th className="px-3 py-1 text-right font-normal">Price</th>
                  <th className="px-3 py-1 text-right font-normal">Capacity</th>
                  <th className="px-3 py-1 text-right font-normal">Big fund build</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((n) => (
                  <tr key={n.symbol}
                      onClick={() => onPick?.(n.symbol)}
                      className={`border-t border-[var(--kt-border)] ${
                        onPick ? "cursor-pointer hover:bg-[var(--kt-hover)]" : ""}`}>
                    <td className="px-3 py-1.5 font-semibold">{n.symbol}</td>
                    <td className={`max-w-[260px] truncate px-3 py-1.5 ${KT.muted}`}
                        title={n.name ?? undefined}>
                      {n.name ?? "—"}
                      {n.security_type === "ADRC" && (
                        <span className={`ml-1.5 ${KT.chip}`}>ADR</span>
                      )}
                    </td>
                    <td className={`px-3 py-1.5 text-right ${KT.number}`}>{usd(n.adv_usd)}</td>
                    <td className={`px-3 py-1.5 text-right ${KT.number}`}>
                      {n.median_close?.toFixed(2)}
                    </td>
                    <td className={`px-3 py-1.5 text-right ${KT.number}`}>{usd(n.capacity_usd)}</td>
                    <td className={`px-3 py-1.5 text-right font-mono tabular-nums ${
                      n.closed_to_big_funds ? KT.up : KT.muted}`}>
                      {n.big_fund_days_to_build == null ? "—"
                        : `${n.big_fund_days_to_build.toFixed(1)}d`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && !busy && (
              <div className={`px-3 py-6 text-[11px] ${KT.muted}`}>
                Nothing in this band. Lower the turnover assumption — at high
                turnover the band admits large caps, which are not closed to
                anyone.
              </div>
            )}
          </div>
          <p className={`border-t border-[var(--kt-border)] px-5 py-3 text-[10px] ${KT.muted}`}>
            Build days assume a $5bn fund taking a 0.5% position at 15% of daily
            volume. Under three days and they can be here too; above it, the
            build moves the price and the name is effectively ours.
          </p>
        </>
      )}
    </div>
  );
}
