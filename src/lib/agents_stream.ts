/**
 * Reads Clark's turn as it happens.
 *
 * The `/agents/query` endpoint returns one JSON blob after the whole turn
 * completes, which for a multi-tool fund question is twenty to sixty seconds of
 * a spinner. `/agents/stream` reports the same turn as it runs: which figures
 * Clark went and fetched, what came back, and the answer as the model writes it.
 *
 * The `complete` payload is byte-for-byte the same object `/agents/query`
 * returns, which is the point — every caller's existing post-processing
 * (interrupts, costs, backtest charts, message construction) keeps working
 * untouched, and the stream is purely additive on top.
 *
 * Deliberately built on `fetch` rather than the shared axios client: axios has
 * no streaming response body in the browser, and `EventSource` cannot POST.
 */

/** A tool Clark called during the turn. */
export interface TraceStep {
  id: string
  name: string
  /** undefined while still running */
  ok?: boolean
  preview?: string
  /** Arguments the tool was called with, once the model finished writing them. */
  input?: Record<string, unknown>
  startedAt: number
  endedAt?: number
}

/**
 * One line of the under-the-hood log, stamped when it actually happened.
 *
 * The existing terminal took a *finished* `agent_flow` and animated it out at
 * 120ms a row while displaying "STREAMING" — a re-enactment with invented
 * pacing, which is why it only ever appeared after the answer. These lines are
 * appended as the events arrive, so their timestamps are the real ones and the
 * log is complete at the moment the turn ends rather than starting then.
 */
export interface LogLine {
  seq: number
  at: number
  level: 'OPEN' | 'CALL' | 'ARGS' | 'RETURN' | 'FAIL' | 'THINK' | 'WRITE' | 'DONE'
  text: string
  /** Long payloads live here so a row stays one line until expanded. */
  detail?: string
}

export interface StreamHandlers {
  /** Fired whenever the trace changes; receives the whole list, newest last. */
  onTrace?: (steps: TraceStep[]) => void
  /** Cumulative answer text so far — not the increment. */
  onText?: (text: string) => void
  /** Cumulative reasoning text, when the model emits any. */
  onThinking?: (text: string) => void
  /** Fired as raw log lines are appended; receives the whole log. */
  onLog?: (lines: LogLine[]) => void
}

type ServerEvent =
  | { type: 'ack' }
  | { type: 'thinking'; text: string }
  | { type: 'tool_start'; id: string; name: string }
  | { type: 'tool_input'; id: string; name: string; input: Record<string, unknown> }
  | { type: 'tool_end'; id: string; name: string; ok: boolean; preview: string }
  | { type: 'delta'; text: string }
  | { type: 'complete'; payload: any }
  | { type: 'error'; message: string }

/** `fund_orders` + `{limit: 10}` -> `fund_orders(limit=10)`. */
function callSignature(name: string, input?: Record<string, unknown>): string {
  if (!input || Object.keys(input).length === 0) return `${name}()`
  const args = Object.entries(input)
    .map(([k, v]) => `${k}=${typeof v === 'string' ? JSON.stringify(v) : JSON.stringify(v)}`)
    .join(', ')
  return `${name}(${args.length > 120 ? args.slice(0, 119) + '…' : args})`
}

/**
 * Run a query, streaming progress, and resolve with the final payload.
 *
 * Rejects on transport failure or an `error` event so callers can fall back to
 * the non-streaming endpoint — a browser or proxy that mishandles SSE should
 * cost the operator a progress animation, not their answer.
 */
export async function streamAgentQuery(
  body: Record<string, unknown>,
  handlers: StreamHandlers = {},
  signal?: AbortSignal,
): Promise<any> {
  const res = await fetch('/api/v1/agents/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })

  if (!res.ok || !res.body) {
    throw new Error(`stream failed: ${res.status}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  // SSE frames are separated by a blank line and can be split across network
  // chunks at any byte, so a partial frame has to survive until the rest lands.
  let buffer = ''
  let text = ''
  let thinking = ''
  const steps: TraceStep[] = []
  const byId = new Map<string, TraceStep>()
  const log: LogLine[] = []
  let final: any = null
  let failure: string | null = null
  // Answer text is one log line that grows, not one per token — 181 rows of
  // three characters each is not a log, it is a denial of service on the eye.
  let writeLine: LogLine | null = null

  const push = (level: LogLine['level'], text: string, detail?: string) => {
    log.push({ seq: log.length, at: Date.now(), level, text, detail })
    handlers.onLog?.([...log])
  }

  const handle = (evt: ServerEvent) => {
    switch (evt.type) {
      case 'ack':
        push('OPEN', 'stream open · agent loop starting')
        break
      case 'thinking':
        thinking += evt.text
        handlers.onThinking?.(thinking)
        break
      case 'tool_start': {
        // The backend keys by toolUseId, but a model that calls the same tool
        // twice in one turn can reuse a name; keep the id as identity and let
        // the name be a label.
        if (byId.has(evt.id)) break
        const step: TraceStep = { id: evt.id, name: evt.name, startedAt: Date.now() }
        byId.set(evt.id, step)
        steps.push(step)
        handlers.onTrace?.([...steps])
        push('CALL', `→ ${evt.name}`)
        break
      }
      case 'tool_input': {
        const step = byId.get(evt.id)
        if (step) {
          step.input = evt.input
          handlers.onTrace?.([...steps])
        }
        push('ARGS', `  ${callSignature(evt.name, evt.input)}`,
             JSON.stringify(evt.input, null, 2))
        break
      }
      case 'tool_end': {
        const step = byId.get(evt.id)
        if (step) {
          step.ok = evt.ok
          step.preview = evt.preview
          step.endedAt = Date.now()
        } else {
          // A result with no matching start: still worth showing, because a
          // silently-dropped tool call is exactly what the trace exists to
          // make visible.
          steps.push({
            id: evt.id, name: evt.name, ok: evt.ok, preview: evt.preview,
            startedAt: Date.now(), endedAt: Date.now(),
          })
        }
        handlers.onTrace?.([...steps])
        const ms = step ? Date.now() - step.startedAt : null
        push(evt.ok ? 'RETURN' : 'FAIL',
             `← ${evt.name || evt.id}${ms != null ? ` · ${(ms / 1000).toFixed(2)}s` : ''}`,
             evt.preview)
        break
      }
      case 'delta':
        text += evt.text
        handlers.onText?.(text)
        if (!writeLine) {
          writeLine = { seq: log.length, at: Date.now(), level: 'WRITE', text: 'writing answer' }
          log.push(writeLine)
        }
        writeLine.text = `writing answer · ${text.length} chars`
        handlers.onLog?.([...log])
        break
      case 'complete':
        final = evt.payload
        push('DONE', 'turn complete')
        break
      case 'error':
        failure = evt.message
        push('FAIL', `stream error: ${evt.message}`)
        break
    }
  }

  const drain = (chunk: string) => {
    buffer += chunk
    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      for (const line of frame.split('\n')) {
        if (!line.startsWith('data:')) continue
        const raw = line.slice(5).trim()
        if (!raw) continue
        try {
          handle(JSON.parse(raw) as ServerEvent)
        } catch {
          // A single malformed frame must not abort a turn that is otherwise
          // producing a good answer.
        }
      }
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    drain(decoder.decode(value, { stream: true }))
  }
  drain(decoder.decode())

  if (failure) throw new Error(failure)
  if (!final) throw new Error('stream ended without a result')
  return final
}
