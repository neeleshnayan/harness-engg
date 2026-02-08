import React from "react";
import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";

interface PortfolioDataPoint {
  date: string;
  value: number;
  balance: number;
  price: number;
}

interface TokenPortfolioChartProps {
  data: PortfolioDataPoint[];
  color?: string;
}

const TokenPortfolioChart: React.FC<TokenPortfolioChartProps> = ({ 
  data, 
  color = "#3b82f6" // Default blue color
}) => {
  if (!data || data.length === 0) {
    return null;
  }

  // Determine if the portfolio is up or down
  const firstValue = data[0]?.value || 0;
  const lastValue = data[data.length - 1]?.value || 0;
  const isUp = lastValue >= firstValue;
  
  // Use green for up, red for down
  const lineColor = isUp ? "#22c55e" : "#ef4444";

  return (
    <div className="w-full h-16 mt-2">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
          <YAxis hide domain={['dataMin', 'dataMax']} />
          <Line
            type="monotone"
            dataKey="value"
            stroke={lineColor}
            strokeWidth={2}
            dot={false}
            animationDuration={300}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TokenPortfolioChart;
