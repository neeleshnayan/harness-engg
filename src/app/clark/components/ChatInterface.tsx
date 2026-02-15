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
          : 'fixed bottom-0 left-0 right-0 z-40'
      }
    >
      <div
        className={embedded ? 'w-full px-3 py-3 border-0' : 'mx-auto max-w-6xl px-3 sm:px-6 lg:px-8 py-3 sm:py-4'}
        style={embedded ? { border: 'none', boxShadow: 'none' } : undefined}
      >
        <div className="flex flex-col gap-2">
          {queueLength > 0 && (
            <div className="mb-1.5 px-1" aria-live="polite">
              <button
                type="button"
                onClick={() => setQueueCollapsed(!queueCollapsed)}
                className="flex items-center gap-1 text-xs font-medium text-white/80 hover:text-white transition-colors"
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
                <ul className="scrollbar-minimal mt-1 text-xs text-white/70 list-none space-y-0.5 max-h-24 overflow-y-auto">
                  {queueQueries.map((query, i) => (
                    <li
                      key={i}
                      className="flex items-center gap-1.5 group py-0.5 pr-0.5 rounded hover:bg-white/5"
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
                            className="flex-1 min-w-0 px-1.5 py-0.5 rounded bg-white/10 border border-white/20 text-white placeholder:text-white/40 text-xs focus:outline-none focus:ring-1 focus:ring-white/30"
                            placeholder="Edit query…"
                            autoFocus
                          />
                          <button type="button" onClick={cancelEdit} className="text-white/50 hover:text-white p-0.5" aria-label="Cancel edit">×</button>
                        </>
                      ) : (
                        <>
                          <span className="flex-shrink-0 w-4 text-white/50">{i + 1}.</span>
                          <span className="flex-1 min-w-0 truncate">
                            {query.length > MAX_QUERY_PREVIEW ? `${query.slice(0, MAX_QUERY_PREVIEW)}…` : query}
                          </span>
                          <div className="flex items-center gap-0.5 flex-shrink-0 text-white/40 group-hover:text-white/60">
                            {onEditQueueItem && (
                              <button
                                type="button"
                                onClick={() => startEdit(i, query)}
                                className="p-1 rounded-md hover:bg-white/10 hover:text-white/90 transition-colors"
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
                                  className="p-1 rounded-md hover:bg-white/10 hover:text-white/90 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                                  aria-label="Move up"
                                  title="Move up"
                                >
                                  <ChevronUp className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => onMoveQueueItem(i, 'down')}
                                  disabled={i === queueQueries.length - 1}
                                  className="p-1 rounded-md hover:bg-white/10 hover:text-white/90 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
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
                                className="p-1 rounded-md hover:bg-red-500/20 hover:text-red-400 transition-colors"
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
                hover:bg-white/[0.08] active:bg-white/[0.06]
                transition-colors
                outline-none focus-visible:bg-white/[0.08]
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
                text-white
                placeholder:text-white/50
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
                bg-teal-500/25 hover:bg-teal-500/35 active:bg-teal-500/30
                transition-colors
                outline-none focus-visible:ring-2 focus-visible:ring-teal-400/40 focus-visible:ring-inset
                disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-white/[0.06]
              "
            >
              <ArrowUp className="h-5 w-5 sm:h-6 sm:w-6 text-white" strokeWidth={2.5} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
