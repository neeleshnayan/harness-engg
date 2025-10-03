'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Loader2, Send, Bot, User, CheckCircle, XCircle } from 'lucide-react';
import agentsApi from '@/lib/agents_api';

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
}

export default function LangChainChat({ 
  userId = '', 
  onBalanceRefresh, 
  onBalanceFlicker, 
  onTransactionRefresh 
}: LangChainChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      type: 'assistant',
      content: 'Hello! I can help you with financial actions and automated paper trading. Try saying "Send 100 USDC to Krypton", "Check my balance", or "Start trading BTC/USD" (paper trading mode).',

      timestamp: new Date(),
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

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

      const data = await response.data
      return data;
    } catch (error) {
      console.error('Error calling LangChain API:', error);
      throw error;
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
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
      <div className="mt-2 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant={intent.confidence > 0.7 ? 'default' : 'secondary'}>
            {intent.action} ({Math.round(intent.confidence * 100)}%)
          </Badge>
          {intent.currency && (
            <Badge variant="outline">{intent.currency}</Badge>
          )}
          {intent.trading_pair && (
            <Badge variant="outline" className="bg-blue-100 text-blue-800">
              {intent.trading_pair}
            </Badge>
          )}
          {intent.strategy && (
            <Badge variant="outline" className="bg-green-100 text-green-800">
              {intent.strategy}
            </Badge>
          )}
          {intent.timeframe && (
            <Badge variant="outline" className="bg-purple-100 text-purple-800">
              {intent.timeframe}
            </Badge>
          )}
        </div>
        {intent.amount && (
          <div className="text-sm text-muted-foreground">
            Amount: {intent.amount}
          </div>
        )}
        {intent.recipient && (
          <div className="text-sm text-muted-foreground">
            Recipient: {intent.recipient}
          </div>
        )}
          {intent.trading_pair && intent.strategy && (
            <div className="text-sm text-muted-foreground">
              Trading: {intent.trading_pair} with {intent.strategy} strategy
            </div>
          )}
          {intent.action && intent.action.includes('trading') && (
            <div className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded mt-1">
              📊 Paper Trading Mode (Alpaca Sandbox)
            </div>
          )}
      </div>
    );
  };

  return (
    <div className="max-w-4xl mx-auto p-4">
      <Card>
        <br/>
        <CardContent>
          {/* Chat Messages */}
          <div className="h-40 overflow-y-auto border rounded-lg p-4 mb-4 bg-muted/20">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex gap-3 mb-4 ${
                  message.type === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                {message.type === 'assistant' && (
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                )}
                
                <div
                  className={`max-w-[80%] rounded-lg p-3 ${
                    message.type === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-background border'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium">
                      {message.type === 'user' ? 'You' : 'Assistant'}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatTimestamp(message.timestamp)}
                    </span>
                    {message.success !== undefined && (
                      message.success ? (
                        <CheckCircle className="h-4 w-4 text-green-500" />
                      ) : (
                        <XCircle className="h-4 w-4 text-red-500" />
                      )
                    )}
                  </div>
                  
                  <p className="text-sm">{message.content}</p>
                  
                  {message.parsedIntent && renderIntentBadge(message.parsedIntent)}
                </div>
                
                {message.type === 'user' && (
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                    <User className="h-4 w-4 text-primary" />
                  </div>
                )}
              </div>
            ))}
            
            {isLoading && (
              <div className="flex gap-3 mb-4 justify-start">
                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div className="bg-background border rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm">Processing your request...</span>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="flex gap-2">
            <Input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your request here... (e.g., 'Send 100 USDC to Krypton', 'Start trading BTC/USD', 'Check my balance')"
              disabled={isLoading}
              className="flex-1"
            />
            <Button
              onClick={handleSendMessage}
              disabled={!inputValue.trim() || isLoading}
              size="icon"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>

          {/* Quick Actions */}
          {/* <div className="mt-4">
            <p className="text-sm text-muted-foreground mb-2">Quick examples:</p>
            <div className="flex flex-wrap gap-2">
              {[
                'Send 100 USDC to Krypton',
                'Check my balance',
                'Transfer 50 USDC to Alice',
                'Show my wallet'
              ].map((example) => (
                <Button
                  key={example}
                  variant="outline"
                  size="sm"
                  onClick={() => setInputValue(example)}
                  disabled={isLoading}
                >
                  {example}
                </Button>
              ))}
            </div>
          </div> */}
        </CardContent>
      </Card>
    </div>
  );
}
