"use client";

import React, { useState } from "react";
import { Loader2, Sparkles } from "lucide-react";

const AGENTS_URL =
  (process.env.NEXT_PUBLIC_AGENTS_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export function ClarkActionBar({
  placeholder,
  suggestions = [],
  onDone,
  theme = "dark",
}: {
  placeholder: string;
  suggestions?: string[];
  onDone?: () => void;
  theme?: "dark" | "light";
}) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [reply, setReply] = useState<string | null>(null);

  const isLight = theme === "light";

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
    <div className={`rounded-2xl border p-4 font-mono shadow-xl transition-all ${
      isLight
        ? "bg-[#FAF8F5] border-[#EAE5D9]"
        : "bg-[#090D18]/90 border-emerald-500/20 backdrop-blur-xl shadow-2xl"
    }`}>
      <div className={`mb-2.5 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest ${
        isLight ? "text-[#10B981]" : "text-emerald-400"
      }`}>
        <Sparkles size={13} className="animate-pulse" /> Ask Clark AI Copilot
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
          className={`min-w-0 flex-1 rounded-xl border px-4 py-2.5 text-xs font-mono outline-none transition ${
            isLight
              ? "bg-[#FFFFFF] border-[#D9D2C5] text-[#1E1E1E] placeholder:text-[#A8A29E] focus:border-[#10B981]"
              : "bg-[#040812] border-zinc-800 text-white placeholder:text-zinc-500 focus:border-emerald-500"
          }`}
        />
        <button
          type="submit"
          disabled={busy}
          className={`flex h-9 items-center gap-1.5 rounded-xl px-5 text-xs font-bold transition shadow-md cursor-pointer ${
            isLight
              ? "bg-[#10B981] hover:bg-[#059669] text-white"
              : "bg-gradient-to-r from-emerald-500 to-amber-500 text-zinc-950 hover:from-emerald-400 hover:to-amber-400"
          }`}
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : "Send"}
        </button>
      </form>

      {suggestions.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => { setQ(s); ask(s); }}
              className={`rounded-full border px-3 py-1 text-[11px] font-bold transition cursor-pointer ${
                isLight
                  ? "border-[#D9D2C5] bg-[#F0EBE1] text-[#10B981] hover:bg-[#E2DDD2]"
                  : "border-emerald-950/60 bg-emerald-950/40 text-emerald-300 hover:bg-emerald-900/60"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {reply && (
        <div className={`mt-3 whitespace-pre-wrap rounded-xl border p-3.5 text-xs font-mono ${
          isLight
            ? "border-[#EAE5D9] bg-[#F3EFE6] text-[#2D2B2A]"
            : "border-emerald-900/50 bg-[#040812] text-emerald-200"
        }`}>
          {reply}
        </div>
      )}
    </div>
  );
}
