"use client";

import React, { useEffect, useState, useMemo, useRef, useLayoutEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogPortal,
  DialogOverlay,
} from "@/components/ui/dialog";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ChartContainer, ChartTooltip } from "@/components/ui/chart";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ReferenceLine } from "recharts";
import { getHistoricalClosingPoolRates, HistoricalPricePoint } from "@/lib/priceCache";
import { X, Triangle } from "lucide-react";

interface TokenPriceHistoryModalProps {
  open: boolean;
  onClose: () => void;
  tokenSymbol: string;
}

const chartConfig = {
  price: {
    label: "Price",
    color: "#3b82f6",
  },
};

const formatDate = (dateString: string) => {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  } catch {
    return dateString;
  }
};

const formatDateShort = (dateString: string) => {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return dateString;
  }
};

// Factory function to create custom dot component with data bound
const createCustomDot = (chartData: any[]) => {
  return (props: any) => {
    const { cx, cy, payload, index } = props;
    const innerRadius = 3;
    const middleRadius = 5.5;
    const outerRadius = 8;

    // Determine color based on price change compared to previous point
    let middleRingColor: string | null = null;
    if (index > 0 && chartData && chartData[index - 1]) {
      const currentPrice = payload.price;
      const previousPrice = chartData[index - 1].price;
      if (currentPrice > previousPrice) {
        middleRingColor = '#10b981'; // emerald-500 (green)
      } else if (currentPrice < previousPrice) {
        middleRingColor = '#ef4444'; // red-500
      }
      // If prices are equal, middleRingColor stays null (no ring)
    }

    return (
      <g>
        {/* Outer circle - blue */}
        <circle
          cx={cx}
          cy={cy}
          r={outerRadius}
          fill="none"
          stroke="#3b82f6"
          strokeWidth={1.5}
          opacity={0.75}
        />
        {/* Middle ring - green/red based on price change */}
        {middleRingColor && (
          <circle
            cx={cx}
            cy={cy}
            r={middleRadius}
            fill="none"
            stroke={middleRingColor}
            strokeWidth={3}
            opacity={0.9}
          />
        )}
        {/* Inner dot - white */}
        <circle
          cx={cx}
          cy={cy}
          r={innerRadius}
          fill="#ffffff"
          stroke="none"
        />
      </g>
    );
  };
};

// Factory function to create custom active dot component with data bound
const createCustomActiveDot = (chartData: any[]) => {
  return (props: any) => {
    const { cx, cy, payload, index } = props;
    const innerRadius = 5;
    const middleRadius = 8;
    const outerRadius = 11;

    // Determine color based on price change compared to previous point
    let middleRingColor: string | null = null;
    if (index > 0 && chartData && chartData[index - 1]) {
      const currentPrice = payload.price;
      const previousPrice = chartData[index - 1].price;
      if (currentPrice > previousPrice) {
        middleRingColor = '#10b981'; // emerald-500 (green)
      } else if (currentPrice < previousPrice) {
        middleRingColor = '#ef4444'; // red-500
      }
      // If prices are equal, middleRingColor stays null (no ring)
    }

    return (
      <g>
        {/* Outer circle - blue */}
        <circle
          cx={cx}
          cy={cy}
          r={outerRadius}
          fill="none"
          stroke="#3b82f6"
          strokeWidth={2}
          opacity={0.85}
        />
        {/* Middle ring - green/red based on price change */}
        {middleRingColor && (
          <circle
            cx={cx}
            cy={cy}
            r={middleRadius}
            fill="none"
            stroke={middleRingColor}
            strokeWidth={4}
            opacity={0.9}
          />
        )}
        {/* Inner dot - white */}
        <circle
          cx={cx}
          cy={cy}
          r={innerRadius}
          fill="#ffffff"
          stroke="none"
        />
      </g>
    );
  };
};

export const TokenPriceHistoryModal: React.FC<TokenPriceHistoryModalProps> = ({
  open,
  onClose,
  tokenSymbol,
}) => {
  const [historicalData, setHistoricalData] = useState<HistoricalPricePoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const hasScrolledToEndRef = useRef(false);

  useEffect(() => {
    if (open && tokenSymbol) {
      setLoading(true);
      setError(null);
      hasScrolledToEndRef.current = false; // Reset flag when opening modal
      getHistoricalClosingPoolRates(tokenSymbol, 1000)
        .then((data) => {
          setHistoricalData(data);
          setLoading(false);
        })
        .catch((err) => {
          console.error("Failed to fetch historical data:", err);
          setError("Failed to load price history");
          setLoading(false);
        });
    } else {
      setHistoricalData([]);
      hasScrolledToEndRef.current = false; // Reset flag when closing modal
    }
  }, [open, tokenSymbol]);

  const chartData = useMemo(() => {
    return historicalData.map((point) => ({
      date: point.date,
      dateLabel: formatDateShort(point.date),
      price: parseFloat(point.price.toFixed(6)),
    }));
  }, [historicalData]);

  const yAxisDomain = useMemo(() => {
    if (chartData.length === 0) return undefined;

    const prices = chartData.map(d => d.price);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const priceRange = maxPrice - minPrice;

    // 5% padding above max price and below min price
    const padding = priceRange * 0.05;

    // Domain should start 5% below min price and end 5% above max price
    const domainMin = Math.max(0, minPrice - padding); // Prevent negative values
    const domainMax = maxPrice + padding;

    return [domainMin, domainMax];
  }, [chartData]);

  const currentPrice = useMemo(() => {
    if (historicalData.length === 0) return null;
    return historicalData[historicalData.length - 1].price;
  }, [historicalData]);

  const priceChange = useMemo(() => {
    if (historicalData.length < 2) return null;
    const first = historicalData[0].price;
    const last = historicalData[historicalData.length - 1].price;
    const change = last - first;
    const percentChange = ((change / first) * 100);
    return { change, percentChange };
  }, [historicalData]);

  const displaySymbol = tokenSymbol.replace(/^k/, '');

  // Calculate precise width for chart based on data points
  // Each data point needs ~3-4px spacing, margins add padding inside this width
  const baseWidth = chartData.length > 0 ? chartData.length * 3.5 : 600;
  const chartMinWidth = Math.max(500, baseWidth);

  // Scroll to end (latest dates) only once when modal opens and data loads
  useLayoutEffect(() => {
    if (open && !loading && chartData.length > 0 && scrollContainerRef.current && !hasScrolledToEndRef.current) {
      const container = scrollContainerRef.current;
      // Use requestAnimationFrame to ensure layout is complete
      requestAnimationFrame(() => {
        if (container && !hasScrolledToEndRef.current) {
          container.scrollLeft = container.scrollWidth;
          hasScrolledToEndRef.current = true; // Mark as scrolled so it doesn't happen again
        }
      });
    }
  }, [open, loading, chartData.length]);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogPortal>
        <DialogOverlay className="bg-black/80 backdrop-blur-sm" />
        <DialogPrimitive.Content
          className="fixed left-[50%] top-[50%] z-50 w-[calc(100%-2rem)] max-w-lg translate-x-[-50%] translate-y-[-50%] bg-zinc-900/95 backdrop-blur-xl border border-zinc-800 shadow-2xl p-0 overflow-hidden rounded-3xl max-h-[90vh] focus:outline-none focus:ring-0 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]"
        >
        {/* Header */}
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-zinc-800/50 !text-left">
          <div className="flex items-start justify-between">
            <div className="flex-1 text-left">
              <DialogTitle className="text-xl font-bold text-white text-left">
                {displaySymbol} Price History
              </DialogTitle>
              {currentPrice && (
                <div className="mt-2 flex items-center gap-3">
                  <p className="text-xl font-semibold text-white">
                    ${currentPrice.toFixed(6)}
                  </p>
                  {priceChange && (
                    <p className={`text-sm font-medium ${
                      priceChange.percentChange >= 0 ? 'text-emerald-400' : 'text-red-400'
                    }`}>
                      <div className="flex items-center gap-1">
                        {priceChange.percentChange >= 0 ? <Triangle className="h-3 w-3 fill-emerald-400" /> : <Triangle className="h-3 w-3 rotate-180 fill-red-400" />}
                        <span>{priceChange.percentChange.toFixed(2)}%</span>
                      </div>
                    </p>
                  )}
                </div>
              )}
            </div>
            <button
              onClick={onClose}
              className="text-zinc-400 hover:text-white transition-colors ml-4 mt-0.5"
              disabled={loading}
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </DialogHeader>

        {/* Content */}
        <div className="flex flex-col overflow-hidden" style={{ height: '360px' }}>
          {loading ? (
            <div className="flex items-center justify-center h-full px-4 py-8">
              <div className="flex flex-col items-center gap-4">
                <div className="relative">
                  <div className="animate-spin rounded-full h-10 w-10 border-2 border-zinc-700 border-t-blue-500"></div>
                  <div className="absolute inset-0 animate-ping rounded-full h-10 w-10 border border-blue-500/20"></div>
                </div>
                <p className="text-zinc-400 text-sm font-light">Loading price history...</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full px-4 py-8">
              <div className="text-center">
                <p className="text-red-400 text-sm mb-2">⚠️</p>
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            </div>
          ) : chartData.length === 0 ? (
            <div className="flex items-center justify-center h-full px-4 py-8">
              <p className="text-zinc-400 text-sm font-light">No historical data available</p>
            </div>
          ) : (
            <>
              {/* Chart Container with Fixed Y-axis */}
              <div className="flex-1 overflow-hidden relative min-h-0 px-1">
                <div className="flex h-full" style={{ height: '320px', maxHeight: '320px' }}>
                  {/* Fixed Y-axis */}
                  <div className="flex-shrink-0 w-[55px] relative bg-zinc-900/95">
                    <ChartContainer config={chartConfig} className="h-full w-full" style={{ height: '320px' }}>
                      <LineChart
                        data={chartData.slice(0, 1)} // Minimal data just for Y-axis
                        width={55}
                        height={320}
                        margin={{ left: 0, right: 0, top: 8, bottom: 0 }}
                      >
                        <YAxis
                          type="number"
                          domain={yAxisDomain}
                          tickLine={false}
                          axisLine={false}
                          tick={{ fill: '#a1a1aa', fontSize: 9, fontWeight: 300, dy: 0 }}
                          tickFormatter={(value) => `$${value.toFixed(4)}`}
                          width={55}
                          orientation="left"
                          allowDataOverflow={false}
                        />
                      </LineChart>
                    </ChartContainer>
                  </div>

                  {/* Scrollable Chart Area */}
                  <div className="flex-1 overflow-hidden relative min-h-0">
                    <div
                      ref={scrollContainerRef}
                      className="h-full overflow-x-auto overflow-y-hidden"
                      style={{
                        scrollbarWidth: 'thin',
                        WebkitOverflowScrolling: 'touch',
                        scrollBehavior: 'auto' // Disable smooth scrolling to prevent visible animation
                      }}
                    >
                      <div style={{ width: `${chartMinWidth}px`, height: '320px' }}>
                        <ChartContainer config={chartConfig} style={{ width: `${chartMinWidth}px`, height: '320px' }}>
                          <LineChart
                            data={chartData}
                            width={chartMinWidth}
                            height={320}
                            margin={{ left: 30, right: 16, top: 8, bottom: 40 }}
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
                              tickMargin={5}
                              angle={-45}
                              textAnchor="end"
                              height={30}
                              interval="preserveStartEnd"
                              tick={{ fill: '#a1a1aa', fontSize: 9, fontWeight: 300 }}
                            />
                            <YAxis
                              type="number"
                              domain={yAxisDomain}
                              hide={true}
                              allowDataOverflow={false}
                            />
                            {/* Vertical dotted lines from each x-axis point */}
                            {chartData.map((point, index) => (
                              <ReferenceLine
                                key={`ref-line-${index}`}
                                x={point.dateLabel}
                                stroke="rgba(255, 255, 255, 0.1)"
                                strokeDasharray="2 2"
                                strokeWidth={1}
                              />
                            ))}
                            <ChartTooltip
                              cursor={{ stroke: '#3b82f6', strokeWidth: 1, strokeDasharray: '5 5' }}
                              content={({ active, payload, label }) => {
                                if (!active || !payload?.length) return null;

                                const value = payload[0]?.value;
                                const numValue = typeof value === 'number' ? value : parseFloat(value as string);

                                return (
                                  <div className="bg-zinc-900/95 backdrop-blur-xl border border-zinc-800/50 rounded-xl p-4 shadow-2xl min-w-[12rem]">
                                    <div className="text-xs text-zinc-400 mb-2 font-light">
                                      {formatDate(label as string)}
                                    </div>
                                    <div className="flex items-center gap-2">
                                      <div className="w-1.5 h-1.5 rounded-full bg-blue-500"></div>
                                      <span className="text-zinc-300 text-xs font-light">Price</span>
                                      <span className="text-white font-mono font-semibold ml-auto text-sm">
                                        ${numValue.toFixed(6)}
                                      </span>
                                    </div>
                                  </div>
                                );
                              }}
                            />
                            <Line
                              type="monotone"
                              dataKey="price"
                              stroke="#3b82f6"
                              strokeWidth={2}
                              dot={createCustomDot(chartData)}
                              activeDot={createCustomActiveDot(chartData)}
                              className="drop-shadow-lg"
                            />
                          </LineChart>
                        </ChartContainer>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
        </DialogPrimitive.Content>
      </DialogPortal>
      </Dialog>
  );
};

export default TokenPriceHistoryModal;