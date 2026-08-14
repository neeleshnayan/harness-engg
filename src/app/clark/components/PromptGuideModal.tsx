"use client"

import React, { useState } from 'react'
import { Copy, ChevronRight } from 'lucide-react'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Category } from '../types'

export interface PromptGuideModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  categories: Category[]
  selectedCategory: string | null
  onSelectCategory: (categoryId: string | null) => void
  onPromptClick: (prompt: string, categoryId: string) => void
  isLoading: boolean
}

/** Same wash, same problem as CategoryTiles — see the note there. One surface,
 *  one border; hover lifts the border rather than the fill. */
const rowBase =
  'rounded-xl border border-[var(--kt-border)] bg-[var(--kt-surface)] ' +
  'transition-colors duration-150 hover:border-[var(--kt-border-strong)] hover:bg-[var(--kt-hover)]'

function PromptRow({
  prompt,
  isLoading,
  onUse,
}: {
  prompt: string
  isLoading: boolean
  onUse: () => void
}) {
  const [copied, setCopied] = useState(false)
  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard.writeText(prompt).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  const handleUse = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    onUse()
  }
  return (
    <div className={`group relative flex items-center gap-2 min-h-[2.75rem] sm:min-h-0 p-0 overflow-hidden ${rowBase}`}>
      <button
        type="button"
        onClick={handleUse}
        disabled={isLoading}
        className="flex-1 text-left p-3.5 rounded-xl text-sm text-[var(--kt-text-dim)] transition-colors group-hover:text-[var(--kt-text)] disabled:opacity-50 sm:p-3"
      >
        {prompt}
      </button>
      <button
        type="button"
        onClick={handleCopy}
        aria-label={copied ? 'Copied' : 'Copy prompt'}
        aria-live="polite"
        className="flex-shrink-0 p-2 rounded-lg text-[var(--kt-text-muted)] hover:text-[var(--kt-text-strong)] hover:bg-[var(--kt-hover)] transition-colors mr-1"
      >
        {copied ? (
          <span className="text-xs text-[var(--kt-accent)] font-medium">Copied!</span>
        ) : (
          <Copy className="h-4 w-4" />
        )}
      </button>
    </div>
  )
}

export default function PromptGuideModal({
  open,
  onOpenChange,
  categories,
  selectedCategory,
  onSelectCategory,
  onPromptClick,
  isLoading,
}: PromptGuideModalProps) {
  const handlePromptClick = (prompt: string, categoryId: string) => {
    onPromptClick(prompt, categoryId)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} modal={false}>
      <DialogContent
        className="
          w-full max-w-md sm:max-w-2xl
          bg-[var(--kt-surface)]
          backdrop-blur-xl
          rounded-2xl
          shadow-2xl
          border-none
          flex flex-col
          overflow-hidden
          p-0
          sm:p-6 sm:rounded-2xl
          max-sm:fixed max-sm:inset-x-0 max-sm:bottom-0 max-sm:top-auto max-sm:translate-x-0 max-sm:translate-y-0
          max-sm:rounded-t-3xl max-sm:rounded-b-none
          max-sm:max-h-[92dvh] max-sm:w-full max-sm:max-w-none
          max-sm:px-4 max-sm:pt-8 max-sm:pb-5
          max-sm:[padding-top:max(2rem,env(safe-area-inset-top,2rem))]
          max-sm:[padding-bottom:max(1.25rem,env(safe-area-inset-bottom,1.25rem))]
          max-sm:data-[state=open]:slide-in-from-bottom
          max-sm:data-[state=closed]:slide-out-to-bottom
          sm:pt-10 sm:pr-14
        "
        aria-describedby={undefined}
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        {/* Mobile: drag handle (Apple-style sheet indicator) */}
        <div className="max-sm:flex max-sm:justify-center max-sm:flex-shrink-0 max-sm:pb-2">
          <div
            className="hidden max-sm:block w-10 h-1 rounded-full bg-white/25"
            aria-hidden
          />
        </div>
        {/* Header: "Prompt Guide" top-left (X is top-right via DialogContent) */}
        <div className="flex items-center flex-shrink-0 pt-1 pb-3 sm:pb-4 px-4 sm:px-6">
          <h2 className="text-lg font-semibold text-[var(--kt-text-strong)]">Prompt Guide</h2>
        </div>
        <DialogTitle className="sr-only">Choose a prompt</DialogTitle>
        <DialogDescription className="sr-only">
          Browse categories and prompt suggestions for Clark.
        </DialogDescription>
        <div
          className="
            overflow-y-auto overflow-x-hidden
            max-h-[60dvh] sm:max-h-[70vh]
            px-4 sm:px-6
            min-h-0
            flex-1
          "
          style={{ WebkitOverflowScrolling: 'touch' } as React.CSSProperties}
        >
          {!selectedCategory ? (
            <div className="w-full flex flex-col items-center pb-6 sm:pb-0">
              <div className="w-full max-w-md space-y-3">
                {categories.map((category) => (
                  <button
                    key={category.id}
                    type="button"
                    onClick={() => onSelectCategory(category.id)}
                    className={`w-full text-left p-4 min-h-[2.75rem] active:scale-[0.99] sm:min-h-0 flex items-center gap-3 ${rowBase}`}
                  >
                    {category.icon.startsWith('/') ? (
                      <img src={category.icon} alt="" aria-hidden className="h-4 w-4 flex-shrink-0 opacity-60" />
                    ) : (
                      <span className="text-base flex-shrink-0">{category.icon}</span>
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-[var(--kt-text)]">{category.title}</div>
                      <div className="truncate text-xs text-[var(--kt-text-muted)]">{category.description}</div>
                    </div>
                    <ChevronRight className="h-5 w-5 flex-shrink-0 text-[var(--kt-text-dim)]" aria-hidden />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            (() => {
              const category = categories.find((c) => c.id === selectedCategory)
              if (!category) return null
              return (
                <div className="w-full flex flex-col items-center pb-6 sm:pb-0">
                  <div className="w-full max-w-md">
                    <button
                      type="button"
                      onClick={() => onSelectCategory(null)}
                      className="flex items-center gap-2 text-[var(--kt-text-dim)] hover:text-[var(--kt-text-strong)] text-sm mb-4 min-h-[2.75rem] -ml-1 pl-1 active:opacity-80 sm:min-h-0 sm:ml-0 sm:pl-0"
                    >
                      <span aria-hidden>←</span> Back to categories
                    </button>
                    <div className="text-[var(--kt-text-strong)] font-medium mb-2">{category.title}</div>
                    <div className="w-full space-y-2">
                      {category.prompts.map((prompt) => (
                        <PromptRow
                          key={prompt}
                          prompt={prompt}
                          isLoading={isLoading}
                          onUse={() => handlePromptClick(prompt, category.id)}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              )
            })()
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
