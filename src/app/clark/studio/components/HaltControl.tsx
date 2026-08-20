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
export function HaltControl({ halted, onChanged }: {
  halted: boolean | undefined;
  onChanged?: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

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
          {halted ? "HALTED" : "active"}
        </span>
      </div>

      <div className="px-5 py-4">
        <p className={`text-[12px] ${KT.muted}`}>
          {halted
            ? "Buys are blocked; sells are still allowed so a position can always be exited. Resuming re-arms a fund that was stopped for a reason."
            : "Halting blocks every buy immediately. Sells stay allowed. It does not cancel orders already working at the venue, and only a human can turn it back on."}
        </p>

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
      </div>
    </div>
  );
}
