"use client"

import React, { useMemo } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { LineChart, Line, XAxis, YAxis, CartesianGrid } from 'recharts'
import { DailyPriceHistoryDataPoint } from '@/lib/api'
import { chartConfig } from '../../constants'
import { formatDate } from '../../utils'

interface PriceHistoryChartProps {
  token: string
  dataPoints: DailyPriceHistoryDataPoint[]
  lookbackDays?: number
}

const formatAxisValue = (value: number) => {
  const abs = Math.abs(value)

  if (abs >= 1_000) {
    return `$${value.toFixed(2)}`
  }

  if (abs >= 1) {
    return `$${value.toFixed(4)}`
  }

  return `$${value.toFixed(6)}`
}

const formatDateShort = (dateStr: string) => {
  try {
    const date = new Date(dateStr)
    const month = date.toLocaleDateString('en-US', { month: 'short' })
    const day = date.getDate()
    return `${month} ${day}`
  } catch {
    return dateStr
  }
}

/** Extract numeric value for chart - supports price, close, portfolio_value (from different data sources) */
function getChartValue(point: Record<string, unknown>): number | null {
  const val = point.price ?? point.close ?? point.portfolio_value
  if (val == null || typeof val !== 'number') return null
  if (Number.isNaN(val)) return null
  return val
}

export default function PriceHistoryChart({ token, dataPoints, lookbackDays }: PriceHistoryChartProps) {
  const chartData = useMemo(() => {
    return (dataPoints || [])
      .map(point => {
        const p = point as Record<string, unknown>
        const value = getChartValue(p)
        if (value === null) return null
        return {
          date: p.date ?? '',
          dateLabel: formatDateShort(String(p.date ?? '')),
          price: parseFloat(Number(value).toFixed(6)),
        }
      })
      .filter((d): d is NonNullable<typeof d> => d != null)
  }, [dataPoints])

  const { domainMin, domainMax } = useMemo(() => {
    if (!chartData.length) {
      return { domainMin: 0, domainMax: 1 }
    }

    const prices = chartData.map(d => d.price)
    const minPrice = Math.min(...prices)
    const maxPrice = Math.max(...prices)
    const priceRange = maxPrice - minPrice

    // 5% padding above max price and below min price
    const padding = priceRange * 0.05

    // Domain should start 5% below min price and end 5% above max price
    const domainMin = Math.max(0, minPrice - padding) // Prevent negative values
    const domainMax = maxPrice + padding

    return { domainMin, domainMax }
  }, [chartData])

  const currentPrice = useMemo(() => {
    if (chartData.length === 0) return null
    return chartData[chartData.length - 1].price
  }, [chartData])

  const priceChange = useMemo(() => {
    if (chartData.length < 2) return null
    const firstPrice = chartData[0].price
    const lastPrice = chartData[chartData.length - 1].price
    const change = lastPrice - firstPrice
    const changePercent = firstPrice > 0 ? (change / firstPrice) * 100 : 0
    return { change, changePercent }
  }, [chartData])

  if (!chartData.length) {
    return (
      <Card className="w-full bg-teal-800/20 border-teal-700/30 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-lg text-white">Price History - {token}</CardTitle>
          <CardDescription className="text-teal-200/70">
            No price data available
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }

  return (
    <Card className="w-full bg-teal-800/20 border-teal-700/30 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="text-lg text-white">Price History - {token}</CardTitle>
        <CardDescription className="text-teal-200/70">
          {lookbackDays ? `Last ${lookbackDays} days` : 'Daily price history'} • {chartData.length} data points
        </CardDescription>
        {currentPrice !== null && (
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-semibold text-white">
              {formatAxisValue(currentPrice)}
            </span>
            {priceChange && (
              <span
                className={`text-sm font-medium ${
                  priceChange.change >= 0 ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {priceChange.change >= 0 ? '+' : ''}
                {priceChange.changePercent.toFixed(2)}%
              </span>
            )}
          </div>
        )}
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-[400px] w-full">
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
              dataKey="dateLabel"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              angle={-45}
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
                  <ChartTooltipContent className="bg-zinc-900/95 border border-teal-700/50 rounded-lg p-3 shadow-lg">
                    <div className="space-y-1">
                      <p className="text-xs text-teal-300/80 font-medium">
                        {formatDate(data.date)}
                      </p>
                      <p className="text-sm font-semibold text-white">
                        Price: {formatAxisValue(data.price)}
                      </p>
                    </div>
                  </ChartTooltipContent>
                )
              }}
            />
            <Line
              type="monotone"
              dataKey="price"
              stroke="#10b981"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: '#10b981', stroke: '#10b981', strokeWidth: 2 }}
            />
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}
