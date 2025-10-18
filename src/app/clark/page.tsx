"use client"

import React, { useState } from 'react'
import { Menu } from 'lucide-react'
import agentsApi from '@/lib/agents_api'
import { useRouter } from 'next/navigation'
import { ChatMessage } from './types'
import { categories } from './constants'
import { useQueryTransformation } from './hooks/useQueryTransformation'
import CategoryTiles from './components/CategoryTiles'
import ChatInterface from './components/ChatInterface'
import ResultsDisplay from './components/ResultsDisplay'



export default function BacktestPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      type: 'assistant',
      content: `Welcome! I'm Clark, your AI Portfolio Manager. I can help you with backtesting, technical analysis, crypto screening, and economic research. What would you like to explore today?`,
      timestamp: new Date(),
    }
  ])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [showMenu, setShowMenu] = useState(false)
  
  const { transformBacktestQuery } = useQueryTransformation(messages)


  const handlePromptClick = async (prompt: string) => {
    setSelectedCategory(null)
    setInputValue('')
    
    const transformedQuery = transformBacktestQuery(prompt)
    
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: prompt,
      timestamp: new Date(),
      transformedQuery: transformedQuery !== prompt ? transformedQuery : undefined,
    }

    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)
    
    try {
      const response = await agentsApi.post('/api/v1/agents/query', {
        query: transformedQuery,
        user_id: 'backtest_user'
      })

      const data = response.data
      
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: data.message,
        timestamp: new Date(),
        parsedIntent: data.parsed_intent,
        success: data.success,
        backtestResult: data.data?.backtest_result,
        screenerResult: data.data?.screener_type && data.data.screener_type !== 'economic' ? data.data : undefined,
        economicResult: data.data?.screener_type === 'economic' ? data.data : undefined
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('LangChain API error:', error)
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: new Date(),
        success: false,
      }

      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return

    const transformedQuery = transformBacktestQuery(inputValue)

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue,
      timestamp: new Date(),
      transformedQuery: transformedQuery !== inputValue ? transformedQuery : undefined,
    }

    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)
    
    try {
      const response = await agentsApi.post('/api/v1/agents/query', {
        query: transformedQuery,
        user_id: 'backtest_user'
      })

      const data = response.data
      
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: data.message,
        timestamp: new Date(),
        parsedIntent: data.parsed_intent,
        success: data.success,
        backtestResult: data.data?.backtest_result,
        screenerResult: data.data?.screener_type && data.data.screener_type !== 'economic' ? data.data : undefined,
        economicResult: data.data?.screener_type === 'economic' ? data.data : undefined
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('LangChain API error:', error)
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: new Date(),
        success: false,
      }

      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 overflow-x-hidden">
      {/* Navbar */}
      <header>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-2 min-h-[4rem]">
            <div className="flex items-center">
              <img
                src="/krypton_logo.svg"
                alt="Krypton Logo"
                className="h-20 w-auto drop-shadow-[0_2px_8px_rgba(16,255,180,0.18)]"
              />
            </div>
            <div className="flex items-center space-x-3">
              <div className="relative">
                <button
                  onClick={() => setShowMenu(!showMenu)}
                  className="flex items-center bg-zinc-800 hover:bg-zinc-700 text-white px-4 py-2 rounded-xl transition-colors font-medium"
                  aria-label="Open menu"
                >
                  <Menu className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="container mx-auto px-4 py-4 max-w-6xl pb-96">
        {/* Category Tiles */}
        <CategoryTiles
          categories={categories}
          selectedCategory={selectedCategory}
          onCategorySelect={setSelectedCategory}
          onPromptClick={handlePromptClick}
          isLoading={isLoading}
        />

        {/* Results Display */}
        <ResultsDisplay messages={messages} />
                    </div>

      {/* Chat Interface */}
      <ChatInterface
        messages={messages}
        inputValue={inputValue}
        setInputValue={setInputValue}
        isLoading={isLoading}
        onSendMessage={handleSendMessage}
                onKeyPress={handleKeyPress}
      />
    </div>
  )
}
