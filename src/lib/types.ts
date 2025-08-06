export interface Strategy {
  id: string;
  name: string;
  riskGrade: 'A' | 'B' | 'C' | 'D';
  maxDrawdown: number;
  description: string;
  netApy: number;
  sharpe: number;
  depositors: number;
  performanceFee: number;
  aum: number;
  apyTrend: number;
  cooldown: string;
} 