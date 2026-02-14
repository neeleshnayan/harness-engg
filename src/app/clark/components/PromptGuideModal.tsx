"use client"

import React from 'react'
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

const cardGradient =
  'linear-gradient(180deg, rgba(255, 255, 255, 0.36) 0%, rgba(161, 207, 211, 0.06) 100%)'
const promptGradient =
  'linear-gradient(180deg, rgba(255, 255, 255, 0.24) 0%, rgba(161, 207, 211, 0.06) 100%)'

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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="
          w-full max-w-md sm:max-w-2xl
          bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80
          backdrop-blur-xl
          rounded-2xl
          shadow-[0_20px_60px_rgba(0,0,0,0.6)]
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
      >
        {/* Mobile: drag handle (Apple-style sheet indicator) */}
        <div className="max-sm:flex max-sm:justify-center max-sm:flex-shrink-0 max-sm:pb-2">
          <div
            className="hidden max-sm:block w-10 h-1 rounded-full bg-white/25"
            aria-hidden
          />
        </div>
        <DialogTitle className="sr-only">Choose a prompt</DialogTitle>
        <DialogDescription className="sr-only">
          Browse categories and prompt suggestions for Clark.
        </DialogDescription>
        <div
          className="
            overflow-y-auto overflow-x-hidden
            max-h-[60dvh] sm:max-h-[70vh]
            px-1 sm:px-2
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
                    className="w-full text-left p-4 rounded-xl backdrop-blur-sm transition-all duration-200 min-h-[2.75rem] active:scale-[0.98] sm:min-h-0"
                    style={{ background: cardGradient }}
                  >
                    <div className="flex items-center gap-3">
                      {category.icon.startsWith('/') ? (
                        <img src={category.icon} alt={category.title} className="h-5 w-5 flex-shrink-0" />
                      ) : (
                        <span className="text-lg flex-shrink-0">{category.icon}</span>
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="text-white font-medium truncate">{category.title}</div>
                        <div className="text-xs text-white/60 truncate">{category.description}</div>
                      </div>
                    </div>
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
                      className="flex items-center gap-2 text-white/80 hover:text-white text-sm mb-4 min-h-[2.75rem] -ml-1 pl-1 active:opacity-80 sm:min-h-0 sm:ml-0 sm:pl-0"
                    >
                      <span aria-hidden>←</span> Back to categories
                    </button>
                    <div className="text-white font-medium mb-2">{category.title}</div>
                    <div className="w-full space-y-2">
                      {category.prompts.map((prompt) => (
                        <button
                          key={prompt}
                          type="button"
                          onClick={() => handlePromptClick(prompt, category.id)}
                          disabled={isLoading}
                          className="w-full text-left p-3.5 rounded-xl backdrop-blur-sm transition-all duration-200 text-sm text-white/90 hover:text-white disabled:opacity-50 min-h-[2.75rem] active:scale-[0.98] sm:min-h-0 sm:p-3"
                          style={{ background: promptGradient }}
                        >
                          {prompt}
                        </button>
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
