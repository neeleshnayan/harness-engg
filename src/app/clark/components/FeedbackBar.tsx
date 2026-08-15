"use client"

import React, { useState } from 'react'
import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { ProvenanceMark } from '../types'

/**
 * Two quiet buttons under an answer — the front of Clark's learning loop.
 *
 * A vote is a signal, not a conversation: it posts the turn (query, answer,
 * which tools were actually read) to the feedback log, where mine_cases.py
 * turns repeated failures into staged e2e case candidates a human reviews.
 * Nothing learned deploys by itself; the vote's whole job is to make sure a
 * real mistake becomes a permanent test instead of a shrug.
 *
 * Provenance rides along deliberately: "confident answer, zero sources" is
 * the failure mode the citation gutter exists to expose, and a down-vote that
 * carries the empty source list tags itself.
 */

export function sendFeedback(body: {
  verdict: 'up' | 'down' | 'rephrased'
  query: string
  answer: string
  sources: { name: string; ok: boolean }[]
  session_id?: string
  note?: string
}) {
  // Fire-and-forget through the same proxy the chat uses. A failed vote must
  // never surface as an error — feedback is telemetry, not a feature the
  // operator is waiting on.
  return fetch('/api/v1/agents/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).catch(() => undefined)
}

export function marksToSources(marks?: ProvenanceMark[]) {
  return (marks ?? []).map((m) => ({ name: m.tool, ok: m.ok }))
}

export default function FeedbackBar({ query, answer, marks, sessionId }: {
  /** The user message this answer replied to. */
  query: string
  answer: string
  marks?: ProvenanceMark[]
  sessionId?: string
}) {
  const [voted, setVoted] = useState<'up' | 'down' | null>(null)

  const vote = (verdict: 'up' | 'down') => {
    if (voted) return
    setVoted(verdict)
    void sendFeedback({
      verdict,
      query,
      answer: answer.slice(0, 8000),
      sources: marksToSources(marks),
      session_id: sessionId,
    })
  }

  if (!query || !answer) return null

  return (
    <div className="mt-1.5 flex items-center gap-1">
      {voted ? (
        <span className="text-[10px] text-[var(--kt-text-muted)]">
          {voted === 'down'
            ? 'noted — repeated failures become test cases'
            : 'noted'}
        </span>
      ) : (
        <>
          {([['up', ThumbsUp], ['down', ThumbsDown]] as const).map(([v, Icon]) => (
            <button
              key={v}
              onClick={() => vote(v)}
              aria-label={v === 'up' ? 'Good answer' : 'Bad answer'}
              title={v === 'up' ? 'Good answer' : 'Bad answer — feeds the test suite'}
              className="rounded p-1 text-[var(--kt-text-muted)] transition-colors hover:bg-[var(--kt-hover)] hover:text-[var(--kt-text)]"
            >
              <Icon size={12} />
            </button>
          ))}
        </>
      )}
    </div>
  )
}
