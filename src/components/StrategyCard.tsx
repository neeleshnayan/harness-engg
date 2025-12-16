'use client';

import type { FC } from 'react';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import type { Strategy } from '@/lib/types';
import {
  ArrowDownRight,
  Users,
  TrendingUp,
  BarChart,
  Percent,
  ChevronsRight,
  Shield,
  Clock,
  Scale,
} from 'lucide-react';

interface StrategyCardProps {
  strategy: Strategy;
  onInvest: (strategy: Strategy) => void;
}

const gradeStyles: Record<Strategy['riskGrade'], string> = {
  A: 'bg-green-500/20 text-green-400 border-green-500/20 hover:bg-green-500/30',
  B: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/20 hover:bg-yellow-500/30',
  C: 'bg-orange-500/20 text-orange-400 border-orange-500/20 hover:bg-orange-500/30',
  D: 'bg-red-500/20 text-red-400 border-red-500/20 hover:bg-red-500/30',
};

const StrategyCard: FC<StrategyCardProps> = ({ strategy, onInvest }) => {
  const {
    name,
    riskGrade,
    maxDrawdown,
    description,
    netApy,
    sharpe,
    depositors,
    performanceFee,
    aum,
    cooldown,
  } = strategy;

  return (
    <Card className="flex flex-col h-full overflow-hidden transition-all duration-300 ease-in-out hover:shadow-xl hover:-translate-y-1 bg-zinc-800/50 backdrop-blur-sm border-zinc-700/50">
      <CardHeader className="pb-4">
        <div className="flex justify-between items-start gap-4">
          <CardTitle className="text-xl text-white">{name}</CardTitle>
          <Badge
            variant="outline"
            className={cn(
              'text-sm px-3 py-1 font-bold shrink-0 flex items-center gap-1.5 border',
              gradeStyles[riskGrade]
            )}
            title="Risk grade is based on backtested max drawdown"
          >
            {riskGrade === 'A' && <Shield className="w-4 h-4" />}
            Risk: {riskGrade}
          </Badge>
        </div>
        <CardDescription className="pt-2 text-sm text-zinc-400">{description}</CardDescription>
      </CardHeader>
      
      <CardContent className="flex-grow space-y-5">
        <div className="space-y-4">
          <h4 className="text-sm font-semibold text-zinc-400">Key Metrics</h4>
          <div className="space-y-4 text-sm">
            {/* Row 1: Net APY & AUM */}
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                <TrendingUp className="w-6 h-6 text-green-400" />
                <div>
                  <p className="text-xs text-zinc-500">{name === 'Pendle Fixed Yield' ? 'Fixed APY' : 'Net APY'}</p>
                  <span className="font-semibold text-lg text-white">{netApy.toFixed(1)}%</span>
                </div>
              </div>
              <div className="flex items-center gap-3 text-right">
                <div>
                  <p className="text-xs text-zinc-500">AUM</p>
                  <span className="font-semibold text-lg text-white">${aum.toLocaleString()}M</span>
                </div>
                <Scale className="w-6 h-6 text-zinc-500" />
              </div>
            </div>

            <Separator className="bg-zinc-700" />

            {/* Row 2: Sharpe, Max Drawdown, Cooldown */}
            <div className="flex justify-between items-center text-center">
              <div className="flex flex-col items-center gap-1">
                <BarChart className="w-5 h-5 text-blue-400" />
                <span className="font-semibold text-white">{sharpe.toFixed(2)}</span>
                <span className="text-xs text-zinc-500">Sharpe</span>
              </div>
              <div className="flex flex-col items-center gap-1">
                <ArrowDownRight className="w-5 h-5 text-red-400" />
                <span className="font-semibold text-white">{maxDrawdown.toFixed(2)}%</span>
                <span className="text-xs text-zinc-500">Max Drawdown</span>
              </div>
              <div className="flex flex-col items-center gap-1">
                <Clock className="w-5 h-5 text-zinc-500" />
                <span className="font-semibold text-white">{cooldown}</span>
                <span className="text-xs text-zinc-500">Lock-in Period</span>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
      
      <CardFooter className="p-4 bg-black/20 flex items-center justify-between mt-auto">
        <div className="flex items-center gap-4 text-sm text-zinc-400 flex-wrap">
            <div className="flex items-center gap-2" title="Number of Depositors">
                <Users className="w-5 h-5" />
                <span className="font-semibold text-white">{depositors.toLocaleString()}</span>
            </div>
             <div className="flex items-center gap-2" title="Performance Fee">
                <Percent className="w-5 h-5" />
                <span className="font-semibold text-white">{performanceFee.toFixed(1)}%</span>
            </div>
        </div>
        <Button size="sm" className="font-bold shrink-0 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700" onClick={() => onInvest(strategy)}>
          Invest
          <ChevronsRight className="w-4 h-4 ml-1" />
        </Button>
      </CardFooter>
    </Card>
  );
};

export default StrategyCard; 