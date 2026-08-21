"use client";

import React, { useState } from "react";
import { Loader2, ShieldAlert, ShieldCheck } from "lucide-react";
import { spineError } from "@/lib/spine_error";
import { KT } from "../theme";
import { fundApiClient } from "@/lib/fund_api";
import {
  canAcknowledge, canRebaseDrawdown, checkNewPeak, cooldownSentence, peakLine,
  raisesEffectivePeak, type DrawdownView, type HaltAcknowledgement,
} from "./haltControls";

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

/**
 * The identity box for an APPROVAL-CHANNEL action.
 *
 * Empty by default and never prefilled, per the dispatch-6 brief. The Studio's
 * older controls (order approve/decline, the loss rebase, the limits editor,
 * the rebalance approve) post a hardcoded `"neelesh"` — that is a firm-wide
 * convention on the CEO's own console and changing it is a governance decision
 * for a human, not a refactor. These two controls are NEW, so they start the way
 * the brief says: the human types who is approving, and an allowlisted approval
 * is never reachable without someone claiming it.
 */
function ApproverBox({ value, onChange, label }: {
  value: string; onChange: (v: string) => void; label: string;
}) {
  const viaCto = /-via-(co-)?cto\b/i.test(value.trim());
  return (
    <div className="mt-2">
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Who is approving? (type it — not prefilled)"
        aria-label={label}
        className="w-full rounded border border-[var(--kt-border)] bg-transparent px-2 py-1.5 text-[12px] outline-none focus:border-[var(--kt-accent)]"
      />
      {viaCto && (
        <p className={`mt-1 text-[10px] ${KT.sev.warn}`}>
          A via-cto identity must carry the CEO&apos;s instruction VERBATIM in
          brackets — the spine&apos;s guard refuses it otherwise.
        </p>
      )}
    </div>
  );
}

export function HaltControl({ halted, haltClass, haltReason, lossReference,
                             rebaseToken, haltAckToken, haltAcknowledgement,
                             haltAlarm, autoresumeCooldownMinutes, drawdown,
                             onChanged }: {
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
  /** Echo for the acknowledgement — a digest of the HALT, so an ack typed
   *  against a screen showing a different darkness is refused. */
  haltAckToken?: string | null;
  /** Present once someone has recorded that they saw this halt. */
  haltAcknowledgement?: HaltAcknowledgement | null;
  /** The alarm that closed the fund, when the spine records one. */
  haltAlarm?: { type?: string | null; message?: string | null;
                severity?: string | null } | null;
  /** Absent = the cool-down is UNKNOWN here, never zero. */
  autoresumeCooldownMinutes?: number | null;
  drawdown?: DrawdownView | null;
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

  // --- acknowledge -------------------------------------------------------
  const [ackOpen, setAckOpen] = useState(false);
  const [ackWho, setAckWho] = useState("");
  const [ackNote, setAckNote] = useState("");
  const [ackErr, setAckErr] = useState<string | null>(null);
  const [ackBusy, setAckBusy] = useState(false);

  // --- drawdown rebase ---------------------------------------------------
  const [ddOpen, setDdOpen] = useState(false);
  const [ddWho, setDdWho] = useState("");
  const [ddPeak, setDdPeak] = useState("");
  const [ddReason, setDdReason] = useState("");
  const [ddErr, setDdErr] = useState<string | null>(null);
  const [ddBusy, setDdBusy] = useState(false);

  const ackAvail = canAcknowledge({ halted, halt_ack_token: haltAckToken,
                                    halt_acknowledgement: haltAcknowledgement });
  const ddAvail = canRebaseDrawdown(drawdown);
  const ddCheck = checkNewPeak(ddPeak, drawdown);
  const ddWarn = raisesEffectivePeak(ddPeak, drawdown);
  const peak = peakLine(drawdown);

  const runAck = async () => {
    if (!haltAckToken) return;
    setAckBusy(true);
    setAckErr(null);
    try {
      await fundApiClient.acknowledgeHalt(ackWho.trim(), haltAckToken,
                                          ackNote.trim() || undefined);
      setAckOpen(false);
      setAckNote("");
      onChanged?.();
    } catch (e: unknown) {
      setAckErr(spineError(e));
    } finally {
      setAckBusy(false);
    }
  };

  const runDrawdownRebase = async () => {
    const token = drawdown?.rebase_token;
    if (!token || !ddCheck.ok) return;
    setDdBusy(true);
    setDdErr(null);
    try {
      await fundApiClient.rebaseDrawdownReference(
        ddWho.trim(), token, Number(ddPeak.trim()), ddReason.trim());
      setDdOpen(false);
      setDdPeak("");
      setDdReason("");
      onChanged?.();
    } catch (e: unknown) {
      setDdErr(spineError(e));
    } finally {
      setDdBusy(false);
    }
  };

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
            {/* The alarm that closed the fund. Absent is stated: a halt whose
                triggering alarm the spine did not record is a halt whose CAUSE
                is unknown, which is different from a halt with no cause. */}
            <p className={`mt-1.5 text-[11px] ${haltAlarm ? KT.body : KT.muted}`}>
              {haltAlarm
                ? <>Alarm: <span className="font-mono">{haltAlarm.type ?? "unnamed"}</span>
                    {haltAlarm.severity ? ` · ${haltAlarm.severity}` : ""}
                    {haltAlarm.message ? ` — ${haltAlarm.message}` : ""}</>
                : "No triggering alarm was recorded against this halt — the cause is unknown, not absent."}
            </p>
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

        {/* ── ACKNOWLEDGE ────────────────────────────────────────────────
            Deliberately its own control, and deliberately worded so it cannot
            be mistaken for a resume: it moves no number and re-arms no path.
            It is condition (1) of four for the loss-halt auto-resume policy,
            and a halt whose other three never hold stays shut forever with
            this sitting harmlessly in the log. */}
        {halted && (
          <div className="mt-4 border-t border-[var(--kt-border)] pt-4">
            <p className={KT.label}>Acknowledge — record that you have seen this</p>
            <p className={`mt-1.5 text-[12px] ${KT.muted}`}>
              Acknowledging does NOT resume trading and does NOT move any
              reference. It records one sentence in the log saying a human saw
              this halt. {cooldownSentence(autoresumeCooldownMinutes)}
            </p>

            {haltAcknowledgement ? (
              <p className={`mt-2 text-[12px] ${KT.accent}`}>
                Acknowledged by {haltAcknowledgement.actor ?? "an unrecorded actor"}
                {haltAcknowledgement.at
                  ? ` at ${haltAcknowledgement.at.slice(0, 16).replace("T", " ")}`
                  : " at an unrecorded time"}
                {haltAcknowledgement.note ? ` — “${haltAcknowledgement.note}”` : ""}.
                {" "}The fund is still halted.
              </p>
            ) : !ackAvail.ok ? (
              <p className={`mt-2 text-[12px] ${KT.sev.warn}`}>{ackAvail.why}</p>
            ) : ackOpen ? (
              <div className={`mt-3 p-3 ${KT.inset}`}>
                <div className="text-[12px] font-medium">
                  Record that you have seen this halt?
                </div>
                <ApproverBox value={ackWho} onChange={setAckWho}
                             label="Who is acknowledging the halt" />
                <input
                  value={ackNote}
                  onChange={(e) => setAckNote(e.target.value)}
                  placeholder="Note (optional — recorded verbatim)"
                  className="mt-2 w-full rounded border border-[var(--kt-border)] bg-transparent px-2 py-1.5 text-[12px] outline-none focus:border-[var(--kt-accent)]"
                />
                <p className={`mt-1.5 font-mono text-[10px] ${KT.muted}`}>
                  confirming halt {haltAckToken}
                </p>
                {ackErr && <p className={`mt-2 text-[12px] ${KT.down}`}>{ackErr}</p>}
                <div className="mt-3 flex gap-2">
                  <button
                    disabled={ackBusy || ackWho.trim().length === 0}
                    onClick={runAck}
                    className={`flex items-center gap-1.5 ${KT.btnGhost} disabled:opacity-40`}
                  >
                    {ackBusy && <Loader2 size={14} className="animate-spin" />}
                    Record the acknowledgement
                  </button>
                  <button disabled={ackBusy}
                          onClick={() => { setAckOpen(false); setAckErr(null); }}
                          className={KT.btnGhost}>
                    Cancel
                  </button>
                </div>
                {ackWho.trim().length === 0 && (
                  <p className={`mt-2 text-[11px] ${KT.muted}`}>
                    An approver is required, and is deliberately not filled in for
                    you — this is an approval-channel action.
                  </p>
                )}
              </div>
            ) : (
              <button onClick={() => setAckOpen(true)} className={`mt-3 ${KT.btnGhost}`}>
                Acknowledge this halt…
              </button>
            )}
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
                <p className={`mt-2 text-[10px] ${KT.muted}`}>
                  Submits as the console identity <code>neelesh</code>, the
                  Studio&apos;s existing convention for approvals on this page. The
                  two controls below ask you to type an identity instead; the
                  difference is deliberate and is on the CTO&apos;s desk.
                </p>
              </div>
            )}
          </div>
        )}

        {/* ── REBASE THE DRAWDOWN PEAK ───────────────────────────────────
            NOT gated on the halt state, deliberately: an inflated peak caps
            risk capacity whether or not the fund is stopped, and the live
            fund's own peak includes the phantom-fill era. Only the token
            gates it, because without one a click cannot prove which peak it
            replaces. */}
        <div className="mt-5 border-t border-[var(--kt-border)] pt-4">
          <p className={KT.label}>The drawdown reference</p>
          <p className={`mt-1.5 text-[12px] ${KT.body}`}>{peak.headline}.</p>
          {drawdown?.peak_note && (
            <p className={`mt-1 text-[11px] ${KT.muted}`}>{drawdown.peak_note}</p>
          )}
          {drawdown?.rebase && (
            <p className={`mt-1 text-[11px] ${KT.muted}`}>
              Rebased by {drawdown.rebase.actor ?? "an unrecorded actor"}
              {drawdown.rebase.at
                ? ` on ${String(drawdown.rebase.at).slice(0, 16).replace("T", " ")}`
                : ""}
              {drawdown.rebase.reason ? ` — “${drawdown.rebase.reason}”` : ""}
            </p>
          )}
          <p className={`mt-2 text-[12px] ${KT.muted}`}>
            Lowering the reference moves NO threshold — the drawdown limit stays
            exactly where the register says it is. It moves the point the limit
            is measured from, once, in the log, with a mandatory reason. It can
            only ever LOWER the peak, and it can never hide a later genuine high:
            the effective peak is the max of the rebased value, every NAV since,
            and current NAV.
          </p>

          {!ddAvail.ok ? (
            <p className={`mt-2 text-[12px] ${KT.sev.warn}`}>{ddAvail.why}</p>
          ) : !ddOpen ? (
            <button onClick={() => setDdOpen(true)} className={`mt-3 ${KT.btnGhost}`}>
              Rebase the drawdown peak…
            </button>
          ) : (
            <div className={`mt-3 p-3 ${KT.inset}`}>
              <div className="text-[12px] font-medium">
                Lower the peak the drawdown is measured from
              </div>
              <ApproverBox value={ddWho} onChange={setDdWho}
                           label="Who is rebasing the drawdown peak" />
              <input
                value={ddPeak}
                onChange={(e) => setDdPeak(e.target.value)}
                inputMode="decimal"
                placeholder="The new peak, in USD — a judgement about which part of the history was real"
                aria-label="The new drawdown peak in USD"
                className="mt-2 w-full rounded border border-[var(--kt-border)] bg-transparent px-2 py-1.5 text-[12px] outline-none focus:border-[var(--kt-accent)]"
              />
              {ddCheck.error && (
                <p className={`mt-1 text-[11px] ${KT.down}`}>{ddCheck.error}</p>
              )}
              {ddWarn && <p className={`mt-1 text-[11px] ${KT.sev.warn}`}>{ddWarn}</p>}
              <textarea
                rows={3}
                value={ddReason}
                onChange={(e) => setDdReason(e.target.value)}
                placeholder="Why is the old peak wrong? (mandatory — recorded verbatim in the event log)"
                className="mt-2 w-full rounded border border-[var(--kt-border)] bg-transparent px-2 py-1.5 text-[12px] outline-none focus:border-[var(--kt-accent)]"
              />
              <p className={`mt-1.5 font-mono text-[10px] ${KT.muted}`}>
                confirming peak {drawdown?.rebase_token}
              </p>
              {ddErr && <p className={`mt-2 text-[12px] ${KT.down}`}>{ddErr}</p>}
              <div className="mt-3 flex gap-2">
                <button
                  disabled={ddBusy || !ddCheck.ok || ddWho.trim().length === 0
                            || ddReason.trim().length === 0}
                  onClick={runDrawdownRebase}
                  className={`flex items-center gap-1.5 ${KT.btnDanger} disabled:opacity-40`}
                >
                  {ddBusy && <Loader2 size={14} className="animate-spin" />}
                  Yes, lower the reference
                </button>
                <button disabled={ddBusy}
                        onClick={() => { setDdOpen(false); setDdErr(null); }}
                        className={KT.btnGhost}>
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
