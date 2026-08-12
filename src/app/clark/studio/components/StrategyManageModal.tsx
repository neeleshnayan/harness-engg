"use client";

import React, { useEffect, useState } from "react";
import { Archive, Loader2, Plus, X } from "lucide-react";
import { fundApiClient, StrategyView } from "@/lib/fund_api";

/** Clean CRUD desk for one strategy: rename, membership (many parents),
 *  lifecycle, allocation, archive. Built for actual fiddling. */
export function StrategyManageModal({
  strategy,
  all,
  onClose,
  onSuccess,
}: {
  strategy: StrategyView | null;
  all: StrategyView[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [name, setName] = useState("");
  const [alloc, setAlloc] = useState<number>(0);
  const [addParent, setAddParent] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (strategy) {
      setName(strategy.name);
      setAlloc(strategy.allocation_pct ?? 0);
      setErr(null);
    }
  }, [strategy]);

  if (!strategy) return null;
  const parents = strategy.parents ?? (strategy.parent_id ? [strategy.parent_id] : []);
  const nameOf = (id: string) => all.find((s) => s.strategy_id === id)?.name || id.slice(0, 8);
  const parentOptions = all.filter(
    (s) => s.strategy_id !== strategy.strategy_id && !parents.includes(s.strategy_id) && !s.archived,
  );

  const run = async (key: string, fn: () => Promise<unknown>, close = false) => {
    setBusy(key);
    setErr(null);
    try {
      await fn();
      onSuccess();
      if (close) onClose();
    } catch (e: unknown) {
      const d = e as { response?: { data?: { detail?: string } }; message?: string };
      setErr(d?.response?.data?.detail || d?.message || "Action failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border border-[var(--kt-border)] bg-[var(--kt-surface)] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[var(--kt-border)] px-4 py-3">
          <span className="text-sm font-semibold">Manage strategy</span>
          <button onClick={onClose} className="text-[var(--kt-text-muted)] hover:text-[var(--kt-text)]"><X size={16} /></button>
        </div>

        <div className="space-y-4 p-4">
          {err && <div className="rounded-md border border-red-800/50 bg-red-950/30 p-2 text-xs text-[var(--kt-down)]">{err}</div>}

          {/* rename */}
          <div>
            <label className="text-[10px] font-medium uppercase tracking-widest text-[var(--kt-text-muted)]">Name</label>
            <div className="mt-1 flex gap-2">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="min-w-0 flex-1 rounded-md border border-[var(--kt-border)] bg-[var(--kt-inset)] px-2.5 py-1.5 text-sm outline-none"
              />
              <button
                onClick={() => run("rename", () => fundApiClient.renameStrategy(strategy.strategy_id, name.trim()))}
                disabled={busy === "rename" || !name.trim() || name.trim() === strategy.name}
                className="rounded-md bg-teal-600 px-3 text-sm text-[var(--kt-text-strong)] hover:bg-teal-700 disabled:opacity-40"
              >
                {busy === "rename" ? <Loader2 size={14} className="animate-spin" /> : "Save"}
              </button>
            </div>
          </div>

          {/* membership — belongs to (many parents) */}
          <div>
            <label className="text-[10px] font-medium uppercase tracking-widest text-[var(--kt-text-muted)]">Belongs to (composes into)</label>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {parents.length === 0 && <span className="text-xs text-[var(--kt-text-muted)]">Standalone — no parents.</span>}
              {parents.map((pid) => (
                <span key={pid} className="flex items-center gap-1 rounded-full border border-[var(--kt-border)] bg-[var(--kt-inset)] px-2 py-0.5 text-xs text-[var(--kt-text)]">
                  {nameOf(pid)}
                  <button
                    onClick={() => run("rm-" + pid, () => fundApiClient.removeStrategyParent(strategy.strategy_id, pid))}
                    className="text-[var(--kt-text-muted)] hover:text-[var(--kt-down)]"
                  >
                    <X size={11} />
                  </button>
                </span>
              ))}
            </div>
            {parentOptions.length > 0 && (
              <div className="mt-2 flex gap-2">
                <select
                  value={addParent}
                  onChange={(e) => setAddParent(e.target.value)}
                  className="min-w-0 flex-1 rounded-md border border-[var(--kt-border)] bg-[var(--kt-inset)] px-2 py-1.5 text-sm outline-none"
                >
                  <option value="">Add a parent…</option>
                  {parentOptions.map((s) => (
                    <option key={s.strategy_id} value={s.strategy_id}>{s.name}</option>
                  ))}
                </select>
                <button
                  onClick={() => addParent && run("add", () => fundApiClient.addStrategyParent(strategy.strategy_id, addParent)).then(() => setAddParent(""))}
                  disabled={busy === "add" || !addParent}
                  className="flex items-center gap-1 rounded-md border border-[var(--kt-border)] px-2.5 text-sm text-[var(--kt-text)] hover:bg-[var(--kt-inset)] disabled:opacity-40"
                >
                  <Plus size={13} /> Add
                </button>
              </div>
            )}
          </div>

          {/* lifecycle + allocation */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-medium uppercase tracking-widest text-[var(--kt-text-muted)]">Lifecycle</label>
              <div className="mt-1 flex gap-1.5">
                {strategy.state !== "deployed" ? (
                  <button
                    onClick={() => run("deploy", () => fundApiClient.setState(strategy.strategy_id, "deployed"))}
                    disabled={busy === "deploy"}
                    className="flex-1 rounded-md bg-teal-600/90 px-2 py-1.5 text-xs text-[var(--kt-text-strong)] hover:bg-teal-600"
                  >
                    Deploy
                  </button>
                ) : (
                  <button
                    onClick={() => run("pause", () => fundApiClient.setState(strategy.strategy_id, "paused"))}
                    disabled={busy === "pause"}
                    className="flex-1 rounded-md border border-amber-700/50 px-2 py-1.5 text-xs text-[var(--kt-warn)] hover:bg-amber-900/20"
                  >
                    Pause
                  </button>
                )}
              </div>
            </div>
            <div>
              <label className="text-[10px] font-medium uppercase tracking-widest text-[var(--kt-text-muted)]">Target %</label>
              <div className="mt-1 flex gap-1.5">
                <input
                  type="number"
                  value={alloc}
                  onChange={(e) => setAlloc(Number(e.target.value))}
                  className="w-16 rounded-md border border-[var(--kt-border)] bg-[var(--kt-inset)] px-2 py-1.5 text-right font-mono text-sm outline-none"
                />
                <button
                  onClick={() => run("alloc", () => fundApiClient.setAllocation(strategy.strategy_id, alloc))}
                  disabled={busy === "alloc"}
                  className="flex-1 rounded-md border border-[var(--kt-border)] px-2 text-xs text-[var(--kt-text)] hover:bg-[var(--kt-inset)]"
                >
                  Set
                </button>
              </div>
            </div>
          </div>

          {/* danger */}
          <div className="border-t border-[var(--kt-border)] pt-3">
            <button
              onClick={() => run("archive", () => fundApiClient.archiveStrategy(strategy.strategy_id), true)}
              disabled={busy === "archive"}
              className="flex items-center gap-1.5 text-xs text-[var(--kt-down)]/80 hover:text-[var(--kt-down)]"
            >
              <Archive size={13} /> Archive strategy
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
