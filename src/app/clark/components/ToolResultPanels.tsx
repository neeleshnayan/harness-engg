"use client"

/**
 * The tool-result renderers, shared by BOTH chat surfaces.
 *
 * /clark/next mounts them through assistant-ui's tool registry; the classic
 * chat renders them directly from `message.toolResults`. One set of panels,
 * because the whole point is that a backtest looks like the same backtest
 * wherever the answer happens to be read.
 *
 * Every panel draws a tool's ACTUAL return value. A result too big for the
 * stream arrives as null and falls back to its one-line preview — an honest
 * stub, never an invented chart.
 */

import React from 'react'
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
// The Studio's formatters. A chat panel and the Studio panel showing the same
// NAV must format it identically — that is the whole reason this import
// crosses out of /studio (2026-08-20 consolidation).
import { money } from '../studio/format'

const c = {
  surface: 'var(--kt-surface, #14161a)',
  border: 'var(--kt-border, #26292f)',
  text: 'var(--kt-text, #c9ccd1)',
  strong: 'var(--kt-text-strong, #e9e7e2)',
  muted: 'var(--kt-text-muted, #6c727a)',
  up: 'var(--kt-up, #79a98c)',
  down: 'var(--kt-down, #ce7681)',
}

export function Panel({ title, right, children }: {
  title: string; right?: React.ReactNode; children: React.ReactNode
}) {
  return (
    <div className="my-2 rounded-xl border" style={{ borderColor: c.border, background: c.surface }}>
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b px-4 py-2"
           style={{ borderColor: c.border }}>
        <span className="font-mono text-[10px] uppercase tracking-[0.18em]" style={{ color: c.muted }}>
          {title}
        </span>
        {right}
      </div>
      <div className="px-4 py-3">{children}</div>
    </div>
  )
}

export function MiniSeries({ points, up }: { points: { x: string; y: number }[]; up: boolean }) {
  return (
    <div className="h-[120px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <XAxis dataKey="x" tick={{ fill: c.muted, fontSize: 9 }} tickLine={false}
                 stroke={c.border} minTickGap={50} />
          <YAxis domain={['auto', 'auto']} hide />
          <Tooltip contentStyle={{ background: c.surface, border: `1px solid ${c.border}`,
                                   borderRadius: 8, fontSize: 11, color: c.text }} />
          <Area type="monotone" dataKey="y" stroke={up ? c.up : c.down}
                strokeWidth={1.5} fill="transparent" dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

/** The honest stub for a result that did not ship whole. */
export function PreviewOnly({ preview }: { preview?: string }) {
  return <div className="font-mono text-[11px]" style={{ color: c.muted }}>{preview ?? 'no result payload'}</div>
}

// --------------------------------------------------------------------------
//  per-tool panels — each takes the tool's raw result object
// --------------------------------------------------------------------------

export type BarsResult = {
  symbol?: string; source?: string; latest_close?: number; change_pct?: number
  closes?: number[]; dates?: string[]; n_bars?: number; sampled?: boolean
  preview?: string
}

export function BarsPanel({ result }: { result: BarsResult }) {
  if (!result.closes?.length) return <PreviewOnly preview={result?.preview} />
  const up = (result.change_pct ?? 0) >= 0
  const pts = result.closes.map((y, i) => ({ x: result.dates?.[i] ?? String(i), y }))
  return (
    <Panel
      title={`${result.symbol ?? 'bars'} · ${result.n_bars ?? pts.length} bars`}
      right={
        <span className="font-mono text-[12px] tabular-nums" style={{ color: up ? c.up : c.down }}>
          {money(result.latest_close)} · {up ? '+' : ''}{result.change_pct?.toFixed(2)}%
        </span>
      }
    >
      <MiniSeries points={pts} up={up} />
      <div className="mt-1 text-[10px]" style={{ color: c.muted }}>
        {result.source}{result.sampled ? ' · downsampled for display' : ''} — spine market data, not memory
      </div>
    </Panel>
  )
}

export type IndicatorResult = {
  symbol?: string; indicator?: string; period?: number | string; as_of?: string
  latest?: Record<string, number | null>; latest_close?: number
  series_tail?: [string, number | null][]; preview?: string
}

export function IndicatorPanel({ result }: { result: IndicatorResult }) {
  if (!result.latest) return <PreviewOnly preview={result?.preview} />
  const pts = (result.series_tail ?? [])
    .filter((p): p is [string, number] => p[1] != null)
    .map(([x, y]) => ({ x, y }))
  const headline = Object.entries(result.latest)
    .map(([k, v]) => `${k.toUpperCase()} ${v == null ? '—' : v.toFixed(2)}`)
    .join(' · ')
  return (
    <Panel
      title={`${result.symbol} · ${String(result.indicator).toUpperCase()}(${result.period})`}
      right={
        <span className="font-mono text-[13px] tabular-nums" style={{ color: c.strong }}>
          {headline}
        </span>
      }
    >
      {pts.length >= 2 && <MiniSeries points={pts} up />}
      <div className="mt-1 text-[10px]" style={{ color: c.muted }}>
        as of {result.as_of} · close {money(result.latest_close)} · computed from real bars, reported as data not signal
      </div>
    </Panel>
  )
}

export type ScreenResult = {
  n?: number
  coins?: { rank?: number; symbol?: string; name?: string; price_usd?: number;
            market_cap_usd?: number; change_24h_pct?: number }[]
  preview?: string
}

export function ScreenPanel({ result }: { result: ScreenResult }) {
  if (!result.coins?.length) return <PreviewOnly preview={result?.preview} />
  return (
    <Panel title={`crypto screen · ${result.n} matches`}>
      <table className="w-full text-[12px]" style={{ color: c.text }}>
        <thead>
          <tr className="text-left text-[10px] uppercase" style={{ color: c.muted }}>
            <th className="pb-1 font-normal">#</th>
            <th className="pb-1 font-normal">name</th>
            <th className="pb-1 text-right font-normal">price</th>
            <th className="pb-1 text-right font-normal">mcap</th>
            <th className="pb-1 text-right font-normal">24h</th>
          </tr>
        </thead>
        <tbody className="font-mono tabular-nums">
          {result.coins.map((r) => (
            <tr key={r.symbol}>
              <td className="py-0.5" style={{ color: c.muted }}>{r.rank}</td>
              <td className="py-0.5">{r.symbol} <span style={{ color: c.muted }}>{r.name}</span></td>
              <td className="py-0.5 text-right">{money(r.price_usd)}</td>
              <td className="py-0.5 text-right">{r.market_cap_usd == null ? '—' : `$${(r.market_cap_usd / 1e9).toFixed(1)}B`}</td>
              <td className="py-0.5 text-right"
                  style={{ color: (r.change_24h_pct ?? 0) >= 0 ? c.up : c.down }}>
                {r.change_24h_pct == null ? '—' : `${r.change_24h_pct.toFixed(1)}%`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-1 text-[10px]" style={{ color: c.muted }}>live CoinGecko data</div>
    </Panel>
  )
}

export type NavToolResult = {
  live?: { total_nav_usd?: number; breakdown?: { positions?: number; cash?: number } }
  since_inception?: { pnl_usd?: number; return_pct?: number; subscribed_usd?: number }
  preview?: string
}

export function NavPanel({ result }: { result: NavToolResult }) {
  const nav = result.live?.total_nav_usd
  if (nav == null) return <PreviewOnly preview={result?.preview} />
  const si = result.since_inception
  const up = (si?.pnl_usd ?? 0) >= 0
  return (
    <Panel title="fund NAV · from the event log">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <span className="font-mono text-2xl font-light tabular-nums" style={{ color: c.strong }}>
          {money(nav)}
        </span>
        {si && (
          <span className="font-mono text-[12px] tabular-nums" style={{ color: up ? c.up : c.down }}>
            {up ? '+' : '−'}{money(Math.abs(si.pnl_usd ?? 0))} since inception
            {si.return_pct != null && ` · ${si.return_pct.toFixed(2)}% per unit`}
          </span>
        )}
      </div>
      <div className="mt-1 font-mono text-[11px] tabular-nums" style={{ color: c.muted }}>
        positions {money(result.live?.breakdown?.positions)} · cash {money(result.live?.breakdown?.cash)}
      </div>
    </Panel>
  )
}

export type BacktestToolResult = {
  result?: { total_return?: number; sharpe?: number; max_drawdown?: number
             n_trades?: number; equity_curve?: number[]; bars?: number
             costs?: { frictionless?: boolean } }
  strategy?: { name?: string }
  preview?: string
}

export function BacktestPanel({ result }: { result: BacktestToolResult }) {
  const r = result.result
  if (!r?.equity_curve?.length) return <PreviewOnly preview={result?.preview} />
  const up = (r.total_return ?? 0) >= 0
  const pts = r.equity_curve.map((y, i) => ({ x: String(i), y }))
  return (
    <Panel
      title={`backtest · ${r.bars ?? pts.length} bars`}
      right={
        <span className="font-mono text-[12px] tabular-nums" style={{ color: up ? c.up : c.down }}>
          {((r.total_return ?? 0) * 100).toFixed(1)}% · sharpe {r.sharpe?.toFixed(2)} · {r.n_trades} trades
        </span>
      }
    >
      <MiniSeries points={pts} up={up} />
      <div className="mt-1 text-[10px]" style={{ color: c.muted }}>
        max drawdown {((r.max_drawdown ?? 0) * 100).toFixed(1)}%
        {r.costs?.frictionless && ' · NO transaction costs — not a tradeable result'}
      </div>
    </Panel>
  )
}

// --------------------------------------------------------------------------
//  classic-chat entry point: render whatever a message's tools returned
// --------------------------------------------------------------------------

/** Tools with a registered panel; anything else renders nothing here. */
const PANELS: Record<string, (props: { result: never }) => React.ReactNode> = {
  market_bars: BarsPanel as never,
  market_indicator: IndicatorPanel as never,
  crypto_screen: ScreenPanel as never,
  fund_nav: NavPanel as never,
  fund_backtest: BacktestPanel as never,
}

export interface StoredToolResult {
  id: string
  tool: string
  result?: unknown
}

export function ToolResultBlocks({ results }: { results?: StoredToolResult[] }) {
  if (!results?.length) return null
  const renderable = results.filter((r) => r.result != null && PANELS[r.tool])
  if (!renderable.length) return null
  return (
    <>
      {renderable.map((r) => {
        const P = PANELS[r.tool] as (props: { result: unknown }) => React.ReactNode
        return <React.Fragment key={r.id}>{P({ result: r.result })}</React.Fragment>
      })}
    </>
  )
}
