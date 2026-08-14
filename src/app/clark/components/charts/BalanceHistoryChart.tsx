"use client"

import React, { useMemo } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Legend } from 'recharts'
import type { DailyBalanceEntry, IntradayBalanceEntry } from '../../types'
import { chartUi } from '../../constants'

const KNOWN_K_TOKENS = ['kUSD', 'kEUR', 'kGBP', 'kAED'] as const

/** Explicit hex colors - avoid CSS vars that may not resolve for legend/line */
const BALANCE_CHART_COLORS = ['#10b981', '#60a5fa', '#f59e0b', '#ec4899']

/** Canonical token key: merge kAED/KAED/AED/kaed into kAED for consistent plotting */
function canonicalTokenKey(t: string): string {
  const s = (t || '').trim()
  if (!s) return s
  const upper = s.toUpperCase()
  // k-prefixed: kEUR, KAED -> kEUR, kAED
  if (upper.startsWith('K') && ['KEUR', 'KGBP', 'KAED', 'KUSD'].includes(upper)) {
    return 'k' + upper.slice(1)
  }
  // No k prefix: EUR, AED -> kEUR, kAED (merge display format with API format)
  if (['EUR', 'GBP', 'AED', 'USD'].includes(upper)) {
    return 'k' + upper
  }
  return s
}

/** Display token: EUR, GBP, etc. - strip k prefix for user-facing labels */
function displayToken(t: string): string {
  const s = (t || '').trim()
  if (s.toUpperCase().startsWith('K') && ['KEUR', 'KGBP', 'KAED', 'KUSD'].includes(s.toUpperCase())) {
    return s.slice(1)  // kEUR -> EUR
  }
  return s
}

/** Normalize balances to a map token -> numeric balance. Handles array or object. Uses canonical keys for consistency. */
function balancesToMap(balances: unknown): Record<string, number> {
  const out: Record<string, number> = {}
  if (balances == null) return out
  if (Array.isArray(balances)) {
    for (const e of balances as { token?: string; balance?: unknown }[]) {
      const t = e?.token ?? ''
      if (!t) continue
      const b = e?.balance
      const num = typeof b === 'number' ? b : typeof b === 'string' ? parseFloat(String(b)) : NaN
      if (!Number.isNaN(num)) {
        const key = canonicalTokenKey(t)
        out[key] = num
      }
    }
    return out
  }
  if (typeof balances === 'object' && !Array.isArray(balances)) {
    for (const [t, b] of Object.entries(balances as Record<string, unknown>)) {
      if (!t) continue
      const num = typeof b === 'number' ? b : typeof b === 'string' ? parseFloat(String(b)) : NaN
      if (!Number.isNaN(num)) {
        const key = canonicalTokenKey(t)
        out[key] = num
      }
    }
    return out
  }
  return out
}

export type BalanceHistoryChartMode = 'daily' | 'intraday'

interface BalanceHistoryChartProps {
  title: string
  mode: BalanceHistoryChartMode
  dailyBalances?: DailyBalanceEntry[]
  intradayBalances?: IntradayBalanceEntry[]
  username_or_address?: string
}

const formatAxisValue = (value: number) => {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`
  if (value >= 1) return value.toFixed(2)
  return value.toFixed(4)
}

const formatDateShort = (dateStr: string) => {
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  } catch {
    return dateStr
  }
}

const formatTimeShort = (timestamp: string) => {
  try {
    const d = new Date(timestamp)
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return timestamp
  }
}

export default function BalanceHistoryChart({
  title,
  mode,
  dailyBalances = [],
  intradayBalances = [],
  username_or_address,
}: BalanceHistoryChartProps) {
  const isDaily = mode === 'daily'
  const rows = isDaily ? dailyBalances : intradayBalances

  const { chartData, tokens, chartConfig } = useMemo(() => {
    const tokensSet = new Set<string>(KNOWN_K_TOKENS)
    for (const row of rows) {
      const m = balancesToMap(row.balances)
      Object.keys(m).forEach(t => tokensSet.add(t))
    }
    const tokenList = Array.from(tokensSet)

    const data = rows.map((row, i) => {
      const m = balancesToMap(row.balances)
      const label = isDaily
        ? formatDateShort((row as DailyBalanceEntry).date)
        : formatTimeShort((row as IntradayBalanceEntry).timestamp)
      const rawLabel = isDaily
        ? (row as DailyBalanceEntry).date
        : (row as IntradayBalanceEntry).timestamp
      const point: Record<string, string | number> = {
        label,
        rawLabel,
        sortKey: rawLabel,
      }
      for (const t of tokenList) {
        point[t] = m[t] ?? 0
      }
      return point
    })

    // Sort by time
    data.sort((a, b) => String(a.sortKey).localeCompare(String(b.sortKey)))

    const config: Record<string, { label: string; color: string }> = {}
    tokenList.forEach((t, i) => {
      config[t] = {
        label: displayToken(t),
        color: BALANCE_CHART_COLORS[i % BALANCE_CHART_COLORS.length],
      }
    })

    return {
      chartData: data,
      tokens: tokenList,
      chartConfig: config,
    }
  }, [rows, isDaily])

  if (chartData.length === 0 || tokens.length === 0) {
    return (
      <Card className={chartUi.card}>
        <CardHeader>
          <CardTitle className="text-lg text-[var(--kt-text-strong)]">{title}</CardTitle>
          <CardDescription className={chartUi.muted}>
            No balance history data for this period.
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }

  const allValues = chartData.flatMap(d => tokens.map(t => Number(d[t])))
  const rawMin = allValues.length ? Math.min(...allValues) : 0
  const minVal = Math.max(0, rawMin)  // Balance charts: do not extend below zero
  const maxVal = Math.max(...allValues, 0.01)
  const padding = (maxVal - minVal) * 0.05 || 0.01
  const domainMin = Math.max(0, minVal - padding)  // Clamp: never show negative on axis
  const domainMax = maxVal + padding

  return (
    <Card className={chartUi.card}>
      <CardHeader>
        <CardTitle className="text-lg text-[var(--kt-text-strong)]">{title}</CardTitle>
        <CardDescription className={chartUi.muted}>
          {isDaily ? 'Daily' : 'Intraday'} balance history
          {username_or_address ? ` · ${username_or_address}` : ''} · {chartData.length} data points · {tokens.length} token{tokens.length !== 1 ? 's' : ''}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-[380px] w-full">
          <LineChart
            data={chartData}
            margin={{ left: 20, right: 20, top: 10, bottom: 40 }}
          >
            <CartesianGrid
              vertical={false}
              strokeDasharray="3 3"
              stroke="rgba(255, 255, 255, 0.05)"
              className="opacity-50"
            />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              angle={isDaily ? -45 : -35}
              textAnchor="end"
              height={60}
              interval="preserveStartEnd"
              tick={{ fill: '#a1a1aa', fontSize: 10, fontWeight: 300 }}
            />
            <YAxis
              type="number"
              domain={[domainMin, domainMax]}
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              tickFormatter={formatAxisValue}
              tick={{ fill: '#a1a1aa', fontSize: 10, fontWeight: 300 }}
            />
            <ChartTooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null
                const data = payload[0].payload
                return (
                  <ChartTooltipContent className={`${chartUi.tooltip} p-3 min-w-[140px]`}>
                    <p className={`text-xs font-medium mb-2 ${chartUi.muted}`}>
                      {isDaily ? formatDateShort(data.rawLabel) : formatTimeShort(data.rawLabel)}
                    </p>
                    <div className="space-y-1">
                      {tokens.map(t => (
                        <div key={t} className="flex justify-between items-center gap-4">
                          <span className={chartUi.muted}>{displayToken(t)}</span>
                          <span className="text-[var(--kt-text-strong)] font-medium tabular-nums">
                            {formatAxisValue(Number(data[t] ?? 0))}
                          </span>
                        </div>
                      ))}
                    </div>
                  </ChartTooltipContent>
                )
              }}
            />
            <Legend
              wrapperStyle={{ paddingTop: 8 }}
              formatter={(value) => <span className={`text-xs ${chartUi.muted}`}>{value}</span>}
            />
            {tokens.map((token, i) => {
              const color = chartConfig[token]?.color ?? BALANCE_CHART_COLORS[i % BALANCE_CHART_COLORS.length]
              return (
                <Line
                  key={token}
                  type="monotone"
                  dataKey={token}
                  name={displayToken(token)}
                  stroke={color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: color, stroke: color, strokeWidth: 2 }}
                />
              )
            })}
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}
