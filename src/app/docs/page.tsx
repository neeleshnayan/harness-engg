"use client";

import React from "react";
import Link from "next/link";
import {
  Code2,
  Zap,
  Server,
  Key,
  MessageSquare,
  Shield,
  ArrowLeft,
} from "lucide-react";

export default function DocsPage() {
  return (
    <div className="min-h-screen w-full bg-[#001C1B] text-white">
      {/* Nav */}
      <header className="sticky top-0 z-50 backdrop-blur-md bg-[#001C1B]/95 border-b border-white/10">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          {/* <Link
            href="/"
            className="inline-flex items-center gap-2 text-white/80 hover:text-white transition-colors text-sm font-medium"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Link> */}
          <span className="text-[10px] uppercase tracking-[0.2em] text-white/50">
            Clark
          </span>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-10 pb-20">
        <h1 className="text-3xl font-semibold text-white mb-2">
          Clark Integration
        </h1>
        <p className="text-white/70 text-lg mb-10">
        Integrate Clark into your LLM client for crypto and stock screening, economic data, tax and regulation info, backtesting, technical analysis, and Krypton Pay (balances, swaps, transfers).
        </p>

        {/* Connecting (e.g. Cursor) */}
        <section className="mb-12">
          <h2 className="flex items-center gap-2 text-xl font-semibold text-white mb-4">
            <Code2 className="h-5 w-5 text-[#90E7EE]" />
            Connecting from your LLM Client
          </h2>
          <p className="text-white/80 leading-relaxed mb-4">
            In your MCP config (e.g. <code className="px-1.5 py-0.5 rounded bg-white/10 font-mono text-sm">mcp.json</code> or Cursor MCP
            settings), add the Clark MCP server with its URL. You can pass user
            identity via headers so you don’t have to send <code className="font-mono text-sm">user_id</code> /
            <code className="font-mono text-sm">username</code> on every tool call:
          </p>
          <div className="rounded-xl bg-white/5 border border-white/10 p-4 font-mono text-sm text-white/90 overflow-x-auto">
            <pre>{`{
  "mcpServers": {
    "krypton-strands": {
      "url": "https://clark.kryptonfund.com/mcp",
      "headers": {
        "x-user-id": "your-user-id", # optional
        "x-username": "your-username" # required
      }
    }
  }
}`}</pre>
          </div>
        </section>

        {/* Tools */}
        <section className="mb-12">
          <h2 className="flex items-center gap-2 text-xl font-semibold text-white mb-4">
            <MessageSquare className="h-5 w-5 text-[#90E7EE]" />
            MCP tools
          </h2>

          <div className="space-y-8">
            <div>
              <h3 className="text-lg font-medium text-white mb-2">
                <code className="px-2 py-1 rounded bg-white/10 text-[#90E7EE]">krypton_query</code>
              </h3>
              <p className="text-white/80 text-sm leading-relaxed mb-3">
                Routes a natural-language query through the Krypton/Strands
                multi-agent orchestrator and returns the structured result
                (message, data, agent_flow, costs, etc.). When the response
                has <code className="font-mono">stop_reason: &quot;interrupt&quot;</code> and an{" "}
                <code className="font-mono">interrupts</code> array (e.g.
                krypton-pay-approval), use{" "}
                <code className="font-mono">krypton_approve_interrupt</code> to
                approve or reject, then the flow continues.
              </p>
              <div className="rounded-xl bg-white/5 border border-white/10 p-4 font-mono text-xs text-white/90 overflow-x-auto">
                <div className="text-white/50 mb-1">Parameters (all optional except query when not sending content):</div>
                query, user_id, username, session_id, top_n, include_search, interrupt_content
              </div>
            </div>

            <div>
              <h3 className="text-lg font-medium text-white mb-2">
                <code className="px-2 py-1 rounded bg-white/10 text-[#90E7EE]">krypton_approve_interrupt</code>
              </h3>
              <p className="text-white/80 text-sm leading-relaxed mb-3">
                Approve or reject an interrupt (e.g. krypton-pay-approval).
                Call this when <code className="font-mono">krypton_query</code> returns{" "}
                <code className="font-mono">stop_reason: &quot;interrupt&quot;</code> with an{" "}
                <code className="font-mono">interrupts</code> array. Pass the
                interrupt id from <code className="font-mono">interrupts[0].id</code>,
                the original query, and <code className="font-mono">approve: true/false</code>.
                <code className="font-mono">user_id</code>, <code className="font-mono">username</code>, and{" "}
                <code className="font-mono">session_id</code> should match the
                original query.
              </p>
              <div className="rounded-xl bg-white/5 border border-white/10 p-4 font-mono text-xs text-white/90 overflow-x-auto">
                <div className="text-white/50 mb-1">Parameters:</div>
                interrupt_id, query, approve (default true), user_id, username, session_id
              </div>
            </div>
          </div>
        </section>

        {/* Functionalities (from Strands) */}
        <section className="mb-12">
          <h2 className="flex items-center gap-2 text-xl font-semibold text-white mb-4">
            <Zap className="h-5 w-5 text-[#90E7EE]" />
            What the orchestrator can do
          </h2>
          <p className="text-white/80 leading-relaxed mb-4">
            The Strands orchestrator behind Clark MCP exposes these skills. You
            send a single natural-language query; the orchestrator chooses which
            tools to call.
          </p>
          <ul className="grid gap-2 text-sm text-white/85">
            <li className="flex items-start gap-2">
              <span className="text-[#90E7EE] font-mono shrink-0">screener</span>
              <span>Crypto screening (price, market cap, technical indicators).</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[#90E7EE] font-mono shrink-0">economic</span>
              <span>Stocks, crypto, forex, commodities, economic indicators, treasury rates, calendar (Financial Modeling Prep).</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[#90E7EE] font-mono shrink-0">regulations</span>
              <span>Tax and regulation information.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[#90E7EE] font-mono shrink-0">backtest</span>
              <span>Strategy backtesting (historical simulations, Sharpe ratio, max drawdown).</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[#90E7EE] font-mono shrink-0">technical</span>
              <span>Technical analysis & charting (RSI, moving averages, Bollinger Bands, ADX, SuperTrend).</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[#90E7EE] font-mono shrink-0">search</span>
              <span>General web search (news, facts, definitions).</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[#90E7EE] font-mono shrink-0">data_fetcher</span>
              <span>Historical OHLCV price data (often used before backtest).</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[#90E7EE] font-mono shrink-0">krypton_pay</span>
              <span>Krypton Pay: balance (current, daily, intraday), k-token price history, swaps, transfers. May trigger human-in-the-loop approval interrupts.</span>
            </li>
          </ul>
        </section>

        {/* Interrupts (HITL) */}
        <section className="mb-12">
          <h2 className="flex items-center gap-2 text-xl font-semibold text-white mb-4">
            <Shield className="h-5 w-5 text-[#90E7EE]" />
            Human-in-the-loop (interrupts)
          </h2>
          <p className="text-white/80 leading-relaxed mb-4">
            For operations that require user approval (e.g. payments), the
            orchestrator can return <code className="font-mono">stop_reason: &quot;interrupt&quot;</code> and an{" "}
            <code className="font-mono">interrupts</code> array (e.g.{" "}
            <code className="font-mono">name: &quot;krypton-pay-approval&quot;</code>).
            Your client should show the user the interrupt details (e.g. amount,
            recipient), then call <code className="font-mono">krypton_approve_interrupt</code> with
            the interrupt id and <code className="font-mono">approve: true</code> or{" "}
            <code className="font-mono">false</code>. The same <code className="font-mono">query</code> and
            session identifiers should be passed so the flow can continue.
          </p>
          <div className="rounded-xl bg-white/5 border border-white/10 p-4 font-mono text-xs text-white/90 overflow-x-auto">
            <pre>{`// Example interrupt response from krypton_query
{
  "stop_reason": "interrupt",
  "interrupts": [{
    "id": "<interrupt-id>",
    "name": "krypton-pay-approval",
    "reason": {
      "receiver_username": "alice",
      "to_token": "USD",
      "received_amount": 10,
      "operation": "direct_transfer"
    }
  }]
}`}</pre>
          </div>
        </section>

        {/* Example query payload */}
        <section className="mb-12">
          <h2 className="flex items-center gap-2 text-xl font-semibold text-white mb-4">
            <Code2 className="h-5 w-5 text-[#90E7EE]" />
            Example query payload
          </h2>
          <p className="text-white/80 text-sm leading-relaxed mb-4">
            What gets sent to the Strands API (via <code className="font-mono">krypton_query</code>) for a normal query:
          </p>
          <div className="rounded-xl bg-white/5 border border-white/10 p-4 font-mono text-xs text-white/90 overflow-x-auto">
            <pre>{`{
  "query": "Find top 5 cryptos with price above $5",
  "user_id": "user123",
  "username": "alice",
  "session_id": "session456",
  "top_n": 5,
  "include_search": true
}`}</pre>
          </div>
          <p className="text-white/70 text-sm mt-4">
            The response includes <code className="font-mono">message</code>,{" "}
            <code className="font-mono">data</code>, <code className="font-mono">agent_flow</code>,{" "}
            <code className="font-mono">parsed_intent</code>, and{" "}
            <code className="font-mono">costs</code>. For interrupt flows, use{" "}
            <code className="font-mono">krypton_approve_interrupt</code> with the
            interrupt id and the same query/session, then continue the
            conversation.
          </p>
        </section>

        <div className="pt-8 border-t border-white/10">
          {/* <Link
            href="/"
            className="inline-flex items-center gap-2 text-[#90E7EE] hover:text-white transition-colors text-sm font-medium"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to home
          </Link> */}
        </div>
      </main>
    </div>
  );
}
