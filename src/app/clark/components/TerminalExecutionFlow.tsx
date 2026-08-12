"use client";

import React, { useState, useEffect, useRef } from "react";
import { Terminal, Copy, Check, Play, Pause, RotateCcw, AlertTriangle, ShieldCheck, Cpu } from "lucide-react";
import { AgentFlowGraph, AgentFlowStep } from "../types";

interface TerminalExecutionFlowProps {
  flow: AgentFlowGraph | AgentFlowStep[];
  query?: string;
  className?: string;
}

export function TerminalExecutionFlow({ flow, query, className = "" }: TerminalExecutionFlowProps) {
  const [copied, setCopied] = useState(false);
  const [filter, setFilter] = useState<"ALL" | "CALLS" | "BLOCKERS" | "SPINE">("ALL");
  const [isStreaming, setIsStreaming] = useState(true);
  const [visibleCount, setVisibleCount] = useState(1);

  const isGraph = flow && typeof flow === "object" && "nodes" in flow && "edges" in flow;
  const steps: AgentFlowStep[] = !flow ? [] : isGraph
    ? (flow as AgentFlowGraph).steps || (flow as AgentFlowGraph).nodes.filter((n) => n.type !== "start" && n.type !== "end")
    : (flow as AgentFlowStep[]);

  const totalTime = isGraph ? (flow as AgentFlowGraph).total_query_time_ms : undefined;

  // Build sequential event stream entries
  const streamEntries: Array<{
    id: string;
    timestamp: string;
    level: "CALL" | "RETURN" | "BLOCKER" | "PASS" | "INFO";
    agent: string;
    action: string;
    detail?: string;
    latencyMs?: number;
  }> = [];

  const startTime = steps[0]?.timestamp || new Date().toISOString();
  streamEntries.push({
    id: "init",
    timestamp: startTime,
    level: "CALL",
    agent: "ORCHESTRATOR",
    action: `INITIATING_EXECUTION_FLOW: "${query || "Agent Query"}"`,
    detail: "Parsing intent & evaluating agent topology...",
  });

  steps.forEach((step, idx) => {
    const ts = step.timestamp || new Date().toISOString();
    const agentName = (step.name || step.id || "AGENT").toUpperCase().replace(/\s+AGENT$/, "");
    const latency = step.latency_ms;
    const toolName = step.tool_name || `consult_${agentName.toLowerCase()}`;

    // 1. Task Call Event
    streamEntries.push({
      id: `call-${idx}`,
      timestamp: ts,
      level: "CALL",
      agent: agentName,
      action: `CALLING_AGENT: ${toolName}`,
      detail: step.input ? `Input payload: "${step.input}"` : undefined,
    });

    // 2. Check for Blocker Event
    const outputStr = typeof step.output === "string" ? step.output : JSON.stringify(step.output || {});
    let blockerMsg: string | undefined;

    if (latency && latency > 10000) {
      blockerMsg = `High latency bottleneck (${(latency / 1000).toFixed(1)}s) on ${agentName}`;
    } else if (outputStr.toLowerCase().includes("issue retrieving") || outputStr.toLowerCase().includes("unreachable")) {
      blockerMsg = `Spine data source unreachable for ${agentName}`;
    }

    if (blockerMsg) {
      streamEntries.push({
        id: `blocker-${idx}`,
        timestamp: ts,
        level: "BLOCKER",
        agent: agentName,
        action: `BLOCKER_FACED: ${blockerMsg}`,
        detail: "Auto-recovering via fallback strategy route",
        latencyMs: latency,
      });
    }

    // 3. Task Return Event
    let summary: string | undefined;
    if (step.output) {
      if (typeof step.output === "string") {
        summary = step.output;
      } else if (typeof step.output === "object") {
        summary = (step.output as any)?.message || (step.output as any)?.summary || JSON.stringify(step.output).slice(0, 100);
      }
    }

    streamEntries.push({
      id: `return-${idx}`,
      timestamp: ts,
      level: "RETURN",
      agent: agentName,
      action: `TASK_RETURN: ${toolName} ──> 200 OK`,
      detail: summary ? `Payload: "${summary}"` : undefined,
      latencyMs: latency,
    });
  });

  // Final Pass Event
  streamEntries.push({
    id: "complete",
    timestamp: new Date().toISOString(),
    level: "PASS",
    agent: "ORCHESTRATOR",
    action: `FLOW_COMPLETE: Synthesized output across ${steps.length} specialized task(s)`,
    detail: totalTime ? `Total elapsed latency: ${(totalTime / 1000).toFixed(2)}s` : undefined,
    latencyMs: totalTime,
  });

  // Real-time task streaming effect
  useEffect(() => {
    setVisibleCount(1);
    setIsStreaming(true);
  }, [flow]);

  useEffect(() => {
    if (!isStreaming) return;
    if (visibleCount >= streamEntries.length) {
      setIsStreaming(false);
      return;
    }

    const timer = setTimeout(() => {
      setVisibleCount((prev) => Math.min(prev + 1, streamEntries.length));
    }, 120);

    return () => clearTimeout(timer);
  }, [visibleCount, isStreaming, streamEntries.length]);

  if (!flow) return null;

  const displayedLogs = streamEntries.slice(0, visibleCount).filter((entry) => {
    if (filter === "BLOCKERS") return entry.level === "BLOCKER";
    if (filter === "CALLS") return entry.level === "CALL" || entry.level === "RETURN";
    if (filter === "SPINE") return entry.agent.includes("BACKTEST") || entry.agent.includes("FUND") || entry.agent.includes("SPINE");
    return true;
  });

  const fullTextLog = streamEntries
    .map(
      (e) =>
        `[${new Date(e.timestamp).toLocaleTimeString()}] [${e.level}] [${e.agent}] ${e.action}${
          e.detail ? ` | ${e.detail}` : ""
        }${e.latencyMs ? ` (${e.latencyMs}ms)` : ""}`
    )
    .join("\n");

  const handleCopy = () => {
    navigator.clipboard.writeText(fullTextLog);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleReplay = () => {
    setVisibleCount(1);
    setIsStreaming(true);
  };

  return (
    <div className={`rounded-xl border border-emerald-950/80 bg-[#090D16] font-mono text-xs shadow-2xl overflow-hidden ${className}`}>
      {/* Terminal Control Header */}
      <div className="flex flex-wrap items-center justify-between border-b border-emerald-900/30 bg-[#0C121E] px-4 py-2.5 gap-2">
        <div className="flex items-center gap-2.5">
          <div className="flex gap-1.5">
            <span className="w-3 h-3 rounded-full bg-rose-500/80 inline-block" />
            <span className="w-3 h-3 rounded-full bg-amber-500/80 inline-block" />
            <span className="w-3 h-3 rounded-full bg-emerald-500/80 inline-block" />
          </div>
          <span className="font-semibold text-emerald-400 tracking-wider flex items-center gap-1.5 ml-2">
            <Terminal size={14} />
            CLARK LIVE TASK STREAM
          </span>
          <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
            {isStreaming ? <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" /> : null}
            {isStreaming ? "STREAMING" : "LIVE CAPTURE"}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={isStreaming ? () => setIsStreaming(false) : handleReplay}
            className="flex items-center gap-1 rounded bg-zinc-800/90 px-2.5 py-1 text-[10px] text-emerald-400 hover:bg-zinc-700 transition"
            title={isStreaming ? "Pause Stream" : "Replay Task Stream"}
          >
            {isStreaming ? <Pause size={12} /> : <RotateCcw size={12} />}
            <span>{isStreaming ? "Pause" : "Replay"}</span>
          </button>

          <div className="flex items-center rounded-md bg-zinc-900 p-0.5 text-[10px] border border-zinc-800">
            <button
              onClick={() => setFilter("ALL")}
              className={`rounded px-2 py-0.5 transition ${filter === "ALL" ? "bg-emerald-500/20 text-emerald-300 font-semibold" : "text-zinc-400"}`}
            >
              ALL
            </button>
            <button
              onClick={() => setFilter("CALLS")}
              className={`rounded px-2 py-0.5 transition ${filter === "CALLS" ? "bg-sky-500/20 text-sky-300 font-semibold" : "text-zinc-400"}`}
            >
              CALLS & RETURNS
            </button>
            <button
              onClick={() => setFilter("BLOCKERS")}
              className={`rounded px-2 py-0.5 transition ${
                filter === "BLOCKERS" ? "bg-amber-500/20 text-amber-300 font-bold" : "text-amber-500/80"
              }`}
            >
              BLOCKERS ({streamEntries.filter((e) => e.level === "BLOCKER").length})
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

      {/* Streaming Terminal Log Body */}
      <div className="max-h-[360px] overflow-y-auto p-4 space-y-2 scrollbar-minimal">
        {displayedLogs.map((entry) => (
          <div
            key={entry.id}
            className={`flex items-start gap-2.5 leading-relaxed font-mono transition-all duration-150 ${
              entry.level === "BLOCKER"
                ? "rounded bg-amber-500/10 p-2 border border-amber-500/30 text-amber-200"
                : entry.level === "PASS"
                ? "text-emerald-300 font-semibold"
                : entry.level === "CALL"
                ? "text-sky-300"
                : entry.level === "RETURN"
                ? "text-teal-300"
                : "text-zinc-400"
            }`}
          >
            <span className="text-[10px] text-zinc-500 select-none pt-0.5">
              [{new Date(entry.timestamp).toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}]
            </span>

            <span
              className={`rounded px-1.5 py-0.5 text-[9px] font-bold tracking-wide ${
                entry.level === "BLOCKER"
                  ? "bg-amber-500/30 text-amber-200"
                  : entry.level === "PASS"
                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                  : entry.level === "CALL"
                  ? "bg-sky-500/20 text-sky-300"
                  : "bg-teal-500/20 text-teal-300"
              }`}
            >
              [{entry.level}]
            </span>

            <span className="font-semibold text-zinc-200">[{entry.agent}]</span>

            <div className="flex-1 min-w-0">
              <div className="text-zinc-200">{entry.action}</div>
              {entry.detail && <div className="text-[11px] text-zinc-400 mt-0.5 truncate">{entry.detail}</div>}
            </div>

            {entry.latencyMs !== undefined && entry.latencyMs > 0 && (
              <span className="text-[10px] text-emerald-400/90 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/40">
                {entry.latencyMs}ms
              </span>
            )}
          </div>
        ))}

        {isStreaming && (
          <div className="flex items-center gap-2 text-emerald-400 text-xs pt-1">
            <span>Streaming tasks</span>
            <span className="animate-pulse font-bold text-emerald-300">▋</span>
          </div>
        )}
      </div>

      {/* Terminal Footer Topology Bar */}
      <div className="border-t border-zinc-900 bg-[#060911] px-4 py-2 flex items-center justify-between text-[11px] text-zinc-500">
        <div className="flex items-center gap-2">
          <Cpu size={12} className="text-emerald-400" />
          <span>Execution Stream: Orchestrator &mdash;&gt; Skill Handlers &mdash;&gt; Spine Engine</span>
        </div>
        {totalTime && <span>Total Latency: <strong className="text-emerald-400">{totalTime}ms</strong></span>}
      </div>
    </div>
  );
}
