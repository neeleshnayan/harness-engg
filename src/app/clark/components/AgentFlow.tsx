"use client"

import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AgentFlowStep } from '../types'
import { ArrowRight, CheckCircle2, Loader2, XCircle } from 'lucide-react'

interface AgentFlowProps {
  flow: AgentFlowStep[]
}

export default function AgentFlow({ flow }: AgentFlowProps) {
  if (!flow || flow.length === 0) return null

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-400" />
      case 'pending':
        return <Loader2 className="h-4 w-4 text-yellow-400 animate-spin" />
      case 'error':
        return <XCircle className="h-4 w-4 text-red-400" />
      default:
        return <CheckCircle2 className="h-4 w-4 text-gray-400" />
    }
  }

  const getAgentColor = (step: AgentFlowStep) => {
    if (step.color) return step.color
    if (step.type === 'orchestrator') return '#4A90E2'
    return '#95A5A6'
  }

  return (
    <Card className="w-full bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-base text-white flex items-center gap-2">
          <span>Agent Execution Flow</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 flex-wrap">
          {flow.map((step, index) => (
            <React.Fragment key={step.id}>
              <div
                className="flex items-center gap-2 px-3 py-2 rounded-lg border transition-all"
                style={{
                  backgroundColor: `${getAgentColor(step)}20`,
                  borderColor: `${getAgentColor(step)}60`,
                }}
              >
                <div className="flex items-center gap-2">
                  {getStatusIcon(step.status)}
                  <span
                    className="text-sm font-medium"
                    style={{ color: getAgentColor(step) }}
                  >
                    {step.name}
                  </span>
                </div>
              </div>
              {index < flow.length - 1 && (
                <ArrowRight className="h-4 w-4 text-zinc-500 flex-shrink-0" />
              )}
            </React.Fragment>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

