"use client";

import React, { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, FlaskConical, Landmark, ShieldAlert } from "lucide-react";
import { fundApiClient, FundModeName, FundModeReport } from "@/lib/fund_api";
import { KT } from "../theme";
import {
  confirmEcho, declarationConflict, preconditionTone, presentMode, selectability,
} from "../fundMode";

/**
 * WHICH FUND IS THIS? — the strip that answers it on every Studio surface.
 *
 * CEO instruction, 2026-08-21: "the UI needs to give a toggle so I can switch
 * from mock mode where we are testing out things to trading mode where we have
 * our live strategies."
 *
 * The failure this prevents is not a wrong click; it is a human reading a test
 * number as a real one. So the strip follows the user everywhere, is never
 * dismissible, and is LOUD in proportion to how wrong that misreading would
 * be — quiet in alpaca-paper (the fund's normal state, where a permanent
 * banner is a banner nobody reads on the day it matters), loud in test, and
 * loudest for real money and for NOT KNOWING.
 *
 * Every presentation judgement lives in ../fundMode.ts with tests. This file
 * is the pixels.
 *
 * Design system: hierarchy from type and space, never from colour alone. Each
 * state carries its own ICON and its own WORDS, so the strip still reads
 * correctly in monochrome, and the surface frame in test mode is a border, not
 * a wash.
 */
export function ModeBar({ pollMs = 30000 }: { pollMs?: number }) {
  const [report, setReport] = useState<FundModeReport | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      setReport(await fundApiClient.getFundMode());
    } catch {
      // Null is the UNREACHABLE state, which presentMode renders as alarming.
      // Deliberately not left at the previous value: a stale mode shown as
      // current is the exact confusion this strip exists to end.
      setReport(null);
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, pollMs);
    return () => clearInterval(t);
  }, [load, pollMs]);

  const p = presentMode(report);

  // The whole surface, not just this strip. `data-fund-mode` on the Studio
  // root lets any panel style itself against the mode, and the frame below is
  // the default treatment: a permanent inset outline you cannot scroll past.
  useEffect(() => {
    if (!loaded) return;
    const root = document.documentElement;
    root.setAttribute("data-fund-mode", p.key);
    return () => root.removeAttribute("data-fund-mode");
  }, [loaded, p.key]);

  // Before the first answer, say nothing rather than guess. A momentary
  // "ALPACA PAPER" that turns out to be wrong is worse than a blank strip.
  if (!loaded) {
    return (
      <Strip volume="quiet">
        <span className={KT.muted}>Reading the fund&rsquo;s mode…</span>
      </Strip>
    );
  }

  const Icon =
    p.key === "test" ? FlaskConical
      : p.key === "alpaca-paper" ? Landmark
      : p.key === "alpaca-prod" ? ShieldAlert
      : AlertTriangle;

  return (
    <>
      {p.frameSurface && <SurfaceFrame volume={p.volume} badge={p.badge} />}
      <Strip volume={p.volume}>
        <Icon size={13} aria-hidden />
        <span className="font-semibold uppercase tracking-wide">{p.badge}</span>
        <span className="font-medium">{p.headline}</span>
        <span className={`hidden truncate lg:inline ${KT.muted}`}>— {p.detail}</span>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="ml-auto shrink-0 underline underline-offset-2"
        >
          {report?.active ? "Switch mode" : "Why?"}
        </button>
      </Strip>
      {open && (
        <ModeSwitchDialog
          report={report}
          onClose={() => setOpen(false)}
          onSwitched={() => { setOpen(false); load(); }}
        />
      )}
    </>
  );
}

/**
 * A permanent outline around the viewport, with the mode named at its foot.
 *
 * "Not a small switch in a corner — in mock mode the whole surface should say
 * so." A strip at the top scrolls out of a reader's attention within seconds;
 * this does not. `pointer-events-none` so it never intercepts a click.
 *
 * PORTALLED TO <body>, and that is not tidiness — it is a bug fix found by
 * screenshotting it. `position: fixed` resolves against the nearest ancestor
 * that establishes a containing block, and StudioHeader carries
 * `backdrop-blur-md`. A backdrop-filter does establish one, exactly as a
 * transform does, so `inset-0` rendered a 1160x190 box around the header
 * instead of a frame around the screen: the "whole surface says so" treatment
 * was confined to the strip that already said so.
 */
function SurfaceFrame({ volume, badge }: { volume: string; badge: string }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  const colour = volume === "alarming" ? "var(--kt-down)" : "var(--kt-warn)";
  return createPortal(
    <div
      aria-hidden
      data-testid="fund-mode-frame"
      className="pointer-events-none fixed inset-0 z-[60]"
      style={{ boxShadow: `inset 0 0 0 3px ${colour}` }}
    >
      <div
        className="absolute bottom-0 left-1/2 -translate-x-1/2 rounded-t-md px-3 py-0.5 font-mono text-[10px] uppercase tracking-[0.18em]"
        style={{ background: colour, color: "var(--kt-bg)" }}
      >
        {badge}
      </div>
    </div>,
    document.body,
  );
}

type Volume = "quiet" | "loud" | "alarming";

const VOLUME: Record<Volume, string> = {
  quiet: "border-[var(--kt-border)] text-[var(--kt-text-dim)]",
  loud: "border-[var(--kt-warn)]/40 bg-[var(--kt-warn)]/10 text-[var(--kt-warn)]",
  alarming: "border-[var(--kt-down)]/50 bg-[var(--kt-down)]/10 text-[var(--kt-down)]",
};

function Strip({ volume, children }: { volume: Volume; children: React.ReactNode }) {
  return (
    <div className={`border-b ${VOLUME[volume]}`}>
      <div className="mx-auto flex max-w-[1600px] items-center gap-2 px-6 py-1.5 text-[11px]">
        {children}
      </div>
    </div>
  );
}

/**
 * The switch itself. A CONTROL, not a preference.
 *
 * Three things are on screen before the button is live, and each one is a
 * refusal the spine would make anyway — shown here so the operator learns the
 * rule from the interface rather than from a 409:
 *
 *   1. WHAT CHANGES — both dimensions, named, with the store each mode writes.
 *   2. THE ECHO — the operator types the mode. Nothing approves what it has
 *      not read, and this is the same guard an order approval passes.
 *   3. THE REASON — free text, required. NAV and the order path both move on
 *      this click; an unexplained move is indistinguishable from an
 *      unauthorised one.
 */
function ModeSwitchDialog({
  report, onClose, onSwitched,
}: {
  report: FundModeReport | null;
  onClose: () => void;
  onSwitched: () => void;
}) {
  const [target, setTarget] = useState<FundModeName | null>(null);
  const [approver, setApprover] = useState("neelesh");
  const [echo, setEcho] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hazard, setHazard] = useState<
    { env: string; file: string; effect: string; remedy: string } | null>(null);
  const [showGate, setShowGate] = useState(false);
  // Open whenever prod is the target, whether or not the operator toggled it:
  // selecting the mode the list gates is exactly when the list must be read.
  const gateOpen = showGate || target === "alpaca-prod";

  const sel = target ? selectability(report, target) : { selectable: false, reason: "" };
  const echoOk = target ? echo.trim() === confirmEcho(target) : false;
  const ready = Boolean(target) && sel.selectable && echoOk && reason.trim().length > 0;

  const submit = async () => {
    if (!target || !ready) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fundApiClient.switchFundMode({
        mode: target, approver: approver.trim(), confirm: echo.trim(),
        reason: reason.trim(),
      });
      // THE SWITCH SUCCEEDED AND THE NEXT RESTART WILL REFUSE. Holding the
      // dialog open is the point: closing on success would put this sentence
      // on a screen nobody is looking at, and the consequence lands hours
      // later at a boot that does not complete (adversary D11, K7).
      if (res?.restart_hazard) {
        setHazard(res.restart_hazard);
        return;
      }
      onSwitched();
    } catch (e: unknown) {
      // The spine's refusals are the useful ones — pending orders, a locked
      // prod gate — so they are shown verbatim rather than replaced with
      // "something went wrong".
      const detail =
        (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : JSON.stringify(detail ?? e));
    } finally {
      setBusy(false);
    }
  };

  // Same containing-block hazard as the frame: this dialog is rendered from
  // inside StudioHeader, whose backdrop-blur would trap `fixed inset-0` in the
  // header's box. Portalled for the same reason and found the same way.
  if (typeof document === "undefined") return null;
  // Bounded height with the ACTION BAR PINNED, found by screenshotting it: the
  // five prod preconditions run to about 250px of prose, and at a 1000px
  // viewport they pushed the echo field, the reason field and the button clean
  // off the bottom. A control whose confirm step is below a wall of
  // explanation is a control people learn to scroll past.
  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-start justify-center bg-black/50 p-6 backdrop-blur-sm">
      <div className={`${KT.panel} mt-12 flex max-h-[86vh] w-full max-w-2xl flex-col`}>
        <div className="overflow-y-auto p-6">
        <div className={KT.label}>The fund&rsquo;s mode</div>
        <h2 className="mt-1 text-lg font-semibold text-[var(--kt-text-strong)]">
          Where orders go, and where events land
        </h2>
        <p className={`mt-2 ${KT.body}`}>
          Two dimensions, one switch. Each mode writes to its own store — a test
          NAV and the fund&rsquo;s NAV are different numbers and are never folded
          together.
        </p>

        {/* WHO DECLARED WHAT — rendered always, not only when they disagree.
            The two authorities are the process environment and the mode file,
            and until now the dialog showed neither: an operator could not see
            that the switch he was about to make would arm a ModeConflict on
            the next restart, and the spine's refusal landed hours later at a
            boot that would not complete (adversary D11, K7). */}
        {report && (
          <DeclaredBy report={report} />
        )}

        <div className="mt-5 space-y-2">
          {(report?.modes ?? []).map((m) => {
            const s = selectability(report, m.mode);
            const isActive = report?.active?.mode === m.mode;
            return (
              <button
                key={m.mode}
                type="button"
                disabled={!s.selectable}
                onClick={() => { setTarget(m.mode); setEcho(""); setError(null); }}
                className={`w-full rounded-xl border p-3 text-left transition-colors ${
                  target === m.mode
                    ? "border-[var(--kt-accent)]"
                    : "border-[var(--kt-border)]"
                } ${s.selectable ? "hover:border-[var(--kt-border-strong)]" : "opacity-60"}`}
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--kt-text-strong)]">
                    {m.mode}
                  </span>
                  {isActive && <span className={KT.chip}>current</span>}
                  {m.venue.real_money && (
                    <span className="rounded-full border border-[var(--kt-down)]/50 px-2 py-0.5 text-[11px] text-[var(--kt-down)]">
                      real money
                    </span>
                  )}
                  {!m.wired && (
                    <span className={`text-[11px] ${KT.muted}`}>never wired</span>
                  )}
                </div>
                <div className={`mt-1 text-[12px] ${KT.body}`}>{m.caution}</div>
                <div className={`mt-1 font-mono text-[11px] ${KT.muted}`}>
                  orders → {m.venue.label} · events → {m.store.pg_database}
                </div>
                {/* A disabled control ALWAYS says why. A greyed button with no
                    explanation is how a precondition list becomes invisible. */}
                {!s.selectable && s.reason && (
                  <div className="mt-1 text-[11px] text-[var(--kt-warn)]">
                    unavailable — {s.reason}
                  </div>
                )}
              </button>
            );
          })}
        </div>

        {/* The prod gate IN FULL — behind a disclosure, not hidden.
            The COUNT is always visible on the alpaca-prod row above ("5 of 5
            preconditions are not met"), so nothing is concealed; what moves
            behind the toggle is 250px of prose that was pushing the confirm
            step off the screen. The summary is the honest part; the detail is
            one click away and open by default whenever prod is the target. */}
        {report && report.prod_gate.preconditions.length > 0 && (
          <div className={`${KT.inset} mt-4 p-3`}>
            <button
              type="button"
              onClick={() => setShowGate((v) => !v)}
              className={`flex w-full items-center gap-2 ${KT.label}`}
            >
              <span>alpaca-prod preconditions</span>
              <span className={KT.muted}>
                {report.prod_gate.n_met}/{report.prod_gate.n_preconditions} met
              </span>
              <span className="ml-auto underline underline-offset-2">
                {gateOpen ? "hide" : "show"}
              </span>
            </button>
            <ul className={`mt-2 space-y-1.5 ${gateOpen ? "" : "hidden"}`}>
              {report.prod_gate.preconditions.map((c) => {
                const t = preconditionTone(c.status);
                return (
                  <li key={c.key} className="flex gap-2 text-[12px]">
                    <span
                      className={`font-mono ${t.blocking ? "text-[var(--kt-warn)]" : KT.accent}`}
                      aria-label={t.word}
                    >
                      {t.symbol}
                    </span>
                    <span className={KT.body}>
                      {c.text}{" "}
                      <span className={KT.muted}>({t.word}: {c.detail})</span>
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {target && (
          <div className="mt-5 space-y-3" data-testid="mode-confirm-fields">
            <Field label={`Type "${confirmEcho(target)}" to confirm you have read the target mode`}>
              <input
                value={echo}
                onChange={(e) => setEcho(e.target.value)}
                className="w-full rounded-lg border border-[var(--kt-border)] bg-[var(--kt-inset)] px-3 py-1.5 font-mono text-sm"
                placeholder={confirmEcho(target)}
              />
            </Field>
            <Field label="Approver">
              <input
                value={approver}
                onChange={(e) => setApprover(e.target.value)}
                className="w-full rounded-lg border border-[var(--kt-border)] bg-[var(--kt-inset)] px-3 py-1.5 text-sm"
              />
            </Field>
            <Field label="Why — recorded in the log, permanently">
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
                className="w-full rounded-lg border border-[var(--kt-border)] bg-[var(--kt-inset)] px-3 py-1.5 text-sm"
              />
            </Field>
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-lg border border-[var(--kt-down)]/50 bg-[var(--kt-down)]/10 p-3 text-[12px] text-[var(--kt-down)]">
            {error}
          </div>
        )}

        {hazard && (
          <div
            className="mt-4 rounded-lg border border-[var(--kt-warn)]/60 bg-[var(--kt-warn)]/10 p-3 text-[12px] text-[var(--kt-warn)]"
            data-testid="mode-restart-hazard"
          >
            <div className="font-semibold">
              Switched — and the next spine restart will REFUSE to start
            </div>
            <div className="mt-1">
              FUND_MODE={hazard.env} in the spine&rsquo;s environment now
              disagrees with the mode file, which says {hazard.file}.{" "}
              {hazard.effect}
            </div>
            <div className="mt-1">{hazard.remedy}</div>
          </div>
        )}
        </div>

        {/* PINNED. Outside the scroll region, so the button and the reason it
            is disabled are on screen whatever the operator has scrolled to. */}
        <div className="flex items-center gap-3 border-t border-[var(--kt-border)] px-6 py-4">
          <button
            type="button"
            onClick={hazard ? onSwitched : submit}
            disabled={!hazard && (!ready || busy)}
            className="rounded-lg border border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] px-4 py-1.5 text-sm text-[var(--kt-accent)] disabled:opacity-40"
          >
            {hazard ? "I have read this" : busy ? "Switching…" : "Switch the fund's mode"}
          </button>
          <button type="button" onClick={onClose} className={`text-sm ${KT.muted}`}>
            {hazard ? "Close" : "Cancel"}
          </button>
          {/* A disabled button says why it is disabled, at the button. The
              operator should never have to scroll up to find out. */}
          <span className={`ml-auto text-right text-[11px] ${KT.muted}`}>
            {!target
              ? "Choose a mode above"
              : !sel.selectable
                ? sel.reason
                : !echoOk
                  ? `Type "${confirmEcho(target)}" to confirm`
                  : !reason.trim()
                    ? "A written reason is required"
                    : "Refused while any order is pending or in flight."}
          </span>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/**
 * The two authorities, side by side, and the conflict between them.
 *
 * Always rendered, never only on disagreement: "which authority is telling
 * this spine what it is" is a question the operator should be able to answer
 * before he changes the answer, and a block that appears only when something
 * is wrong teaches nobody what the normal state looks like.
 */
function DeclaredBy({ report }: { report: FundModeReport }) {
  const conflict = declarationConflict(report);
  const env = report.declared?.env;
  const file = report.declared?.file?.mode;
  const fileError = report.declared?.file_error;
  return (
    <div className={`${KT.inset} mt-4 p-3`} data-testid="mode-declared-by">
      <div className={KT.label}>Declared by</div>
      <dl className="mt-1.5 grid grid-cols-[7rem_1fr] gap-x-3 gap-y-1 text-[12px]">
        <dt className={KT.muted}>FUND_MODE (env)</dt>
        {/* Absence is rendered as absence. "not set" is a fact about the
            environment; a blank cell would read as a rendering failure. */}
        <dd className="font-mono text-[var(--kt-text-strong)]">
          {env || <span className={KT.muted}>not set</span>}
        </dd>
        <dt className={KT.muted}>mode file</dt>
        <dd className="font-mono text-[var(--kt-text-strong)]">
          {fileError
            ? <span className="text-[var(--kt-warn)]">unreadable — {fileError}</span>
            : file || <span className={KT.muted}>no file</span>}
        </dd>
        <dt className={KT.muted}>file path</dt>
        <dd className={`font-mono ${KT.muted}`}>{report.declared?.file_path}</dd>
      </dl>
      {conflict && (
        <div
          className="mt-2 rounded-lg border border-[var(--kt-warn)]/50 p-2 text-[12px] text-[var(--kt-warn)]"
          data-testid="mode-declaration-conflict"
        >
          <div className="font-semibold">
            These two disagree — {conflict.effect}
          </div>
          <div className="mt-0.5">{conflict.remedy}</div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className={KT.label}>{label}</div>
      <div className="mt-1">{children}</div>
    </label>
  );
}
