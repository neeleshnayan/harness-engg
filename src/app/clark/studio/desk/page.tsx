"use client";

import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  Send,
  Skull,
  Swords,
  Users,
} from "lucide-react";
import { fundApiClient, DeskView } from "@/lib/fund_api";
import { KT } from "../theme";
import { StudioNav } from "../components/StudioNav";
import { RiskBar } from "../components/RiskBar";

/**
 * Desk — the firm that builds the fund, visible and triggerable.
 *
 * Three things, in the order the operator needs them:
 *
 *   1. REQUEST WORK — the triggerable part. A click writes a DESK_REQUESTED
 *      event, so the ask is a durable fact in the log rather than a toast that
 *      dies with the tab. The honesty line from the payload is rendered verbatim:
 *      the spine records requests, it does not run agents.
 *   2. THE ARTIFACT CHAIN — proposals and designs paired with the adversarial
 *      verdicts that killed or spared them. A killed artifact is rendered as a
 *      kill, prominently: at this firm a demonstrated kill is a WIN, and the UI
 *      should feel that way rather than apologise for it.
 *   3. THE BENCH — who exists, and the measured failure that justifies each seat.
 *
 * Everything comes from GET /fund/desk. Nothing here is hardcoded, including the
 * roster — the page renders whatever firm the constitution currently defines.
 */

const STATUS_CHIP: Record<string, string> = {
  killed: "border-transparent bg-[var(--kt-inset)] text-[var(--kt-down)]",
  survives:
    "border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] text-[var(--kt-accent)]",
  under_review: "border-transparent bg-[var(--kt-inset)] text-[var(--kt-warn)]",
};

export default function DeskPage() {
  const [d, setD] = useState<DeskView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ kind: "proposal", subject: "", note: "" });
  const [sent, setSent] = useState<string | null>(null);

  const load = async () => {
    try {
      const r = await fundApiClient.getDesk();
      setD(r);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "unreachable");
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, []);

  const submit = async () => {
    if (!form.subject.trim() || busy) return;
    setBusy(true);
    setSent(null);
    try {
      await fundApiClient.postDeskRequest(form);
      setSent(
        "Recorded to the event log. The CTO session picks it up from here.",
      );
      setForm({ ...form, subject: "", note: "" });
      await load();
    } catch (e) {
      setSent(`Failed: ${e instanceof Error ? e.message : "unreachable"}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <RiskBar />
      <div className={KT.container}>
        <header className="mb-7 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className={KT.label}>Krypton Fund · Research Desk</p>
            <h1 className="mt-1 flex items-center gap-2 text-2xl font-medium tracking-tight">
              <Swords size={22} className={KT.accent} />
              The firm that builds the fund
            </h1>
          </div>
          <StudioNav />
        </header>

        {err && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 text-[var(--kt-warn)]" />
            <p className="text-sm">Spine unreachable — showing nothing rather than a healthy desk. {err}</p>
          </div>
        )}
        {!d && !err && <p className={`text-sm ${KT.muted}`}>Reading the desk…</p>}

        {d && (
          <>
            {/* 1 — request work: the triggerable part */}
            <section className={`${KT.card} mb-8 border-[var(--kt-accent-border)]`}>
              <p className={`${KT.label} mb-3`}>Request work from the bench</p>
              <div className="flex flex-wrap items-end gap-3">
                <label className="flex flex-col gap-1">
                  <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                    kind
                  </span>
                  <select
                    value={form.kind}
                    onChange={(e) => setForm({ ...form, kind: e.target.value })}
                    className={KT.input}
                  >
                    <option value="proposal">proposal — mechanism</option>
                    <option value="thesis">thesis — analyst</option>
                    <option value="portfolio_review">portfolio review — pm</option>
                    <option value="attack">attack — adversary</option>
                    <option value="audit">audit — validator</option>
                    <option value="build">build — cto</option>
                  </select>
                </label>
                <label className="flex min-w-[16rem] flex-1 flex-col gap-1">
                  <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                    subject
                  </span>
                  <input
                    value={form.subject}
                    onChange={(e) => setForm({ ...form, subject: e.target.value })}
                    placeholder="what to propose on / attack / audit"
                    className={KT.input}
                  />
                </label>
                <button
                  type="button"
                  onClick={submit}
                  disabled={busy || !form.subject.trim()}
                  className={`${KT.btn} flex items-center gap-1.5 disabled:opacity-40`}
                >
                  <Send size={13} /> {busy ? "Recording…" : "Record request"}
                </button>
              </div>
              {sent && <p className={`mt-2 text-xs ${KT.muted}`}>{sent}</p>}
              <p className={`mt-3 text-xs italic leading-relaxed ${KT.muted}`}>
                {d.execution_note}
              </p>
            </section>

            {/* open requests */}
            {d.requests.filter((r) => r.status === "open").length > 0 && (
              <section className="mb-8">
                <p className={`${KT.label} mb-2`}>
                  Waiting for the CTO session ({d.open_requests})
                </p>
                <div className="space-y-1.5">
                  {d.requests
                    .filter((r) => r.status === "open")
                    .map((r) => (
                      <div key={r.request_id} className={`${KT.card} p-3 text-sm`}>
                        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--kt-warn)]">
                          {r.kind} → {r.serves}
                        </span>
                        <span className="ml-3">{r.subject}</span>
                        {r.note && (
                          <p className={`mt-1 text-xs ${KT.muted}`}>{r.note}</p>
                        )}
                      </div>
                    ))}
                </div>
              </section>
            )}

            {/* 2 — the artifact chain */}
            <section className="mb-8">
              <div className="mb-3 flex items-baseline justify-between gap-2">
                <p className={KT.label}>The artifact chain</p>
                <p className={`flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                  <Skull size={11} className="text-[var(--kt-down)]" />
                  {d.kills} kill{d.kills === 1 ? "" : "s"} — at this firm a
                  demonstrated kill is a win
                </p>
              </div>
              <div className="space-y-2">
                {d.artifacts.map((a) => (
                  <div
                    key={a.path}
                    className={`${KT.card} border-l-2 p-4 ${
                      a.status === "killed"
                        ? "border-l-[var(--kt-down)]"
                        : a.status === "survives"
                          ? "border-l-[var(--kt-accent)]"
                          : "border-l-[var(--kt-warn)]"
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                        {a.kind}
                      </span>
                      <span className="text-sm font-medium">{a.title}</span>
                      <span
                        className={`rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] ${STATUS_CHIP[a.status] ?? ""}`}
                      >
                        {a.status.replace("_", " ")}
                      </span>
                    </div>
                    <p className={`mt-1 font-mono text-[10px] ${KT.muted}`}>{a.path}</p>
                    {a.review && (
                      <p className={`mt-1.5 text-xs ${KT.muted}`}>
                        <span className="text-[var(--kt-down)]">
                          {a.review.verdict}
                        </span>{" "}
                        — {a.review.review_title}{" "}
                        <span className="font-mono text-[10px]">
                          ({a.review.review_path})
                        </span>
                      </p>
                    )}
                    {a.note && (
                      <p className={`mt-1.5 text-xs italic ${KT.muted}`}>{a.note}</p>
                    )}
                  </div>
                ))}
              </div>
            </section>

            {/* 3 — the bench */}
            <section className="mb-8">
              <p className={`${KT.label} mb-3 flex items-center gap-2`}>
                <Users size={12} /> The bench
              </p>
              <div className="grid gap-3 md:grid-cols-3">
                {d.roster.map((r) => (
                  <div key={r.agent} className={`${KT.card} p-4`}>
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-mono text-sm text-[var(--kt-accent)]">
                        {r.agent}
                      </p>
                      <span
                        className={`flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.1em] ${
                          r.activity.status === "working"
                            ? "text-[var(--kt-warn)]"
                            : KT.muted
                        }`}
                      >
                        <span
                          className={`h-1.5 w-1.5 rounded-full ${
                            r.activity.status === "working"
                              ? "animate-pulse bg-[var(--kt-warn)]"
                              : "bg-[var(--kt-border-strong)]"
                          }`}
                        />
                        {r.activity.status}
                      </span>
                    </div>
                    {r.activity.status === "working" && r.activity.task && (
                      <p className="mt-1.5 rounded bg-[var(--kt-inset)] px-2 py-1 text-xs leading-snug">
                        {r.activity.task}
                      </p>
                    )}
                    {r.activity.last_delivered && (
                      <p className={`mt-1.5 text-[11px] ${KT.muted}`}>
                        last delivered:{" "}
                        <span className="font-mono">
                          {r.activity.last_delivered.artifact}
                        </span>
                      </p>
                    )}
                    <p className="mt-1.5 text-xs leading-relaxed">{r.lane}</p>
                    <p className={`mt-2 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                      emits
                    </p>
                    <p className={`text-xs ${KT.muted}`}>{r.emits}</p>
                    <p className={`mt-2 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                      exists because
                    </p>
                    <p className={`text-xs leading-relaxed ${KT.muted}`}>
                      {r.exists_because}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            {/* the protocol, verbatim */}
            <section className={`${KT.card} mb-6 p-4`}>
              <p className={`${KT.label} mb-2`}>The working protocol</p>
              <ol className="space-y-1.5">
                {d.protocol.map((line, i) => (
                  <li key={i} className="flex gap-3 text-xs leading-relaxed">
                    <span className="font-mono text-[var(--kt-accent)]">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    {line}
                  </li>
                ))}
              </ol>
            </section>
          </>
        )}
      </div>
    </>
  );
}
