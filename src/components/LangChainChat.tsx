'use client';

import React, { useState, useRef, useEffect } from 'react';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Loader2, Send, User, CheckCircle, XCircle, X } from 'lucide-react';
import agentsApi from '@/lib/agents_api';
import { parseErrorMessage } from '@/lib/parseError';

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  parsedIntent?: any;
  success?: boolean;
}

interface LangChainChatProps {
  userId?: string;
  onBalanceRefresh?: () => void;
  onBalanceFlicker?: () => void;
  onTransactionRefresh?: () => void;
  onClose?: () => void;
}

export default function LangChainChat({ 
  userId = '', 
  onBalanceRefresh, 
  onBalanceFlicker, 
  onTransactionRefresh,
  onClose
}: LangChainChatProps) {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const [userName, setUserName] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initialize session ID and username
  useEffect(() => {
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
    setSessionId(newSessionId)
    
    // Extract username from localStorage
    const storedUserData = localStorage.getItem('userData')
    if (storedUserData) {
      try {
        const parsedData = JSON.parse(storedUserData)
        if (parsedData.username) {
          setUserName(parsedData.username)
        }
      } catch (error) {
        console.error('Error parsing user data:', error)
      }
    }
  }, []);

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
      // Make actual API call to LangChain service
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
      
      // Check if this was a successful USDC transaction and trigger balance refresh/flicker
      if (response.success && response.parsed_intent) {
        const intent = response.parsed_intent;
        // Check if it's a send USDC action with high confidence
        if (intent.action === 'send_usdc' && intent.confidence > 0.7) {
          // Trigger balance flicker effect
          if (onBalanceFlicker) {
            onBalanceFlicker();
          }
          // Trigger balance refresh
          if (onBalanceRefresh) {
            onBalanceRefresh();
          }
          // Trigger transaction history refresh
          if (onTransactionRefresh) {
            onTransactionRefresh();
          }
        }
      }
    } catch (error) {
      console.error('LangChain API error:', error);
      const content = parseErrorMessage(error, 'Sorry, I encountered an error processing your request. Please try again.');
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content,
        timestamp: new Date(),
        success: false,
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const callLangChainAPI = async (query: string) => {
    try {
      const response = await agentsApi.post('/api/v1/agents/query', {
        query: query,
        user_id: userId,
        username: userName,
        session_id: sessionId
      });
      if (response.status >= 400) {
        const errorText = response.data;
        console.error('API Error Response:', errorText);
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
      }

      return response.data;
    } catch (error) {
      console.error('Error calling LangChain API:', error);
      throw error;
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
    <div className="flex w-full items-center justify-center">
      <div className="relative w-full h-[20vh] md:h-auto max-w-md md:max-w-full flex flex-col overflow-hidden rounded-3xl border border-white/10 bg-[#0B0F13] text-white shadow-[0_20px_60px_rgba(0,0,0,0.35)]">
        <div className="absolute right-4 top-4 z-10">
          <button
            type="button"
            onClick={() => router.push('/clark')}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white transition hover:border-white/30 hover:bg-white/10"
            aria-label="Close Clark chat"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {messages.length === 0 && (
          <div className="flex flex-col items-center gap-2 md:gap-3 px-6 md:px-10 pb-3 md:pb-6 pt-6 md:pt-10 text-center shrink-0">
            <div className="h-12 w-12 md:h-20 md:w-20">
              <Image
                src="/clark.svg"
                alt="Clark"
                width={10}
                height={10}
                priority
                className="h-full w-full object-contain"
              />
            </div>
          </div>
        )}

        <div className={`flex flex-1 flex-col gap-4 overflow-y-auto px-6 pb-4 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-white/10 min-h-0 ${messages.length > 0 ? 'pt-4' : ''}`}>
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex items-end gap-3 ${
                message.type === 'user' ? 'flex-row-reverse' : 'flex-row'
              }`}
            >
              
                {message.type === 'user' ? (
                  <User className="h-5 w-5" />
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
                  {message.success !== undefined && (
                    message.success ? (
                      <CheckCircle className="h-4 w-4 text-emerald-400" />
                    ) : (
                      <XCircle className="h-4 w-4 text-rose-400" />
                    )
                  )}
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

        <div className="p-2">
          <div className="flex items-center gap-3">
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
                placeholder="Ask Clark to send USDC or check balances..."
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
      </div>
    </div>
  );
}
