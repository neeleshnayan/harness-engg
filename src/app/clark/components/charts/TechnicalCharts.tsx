"use client"

import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { LineChart, Line, XAxis, YAxis, CartesianGrid } from 'recharts'
import { BacktestDataPoint } from '../../types'
import { chartConfig } from '../../constants'
import { formatDate } from '../../utils'

interface TechnicalChartsProps {
  dataPoints: BacktestDataPoint[]
  technicalIndicatorsRequested: string[]
  targetAssets: string[]
}

export default function TechnicalCharts({ 
  dataPoints, 
  technicalIndicatorsRequested, 
  targetAssets 
}: TechnicalChartsProps) {
  const filteredData = dataPoints.filter(dp => 
    dp.technical_indicators?.sma_30 !== null && dp.technical_indicators?.sma_30 !== undefined
  ).map(dp => ({
    ...dp,
    sma_30: dp.technical_indicators?.sma_30,
    sma_100: dp.technical_indicators?.sma_100,
    sma_200: dp.technical_indicators?.sma_200
  }))

  const rsiData = dataPoints.filter(dp => 
    dp.technical_indicators?.rsi !== null && dp.technical_indicators?.rsi !== undefined
  ).map(dp => ({
    ...dp,
    rsi: Number(dp.technical_indicators?.rsi)
  })).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

  const bollingerData = dataPoints.filter(dp => 
    dp.technical_indicators?.bb_upper !== null && dp.technical_indicators?.bb_upper !== undefined
  ).map(dp => ({
    ...dp,
    bb_upper: Number(dp.technical_indicators?.bb_upper),
    bb_middle: Number(dp.technical_indicators?.bb_middle),
    bb_lower: Number(dp.technical_indicators?.bb_lower)
  })).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

  return (
    <div className="space-y-6">
      {/* Moving Averages Chart */}
      {(technicalIndicatorsRequested.includes('dma_30') || 
        technicalIndicatorsRequested.includes('dma_100') || 
        technicalIndicatorsRequested.includes('dma_200')) && (
        <Card className="w-full">
          <CardHeader>
            <CardTitle>Moving Averages Analysis</CardTitle>
            <CardDescription>
              Simple Moving Averages (SMA) for {targetAssets.length > 0 ? targetAssets.join(', ') : 'selected assets'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={chartConfig} className="h-[400px] w-full">
              <LineChart data={filteredData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                <XAxis 
                  dataKey="date" 
                  tickFormatter={(value) => formatDate(value)}
                  tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.6)' }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                  tickLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                />
                <YAxis 
                  tickFormatter={(value) => `$${value.toFixed(0)}`}
                  tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.6)' }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                  tickLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                />
                <ChartTooltip content={<ChartTooltipContent />} />
                {technicalIndicatorsRequested.includes('dma_30') && (
                  <Line
                    type="monotone"
                    dataKey="sma_30"
                    stroke="var(--color-sma_30)"
                    strokeWidth={2}
                    dot={false}
                    name="30-day SMA"
                  />
                )}
                {technicalIndicatorsRequested.includes('dma_100') && (
                  <Line
                    type="monotone"
                    dataKey="sma_100"
                    stroke="var(--color-sma_100)"
                    strokeWidth={2}
                    dot={false}
                    name="100-day SMA"
                  />
                )}
                {technicalIndicatorsRequested.includes('dma_200') && (
                  <Line
                    type="monotone"
                    dataKey="sma_200"
                    stroke="var(--color-sma_200)"
                    strokeWidth={2}
                    dot={false}
                    name="200-day SMA"
                  />
                )}
              </LineChart>
            </ChartContainer>
          </CardContent>
        </Card>
      )}

      {/* RSI Chart */}
      {technicalIndicatorsRequested.includes('rsi') && (
        <Card className="w-full">
          <CardHeader>
            <CardTitle>Relative Strength Index (RSI)</CardTitle>
            <CardDescription>
              RSI with overbought (70) and oversold (30) levels for {targetAssets.length > 0 ? targetAssets.join(', ') : 'selected assets'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={chartConfig} className="h-[300px] w-full">
              <LineChart data={rsiData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                <XAxis 
                  dataKey="date" 
                  tickFormatter={(value) => formatDate(value)}
                  tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.6)' }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                  tickLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                />
                <YAxis 
                  domain={[0, 100]}
                  tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.6)' }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                  tickLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Line
                  type="monotone"
                  dataKey="rsi"
                  stroke="#8884d8"
                  strokeWidth={2}
                  dot={false}
                  name="RSI"
                  connectNulls={false}
                  isAnimationActive={true}
                />
                {/* Reference lines for overbought/oversold */}
                <Line
                  type="monotone"
                  dataKey={() => 70}
                  stroke="#ef4444"
                  strokeWidth={1}
                  strokeDasharray="3 3"
                  dot={false}
                  name="Overbought (70)"
                />
                <Line
                  type="monotone"
                  dataKey={() => 30}
                  stroke="#ef4444"
                  strokeWidth={1}
                  strokeDasharray="3 3"
                  dot={false}
                  name="Oversold (30)"
                />
              </LineChart>
            </ChartContainer>
          </CardContent>
        </Card>
      )}

      {/* Bollinger Bands Chart */}
      {technicalIndicatorsRequested.includes('bollinger_bands') && (
        <Card className="w-full">
          <CardHeader>
            <CardTitle>Bollinger Bands Analysis</CardTitle>
            <CardDescription>
              Bollinger Bands (20-period, 2 standard deviations) for volatility analysis of {targetAssets.length > 0 ? targetAssets.join(', ') : 'selected assets'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={chartConfig} className="h-[400px] w-full">
              <LineChart data={bollingerData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                <XAxis 
                  dataKey="date" 
                  tickFormatter={(value) => formatDate(value)}
                  tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.6)' }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                  tickLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                />
                <YAxis 
                  tickFormatter={(value) => `$${value.toFixed(0)}`}
                  tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.6)' }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                  tickLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Line
                  type="monotone"
                  dataKey="bb_upper"
                  stroke="#8884d8"
                  strokeWidth={2}
                  dot={false}
                  name="Upper Band"
                  connectNulls={false}
                  isAnimationActive={true}
                />
                <Line
                  type="monotone"
                  dataKey="bb_middle"
                  stroke="#82ca9d"
                  strokeWidth={2}
                  dot={false}
                  name="Middle Band (SMA)"
                  connectNulls={false}
                  isAnimationActive={true}
                />
                <Line
                  type="monotone"
                  dataKey="bb_lower"
                  stroke="#ffc658"
                  strokeWidth={2}
                  dot={false}
                  name="Lower Band"
                  connectNulls={false}
                  isAnimationActive={true}
                />
              </LineChart>
            </ChartContainer>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
