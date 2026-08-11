"use client";

import React, { useState } from "react";
import { Loader2, Sparkles } from "lucide-react";

const AGENTS_URL =
  (process.env.NEXT_PUBLIC_AGENTS_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

/** In-context Clark bar: ask Clark to reason/act on this page's domain. */
export function ClarkActionBar({
  placeholder,
  suggestions = [],
  onDone,
}: {
  placeholder: string;
  suggestions?: string[];
  onDone?: () => void;
}) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [reply, setReply] = useState<string | null>(null);

  const ask = async (text: string) => {
    const query = text.trim();
    if (!query) return;
    setBusy(true);
    setReply(null);
    try {
      const r = await fetch(`${AGENTS_URL}/api/v1/agents/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, username: "rushi", user_id: "rushi", include_search: false }),
      });
      const d = await r.json();
      setReply(d?.message || "(no response)");
      onDone?.();
    } catch {
      setReply("Could not reach Clark (is it running on :8000?).");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-teal-800/40 bg-[#0C152B]/90 p-3.5 shadow-lg backdrop-blur-md">
      <div className="mb-2 flex items-center gap-1.5 text-[11px] font-mono font-bold uppercase tracking-widest text-teal-400">
        <Sparkles size={13} className="text-teal-400 animate-pulse" /> Ask Clark AI Copilot
      </div>
      <form
        className="flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          ask(q);
        }}
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={placeholder}
          className="min-w-0 flex-1 rounded-lg border border-zinc-700/80 bg-zinc-950 px-3.5 py-2 text-xs font-mono text-white placeholder:text-zinc-500 outline-none focus:border-teal-500"
        />
        <button
          type="submit"
          disabled={busy}
          className="flex h-9 items-center gap-1.5 rounded-lg bg-gradient-to-r from-teal-500 to-emerald-500 px-4 text-xs font-mono font-bold text-zinc-950 disabled:opacity-50 cursor-pointer shadow-md"
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : "Send"}
        </button>
      </form>
      {suggestions.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5 font-mono">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => { setQ(s); ask(s); }}
              className="rounded-full border border-teal-800/50 bg-teal-950/60 px-2.5 py-0.5 text-[11px] font-bold text-teal-300 hover:bg-teal-900 hover:text-white cursor-pointer"
            >
              {s}
            </button>
          ))}
        </div>
      )}
      {reply && (
        <div className="mt-2.5 whitespace-pre-wrap rounded-lg border border-teal-700/50 bg-zinc-950 p-3 text-xs font-mono text-teal-200">
          {reply}
        </div>
      )}
    </div>
  );
}
