'use client';

import { useState, useMemo, useEffect, useRef } from 'react';
import {
  Rocket,
  TrendingUp,
  ArrowUpRight,
  Zap,
  Scale,
  BrainCircuit,
  Shuffle,
  BarChart,
  Filter,
  SortAsc,
  Circle,
} from 'lucide-react';

import type { Strategy } from '@/lib/types';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import StrategyCard from '@/components/StrategyCard';
import InvestDialog from '@/components/InvestDialog';
import { Separator } from '@/components/ui/separator';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart';
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from 'recharts';
import { useToast } from '@/hooks/use-toast';
import { Toast, ToastDescription, ToastTitle } from '@/components/ui/toast';

const initialStrategies: Strategy[] = [
  {
    id: '1',
    name: 'ETH-BTC Momentum',
    riskGrade: 'B',
    maxDrawdown: 18.2,
    description: 'Rotates between ETH and BTC based on relative strength, aiming to capture major trends.',
    netApy: 22.5,
    sharpe: 1.65,
    depositors: 1450,
    performanceFee: 15.0,
    aum: 42.1,
    apyTrend: 2.1,
    cooldown: '3d',
  },
  {
    id: '2',
    name: 'Blue Chip Stable Yield',
    riskGrade: 'A',
    maxDrawdown: 2.5,
    description: 'Generates yield from over-collateralized lending and liquidity pools of top-tier stablecoins.',
    netApy: 9.8,
    sharpe: 3.5,
    depositors: 18234,
    performanceFee: 10.0,
    aum: 175.2,
    apyTrend: 0.5,
    cooldown: 'None',
  },
  {
    id: '3',
    name: 'DeFi Pulse Index',
    riskGrade: 'C',
    maxDrawdown: 35.8,
    description: 'A market-cap weighted index of top-tier DeFi protocols, rebalanced to capture growth.',
    netApy: 42.1,
    sharpe: 1.1,
    depositors: 812,
    performanceFee: 20.0,
    aum: 22.8,
    apyTrend: -3.4,
    cooldown: '7d',
  },
  {
    id: '9',
    name: 'Pendle Fixed Yield',
    riskGrade: 'A',
    maxDrawdown: 1.5,
    description: 'Earn a consistent, fixed yield on your stablecoins by leveraging Pendle\'s interest rate tokenization protocol.',
    netApy: 8.2,
    sharpe: 3.75,
    depositors: 25300,
    performanceFee: 10.0,
    aum: 250.5,
    apyTrend: 0.1,
    cooldown: 'None'
  },
  { 
    id: '4', 
    name: 'Hyper Growth Arbitrage', 
    riskGrade: 'D', 
    maxDrawdown: 65.5, 
    description: 'High-frequency trading strategy that exploits pricing inefficiencies across exchanges.', 
    netApy: 135.3, 
    sharpe: 0.85, 
    depositors: 121, 
    performanceFee: 30.0, 
    aum: 8.9, 
    apyTrend: 15.2, 
    cooldown: '14d' 
  },
];

const allPossibleStrategies: Strategy[] = [
    ...initialStrategies,
    { id: '5', name: 'AI Narrative Basket', riskGrade: 'C', maxDrawdown: 40.5, description: 'Thematic investment in a curated basket of high-potential AI-related crypto assets.', netApy: 55.0, sharpe: 1.4, depositors: 950, performanceFee: 20.0, aum: 19.5, apyTrend: 8.3, cooldown: '7d' },
    { id: '6', name: 'Tokenized Treasury Yield', riskGrade: 'A', maxDrawdown: 1.1, description: 'Stable returns from tokenized, short-term government treasury bills on-chain.', netApy: 5.5, sharpe: 4.8, depositors: 21200, performanceFee: 5.0, aum: 210.7, apyTrend: 0.2, cooldown: 'None' },
    { id: '7', name: 'Metaverse REIT', riskGrade: 'D', maxDrawdown: 72.0, description: 'A portfolio of virtual land and assets across major metaverse platforms.', netApy: 110.0, sharpe: 0.9, depositors: 410, performanceFee: 25.0, aum: 11.4, apyTrend: -10.1, cooldown: '14d' },
    { id: '8', name: 'Solana Ecosystem Alpha', riskGrade: 'B', maxDrawdown: 22.8, description: 'Actively managed portfolio of promising new projects within the Solana ecosystem.', netApy: 38.0, sharpe: 1.8, depositors: 3105, performanceFee: 18.0, aum: 65.3, apyTrend: 4.5, cooldown: '3d' },
];

const portfolioData = {
  performance: [
    { month: 'Jan', value: 100000 },
    { month: 'Feb', value: 102500 },
    { month: 'Mar', value: 101800 },
    { month: 'Apr', value: 106000 },
    { month: 'May', value: 105200 },
    { month: 'Jun', value: 109500 },
    { month: 'Jul', value: 114000 },
    { month: 'Aug', value: 113200 },
    { month: 'Sep', value: 117500 },
    { month: 'Oct', value: 116000 },
    { month: 'Nov', value: 121000 },
    { month: 'Dec', value: 125000 },
  ],
  metrics: {
    totalReturn: 25.0,
    volatility: 8.5,
    sharpeRatio: 2.1,
  },
};

const chartConfig = {
  value: {
    label: 'Portfolio Value ',
    color: '#3b82f6', // Rich blue color
  },
};

export default function HedgeFundDashboard() {
  const [strategies, setStrategies] = useState<Strategy[]>(initialStrategies);
  const [selectedStrategyForInvestment, setSelectedStrategyForInvestment] = useState<Strategy | null>(null);
  const [isInvestDialogOpen, setInvestDialogOpen] = useState(false);
  const autopilotIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const { toast, toasts, dismiss } = useToast();

  const [isAutopilotOn, setIsAutopilotOn] = useState(false);
  const [riskFilter, setRiskFilter] = useState('all');
  const [sortOrder, setSortOrder] = useState('apy-desc');

  useEffect(() => {
    if (isAutopilotOn) {
      autopilotIntervalRef.current = setInterval(() => {
        setStrategies(prevStrategies => {
          // Remove a random strategy
          const strategyToRemoveIndex = Math.floor(Math.random() * prevStrategies.length);
          const removedStrategy = prevStrategies[strategyToRemoveIndex];
          const remainingStrategies = prevStrategies.filter((_, index) => index !== strategyToRemoveIndex);

          // Add a new random strategy that is not already in the portfolio
          const availableNewStrategies = allPossibleStrategies.filter(
            s => !remainingStrategies.some(rs => rs.id === s.id) && s.id !== removedStrategy.id
          );
          
          if (availableNewStrategies.length > 0) {
            const newStrategy = availableNewStrategies[Math.floor(Math.random() * availableNewStrategies.length)];
            
            toast({
              title: "Autopilot Rebalanced!",
              description: `Removed "${removedStrategy.name}" and added "${newStrategy.name}".`,
            });
            return [...remainingStrategies, newStrategy];
          }
          return prevStrategies; // No change if no new strategies are available
        });
      }, 5000); // Rebalance every 5 seconds
    } else {
      if (autopilotIntervalRef.current) {
        clearInterval(autopilotIntervalRef.current);
      }
    }

    return () => {
      if (autopilotIntervalRef.current) {
        clearInterval(autopilotIntervalRef.current);
      }
    };
  }, [isAutopilotOn]);

  const handleInvestClick = (strategy: Strategy) => {
    setSelectedStrategyForInvestment(strategy);
    setInvestDialogOpen(true);
  };
  
  const handleInvestmentSubmit = (amount: number) => {
    toast({
      title: 'Investment Submitted!',
      description: `You have invested ${amount} USDC in "${selectedStrategyForInvestment?.name}".`,
    });
  };

  const displayedStrategies = useMemo(() => {
    let filtered = [...strategies];

    if (riskFilter !== 'all') {
      filtered = filtered.filter(s => s.riskGrade === riskFilter);
    }

    if (sortOrder === 'apy-desc') {
      filtered.sort((a, b) => b.netApy - a.netApy);
    } else if (sortOrder === 'apy-asc') {
      filtered.sort((a, b) => a.netApy - b.netApy);
    }

    return filtered;
  }, [strategies, riskFilter, sortOrder]);

  return (
    <>
      <main className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900">
        <div className="container mx-auto px-4 py-8">
        <header className="text-center mb-12">
          <div className="flex justify-center items-center gap-4 mb-4">
            <h1 className="text-5xl font-extrabold text-white tracking-tight drop-shadow-lg">
              Tokenized Strategies
            </h1>
          </div>
          <p className="text-xl text-zinc-400 mt-2 max-w-3xl mx-auto">
            Your all-in-one dashboard for portfolio analysis and automated strategy discovery.
          </p>
          <div className="flex flex-col items-center justify-center mt-8">
            <div className="flex items-center gap-3 px-6 py-3 bg-gradient-to-r from-zinc-900/80 via-cyan-900/40 to-blue-900/40 backdrop-blur-xl border border-cyan-400/20 rounded-2xl shadow-lg">
              <Circle className="h-6 w-6 text-cyan-400" />
              <Label htmlFor="autopilot-mode" className="text-lg font-semibold text-white">Autopilot</Label>
              <Switch id="autopilot-mode" checked={isAutopilotOn} onCheckedChange={setIsAutopilotOn} />
            </div>
            <span className="text-cyan-300 text-sm mt-2">Let AI optimize your portfolio</span>
          </div>
          {isAutopilotOn && (
            <Alert className="max-w-xl mx-auto mt-6 text-left border-cyan-400/30 bg-cyan-400/10">
              <Circle className="h-4 w-4 text-cyan-400" />
              <AlertTitle className="text-cyan-300">Autopilot is Active!</AlertTitle>
              <AlertDescription className="text-cyan-200">
                Your portfolio is being automatically rebalanced for optimal performance.
              </AlertDescription>
            </Alert>
          )}
        </header>

        <section id="portfolio-dashboard" className="mb-16">
          <Card className="bg-gradient-to-br from-zinc-900/80 via-zinc-800/60 to-cyan-900/40 border-cyan-400/10 shadow-2xl rounded-3xl">
            <CardHeader>
              <CardTitle className="text-2xl flex items-center gap-2 text-white">
                <TrendingUp className="h-6 w-6" />
                Portfolio Performance (12 Months)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="aspect-video w-full">
                <ChartContainer config={chartConfig}>
                  <AreaChart
                    accessibilityLayer
                    data={portfolioData.performance}
                    margin={{ left: 12, right: 12, top: 20 }}
                  >
                    <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="rgba(59, 130, 246, 0.2)" />
                    <XAxis
                      dataKey="month"
                      tickLine={false}
                      axisLine={false}
                      tickMargin={8}
                      tickFormatter={(value) => value.slice(0, 3)}
                      tick={{ fill: '#9ca3af' }}
                    />
                    <YAxis
                      tickFormatter={(value) => `$${Number(value) / 1000}k`}
                      tickLine={false}
                      axisLine={false}
                      tick={{ fill: '#9ca3af' }}
                    />
                    <ChartTooltip
                      cursor={false}
                      content={<ChartTooltipContent indicator="dot" />}
                    />
                    <Area
                      dataKey="value"
                      type="natural"
                      fill="#1e209c"
                      fillOpacity={0.3}
                      stroke="#292bba"
                      strokeWidth={3}
                      stackId="a"
                    />
                  </AreaChart>
                </ChartContainer>
              </div>
            </CardContent>
            <CardFooter className="border-t border-zinc-700 p-8">
              <div className="flex flex-col sm:flex-row gap-6 w-full justify-between">
                <div className="flex-1 bg-gradient-to-br from-zinc-900/80 via-cyan-900/40 to-blue-900/40 border border-cyan-400/10 rounded-2xl shadow-lg p-6 flex flex-col items-center min-w-[220px]">
                  <div className="flex items-center gap-2 text-zinc-400 text-base font-medium mb-2">
                    <ArrowUpRight className="h-5 w-5 text-green-400" />
                    Total Return
                  </div>
                  <div className="text-3xl font-extrabold text-green-400 mb-1">+{portfolioData.metrics.totalReturn.toFixed(2)}%</div>
                  <div className="text-xs text-zinc-500">Since inception</div>
                  <div className="mt-2 pt-2 border-t border-zinc-700 w-full flex flex-col items-center">
                    <div className="text-lg font-bold text-green-400">+12.00%</div>
                    <div className="text-xs text-zinc-500">CAGR</div>
                  </div>
                </div>
                <div className="flex-1 bg-gradient-to-br from-zinc-900/80 via-cyan-900/40 to-blue-900/40 border border-cyan-400/10 rounded-2xl shadow-lg p-6 flex flex-col items-center min-w-[220px]">
                  <div className="flex items-center gap-2 text-zinc-400 text-base font-medium mb-2">
                    <Zap className="h-5 w-5 text-cyan-300" />
                    Volatility (Ann.)
                  </div>
                  <div className="text-3xl font-extrabold text-white mb-1">{portfolioData.metrics.volatility.toFixed(2)}%</div>
                  <div className="text-xs text-zinc-500">Annualized std. deviation</div>
                </div>
                <div className="flex-1 bg-gradient-to-br from-zinc-900/80 via-cyan-900/40 to-blue-900/40 border border-cyan-400/10 rounded-2xl shadow-lg p-6 flex flex-col items-center min-w-[220px]">
                  <div className="flex items-center gap-2 text-zinc-400 text-base font-medium mb-2">
                    <BarChart className="h-5 w-5 text-purple-300" />
                    Sharpe Ratio
                  </div>
                  <div className="text-3xl font-extrabold text-white mb-1">{portfolioData.metrics.sharpeRatio.toFixed(2)}</div>
                  <div className="text-xs text-zinc-500">Risk-adjusted return</div>
                </div>
              </div>
            </CardFooter>
          </Card>
        </section>
        
        <Separator className="my-16 bg-zinc-700" />

        <section id="strategy-discovery">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
                <h2 className="text-3xl font-bold text-white">
                Explore Strategies
                </h2>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <Filter className="w-4 h-4 text-zinc-400" />
                    <Select value={riskFilter} onValueChange={setRiskFilter}>
                      <SelectTrigger className="w-[180px] bg-zinc-800 border-zinc-700 text-white">
                        <SelectValue placeholder="Filter by risk..." />
                      </SelectTrigger>
                      <SelectContent className="bg-zinc-800 border-zinc-700">
                        <SelectItem value="all">All Risk Grades</SelectItem>
                        <SelectItem value="A">Risk Grade A</SelectItem>
                        <SelectItem value="B">Risk Grade B</SelectItem>
                        <SelectItem value="C">Risk Grade C</SelectItem>
                        <SelectItem value="D">Risk Grade D</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                   <div className="flex items-center gap-2">
                     <SortAsc className="w-4 h-4 text-zinc-400" />
                     <Select value={sortOrder} onValueChange={setSortOrder}>
                        <SelectTrigger className="w-[180px] bg-zinc-800 border-zinc-700 text-white">
                            <SelectValue placeholder="Sort by..." />
                        </SelectTrigger>
                        <SelectContent className="bg-zinc-800 border-zinc-700">
                            <SelectItem value="apy-desc">APY: High to Low</SelectItem>
                            <SelectItem value="apy-asc">APY: Low to High</SelectItem>
                        </SelectContent>
                     </Select>
                   </div>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {displayedStrategies.map((strategy) => (
                <StrategyCard
                    key={strategy.id}
                    strategy={strategy}
                    onInvest={handleInvestClick}
                />
                ))}
            </div>
            {displayedStrategies.length === 0 && (
                <div className="col-span-full text-center py-16 text-zinc-400 rounded-lg bg-zinc-800/50">
                  <p className="text-lg font-medium">No strategies match your criteria.</p>
                  <p className="text-sm">Try adjusting your filters.</p>
                </div>
            )}
        </section>
        </div>
      </main>
      <InvestDialog
        isOpen={isInvestDialogOpen}
        onClose={() => setInvestDialogOpen(false)}
        strategy={selectedStrategyForInvestment}
        onSubmit={handleInvestmentSubmit}
      />
      
      {/* Toast notifications */}
      <div className="fixed top-4 right-4 z-50 space-y-2">
        {toasts.map((toast) => (
          <Toast key={toast.id} className="bg-zinc-900 border-zinc-700 text-white">
            <ToastTitle>{toast.title}</ToastTitle>
            {toast.description && <ToastDescription>{toast.description}</ToastDescription>}
          </Toast>
        ))}
      </div>
    </>
  );
} 