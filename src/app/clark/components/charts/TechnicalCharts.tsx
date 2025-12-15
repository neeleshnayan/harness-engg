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

  const stochRsiData = dataPoints.filter(dp =>
    dp.technical_indicators?.stochastic_rsi_k !== null && dp.technical_indicators?.stochastic_rsi_k !== undefined
  ).map(dp => {
    const raw = dp.technical_indicators?.stochastic_rsi
    const k = dp.technical_indicators?.stochastic_rsi_k
    const d = dp.technical_indicators?.stochastic_rsi_d
    return {
      ...dp,
      stochastic_rsi: raw !== null && raw !== undefined ? Number(raw) * 100 : null,
      stochastic_rsi_k: k !== null && k !== undefined ? Number(k) * 100 : null,
      stochastic_rsi_d: d !== null && d !== undefined ? Number(d) * 100 : null,
    }
  }).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

  const bollingerData = dataPoints.filter(dp => 
    dp.technical_indicators?.bb_upper !== null && dp.technical_indicators?.bb_upper !== undefined
  ).map(dp => ({
    ...dp,
    bb_upper: Number(dp.technical_indicators?.bb_upper),
    bb_middle: Number(dp.technical_indicators?.bb_middle),
    bb_lower: Number(dp.technical_indicators?.bb_lower),
    price: dp.technical_indicators?.current_price !== undefined && dp.technical_indicators?.current_price !== null
      ? Number(dp.technical_indicators.current_price)
      : null
  })).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

  const superTrendData = dataPoints.filter(dp => 
    dp.technical_indicators?.super_trend !== null && dp.technical_indicators?.super_trend !== undefined
  ).map(dp => ({
    ...dp,
    super_trend: Number(dp.technical_indicators?.super_trend),
    super_trend_direction: dp.technical_indicators?.super_trend_direction,
    price: dp.technical_indicators?.current_price !== undefined && dp.technical_indicators?.current_price !== null
      ? Number(dp.technical_indicators.current_price)
      : null
  })).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

  const adxData = dataPoints.filter(dp => 
    dp.technical_indicators?.adx !== null && dp.technical_indicators?.adx !== undefined
  ).map(dp => ({
    ...dp,
    adx: dp.technical_indicators?.adx !== null && dp.technical_indicators?.adx !== undefined
      ? Number(dp.technical_indicators.adx)
      : null,
    adx_plus_dmi: dp.technical_indicators?.adx_plus_dmi !== null && dp.technical_indicators?.adx_plus_dmi !== undefined
      ? Number(dp.technical_indicators.adx_plus_dmi)
      : null,
    adx_minus_dmi: dp.technical_indicators?.adx_minus_dmi !== null && dp.technical_indicators?.adx_minus_dmi !== undefined
      ? Number(dp.technical_indicators.adx_minus_dmi)
      : null,
  })).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

  return (
    <div className="space-y-6">
      {/* Moving Averages Chart */}
      {(
        technicalIndicatorsRequested.includes('dma_30') ||
        technicalIndicatorsRequested.includes('dma_100') ||
        technicalIndicatorsRequested.includes('dma_200') ||
        technicalIndicatorsRequested.includes('sma_30') ||
        technicalIndicatorsRequested.includes('sma_100') ||
        technicalIndicatorsRequested.includes('sma_200')
      ) && (
        <Card className="w-full bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-lg text-white">Moving Averages Analysis</CardTitle>
            <CardDescription className="text-zinc-400">
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
                {(technicalIndicatorsRequested.includes('dma_30') || technicalIndicatorsRequested.includes('sma_30')) && (
                  <Line
                    type="monotone"
                    dataKey="sma_30"
                    stroke="var(--color-sma_30)"
                    strokeWidth={2}
                    dot={false}
                    name="30-day SMA"
                  />
                )}
                {(technicalIndicatorsRequested.includes('dma_100') || technicalIndicatorsRequested.includes('sma_100')) && (
                  <Line
                    type="monotone"
                    dataKey="sma_100"
                    stroke="var(--color-sma_100)"
                    strokeWidth={2}
                    dot={false}
                    name="100-day SMA"
                  />
                )}
                {(technicalIndicatorsRequested.includes('dma_200') || technicalIndicatorsRequested.includes('sma_200')) && (
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
        <Card className="w-full bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-lg text-white">Relative Strength Index (RSI)</CardTitle>
            <CardDescription className="text-zinc-400">
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
                  stroke="var(--color-rsi)"
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

      {/* Stochastic RSI Chart */}
      {technicalIndicatorsRequested.includes('stochastic_rsi') && (
        <Card className="w-full bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-lg text-white">Stochastic RSI Oscillator</CardTitle>
            <CardDescription className="text-zinc-400">
              Stochastic RSI %K and %D with overbought (80) and oversold (20) levels for {targetAssets.length > 0 ? targetAssets.join(', ') : 'selected assets'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={chartConfig} className="h-[300px] w-full">
              <LineChart data={stochRsiData}>
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
                  dataKey="stochastic_rsi_k"
                  stroke="var(--color-stochastic_rsi_k)"
                  strokeWidth={2}
                  dot={false}
                  name="Stoch RSI %K"
                  connectNulls={false}
                  isAnimationActive={true}
                />
                <Line
                  type="monotone"
                  dataKey="stochastic_rsi_d"
                  stroke="var(--color-stochastic_rsi_d)"
                  strokeWidth={2}
                  dot={false}
                  name="Stoch RSI %D"
                  connectNulls={false}
                  isAnimationActive={true}
                />
                <Line
                  type="monotone"
                  dataKey="stochastic_rsi"
                  stroke="var(--color-stochastic_rsi)"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                  dot={false}
                  name="Stoch RSI (Raw)"
                  connectNulls={false}
                  isAnimationActive={true}
                />
                <Line
                  type="monotone"
                  dataKey={() => 80}
                  stroke="#f97316"
                  strokeWidth={1}
                  strokeDasharray="3 3"
                  dot={false}
                  name="Overbought (80)"
                />
                <Line
                  type="monotone"
                  dataKey={() => 20}
                  stroke="#38bdf8"
                  strokeWidth={1}
                  strokeDasharray="3 3"
                  dot={false}
                  name="Oversold (20)"
                />
              </LineChart>
            </ChartContainer>
          </CardContent>
        </Card>
      )}

      {/* Bollinger Bands Chart */}
      {technicalIndicatorsRequested.includes('bollinger_bands') && (
        <Card className="w-full bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-lg text-white">Bollinger Bands Analysis</CardTitle>
            <CardDescription className="text-zinc-400">
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
                  stroke="var(--color-bb_upper)"
                  strokeWidth={2}
                  dot={false}
                  name="Upper Band"
                  connectNulls={false}
                  isAnimationActive={true}
                />
                <Line
                  type="monotone"
                  dataKey="bb_middle"
                  stroke="var(--color-bb_middle)"
                  strokeWidth={2}
                  dot={false}
                  name="Middle Band (SMA)"
                  connectNulls={false}
                  isAnimationActive={true}
                />
                <Line
                  type="monotone"
                  dataKey="bb_lower"
                  stroke="var(--color-bb_lower)"
                  strokeWidth={2}
                  dot={false}
                  name="Lower Band"
                  connectNulls={false}
                  isAnimationActive={true}
                />
                <Line
                  type="monotone"
                  dataKey="price"
                  stroke="var(--color-price)"
                  strokeWidth={2}
                  dot={false}
                  name="Price"
                  connectNulls={false}
                  isAnimationActive={true}
                />
              </LineChart>
            </ChartContainer>
          </CardContent>
        </Card>
      )}

      {/* Super Trend Chart */}
      {(technicalIndicatorsRequested.includes('super_trend') || technicalIndicatorsRequested.includes('supertrend')) && (
        <Card className="w-full bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-lg text-white">Super Trend Analysis</CardTitle>
            <CardDescription className="text-zinc-400">
              Super Trend indicator (volatility adjusted trend levels) for {targetAssets.length > 0 ? targetAssets.join(', ') : 'selected assets'}.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={chartConfig} className="h-[400px] w-full">
              <LineChart data={superTrendData}>
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
                  dataKey="super_trend"
                  stroke="var(--color-super_trend)"
                  strokeWidth={2}
                  dot={false}
                  name="Super Trend"
                  connectNulls={false}
                  isAnimationActive={true}
                />
                <Line
                  type="monotone"
                  dataKey="price"
                  stroke="var(--color-price)"
                  strokeWidth={2}
                  dot={false}
                  name="Price"
                  connectNulls={false}
                  isAnimationActive={true}
                />
              </LineChart>
            </ChartContainer>
          </CardContent>
        </Card>
      )}

      {/* ADX Chart */}
      {(technicalIndicatorsRequested.includes('adx') || 
        technicalIndicatorsRequested.includes('adx_plus_dmi') || 
        technicalIndicatorsRequested.includes('adx_minus_dmi')) && (
        <Card className="w-full bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-lg text-white">Average Directional Index (ADX)</CardTitle>
            <CardDescription className="text-zinc-400">
              ADX with +DMI (Positive Directional Movement) and -DMI (Negative Directional Movement) for {targetAssets.length > 0 ? targetAssets.join(', ') : 'selected assets'}.
              ADX measures trend strength, +DMI shows upward momentum, -DMI shows downward momentum.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={chartConfig} className="h-[400px] w-full">
              <LineChart data={adxData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                <XAxis 
                  dataKey="date" 
                  tickFormatter={(value) => formatDate(value)}
                  tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.6)' }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                  tickLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                />
                <YAxis 
                  tick={{ fontSize: 12, fill: 'rgba(255,255,255,0.6)' }}
                  axisLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                  tickLine={{ stroke: 'rgba(255,255,255,0.12)' }}
                />
                <ChartTooltip content={<ChartTooltipContent />} />
                {(technicalIndicatorsRequested.includes('adx') || 
                  technicalIndicatorsRequested.includes('adx_plus_dmi') || 
                  technicalIndicatorsRequested.includes('adx_minus_dmi')) && (
                  <Line
                    type="monotone"
                    dataKey="adx"
                    stroke="var(--color-adx)"
                    strokeWidth={2}
                    dot={false}
                    name="ADX"
                    connectNulls={false}
                    isAnimationActive={true}
                  />
                )}
                {(technicalIndicatorsRequested.includes('adx') || 
                  technicalIndicatorsRequested.includes('adx_plus_dmi')) && (
                  <Line
                    type="monotone"
                    dataKey="adx_plus_dmi"
                    stroke="var(--color-adx_plus_dmi)"
                    strokeWidth={2}
                    dot={false}
                    name="+DMI"
                    connectNulls={false}
                    isAnimationActive={true}
                  />
                )}
                {(technicalIndicatorsRequested.includes('adx') || 
                  technicalIndicatorsRequested.includes('adx_minus_dmi')) && (
                  <Line
                    type="monotone"
                    dataKey="adx_minus_dmi"
                    stroke="var(--color-adx_minus_dmi)"
                    strokeWidth={2}
                    dot={false}
                    name="-DMI"
                    connectNulls={false}
                    isAnimationActive={true}
                  />
                )}
                {/* Reference lines for ADX trend strength */}
                {technicalIndicatorsRequested.includes('adx') && (
                  <>
                    <Line
                      type="monotone"
                      dataKey={() => 20}
                      stroke="#fbbf24"
                      strokeWidth={1}
                      strokeDasharray="3 3"
                      dot={false}
                      name="Strong Trend (20)"
                    />
                    <Line
                      type="monotone"
                      dataKey={() => 25}
                      stroke="#f59e0b"
                      strokeWidth={1}
                      strokeDasharray="3 3"
                      dot={false}
                      name="Very Strong Trend (25)"
                    />
                  </>
                )}
              </LineChart>
            </ChartContainer>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
