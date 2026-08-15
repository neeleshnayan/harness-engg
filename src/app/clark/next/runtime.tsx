"use client"

/**
 * assistant-ui runtime over Clark's existing SSE — the external-store pattern.
 *
 * Our message state stays the source of truth (it carries provenance and the
 * live trace, which assistant-ui's own types do not), and `convertMessage`
 * derives what the Thread renders: each completed tool call becomes a
 * tool-call content part, so a registered tool UI renders the REAL result the
 * spine returned — deterministic data as components, never model-invented UI.
 *
 * This is the parallel surface (/clark/next). The main chat at /clark is
 * untouched until this reaches parity with citations, terminal and devtools.
 */

import React, { useCallback, useRef, useState } from 'react'
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from '@assistant-ui/react'
import { TraceStep, streamAgentQuery } from '@/lib/agents_stream'
import { stripReasoningFromMessage } from '../utils/createAssistantMessage'

export interface ClarkMsg {
  id: string
  role: 'user' | 'assistant'
  text: string
  steps: TraceStep[]
  /** Turn failed at transport level — rendered as an honest error, not silence. */
  failed?: boolean
}

const convertMessage = (m: ClarkMsg): ThreadMessageLike => {
  if (m.role === 'user') {
    return { role: 'user', content: [{ type: 'text', text: m.text }] }
  }
  type Part = Extract<ThreadMessageLike['content'][number], { type: 'tool-call' } | { type: 'text' }>
  // Tool calls first, in call order — the receipts above the prose, same
  // hierarchy as the citation gutter. Only finished calls carry results.
  const parts: Part[] = m.steps
    .filter((s) => s.name)
    .map((s) => ({
      type: 'tool-call' as const,
      toolCallId: s.id,
      toolName: s.name,
      args: (s.input ?? {}) as Extract<Part, { type: 'tool-call' }>['args'],
      result: s.result ?? (s.ok != null ? { preview: s.preview ?? '', ok: s.ok } : undefined),
    }))
  parts.push({ type: 'text', text: m.text })
  return { role: 'assistant', content: parts }
}

export function ClarkRuntimeProvider({ children }: { children: React.ReactNode }) {
  const [messages, setMessages] = useState<ClarkMsg[]>([])
  const [isRunning, setIsRunning] = useState(false)
  // Session identity mirrors the main chat's convention; per-tab, not stored.
  const sessionIdRef = useRef(`next_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`)

  const patchLast = useCallback((patch: Partial<ClarkMsg>) => {
    setMessages((prev) => {
      const next = [...prev]
      const last = next[next.length - 1]
      if (last?.role === 'assistant') next[next.length - 1] = { ...last, ...patch }
      return next
    })
  }, [])

  const onNew = useCallback(async (message: AppendMessage) => {
    console.info('[clark-next] onNew', JSON.stringify(message?.content ?? null))
    const text = (message.content ?? [])
      .filter((c): c is { type: 'text'; text: string } => c.type === 'text')
      .map((c) => c.text)
      .join('\n')
      .trim()
    if (!text) { console.warn('[clark-next] onNew: empty text, ignoring'); return }

    setMessages((prev) => [
      ...prev,
      { id: `u_${Date.now()}`, role: 'user', text, steps: [] },
      { id: `a_${Date.now()}`, role: 'assistant', text: '', steps: [] },
    ])
    setIsRunning(true)
    try {
      const payload = await streamAgentQuery(
        { query: text, session_id: sessionIdRef.current, username: 'krypton' },
        {
          onTrace: (steps) => patchLast({ steps: [...steps] }),
          onText: (t) => patchLast({ text: t }),
        },
      )
      const finalText = stripReasoningFromMessage(String(payload?.message ?? '')).trim()
      if (finalText) patchLast({ text: finalText })
    } catch (e) {
      patchLast({
        failed: true,
        text: `Could not complete the turn: ${e instanceof Error ? e.message : e}. ` +
              'The fund state is unknown from here — this is not an all-clear.',
      })
    } finally {
      setIsRunning(false)
    }
  }, [patchLast])

  const runtime = useExternalStoreRuntime<ClarkMsg>({
    messages,
    isRunning,
    onNew,
    convertMessage,
  })

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  )
}
