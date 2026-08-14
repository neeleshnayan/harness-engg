"use client"

import React, { useMemo } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts'
import { PieChart as PieChartIcon, BarChart3 } from 'lucide-react'
import { BacktestAllocation } from '../../types'
import { chartConfig, allocationColors, chartUi } from '../../constants'

interface AllocationChartsProps {
  allocations?: BacktestAllocation[]
  symbol?: string
  targetAssets?: string[]
  totalReturn?: number
}

const RETURN_COLORS = {
  positive: '#22c55e',
  negative: '#ef4444',
} as const

export default function AllocationCharts({ allocations, symbol, targetAssets, totalReturn }: AllocationChartsProps) {
  const effectiveAllocations = useMemo<BacktestAllocation[]>(() => {
    if (Array.isArray(allocations) && allocations.length > 0) {
      return allocations
    }

    const sym = symbol || (Array.isArray(targetAssets) && targetAssets[0]) || 'GLD'
    const ret = typeof totalReturn === 'number' ? totalReturn : 0

    return [
      {
        symbol: String(sym).toUpperCase(),
        allocation_percentage: 100,
        total_return: ret,
        final_value: 0,
      },
    ]
  }, [allocations, symbol, targetAssets, totalReturn])

  if (!effectiveAllocations.length) {
    return null
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 w-full mt-4">
      <Card className={chartUi.card}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-[var(--kt-text-strong)] text-base font-semibold">
            <PieChartIcon className="h-5 w-5 text-[var(--kt-accent)]" />
            Portfolio Allocation
          </CardTitle>
          <CardDescription className={chartUi.muted}>
            Final allocation percentages by asset
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={chartConfig} className="h-[280px] w-full">
            <PieChart style={{ background: 'transparent' }}>
              <Pie
                data={effectiveAllocations}
                dataKey="allocation_percentage"
                nameKey="symbol"
                cx="50%"
                cy="50%"
                outerRadius={90}
                labelLine={{ stroke: 'rgba(255,255,255,0.25)' }}
                label={(props) => {
                  const RADIAN = Math.PI / 180
                  const {
                    cx, cy, midAngle, outerRadius,
                    percent, name, symbol, allocation_percentage
                  } = props as any
                  const radius = outerRadius + 12
                  const x = cx + radius * Math.cos(-midAngle * RADIAN)
                  const y = cy + radius * Math.sin(-midAngle * RADIAN)
                  const val = allocation_percentage !== undefined ? allocation_percentage : (percent ?? 1) * 100
                  const labelText = `${(symbol || name || 'Asset')}: ${val.toFixed(1)}%`
                  return (
                    <text
                      x={x}
                      y={y}
                      fill="rgba(255,255,255,0.9)"
                      textAnchor={x > cx ? 'start' : 'end'}
                      dominantBaseline="central"
                      fontSize={12}
                      fontWeight={500}
                    >
                      {labelText}
                    </text>
                  )
                }}
              >
                {effectiveAllocations.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={allocationColors[index % allocationColors.length]} />
                ))}
              </Pie>
              <ChartTooltip content={<ChartTooltipContent />} />
            </PieChart>
          </ChartContainer>
        </CardContent>
      </Card>

      <Card className={chartUi.card}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-[var(--kt-text-strong)] text-base font-semibold">
            <BarChart3 className="h-5 w-5 text-[var(--kt-accent)]" />
            Asset Performance
          </CardTitle>
          <CardDescription className={chartUi.muted}>
            Individual asset returns during backtest period
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={chartConfig} className="h-[280px] w-full">
            <BarChart data={effectiveAllocations} style={{ background: 'transparent' }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis 
                dataKey="symbol" 
                tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.7)' }}
                axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                tickLine={{ stroke: 'rgba(255,255,255,0.12)' }}
              />
              <YAxis 
                tickFormatter={(value) => `${value.toFixed(1)}%`}
                tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.7)' }}
                axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                tickLine={{ stroke: 'rgba(255,255,255,0.12)' }}
              />
              <Bar dataKey="total_return" fill={RETURN_COLORS.positive}>
                {effectiveAllocations.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={(entry.total_return ?? 0) >= 0 ? RETURN_COLORS.positive : RETURN_COLORS.negative}
                  />
                ))}
              </Bar>
            </BarChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </div>
  )
}
