"use client";

import React, { useState } from "react";
import { Loader2, Sparkles } from "lucide-react";

const AGENTS_URL =
  (process.env.NEXT_PUBLIC_AGENTS_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

/** In-context Clark bar: ask Clark to reason/act on this page's domain.
 *
 * Order proposals still land in the approval queue (human-gated); reads reply
 * inline. This is the seam for "integrate with Clark to take complex actions"
 * from each subpage. */
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
    <div className="rounded-xl border border-teal-800/40 bg-teal-950/10 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-widest text-teal-400/80">
        <Sparkles size={12} /> Ask Clark
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
          className="min-w-0 flex-1 rounded-md border border-zinc-700 bg-zinc-900/60 px-3 py-2 text-sm outline-none placeholder:text-zinc-600"
        />
        <button
          type="submit"
          disabled={busy}
          className="flex h-9 items-center gap-1.5 rounded-md bg-gradient-to-r from-teal-600 to-sky-600 px-3 text-sm text-white disabled:opacity-50"
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : "Send"}
        </button>
      </form>
      {suggestions.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => { setQ(s); ask(s); }}
              className="rounded-full border border-zinc-700 px-2 py-0.5 text-[11px] text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
            >
              {s}
            </button>
          ))}
        </div>
      )}
      {reply && (
        <div className="mt-2 whitespace-pre-wrap rounded-md border border-zinc-800 bg-zinc-900/60 p-2.5 text-sm text-zinc-300">
          {reply}
        </div>
      )}
    </div>
  );
}
