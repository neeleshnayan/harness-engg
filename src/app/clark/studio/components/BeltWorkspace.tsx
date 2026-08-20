"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { fundApiClient } from "@/lib/fund_api";
import { KT } from "../theme";

/**
 * The belt's workspace — which strategies ran, when, the code, and what the
 * holdout said. CEO ask, 2026-08-20: "an agent workspace so I can see which
 * strategies were run, when, the code and backtest results."
 *
 * Grouped by ALGORITHM (that is how the quant thinks), each with its sweep
 * history under it. The source is fetched only when opened — 14 algorithms'
 * code on page load would be weight without a reader. Absence discipline:
 * a sweep with no holdout says so; an algorithm with no sweeps is shown as
 * never-run, which is a real state, not a gap.
 */

type Sweeps = Awaited<ReturnType<typeof fundApiClient.getLeanSweeps>>["sweeps"];
type Algos = Awaited<ReturnType<typeof fundApiClient.getLeanAlgorithms>>["algorithms"];

const pct = (n?: number | null) => (n == null ? "—" : `${n > 0 ? "+" : ""}${n}%`);

export function BeltWorkspace() {
  const [sweeps, setSweeps] = useState<Sweeps | null>(null);
  const [algos, setAlgos] = useState<Algos | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [openAlgo, setOpenAlgo] = useState<string | null>(null);
  const [source, setSource] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    const [s, a] = await Promise.allSettled([
      fundApiClient.getLeanSweeps(),
      fundApiClient.getLeanAlgorithms(),
    ]);
    if (s.status === "fulfilled") { setSweeps(s.value.sweeps || []); setErr(null); }
    else setErr(s.reason instanceof Error ? s.reason.message : "unreachable");
    if (a.status === "fulfilled") setAlgos(a.value.algorithms || []);
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggle = async (name: string) => {
    const next = openAlgo === name ? null : name;
    setOpenAlgo(next);
    if (next && !(next in source)) {
      try {
        const got = await fundApiClient.getLeanAlgorithm(next);
        setSource((m) => ({ ...m, [next]: got.code }));
      } catch {
        setSource((m) => ({ ...m, [next]: "" }));
      }
    }
  };

  const byAlgo = useMemo(() => {
    const m = new Map<string, Sweeps>();
    for (const s of sweeps ?? []) {
      const rows = m.get(s.algorithm) ?? [];
      rows.push(s);
      m.set(s.algorithm, rows);
    }
    for (const rows of m.values()) {
      rows.sort((a, b) => (b.submitted_at || "").localeCompare(a.submitted_at || ""));
    }
    return m;
  }, [sweeps]);

  const names = useMemo(() => {
    const fromDisk = (algos ?? []).map((a) => a.name);
    const fromSweeps = Array.from(byAlgo.keys());
    return Array.from(new Set([...fromDisk, ...fromSweeps])).sort(
      (a, b) => ((byAlgo.get(b)?.[0]?.submitted_at || "")
        .localeCompare(byAlgo.get(a)?.[0]?.submitted_at || "")),
    );
  }, [algos, byAlgo]);

  if (err) {
    return (
      <p className={`mt-8 text-sm ${KT.sev.warn}`}>
        The belt workspace could not be read ({err}) — what ran is unknown, not
        nothing.
      </p>
    );
  }
  if (sweeps === null) return null;

  return (
    <section className="mt-10">
      <p className={`${KT.label} mb-1`}>The belt — what ran</p>
      <p className={`mb-4 max-w-3xl text-xs leading-relaxed ${KT.muted}`}>
        Every algorithm in the quant&apos;s workspace with its sweep history:
        when it ran, the training-window winner, and the held-out legs. Open one
        to read its code verbatim — the same file the container mounted.
      </p>
      <div className="space-y-2">
        {names.map((name) => {
          const rows = byAlgo.get(name) ?? [];
          const isOpen = openAlgo === name;
          return (
            <div key={name} className={`${KT.card} p-0`}>
              <button
                type="button"
                onClick={() => toggle(name)}
                aria-expanded={isOpen}
                className="flex w-full flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-3 text-left"
              >
                <span className="font-mono text-sm text-[var(--kt-accent)]">{name}</span>
                <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                  {rows.length
                    ? `${rows.length} sweep${rows.length === 1 ? "" : "s"} · last ${String(rows[0].submitted_at || "").slice(0, 10)}`
                    : "never run on the belt"}
                </span>
                <span className={`ml-auto font-mono text-[10px] ${KT.muted}`}>
                  {isOpen ? "− close" : "+ runs & code"}
                </span>
              </button>
              {isOpen && (
                <div className="border-t border-[var(--kt-border)] px-4 py-3">
                  {rows.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                            <th className="py-1 pr-4 font-normal">submitted</th>
                            <th className="py-1 pr-4 font-normal">state</th>
                            <th className="py-1 pr-4 font-normal">grid</th>
                            <th className="py-1 pr-4 font-normal">train best</th>
                            <th className="py-1 pr-4 font-normal">holdout train → test</th>
                            <th className="py-1 font-normal">test orders</th>
                          </tr>
                        </thead>
                        <tbody className="tabular-nums">
                          {rows.map((s) => {
                            const h = s.holdout_result;
                            return (
                              <tr key={s.sweep_id} className="border-t border-[var(--kt-border)]">
                                <td className="py-1.5 pr-4 font-mono text-[11px]">
                                  {String(s.submitted_at || "—").slice(0, 16).replace("T", " ")}
                                </td>
                                <td className="py-1.5 pr-4">{s.state}</td>
                                <td className="py-1.5 pr-4">
                                  {s.completed ?? "—"}/{s.total ?? "—"}
                                </td>
                                <td className="py-1.5 pr-4">
                                  {pct(s.summary?.best?.total_return_pct)}
                                </td>
                                <td className="py-1.5 pr-4">
                                  {h?.train || h?.test
                                    ? `${pct(h?.train?.return_pct)} → ${pct(h?.test?.return_pct)}`
                                    : "no holdout recorded"}
                                </td>
                                <td className="py-1.5">
                                  {h?.test?.total_orders ?? "—"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className={`text-xs ${KT.muted}`}>
                      On disk, never swept — code without a verdict.
                    </p>
                  )}
                  <div className="mt-3">
                    <p className={`${KT.label} mb-1`}>main.py, verbatim</p>
                    {source[name] === undefined ? (
                      <p className={`text-xs ${KT.muted}`}>reading…</p>
                    ) : source[name] === "" ? (
                      <p className={`text-xs ${KT.sev.warn}`}>
                        The source could not be read — absent, not empty.
                      </p>
                    ) : (
                      <pre className={`max-h-96 overflow-auto rounded-lg p-3 text-[11px] leading-relaxed ${KT.inset}`}>
                        {source[name]}
                      </pre>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
