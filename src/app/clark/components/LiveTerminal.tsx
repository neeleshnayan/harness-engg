"use client"

import React, { useEffect, useRef, useState } from 'react'
import { ChevronRight, Copy, Terminal } from 'lucide-react'
import type { LogLine } from '@/lib/agents_stream'

/**
 * The under-the-hood log, while it is happening.
 *
 * There was already a terminal here. It took the *finished* `agent_flow`,
 * animated it out one row every 120ms, and labelled itself "CLARK LIVE TASK
 * STREAM · STREAMING" — a re-enactment with invented pacing that could only
 * ever appear after the answer it was narrating. The timings on screen were
 * the animation's, not the fund's.
 *
 * These lines are appended as the SSE events land, so every timestamp is real,
 * the log is readable while the turn is still running, and a tool that hangs
 * shows up as a CALL with no RETURN under it — which is the single most useful
 * thing a log like this can tell you.
 *
 * Deliberately monospace and deliberately terse. This is the raw view; the
 * trace panel above it is the readable one. Anyone opening this wants the
 * actual call and the actual payload, not a friendlier paraphrase of them.
 */

const LEVEL_STYLE: Record<LogLine['level'], { color: string; tag: string }> = {
  OPEN:   { color: 'text-[var(--kt-text-muted)]', tag: 'open' },
  CALL:   { color: 'text-[var(--kt-agent)]',      tag: 'call' },
  ARGS:   { color: 'text-[var(--kt-text-muted)]', tag: 'args' },
  RETURN: { color: 'text-[var(--kt-accent)]',     tag: ' ok ' },
  FAIL:   { color: 'text-[var(--kt-down)]',       tag: 'fail' },
  THINK:  { color: 'text-[var(--kt-text-muted)]', tag: 'think' },
  WRITE:  { color: 'text-[var(--kt-text-dim)]',   tag: 'write' },
  DONE:   { color: 'text-[var(--kt-accent)]',     tag: 'done' },
}

const clock = (ms: number) => {
  const d = new Date(ms)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}.${String(d.getMilliseconds()).padStart(3, '0')}`
}

function Row({ line }: { line: LogLine }) {
  const [open, setOpen] = useState(false)
  const style = LEVEL_STYLE[line.level] ?? LEVEL_STYLE.OPEN
  return (
    <div>
      <button
        type="button"
        onClick={() => line.detail && setOpen((o) => !o)}
        disabled={!line.detail}
        className="flex w-full items-start gap-2 px-3 py-[3px] text-left hover:bg-[var(--kt-hover)] disabled:hover:bg-transparent"
      >
        <span className="flex-shrink-0 tabular-nums text-[var(--kt-text-muted)]">
          {clock(line.at)}
        </span>
        <span className={`flex-shrink-0 uppercase ${style.color}`}>{style.tag}</span>
        <span className={`min-w-0 flex-1 whitespace-pre-wrap break-words ${style.color}`}>
          {line.text}
        </span>
        {line.detail && (
          <ChevronRight
            className={`mt-[2px] h-3 w-3 flex-shrink-0 text-[var(--kt-text-muted)] transition-transform ${open ? 'rotate-90' : ''}`}
          />
        )}
      </button>
      {open && line.detail && (
        <pre className="mx-3 mb-1 overflow-x-auto whitespace-pre-wrap break-all rounded border border-[var(--kt-border)] bg-[var(--kt-inset)] px-2.5 py-1.5 text-[11px] leading-relaxed text-[var(--kt-text-muted)]">
          {line.detail}
        </pre>
      )}
    </div>
  )
}

export default function LiveTerminal({
  lines,
  running,
  defaultOpen = false,
  tall = false,
}: {
  lines: LogLine[]
  running: boolean
  /** Persisted by the caller, so the choice survives across turns. */
  defaultOpen?: boolean
  /** Devtools gives this a panel to fill; inline callers get a short window so
   *  the log never pushes the answer off screen. */
  tall?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  const [copied, setCopied] = useState(false)
  const bodyRef = useRef<HTMLDivElement>(null)
  const pinnedRef = useRef(true)

  // Follow the tail, but stop following the moment the operator scrolls up —
  // yanking them back to the bottom while they are reading a payload is the
  // fastest way to make a log useless.
  const onScroll = () => {
    const el = bodyRef.current
    if (!el) return
    pinnedRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24
  }
  useEffect(() => {
    if (!open || !pinnedRef.current) return
    const el = bodyRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [lines, open])

  if (lines.length === 0) return null

  const copy = () => {
    const text = lines
      .map((l) => `[${clock(l.at)}] ${l.level.padEnd(6)} ${l.text}${l.detail ? `\n${l.detail}` : ''}`)
      .join('\n')
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }

  return (
    <div className="mt-2 overflow-hidden rounded-xl border border-[var(--kt-border)] bg-[var(--kt-surface)] font-mono text-[11px]">
      <div className="flex items-center gap-2 px-3 py-1.5">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          aria-expanded={open}
        >
          <ChevronRight
            className={`h-3.5 w-3.5 flex-shrink-0 text-[var(--kt-text-muted)] transition-transform ${open ? 'rotate-90' : ''}`}
          />
          <Terminal className="h-3.5 w-3.5 flex-shrink-0 text-[var(--kt-text-muted)]" />
          <span className="uppercase tracking-[0.16em] text-[var(--kt-text-muted)]">
            Under the hood
          </span>
          <span className="text-[var(--kt-text-muted)]">
            {lines.length} {lines.length === 1 ? 'event' : 'events'}
          </span>
          {running && (
            <span className="flex items-center gap-1 text-[var(--kt-agent)]">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--kt-agent)]" />
              live
            </span>
          )}
        </button>
        {open && (
          <button
            type="button"
            onClick={copy}
            className="flex flex-shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-[var(--kt-text-muted)] transition-colors hover:bg-[var(--kt-hover)] hover:text-[var(--kt-text)]"
            title="Copy log"
          >
            {copied ? 'copied' : <Copy className="h-3 w-3" />}
          </button>
        )}
      </div>

      {open && (
        <div
          ref={bodyRef}
          onScroll={onScroll}
          className={`scrollbar-minimal overflow-y-auto border-t border-[var(--kt-border)] py-1 ${tall ? 'max-h-[60vh]' : 'max-h-[260px]'}`}
        >
          {lines.map((l) => (
            <Row key={l.seq} line={l} />
          ))}
        </div>
      )}
    </div>
  )
}
