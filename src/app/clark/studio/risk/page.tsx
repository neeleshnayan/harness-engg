"use client";

import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import { spineError } from "@/lib/spine_error";
import { StudioHeader } from "../components/StudioHeader";
import { LossSurface } from "../components/LossSurface";
import { FactorMap3D } from "../components/FactorMap3D";
import { KT } from "../theme";
import { fundApiClient, AdvancedRiskView, FactorRow } from "@/lib/fund_api";

/**
 * RISK — Vishesh's surface. Structural risk, not position bookkeeping.
 *
 * Monitor answers "are we inside our limits today". This page answers the
 * questions limits cannot see:
 *
 *   · Is this book actually diversified, or one bet wearing nine hats?
 *   · Which position drives the RISK (as opposed to holding the capital)?
 *   · How bad is the tail, measured rather than assumed normal?
 *   · Is the market itself becoming fragile?
 *   · What move would breach our halt, and would we survive a real crisis?
 *
 * Every block reports `measurable: false` with a reason when it cannot be
 * computed. Nothing here renders a zero for an unknown — a zero is a claim, and
 * on a risk screen a false all-clear is the most expensive bug available.
 */

const money = (n?: number | null, dp = 0) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;
const pct = (n?: number | null, dp = 1) => (n == null ? "—" : `${Number(n).toFixed(dp)}%`);

/** Cached numbers must always announce their age. */
const fmtAge = (s?: number) => {
  if (s == null) return "—";
  if (s < 90) return `${Math.round(s)}s`;
  return `${Math.round(s / 60)}m`;
};

const SEV_TONE: Record<string, string> = {
  critical: "border-[var(--kt-down)]/40 bg-[var(--kt-down)]/10 text-[var(--kt-down)]",
  warn: "border-[var(--kt-warn)]/40 bg-[var(--kt-warn)]/10 text-[var(--kt-warn)]",
  info: "border-[var(--kt-border)] bg-[var(--kt-inset)] text-[var(--kt-text-dim)]",
};

function Panel({ title, subtitle, children, right }: {
  title: string; subtitle?: string; right?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section className={KT.panel}>
      <div className="flex items-start justify-between gap-4 border-b border-[var(--kt-border)] px-5 py-3">
        <div>
          <div className={KT.label}>{title}</div>
          {subtitle && <div className={`mt-1 text-[11px] ${KT.muted}`}>{subtitle}</div>}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

/** Unknown must look unknown. */
function NotMeasurable({ reason }: { reason?: string }) {
  return (
    <div className={`px-5 py-8 text-sm ${KT.sev.warn}`}>
      Not measurable — {reason ?? "no reason given"}.
      <div className={`mt-1 text-[11px] ${KT.muted}`}>
        This is not an all-clear. It means the figure could not be computed.
      </div>
    </div>
  );
}

/** Correlation matrix as a heatmap. 2D is the right dimensionality here. */
function CorrelationGrid({ symbols, matrix }: { symbols: string[]; matrix: number[][] }) {
  const tone = (v: number) => {
    const a = Math.min(Math.abs(v), 1);
    return v >= 0
      ? `rgba(239, 68, 68, ${0.08 + a * 0.55})`
      : `rgba(16, 185, 129, ${0.08 + a * 0.55})`;
  };
  return (
    <div className="overflow-x-auto px-5 py-4">
      <table className="border-separate border-spacing-0.5 font-mono text-[10px]">
        <thead>
          <tr>
            <th />
            {symbols.map((s) => (
              <th key={s} className={`px-1 pb-1 font-normal ${KT.muted}`}>{s}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={symbols[i]}>
              <td className={`pr-2 text-right font-normal ${KT.muted}`}>{symbols[i]}</td>
              {row.map((v, j) => (
                <td
                  key={j}
                  title={`${symbols[i]} / ${symbols[j]}: ${v.toFixed(2)}`}
                  className="h-7 w-11 rounded text-center tabular-nums text-[var(--kt-text)]"
                  style={{ background: i === j ? "var(--kt-inset)" : tone(v) }}
                >
                  {i === j ? "—" : v.toFixed(2)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className={`mt-2 text-[11px] ${KT.muted}`}>
        Red = moves together (no diversification). Green = moves opposite (a genuine hedge).
      </p>
    </div>
  );
}

/** Signed factor betas. The zero line is the whole point — a bar's side tells
 *  you the direction of the exposure, its length how much of it you have. */
function FactorBars({ rows }: { rows: FactorRow[] }) {
  const max = Math.max(...rows.map((r) => Math.abs(r.beta)), 0.5);
  return (
    <div className="space-y-2 px-5 py-4">
      {rows.map((r) => {
        const frac = Math.min(Math.abs(r.beta) / max, 1) * 50;
        const pos = r.beta >= 0;
        return (
          <div key={r.key} title={r.reads}>
            <div className="flex items-baseline gap-2 text-[11px]">
              <span className="w-20 font-medium">{r.label}</span>
              <span className={KT.muted}>{r.proxy}</span>
              <span className={`ml-auto font-mono tabular-nums ${r.significant ? "" : KT.muted}`}>
                {r.beta >= 0 ? "+" : ""}{r.beta.toFixed(2)}
              </span>
              <span className={`w-14 text-right font-mono tabular-nums ${
                r.significant ? (pos ? KT.down : KT.up) : KT.muted}`}>
                t {r.t_stat >= 0 ? "+" : ""}{r.t_stat.toFixed(1)}
              </span>
            </div>
            <div className="relative mt-1 h-2 w-full rounded bg-[var(--kt-track)]">
              <div className="absolute inset-y-0 left-1/2 w-px bg-[var(--kt-border-strong)]" />
              <div
                className={`absolute inset-y-0 rounded ${
                  r.significant ? "bg-[var(--kt-accent)]" : "bg-[var(--kt-text-muted)]"
                }`}
                style={pos
                  ? { left: "50%", width: `${frac}%` }
                  : { right: "50%", width: `${frac}%` }}
              />
            </div>
          </div>
        );
      })}
      <p className={`pt-1 text-[11px] ${KT.muted}`}>
        Solid = statistically significant (|t| &ge; 2). Faded bars are exposures the
        data cannot actually confirm.
      </p>
    </div>
  );
}

export default function RiskPage() {
  const [v, setV] = useState<AdvancedRiskView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (force = false) => {
    setLoading(true);
    try {
      setV(await fundApiClient.getRiskAdvanced({ force }));
      setErr(null);
    } catch (e: unknown) {
      setErr(spineError(e));
      setV(null);          // unknown, not empty
    } finally {
      setLoading(false);
    }
  }, []);

  // Deliberately NOT polled, and cached server-side for 30 minutes. This reads a
  // year of market history per holding and replays five crisis windows; on a
  // timer it would hammer the data source for a page nobody watches by the
  // second. The cache is keyed on the book itself, so a fill invalidates it
  // immediately — only idle refreshes are served from it.
  useEffect(() => { load(false); }, [load]);

  const corr = v?.correlation;
  const rc = v?.risk_contribution;
  const tail = v?.tail;
  const es = tail?.levels?.["0.975"];

  return (
    <div className={KT.page}>
      <StudioHeader
        subtitle="Structural risk — diversification, tails, regime and survivability"
        actions={
          <div className="flex items-center gap-3">
            {v?.computed_at && (
              <span className={`text-[11px] ${KT.muted}`}>
                {v.cached
                  ? `cached · computed ${fmtAge(v.cache_age_seconds)} ago`
                  : "computed just now"}
              </span>
            )}
            <button onClick={() => load(true)} disabled={loading}
                    className={`flex h-8 items-center ${KT.btnGhost}`}>
              {loading ? <Loader2 size={14} className="mr-1.5 animate-spin" /> : <RefreshCw size={14} className="mr-1.5" />}
              Recompute
            </button>
          </div>
        }
      />

      <div className="mx-auto max-w-[1600px] space-y-6 px-6 py-6">
        {err && <div className={`p-3 text-sm ${KT.inset} ${KT.down}`}>{err}</div>}

        {loading && !v && (
          <div className={`flex items-center gap-2 p-10 text-sm ${KT.muted}`}>
            <Loader2 size={14} className="animate-spin" />
            Measuring correlation, tails and market regime — this reads a year of history.
          </div>
        )}

        {v && (
          <>
            {/* --- what a person should read first --- */}
            {v.headlines?.length > 0 && (
              <div className={`${KT.card} space-y-2`}>
                {v.headlines.map((h, i) => (
                  <p key={i} className="text-sm text-[var(--kt-text)]">{h}</p>
                ))}
              </div>
            )}

            {v.alarms?.length > 0 && (
              <div className="space-y-2">
                {v.alarms.map((a) => (
                  <div key={a.key} className={`flex gap-2 rounded-xl border p-3 text-sm ${SEV_TONE[a.severity] ?? SEV_TONE.info}`}>
                    <AlertTriangle size={15} className="mt-0.5 shrink-0" />
                    <span>{a.message}</span>
                  </div>
                ))}
              </div>
            )}

            {/* --- headline structural numbers --- */}
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <div className={KT.card}>
                <div className={KT.label}>Effective bets</div>
                <div className={`mt-1 ${KT.numberLg}`}>
                  {corr?.measurable ? corr.effective_bets.toFixed(1) : "—"}
                </div>
                <div className={`mt-1 text-[11px] ${KT.muted}`}>
                  {corr?.measurable ? `from ${corr.n_positions} positions` : "unmeasured"}
                </div>
              </div>
              <div className={KT.card}>
                <div className={KT.label}>Book volatility</div>
                <div className={`mt-1 ${KT.numberLg}`}>
                  {corr?.measurable ? pct(corr.portfolio_vol_pct) : "—"}
                </div>
                <div className={`mt-1 text-[11px] ${KT.muted}`}>
                  {corr?.measurable ? `${pct(corr.stressed_vol_pct)} if correlations → 1` : "unmeasured"}
                </div>
              </div>
              <div className={KT.card}>
                <div className={KT.label}>Expected shortfall 97.5%</div>
                <div className={`mt-1 ${KT.numberLg}`}>
                  {es ? pct(es.expected_shortfall_pct, 2) : "—"}
                </div>
                <div className={`mt-1 text-[11px] ${KT.muted}`}>
                  {es ? `${money(es.expected_shortfall_usd)} on a bad day` : "unmeasured"}
                </div>
              </div>
              <div className={KT.card}>
                <div className={KT.label}>Move to halt</div>
                <div className={`mt-1 ${KT.numberLg}`}>
                  {v.reverse_stress?.measurable ? pct(v.reverse_stress.uniform_move_to_halt_pct) : "—"}
                </div>
                <div className={`mt-1 text-[11px] ${KT.muted}`}>
                  {v.reverse_stress?.measurable
                    ? `${money(v.reverse_stress.loss_to_halt_usd)} of loss`
                    : v.reverse_stress?.reason ?? "unmeasured"}
                </div>
              </div>
            </div>

            {/* --- the surface --- */}
            <Panel
              title="Loss surface"
              subtitle="Expected shortfall as correlation and holding period vary — drag to rotate"
            >
              <div className="px-3 py-3">
                <LossSurface surface={v.loss_surface} />
              </div>
            </Panel>

            {/* --- is this alpha, or beta we already own? --- */}
            <div className="grid gap-6 lg:grid-cols-2">
              <Panel
                title="Factor exposure"
                subtitle="What the book is actually exposed to, regressed on tradeable proxies"
              >
                {!v.factor_model?.measurable ? (
                  <NotMeasurable reason={v.factor_model?.reason} />
                ) : (
                  <>
                    <div className="grid grid-cols-3 gap-3 px-5 pt-4">
                      <div>
                        <div className={KT.label}>Alpha (ann.)</div>
                        <div className={`mt-1 font-mono text-lg font-light ${
                          v.factor_model.alpha_significant
                            ? ((v.factor_model.alpha_annual_pct ?? 0) > 0 ? KT.up : KT.down)
                            : KT.muted}`}>
                          {pct(v.factor_model.alpha_annual_pct, 1)}
                        </div>
                        <div className={`text-[11px] ${KT.muted}`}>
                          t {v.factor_model.alpha_t_stat?.toFixed(1)}
                          {v.factor_model.alpha_significant ? "" : " · not significant"}
                        </div>
                      </div>
                      <div>
                        <div className={KT.label}>R²</div>
                        <div className="mt-1 font-mono text-lg font-light">
                          {((v.factor_model.r_squared ?? 0) * 100).toFixed(0)}%
                        </div>
                        <div className={`text-[11px] ${KT.muted}`}>explained by factors</div>
                      </div>
                      <div>
                        <div className={KT.label}>Idiosyncratic</div>
                        <div className="mt-1 font-mono text-lg font-light">
                          {((v.factor_model.idiosyncratic_share ?? 0) * 100).toFixed(0)}%
                        </div>
                        <div className={`text-[11px] ${KT.muted}`}>genuinely ours</div>
                      </div>
                    </div>
                    <FactorBars rows={v.factor_model.factors ?? []} />
                    <div className={`space-y-1 border-t border-[var(--kt-border)] px-5 py-3 text-[11px] ${KT.muted}`}>
                      {(v.factor_model.verdict ?? []).map((l, i) => <p key={i}>· {l}</p>)}
                      {(v.factor_model.caveats ?? []).slice(0, 1).map((l, i) => <p key={`c${i}`}>· {l}</p>)}
                    </div>
                  </>
                )}
              </Panel>

              <Panel
                title="Factor map"
                subtitle="Holdings placed in the book's own latent factors — clusters are one bet"
              >
                <div className="px-3 py-3">
                  <FactorMap3D map={v.factor_map} />
                </div>
              </Panel>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              {/* --- risk vs capital --- */}
              <Panel
                title="Risk contribution"
                subtitle="Euler decomposition — capital weight is not risk weight"
              >
                {!rc?.measurable ? (
                  <NotMeasurable reason={rc?.reason} />
                ) : (
                  <div className="px-5 py-3">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className={KT.label}>
                          <th className="pb-2 text-left font-normal">Name</th>
                          <th className="pb-2 text-right font-normal">Capital</th>
                          <th className="pb-2 text-right font-normal">Risk</th>
                          <th className="pb-2 text-right font-normal">Gap</th>
                        </tr>
                      </thead>
                      <tbody className="font-mono tabular-nums">
                        {(rc.contributions ?? []).map((r) => (
                          <tr key={r.symbol} className="border-t border-[var(--kt-border)]">
                            <td className="py-1.5 font-sans font-medium">{r.symbol}</td>
                            <td className="py-1.5 text-right text-[var(--kt-text-dim)]">
                              {pct(r.capital_weight_pct)}
                            </td>
                            <td className="py-1.5 text-right">{pct(r.risk_share_pct)}</td>
                            <td className={`py-1.5 text-right ${
                              r.risk_vs_capital_gap_pct > 10 ? KT.down
                                : r.risk_vs_capital_gap_pct < -5 ? KT.up : KT.muted}`}>
                              {r.risk_vs_capital_gap_pct > 0 ? "+" : ""}
                              {r.risk_vs_capital_gap_pct.toFixed(1)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className={`mt-3 text-[11px] ${KT.muted}`}>
                      Components sum exactly to book volatility (residual{" "}
                      {rc.decomposition_residual?.toExponential(1) ?? "—"}). A negative
                      risk share means the name is hedging the rest of the book.
                    </p>
                  </div>
                )}
              </Panel>

              {/* --- correlation --- */}
              <Panel
                title="Correlation"
                subtitle={corr?.measurable
                  ? `${corr.n_obs} trading days to ${corr.window_end}`
                  : undefined}
              >
                {!corr?.measurable
                  ? <NotMeasurable reason={corr?.reason} />
                  : <CorrelationGrid symbols={corr.symbols} matrix={corr.matrix} />}
              </Panel>
            </div>

            {/* --- are the strategies actually different --- */}
            <Panel
              title="Strategy independence"
              subtitle="Different tickers that move together are still one bet"
            >
              {!corr?.strategy_overlap?.measurable ? (
                <NotMeasurable reason={corr?.strategy_overlap?.reason} />
              ) : (
                <ul className="divide-y divide-[var(--kt-border)]">
                  {(corr.strategy_overlap.pairs ?? []).map((p) => (
                    <li key={`${p.a}-${p.b}`} className="flex flex-wrap items-baseline gap-x-3 px-5 py-3 text-sm">
                      <span className="font-medium">{p.a_name}</span>
                      <span className={KT.muted}>vs</span>
                      <span className="font-medium">{p.b_name}</span>
                      <span className={`ml-auto font-mono tabular-nums ${
                        (p.return_correlation ?? 0) > 0.8 ? KT.down
                          : (p.return_correlation ?? 0) > 0.5 ? "text-[var(--kt-warn)]" : KT.up}`}>
                        {p.return_correlation == null ? "—" : p.return_correlation.toFixed(2)}
                      </span>
                      <span className={`w-full text-[11px] ${KT.muted}`}>
                        {p.shared_exposure_pct.toFixed(0)}% shared exposure
                        {p.shared_symbols.length > 0 && ` (${p.shared_symbols.join(", ")})`}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            {/* --- would we survive --- */}
            <Panel
              title="Historical survivability"
              subtitle="Real returns from real crises applied to today's exact book"
            >
              {!v.historical?.measurable ? (
                <NotMeasurable reason={v.historical?.reason} />
              ) : (
                <ul className="divide-y divide-[var(--kt-border)]">
                  {(v.historical.scenarios ?? []).map((s) => (
                    <li key={s.key} className="px-5 py-3 text-sm">
                      {!s.measurable ? (
                        <div className={KT.sev.warn}>{s.label} — not measurable: {s.reason}</div>
                      ) : (
                        <>
                          <div className="flex flex-wrap items-baseline gap-x-3">
                            <span className="font-medium">{s.label}</span>
                            <span className={`text-[11px] ${KT.muted}`}>{s.start} → {s.end}</span>
                            <span className={`ml-auto font-mono tabular-nums ${KT.down}`}>
                              {pct(s.nav_change_pct, 1)}
                            </span>
                            <span className={`w-20 text-right font-mono tabular-nums ${KT.down}`}>
                              {money(s.pnl_usd)}
                            </span>
                          </div>
                          <div className={`mt-1 text-[11px] ${KT.muted}`}>
                            {s.note}. Worst name {s.worst_name?.symbol}{" "}
                            ({pct(s.worst_name?.return_pct, 1)}). {s.caveat}
                          </div>
                        </>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <div className="grid gap-6 lg:grid-cols-2">
              {/* --- market regime --- */}
              <Panel
                title="Market regime"
                subtitle="The market, not this book — measured on sector ETFs"
              >
                {!v.regime?.measurable ? (
                  <NotMeasurable reason={v.regime?.reason} />
                ) : (
                  <div className="space-y-3 px-5 py-4 text-sm">
                    <div>
                      <div className="flex items-baseline justify-between">
                        <span className={KT.label}>Turbulence</span>
                        <span className={`font-mono tabular-nums ${
                          v.regime.turbulence?.elevated ? KT.down : KT.muted}`}>
                          {v.regime.turbulence?.percentile != null
                            ? `${v.regime.turbulence.percentile.toFixed(0)}th pct` : "—"}
                        </span>
                      </div>
                      <p className={`mt-1 text-[11px] ${KT.muted}`}>
                        {v.regime.turbulence?.verdict ?? v.regime.turbulence?.reason}
                      </p>
                    </div>
                    <div className="border-t border-[var(--kt-border)] pt-3">
                      <div className="flex items-baseline justify-between">
                        <span className={KT.label}>Absorption ratio</span>
                        <span className={`font-mono tabular-nums ${
                          v.regime.absorption?.flagged ? KT.down : KT.muted}`}>
                          {v.regime.absorption?.current != null
                            ? `${(v.regime.absorption.current * 100).toFixed(0)}%` : "—"}
                          {v.regime.absorption?.standardised_shift != null &&
                            ` (${v.regime.absorption.standardised_shift > 0 ? "+" : ""}${v.regime.absorption.standardised_shift.toFixed(2)}σ)`}
                        </span>
                      </div>
                      <p className={`mt-1 text-[11px] ${KT.muted}`}>
                        {v.regime.absorption?.verdict ?? v.regime.absorption?.reason}
                      </p>
                    </div>
                    {(v.regime.interpretation ?? []).slice(-1).map((line, i) => (
                      <p key={i} className={`border-t border-[var(--kt-border)] pt-3 text-[11px] ${KT.muted}`}>
                        {line}
                      </p>
                    ))}
                  </div>
                )}
              </Panel>

              {/* --- tail + vol regime --- */}
              <Panel title="Tail & volatility regime" subtitle="Measured, not assumed normal">
                {!tail?.measurable ? (
                  <NotMeasurable reason={tail?.reason} />
                ) : (
                  <div className="space-y-3 px-5 py-4 text-sm">
                    <div className="grid grid-cols-2 gap-3 font-mono tabular-nums">
                      {Object.entries(tail.levels ?? {}).map(([k, lv]) => (
                        <div key={k} className={KT.inset + " p-3"}>
                          <div className={KT.label}>{(lv.confidence * 100).toFixed(1)}% ES</div>
                          <div className="mt-1 text-lg font-light">{pct(lv.expected_shortfall_pct, 2)}</div>
                          <div className={`text-[11px] ${KT.muted}`}>
                            VaR {pct(lv.var_pct, 2)} · {lv.tail_observations} tail days
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className={`text-[11px] ${KT.muted}`}>
                      Worst observed day {pct(tail.worst_day_pct, 2)} ({money(tail.worst_day_usd)}),
                      worst 5-day {pct(tail.worst_5day_pct, 2)} ({money(tail.worst_5day_usd)}).
                    </div>
                    {v.vol_regime?.measurable && (
                      <div className={`border-t border-[var(--kt-border)] pt-3 text-[11px] ${KT.muted}`}>
                        EWMA vol {pct(v.vol_regime.ewma_vol_pct)} vs {pct(v.vol_regime.equal_weighted_vol_pct)}{" "}
                        equal-weighted — {v.vol_regime.verdict}.
                      </div>
                    )}
                    {(tail.caveats ?? []).map((c, i) => (
                      <p key={i} className={`text-[11px] ${KT.muted}`}>· {c}</p>
                    ))}
                  </div>
                )}
              </Panel>
            </div>

            {/* --- reverse stress detail --- */}
            <Panel
              title="Reverse stress"
              subtitle="Not 'what if -20%' but 'what would it take to halt us'"
            >
              {!v.reverse_stress?.measurable ? (
                <NotMeasurable reason={v.reverse_stress?.reason} />
              ) : (
                <div className="px-5 py-4 text-sm">
                  <p className="text-[var(--kt-text)]">{v.reverse_stress.headline}</p>
                  {v.reverse_stress.daily_headline && (
                    <p className={`mt-1 ${KT.muted}`}>{v.reverse_stress.daily_headline}</p>
                  )}
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(v.reverse_stress.single_name ?? []).map((n) => (
                      <span
                        key={n.symbol}
                        className={`rounded-lg border px-2 py-1 font-mono text-[11px] ${
                          n.possible
                            ? "border-[var(--kt-down)]/40 text-[var(--kt-down)]"
                            : `border-[var(--kt-border)] ${KT.muted}`
                        }`}
                        title={n.possible
                          ? `${n.symbol} alone could breach the halt`
                          : `${n.symbol} could go to zero without breaching the halt`}
                      >
                        {n.symbol} {n.move_to_halt_pct == null ? "—" : `${n.move_to_halt_pct.toFixed(0)}%`}
                      </span>
                    ))}
                  </div>
                  <p className={`mt-2 text-[11px] ${KT.muted}`}>{v.reverse_stress.single_name_note}</p>
                </div>
              )}
            </Panel>
          </>
        )}
      </div>
    </div>
  );
}
