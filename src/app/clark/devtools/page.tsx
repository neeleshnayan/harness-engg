"use client"

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import { ChatMessage, AgentFlowGraph, AgentFlowStep } from '../types'
import AgentFlow from '../components/AgentFlow'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'

export default function DevtoolsPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [selectedQueryIndex, setSelectedQueryIndex] = useState<number | null>(null)

  useEffect(() => {
    // Load messages from localStorage
    try {
      const storedMessages = localStorage.getItem('clark_messages')
      if (storedMessages) {
        const parsedMessages = JSON.parse(storedMessages).map((msg: any) => ({
          ...msg,
          timestamp: new Date(msg.timestamp) // Convert string back to Date
        })) as ChatMessage[]
        setMessages(parsedMessages)
      }
    } catch (error) {
      console.error('Error loading messages:', error)
    }
  }, [])

  // Get all queries (user messages) with their corresponding agent flows
  const queriesWithFlows = messages
    .map((message, index) => {
      if (message.type === 'user') {
        // Find the next assistant message that has an agent flow
        const nextAssistant = messages.slice(index + 1).find(m => 
          m.type === 'assistant' && m.agentFlow
        )
        return {
          query: message.content,
          timestamp: message.timestamp,
          messageIndex: index,
          agentFlow: nextAssistant?.agentFlow
        }
      }
      return null
    })
    .filter((item): item is NonNullable<typeof item> => item !== null && item.agentFlow !== undefined)

  const hasFlowContent = (flow: AgentFlowGraph | AgentFlowStep[] | undefined) => {
    if (!flow) return false
    if (Array.isArray(flow)) {
      return flow.length > 0
    }
    return (flow as AgentFlowGraph)?.steps?.length > 0 || 
           (flow as AgentFlowGraph)?.nodes?.length > 0
  }

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 overflow-x-hidden">
      {/* Navbar */}
      <header className="fixed top-0 left-0 right-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-2 min-h-[4rem]">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.push('/clark')}
                className="flex items-center gap-2 text-white hover:text-zinc-300 transition-colors"
              >
                <ArrowLeft className="h-4 w-4" />
                <span>Back to Clark</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Spacer for fixed navbar height */}
      <div className="h-24" />

      {/* Main Content */}
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-white mb-2">Agent Flow Devtools</h1>
          <p className="text-zinc-400">
            View agent flow graphs for all queries sent by the user
          </p>
        </div>

        {queriesWithFlows.length === 0 ? (
          <Card className="bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
            <CardContent className="p-8 text-center">
              <p className="text-zinc-400">
                No agent flow data available. Send some queries in the main Clark interface to see flow graphs here.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-6">
            {queriesWithFlows.map((queryData, index) => {
              const isExpanded = selectedQueryIndex === index
              return (
                <Card 
                  key={index} 
                  className="bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm"
                >
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <CardTitle className="text-lg text-white mb-2">
                          Query #{queriesWithFlows.length - index}
                        </CardTitle>
                        <CardDescription className="text-zinc-300 mb-2">
                          {queryData.query}
                        </CardDescription>
                        <div className="text-xs text-zinc-500">
                          {queryData.timestamp.toLocaleString()}
                        </div>
                      </div>
                      <button
                        onClick={() => setSelectedQueryIndex(isExpanded ? null : index)}
                        className="ml-4 px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg transition-colors text-sm"
                      >
                        {isExpanded ? 'Hide Flow' : 'Show Flow'}
                      </button>
                    </div>
                  </CardHeader>
                  {isExpanded && queryData.agentFlow && hasFlowContent(queryData.agentFlow) && (
                    <CardContent>
                      <AgentFlow flow={queryData.agentFlow} />
                    </CardContent>
                  )}
                </Card>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
