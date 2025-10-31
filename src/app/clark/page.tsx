"use client"

import React, { useState, useEffect, useRef } from 'react'
import { Menu } from 'lucide-react'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import agentsApi from '@/lib/agents_api'
import { useRouter } from 'next/navigation'
import { ChatMessage } from './types'
import { categories } from './constants'
import CategoryTiles from './components/CategoryTiles'
import ChatInputBar from './components/ChatInterface'
import ResultsDisplay from './components/ResultsDisplay'



export default function BacktestPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [showMenu, setShowMenu] = useState(false)
  const [isPromptModalOpen, setIsPromptModalOpen] = useState(false)
  const feedRef = useRef<HTMLDivElement>(null)
  
  // Session management for mem0 integration
  const [userId, setUserId] = useState<string>('')
  const [sessionId, setSessionId] = useState<string>('')
  

  // Initialize session and user IDs on component mount
  useEffect(() => {
    // Generate or retrieve user ID (persistent across sessions)
    let storedUserId = localStorage.getItem('clark_user_id')
    if (!storedUserId) {
      storedUserId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      localStorage.setItem('clark_user_id', storedUserId)
    }
    setUserId(storedUserId)

    // Generate session ID (new for each browser session)
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    setSessionId(newSessionId)
  }, [])

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [messages])


  const handlePromptClick = async (prompt: string) => {
    setSelectedCategory(null)
    setIsPromptModalOpen(false)
    setInputValue('')
    
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: prompt,
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)
    
    try {
      const response = await agentsApi.post('/api/v1/agents/query', {
        query: prompt,
        user_id: userId,
        session_id: sessionId
      })

      const data = response.data
      
      const backtestResult = data.data?.backtest_result
      const screenerResult = data.data?.screener_type && data.data.screener_type !== 'economic' ? data.data : undefined
      const economicResult = data.data?.screener_type === 'economic' ? data.data : undefined
      const hasResults = Boolean(backtestResult || screenerResult || economicResult)
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: hasResults ? data.message : 'Sorry, I\'m unable to process your request at the moment.',
        timestamp: new Date(),
        parsedIntent: data.parsed_intent,
        success: data.success && hasResults ? true : false,
        backtestResult,
        screenerResult,
        economicResult
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('LangChain API error:', error)
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'Sorry, I\'m unable to process your request at the moment.',
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

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue,
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)
    
    try {
      const response = await agentsApi.post('/api/v1/agents/query', {
        query: inputValue,
        user_id: userId,
        session_id: sessionId
      })

      const data = response.data
      
      const backtestResult2 = data.data?.backtest_result
      const screenerResult2 = data.data?.screener_type && data.data.screener_type !== 'economic' ? data.data : undefined
      const economicResult2 = data.data?.screener_type === 'economic' ? data.data : undefined
      const hasResults2 = Boolean(backtestResult2 || screenerResult2 || economicResult2)
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: hasResults2 ? data.message : 'Sorry, I\'m unable to process your request at the moment.',
        timestamp: new Date(),
        parsedIntent: data.parsed_intent,
        success: data.success && hasResults2 ? true : false,
        backtestResult: backtestResult2,
        screenerResult: screenerResult2,
        economicResult: economicResult2
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('LangChain API error:', error)
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'Sorry, I\'m unable to process your request at the moment.',
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
      <header className="fixed top-0 left-0 right-0 z-50">
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
      {/* Spacer for fixed navbar height */}
      <div className="h-24" />

      {/* Main Content Area - continuous feed */}
      <div className={`container mx-auto px-4 py-2 max-w-6xl relative z-0`}>
        {/* Clark Logo - Show only when no user messages or results */}
        {!messages.some(m => m.type === 'user') && !messages.some(m => m.backtestResult || m.screenerResult || m.economicResult) && (
          <div className="flex items-center justify-center mb-2 mt-20 sm:mt-0">
            <img src="/clark.svg" alt="Clark" className="h-[7.28rem] w-[7.28rem] sm:h-[9.1rem] sm:w-[9.1rem] drop-shadow-[0_4px_16px_rgba(162,89,247,0.3)]" />
          </div>
        )}

        {/* Category Tiles - Show only when no user messages or results */}
        {!messages.some(m => m.type === 'user') && !messages.some(m => m.backtestResult || m.screenerResult || m.economicResult) && (
          <CategoryTiles
            categories={categories}
            selectedCategory={selectedCategory}
            onCategorySelect={setSelectedCategory}
            onPromptClick={handlePromptClick}
            isLoading={isLoading}
          />
        )}

        {/* Continuous Feed: scrollable area bounded by navbar (top) and chat input (bottom) */}
        <div className="dark">
          <div ref={feedRef} className="max-h-[calc(100vh-6rem-6.5rem)] overflow-y-auto">
            <ResultsDisplay messages={messages} isLoading={isLoading} />
          </div>
        </div>
        
        {/* Prompts modal opened by left icon */}
        <Dialog open={isPromptModalOpen} onOpenChange={setIsPromptModalOpen}>
          <DialogContent className="sm:max-w-2xl bg-zinc-900/95 border border-zinc-700/60 rounded-2xl">
            <div className="max-h-[70vh] overflow-y-auto px-2">
              {(!selectedCategory) && (
                <div className="w-full flex flex-col items-center">
                  <div className="w-full max-w-md space-y-3">
                    {categories.map((category) => (
                      <button
                        key={category.id}
                        onClick={() => setSelectedCategory(category.id)}
                        className="w-full text-left p-4 rounded-xl bg-zinc-800/40 hover:bg-zinc-700/60 border border-zinc-700/50 hover:border-purple-500/50 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          {category.icon.startsWith('/') ? (
                            <img src={category.icon} alt={category.title} className="h-5 w-5" />
                          ) : (
                            <span className="text-lg">{category.icon}</span>
                          )}
                          <div className="min-w-0">
                            <div className="text-white font-medium truncate">{category.title}</div>
                            <div className="text-xs text-zinc-400 truncate">{category.description}</div>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {selectedCategory && (
                <div className="w-full flex flex-col items-center space-y-4">
                  <div className="w-full max-w-md">
                    <button
                      onClick={() => setSelectedCategory(null)}
                      className="mb-3 text-xs text-zinc-400 hover:text-white"
                    >
                      ← Back
                    </button>
                    <div className="space-y-3">
                      {categories.find(c => c.id === selectedCategory)?.prompts.map((prompt, idx) => (
                        <button
                          key={idx}
                          onClick={() => handlePromptClick(prompt)}
                          disabled={isLoading}
                          className="w-full text-left p-4 rounded-xl bg-zinc-800/40 hover:bg-zinc-700/60 border border-zinc-700/50 hover:border-purple-500/50 transition-colors text-white disabled:opacity-50"
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>

      </div>

      {/* Chat Input Bar - fixed at bottom */}
      <ChatInputBar
        inputValue={inputValue}
        setInputValue={setInputValue}
        isLoading={isLoading}
        onSendMessage={handleSendMessage}
        onKeyPress={handleKeyPress}
        onOpenPromptModal={() => setIsPromptModalOpen(true)}
      />
    </div>
  )
}
