"use client";

import React, { useCallback, useEffect, useState } from "react";
import { ExternalLink, Loader2 } from "lucide-react";
import { KT } from "../theme";
import { fundApi } from "@/lib/fund_api";

/**
 * The rung between a ticker and understanding.
 *
 * The map used to end at a row of ticker chips, which is a dead end dressed as a
 * result: a symbol tells a reader nothing, so the honest next click was "go read
 * a 10-Q yourself". The thing that actually makes a name comprehensible in one
 * pass is the SENTENCE the filing used — so that is what this shows, verbatim,
 * next to a link to the document it came from.
 *
 * Quote first, paraphrase second. The summary is a model's words and could be
 * wrong; the quote is the company's own and can be checked in the source in one
 * click. Putting the checkable thing in the primary position is the difference
 * between evidence and assertion.
 *
 * Then exactly two actions, both one click and no typing:
 *
 *   - A JUDGEMENT. Under a laziness assumption, a dismissal and an unread are
 *     indistinguishable — both are simply absent — so a dismissal has to be
 *     declared to exist at all. Declared, it can be revisited and shows up in
 *     the legend as a choice somebody made; inferred, it hardens into a silent
 *     blind spot.
 *   - TAKE IT TO THE LAB, carrying the observation_id. This is the link the
 *     provenance report needs. Without it "does the liquidity region actually
 *     pay?" is unanswerable in principle, no matter how many candidates run —
 *     which is exactly the state the fund was in until this existed.
 */

interface Observation {
  observation_id: string;
  ticker: string;
  form: string;
  filed: string;
  url: string;
  category: string;
  observation: string;
  quote: string | null;
  reviewed: string | null;
  read_partial_filing?: boolean;
}

const OUTCOMES: { key: string; label: string }[] = [
  { key: "interesting", label: "Worth a look" },
  { key: "not_relevant", label: "Not relevant" },
];

export function Evidence({
  ticker,
  category,
  onTakeToLab,
}: {
  ticker: string;
  category?: string | null;
  onTakeToLab?: (ticker: string, observationIds: string[]) => void;
}) {
  const [rows, setRows] = useState<Observation[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      const params = new URLSearchParams({ ticker, limit: "12" });
      if (category) params.set("category", category);
      const r = await fundApi.get(`/api/v1/fund/research/observations?${params}`);
      setRows((r.data.observations ?? []) as Observation[]);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setErr(detail ?? String(e));
    } finally {
      setBusy(false);
    }
  }, [ticker, category]);

  useEffect(() => { load(); }, [load]);

  const review = async (id: string, outcome: string) => {
    setSaving(id);
    try {
      await fundApi.post(`/api/v1/fund/research/observations/${id}/review`, { outcome });
      // Reflect it locally rather than refetching: the reader is mid-scan and a
      // full reload would move the list under them.
      setRows((prev) =>
        (prev ?? []).map((o) => (o.observation_id === id ? { ...o, reviewed: outcome } : o)),
      );
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setErr(detail ?? String(e));
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className={`mt-2 ${KT.inset} p-3`}>
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="font-mono text-[12px] font-semibold">{ticker}</span>
        <span className={KT.label}>
          {category ? category.replace(/_/g, " ") : "what the filings said"}
        </span>
        {busy && <Loader2 size={12} className="animate-spin" />}
        <button onClick={() => onTakeToLab?.(ticker, (rows ?? []).map((o) => o.observation_id))}
                disabled={!rows?.length}
                className={`ml-auto h-7 ${KT.btnGhost} px-2 text-[11px] disabled:opacity-40`}>
          Take to Lab
        </button>
      </div>

      {err && <div className={`mt-2 text-[11px] ${KT.down}`}>{err}</div>}

      {rows && rows.length === 0 && (
        <p className={`mt-2 text-[11px] ${KT.muted}`}>
          Nothing has been read for {ticker} yet — which is a gap in our reading,
          not a statement about the company.
        </p>
      )}

      <div className="mt-2 flex flex-col gap-2">
        {(rows ?? []).map((o) => (
          <div key={o.observation_id}
               className="rounded-lg border border-[var(--kt-border)] bg-[var(--kt-surface)] p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className={KT.label}>{o.category.replace(/_/g, " ")}</span>
              <span className={`font-mono text-[10px] ${KT.muted}`}>
                {o.form} · {o.filed}
              </span>
              <a href={o.url} target="_blank" rel="noreferrer"
                 className={`flex items-center gap-1 text-[10px] ${KT.accent} hover:underline`}>
                source <ExternalLink size={10} />
              </a>
              {o.reviewed && (
                <span className={`ml-auto ${KT.chip} capitalize`}>
                  {o.reviewed.replace(/_/g, " ")}
                </span>
              )}
            </div>

            {/* The company's own words lead. They are what can be checked. */}
            {o.quote && (
              <blockquote className="mt-2 border-l-2 border-[var(--kt-accent-border)] pl-3 text-[12px] leading-relaxed text-[var(--kt-text)]">
                {o.quote}
              </blockquote>
            )}
            <p className={`mt-2 text-[11px] ${KT.muted}`}>{o.observation}</p>
            {o.read_partial_filing && (
              <p className={`mt-1 text-[10px] text-[var(--kt-warn)]`}>
                only part of this filing was read — absence of a finding here
                means less than usual
              </p>
            )}

            {!o.reviewed && (
              <div className="mt-2 flex gap-1.5">
                {OUTCOMES.map((x) => (
                  <button key={x.key}
                          onClick={() => review(o.observation_id, x.key)}
                          disabled={saving === o.observation_id}
                          className={`h-7 ${KT.btnGhost} px-2 text-[11px] disabled:opacity-40`}>
                    {x.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
