'use client';

import React, { useState, useRef, useEffect } from 'react';
import Image from 'next/image';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Loader2, Send, User } from 'lucide-react';
import agentsApi from '@/lib/agents_api';
import { Category } from '@/app/clark/types';

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  parsedIntent?: any;
  success?: boolean;
}

interface HedgeFundChatProps {
  userId?: string;
}

const hedgeFundCategories: Category[] = [
  {
    id: 'strategy',
    title: 'Strategy & Backtesting',
    icon: '/backtesting.svg',
    description: 'Test portfolio strategies',
    prompts: [
      'Backtest Bitcoin & Ethereum with 50% each from 01/01/2025 to 09/09/2025 with 1000 USD',
      'Backtest BTC & ETH 50/50 with monthly rebalancing from 01/01/2025 to 09/09/2025 with 1000 USD',
      'Backtest a strategy where Buy when RSI < 30 & Sell when RSI > 70 with 1000 USD from 01/01/2025 to 09/09/2025',
      'Backtest a strategy where Buy when EMA(9) crosses above EMA(21) and RSI(14) > 50 & Sell when EMA(9) crosses below EMA(21) or RSI(14) < 45 with 1000 USD from 01/01/2025 to 09/09/2025',
      'Backtest a strategy where Buy when MACD(12,26,9) cross up and ADX(14) > 20 & Sell when MACD cross down or ADX < 18 with 1000 USD from 01/01/2025 to 09/09/2025',
      'Backtest a strategy where Buy when Stochastic RSI %K < 20 and RSI(14) > 50 & Sell when Stochastic RSI %K > 80 with 1500 USD from 01/01/2025 to 09/09/2025',
      'Backtest using Super Trend on Bitcoin from 2025-01-01 to 2025-09-09 with 1000 USD'
    ]
  },
  {
    id: 'technical',
    title: 'Technical Analysis',
    icon: '/technical.svg',
    description: 'Analyze price trends',
    prompts: [
      'Plot RSI and moving averages for Bitcoin from 2025-01-01 to 2025-09-09',
      'Show Bollinger Bands for Ethereum over the last 6 months',
      'Display technical indicators for Solana and Cardano',
      'Plot 30, 100, and 200-day moving averages for BTC',
      'Show RSI analysis for ETH and ADA',
      'Overlay Stochastic RSI and RSI for BTC over the last quarter',
      'Show me Super Trend analysis for Bitcoin from 2025-01-01 to 2025-09-09'
    ]
  },
  {
    id: 'screeners',
    title: 'Crypto Screeners',
    icon: '/screener.svg',
    description: 'Filter cryptos for specific criteria',
    prompts: [
      'Find top 5 cryptos with price above $5',
      'Show me cryptos priced between $10 and $1000',
      'Find cryptos with daily gain over 30%',
      'Find cryptos near 52-week high',
      'Find cryptos with RSI bearish (oversold)',
      'Find cryptos with RSI bullish (overbought)',
      'Find cryptos with golden cross pattern',
      'Find top 5 cryptos with current price above 10 Day EMA',
      'Find top 5 cryptos with current price above 5 Day EMA'
    ]
  },
  {
    id: 'research',
    title: 'Market Research',
    icon: '/research.svg',
    description: 'Access economic data',
    prompts: [
      'Show me GDP data for top 10 countries',
      'What are the inflation rates for major economies?',
      'Display unemployment rates',
      'Show interest rates for countries',
      'Show me the latest economic news',
      'What\'s happening in the economy?',
      'Show economic calendar',
      'What are the upcoming economic events?'
    ]
  },
  {
    id: 'tax',
    title: 'Tax & Regulations',
    icon: '/tax.svg',
    description: 'Tax guidance and compliance',
    prompts: [
      'Summarize how crypto income is taxed in India, especially consulting fees or advisory revenue.',
      'What documentation should I prepare when responding to an Indian Section 142(1) crypto notice?',
      'Explain the TDS obligations for trades on foreign exchanges or DEXs from an Indian tax perspective.',
      'How does the Indian IT Department track offshore crypto wallets, and what risks trigger audits?',
      'Provide an overview of crypto tax obligations in Germany and any jurisdiction-specific nuances.'
    ]
  },
];

export default function HedgeFundChat({ userId = '' }: HedgeFundChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const callLangChainAPI = async (query: string) => {
    try {
      const response = await agentsApi.post('/api/v1/agents/query', {
        query: query,
        user_id: userId
      });
      if (response.status >= 400) {
        const errorText = response.data;
        console.error('API Error Response:', errorText);
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
      }

      const data = await response.data;
      return data;
    } catch (error) {
      console.error('Error calling LangChain API:', error);
      throw error;
    }
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    
    try {
      const response = await callLangChainAPI(inputValue);
      
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: response.message,
        timestamp: new Date(),
        parsedIntent: response.parsed_intent,
        success: response.success,
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Hedge Fund Chat API error:', error);
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: new Date(),
        success: false,
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePromptClick = async (prompt: string, categoryId?: string | null) => {
    setSelectedCategory(null);
    setInputValue('');
    
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: prompt,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    
    try {
      const response = await callLangChainAPI(prompt);
      
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: response.message,
        timestamp: new Date(),
        parsedIntent: response.parsed_intent,
        success: response.success,
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Hedge Fund Chat API error:', error);
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: new Date(),
        success: false,
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const formatTimestamp = (timestamp: Date) => {
    return timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const renderIntentBadge = (intent: any) => {
    if (!intent) return null;

    return (
      <div className="mt-3 space-y-2 text-xs text-white/60">
        <div className="flex flex-wrap gap-2">
          <span
            className={`rounded-full px-3 py-1 ${
              intent.confidence > 0.7
                ? 'border border-emerald-400/60 bg-emerald-400/10 text-emerald-100'
                : 'border border-white/20 bg-white/5 text-white/70'
            }`}
          >
            {intent.action} ({Math.round(intent.confidence * 100)}%)
          </span>
          {intent.currency && (
            <span className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-white/70">
              {intent.currency}
            </span>
          )}
          {intent.trading_pair && (
            <span className="rounded-full border border-blue-400/50 bg-blue-400/10 px-3 py-1 text-blue-100">
              {intent.trading_pair}
            </span>
          )}
          {intent.strategy && (
            <span className="rounded-full border border-green-400/50 bg-green-400/10 px-3 py-1 text-green-100">
              {intent.strategy}
            </span>
          )}
          {intent.timeframe && (
            <span className="rounded-full border border-purple-400/50 bg-purple-400/10 px-3 py-1 text-purple-100">
              {intent.timeframe}
            </span>
          )}
        </div>
        {intent.amount && (
          <div>Amount: {intent.amount}</div>
        )}
        {intent.recipient && (
          <div>Recipient: {intent.recipient}</div>
        )}
        {intent.trading_pair && intent.strategy && (
          <div>
            Trading: {intent.trading_pair} with {intent.strategy} strategy
          </div>
        )}
        {intent.action && intent.action.includes('trading') && (
          <div className="rounded-full border border-blue-400/40 bg-blue-500/10 px-3 py-1 text-[11px] text-blue-100">
            📊 Paper Trading Mode (Alpaca Sandbox)
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="w-full">
      <Card className="bg-zinc-800/50 backdrop-blur-sm border border-zinc-700/50 shadow-2xl rounded-3xl">
        <CardContent className="p-0">
          <div className="flex flex-col h-100" >
            {/* Clark Logo - Show only when no messages */}
            {messages.length === 0 && (
              <div className="flex flex-col items-center gap-2 md:gap-3 px-6 md:px-10 pb-3 md:pb-6 pt-6 md:pt-10 text-center shrink-0">
                <div className="h-12 w-12 md:h-16 md:w-16">
                  <Image
                    src="/clark.svg"
                    alt="Clark"
                    width={64}
                    height={64}
                    priority
                    className="h-full w-full object-contain"
                  />
                </div>
              </div>
            )}

            {/* Category Tiles - Show only when no messages */}
            {messages.length === 0 && (
              <div className="px-6 pt-2 pb-4">
                {/* Mobile: center 4 tiles on first page; 5th appears on swipe */}
                <div className="block md:hidden overflow-x-auto pb-2 -mx-2 snap-x snap-mandatory">
                  <div className="flex w-[100vw]">
                    {(() => {
                      const totalTiles = hedgeFundCategories.length;
                      const tilesPerRow = 2;
                      const totalRows = Math.ceil(totalTiles / tilesPerRow);
                      
                      const columns = Array.from({ length: totalRows }).map((_, colIndex) => {
                        const startIndex = colIndex * tilesPerRow;
                        const colTiles = hedgeFundCategories.slice(startIndex, startIndex + tilesPerRow);
                        return (
                          <div key={`col-${colIndex}`} className="flex flex-col gap-3">
                            {colTiles.map((category) => (
                              <Card
                                key={category.id}
                                className="cursor-pointer hover:bg-zinc-800/60 active:bg-zinc-700/60 transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] hover:shadow-lg border-zinc-700/50 bg-zinc-800/30 backdrop-blur-sm min-h-[80px] w-[calc(50vw-1.5rem)] touch-manipulation"
                                onClick={() => setSelectedCategory(category.id)}
                              >
                                <CardHeader className="pb-3 pt-3 px-3 h-full flex flex-col justify-center">
                                  <CardTitle className="text-xs text-white flex items-center gap-2 mb-1">
                                    {category.icon.startsWith('/') ? (
                                      <Image src={category.icon} alt={category.title} width={16} height={16} className="h-4 w-4 flex-shrink-0" />
                                    ) : (
                                      <span className="text-base flex-shrink-0">{category.icon}</span>
                                    )}
                                    <span className="truncate">{category.title}</span>
                                  </CardTitle>
                                  <CardDescription className="text-xs text-zinc-400 leading-tight line-clamp-2">
                                    {category.description}
                                  </CardDescription>
                                </CardHeader>
                              </Card>
                            ))}
                          </div>
                        );
                      });

                      const pages = [] as React.ReactNode[];
                      for (let i = 0; i < columns.length; i += 2) {
                        const hasSecondColumn = Boolean(columns[i + 1]);
                        pages.push(
                          <div key={`page-${i/2}`} className="min-w-full snap-start px-2">
                            <div className={`flex ${hasSecondColumn ? 'justify-center' : 'justify-start'} gap-3`}>
                              {columns[i]}
                              {columns[i + 1]}
                            </div>
                          </div>
                        );
                      }
                      return pages;
                    })()}
                  </div>
                </div>

                {/* Desktop: Single line layout */}
                <div className="hidden md:flex justify-between gap-3 flex-nowrap">
                  {hedgeFundCategories.map((category) => (
                    <Card
                      key={category.id}
                      className="cursor-pointer hover:bg-zinc-700/60 active:bg-zinc-600/60 transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] hover:shadow-lg border-zinc-700/50 bg-zinc-800/30 backdrop-blur-sm min-h-[90px] flex-1"
                      onClick={() => setSelectedCategory(category.id)}
                    >
                      <CardHeader className="pb-3 pt-3 px-3 h-full flex flex-col justify-center">
                        <CardTitle className="text-sm text-white flex items-center gap-2 mb-1">
                          {category.icon.startsWith('/') ? (
                            <Image src={category.icon} alt={category.title} width={20} height={20} className="h-5 w-5 flex-shrink-0" />
                          ) : (
                            <span className="text-lg flex-shrink-0">{category.icon}</span>
                          )}
                          <span className="truncate">{category.title}</span>
                        </CardTitle>
                        <CardDescription className="text-xs text-zinc-400 leading-tight line-clamp-2">
                          {category.description}
                        </CardDescription>
                      </CardHeader>
                    </Card>
                  ))}
                </div>
              </div>
            )}

            {/* Messages Area */}
            <div className={`flex-1 overflow-y-auto px-6 pb-4 space-y-4 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-white/10 min-h-0 ${messages.length > 0 ? 'pt-4' : ''}`}>
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex items-end gap-3 ${
                    message.type === 'user' ? 'flex-row-reverse' : 'flex-row'
                  }`}
                >
                  {message.type === 'user' ? (
                    <User className="h-5 w-5 text-zinc-400" />
                  ) : (
                    <Image
                      src="/clark.svg"
                      alt="Clark"
                      width={24}
                      height={24}
                      className="h-6 w-6"
                    />
                  )}

                  <div
                    className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-6 ${
                      message.type === 'user'
                        ? 'bg-emerald-400/90 text-[#04100A] shadow-[0_0_25px_rgba(52,211,153,0.25)]'
                        : 'border border-white/10 bg-white/[0.04] text-white/90 backdrop-blur-sm'
                    }`}
                  >
                    <div className="mb-2 flex items-center gap-2 text-xs font-medium">
                      <span className="uppercase tracking-wide">
                        {message.type === 'user' ? 'You' : 'Clark'}
                      </span>
                      <span className="text-white/50">
                        {formatTimestamp(message.timestamp)}
                      </span>
                      {/* {message.success !== undefined && (
                        message.success ? (
                          <CheckCircle className="h-4 w-4 text-emerald-400" />
                        ) : (
                          <XCircle className="h-4 w-4 text-rose-400" />
                        )
                      )} */}
                    </div>
                    <p>{message.content}</p>
                    {message.parsedIntent && renderIntentBadge(message.parsedIntent)}
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="flex items-end gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-400/10 ring-1 ring-emerald-400/30">
                    <Image
                      src="/clark.svg"
                      alt="Clark"
                      width={24}
                      height={24}
                      className="h-6 w-6"
                    />
                  </div>
                  <div className="max-w-[75%] rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white/70 backdrop-blur-sm">
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-emerald-300" />
                      <span>Processing your request...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            {/* <div className="p-4 border-t border-zinc-700/50"> */}
              <div className="flex p-2 items-center gap-3">
                <div className="relative flex-1">
                  <div className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 opacity-80">
                    <Image
                      src="/clark.svg"
                      alt="Clark"
                      width={18}
                      height={18}
                      className="h-5 w-5"
                    />
                  </div>
                  <Input
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyPress}
                    placeholder="Ask Clark"
                    disabled={isLoading}
                    className="h-12 rounded-full border-white/15 bg-white/[0.06] pl-12 pr-14 text-sm text-white placeholder:text-white/40 focus-visible:ring-1 focus-visible:ring-emerald-400"
                  />
                </div>
                <Button
                  onClick={handleSendMessage}
                  disabled={!inputValue.trim() || isLoading}
                  size="icon"
                  className="h-12 w-12 rounded-full bg-emerald-400 text-[#04100A] hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </div>
          {/* </div> */}
        </CardContent>
      </Card>

      {/* Prompts Modal */}
      {selectedCategory && (
        <div 
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setSelectedCategory(null)}
        >
          <Card 
            className="w-full max-w-2xl bg-zinc-900/95 border-zinc-700/50 shadow-2xl backdrop-blur-sm rounded-2xl max-h-[80vh]"
            onClick={(e) => e.stopPropagation()}
          >
            <CardHeader className="border-b border-zinc-700/50 p-6">
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <CardTitle className="text-lg text-white flex items-center gap-2">
                    {(() => {
                      const category = hedgeFundCategories.find(c => c.id === selectedCategory);
                      const icon = category?.icon || '';
                      return icon.startsWith('/') ? (
                        <Image src={icon} alt={category?.title || ''} width={24} height={24} className="h-6 w-6 flex-shrink-0" />
                      ) : (
                        <span className="text-2xl flex-shrink-0">{icon}</span>
                      );
                    })()}
                    <span className="truncate">{hedgeFundCategories.find(c => c.id === selectedCategory)?.title}</span>
                  </CardTitle>
                  <CardDescription className="text-zinc-400 mt-1 text-sm">
                    {hedgeFundCategories.find(c => c.id === selectedCategory)?.description}
                  </CardDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedCategory(null)}
                  className="text-zinc-400 hover:text-white h-8 w-8 p-0 ml-2 flex-shrink-0"
                >
                  ✕
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-4 p-6 max-h-[60vh] overflow-y-auto">
              <div className="space-y-3">
                {hedgeFundCategories.find(c => c.id === selectedCategory)?.prompts.map((prompt, index) => (
                  <button
                    key={index}
                    onClick={() => handlePromptClick(prompt, selectedCategory)}
                    disabled={isLoading}
                    className="w-full text-left p-4 rounded-lg bg-zinc-800/40 hover:bg-zinc-700/60 active:bg-zinc-600/60 border border-zinc-700/50 hover:border-purple-500/50 transition-all duration-200 text-white disabled:opacity-50 disabled:cursor-not-allowed group min-h-[60px] flex items-center"
                  >
                    <div className="flex items-start gap-3 w-full">
                      <span className="text-purple-400 font-bold text-sm mt-1 flex-shrink-0">•</span>
                      <span className="flex-1 text-sm group-hover:text-purple-300 transition-colors leading-relaxed">
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
  );
}

