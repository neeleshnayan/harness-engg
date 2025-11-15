'use client';

import { useState, useMemo, useEffect, useRef } from 'react';
import HedgeFundQuestionnaire from './HedgeFundQuestionnaire';
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
  Bot,
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
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import HedgeFundChat from '@/components/HedgeFundChat';

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
  const router = useRouter();
  const [strategies, setStrategies] = useState<Strategy[]>(initialStrategies);
  const [selectedStrategyForInvestment, setSelectedStrategyForInvestment] = useState<Strategy | null>(null);
  const [isInvestDialogOpen, setInvestDialogOpen] = useState(false);
  const autopilotIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const { toast, toasts, dismiss } = useToast();

  const [isAutopilotOn, setIsAutopilotOn] = useState(false);
  const [showQuestionnaire, setShowQuestionnaire] = useState(false);
  const [riskFilter, setRiskFilter] = useState('all');
  const [sortOrder, setSortOrder] = useState('apy-desc');
  const [userId, setUserId] = useState<string>('');

  // Get userId from localStorage
  useEffect(() => {
    const storedUserData = localStorage.getItem('userData');
    if (storedUserData) {
      try {
        const parsedData = JSON.parse(storedUserData);
        const actualUserId = parsedData.user_id;
        setUserId(actualUserId || '');
      } catch (error) {
        console.error('Error parsing user data:', error);
        setUserId('');
      }
    }
  }, []);

  useEffect(() => {
    if (isAutopilotOn) {
      setShowQuestionnaire(true);
    }
    if (!isAutopilotOn) {
      setShowQuestionnaire(false);
      if (autopilotIntervalRef.current) {
        clearInterval(autopilotIntervalRef.current);
      }
    }
  }, [isAutopilotOn]);

  // Start autopilot rebalancing only after questionnaire is completed
  useEffect(() => {
    if (isAutopilotOn && !showQuestionnaire) {
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
              description: `Removed \"${removedStrategy.name}\" and added \"${newStrategy.name}\".`,
            });
            return [...remainingStrategies, newStrategy];
          }
          return prevStrategies; // No change if no new strategies are available
        });
      }, 5000);
    }
    return () => {
      if (autopilotIntervalRef.current) {
        clearInterval(autopilotIntervalRef.current);
      }
    };
  }, [isAutopilotOn, showQuestionnaire]);

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
      {showQuestionnaire && (
        <HedgeFundQuestionnaire
          onComplete={() => setShowQuestionnaire(false)}
          onClose={() => {
            setShowQuestionnaire(false);
            setIsAutopilotOn(false);
          }}
          showBackButton={true}
        />
      )}
      {!showQuestionnaire && (
        <main className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900">
          <div className="container mx-auto px-4 py-8">
          <header className="flex flex-col md:flex-row justify-between items-center mb-8">
            <div>
              <h1 className="text-4xl font-bold text-white">Hedge Fund Dashboard</h1>
              <p className="text-lg text-zinc-400 mt-1">Your portfolio overview and strategy hub.</p>
            </div>
            <div className="flex items-center gap-3 mt-4 md:mt-0">
              <Button
                onClick={() => router.push('/clark')}
                className="bg-gradient-to-r from-purple-500 to-blue-600 hover:from-purple-600 hover:to-blue-700 text-white font-semibold px-6 py-2 rounded-lg transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] flex items-center gap-2"
              >
                <img src="/clark.svg" alt="Clark" className="h-8 w-8" />
              </Button>
              <div className="flex items-center gap-3 px-4 py-2 bg-zinc-800/50 border border-zinc-700/50 rounded-lg">
                <Label htmlFor="autopilot-mode" className="text-white font-medium">Autopilot</Label>
                <Switch id="autopilot-mode" checked={isAutopilotOn} onCheckedChange={setIsAutopilotOn} />
                <BrainCircuit className="h-5 w-5 text-cyan-400" />
              </div>
            </div>
          </header>

          {isAutopilotOn && (
            <Alert className="mb-8 border-cyan-400/30 bg-cyan-400/10 text-cyan-200">
              <Circle className="h-4 w-4" />
              <AlertTitle className="text-cyan-300">Autopilot is Active!</AlertTitle>
              <AlertDescription>
                The AI is automatically rebalancing your portfolio for optimal performance.
              </AlertDescription>
            </Alert>
          )}

          <section id="portfolio-dashboard" className="mb-4">
            <Card className="bg-zinc-800/50 backdrop-blur-sm border border-zinc-700/50 shadow-2xl rounded-3xl">
              <CardHeader>
                <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4">
                  <div>
                    <CardTitle className="text-2xl flex items-center gap-2 text-white">
                      <TrendingUp className="h-6 w-6" />
                      Portfolio Performance
                    </CardTitle>
                    <CardDescription>Last 12 months performance</CardDescription>
                  </div>
                  <div className="flex items-center gap-x-6 gap-y-2 flex-wrap">
                    <div className="flex items-center gap-2">
                      <ArrowUpRight className="h-5 w-5 text-green-400" />
                      <div>
                        <p className="text-xs text-zinc-400">Total Return</p>
                        <p className="text-base font-bold text-white">+{portfolioData.metrics.totalReturn.toFixed(2)}%</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Zap className="h-5 w-5 text-cyan-400" />
                      <div>
                        <p className="text-xs text-zinc-400">Volatility</p>
                        <p className="text-base font-bold text-white">{portfolioData.metrics.volatility.toFixed(2)}%</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <BarChart className="h-5 w-5 text-purple-400" />
                      <div>
                        <p className="text-xs text-zinc-400">Sharpe Ratio</p>
                        <p className="text-base font-bold text-white">{portfolioData.metrics.sharpeRatio.toFixed(2)}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="aspect-video w-full">
                  <ChartContainer config={chartConfig}>
                    <AreaChart
                      accessibilityLayer
                      data={portfolioData.performance}
                      margin={{ left: 12, right: 12, top: 20 }}
                    >
                      <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.1)" />
                      <XAxis
                        dataKey="month"
                        tickLine={false}
                        axisLine={false}
                        tickMargin={8}
                        tickFormatter={(value) => value.slice(0, 3)}
                        tick={{ fill: '#9ca3af' }}
                      />
                      <YAxis
                        tickFormatter={(value) => `${Number(value) / 1000}k`}
                        tickLine={false}
                        axisLine={false}
                        tick={{ fill: '#9ca3af' }}
                      />
                      <ChartTooltip
                        cursor={false}
                        content={<ChartTooltipContent indicator="dot" labelClassName="text-zinc-400" className="bg-zinc-900/80 backdrop-blur-sm border-zinc-700/50"/>}
                      />
                      <Area
                        dataKey="value"
                        type="natural"
                        fill="rgba(59, 130, 246, 0.1)"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        stackId="a"
                      />
                    </AreaChart>
                  </ChartContainer>
                </div>
              </CardContent>

            </Card>
          </section>

          {/* <Separator className="my-2 bg-zinc-800" /> */}

          <section id="clark-chat" className="mb-4">
            <HedgeFundChat userId={userId} />
          </section>

          <Separator className="my-2 bg-zinc-800" />

          <section id="strategy-discovery">
              <div className="flex flex-col md:flex-row justify-between items-center gap-4 mb-8">
                  <h2 className="text-3xl font-bold text-white">
                    Strategy Marketplace
                  </h2>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <Filter className="w-5 h-5 text-zinc-400" />
                      <Select value={riskFilter} onValueChange={setRiskFilter}>
                        <SelectTrigger className="w-[160px] bg-zinc-900/50 border-zinc-700 text-white">
                          <SelectValue placeholder="Filter by risk..." />
                        </SelectTrigger>
                        <SelectContent className="bg-zinc-900 border-zinc-700 text-white">
                          <SelectItem value="all">All Risk Grades</SelectItem>
                          <SelectItem value="A">Risk Grade A</SelectItem>
                          <SelectItem value="B">Risk Grade B</SelectItem>
                          <SelectItem value="C">Risk Grade C</SelectItem>
                          <SelectItem value="D">Risk Grade D</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                     <div className="flex items-center gap-2">
                       <SortAsc className="w-5 h-5 text-zinc-400" />
                       <Select value={sortOrder} onValueChange={setSortOrder}>
                          <SelectTrigger className="w-[160px] bg-zinc-900/50 border-zinc-700 text-white">
                              <SelectValue placeholder="Sort by..." />
                          </SelectTrigger>
                          <SelectContent className="bg-zinc-900 border-zinc-700 text-white">
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
                  <div className="col-span-full text-center py-20 px-4 text-zinc-400 rounded-lg bg-zinc-800/50 border border-zinc-700/50">
                    <Zap className="mx-auto h-12 w-12 text-zinc-500 mb-4" />
                    <h3 className="text-xl font-semibold text-white">No Strategies Found</h3>
                    <p className="text-zinc-500 mt-2">Try adjusting your filters to discover new opportunities.</p>
                  </div>
              )}
          </section>
          </div>
        </main>
      )}
      <InvestDialog
        isOpen={isInvestDialogOpen}
        onClose={() => setInvestDialogOpen(false)}
        strategy={selectedStrategyForInvestment}
        onSubmit={handleInvestmentSubmit}
      />

      <div className="fixed top-4 right-4 z-50 space-y-2">
        {toasts.map((toast) => (
          <Toast key={toast.id} className="bg-zinc-800/50 backdrop-blur-sm border-zinc-700/50 text-white">
            <div className="flex items-start gap-3">
              <BrainCircuit className="h-5 w-5 text-cyan-400 mt-1" />
              <div>
                <ToastTitle>{toast.title}</ToastTitle>
                {toast.description && <ToastDescription>{toast.description}</ToastDescription>}
              </div>
            </div>
          </Toast>
        ))}
      </div>
    </>
  );
}