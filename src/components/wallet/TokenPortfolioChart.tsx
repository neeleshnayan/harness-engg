import React from "react";
import { AreaChart, Area, ResponsiveContainer, YAxis, Tooltip } from "recharts";
import { StrategyChartTooltip } from "@/components/charts/StrategyChartTooltip";

interface PortfolioDataPoint {
  date: string;
  value: number;
  balance: number;
  price: number;
}

interface TokenPortfolioChartProps {
  data: PortfolioDataPoint[];
  color?: string;
  rateChangeDirection?: 'up' | 'down' | 'same';
}

const TokenPortfolioChart: React.FC<TokenPortfolioChartProps> = ({ 
  data, 
  color = "#3b82f6", // Default blue color
  rateChangeDirection
}) => {
  if (!data || data.length === 0) {
    return null;
  }

  // Use rate change direction if provided, otherwise fallback to comparing first/last values
  let isUp: boolean;
  if (rateChangeDirection !== undefined) {
    isUp = rateChangeDirection === 'up';
  } else {
    // Fallback: compare first and last values
    const firstValue = data[0]?.value || 0;
    const lastValue = data[data.length - 1]?.value || 0;
    isUp = lastValue >= firstValue;
  }
  
  // Use green for up, red for down with gradient colors
  const lineColor = isUp ? "#22c55e" : "#ef4444";
  const gradientId = `gradient-${isUp ? 'up' : 'down'}`;
  const gradientStartColor = isUp ? "#22c55e" : "#ef4444";
  const gradientEndColor = isUp ? "rgba(34, 197, 94, 0.1)" : "rgba(239, 68, 68, 0.1)";

  // Format currency value for tooltip
  const formatTooltipValue = (value: number) => {
    return `$${value.toFixed(2)}`;
  };

  // Format date for tooltip
  const formatTooltipDate = (date: string) => {
    if (!date) return '';
    try {
      const dateObj = new Date(date);
      return dateObj.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric',
        year: dateObj.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined
      });
    } catch {
      return date;
    }
  };

  return (
    <div className="w-full h-20 sm:h-24 lg:h-28 -mx-1">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart 
          data={data} 
          margin={{ top: 8, right: 0, bottom: 0, left: 0 }}
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={gradientStartColor} stopOpacity={0.4} />
              <stop offset="100%" stopColor={gradientEndColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <YAxis hide domain={['dataMin', 'dataMax']} />
          <Tooltip
            content={(props) => {
              if (!props.active || !props.payload || !props.payload.length) return null;
              
              const payloadItem = props.payload[0];
              const dataPoint = payloadItem.payload as PortfolioDataPoint;
              
              // Add color to payload for tooltip indicator
              const payloadWithColor = props.payload.map(item => ({
                ...item,
                color: lineColor
              }));
              
              return (
                <StrategyChartTooltip
                  active={props.active}
                  payload={payloadWithColor}
                  label={props.label}
                  labelFormatted={formatTooltipDate(dataPoint.date)}
                  valueFormatter={formatTooltipValue}
                />
              );
            }}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={lineColor}
            strokeWidth={2.5}
            fill={`url(#${gradientId})`}
            fillOpacity={1}
            dot={false}
            activeDot={{ r: 4, fill: lineColor, strokeWidth: 2, stroke: '#fff' }}
            animationDuration={800}
            animationEasing="ease-out"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TokenPortfolioChart;
