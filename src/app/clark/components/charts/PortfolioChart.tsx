"use client"

import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { LineChart, Line, XAxis, YAxis, CartesianGrid } from 'recharts'
import { BacktestDataPoint } from '../../types'
import { chartConfig } from '../../constants'
import { formatDate } from '../../utils'

interface PortfolioChartProps {
  dataPoints: BacktestDataPoint[]
  startDate: string
  endDate: string
}

export default function PortfolioChart({ dataPoints, startDate, endDate }: PortfolioChartProps) {
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
            <ChartTooltip content={<ChartTooltipContent />} />
            <Line
              type="monotone"
              dataKey="portfolio_value"
              stroke="var(--color-portfolio)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}
