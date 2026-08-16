"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { Loader2, Play, Save } from "lucide-react";
import { python } from "@codemirror/lang-python";
import { KT } from "../theme";
import { fundApi } from "@/lib/fund_api";

/**
 * The Lab's LEAN desk: write a real QCAlgorithm, run it on the real engine.
 *
 * The editor talks only to the harness (save algorithm, submit job, poll) —
 * Docker, workspaces and the engine container stay invisible. The code the
 * operator writes is arbitrary Python and it RUNS: the container is the
 * sandbox (read-only mount, no credentials, no signal token, wall-clock
 * kill). Results render from the engine's actual statistics; a failed run
 * shows LEAN's real error and the log tail, because "something went wrong"
 * teaches nothing.
 */

const CodeMirror = dynamic(() => import("@uiw/react-codemirror"), {
  ssr: false,
  loading: () => <div className={`p-6 text-sm ${KT.muted}`}>Loading editor…</div>,
});

const TEMPLATE = `from AlgorithmImports import *
import urllib.request

SPINE = "http://host.docker.internal:8090/api/v1/fund"


class SpineBars(PythonData):
    """Daily bars from the fund's own market-data layer — the engine judges
    the market on the same closes the fund marks its book with. CSV, one
    line per bar: LEAN's reader iterates lines as data points."""

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


class MyAlgorithm(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2025, 6, 1)
        self.set_cash(2000)
        self.sym = self.add_data(SpineBars, "SPY", Resolution.DAILY).symbol
        self.sma = self.sma(self.sym, 20)

    def on_data(self, data: Slice):
        if self.sym not in data or not self.sma.is_ready:
            return
        price = data[self.sym].value
        if price > self.sma.current.value and not self.portfolio[self.sym].invested:
            self.set_holdings(self.sym, 0.95)
        elif price < self.sma.current.value and self.portfolio[self.sym].invested:
            self.liquidate(self.sym)
`;

interface LeanJob {
  job_id: string;
  algorithm?: string;
  state: string;
  error?: string | null;
  wall_seconds?: number;
  log_tail?: string[];
  result?: {
    total_return_pct?: number | null;
    sharpe?: number | null;
    max_drawdown_pct?: number | null;
    total_trades?: number | null;
    equity_curve?: number[];
  } | null;
}

const pctf = (n?: number | null) => (n == null ? "—" : `${n.toFixed(1)}%`);

function EquitySpark({ curve }: { curve: number[] }) {
  if (curve.length < 2) return null;
  const min = Math.min(...curve), max = Math.max(...curve), span = max - min || 1;
  const w = 640, h = 120;
  const pts = curve
    .map((v, i) => `${(i / (curve.length - 1)) * w},${h - 4 - ((v - min) / span) * (h - 8)}`)
    .join(" ");
  const up = curve[curve.length - 1] >= curve[0];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-[120px] w-full">
      <polyline points={pts} fill="none" strokeWidth={1.5}
                stroke={up ? "var(--kt-up)" : "var(--kt-down)"} />
    </svg>
  );
}

export function LeanLab() {
  const [code, setCode] = useState(TEMPLATE);
  const [name, setName] = useState("my_algorithm");
  const [job, setJob] = useState<LeanJob | null>(null);
  const [busy, setBusy] = useState<"save" | "run" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const run = useCallback(async () => {
    setErr(null);
    setBusy("run");
    setJob(null);
    setElapsed(0);
    try {
      await fundApi.post("/api/v1/fund/lean/algorithms", { name, code });
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
          }
        } catch { /* poll errors: keep polling until timeout kills the job */ }
      }, 2500);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setErr(detail ?? String(e));
      setBusy(null);
    }
  }, [name, code]);

  const r = job?.result;

  return (
    <div className={`mt-6 ${KT.panel}`}>
      <div className="flex flex-wrap items-center gap-3 border-b border-[var(--kt-border)] px-5 py-3">
        <div>
          <span className={KT.label}>LEAN lab</span>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            A real QCAlgorithm on the real engine — code runs sandboxed in the
            engine container; results come from LEAN&apos;s own statistics.
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ""))}
            className={`w-44 ${KT.input}`}
            aria-label="Algorithm name"
          />
          <button onClick={run} disabled={busy !== null}
                  className={`flex h-9 items-center gap-1.5 ${KT.btn} disabled:opacity-40`}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {busy ? `Running · ${elapsed}s` : "Save & run"}
          </button>
        </div>
      </div>

      <div className="border-b border-[var(--kt-border)]">
        <CodeMirror
          value={code}
          onChange={setCode}
          extensions={[python()]}
          theme="dark"
          height="420px"
          basicSetup={{ lineNumbers: true, foldGutter: false }}
        />
      </div>

      {err && <div className={`px-5 py-3 text-sm ${KT.down}`}>{err}</div>}

      {job?.state === "running" || job?.state === "queued" ? (
        <div className={`flex items-center gap-2 px-5 py-4 text-sm ${KT.muted}`}>
          <Loader2 size={14} className="animate-spin" />
          Engine {job.state} · {elapsed}s — the full LEAN engine takes tens of
          seconds; this is the price of the engine of record.
        </div>
      ) : null}

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

      {job?.state === "done" && r && (
        <div className="px-5 py-4">
          <div className="flex flex-wrap gap-x-8 gap-y-2 font-mono text-[13px] tabular-nums">
            <span className={(r.total_return_pct ?? 0) >= 0 ? KT.up : KT.down}>
              return {pctf(r.total_return_pct)}
            </span>
            <span>sharpe {r.sharpe?.toFixed(2) ?? "—"}</span>
            <span>max DD {pctf(r.max_drawdown_pct)}</span>
            <span>{r.total_trades ?? "—"} orders</span>
            <span className={KT.muted}>{job.wall_seconds}s wall</span>
          </div>
          {r.equity_curve && r.equity_curve.length >= 2 && (
            <div className="mt-3"><EquitySpark curve={r.equity_curve} /></div>
          )}
          <p className={`mt-2 text-[10px] ${KT.muted}`}>
            LEAN engine statistics, verbatim. Nothing here is registered or
            persisted to the fund — promotion to a strategy is a separate,
            deliberate step.
          </p>
        </div>
      )}
    </div>
  );
}
