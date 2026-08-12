"use client";

import React, { useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { KT } from "../theme";

const AGENTS_URL =
  (process.env.NEXT_PUBLIC_AGENTS_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

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
    <div className={KT.card}>
      <div className={`mb-2.5 flex items-center gap-1.5 ${KT.label} ${KT.accent}`}>
        <Sparkles size={13} /> Ask Clark AI Copilot
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
          className={`min-w-0 flex-1 ${KT.input}`}
        />
        <button type="submit" disabled={busy} className={`flex h-9 items-center gap-1.5 ${KT.btn}`}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : "Send"}
        </button>
      </form>

      {suggestions.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button key={s} onClick={() => { setQ(s); ask(s); }} className={KT.chip}>
              {s}
            </button>
          ))}
        </div>
      )}

      {reply && (
        <div className={`mt-3 whitespace-pre-wrap p-3.5 text-xs ${KT.inset} ${KT.body}`}>
          {reply}
        </div>
      )}
    </div>
  );
}
