"use client"

import React, { useState } from 'react'
import type { ProvenanceMark } from '../types'

/**
 * What Clark read to write the answer under it.
 *
 * A model writing confidently about money looks identical whether it read the
 * book or guessed. That is the whole risk in this product, and it cannot be
 * fixed by asking the model to be careful — only by showing the operator, at a
 * glance, which sources the sentence rests on. On its first real outing it
 * caught exactly that: a question about NAV *and* the day-trade budget came
 * back citing one source, `compliance`, because Clark never called `fund_nav`
 * and wrote the NAV half from memory.
 *
 * This began as a fixed 92px column beside the prose. It read well but cost
 * every message a tenth of its width permanently, and the answer is what the
 * operator came for. Now it is one horizontal line above the text: same
 * information, no column, and the summary — count and total time — stays
 * visible while the per-tool breakdown folds away.
 *
 * Every mark comes from a real stream event: tool name, the arguments it was
 * actually called with, the time it actually took. Nothing here is inferred,
 * because a fabricated citation would be worse than none at all.
 */

/** `fund_compliance` -> `compliance`. The model's vocabulary, not the
 *  operator's, and the `fund_` prefix is the same on every row. */
const short = (tool: string) =>
  (tool || 'tool').replace(/^(fund|consult)_/, '').replace(/_/g, ' ')

/** `{limit: 5}` -> `limit 5`. Scalars only: a tool called with a nested object
 *  has no one-line form, and the row would understate the call. */
function args(input?: Record<string, unknown>): string | null {
  if (!input) return null
  const parts = Object.entries(input)
    .filter(([, v]) => v !== null && typeof v !== 'object')
    .map(([k, v]) => `${k} ${v}`)
  if (parts.length === 0) return null
  const joined = parts.join(', ')
  return joined.length > 40 ? joined.slice(0, 39) + '…' : joined
}

export default function CitationGutter({ marks }: { marks: ProvenanceMark[] }) {
  const [open, setOpen] = useState(false)
  if (!marks || marks.length === 0) return null

  const failed = marks.filter((m) => !m.ok).length
  const total = marks.reduce((a, m) => a + (m.ms ?? 0), 0)

  return (
    <div className="mb-2 font-mono text-[10px] leading-none text-[var(--kt-text-muted)]">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 rounded py-0.5 transition-colors hover:text-[var(--kt-text-dim)]"
        aria-expanded={open}
        title={open ? 'Hide sources' : 'Show sources'}
      >
        <span className="tracking-[0.14em] uppercase">
          {marks.length} {marks.length === 1 ? 'source' : 'sources'}
        </span>
        {total > 0 && (
          <>
            <span aria-hidden>·</span>
            <span className="tabular-nums">{(total / 1000).toFixed(2)}s</span>
          </>
        )}
        {failed > 0 && (
          <>
            <span aria-hidden>·</span>
            <span className="text-[var(--kt-down)]">{failed} failed</span>
          </>
        )}
        <span
          aria-hidden
          className={`transition-transform ${open ? 'rotate-90' : ''}`}
        >
          ›
        </span>
      </button>

      {open && (
        // Wraps rather than scrolls: four tools on one line, eight on two, and
        // the answer below never moves sideways.
        <ul className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 border-t border-[var(--kt-border)] pt-1.5">
          {marks.map((m) => {
            const a = args(m.input)
            return (
              <li
                key={m.id}
                className={`whitespace-nowrap ${m.ok ? '' : 'text-[var(--kt-down)]'}`}
              >
                <span className="text-[var(--kt-text-dim)]">{short(m.tool)}</span>
                {a && <span className="opacity-70"> ({a})</span>}
                {m.ms != null && (
                  <span className="tabular-nums opacity-70"> {(m.ms / 1000).toFixed(2)}s</span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
