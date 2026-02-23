"use client"

import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts'
import { PieChart as PieChartIcon } from 'lucide-react'
import { BacktestAllocation } from '../../types'
import { chartConfig, allocationColors, chartUi } from '../../constants'

interface AllocationChartsProps {
  allocations: BacktestAllocation[]
}

const RETURN_COLORS = {
  positive: '#22c55e',
  negative: '#ef4444',
} as const

export default function AllocationCharts({ allocations }: AllocationChartsProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 w-full">
      <Card className={chartUi.card}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-white">
            <PieChartIcon className="h-5 w-5" />
            Portfolio Allocation
          </CardTitle>
          <CardDescription className={chartUi.muted}>
            Final allocation percentages by asset
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={chartConfig} className="h-[300px] w-full">
            <PieChart style={{ background: 'transparent' }}>
              <Pie
                data={allocations}
                dataKey="allocation_percentage"
                nameKey="symbol"
                cx="50%"
                cy="50%"
                outerRadius={100}
                labelLine={{ stroke: 'rgba(255,255,255,0.25)' }}
                label={(props) => {
                  const RADIAN = Math.PI / 180
                  const {
                    cx, cy, midAngle, outerRadius,
                    percent, name, symbol, allocation_percentage
                  } = props as any
                  const radius = outerRadius + 10
                  const x = cx + radius * Math.cos(-midAngle * RADIAN)
                  const y = cy + radius * Math.sin(-midAngle * RADIAN)
                  const labelText = `${(symbol || name)}: ${(
                    allocation_percentage !== undefined ? allocation_percentage : percent * 100
                  ).toFixed(1)}%`
                  return (
                    <text
                      x={x}
                      y={y}
                      fill="rgba(255,255,255,0.85)"
                      textAnchor={x > cx ? 'start' : 'end'}
                      dominantBaseline="central"
                      fontSize={12}
                    >
                      {labelText}
                    </text>
                  )
                }}
              >
                {allocations.map((_, index) => (
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
          <CardTitle className=' text-white'>Asset Performance</CardTitle>
          <CardDescription className={chartUi.muted}>
            Individual asset returns during backtest period
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={chartConfig} className="h-[300px] w-full">
            <BarChart data={allocations} style={{ background: 'transparent' }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis 
                dataKey="symbol" 
                tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.6)' }}
                angle={-45}
                textAnchor="end"
                height={80}
                axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                tickLine={{ stroke: 'rgba(255,255,255,0.12)' }}
              />
              <YAxis 
                tickFormatter={(value) => `${value.toFixed(1)}%`}
                tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.6)' }}
                axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                tickLine={{ stroke: 'rgba(255,255,255,0.12)' }}
              />
              <Bar dataKey="total_return" fill={RETURN_COLORS.positive}>
                {allocations.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.total_return >= 0 ? RETURN_COLORS.positive : RETURN_COLORS.negative}
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
