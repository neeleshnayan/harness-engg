"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Loader2, Sliders } from "lucide-react";
import { spineError } from "@/lib/spine_error";
import { KT } from "../theme";
import { RiskLimitsConfig, fundApiClient } from "@/lib/fund_api";

/**
 * The mandate's limits, editable — because a limit you cannot see is a rule you
 * cannot reason about, and one you can only change by curling the API is one
 * that gets worked around instead of changed.
 *
 * Changes are event-sourced by the spine (RiskLimitsSet), so loosening a limit
 * is on the record next to the trade it permitted. That is the point: this is
 * not a settings page, it is an amendment to the mandate.
 *
 * Editing is two-step for the same reason halting is. Nothing here takes effect
 * until Apply, and the diff is shown first — a slider that silently widens a
 * risk limit is how a fund ends up with limits nobody chose.
 */

//: The pre-trade limits an operator actually tunes. The structural ones
//: (correlation, effective bets, expected shortfall) are Vishesh's and live on
//: the Risk page — they are not knobs you turn to get an order through.
const FIELDS: { key: keyof RiskLimitsConfig; label: string; help: string }[] = [
  { key: "max_position_pct", label: "Max single position",
    help: "no one name may exceed this share of NAV" },
  { key: "max_order_notional_pct", label: "Max order size",
    help: "caps the exposure-INCREASING part of an order; closing a position is exempt" },
  { key: "max_strategy_pct", label: "Max per strategy",
    help: "no one strategy may exceed this share of NAV" },
  { key: "min_cash_pct", label: "Cash floor",
    help: "buys are refused if they would drop cash below this" },
  { key: "max_drawdown_pct", label: "Drawdown halt",
    help: "trading halts automatically at this drawdown from peak NAV" },
  { key: "max_daily_loss_pct", label: "Daily loss halt",
    help: "halts if NAV falls this far versus the last daily strike" },
];

const asPct = (v?: number | null) => (v == null ? "" : String(Math.round(v * 1000) / 10));

export function LimitsEditor({ onChanged }: { onChanged?: () => void }) {
  const [limits, setLimits] = useState<RiskLimitsConfig | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const l = await fundApiClient.getRiskLimits();
      setLimits(l);
      setDraft(Object.fromEntries(FIELDS.map((f) => [f.key, asPct(l[f.key] as number)])));
      setErr(null);
    } catch (e: unknown) {
      setErr(spineError(e));
      setLimits(null);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Only fields the operator actually changed, converted back to fractions.
  const changes = FIELDS.flatMap((f) => {
    if (!limits) return [];
    const before = (limits[f.key] as number) ?? 0;
    const raw = draft[f.key];
    if (raw === undefined || raw === "") return [];
    const after = Number(raw) / 100;
    if (!Number.isFinite(after) || Math.abs(after - before) < 1e-9) return [];
    return [{ ...f, before, after }];
  });

  const apply = async () => {
    setBusy(true);
    setErr(null);
    try {
      await fundApiClient.setRiskLimits(
        Object.fromEntries(changes.map((c) => [c.key, c.after])), "neelesh",
      );
      await load();
      onChanged?.();
    } catch (e: unknown) {
      setErr(spineError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={KT.panel}>
      <button onClick={() => setOpen((o) => !o)}
              className="flex w-full items-center justify-between px-5 py-3 text-left">
        <span className="flex items-center gap-2">
          <Sliders size={14} className={KT.muted} />
          <span className={KT.label}>Risk limits</span>
        </span>
        <span className={`text-[11px] ${KT.muted}`}>{open ? "hide" : "view / edit"}</span>
      </button>

      {open && (
        <div className="border-t border-[var(--kt-border)] px-5 py-4">
          {err && <div className={`mb-3 text-[12px] ${KT.down}`}>{err}</div>}
          {!limits ? (
            <div className={`text-[12px] ${KT.sev.warn}`}>
              Limits unreadable — they are still in force, this view just cannot show them.
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {FIELDS.map((f) => (
                  <label key={f.key} className="block">
                    <span className={`block text-[11px] ${KT.muted}`}>{f.label}</span>
                    <span className="mt-1 flex items-center gap-1">
                      <input
                        type="number" step="0.5" min="0" max="100"
                        value={draft[f.key] ?? ""}
                        onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
                        className="w-20 rounded border border-[var(--kt-border)] bg-transparent px-2 py-1 font-mono text-[12px] tabular-nums outline-none focus:border-[var(--kt-accent)]"
                      />
                      <span className={`text-[11px] ${KT.muted}`}>% of NAV</span>
                    </span>
                    <span className={`mt-0.5 block text-[10px] ${KT.muted}`}>{f.help}</span>
                  </label>
                ))}
              </div>

              {changes.length > 0 && (
                <div className={`mt-4 p-3 ${KT.inset}`}>
                  <div className="text-[12px] font-medium">
                    {changes.length} change{changes.length === 1 ? "" : "s"} to the mandate
                  </div>
                  <ul className={`mt-1.5 space-y-0.5 text-[12px] ${KT.muted}`}>
                    {changes.map((c) => {
                      // "Looser" is not always "bigger": a floor loosens by falling.
                      const looser = c.key === "min_cash_pct"
                        ? c.after < c.before : c.after > c.before;
                      return (
                        <li key={c.key}>
                          · {c.label}: {(c.before * 100).toFixed(1)}% →{" "}
                          <span className="font-mono">{(c.after * 100).toFixed(1)}%</span>{" "}
                          <span className={looser ? KT.down : KT.up}>
                            ({looser ? "looser" : "tighter"})
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                  <div className="mt-3 flex gap-2">
                    <button disabled={busy} onClick={apply}
                            className={`flex items-center gap-1.5 ${KT.btn}`}>
                      {busy && <Loader2 size={14} className="animate-spin" />}
                      Apply to the mandate
                    </button>
                    <button disabled={busy} onClick={load} className={KT.btnGhost}>
                      Discard
                    </button>
                  </div>
                  <p className={`mt-2 text-[10px] ${KT.muted}`}>
                    Recorded as an event, so a loosened limit sits in the log beside
                    the trade it allowed.
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
