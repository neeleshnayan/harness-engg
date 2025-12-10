"use client"

import React, { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AgentFlowStep, AgentFlowGraph, AgentFlowEdge } from '../types'
import { ArrowRight, ArrowDown, CheckCircle2, Loader2, XCircle, GitBranch, GitMerge, ChevronDown, ChevronUp, Code, MessageSquare } from 'lucide-react'

interface AgentFlowProps {
  flow: AgentFlowGraph | AgentFlowStep[]
}

// Type guard to check if flow is a graph structure
function isFlowGraph(flow: AgentFlowGraph | AgentFlowStep[]): flow is AgentFlowGraph {
  return flow && typeof flow === 'object' && 'nodes' in flow && 'edges' in flow
}

export default function AgentFlow({ flow }: AgentFlowProps) {
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set())
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

  const toggleAgentExpansion = (agentId: string) => {
    setExpandedAgents(prev => {
      const newSet = new Set(prev)
      if (newSet.has(agentId)) {
        newSet.delete(agentId)
      } else {
        newSet.add(agentId)
      }
      return newSet
    })
  }

  const renderAgentNode = (step: AgentFlowStep, showExpandButton: boolean = true) => {
    const isExpanded = expandedAgents.has(step.id)
    const hasInputOutput = step.input || step.output
    const canExpand = showExpandButton && hasInputOutput

    return (
      <div className="flex flex-col gap-2">
        <div
          className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-all ${canExpand ? 'cursor-pointer hover:opacity-80' : ''}`}
          onClick={canExpand ? () => toggleAgentExpansion(step.id) : undefined}
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
          {canExpand && (
            isExpanded ? (
              <ChevronUp className="h-4 w-4 text-zinc-400 ml-auto" />
            ) : (
              <ChevronDown className="h-4 w-4 text-zinc-400 ml-auto" />
            )
          )}
        </div>
        
        {/* Expanded input/output details */}
        {isExpanded && hasInputOutput && (
          <div className="ml-4 space-y-2 border-l-2 border-zinc-700 pl-4">
            {step.input && (
              <div className="bg-zinc-900/50 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Code className="h-3 w-3 text-blue-400" />
                  <span className="text-xs font-semibold text-blue-400 uppercase">Input</span>
                </div>
                <p className="text-xs text-zinc-300 whitespace-pre-wrap break-words">{step.input}</p>
              </div>
            )}
            {step.output && (
              <div className="bg-zinc-900/50 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <MessageSquare className="h-3 w-3 text-green-400" />
                  <span className="text-xs font-semibold text-green-400 uppercase">Output</span>
                  {step.output.success ? (
                    <CheckCircle2 className="h-3 w-3 text-green-400 ml-auto" />
                  ) : (
                    <XCircle className="h-3 w-3 text-red-400 ml-auto" />
                  )}
                </div>
                <div className="space-y-1">
                  {step.output.message && (
                    <p className="text-xs text-zinc-300 whitespace-pre-wrap break-words">{step.output.message}</p>
                  )}
                  {step.output.data_keys && step.output.data_keys.length > 0 && (
                    <div className="mt-2">
                      <span className="text-xs text-zinc-500">Data keys: </span>
                      <span className="text-xs text-zinc-400">{step.output.data_keys.join(', ')}</span>
                    </div>
                  )}
                  {step.output.has_data && (
                    <span className="inline-block text-xs text-green-400 mt-1">✓ Has data</span>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

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
        {renderAgentNode(orchestrator, false)}

        {/* Arrow down */}
        {otherAgents.length > 0 && (
          <ArrowDown className="h-4 w-4 text-zinc-500" />
        )}

        {/* Parallel agents */}
        {otherAgents.length > 0 && (
          <div className="flex items-start gap-3 flex-wrap justify-center">
            {otherAgents.map((step, index) => (
              <React.Fragment key={step.id}>
                <div className="flex flex-col items-center">
                  {renderAgentNode(step, true)}
                </div>
                {index < otherAgents.length - 1 && (
                  <span className="text-zinc-500 text-xs self-center">+</span>

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
            {renderAgentNode(step, true)}
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
      <div className="flex flex-col gap-2">
        {steps.map((step, index) => (
          <React.Fragment key={step.id}>
            <div className="flex items-start gap-2">
              {renderAgentNode(step, true)}
              {index < steps.length - 1 && (
                <ArrowRight className="h-4 w-4 text-zinc-500 flex-shrink-0 mt-3" />
              )}
            </div>
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
