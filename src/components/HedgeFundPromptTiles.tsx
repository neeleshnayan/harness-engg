"use client"

import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { TrendingUp, BarChart, BrainCircuit, DollarSign, PieChart, Zap } from 'lucide-react'

interface Category {
  id: string
  title: string
  icon: React.ReactNode
  description: string
  prompts: string[]
}

const hedgeFundCategories: Category[] = [
  {
    id: 'strategy',
    title: 'Strategy Analysis',
    icon: <TrendingUp className="h-5 w-5" />,
    description: 'Analyze investment strategies',
    prompts: [
      'What is the best strategy for my risk profile?',
      'Compare ETH-BTC Momentum vs Blue Chip Stable Yield',
      'Show me strategies with Sharpe ratio above 2.0',
      'What strategies have the lowest max drawdown?',
      'Recommend strategies based on my portfolio goals'
    ]
  },
  {
    id: 'performance',
    title: 'Performance Insights',
    icon: <BarChart className="h-5 w-5" />,
    description: 'Get portfolio performance data',
    prompts: [
      'What is my current portfolio performance?',
      'Show me my total returns this month',
      'What is my portfolio Sharpe ratio?',
      'Compare my performance to the market',
      'Show me my best and worst performing strategies'
    ]
  },
  {
    id: 'allocation',
    title: 'Portfolio Allocation',
    icon: <PieChart className="h-5 w-5" />,
    description: 'Optimize your allocations',
    prompts: [
      'How should I allocate my funds across strategies?',
      'What is my current allocation breakdown?',
      'Suggest optimal allocation for risk grade A strategies',
      'Show me diversification opportunities',
      'What is the recommended allocation for my goals?'
    ]
  },
  {
    id: 'risk',
    title: 'Risk Management',
    icon: <BrainCircuit className="h-5 w-5" />,
    description: 'Assess and manage risk',
    prompts: [
      'What is my portfolio risk level?',
      'Show me strategies with risk grade A',
      'What is the max drawdown of my current portfolio?',
      'How can I reduce portfolio volatility?',
      'Analyze risk-adjusted returns'
    ]
  },
  {
    id: 'investment',
    title: 'Investment Actions',
    icon: <DollarSign className="h-5 w-5" />,
    description: 'Make investment decisions',
    prompts: [
      'Invest 1000 USDC in ETH-BTC Momentum',
      'Show me investment opportunities',
      'What is the minimum investment for Blue Chip Stable Yield?',
      'Compare performance fees across strategies',
      'What strategies have no cooldown period?'
    ]
  },
  {
    id: 'autopilot',
    title: 'Autopilot',
    icon: <Zap className="h-5 w-5" />,
    description: 'AI-powered rebalancing',
    prompts: [
      'How does autopilot work?',
      'Enable autopilot for my portfolio',
      'What strategies does autopilot recommend?',
      'Show me autopilot rebalancing history',
      'Optimize my portfolio with autopilot'
    ]
  }
]

interface HedgeFundPromptTilesProps {
  selectedCategory: string | null
  onCategorySelect: (categoryId: string | null) => void
  onPromptClick: (prompt: string, categoryId: string) => void
  isLoading: boolean
}

export default function HedgeFundPromptTiles({
  selectedCategory,
  onCategorySelect,
  onPromptClick,
  isLoading
}: HedgeFundPromptTilesProps) {
  return (
    <div className="pb-1 mb-1">
      {/* Category Tiles */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 w-full">
        {hedgeFundCategories.map((category) => (
          <Card
            key={category.id}
            className="cursor-pointer hover:bg-zinc-800/60 active:bg-zinc-700/60 transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] hover:shadow-lg border-zinc-700/50 bg-zinc-800/30 backdrop-blur-sm min-h-[100px] touch-manipulation"
            onClick={() => onCategorySelect(category.id)}
          >
            <CardHeader className="pb-3 pt-4 px-3 h-full flex flex-col justify-center items-center text-center">
              <div className="text-cyan-400 mb-2">
                {category.icon}
              </div>
              <CardTitle className="text-xs text-white mb-1">
                {category.title}
              </CardTitle>
              <CardDescription className="text-[10px] text-zinc-400 leading-tight line-clamp-2">
                {category.description}
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>

      {/* Prompts Modal */}
      {selectedCategory && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
             onClick={() => onCategorySelect(null)}>
          <Card className="w-full h-[85vh] sm:h-auto sm:max-h-[80vh] sm:max-w-2xl bg-zinc-900/95 border-zinc-700/50 shadow-2xl backdrop-blur-sm rounded-t-2xl sm:rounded-2xl"
                onClick={(e) => e.stopPropagation()}>
            <CardHeader className="border-b border-zinc-700/50 p-4 sm:p-6">
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <CardTitle className="text-base sm:text-lg text-white flex items-center gap-2">
                    {(() => {
                      const category = hedgeFundCategories.find(c => c.id === selectedCategory);
                      return (
                        <>
                          <div className="text-cyan-400">
                            {category?.icon}
                          </div>
                          <span className="truncate">{category?.title}</span>
                        </>
                      );
                    })()}
                  </CardTitle>
                  <CardDescription className="text-zinc-400 mt-1 text-xs sm:text-sm line-clamp-2">
                    {hedgeFundCategories.find(c => c.id === selectedCategory)?.description}
                  </CardDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onCategorySelect(null)}
                  className="text-zinc-400 hover:text-white h-8 w-8 p-0 ml-2 flex-shrink-0 touch-manipulation"
                >
                  ✕
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-4 p-4 sm:p-6 max-h-[calc(85vh-120px)] sm:max-h-[60vh] overflow-y-auto">
              <div className="space-y-3">
                {hedgeFundCategories.find(c => c.id === selectedCategory)?.prompts.map((prompt, index) => (
                  <button
                    key={index}
                    onClick={() => onPromptClick(prompt, selectedCategory)}
                    disabled={isLoading}
                    className="w-full text-left p-4 rounded-lg bg-zinc-800/40 hover:bg-zinc-700/60 active:bg-zinc-600/60 border border-zinc-700/50 hover:border-cyan-500/50 transition-all duration-200 text-white disabled:opacity-50 disabled:cursor-not-allowed group touch-manipulation min-h-[60px] flex items-center"
                  >
                    <div className="flex items-start gap-3 w-full">
                      <span className="text-cyan-400 font-bold text-sm mt-1 flex-shrink-0">•</span>
                      <span className="flex-1 text-sm sm:text-base group-hover:text-cyan-300 transition-colors leading-relaxed">
                        {prompt}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}

