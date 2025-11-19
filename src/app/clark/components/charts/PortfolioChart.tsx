"use client"

import React, { useMemo } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { LineChart, Line, XAxis, YAxis, CartesianGrid } from 'recharts'
import type { DotProps } from 'recharts'
import { BacktestDataPoint, BacktestTrade } from '../../types'
import { chartConfig } from '../../constants'
import { formatDate } from '../../utils'

interface PortfolioChartProps {
  dataPoints: BacktestDataPoint[]
  startDate: string
  endDate: string
  trades?: BacktestTrade[]
}

type TradeBucket = {
  buys: BacktestTrade[]
  sells: BacktestTrade[]
}

const normalizeDate = (value: string) => {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toISOString().slice(0, 10)
}

export default function PortfolioChart({ dataPoints, startDate, endDate, trades }: PortfolioChartProps) {
  const tradesByDate = useMemo(() => {
    if (!trades?.length) {
      return new Map<string, TradeBucket>()
    }

    const buckets = new Map<string, TradeBucket>()
    trades.forEach(trade => {
      if (trade.entry_date) {
        const key = normalizeDate(trade.entry_date)
        const entryBucket = buckets.get(key) ?? { buys: [], sells: [] }
        entryBucket.buys.push(trade)
        buckets.set(key, entryBucket)
      }
      if (trade.exit_date) {
        const key = normalizeDate(trade.exit_date)
        const exitBucket = buckets.get(key) ?? { buys: [], sells: [] }
        exitBucket.sells.push(trade)
        buckets.set(key, exitBucket)
      }
    })

    return buckets
  }, [trades])

  const renderTradeDot = (props: DotProps) => {
    const { cx, cy, payload } = props
    if (typeof cx !== 'number' || typeof cy !== 'number' || !payload?.date) {
      return null
    }
    const bucket = tradesByDate.get(normalizeDate(payload.date))
    if (!bucket) return null

    const hasBuy = bucket.buys.length > 0
    const hasSell = bucket.sells.length > 0
    const circleY = hasSell ? cy + 6 : cy
    const triangleY = cy - 8

    return (
      <g>
        {hasBuy && (
          <circle
            cx={cx}
            cy={circleY}
            r={4}
            fill="#22c55e"
            stroke="#0f172a"
            strokeWidth={1}
          />
        )}
        {hasSell && (
          <path
            d={`M ${cx} ${triangleY} L ${cx - 5} ${triangleY + 10} L ${cx + 5} ${triangleY + 10} Z`}
            fill="#ef4444"
            stroke="#0f172a"
            strokeWidth={1}
          />
        )}
      </g>
    )
  }

  const tooltipLabelFormatter = (value: string | number) => {
    if (typeof value !== 'string') return formatDate(String(value))
    const bucket = tradesByDate.get(normalizeDate(value))
    if (!bucket) return formatDate(value)

    const badges = [
      bucket.buys.length ? `${bucket.buys.length} buy${bucket.buys.length > 1 ? 's' : ''}` : '',
      bucket.sells.length ? `${bucket.sells.length} sell${bucket.sells.length > 1 ? 's' : ''}` : '',
    ].filter(Boolean)

    return badges.length
      ? `${formatDate(value)} • ${badges.join(' & ')}`
      : formatDate(value)
  }

  const tooltipValueFormatter = (value: number | string) => {
    if (typeof value !== 'number') return value
    return `$${value.toLocaleString(undefined, {
      maximumFractionDigits: value >= 1000 ? 0 : 2,
    })}`
  }

  return (
    <Card className="w-full bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
      <CardHeader className="pb-4">
        <CardTitle className="text-lg text-white">Portfolio Performance</CardTitle>
        <CardDescription className="text-zinc-400">
          Portfolio value over time from {formatDate(startDate)} to {formatDate(endDate)}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-[400px] w-full">
          <LineChart data={dataPoints}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
            <XAxis 
              dataKey="date" 
              tickFormatter={(value) => formatDate(value)}
              tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.6)' }}
              axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
              tickLine={{ stroke: 'rgba(255,255,255,0.12)' }}
            />
            <YAxis 
              tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
              tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.6)' }}
              axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
              tickLine={{ stroke: 'rgba(255,255,255,0.12)' }}
            />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  labelFormatter={tooltipLabelFormatter}
                  formatter={(value) => [tooltipValueFormatter(value), chartConfig.portfolio.label]}
                />
              }
            />
            <Line
              type="monotone"
              dataKey="portfolio_value"
              stroke="var(--color-portfolio)"
              strokeWidth={2}
              dot={renderTradeDot}
            />
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}
