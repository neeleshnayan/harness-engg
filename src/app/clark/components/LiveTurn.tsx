"use client"

import React, { useEffect, useRef, useState } from 'react'
import { Check, ChevronRight, X } from 'lucide-react'
import type { TraceStep } from '@/lib/agents_stream'
import { markdownToHtml } from '../utils/markdown'
import CitationGutter from './CitationGutter'

/**
 * What Clark is doing, while it does it.
 *
 * The old loading state was the word "Thinking…" next to a pulsing logo for
 * however long the turn took — twenty seconds for a simple NAV question, over
 * a minute for anything that touches several parts of the book. It said
 * nothing about whether Clark had reached the spine at all, which is the one
 * thing worth knowing: a confident paragraph assembled from no lookups reads
 * exactly like a confident paragraph assembled from six.
 *
 * So the trace is the point, not the typing. Each row is a real call to the
 * fund spine — `fund_compliance`, `fund_risk` — and it fills in as the result
 * lands. An operator can tell, before a word of prose arrives, whether the
 * answer they are about to read is grounded.
 *
 * Rows are collapsed to a line each and previews sit behind a disclosure.
 * A trace that dumps the whole position book on screen is a trace nobody
 * reads, which costs more than it gives.
 */

/** `fund_compliance` -> `Compliance`. The model sees tool names; the operator
 *  should not have to. */
function label(name: string): string {
  if (!name) return 'Tool'
  return name
    .replace(/^(fund|consult)_/, '')
    .replace(/_/g, ' ')
    .replace(/^./, (c) => c.toUpperCase())
}

function Elapsed({ step }: { step: TraceStep }) {
  const [, force] = useState(0)
  // Running steps need a ticking clock; finished ones are static, so the
  // interval is only armed while something is actually in flight.
  useEffect(() => {
    if (step.endedAt) return
    const t = setInterval(() => force((n) => n + 1), 200)
    return () => clearInterval(t)
  }, [step.endedAt])
  const ms = (step.endedAt ?? Date.now()) - step.startedAt
  if (ms < 400) return null
  return (
    <span className="font-mono text-[10px] tabular-nums text-[var(--kt-text-muted)]">
      {(ms / 1000).toFixed(1)}s
    </span>
  )
}

function TraceRow({ step }: { step: TraceStep }) {
  const [open, setOpen] = useState(false)
  const running = step.endedAt == null
  const failed = step.ok === false

  return (
    <div className="border-b border-[var(--kt-border)] last:border-b-0">
      <button
        type="button"
        onClick={() => step.preview && setOpen((o) => !o)}
        className="flex w-full items-center gap-2.5 px-3 py-2 text-left disabled:cursor-default"
        disabled={!step.preview}
      >
        <span className="flex h-4 w-4 flex-shrink-0 items-center justify-center">
          {running ? (
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--kt-agent)]" />
          ) : failed ? (
            <X className="h-3.5 w-3.5 text-[var(--kt-down)]" />
          ) : (
            <Check className="h-3.5 w-3.5 text-[var(--kt-accent)]" />
          )}
        </span>
        <span className="flex-1 truncate text-[13px] text-[var(--kt-text-dim)]">
          {label(step.name)}
        </span>
        <Elapsed step={step} />
        {step.preview && (
          <ChevronRight
            className={`h-3.5 w-3.5 flex-shrink-0 text-[var(--kt-text-muted)] transition-transform ${open ? 'rotate-90' : ''}`}
          />
        )}
      </button>
      {open && step.preview && (
        <pre className="overflow-x-auto whitespace-pre-wrap break-all border-t border-[var(--kt-border)] bg-[var(--kt-inset)] px-3 py-2 font-mono text-[11px] leading-relaxed text-[var(--kt-text-muted)]">
          {step.preview}
        </pre>
      )}
    </div>
  )
}

export default function LiveTurn({
  steps,
  text,
}: {
  steps: TraceStep[]
  text: string
}) {
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, [text, steps.length])

  const anyRunning = steps.some((s) => s.endedAt == null)
  const nothingYet = steps.length === 0 && !text

  // Only finished steps become marks — the same rule the committed message
  // uses, so the gutter reads identically before and after the handover.
  const marks = steps
    .filter((s) => s.endedAt != null)
    .map((s) => ({
      id: s.id,
      tool: s.name,
      input: s.input,
      ok: s.ok !== false,
      ms: s.endedAt != null ? s.endedAt - s.startedAt : undefined,
    }))

  return (
    <div className="mb-6">
      {steps.length > 0 && (
        <div className="mb-3 overflow-hidden rounded-xl border border-[var(--kt-border)] bg-[var(--kt-surface)]">
          <div className="flex items-center gap-2 border-b border-[var(--kt-border)] px-3 py-1.5">
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--kt-text-muted)]">
              {anyRunning ? 'Reading the book' : `Read ${steps.length} source${steps.length === 1 ? '' : 's'}`}
            </span>
          </div>
          {steps.map((s) => (
            <TraceRow key={s.id} step={s} />
          ))}
        </div>
      )}

      {nothingYet && (
        <p className="text-sm text-[var(--kt-text-muted)]">
          Working<span className="animate-pulse">…</span>
        </p>
      )}

      {text && (
        // Same citation line, same rule, same renderer as a committed reply,
        // so nothing shifts at the moment the turn commits and the real
        // message replaces this.
        // Rendering markdown mid-stream means the occasional half-written `**`
        // shows as literal asterisks for a frame, which is far cheaper than
        // showing raw markup for the whole answer and snapping at the end.
        <div>
          <CitationGutter marks={marks} />
          <div className="min-w-0 border-l-2 border-[var(--kt-border)] pl-4 text-sm leading-relaxed text-[var(--kt-text)]">
            <div
              className="clark-prose max-w-none"
              dangerouslySetInnerHTML={{ __html: markdownToHtml(text) }}
            />
            <span className="mt-1 inline-block h-3.5 w-[2px] animate-pulse bg-[var(--kt-text-muted)]" />
          </div>
        </div>
      )}
      <div ref={endRef} />
    </div>
  )
}
