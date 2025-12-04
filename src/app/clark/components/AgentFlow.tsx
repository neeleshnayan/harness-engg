"use client"

import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AgentFlowStep, AgentFlowGraph, AgentFlowEdge } from '../types'
import { ArrowRight, ArrowDown, CheckCircle2, Loader2, XCircle, GitBranch, GitMerge } from 'lucide-react'

interface AgentFlowProps {
  flow: AgentFlowGraph | AgentFlowStep[]
}

// Type guard to check if flow is a graph structure
function isFlowGraph(flow: AgentFlowGraph | AgentFlowStep[]): flow is AgentFlowGraph {
  return flow && typeof flow === 'object' && 'nodes' in flow && 'edges' in flow
}

export default function AgentFlow({ flow }: AgentFlowProps) {
  if (!flow) {
    console.log('[AgentFlow] No flow data provided')
    return null
  }

  console.log('[AgentFlow] Received flow:', flow)

  // Handle both old array format and new graph format
  let steps: AgentFlowStep[]
  let flowType: string = 'single'
  let edges: AgentFlowEdge[] = []

  if (isFlowGraph(flow)) {
    // New graph format - use steps array for display
    steps = flow.steps || flow.nodes.filter(n => n.type !== 'start' && n.type !== 'end')
    flowType = flow.flow_type || 'single'
    edges = flow.edges || []
    console.log('[AgentFlow] Graph format detected - flow_type:', flowType, 'steps:', steps.length)
  } else {
    // Old array format
    steps = flow
    console.log('[AgentFlow] Array format detected - steps:', steps.length)
  }

  if (!steps || steps.length === 0) {
    console.log('[AgentFlow] No steps to display')
    return null
  }

  console.log('[AgentFlow] Rendering card with', steps.length, 'steps')

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-400" />
      case 'pending':
        return <Loader2 className="h-4 w-4 text-yellow-400 animate-spin" />
      case 'error':
      case 'failed':
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

  const getFlowTypeIcon = () => {
    switch (flowType) {
      case 'parallel':
        return <GitBranch className="h-4 w-4 text-purple-400" />
      case 'sequential':
        return <GitMerge className="h-4 w-4 text-blue-400" />
      default:
        return null
    }
  }

  const getFlowTypeLabel = () => {
    switch (flowType) {
      case 'parallel':
        return 'Parallel Execution'
      case 'sequential':
        return 'Sequential Pipeline'
      default:
        return 'Agent Flow'
    }
  }

  // For parallel flows, group agents that have the same parent
  const renderParallelFlow = () => {
    // Find the orchestrator
    const orchestrator = steps.find(s => s.type === 'orchestrator')
    const otherAgents = steps.filter(s => s.type !== 'orchestrator')

    if (!orchestrator) {
      // Fallback to linear rendering
      return renderLinearFlow()
    }

    return (
      <div className="flex flex-col items-center gap-3">
        {/* Orchestrator */}
        <div
          className="flex items-center gap-2 px-3 py-2 rounded-lg border transition-all"
          style={{
            backgroundColor: `${getAgentColor(orchestrator)}20`,
            borderColor: `${getAgentColor(orchestrator)}60`,
          }}
        >
          {getStatusIcon(orchestrator.status)}
          <span
            className="text-sm font-medium"
            style={{ color: getAgentColor(orchestrator) }}
          >
            {orchestrator.name}
          </span>
        </div>

        {/* Arrow down */}
        {otherAgents.length > 0 && (
          <ArrowDown className="h-4 w-4 text-zinc-500" />
        )}

        {/* Parallel agents */}
        {otherAgents.length > 0 && (
          <div className="flex items-center gap-3 flex-wrap justify-center">
            {otherAgents.map((step, index) => (
              <React.Fragment key={step.id}>
                <div
                  className="flex items-center gap-2 px-3 py-2 rounded-lg border transition-all"
                  style={{
                    backgroundColor: `${getAgentColor(step)}20`,
                    borderColor: `${getAgentColor(step)}60`,
                  }}
                >
                  {getStatusIcon(step.status)}
                  <span
                    className="text-sm font-medium"
                    style={{ color: getAgentColor(step) }}
                  >
                    {step.name}
                  </span>
                </div>
                {index < otherAgents.length - 1 && (
                  <span className="text-zinc-500 text-xs">+</span>
                )}
              </React.Fragment>
            ))}
          </div>
        )}
      </div>
    )
  }

  // For sequential flows, render in order
  const renderSequentialFlow = () => {
    return (
      <div className="flex flex-col items-center gap-2">
        {steps.map((step, index) => (
          <React.Fragment key={step.id}>
            <div
              className="flex items-center gap-2 px-3 py-2 rounded-lg border transition-all"
              style={{
                backgroundColor: `${getAgentColor(step)}20`,
                borderColor: `${getAgentColor(step)}60`,
              }}
            >
              {getStatusIcon(step.status)}
              <span
                className="text-sm font-medium"
                style={{ color: getAgentColor(step) }}
              >
                {step.name}
              </span>
            </div>
            {index < steps.length - 1 && (
              <ArrowDown className="h-4 w-4 text-zinc-500" />
            )}
          </React.Fragment>
        ))}
      </div>
    )
  }

  // Linear flow (default)
  const renderLinearFlow = () => {
    return (
      <div className="flex items-center gap-2 flex-wrap">
        {steps.map((step, index) => (
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
            {index < steps.length - 1 && (
              <ArrowRight className="h-4 w-4 text-zinc-500 flex-shrink-0" />
            )}
          </React.Fragment>
        ))}
      </div>
    )
  }

  return (
    <Card className="w-full bg-zinc-800/30 border-zinc-700/50 backdrop-blur-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-base text-white flex items-center gap-2">
          {getFlowTypeIcon()}
          <span>{getFlowTypeLabel()}</span>
          {flowType !== 'single' && (
            <span className="text-xs text-zinc-400 font-normal ml-2">
              ({steps.length} agent{steps.length !== 1 ? 's' : ''})
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {flowType === 'parallel' && renderParallelFlow()}
        {flowType === 'sequential' && renderSequentialFlow()}
        {flowType === 'single' && renderLinearFlow()}
      </CardContent>
    </Card>
  )
}
