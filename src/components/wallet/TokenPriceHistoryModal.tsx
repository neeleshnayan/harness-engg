"use client";

import React, { useEffect, useState, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { ChartContainer, ChartTooltip } from "@/components/ui/chart";
import { LineChart, Line, XAxis, YAxis, CartesianGrid } from "recharts";
import { getHistoricalClosingPoolRates, HistoricalPricePoint } from "@/lib/priceCache";

interface TokenPriceHistoryModalProps {
  open: boolean;
  onClose: () => void;
  tokenSymbol: string;
}

const chartConfig = {
  price: {
    label: "Price (USD)",
    color: "hsl(var(--chart-1))",
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

export const TokenPriceHistoryModal: React.FC<TokenPriceHistoryModalProps> = ({
  open,
  onClose,
  tokenSymbol,
}) => {
  const [historicalData, setHistoricalData] = useState<HistoricalPricePoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && tokenSymbol) {
      setLoading(true);
      setError(null);
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
    }
  }, [open, tokenSymbol]);

  const chartData = useMemo(() => {
    return historicalData.map((point) => ({
      date: point.date,
      dateLabel: formatDateShort(point.date),
      price: parseFloat(point.price.toFixed(6)),
    }));
  }, [historicalData]);

  const displaySymbol = tokenSymbol.replace(/^k/, '');

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[95vh] sm:max-h-[90vh] overflow-y-auto bg-zinc-900/95 border-zinc-700 w-[95vw] sm:w-full max-w-[95vw] sm:max-w-4xl p-4 sm:p-6 [&>button]:hidden">
        <DialogHeader>
          <DialogTitle className="text-xl sm:text-2xl font-bold text-white">
            {displaySymbol} Price History
          </DialogTitle>
          <DialogDescription className="text-zinc-400 text-sm">
            Historical closing prices in USD over time
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4">
          {loading ? (
            <div className="flex items-center justify-center h-[300px] sm:h-[400px]">
              <div className="flex flex-col items-center gap-3">
                <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent"></div>
                <p className="text-zinc-400 text-sm">Loading price history...</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-[300px] sm:h-[400px]">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          ) : chartData.length === 0 ? (
            <div className="flex items-center justify-center h-[300px] sm:h-[400px]">
              <p className="text-zinc-400 text-sm">No historical data available</p>
            </div>
          ) : (
            <div className="w-full">
              <ChartContainer config={chartConfig} className="h-[300px] sm:h-[400px] w-full">
                <LineChart
                  data={chartData}
                  margin={{ left: 8, right: 8, top: 20, bottom: 60 }}
                >
                  <CartesianGrid
                    vertical={false}
                    strokeDasharray="3 3"
                    stroke="rgba(255, 255, 255, 0.1)"
                  />
                  <XAxis
                    dataKey="dateLabel"
                    tickLine={false}
                    axisLine={false}
                    tickMargin={8}
                    angle={-45}
                    textAnchor="end"
                    height={80}
                    interval="preserveStartEnd"
                    tick={{ fill: '#9ca3af', fontSize: 10 }}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    tick={{ fill: '#9ca3af', fontSize: 10 }}
                    tickFormatter={(value) => `$${value.toFixed(4)}`}
                    width={60}
                  />
                  <ChartTooltip
                    cursor={{ stroke: '#3b82f6', strokeWidth: 1 }}
                    content={({ active, payload, label }) => {
                      if (!active || !payload?.length) return null;

                      const value = payload[0]?.value;
                      const numValue = typeof value === 'number' ? value : parseFloat(value as string);

                      return (
                        <div className="bg-zinc-900/95 backdrop-blur-sm border border-zinc-700/50 rounded-lg p-3 shadow-xl min-w-[10rem]">
                          <div className="font-medium text-white mb-2 text-sm">
                            {formatDate(label as string)}
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                            <span className="text-zinc-300 text-xs">Price:</span>
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
                    dot={false}
                    activeDot={{ r: 4, fill: '#3b82f6' }}
                  />
                </LineChart>
              </ChartContainer>

              {/* Stats */}
              {historicalData.length > 0 && (
                <div className="mt-4 sm:mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 pt-4 border-t border-zinc-700/50">
                  <div>
                    <p className="text-xs text-zinc-400 mb-1">Current Price</p>
                    <p className="text-base sm:text-lg font-semibold text-white">
                      ${historicalData[historicalData.length - 1].price.toFixed(6)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-zinc-400 mb-1">Data Points</p>
                    <p className="text-base sm:text-lg font-semibold text-white">{historicalData.length}</p>
                  </div>
                  <div>
                    <p className="text-xs text-zinc-400 mb-1">Date Range</p>
                    <p className="text-xs sm:text-sm font-semibold text-white">
                      {formatDateShort(historicalData[0].date)} - {formatDateShort(historicalData[historicalData.length - 1].date)}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default TokenPriceHistoryModal;

