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
    <div className="fixed bottom-0 left-0 right-0 z-40">
      <div className="container mx-auto px-4 max-w-6xl">
        <Card className="rounded-t-2xl sm:rounded-none border-0 shadow-2xl bg-zinc-900/95 backdrop-blur-md border-t border-zinc-700/50">
        <CardContent className="p-0">
          {/* Combined Chat Interface */}
          <div className={`flex flex-col ${messages.length <= 1 ? 'h-50 sm:h-52' : 'h-56 sm:h-56'}`}>
            {/* Chat Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 border-b border-zinc-700/50 scrollbar-thin scrollbar-thumb-zinc-600 scrollbar-track-transparent">
              {messages.length === 0 ? (
                <div className="flex items-center justify-center h-full text-zinc-400">
                  <div className="text-center">
                    <img src="/clark process.svg" alt="Clark" className="h-12 w-12 mx-auto mb-3 opacity-60" />
                    <p className="text-sm">Start a conversation with Clark</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex gap-3 ${
                        message.type === 'user' ? 'justify-end' : 'justify-start'
                      }`}
                    >
                      {message.type === 'assistant' && (
                        <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                          <img src="/clark process.svg" alt="Clark" className="h-8 w-8" />
                        </div>
                      )}
                      
                      <div
                        className={`max-w-[85%] ${
                          message.type === 'user'
                            ? 'rounded-2xl p-4 bg-gradient-to-r from-blue-500 to-purple-600 text-white'
                            : message.success === false
                            ? 'text-white'
                            : 'rounded-2xl p-4 bg-zinc-800/60 border border-zinc-700/50 text-white backdrop-blur-sm'
                        }`}
                      >
                        {(message.type === 'user' || message.success !== false) && (
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
                        )}
                        
                        <div className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</div>
                          
                        {message.success !== false && message.parsedIntent && renderIntentBadge(message.parsedIntent)}
                          
                        {message.success !== false && message.parsedIntent?.custom_allocations && (
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
                        <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                          <User className="h-4 w-4 text-blue-400" />
                        </div>
                      )}
                    </div>
                  ))}
                  
                  {isLoading && (
                    <div className="flex gap-3 justify-start">
                      <div className="w-8 h-8 flex items-center justify-center">
                        <img src="/clark process.svg" alt="Clark" className="h-8 w-8" />
                      </div>
                      <div className="bg-zinc-800/60 border border-zinc-700/50 rounded-2xl p-4 backdrop-blur-sm">
                        <div className="flex items-center gap-2">
                          <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
                          <span className="text-sm text-white">Processing your request...</span>
                        </div>
                      </div>
                    </div>
                  )}
                  
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* Input Area */}
            <div className="p-4 bg-zinc-800/30 backdrop-blur-sm">
              <div className="flex gap-3">
                <Input
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={onKeyPress}
                  placeholder="Ask me anything..."
                  disabled={isLoading}
                  className="flex-1 bg-zinc-800/60 border-zinc-700/50 text-white placeholder:text-zinc-400 focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20 rounded-xl h-12"
                />
                <Button
                  onClick={onSendMessage}
                  disabled={!inputValue.trim() || isLoading}
                  size="icon"
                  className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 border-0 rounded-xl shadow-lg h-12 w-12"
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      </div>
    </div>
  )
}
