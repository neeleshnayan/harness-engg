"use client"

import React, { useRef, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Send, User, CheckCircle, XCircle, Loader2 } from 'lucide-react'
import { ChatMessage } from '../types'
import { formatTimestamp } from '../utils'

interface ChatInterfaceProps {
  messages: ChatMessage[]
  inputValue: string
  setInputValue: (value: string) => void
  isLoading: boolean
  onSendMessage: () => void
  onKeyPress: (e: React.KeyboardEvent) => void
}

export default function ChatInterface({
  messages,
  inputValue,
  setInputValue,
  isLoading,
  onSendMessage,
  onKeyPress
}: ChatInterfaceProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const renderIntentBadge = (intent: any) => {
    if (!intent) return null

    return (
      <div className="mt-2 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant={intent.confidence > 0.7 ? 'default' : 'secondary'}>
            {intent.action} ({Math.round(intent.confidence * 100)}%)
          </Badge>
          {intent.strategy && (
            <Badge variant="outline" className="bg-green-100 text-green-800">
              {intent.strategy === 'custom' ? 'Custom Portfolio' : intent.strategy}
            </Badge>
          )}
          {intent.start_date && (
            <Badge variant="outline" className="bg-blue-100 text-blue-800">
              {intent.start_date}
            </Badge>
          )}
          {intent.end_date && (
            <Badge variant="outline" className="bg-blue-100 text-blue-800">
              {intent.end_date}
            </Badge>
          )}
          {intent.initial_capital && (
            <Badge variant="outline" className="bg-purple-100 text-purple-800">
              ${intent.initial_capital}
            </Badge>
          )}
          {intent.rebalance_frequency && (
            <Badge variant="outline" className="bg-orange-100 text-orange-800">
              {intent.rebalance_frequency}
            </Badge>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="fixed bottom-0 left-0 right-0">
      <Card className="rounded-none border-0 shadow-xl bg-transparent backdrop-blur-sm">
        <CardContent className="p-4">
          {/* Chat Messages */}
          <div className="h-40 overflow-y-auto border rounded-lg p-3 mb-3 bg-zinc-900/40 border-zinc-700/50 scrollbar-thin scrollbar-thumb-zinc-600 scrollbar-track-transparent">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex gap-3 mb-4 ${
                  message.type === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                {message.type === 'assistant' && (
                  <div className="w-8 h-8 flex items-center justify-center">
                    <img src="/clark process.svg" alt="Clark" className="h-8 w-8" />
                  </div>
                )}
                
                <div
                  className={`max-w-[85%] rounded-lg p-3 ${
                    message.type === 'user'
                      ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white'
                      : 'bg-zinc-800/60 border border-zinc-700/50 text-white backdrop-blur-sm'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-medium text-white/90">
                      {message.type === 'user' ? 'You' : 'Clark'}
                    </span>
                    <span className="text-xs text-zinc-400/80">
                      {formatTimestamp(message.timestamp)}
                    </span>
                    {message.success !== undefined && (
                      message.success ? (
                        <CheckCircle className="h-3 w-3 text-green-400" />
                      ) : (
                        <XCircle className="h-3 w-3 text-red-400" />
                      )
                    )}
                  </div>
                  
                  <div className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</div>
                    
                  {message.transformedQuery && (
                    <div className="mt-3 p-3 bg-purple-500/10 rounded-lg border border-purple-500/20">
                      <h4 className="text-sm font-semibold text-purple-300 mb-2">✨ Query Enhanced:</h4>
                      <div className="text-xs text-purple-200 whitespace-pre-wrap leading-relaxed">
                        {message.transformedQuery}
                      </div>
                    </div>
                  )}
                    
                  {message.parsedIntent && renderIntentBadge(message.parsedIntent)}
                    
                  {message.parsedIntent?.custom_allocations && (
                    <div className="mt-3 p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
                      <h4 className="text-sm font-semibold text-blue-300 mb-2">Custom Portfolio Allocation:</h4>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        {Object.entries(message.parsedIntent.custom_allocations).map(([asset, percentage]) => (
                          <div key={asset} className="flex justify-between">
                            <span className="text-blue-200">{asset.replace('/USDT', '')}:</span>
                            <span className="font-medium text-blue-100">{percentage as number}%</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                
                {message.type === 'user' && (
                  <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center">
                    <User className="h-4 w-4 text-blue-400" />
                  </div>
                )}
              </div>
            ))}
            
            {isLoading && (
              <div className="flex gap-3 mb-4 justify-start">
                <div className="w-8 h-8 flex items-center justify-center">
                  <img src="/clark process.svg" alt="Clark" className="h-8 w-8" />
                </div>
                <div className="bg-zinc-800/60 border border-zinc-700/50 rounded-lg p-3 backdrop-blur-sm">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
                    <span className="text-sm text-white">Processing your request...</span>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="flex gap-3">
            <Input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={onKeyPress}
              placeholder="Ask me anything about backtesting, technical analysis, or market research..."
              disabled={isLoading}
              className="flex-1 bg-zinc-800/60 border-zinc-700/50 text-white placeholder:text-zinc-400 focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20 rounded-lg"
            />
            <Button
              onClick={onSendMessage}
              disabled={!inputValue.trim() || isLoading}
              size="icon"
              className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 border-0 rounded-lg shadow-lg"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
