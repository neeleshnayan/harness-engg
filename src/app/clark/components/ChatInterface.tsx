"use client"

import React, { useState } from 'react'
import { Pencil, ChevronUp, ChevronDown, Trash2, ArrowUp } from 'lucide-react'

interface ChatInputBarProps {
  inputValue: string
  setInputValue: (value: string) => void
  isLoading: boolean
  onSendMessage: () => void
  onKeyPress: (e: React.KeyboardEvent) => void
  onOpenPromptModal?: () => void
  queueLength?: number
  queueQueries?: string[]
  onRemoveQueueItem?: (index: number) => void
  onEditQueueItem?: (index: number, newQuery: string) => void
  onMoveQueueItem?: (index: number, direction: 'up' | 'down') => void
  /** When true, bar is not fixed to viewport (e.g. inside a dialog) */
  embedded?: boolean
  /** Width of the docked sidebar, in px, so the fixed bar centres over the
   *  content area rather than the whole viewport. The bar and the column
   *  above it are both 820px, but centring one on the window and the other
   *  on the area right of a 260px sidebar left them 130px out of line —
   *  visible as the composer sitting off to the left of the conversation. */
  offsetLeft?: number
}

const MAX_QUERY_PREVIEW = 52

export default function ChatInputBar({
  inputValue,
  setInputValue,
  isLoading,
  onSendMessage,
  onKeyPress,
  onOpenPromptModal,
  queueLength = 0,
  queueQueries = [],
  onRemoveQueueItem,
  onEditQueueItem,
  onMoveQueueItem,
  embedded = false,
  offsetLeft = 0,
}: ChatInputBarProps) {
  const [queueCollapsed, setQueueCollapsed] = useState(false)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editingValue, setEditingValue] = useState('')

  const startEdit = (index: number, query: string) => {
    setEditingIndex(index)
    setEditingValue(query)
  }
  const saveEdit = () => {
    if (editingIndex !== null && onEditQueueItem) {
      onEditQueueItem(editingIndex, editingValue)
      setEditingIndex(null)
      setEditingValue('')
    }
  }
  const cancelEdit = () => {
    setEditingIndex(null)
    setEditingValue('')
  }

  return (
    <div
      className={
        embedded
          ? 'relative z-40 w-full outline-none ring-0'
          : 'fixed bottom-0 left-0 right-0 z-40 bg-[var(--kt-bg)]/80 backdrop-blur-md'
      }
      // Padding rather than `left`, and deliberately not transitioned. This
      // offset decides where the composer *is*, not how it looks: a CSS
      // transition stalls whenever the tab is not compositing, and a stalled
      // decoration is invisible while a stalled layout leaves the composer
      // 260px out of line with the conversation above it. It snaps.
      style={embedded ? undefined : { paddingLeft: offsetLeft }}
    >
      {/* 820px, not max-w-6xl. The docked bar and the reading column above it
       *  are one object seen twice; at 1152px against an 820px column the
       *  composer visibly overhung the conversation on both sides. */}
      <div
        className={embedded ? 'w-full px-4 py-3 border-0' : 'mx-auto max-w-[820px] px-6 py-3 sm:py-4'}
        style={embedded ? { border: 'none', boxShadow: 'none' } : undefined}
      >
        <div className="flex flex-col gap-2">
          {queueLength > 0 && (
            <div className="mb-1.5 px-1" aria-live="polite">
              <button
                type="button"
                onClick={() => setQueueCollapsed(!queueCollapsed)}
                className="flex items-center gap-1 text-xs font-medium text-[var(--kt-text-dim)] hover:text-[var(--kt-text-strong)] transition-colors"
                aria-expanded={!queueCollapsed}
              >
                {queueCollapsed ? (
                  <ChevronDown className="h-3.5 w-3.5 flex-shrink-0 rotate-[-90deg]" aria-hidden />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5 flex-shrink-0" aria-hidden />
                )}
                {queueLength} Queued
              </button>
              {!queueCollapsed && (
                <ul className="scrollbar-minimal mt-1 text-xs text-[var(--kt-text-dim)] list-none space-y-0.5 max-h-24 overflow-y-auto">
                  {queueQueries.map((query, i) => (
                    <li
                      key={i}
                      className="flex items-center gap-1.5 group py-0.5 pr-0.5 rounded hover:bg-[var(--kt-inset)]"
                      title={query}
                    >
                      {editingIndex === i ? (
                        <>
                          <input
                            type="text"
                            value={editingValue}
                            onChange={(e) => setEditingValue(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') saveEdit()
                              if (e.key === 'Escape') cancelEdit()
                            }}
                            onBlur={saveEdit}
                            className="flex-1 min-w-0 px-1.5 py-0.5 rounded bg-[var(--kt-hover)] border border-[var(--kt-border)] text-[var(--kt-text-strong)] placeholder:text-[var(--kt-text-muted)] text-xs focus:outline-none focus:ring-1 focus:ring-white/30"
                            placeholder="Edit query…"
                            autoFocus
                          />
                          <button type="button" onClick={cancelEdit} className="text-[var(--kt-text-muted)] hover:text-[var(--kt-text-strong)] p-0.5" aria-label="Cancel edit">×</button>
                        </>
                      ) : (
                        <>
                          <span className="flex-shrink-0 w-4 text-[var(--kt-text-muted)]">{i + 1}.</span>
                          <span className="flex-1 min-w-0 truncate">
                            {query.length > MAX_QUERY_PREVIEW ? `${query.slice(0, MAX_QUERY_PREVIEW)}…` : query}
                          </span>
                          <div className="flex items-center gap-0.5 flex-shrink-0 text-[var(--kt-text-muted)] group-hover:text-[var(--kt-text-muted)]">
                            {onEditQueueItem && (
                              <button
                                type="button"
                                onClick={() => startEdit(i, query)}
                                className="p-1 rounded-md hover:bg-[var(--kt-hover)] hover:text-[var(--kt-text)] transition-colors"
                                aria-label="Edit query"
                                title="Edit"
                              >
                                <Pencil className="h-3.5 w-3.5" />
                              </button>
                            )}
                            {onMoveQueueItem && (
                              <>
                                <button
                                  type="button"
                                  onClick={() => onMoveQueueItem(i, 'up')}
                                  disabled={i === 0}
                                  className="p-1 rounded-md hover:bg-[var(--kt-hover)] hover:text-[var(--kt-text)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                                  aria-label="Move up"
                                  title="Move up"
                                >
                                  <ChevronUp className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => onMoveQueueItem(i, 'down')}
                                  disabled={i === queueQueries.length - 1}
                                  className="p-1 rounded-md hover:bg-[var(--kt-hover)] hover:text-[var(--kt-text)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                                  aria-label="Move down"
                                  title="Move down"
                                >
                                  <ChevronDown className="h-3.5 w-3.5" />
                                </button>
                              </>
                            )}
                            {onRemoveQueueItem && (
                              <button
                                type="button"
                                onClick={() => onRemoveQueueItem(i)}
                                className="p-1 rounded-md hover:bg-red-500/20 hover:text-[var(--kt-down)] transition-colors"
                                aria-label="Remove from queue"
                                title="Remove from queue"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            )}
                          </div>
                        </>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {/* Single clean bar: no border/outline/ring so no black box in mini-clark */}
          <div
            className="
              flex items-center
              rounded-2xl overflow-hidden
              bg-white/[0.07]
              shadow-none outline-none ring-0 border-0
            "
          >
            {/* Clark icon - no separate border, no focus ring bleed */}
            <button
              type="button"
              onClick={onOpenPromptModal}
              aria-label="Open prompt suggestions"
              className="
                h-10 w-10 sm:h-12 sm:w-12 flex-shrink-0
                rounded-full m-1
                bg-transparent
                flex items-center justify-center
                hover:bg-[var(--kt-hover)] active:bg-[var(--kt-hover)]
                transition-colors
                outline-none focus-visible:bg-[var(--kt-hover)]
              "
            >
              <img src="/clark process.svg" alt="" className="h-5 w-5 sm:h-6 sm:w-6 opacity-90" />
            </button>

            {/* Textarea - Enter sends, Shift+Enter newline */}
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={onKeyPress}
              placeholder="Ask Clark"
              disabled={false}
              aria-label="Message Clark"
              rows={1}
              className="
                flex-1 min-w-0
                min-h-[2.5rem] sm:min-h-[3rem]
                max-h-32 overflow-y-auto resize-none
                py-2.5 sm:py-3 px-3 sm:px-4
                bg-transparent
                border-0
                text-sm sm:text-base
                text-[var(--kt-text-strong)]
                placeholder:text-[var(--kt-text-muted)]
                focus:outline-none focus:ring-0 focus:ring-offset-0
                disabled:opacity-60 disabled:cursor-not-allowed
              "
            />

            {/* Send - single surface, larger icon */}
            <button
              type="button"
              onClick={() => onSendMessage()}
              disabled={!inputValue.trim()}
              aria-label="Send message"
              className="
                flex items-center justify-center
                h-10 w-10 sm:h-12 sm:w-12 flex-shrink-0
                rounded-r-2xl
                bg-[var(--kt-accent)]/25 hover:bg-[var(--kt-accent)]/35 active:bg-[var(--kt-accent)]/30
                transition-colors
                outline-none focus-visible:ring-2 focus-visible:ring-teal-400/40 focus-visible:ring-inset
                disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-[var(--kt-hover)]
              "
            >
              <ArrowUp className="h-5 w-5 sm:h-6 sm:w-6 text-[var(--kt-text-strong)]" strokeWidth={2.5} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
