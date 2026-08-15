"use client";

import React, { useCallback, useEffect, useState } from "react";
import { KT } from "../theme";
import {
  MemoView, Postmortem, ThesisStatus, ThesisView, fundApiClient,
} from "@/lib/fund_api";

/**
 * Theses and memos, on the page where ideas are worked out.
 *
 * The whole pipeline existed end-to-end except the screen: the spine versions
 * theses, ties orders to them, stores memos and records postmortems; the API
 * client had every method typed — and none of it was reachable without curl.
 * The nav comment has said "theses, memos … live on Lab" since the Decide tab
 * was dissolved; this is that sentence finally being true.
 *
 * The design position: a thesis is the WHY behind trades. An order card
 * already links a thesis_id; this desk is where that id resolves to a claim a
 * human wrote, the memos arguing it, and — once it is over — the postmortem
 * saying whether it was right. Nothing here invents numbers: P&L lives on the
 * postmortem the spine computed, not on anything derived client-side.
 *
 * Status is text, not colour-coded chips. Five statuses would need five hues,
 * and the palette holds exactly one loud colour by design. `invalidated` gets
 * the down colour because it is the one status that is a live warning — the
 * fund holds positions whose reason has died.
 */

const STATUS_NEXT: Record<ThesisStatus, ThesisStatus[]> = {
  draft: ["active"],
  active: ["invalidated", "exited"],
  invalidated: ["exited"],
  exited: ["reviewed"],
  reviewed: [],
};

function StatusMark({ s }: { s: ThesisStatus }) {
  return (
    <span
      className={`font-mono text-[10px] uppercase tracking-[0.14em] ${
        s === "invalidated" ? "text-[var(--kt-down)]"
        : s === "active" ? "text-[var(--kt-text)]"
        : "text-[var(--kt-text-muted)]"
      }`}
    >
      {s}
    </span>
  );
}

function ThesisRow({ t, onChanged }: { t: ThesisView; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  const [memos, setMemos] = useState<MemoView[] | null>(null);
  const [pm, setPm] = useState<Postmortem | null>(null);
  const [busy, setBusy] = useState(false);

  const expand = useCallback(async () => {
    setOpen((o) => !o);
    if (memos === null) {
      const m = await fundApiClient.getThesisMemos(t.thesis_id).catch(() => ({ memos: [] }));
      setMemos(m.memos);
      if (t.has_postmortem) {
        setPm(await fundApiClient.getPostmortem(t.thesis_id).catch(() => null));
      }
    }
  }, [memos, t.thesis_id, t.has_postmortem]);

  const advance = useCallback(async (next: ThesisStatus) => {
    setBusy(true);
    try {
      await fundApiClient.setThesisStatus(t.thesis_id, next);
      onChanged();
    } finally {
      setBusy(false);
    }
  }, [t.thesis_id, onChanged]);

  return (
    <div className="border-t border-[var(--kt-border)] first:border-t-0">
      <button
        type="button"
        onClick={expand}
        className="flex w-full items-baseline gap-3 px-4 py-2.5 text-left transition-colors hover:bg-[var(--kt-hover)]"
        aria-expanded={open}
      >
        <StatusMark s={t.status} />
        <span className="min-w-0 flex-1 truncate text-sm text-[var(--kt-text)]">{t.title}</span>
        {t.assets && t.assets.length > 0 && (
          <span className="font-mono text-[11px] text-[var(--kt-text-muted)]">
            {t.assets.join(" ")}
          </span>
        )}
        <span className="font-mono text-[11px] tabular-nums text-[var(--kt-text-muted)]">
          {(t.memo_ids?.length ?? 0)}m · {(t.order_ids?.length ?? 0)}o
        </span>
      </button>

      {open && (
        <div className="border-t border-[var(--kt-border)] bg-[var(--kt-inset)] px-4 py-3">
          {t.claim && <p className={`mb-2 max-w-[70ch] text-[13px] ${KT.body}`}>{t.claim}</p>}

          {(t.invalidation_conditions?.length ?? 0) > 0 && (
            <div className="mb-2">
              <div className={KT.label}>Invalidation</div>
              <ul className="mt-1 space-y-0.5">
                {t.invalidation_conditions!.map((c, i) => (
                  <li key={i} className="text-[12px] text-[var(--kt-text-dim)]">— {c}</li>
                ))}
              </ul>
            </div>
          )}

          {memos && memos.length > 0 && (
            <div className="mb-2">
              <div className={KT.label}>Memos</div>
              <ul className="mt-1 space-y-1">
                {memos.map((m) => (
                  <li key={m.memo_id} className="text-[12px] text-[var(--kt-text-dim)]">
                    <span className="text-[var(--kt-text)]">{m.title}</span>
                    {m.recommendation && <> — {m.recommendation}</>}
                    {m.conviction && (
                      <span className="font-mono text-[10px] uppercase text-[var(--kt-text-muted)]">
                        {" "}· {m.conviction} conviction · {m.status}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {pm && (
            <div className="mb-2">
              <div className={KT.label}>Postmortem</div>
              <p className="mt-1 text-[12px] text-[var(--kt-text-dim)]">
                <span className={pm.verdict === "correct" ? "text-[var(--kt-up)]"
                  : pm.verdict === "wrong" ? "text-[var(--kt-down)]"
                  : "text-[var(--kt-text)]"}>
                  {pm.verdict.replace("_", " ")}
                </span>
                {" · "}
                <span className="font-mono tabular-nums">
                  {pm.outcome_pnl_usd >= 0 ? "+" : "−"}${Math.abs(pm.outcome_pnl_usd).toFixed(2)}
                </span>
                {pm.what_happened && <> — {pm.what_happened}</>}
              </p>
            </div>
          )}

          {STATUS_NEXT[t.status].length > 0 && (
            <div className="mt-2 flex gap-2">
              {STATUS_NEXT[t.status].map((n) => (
                <button
                  key={n}
                  type="button"
                  disabled={busy}
                  onClick={() => advance(n)}
                  className={`${KT.btnGhost} text-xs disabled:opacity-50`}
                >
                  mark {n}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ThesisDesk() {
  const [theses, setTheses] = useState<ThesisView[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [claim, setClaim] = useState("");
  const [assets, setAssets] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    fundApiClient.getTheses()
      .then((r) => { setTheses(r.theses); setError(null); })
      .catch(() => setError("Theses unreadable — the spine did not answer."));
  }, []);

  useEffect(() => { load(); }, [load]);

  const create = useCallback(async () => {
    if (!title.trim()) return;
    setBusy(true);
    try {
      await fundApiClient.createThesis({
        title: title.trim(),
        claim: claim.trim() || undefined,
        assets: assets.trim() ? assets.trim().toUpperCase().split(/[\s,]+/) : undefined,
      });
      setTitle(""); setClaim(""); setAssets(""); setCreating(false);
      load();
    } catch {
      setError("Create failed — nothing was recorded.");
    } finally {
      setBusy(false);
    }
  }, [title, claim, assets, load]);

  // Live ideas first; the shelf of reviewed ones last.
  const ORDER: ThesisStatus[] = ["active", "invalidated", "draft", "exited", "reviewed"];
  const sorted = [...(theses ?? [])].sort(
    (a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status),
  );

  return (
    <div className={KT.panel}>
      <div className="flex items-center justify-between border-b border-[var(--kt-border)] px-4 py-2.5">
        <span className={KT.label}>Theses — why the fund holds what it holds</span>
        <button type="button" onClick={() => setCreating((c) => !c)} className={`${KT.btnGhost} text-xs`}>
          {creating ? "Cancel" : "New thesis"}
        </button>
      </div>

      {creating && (
        <div className="space-y-2 border-b border-[var(--kt-border)] bg-[var(--kt-inset)] px-4 py-3">
          <input
            className={`${KT.input} w-full`}
            placeholder="Title — one sentence naming the idea"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={140}
          />
          <textarea
            className={`${KT.input} min-h-[64px] w-full resize-y`}
            placeholder="Claim — what must be true for this trade to work"
            value={claim}
            onChange={(e) => setClaim(e.target.value)}
          />
          <div className="flex items-center gap-2">
            <input
              className={`${KT.input} flex-1`}
              placeholder="Assets (e.g. NVDA MSFT)"
              value={assets}
              onChange={(e) => setAssets(e.target.value)}
            />
            <button
              type="button"
              onClick={create}
              disabled={busy || !title.trim()}
              className={`${KT.btn} disabled:opacity-50`}
            >
              Record thesis
            </button>
          </div>
        </div>
      )}

      {error && (
        <p className="px-4 py-3 text-[12px] text-[var(--kt-down)]">{error}</p>
      )}

      {theses === null && !error && (
        <p className={`px-4 py-6 text-center text-[12px] ${KT.muted}`}>Reading theses…</p>
      )}

      {theses !== null && theses.length === 0 && (
        <p className={`px-4 py-6 text-[12px] ${KT.muted}`}>
          No theses recorded. Every order can carry a thesis_id — an order without
          one is a trade whose reason lives in somebody&apos;s head.
        </p>
      )}

      {sorted.map((t) => (
        <ThesisRow key={t.thesis_id} t={t} onChanged={load} />
      ))}
    </div>
  );
}
