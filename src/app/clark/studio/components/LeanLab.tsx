"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { FileCode2, Loader2, Play, Plus, Save, Sparkles } from "lucide-react";
import { python } from "@codemirror/lang-python";
import { KT } from "../theme";
import { LeanResults, LeanRunResult } from "./LeanResults";
import { SweepPanel } from "./SweepPanel";
import { fundApi } from "@/lib/fund_api";
import agentsApi from "@/lib/agents_api";

/**
 * The Lab's LEAN desk: a strategy library and an IDE over the real engine.
 *
 * The editor talks only to the harness (list, load, save, submit, poll) —
 * Docker, workspaces and the engine container stay invisible. Algorithms are
 * ordinary LEAN projects on disk (`<name>/main.py`, a `class X(QCAlgorithm)`),
 * which is why the same file runs here, under `lean backtest`, or in anyone's
 * editor: the library IS a LEAN workspace, not a private format.
 *
 * The code the operator writes is arbitrary Python and it RUNS: the container
 * is the sandbox (read-only mount, no credentials, no signal token, wall-clock
 * kill). Results render from the engine's actual statistics; a failed run shows
 * LEAN's real error and the log tail, because "something went wrong" teaches
 * nothing.
 */

const CodeMirror = dynamic(() => import("@uiw/react-codemirror"), {
  ssr: false,
  loading: () => <div className={`p-6 text-sm ${KT.muted}`}>Loading editor…</div>,
});

/** Bars from the fund's own market-data layer — the engine judges the market
 *  on the same closes the fund marks its book with. CSV, one line per bar:
 *  LEAN's remote-file reader iterates LINES as data points, so a JSON blob
 *  reads as exactly one bar. */
const SPINE_BARS = `from AlgorithmImports import *

SPINE = "http://host.docker.internal:8090/api/v1/fund"


class SpineBars(PythonData):
    """Daily bars from the fund's own market-data layer."""

    def get_source(self, config, date, is_live):
        url = f"{SPINE}/marketdata/bars?symbol={config.symbol.value}&lookback_days=700&format=csv"
        return SubscriptionDataSource(url, SubscriptionTransportMedium.REMOTE_FILE)

    def reader(self, config, line, date, is_live):
        try:
            ds, close = line.strip().split(",")
            bar = SpineBars()
            bar.symbol = config.symbol
            bar.time = datetime.strptime(ds, "%Y-%m-%d")
            bar.value = float(close)
            return bar
        except (ValueError, AttributeError):
            return None
`;

const STARTERS: { id: string; label: string; hint: string; code: string }[] = [
  {
    id: "sma_cross",
    label: "SMA crossover",
    hint: "trades — produces real return, Sharpe and drawdown",
    code: `${SPINE_BARS}

class MyAlgorithm(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2025, 1, 1)
        self.set_cash(2000)
        # Read tunables as parameters so the Lab can sweep them. get_parameter
        # returns None when unset, hence the defaults — a plain Run still works.
        fast = int(self.get_parameter("fast") or 20)
        slow = int(self.get_parameter("slow") or 60)
        self.sym = self.add_data(SpineBars, "SPY", Resolution.DAILY).symbol
        self.fast = self.sma(self.sym, fast)
        self.slow = self.sma(self.sym, slow)

    def on_data(self, data: Slice):
        if self.sym not in data or not self.slow.is_ready:
            return
        if self.fast.current.value > self.slow.current.value:
            if not self.portfolio[self.sym].invested:
                self.set_holdings(self.sym, 0.95)
        elif self.portfolio[self.sym].invested:
            self.liquidate(self.sym)
`,
  },
  {
    id: "signal_only",
    label: "Signal-only filter",
    hint: "never trades — logs a call, for sidecars that propose",
    code: `${SPINE_BARS}

class MyAlgorithm(QCAlgorithm):
    """Signal-only: this algorithm cannot trade. It states a view and logs it;
    turning a view into an order is a separate, human-approved step."""

    def initialize(self):
        self.set_start_date(2025, 1, 1)
        self.set_cash(2000)
        self.sym = self.add_data(SpineBars, "GLD", Resolution.DAILY).symbol
        self.sma = self.sma(self.sym, 100)
        self.state = None  # "in" | "out" — a call fires only on CHANGE

    def on_data(self, data: Slice):
        if self.sym not in data or not self.sma.is_ready:
            return
        price = data[self.sym].value
        want = "in" if price > self.sma.current.value else "out"
        if want == self.state:
            return
        prev, self.state = self.state, want
        if prev is None:
            return  # the first observation is a state, not a signal
        self.log(f"CALL {want} @ {price:.2f} vs sma {self.sma.current.value:.2f}")
`,
  },
  {
    id: "blank",
    label: "Blank",
    hint: "the minimum LEAN accepts",
    code: `from AlgorithmImports import *


class MyAlgorithm(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2025, 1, 1)
        self.set_cash(2000)

    def on_data(self, data: Slice):
        pass
`,
  },
];

interface LeanJob {
  job_id: string;
  algorithm?: string;
  state: string;
  error?: string | null;
  wall_seconds?: number;
  log_tail?: string[];
  result?: LeanRunResult | null;
}

interface SavedAlgo {
  name: string;
  class_name?: string | null;
  lines?: number;
  modified_at?: string;
}

const pctf = (n?: number | null) => (n == null ? "—" : `${n.toFixed(1)}%`);

export function LeanLab() {
  const [code, setCode] = useState(STARTERS[0].code);
  const [name, setName] = useState("my_algorithm");
  const [library, setLibrary] = useState<SavedAlgo[]>([]);
  const [loadedName, setLoadedName] = useState<string | null>(null);
  const [savedCode, setSavedCode] = useState<string | null>(null);
  const [job, setJob] = useState<LeanJob | null>(null);
  const [history, setHistory] = useState<LeanJob[]>([]);
  const [busy, setBusy] = useState<"save" | "run" | "author" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [ask, setAsk] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const refreshLibrary = useCallback(async () => {
    try {
      const d = (await fundApi.get("/api/v1/fund/lean/algorithms")).data;
      setLibrary(d.algorithms ?? []);
    } catch {
      /* an unreachable library is not worth an error banner over the editor;
         the Save button reports the real failure when it matters. */
    }
  }, []);

  useEffect(() => { refreshLibrary(); }, [refreshLibrary]);

  /** Load on demand: the library is the repo, the editor is the working copy. */
  const load = useCallback(async (algoName: string) => {
    setErr(null);
    setNote(null);
    try {
      const d = (await fundApi.get(`/api/v1/fund/lean/algorithms/${algoName}`)).data;
      setCode(d.code);
      setSavedCode(d.code);
      setName(algoName);
      setLoadedName(algoName);
    } catch (e: unknown) {
      setErr(detailOf(e));
    }
  }, []);

  const startFrom = useCallback((starterId: string) => {
    const s = STARTERS.find((x) => x.id === starterId);
    if (!s) return;
    setCode(s.code);
    setSavedCode(null);
    setLoadedName(null);
    setErr(null);
    setNote(null);
  }, []);

  /** Describe it; Clark writes the file; you read and tweak it. A draft, not
   *  an answer — nothing is saved or run until the operator says so. */
  const author = useCallback(async () => {
    const description = ask.trim();
    if (!description) return;
    setErr(null);
    setNote(null);
    setWarnings([]);
    setBusy("author");
    try {
      const d = (await agentsApi.post("/api/v1/agents/lean/author", { description })).data;
      if (d.error) {
        setErr(d.error);
        return;
      }
      setCode(d.code);
      setSavedCode(null);      // a draft is unsaved by definition
      setLoadedName(null);
      if (d.name) setName(d.name);
      setWarnings(d.warnings ?? []);
      setNote(
        (d.warnings?.length ?? 0) > 0
          ? "Draft written — read the notes below before running."
          : "Draft written — read it, tweak it, then Run.",
      );
    } catch (e: unknown) {
      setErr(detailOf(e));
    } finally {
      setBusy(null);
    }
  }, [ask]);

  const save = useCallback(async () => {
    setErr(null);
    setNote(null);
    setBusy("save");
    try {
      await fundApi.post("/api/v1/fund/lean/algorithms", { name, code });
      setSavedCode(code);
      setLoadedName(name);
      setNote(`Saved to the library as ${name}`);
      await refreshLibrary();
    } catch (e: unknown) {
      setErr(detailOf(e));
    } finally {
      setBusy(null);
    }
  }, [name, code, refreshLibrary]);

  const run = useCallback(async () => {
    setErr(null);
    setNote(null);
    setBusy("run");
    setJob(null);
    setElapsed(0);
    try {
      // Save first, always: the engine runs what is ON DISK. Running the
      // library's copy while the operator reads their unsaved edits is the
      // kind of quiet mismatch that makes a backtest a lie.
      await fundApi.post("/api/v1/fund/lean/algorithms", { name, code });
      setSavedCode(code);
      setLoadedName(name);
      await refreshLibrary();
      const sub = (await fundApi.post("/api/v1/fund/lean/backtests", { algorithm: name })).data;
      const t0 = Date.now();
      pollRef.current = setInterval(async () => {
        setElapsed(Math.round((Date.now() - t0) / 1000));
        try {
          const j = (await fundApi.get(`/api/v1/fund/lean/backtests/${sub.job_id}`)).data as LeanJob;
          setJob(j);
          if (j.state === "done" || j.state === "failed") {
            if (pollRef.current) clearInterval(pollRef.current);
            setBusy(null);
            setHistory((h) => [j, ...h].slice(0, 8));
          }
        } catch { /* poll errors: keep polling until timeout kills the job */ }
      }, 2500);
    } catch (e: unknown) {
      setErr(detailOf(e));
      setBusy(null);
    }
  }, [name, code, refreshLibrary]);

  const r = job?.result;
  const dirty = savedCode !== null && savedCode !== code;

  return (
    <div className={`mt-6 ${KT.panel}`}>
      {/* ---------------- header ---------------- */}
      <div className="flex flex-wrap items-center gap-3 border-b border-[var(--kt-border)] px-5 py-3">
        <div className="min-w-0">
          <span className={KT.label}>LEAN lab</span>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            A real QCAlgorithm on the real engine — the lab above is the fast
            loop, this is the engine of record. Results are LEAN&apos;s own statistics.
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ""))}
            className={`w-44 ${KT.input}`}
            aria-label="Algorithm name"
            placeholder="algorithm_name"
          />
          <button onClick={save} disabled={busy !== null || !name}
                  title="Save to the library without running"
                  className={`flex h-9 items-center gap-1.5 ${KT.btnGhost} disabled:opacity-40`}>
            {busy === "save" ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Save
          </button>
          <button onClick={run} disabled={busy !== null || !name}
                  className={`flex h-9 items-center gap-1.5 ${KT.btn} disabled:opacity-40`}>
            {busy === "run" ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {busy === "run" ? `Running · ${elapsed}s` : "Run"}
          </button>
        </div>
      </div>

      {/* ---------------- ask Clark for the code ---------------- */}
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--kt-border)] px-5 py-3">
        <Sparkles size={13} className={`shrink-0 ${KT.agent.text}`} />
        <input
          value={ask}
          onChange={(e) => setAsk(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); author(); } }}
          placeholder="Describe a strategy — e.g. buy GLD when it crosses above its 100-day SMA, sell below"
          className={`min-w-[240px] flex-1 ${KT.input}`}
          aria-label="Describe the strategy for Clark to write"
        />
        <button onClick={author} disabled={busy !== null || !ask.trim()}
                className={`flex h-9 items-center gap-1.5 ${KT.agent.btn} disabled:opacity-40`}>
          {busy === "author" ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          {busy === "author" ? "Writing…" : "Ask Clark"}
        </button>
      </div>

      {warnings.length > 0 && (
        <div className="border-b border-[var(--kt-border)] px-5 py-3">
          <div className={KT.label}>Read before running</div>
          <ul className="mt-1.5 space-y-1">
            {warnings.map((w, i) => (
              <li key={i} className="text-[11px] text-[var(--kt-warn)]">— {w}</li>
            ))}
          </ul>
          <p className={`mt-2 text-[10px] ${KT.muted}`}>
            Clark wrote this; the engine has not seen it yet. These are problems
            that would surface at run time as errors that read like engine
            faults rather than code faults.
          </p>
        </div>
      )}

      {/* ---------------- library + editor ---------------- */}
      <div className="grid grid-cols-1 border-b border-[var(--kt-border)] lg:grid-cols-[220px_1fr]">
        <div className="border-b border-[var(--kt-border)] lg:border-b-0 lg:border-r">
          <div className={`px-4 pt-4 ${KT.label}`}>Strategies</div>
          {library.length === 0 ? (
            <div className={`px-4 py-3 text-[11px] ${KT.muted}`}>
              Nothing saved yet.
            </div>
          ) : (
            <ul className="mt-2 max-h-[380px] overflow-y-auto">
              {library.map((a) => (
                <li key={a.name}>
                  <button
                    onClick={() => load(a.name)}
                    className={`flex w-full items-baseline gap-2 px-4 py-2 text-left text-[11px] transition-colors hover:bg-[var(--kt-hover)] ${
                      a.name === loadedName ? "bg-[var(--kt-inset)]" : ""
                    }`}
                  >
                    <FileCode2 size={12} className={`shrink-0 ${KT.muted}`} />
                    <span className="truncate font-semibold">{a.name}</span>
                    <span className={`ml-auto shrink-0 font-mono ${KT.muted}`}>{a.lines ?? "—"}L</span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className={`mt-3 border-t border-[var(--kt-border)] px-4 pt-3 ${KT.label}`}>
            Start from
          </div>
          <ul className="mb-4 mt-1">
            {STARTERS.map((s) => (
              <li key={s.id}>
                <button onClick={() => startFrom(s.id)} title={s.hint}
                        className="flex w-full items-center gap-2 px-4 py-1.5 text-left text-[11px] text-[var(--kt-text-dim)] transition-colors hover:bg-[var(--kt-hover)]">
                  <Plus size={11} className="shrink-0" />
                  <span className="truncate">{s.label}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="min-w-0">
          <CodeMirror
            value={code}
            onChange={setCode}
            extensions={[python()]}
            theme="dark"
            // Tall enough to hold a whole algorithm without scrolling: the
            // SpineBars boilerplate alone is ~25 lines, so a short pane meant
            // the strategy — the only part anyone edits — was always below the
            // fold.
            height="640px"
            basicSetup={{ lineNumbers: true, foldGutter: false }}
          />
        </div>
      </div>

      {/* ---------------- status ---------------- */}
      {dirty && (
        <div className={`px-5 pt-3 text-[11px] ${KT.muted}`}>
          Edited since last save — Run saves first, so the engine always runs what you see.
        </div>
      )}
      {note && <div className={`px-5 pt-3 text-[11px] ${KT.accent}`}>{note}</div>}
      {err && <div className={`px-5 py-3 text-sm ${KT.down}`}>{err}</div>}

      {(job?.state === "running" || job?.state === "queued") && (
        <div className={`flex items-center gap-2 px-5 py-4 text-sm ${KT.muted}`}>
          <Loader2 size={14} className="animate-spin" />
          Engine {job.state} · {elapsed}s — the full LEAN engine takes tens of
          seconds; this is the price of the engine of record.
        </div>
      )}

      {job?.state === "failed" && (
        <div className="px-5 py-4">
          <div className={`text-sm ${KT.down}`}>Run failed: {job.error}</div>
          {(job.log_tail?.length ?? 0) > 0 && (
            <pre className={`mt-2 max-h-48 overflow-auto rounded-lg bg-[var(--kt-inset)] p-3 font-mono text-[11px] leading-relaxed ${KT.muted}`}>
              {job.log_tail?.join("\n")}
            </pre>
          )}
        </div>
      )}

      {/* ---------------- results ---------------- */}
      {job?.state === "done" && r && (
        <LeanResults result={r} algorithm={job.algorithm ?? name}
                     wallSeconds={job.wall_seconds} />
      )}

      {/* The sweep needs a SAVED algorithm — it runs the copy on disk many
          times over, so it is offered once there is one to run. */}
      {loadedName && (
        <div className="px-5 pb-5">
          <SweepPanel algorithm={loadedName} disabled={busy !== null} />
        </div>
      )}

      {/* ---------------- run history: research is comparison --------------- */}
      {history.length > 1 && (
        <div className="border-t border-[var(--kt-border)] px-5 py-3">
          <div className={KT.label}>This session</div>
          <ul className="mt-2 space-y-1">
            {history.map((h, i) => (
              <li key={`${h.job_id}-${i}`} className="flex items-baseline gap-3 text-[11px]">
                <span className="font-semibold">{h.algorithm}</span>
                <span className={KT.muted}>{h.state}</span>
                <span className={`ml-auto font-mono ${(h.result?.total_return_pct ?? 0) >= 0 ? KT.up : KT.down}`}>
                  {pctf(h.result?.total_return_pct)}
                </span>
                <span className={`w-16 text-right font-mono ${KT.muted}`}>{h.wall_seconds ?? "—"}s</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function detailOf(e: unknown): string {
  const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail ?? String(e);
}
