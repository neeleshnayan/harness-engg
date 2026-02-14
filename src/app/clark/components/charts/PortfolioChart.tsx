"use client"

import React, { useMemo } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { LineChart, Line, XAxis, YAxis, CartesianGrid } from 'recharts'
import type { DotProps } from 'recharts'
import type { ValueType, NameType } from 'recharts/types/component/DefaultTooltipContent'
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

type TradeDotProps = DotProps & {
  payload?: BacktestDataPoint
}

const formatAxisValue = (value: number) => {
  const abs = Math.abs(value)

  if (abs >= 1_000_000) {
    const decimals = abs >= 10_000_000 ? 0 : 1
    return `$${(value / 1_000_000).toFixed(decimals)}M`
  }

  if (abs >= 1_000) {
    const decimals = abs >= 10_000 ? 0 : 1
    return `$${(value / 1_000).toFixed(decimals)}k`
  }

  if (abs >= 100) {
    return `$${value.toFixed(0)}`
  }

  if (abs >= 1) {
    return `$${value.toFixed(2)}`
  }

  return `$${value.toFixed(2)}`
}

export default function PortfolioChart({ dataPoints, startDate, endDate, trades }: PortfolioChartProps) {
  const { domainMin, domainMax } = useMemo(() => {
    if (!dataPoints.length) {
      return { domainMin: 0, domainMax: 1 }
    }

    let minValue = Number.POSITIVE_INFINITY
    let maxValue = Number.NEGATIVE_INFINITY

    dataPoints.forEach(point => {
      if (typeof point.portfolio_value === 'number') {
        if (point.portfolio_value < minValue) minValue = point.portfolio_value
        if (point.portfolio_value > maxValue) maxValue = point.portfolio_value
      }
    })

    if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) {
      return { domainMin: 0, domainMax: 1 }
    }

    const range = maxValue - minValue
    const padding = range > 0 ? range * 0.5 : Math.max(minValue * 0.5, 1)
    const lowerBound = Math.max(0, minValue - padding)
    const upperBound = maxValue + padding

    return { domainMin: lowerBound, domainMax: upperBound }
  }, [dataPoints])

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

  const renderTradeDot = (props: TradeDotProps) => {
    const { cx, cy, payload } = props
    const fallbackKey = `${cx ?? 0}-${cy ?? 0}`
    if (typeof cx !== 'number' || typeof cy !== 'number' || !payload?.date) {
      return <g key={fallbackKey} />
    }
    const bucket = tradesByDate.get(normalizeDate(payload.date))
    if (!bucket) return <g key={fallbackKey} />

    const hasBuy = bucket.buys.length > 0
    const hasSell = bucket.sells.length > 0
    const circleY = hasSell ? cy + 6 : cy
    const triangleY = cy - 8
    const key = `${payload.date}-${cx}-${cy}`

    return (
      <g key={key}>
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

  const tooltipValueFormatter = (
    value: ValueType,
    name?: NameType
  ): [string, string] => {
    const label = chartConfig.portfolio.label || 'Portfolio Value'
    if (typeof value !== 'number') {
      return [String(value ?? ''), label]
    }
    const formatted = `$${value.toLocaleString(undefined, {
      maximumFractionDigits: value >= 1000 ? 0 : 2,
    })}`
    return [formatted, label]
  }

  return (
    <Card className="w-full bg-teal-800/20 border-teal-700/30 backdrop-blur-sm">
      <CardHeader className="pb-4">
        <CardTitle className="text-lg text-white">Portfolio Performance</CardTitle>
        <CardDescription className="text-teal-200/70">
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
              tickFormatter={formatAxisValue}
              tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.6)' }}
              axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
              tickLine={{ stroke: 'rgba(255,255,255,0.12)' }}
              domain={[domainMin, domainMax]}
            />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  labelFormatter={tooltipLabelFormatter}
                  formatter={tooltipValueFormatter}
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
