"use client";

import React, { useState } from "react";
import { Terminal, Copy, Check, Filter, AlertTriangle, ShieldCheck, Cpu, RefreshCw } from "lucide-react";
import { AgentFlowGraph, AgentFlowStep } from "../types";

interface TerminalExecutionFlowProps {
  flow: AgentFlowGraph | AgentFlowStep[];
  query?: string;
  className?: string;
}

export function TerminalExecutionFlow({ flow, query, className = "" }: TerminalExecutionFlowProps) {
  const [copied, setCopied] = useState(false);
  const [filter, setFilter] = useState<"ALL" | "BLOCKERS" | "SPINE">("ALL");

  if (!flow) return null;

  const isGraph = typeof flow === "object" && "nodes" in flow && "edges" in flow;
  const steps: AgentFlowStep[] = isGraph
    ? (flow as AgentFlowGraph).steps || (flow as AgentFlowGraph).nodes.filter((n) => n.type !== "start" && n.type !== "end")
    : (flow as AgentFlowStep[]);

  const totalTime = isGraph ? (flow as AgentFlowGraph).total_query_time_ms : undefined;

  // Synthesize rich execution log lines from the flow steps
  const logEntries: Array<{
    id: string;
    timestamp: string;
    level: "INFO" | "EXEC" | "BLOCKER" | "SUCCESS";
    agent: string;
    message: string;
    latencyMs?: number;
    blockerReason?: string;
  }> = [];

  // Start event
  const startTime = steps[0]?.timestamp || new Date().toISOString();
  logEntries.push({
    id: "init",
    timestamp: startTime,
    level: "INFO",
    agent: "ORCHESTRATOR",
    message: `Received execution request: "${query || "Agent Query"}"`,
  });

  steps.forEach((step, idx) => {
    const ts = step.timestamp || new Date().toISOString();
    const agentName = (step.name || step.id || "AGENT").toUpperCase().replace(/\s+AGENT$/, "");
    const latency = step.latency_ms;

    // Check if there was a data fetch delay or fallback blocker
    let blockerReason: string | undefined;
    const outputStr = typeof step.output === "string" ? step.output : JSON.stringify(step.output || {});

    if (latency && latency > 10000) {
      blockerReason = `High latency (${(latency / 1000).toFixed(1)}s) on ${agentName} — fallback route active`;
    } else if (outputStr.toLowerCase().includes("issue retrieving") || outputStr.toLowerCase().includes("fallback")) {
      blockerReason = `Data source fallback triggered for ${step.input || "query"}`;
    }

    if (blockerReason) {
      logEntries.push({
        id: `blocker-${idx}`,
        timestamp: ts,
        level: "BLOCKER",
        agent: agentName,
        message: `[BLOCKER DETECTED] ${blockerReason}`,
        latencyMs: latency,
        blockerReason,
      });
    }

    logEntries.push({
      id: `step-${idx}`,
      timestamp: ts,
      level: step.status === "completed" ? "SUCCESS" : "EXEC",
      agent: agentName,
      message: `Executing ${step.tool_name || agentName} → Input: "${step.input || query || "N/A"}"`,
      latencyMs: latency,
    });

    if (step.output) {
      const summary =
        typeof step.output === "string"
          ? step.output
          : (step.output as any).message || (step.output as any).summary || JSON.stringify(step.output).slice(0, 120);
      logEntries.push({
        id: `out-${idx}`,
        timestamp: ts,
        level: "INFO",
        agent: agentName,
        message: `Return payload: ${summary}`,
      });
    }
  });

  // Final summary log
  logEntries.push({
    id: "complete",
    timestamp: new Date().toISOString(),
    level: "SUCCESS",
    agent: "ORCHESTRATOR",
    message: `Execution complete across ${steps.length} specialized step(s)${
      totalTime ? ` in ${(totalTime / 1000).toFixed(2)}s` : ""
    }`,
    latencyMs: totalTime,
  });

  const filteredLogs = logEntries.filter((log) => {
    if (filter === "BLOCKERS") return log.level === "BLOCKER";
    if (filter === "SPINE") return log.agent.includes("BACKTEST") || log.agent.includes("FUND") || log.agent.includes("SPINE");
    return true;
  });

  const fullLogText = logEntries
    .map(
      (l) =>
        `[${new Date(l.timestamp).toLocaleTimeString()}] [${l.level}] [${l.agent}] ${l.message} ${
          l.latencyMs ? `(${l.latencyMs}ms)` : ""
        }`
    )
    .join("\n");

  const handleCopy = () => {
    navigator.clipboard.writeText(fullLogText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`rounded-xl border border-zinc-800 bg-zinc-950 font-mono text-xs shadow-2xl overflow-hidden ${className}`}>
      {/* Header Bar */}
      <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-900/80 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Terminal size={14} className="text-emerald-400" />
          <span className="font-semibold text-zinc-200 tracking-wider">CLARK EXECUTION TERMINAL</span>
          <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400 border border-emerald-500/20">
            LIVE TRACE
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-md bg-zinc-800/80 p-0.5 text-[10px]">
            <button
              onClick={() => setFilter("ALL")}
              className={`rounded px-2 py-0.5 transition ${filter === "ALL" ? "bg-zinc-700 text-zinc-100" : "text-zinc-400"}`}
            >
              ALL ({logEntries.length})
            </button>
            <button
              onClick={() => setFilter("BLOCKERS")}
              className={`rounded px-2 py-0.5 transition ${
                filter === "BLOCKERS" ? "bg-amber-500/20 text-amber-300 font-bold" : "text-amber-500/80"
              }`}
            >
              BLOCKERS ({logEntries.filter((l) => l.level === "BLOCKER").length})
            </button>
            <button
              onClick={() => setFilter("SPINE")}
              className={`rounded px-2 py-0.5 transition ${filter === "SPINE" ? "bg-teal-500/20 text-teal-300" : "text-zinc-400"}`}
            >
              SPINE
            </button>
          </div>

          <button
            onClick={handleCopy}
            className="flex items-center gap-1 rounded bg-zinc-800 px-2 py-1 text-[10px] text-zinc-300 hover:bg-zinc-700"
          >
            {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
            {copied ? "Copied" : "Copy Logs"}
          </button>
        </div>
      </div>

      {/* Terminal Output */}
      <div className="max-h-[320px] overflow-y-auto p-4 space-y-1.5 scrollbar-thin scrollbar-thumb-zinc-800">
        {filteredLogs.length === 0 ? (
          <div className="py-8 text-center text-zinc-600">No log entries matching filter</div>
        ) : (
          filteredLogs.map((log) => (
            <div
              key={log.id}
              className={`flex items-start gap-2.5 leading-relaxed ${
                log.level === "BLOCKER"
                  ? "rounded bg-amber-500/10 p-2 border border-amber-500/30 text-amber-200"
                  : log.level === "SUCCESS"
                  ? "text-emerald-300"
                  : log.level === "EXEC"
                  ? "text-sky-300"
                  : "text-zinc-400"
              }`}
            >
              <span className="text-[10px] text-zinc-600 select-none">
                {new Date(log.timestamp).toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>

              <span
                className={`rounded px-1 py-0.2 text-[9px] font-bold tracking-wider ${
                  log.level === "BLOCKER"
                    ? "bg-amber-500/30 text-amber-200"
                    : log.level === "SUCCESS"
                    ? "bg-emerald-500/20 text-emerald-300"
                    : "bg-zinc-800 text-zinc-400"
                }`}
              >
                [{log.level}]
              </span>

              <span className="font-semibold text-zinc-300">[{log.agent}]</span>

              <span className="flex-1 whitespace-pre-wrap">{log.message}</span>

              {log.latencyMs !== undefined && log.latencyMs > 0 && (
                <span className="text-[10px] text-zinc-500 bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800">
                  {log.latencyMs}ms
                </span>
              )}
            </div>
          ))
        )}
      </div>

      {/* Terminal Footer with Execution Pipeline */}
      <div className="border-t border-zinc-900 bg-zinc-950/90 px-4 py-2 flex items-center justify-between text-[11px] text-zinc-500">
        <div className="flex items-center gap-2">
          <Cpu size={12} className="text-teal-400" />
          <span>Topology: Orchestrator → Spine Event Log → Execution Engine</span>
        </div>
        {totalTime && <span>Total Execution: <strong className="text-emerald-400">{totalTime}ms</strong></span>}
      </div>
    </div>
  );
}
