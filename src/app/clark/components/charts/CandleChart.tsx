"use client"

import React, { useMemo, useRef, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { CandleData, CandleDataPoint } from '../../types'
import { formatDate } from '../../utils'

interface CandleChartProps {
  candleData: CandleData
  title?: string
}

interface CandleChartDataPoint {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume?: number | null
  isUp: boolean
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

  return `$${value.toFixed(4)}`
}

export default function CandleChart({ candleData, title }: CandleChartProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [hoveredCandle, setHoveredCandle] = React.useState<CandleChartDataPoint | null>(null)
  const [tooltipPosition, setTooltipPosition] = React.useState<{ x: number; y: number } | null>(null)

  const chartData = useMemo<CandleChartDataPoint[]>(() => {
    if (!candleData?.candles?.length) return []

    return candleData.candles.map((candle: CandleDataPoint) => {
      // Ensure all values are numbers
      const open = Number(candle.open)
      const close = Number(candle.close)
      const high = Number(candle.high)
      const low = Number(candle.low)
      
      // Determine if candle is up (close > open) or down (close < open)
      // If equal, treat as down (red) to be more conservative
      const isUp = close > open
      
      return {
        date: candle.date,
        open,
        high,
        low,
        close,
        volume: candle.volume,
        isUp,
      }
    })
  }, [candleData])

  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = React.useState(800)

  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.offsetWidth)
      }
    }
    updateWidth()
    window.addEventListener('resize', updateWidth)
    return () => window.removeEventListener('resize', updateWidth)
  }, [])

  const { domainMin, domainMax, width, height, margin } = useMemo(() => {
    const calculatedWidth = Math.max(600, containerWidth - 40) // Account for padding
    const calculatedHeight = 400
    const calculatedMargin = { top: 20, right: 20, bottom: 60, left: 80 }

    if (!chartData.length) {
      return { domainMin: 0, domainMax: 1, width: calculatedWidth, height: calculatedHeight, margin: calculatedMargin }
    }

    let minValue = Number.POSITIVE_INFINITY
    let maxValue = Number.NEGATIVE_INFINITY

    chartData.forEach(point => {
      if (point.low < minValue) minValue = point.low
      if (point.high > maxValue) maxValue = point.high
    })

    if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) {
      return { domainMin: 0, domainMax: 1, width: calculatedWidth, height: calculatedHeight, margin: calculatedMargin }
    }

    const range = maxValue - minValue
    const padding = range * 0.1 // 10% padding
    const lowerBound = Math.max(0, minValue - padding)
    const upperBound = maxValue + padding

    return {
      domainMin: lowerBound,
      domainMax: upperBound,
      width: calculatedWidth,
      height: calculatedHeight,
      margin: calculatedMargin
    }
  }, [chartData, containerWidth])

  // Limit data points for performance (show max 200 candles)
  const displayData = useMemo(() => {
    return chartData.length > 200 
      ? chartData.filter((_, index) => index % Math.ceil(chartData.length / 200) === 0)
      : chartData
  }, [chartData])

  const priceToY = (price: number) => {
    const range = domainMax - domainMin
    if (range === 0) return height / 2
    const ratio = (price - domainMin) / range
    return margin.top + (height - margin.top - margin.bottom) * (1 - ratio)
  }

  const candleWidth = Math.max(2, Math.min(8, (width - margin.left - margin.right) / displayData.length * 0.6))
  const candleSpacing = (width - margin.left - margin.right) / displayData.length

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return
    
    const rect = svgRef.current.getBoundingClientRect()
    const svgX = ((e.clientX - rect.left) / rect.width) * width
    const svgY = ((e.clientY - rect.top) / rect.height) * height

    // Find the closest candle
    const candleIndex = Math.round((svgX - margin.left) / candleSpacing)
    if (candleIndex >= 0 && candleIndex < displayData.length) {
      const candle = displayData[candleIndex]
      setHoveredCandle(candle)
      setTooltipPosition({ x: e.clientX, y: e.clientY })
    } else {
      setHoveredCandle(null)
      setTooltipPosition(null)
    }
  }

  const handleMouseLeave = () => {
    setHoveredCandle(null)
    setTooltipPosition(null)
  }

  if (!chartData.length) {
    return null
  }

  return (
    <Card className="bg-teal-800/20 border-teal-700/30 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="text-white text-lg">
          {title || `${candleData.symbol} Price Chart`}
        </CardTitle>
        <CardDescription className="text-teal-200/70 text-sm">
          OHLC Candlestick Chart
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div ref={containerRef} className="relative w-full" style={{ height: `${height}px` }}>
          <svg
            ref={svgRef}
            width="100%"
            height={height}
            viewBox={`0 0 ${width} ${height}`}
            preserveAspectRatio="xMidYMid meet"
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            className="cursor-crosshair"
          >
            {/* Grid lines */}
            {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
              const y = margin.top + (height - margin.top - margin.bottom) * (1 - ratio)
              const price = domainMin + (domainMax - domainMin) * ratio
              return (
                <g key={`grid-${ratio}`}>
                  <line
                    x1={margin.left}
                    y1={y}
                    x2={width - margin.right}
                    y2={y}
                    stroke="rgba(255,255,255,0.08)"
                    strokeWidth={1}
                    strokeDasharray="3 3"
                    opacity={0.3}
                  />
                  <text
                    x={margin.left - 10}
                    y={y + 4}
                    fill="rgba(255,255,255,0.6)"
                    fontSize="12"
                    textAnchor="end"
                  >
                    {formatAxisValue(price)}
                  </text>
                </g>
              )
            })}

            {/* Y-axis line */}
            <line
              x1={margin.left}
              y1={margin.top}
              x2={margin.left}
              y2={height - margin.bottom}
              stroke="rgba(255,255,255,0.12)"
              strokeWidth={1}
            />

            {/* X-axis line */}
            <line
              x1={margin.left}
              y1={height - margin.bottom}
              x2={width - margin.right}
              y2={height - margin.bottom}
              stroke="rgba(255,255,255,0.12)"
              strokeWidth={1}
            />

            {/* Candlesticks */}
            {displayData.map((candle, index) => {
              const x = margin.left + index * candleSpacing + candleSpacing / 2
              const openY = priceToY(candle.open)
              const closeY = priceToY(candle.close)
              const highY = priceToY(candle.high)
              const lowY = priceToY(candle.low)

              const bodyTop = Math.min(openY, closeY)
              const bodyBottom = Math.max(openY, closeY)
              const bodyHeight = Math.max(1, bodyBottom - bodyTop)

              // Colors: green for up candles, red for down candles
              const color = candle.isUp ? '#22c55e' : '#ef4444'
              const strokeColor = candle.isUp ? '#16a34a' : '#dc2626'

              return (
                <g key={`candle-${index}`}>
                  {/* Wick (high-low line) */}
                  <line
                    x1={x}
                    y1={highY}
                    x2={x}
                    y2={lowY}
                    stroke={color}
                    strokeWidth={1.5}
                  />
                  {/* Body (open-close rectangle) */}
                  <rect
                    x={x - candleWidth / 2}
                    y={bodyTop}
                    width={candleWidth}
                    height={bodyHeight}
                    fill={color}
                    stroke={strokeColor}
                    strokeWidth={1}
                  />
                </g>
              )
            })}

            {/* X-axis labels */}
            {displayData.map((candle, index) => {
              if (index % Math.ceil(displayData.length / 10) !== 0) return null
              const x = margin.left + index * candleSpacing + candleSpacing / 2
              const date = new Date(candle.date)
              return (
                <text
                  key={`label-${index}`}
                  x={x}
                  y={height - margin.bottom + 20}
                  fill="rgba(255,255,255,0.6)"
                  fontSize="11"
                  textAnchor="middle"
                  transform={`rotate(-45 ${x} ${height - margin.bottom + 20})`}
                >
                  {`${date.getMonth() + 1}/${date.getDate()}`}
                </text>
              )
            })}
          </svg>

          {/* Tooltip */}
          {hoveredCandle && tooltipPosition && (
            <div
              className="fixed z-50 rounded-lg border bg-teal-900/95 backdrop-blur-sm p-3 shadow-lg border-teal-700/50 pointer-events-none"
              style={{
                left: `${tooltipPosition.x + 10}px`,
                top: `${tooltipPosition.y - 10}px`,
                transform: 'translateY(-100%)',
              }}
            >
              <div className="text-xs font-medium text-teal-200/70 mb-2">
                {formatDate(hoveredCandle.date)}
              </div>
              <div className="space-y-1">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-teal-200/70 text-xs">Open:</span>
                  <span className="text-white text-xs font-medium">
                    {formatAxisValue(hoveredCandle.open)}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-teal-200/70 text-xs">High:</span>
                  <span className="text-green-400 text-xs font-medium">
                    {formatAxisValue(hoveredCandle.high)}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-teal-200/70 text-xs">Low:</span>
                  <span className="text-red-400 text-xs font-medium">
                    {formatAxisValue(hoveredCandle.low)}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-teal-200/70 text-xs">Close:</span>
                  <span className={`text-xs font-medium ${hoveredCandle.isUp ? 'text-green-400' : 'text-red-400'}`}>
                    {formatAxisValue(hoveredCandle.close)}
                  </span>
                </div>
                {hoveredCandle.volume !== null && hoveredCandle.volume !== undefined && (
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-teal-200/70 text-xs">Volume:</span>
                    <span className="text-teal-200/90 text-xs font-medium">
                      {formatAxisValue(hoveredCandle.volume)}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
