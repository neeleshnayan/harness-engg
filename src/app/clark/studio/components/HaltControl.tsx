"use client";

import React, { useState } from "react";
import { Loader2, ShieldAlert, ShieldCheck } from "lucide-react";
import { spineError } from "@/lib/spine_error";
import { KT } from "../theme";
import { fundApiClient } from "@/lib/fund_api";

/**
 * The kill switch. Deliberately at the bottom, and deliberately two steps.
 *
 * It used to be a single click in the header of the breaches panel, inches from
 * the numbers an operator reads every day. Halting stops the fund buying and
 * requires a human to turn it back on; resuming re-arms a fund that was stopped
 * for a reason. Neither belongs behind a button you can hit while scanning.
 *
 * So: last thing on the page, and the second click has to say what it does. The
 * confirm step also takes the reason, because a halt with no stated cause is
 * indistinguishable from a misclick when someone reads the log later.
 *
 * Note the asymmetry — halting is the SAFE direction and stays quick to reach in
 * an emergency (two clicks, no typing required). Resuming is the dangerous one
 * and is the same two steps, because turning risk back on should never be easier
 * than turning it off.
 */
/**
 * How each halt class reads on the panel. The class changes the REOPENING
 * PROCEDURE, which is the only reason the distinction is worth a word on screen
 * (CEO-blessed principle, 2026-08-20).
 */
const HALT_CLASS_COPY: Record<string, { label: string; says: string }> = {
  integrity: {
    label: "INTEGRITY HALT",
    says: "The fund cannot currently MEASURE itself — a bad or absent mark, a "
      + "stale feed, or a dead control heartbeat. Nothing is known to be wrong "
      + "with the book; what is wrong is our sight of it. There is no "
      + "acknowledge-and-carry-on here: fix the integrity fault, then resume.",
  },
  loss: {
    label: "LOSS HALT",
    says: "The fund measured itself correctly and does not like the answer. "
      + "This is a circuit breaker: either resume, or acknowledge the loss and "
      + "rebase the daily-loss reference to current NAV with a written reason.",
  },
  manual: {
    label: "MANUAL HALT",
    says: "A human pulled the switch. It resumes when the same authority says so.",
  },
};

export function HaltControl({ halted, haltClass, haltReason, lossReference,
                             rebaseToken, onChanged }: {
  halted: boolean | undefined;
  /** null/undefined = UNKNOWN (a pre-classes halt, or a spine that does not
   *  report it). Rendered as unknown, never as "manual". */
  haltClass?: "integrity" | "loss" | "manual" | null;
  haltReason?: string | null;
  lossReference?: {
    nav_usd: number | null;
    kind: "prior_strike" | "rebased" | "absent";
    at: string | null;
    change_pct: number | null;
  };
  /** The echo the rebase must send back — read off THIS render. */
  rebaseToken?: string;
  onChanged?: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [rebasing, setRebasing] = useState(false);
  const [rebaseReason, setRebaseReason] = useState("");
  const [rebaseErr, setRebaseErr] = useState<string | null>(null);
  const [rebaseBusy, setRebaseBusy] = useState(false);

  const runRebase = async () => {
    if (!rebaseToken) return;
    setRebaseBusy(true);
    setRebaseErr(null);
    try {
      await fundApiClient.rebaseLossReference(rebaseReason.trim(), rebaseToken, "neelesh");
      setRebasing(false);
      setRebaseReason("");
      onChanged?.();
    } catch (e: unknown) {
      setRebaseErr(spineError(e));
    } finally {
      setRebaseBusy(false);
    }
  };

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      if (halted) await fundApiClient.resumeTrading("neelesh");
      else await fundApiClient.haltTrading(reason.trim() || "manual halt from monitor", "neelesh");
      setConfirming(false);
      setReason("");
      onChanged?.();
    } catch (e: unknown) {
      setErr(spineError(e));
    } finally {
      setBusy(false);
    }
  };

  if (halted === undefined) {
    return (
      <div className={`${KT.panel} px-5 py-4 text-sm ${KT.sev.warn}`}>
        Halt state unknown — the spine is unreadable, so this is not an all-clear.
      </div>
    );
  }

  return (
    <div className={KT.panel}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--kt-border)] px-5 py-3">
        <div className="flex items-center gap-2">
          {halted
            ? <ShieldAlert size={15} className={KT.down} />
            : <ShieldCheck size={15} className={KT.accent} />}
          <span className={KT.label}>Trading kill switch</span>
        </div>
        <span className={`font-mono text-[12px] ${halted ? KT.down : KT.muted}`}>
          {halted ? (haltClass ? HALT_CLASS_COPY[haltClass]?.label ?? "HALTED" : "HALTED") : "active"}
        </span>
      </div>

      <div className="px-5 py-4">
        <p className={`text-[12px] ${KT.muted}`}>
          {halted
            ? "Buys are blocked; sells are still allowed so a position can always be exited. Resuming re-arms a fund that was stopped for a reason."
            : "Halting blocks every buy immediately. Sells stay allowed. It does not cancel orders already working at the venue, and only a human can turn it back on."}
        </p>

        {/* WHICH kind of dark, and therefore which way out. An unclassified
            halt says so — it does not get filed as manual, which would make it
            eligible for a reopening procedure nobody chose for it. */}
        {halted && (
          <div className={`mt-3 p-3 text-[12px] ${KT.inset}`}>
            {haltClass ? (
              <p className={KT.body}>{HALT_CLASS_COPY[haltClass]?.says}</p>
            ) : (
              <p className={KT.sev.warn}>
                This halt carries no class — it was recorded before halt classes
                existed, or the spine does not report one. Which kind of dark this
                is, is unknown; treat it as an integrity halt until someone
                establishes otherwise.
              </p>
            )}
            {haltReason && (
              <p className={`mt-1.5 font-mono text-[11px] ${KT.muted}`}>{haltReason}</p>
            )}
          </div>
        )}

        {/* The daily-loss reference, always — because `kind: 'absent'` means the
            daily-loss halt is NOT EVALUATING, and that is the single most
            important thing this panel can tell an operator. It used to be
            invisible in every state. */}
        {lossReference && (
          <p className={`mt-3 text-[11px] ${
            lossReference.kind === "absent" ? KT.sev.warn : KT.muted}`}>
            {lossReference.kind === "absent" ? (
              <>
                Daily-loss reference: <strong>ABSENT</strong> — no prior-day NAV strike
                and no acknowledged rebase, so the daily-loss halt is not evaluating at
                all. This is an absence, not a pass.
              </>
            ) : (
              <>
                Daily loss measured from{" "}
                {lossReference.nav_usd != null
                  ? `$${lossReference.nav_usd.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
                  : "an unreported NAV"}
                {lossReference.kind === "rebased"
                  ? " (rebased by acknowledgement"
                  : " (the prior day's last strike"}
                {lossReference.at ? `, ${lossReference.at.slice(0, 16).replace("T", " ")})` : ")"}
                {lossReference.change_pct != null &&
                  ` · currently ${lossReference.change_pct >= 0 ? "+" : ""}${lossReference.change_pct.toFixed(2)}%`}
              </>
            )}
          </p>
        )}

        {err && <div className={`mt-3 text-[12px] ${KT.down}`}>{err}</div>}

        {!confirming ? (
          <button
            onClick={() => setConfirming(true)}
            className={`mt-3 flex items-center gap-1.5 ${halted ? KT.btn : KT.btnDanger}`}
          >
            {halted ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
            {halted ? "Resume trading" : "Halt trading"}
          </button>
        ) : (
          <div className={`mt-3 p-3 ${KT.inset}`}>
            <div className={`text-[12px] font-medium ${halted ? "" : KT.down}`}>
              {halted
                ? "Resume trading? The fund will be able to buy again."
                : "Halt trading? Every buy is blocked until a human resumes it."}
            </div>
            {!halted && (
              <input
                autoFocus
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Why are you halting? (recorded in the audit log)"
                className={`mt-2 w-full rounded border border-[var(--kt-border)] bg-transparent px-2 py-1.5 text-[12px] outline-none focus:border-[var(--kt-accent)]`}
              />
            )}
            <div className="mt-3 flex gap-2">
              <button disabled={busy} onClick={run}
                      className={`flex items-center gap-1.5 ${halted ? KT.btn : KT.btnDanger}`}>
                {busy && <Loader2 size={14} className="animate-spin" />}
                {halted ? "Yes, resume" : "Yes, halt trading"}
              </button>
              <button disabled={busy} onClick={() => { setConfirming(false); setReason(""); }}
                      className={KT.btnGhost}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* ── ACKNOWLEDGE AND REBASE (loss class only) ────────────────────
            Rendered ONLY for a loss halt. Not for an integrity halt, where the
            spine refuses it anyway — but a control that is present and always
            errors teaches an operator to click through errors, so it is absent
            instead, with the reason said above.

            `confirm` is the rebase_token from THIS render of the risk monitor.
            If NAV, the reference or the halt state has moved since the panel
            was drawn, the token no longer matches and the spine refuses: a
            confirm cannot be copied off a screen that has gone stale. */}
        {halted && haltClass === "loss" && (
          <div className="mt-5 border-t border-[var(--kt-border)] pt-4">
            <p className={KT.label}>Acknowledge the loss and rebase</p>
            <p className={`mt-1.5 text-[12px] ${KT.muted}`}>
              Moves the daily-loss reference to the fund&apos;s CURRENT NAV, so the
              same drop stops re-tripping the breaker. It moves no threshold — the
              limit stays exactly where the register says it is. Recorded as a{" "}
              <code>LossReferenceRebased</code> event with your reason, and refused
              while an integrity halt is open.
            </p>

            {!rebaseToken ? (
              <p className={`mt-2 text-[12px] ${KT.sev.warn}`}>
                This spine did not return a rebase token, so the control cannot prove
                which state it is acting on and is disabled. Not an error — a missing
                capability.
              </p>
            ) : rebaseErr ? (
              <div className={`mt-2 text-[12px] ${KT.down}`}>{rebaseErr}</div>
            ) : null}

            {rebaseToken && !rebasing && (
              <button onClick={() => setRebasing(true)} className={`mt-3 ${KT.btnGhost}`}>
                Acknowledge and rebase…
              </button>
            )}

            {rebaseToken && rebasing && (
              <div className={`mt-3 p-3 ${KT.inset}`}>
                <div className="text-[12px] font-medium">
                  Rebase the daily-loss reference to current NAV?
                </div>
                <textarea
                  autoFocus
                  rows={3}
                  value={rebaseReason}
                  onChange={(e) => setRebaseReason(e.target.value)}
                  placeholder="Why is this drop acceptable? (mandatory — recorded verbatim in the event log)"
                  className="mt-2 w-full rounded border border-[var(--kt-border)] bg-transparent px-2 py-1.5 text-[12px] outline-none focus:border-[var(--kt-accent)]"
                />
                <p className={`mt-1.5 font-mono text-[10px] ${KT.muted}`}>
                  confirming state {rebaseToken}
                </p>
                <div className="mt-3 flex gap-2">
                  <button
                    disabled={rebaseBusy || rebaseReason.trim().length === 0}
                    onClick={runRebase}
                    className={`flex items-center gap-1.5 ${KT.btnDanger} disabled:opacity-40`}
                  >
                    {rebaseBusy && <Loader2 size={14} className="animate-spin" />}
                    Yes, rebase the reference
                  </button>
                  <button disabled={rebaseBusy}
                          onClick={() => { setRebasing(false); setRebaseReason(""); setRebaseErr(null); }}
                          className={KT.btnGhost}>
                    Cancel
                  </button>
                </div>
                {rebaseReason.trim().length === 0 && (
                  <p className={`mt-2 text-[11px] ${KT.muted}`}>
                    A reason is required. The spine refuses a rebase without one.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
