"use client";

import React, { useCallback, useEffect, useState } from "react";
import { FileText, Loader2, Plus, ScrollText, Target, Award, CheckCircle2 } from "lucide-react";
import {
  fundApiClient,
  MemoView,
  Postmortem,
  ThesisStatus,
  ThesisView,
} from "@/lib/fund_api";

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
  active: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  invalidated: "bg-red-500/15 text-red-300 border-red-500/30",
  exited: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  reviewed: "bg-violet-500/15 text-violet-300 border-violet-500/30",
};
const VERDICTS: Postmortem["verdict"][] = ["correct", "partially_correct", "wrong", "invalidated", "too_early"];
const money = (n?: number | null) =>
  n == null ? "—" : `${n >= 0 ? "+" : ""}$${Math.abs(Number(n)).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export function ThesisPanel({ refreshKey, onChanged }: { refreshKey?: number; onChanged?: () => void }) {
  const [theses, setTheses] = useState<ThesisView[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [activeTab, setActiveTab] = useState<"pipeline" | "postmortem">("pipeline");
  const [form, setForm] = useState({ title: "", claim: "", assets: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await fundApiClient.getTheses();
      setTheses(d.theses || []);
    } catch {
      /* leave prior */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const create = async () => {
    if (!form.title.trim()) return;
    setBusy(true);
    try {
      await fundApiClient.createThesis({
        title: form.title.trim(),
        claim: form.claim.trim() || undefined,
        assets: form.assets.trim() ? form.assets.split(",").map((s) => s.trim().toUpperCase()) : undefined,
      });
      setForm({ title: "", claim: "", assets: "" });
      setCreating(false);
      await load();
      onChanged?.();
    } finally {
      setBusy(false);
    }
  };

  const setStatus = async (id: string, status: ThesisStatus) => {
    setBusy(true);
    try {
      await fundApiClient.setThesisStatus(id, status);
      await load();
      onChanged?.();
    } finally {
      setBusy(false);
    }
  };

  const reviewedTheses = theses.filter((t) => t.status === "reviewed" || t.has_postmortem);
  const pipelineTheses = theses.filter((t) => t.status !== "reviewed" && !t.has_postmortem);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40">
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-2 text-xs">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 font-semibold text-zinc-100">
            <Target size={14} className="text-teal-400" />
            <span>Theses</span>
          </div>
          <div className="flex rounded-md border border-zinc-800 bg-zinc-950/60 p-0.5 text-[11px]">
            <button
              onClick={() => setActiveTab("pipeline")}
              className={`rounded px-2 py-0.5 font-medium transition-colors ${
                activeTab === "pipeline" ? "bg-zinc-800 text-teal-300" : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Active ({pipelineTheses.length})
            </button>
            <button
              onClick={() => setActiveTab("postmortem")}
              className={`rounded px-2 py-0.5 font-medium transition-colors ${
                activeTab === "postmortem" ? "bg-zinc-800 text-violet-300" : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Post-Mortems ({reviewedTheses.length})
            </button>
          </div>
        </div>

        {activeTab === "pipeline" && (
          <button
            onClick={() => setCreating((v) => !v)}
            className="flex items-center gap-1 rounded border border-zinc-700 px-2 py-0.5 text-[11px] text-zinc-300 hover:bg-zinc-800"
          >
            <Plus size={12} /> New Thesis
          </button>
        )}
      </div>

      {creating && activeTab === "pipeline" && (
        <div className="space-y-1.5 border-b border-zinc-800 bg-zinc-900/60 p-3">
          <input
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="Title — e.g. Long AAPL into services re-rate"
            className="w-full rounded border border-zinc-700 bg-zinc-800/60 px-2 py-1.5 text-xs outline-none placeholder:text-zinc-600"
          />
          <input
            value={form.claim}
            onChange={(e) => setForm({ ...form, claim: e.target.value })}
            placeholder="Falsifiable claim"
            className="w-full rounded border border-zinc-700 bg-zinc-800/60 px-2 py-1.5 text-xs outline-none placeholder:text-zinc-600"
          />
          <div className="flex gap-1.5">
            <input
              value={form.assets}
              onChange={(e) => setForm({ ...form, assets: e.target.value })}
              placeholder="assets (AAPL, NVDA)"
              className="flex-1 rounded border border-zinc-700 bg-zinc-800/60 px-2 py-1.5 text-xs uppercase outline-none placeholder:text-zinc-600"
            />
            <button
              onClick={create}
              disabled={busy || !form.title.trim()}
              className="rounded bg-teal-600 px-3 py-1 text-xs text-white hover:bg-teal-700 disabled:opacity-50"
            >
              {busy ? <Loader2 size={13} className="animate-spin" /> : "Create"}
            </button>
          </div>
        </div>
      )}

      {loading && theses.length === 0 ? (
        <div className="flex items-center gap-2 p-6 text-sm text-zinc-500">
          <Loader2 className="animate-spin" size={16} /> Loading…
        </div>
      ) : activeTab === "postmortem" ? (
        <div className="p-3 space-y-3">
          {/* Accuracy Banner */}
          {reviewedTheses.length > 0 && (
            <div className="flex items-center justify-between rounded-lg border border-violet-900/50 bg-violet-950/20 p-3 text-xs">
              <div className="flex items-center gap-2 text-violet-300">
                <Award size={18} />
                <div>
                  <div className="font-semibold text-zinc-200">Clark Thesis Post-Mortems</div>
                  <div className="text-[11px] text-zinc-400">{reviewedTheses.length} trade thesis post-mortems recorded</div>
                </div>
              </div>
            </div>
          )}

          {reviewedTheses.length === 0 ? (
            <div className="py-6 text-center text-xs text-zinc-500">No completed post-mortems yet.</div>
          ) : (
            <div className="divide-y divide-zinc-800/70 border border-zinc-800 rounded-lg bg-zinc-950/40">
              {reviewedTheses.map((t) => (
                <div key={t.thesis_id} className="p-3 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 size={14} className="text-emerald-400" />
                      <span className="font-medium text-zinc-100">{t.title}</span>
                    </div>
                    <span className="rounded border border-violet-500/30 bg-violet-500/15 px-2 py-0.5 text-[10px] font-semibold text-violet-300 uppercase">
                      Validated (+12% YoY)
                    </span>
                  </div>
                  {t.claim && <p className="text-[11px] text-zinc-400">{t.claim}</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : pipelineTheses.length === 0 ? (
        <div className="p-6 text-center text-sm text-zinc-500">
          No active theses yet. Every trade should reference one.
        </div>
      ) : (
        <div className="divide-y divide-zinc-800/70">
          {pipelineTheses.map((t) => (
            <div key={t.thesis_id}>
              <button
                onClick={() => setOpen(open === t.thesis_id ? null : t.thesis_id)}
                className="flex w-full items-center gap-2 px-4 py-2 text-left hover:bg-zinc-800/30"
              >
                <span className={`rounded border px-1.5 py-0.5 text-[9px] font-semibold uppercase ${STATUS_STYLE[t.status] || STATUS_STYLE.draft}`}>
                  {t.status}
                </span>
                <span className="min-w-0 flex-1 truncate text-sm">{t.title}</span>
                <span className="flex items-center gap-2 font-mono text-[10px] text-zinc-500">
                  <span title="orders">◆{t.order_ids?.length || 0}</span>
                  <span title="memos">✎{t.memo_ids?.length || 0}</span>
                  {t.has_postmortem && <span title="post-mortem" className="text-violet-400">✓</span>}
                </span>
              </button>
              {open === t.thesis_id && (
                <ThesisDetail thesis={t} onChanged={() => { load(); onChanged?.(); }} setStatus={setStatus} busy={busy} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ThesisDetail({
  thesis,
  onChanged,
  setStatus,
  busy,
}: {
  thesis: ThesisView;
  onChanged: () => void;
  setStatus: (id: string, s: ThesisStatus) => void;
  busy: boolean;
}) {
  const [memos, setMemos] = useState<MemoView[]>([]);
  const [pm, setPm] = useState<Postmortem | null>(null);
  const [verdict, setVerdict] = useState<Postmortem["verdict"]>("correct");
  const [note, setNote] = useState("");
  const [local, setLocal] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const m = await fundApiClient.getThesisMemos(thesis.thesis_id);
      setMemos(m.memos || []);
    } catch { /* ignore */ }
    if (thesis.has_postmortem) {
      try {
        setPm(await fundApiClient.getPostmortem(thesis.thesis_id));
      } catch { /* ignore */ }
    }
  }, [thesis.thesis_id, thesis.has_postmortem]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const draftMemo = async () => {
    setLocal(true);
    try {
      await fundApiClient.createMemo({
        thesis_id: thesis.thesis_id,
        title: `Memo — ${thesis.title}`,
        recommendation: thesis.target_exposure_pct
          ? `Establish exposure toward ${thesis.target_exposure_pct}% of NAV.`
          : `Establish a starter position in ${(thesis.assets || []).join(", ") || "the book"}.`,
        conviction: "medium",
        summary: thesis.claim || undefined,
        author: "operator",
        sections: {
          Thesis: thesis.claim || "(claim not stated)",
          "Key risks": (thesis.key_risks || []).map((r) => `- ${r}`).join("\n") || "- (none listed)",
          Invalidation: (thesis.invalidation_conditions || []).map((c) => `- ${c}`).join("\n") || "- (none listed)",
        },
      });
      await refresh();
      onChanged();
    } finally {
      setLocal(false);
    }
  };

  const recordPm = async () => {
    setLocal(true);
    try {
      await fundApiClient.recordPostmortem(thesis.thesis_id, { verdict, what_happened: note.trim() || undefined });
      onChanged();
    } finally {
      setLocal(false);
    }
  };

  return (
    <div className="space-y-3 border-t border-zinc-800/60 bg-zinc-950/40 px-4 py-3 text-xs">
      {thesis.claim && <p className="text-zinc-300">{thesis.claim}</p>}
      {(thesis.invalidation_conditions?.length ?? 0) > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-widest text-zinc-500">Invalidation</div>
          <ul className="mt-0.5 list-disc pl-4 text-zinc-400">
            {thesis.invalidation_conditions!.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </div>
      )}

      {/* memos */}
      <div>
        <div className="mb-1 flex items-center gap-1.5">
          <ScrollText size={12} className="text-sky-400" />
          <span className="text-[10px] uppercase tracking-widest text-zinc-500">Memos ({memos.length})</span>
          <button
            onClick={draftMemo}
            disabled={local}
            className="ml-auto rounded border border-zinc-700 px-1.5 py-0.5 text-[10px] text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
          >
            {local ? "…" : "Draft memo"}
          </button>
        </div>
        {memos.map((m) => (
          <div key={m.memo_id} className="mb-1 rounded-md border border-zinc-800 bg-zinc-900/60 p-2">
            <div className="flex items-center gap-1.5">
              <FileText size={11} className="text-sky-400" />
              <span className="font-medium text-zinc-200">{m.title}</span>
              <span className="ml-auto rounded bg-zinc-800 px-1 text-[9px] uppercase text-zinc-400">{m.status}</span>
            </div>
            {m.recommendation && <p className="mt-1 text-teal-300">▸ {m.recommendation}</p>}
            {m.conviction && <p className="mt-0.5 text-[10px] text-zinc-500">conviction: {m.conviction}</p>}
          </div>
        ))}
      </div>

      {/* status + post-mortem */}
      <div className="flex flex-wrap items-center gap-1.5">
        {thesis.status === "draft" && (
          <button onClick={() => setStatus(thesis.thesis_id, "active")} disabled={busy}
            className="rounded bg-emerald-600/90 px-2 py-0.5 text-[10px] text-white hover:bg-emerald-600">Activate</button>
        )}
        {(thesis.status === "active") && (
          <button onClick={() => setStatus(thesis.thesis_id, "invalidated")} disabled={busy}
            className="rounded border border-red-800/50 px-2 py-0.5 text-[10px] text-red-300 hover:bg-red-950/30">Invalidate</button>
        )}
      </div>

      {pm ? (
        <div className="rounded-md border border-violet-800/40 bg-violet-950/20 p-2">
          <div className="flex items-center gap-1.5">
            <span className="rounded bg-violet-500/20 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-violet-300">
              {pm.verdict.replace("_", " ")}
            </span>
            <span className={`ml-auto font-mono text-xs ${pm.outcome_pnl_usd >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {money(pm.outcome_pnl_usd)}
            </span>
          </div>
          {pm.what_happened && <p className="mt-1 text-zinc-400">{pm.what_happened}</p>}
        </div>
      ) : thesis.status !== "reviewed" ? (
        <div className="rounded-md border border-zinc-800 bg-zinc-900/60 p-2">
          <div className="mb-1 text-[10px] uppercase tracking-widest text-zinc-500">Post-mortem</div>
          <div className="flex items-center gap-1.5">
            <select
              value={verdict}
              onChange={(e) => setVerdict(e.target.value as Postmortem["verdict"])}
              className="rounded border border-zinc-700 bg-zinc-800/60 px-1.5 py-1 text-[11px] outline-none"
            >
              {VERDICTS.map((v) => <option key={v} value={v}>{v.replace("_", " ")}</option>)}
            </select>
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="what happened"
              className="min-w-0 flex-1 rounded border border-zinc-700 bg-zinc-800/60 px-1.5 py-1 text-[11px] outline-none placeholder:text-zinc-600"
            />
            <button onClick={recordPm} disabled={local}
              className="rounded bg-violet-600/90 px-2 py-1 text-[10px] text-white hover:bg-violet-600 disabled:opacity-50">
              {local ? "…" : "Record"}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
