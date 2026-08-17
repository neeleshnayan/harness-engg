"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Compass, Loader2 } from "lucide-react";
import { KT } from "../theme";
import { fundApi } from "@/lib/fund_api";
import { Evidence } from "./Evidence";

/**
 * The map — where absence is visible.
 *
 * Not a ranked list. A ranking collapses many dimensions into one order, and
 * once collapsed you cannot see what was flattened; act on the top ten for a
 * month and the ranking's blind spots quietly become your own, with no signal
 * that anything is missing.
 *
 * A map preserves structure, and that single property does the work: an EMPTY
 * REGION IS VISIBLE. "We have read zero margin observations" is the most useful
 * sentence this view can produce, and a list would never have said it.
 *
 * Built on the assumption that the operator is lazy by default — which is not
 * an insult, it is a design constraint with a sharp consequence. A lazy reader
 * trusts the default view completely: they will not audit it, will not compare
 * it against the corpus, will not notice it drifting. So the default carries
 * nearly all the responsibility, and being HONEST here matters more than being
 * clever behind it. Hence extent before content, and the projection stated on
 * the face of the map rather than in a settings panel nobody opens.
 */

interface Region {
  category: string;
  count: number;
  tickers: string[];
  latest: string | null;
  share: number;
  empty: boolean;
}

interface MapData {
  extent: {
    filings_read: number;
    observations: number;
    tickers_read: number;
    tickers_available: number | null;
    coverage_pct: number | null;
    note: string;
  };
  projection: {
    filters: { filter: string; chosen: boolean; note: string }[];
    warnings: string[];
  };
  regions: Region[];
  tickers: { ticker: string; count: number; categories: string[] }[];
  totals: { observations: number; regions: number; empty_regions: number };
}

const label = (c: string) => c.replace(/_/g, " ");

export function ResearchMap({
  onPick,
}: {
  /** Carries the observation ids, so a candidate started from here arrives with
   *  its provenance attached rather than as an orphan hypothesis. */
  onPick?: (ticker: string, observationIds?: string[]) => void;
}) {
  const [data, setData] = useState<MapData | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      setData((await fundApi.get("/api/v1/fund/research/map")).data as MapData);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setErr(detail ?? String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const max = Math.max(1, ...(data?.regions ?? []).map((r) => r.count));

  return (
    <div className={`mt-6 ${KT.panel}`}>
      <div className="flex flex-wrap items-center gap-3 border-b border-[var(--kt-border)] px-5 py-3">
        <div className="min-w-0">
          <span className={KT.label}>The map</span>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            What has been read, what it said, and where nothing is.
          </div>
        </div>
        <button onClick={load} disabled={busy}
                className={`ml-auto flex h-9 items-center gap-1.5 ${KT.btnGhost} disabled:opacity-40`}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Compass size={14} />}
          Refresh
        </button>
      </div>

      {err && <div className={`px-5 py-3 text-sm ${KT.down}`}>{err}</div>}

      {data && (
        <>
          {/* Extent first, always. Arranging eleven observations beautifully
              says nothing about five thousand unopened names, and that is by
              far the largest empty region here. */}
          <div className="border-b border-[var(--kt-border)] px-5 py-4">
            <div className={KT.label}>Ground covered</div>
            <div className="mt-2 flex flex-wrap items-baseline gap-x-8 gap-y-1 font-mono tabular-nums">
              <span className="text-xl font-light">
                {data.extent.tickers_read}
                <span className={`ml-1 text-sm ${KT.muted}`}>
                  / {data.extent.tickers_available?.toLocaleString() ?? "?"} names
                </span>
              </span>
              <span className={`text-sm ${KT.muted}`}>
                {data.extent.observations} observations from {data.extent.filings_read} filings
              </span>
            </div>
            {data.extent.coverage_pct != null && (
              <div className="mt-3">
                <div className={KT.barTrack}>
                  <div className={KT.barFill}
                       style={{ width: `${Math.max(0.4, data.extent.coverage_pct)}%` }} />
                </div>
              </div>
            )}
            <p className={`mt-2 text-[11px] ${KT.muted}`}>{data.extent.note}</p>
          </div>

          {/* The terrain, drawn as territory rather than listed as rows.
              A bar chart ranks; a field of plots lets you SEE where the
              fund has been and where it has not, which is the whole reason
              this is a map. Empty regions keep their plot — dashed, unlit,
              and impossible to scroll past without noticing — because a
              list would simply have omitted them.

              Calm on purpose: one accent, weight and space doing the work.
              A heat-mapped rainbow would imply a precision that eleven
              observations per region cannot support. */}
          <div className="px-5 py-4">
            <div className="flex items-baseline gap-3">
              <div className={KT.label}>Regions</div>
              <div className={`text-[10px] ${KT.muted}`}>
                {data.totals.regions - data.totals.empty_regions} explored ·{" "}
                {data.totals.empty_regions} untouched
              </div>
            </div>

            <div className="mt-3 grid gap-2"
                 style={{ gridTemplateColumns: "repeat(auto-fill, minmax(158px, 1fr))" }}>
              {data.regions.map((r) => {
                const open_ = open === r.category;
                const fill = r.empty ? 0 : Math.max(6, (r.count / max) * 100);
                return (
                  <button
                    key={r.category}
                    onClick={() => {
                      setOpen(open_ ? null : r.category);
                      setPicked(null);
                    }}
                    disabled={r.empty}
                    className={`group relative overflow-hidden rounded-xl border p-3 text-left transition-all ${
                      r.empty
                        ? "cursor-default border-dashed border-[var(--kt-border)] opacity-50"
                        : open_
                          ? "border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)]"
                          : "border-[var(--kt-border)] hover:border-[var(--kt-border-strong)]"
                    }`}
                  >
                    <div className={`truncate text-[10px] font-mono uppercase tracking-[0.14em] ${KT.muted}`}>
                      {label(r.category)}
                    </div>
                    <div className="mt-2 flex items-baseline gap-1.5">
                      {r.empty ? (
                        <span className={`text-[11px] ${KT.muted}`}>unexplored</span>
                      ) : (
                        <>
                          <span className="font-mono tabular-nums text-2xl font-light text-[var(--kt-text-strong)]">
                            {r.count}
                          </span>
                          <span className={`text-[10px] ${KT.muted}`}>
                            {(r.share * 100).toFixed(0)}%
                          </span>
                        </>
                      )}
                    </div>
                    {/* How much of the read corpus this region accounts for —
                        the plot's "developed" edge. */}
                    <div className="mt-2 h-[3px] w-full rounded-full bg-[var(--kt-border)]">
                      <div className="h-full rounded-full bg-[var(--kt-accent)]"
                           style={{ width: `${fill}%` }} />
                    </div>
                    {!r.empty && (
                      <div className={`mt-2 truncate text-[10px] ${KT.muted}`}>
                        {r.tickers.length} name{r.tickers.length === 1 ? "" : "s"}
                        {r.latest ? ` · ${r.latest.slice(0, 10)}` : ""}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Drilling in is the point of a map: pick a region, see who is in
                it, and carry that name straight to the Lab. */}
            {open && (
              <div className={`mt-3 ${KT.inset} p-3`}>
                <div className="flex items-baseline gap-2">
                  <span className={KT.label}>{label(open)}</span>
                  <span className={`text-[10px] ${KT.muted}`}>
                    pick a name to read what its filing actually said
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {(data.regions.find((r) => r.category === open)?.tickers ?? []).map((t) => (
                    <button key={t}
                            onClick={() => setPicked(picked === t ? null : t)}
                            className={`cursor-pointer ${KT.chip} ${
                              picked === t ? "" : "hover:opacity-80"
                            }`}
                            style={picked === t
                              ? { outline: "1px solid var(--kt-accent)", outlineOffset: "1px" }
                              : undefined}>
                      {t}
                    </button>
                  ))}
                </div>

                {/* A ticker on its own is a dead end. What makes it legible is
                    the filing's own sentence, which is one click deeper — and
                    from there a judgement or a candidate, without typing. */}
                {picked && (
                  <Evidence ticker={picked} category={open}
                            onTakeToLab={(t, ids) => onPick?.(t, ids)} />
                )}
              </div>
            )}
          </div>

          {/* How the map distorts. On the face of it, not in a settings panel:
              a lazy reader never opens the panel, and a projection they cannot
              see is one they will read straight through. */}
          <div className="border-t border-[var(--kt-border)] px-5 py-4">
            <div className={KT.label}>Legend</div>
            <div className="mt-2 space-y-1.5">
              {data.projection.filters.map((f) => (
                <div key={f.filter} className="flex items-start gap-2 text-[11px]">
                  <span className={`mt-0.5 shrink-0 font-mono text-[9px] uppercase tracking-wider ${
                    f.chosen ? KT.muted : "text-[var(--kt-warn)]"}`}>
                    {f.chosen ? "chosen" : "unchosen"}
                  </span>
                  <span className={KT.muted}>
                    <span className="capitalize">{label(f.filter)}</span> — {f.note}
                  </span>
                </div>
              ))}
            </div>
            {data.projection.warnings.map((w, i) => (
              <p key={i} className={`mt-2 text-[11px] text-[var(--kt-warn)]`}>{w}</p>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
