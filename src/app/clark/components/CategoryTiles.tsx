"use client"

import React, { useState } from 'react'
import { Copy } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Category } from '../types'

/**
 * Tiles and prompt rows used to be painted with
 * `linear-gradient(180deg, rgba(255,255,255,.36), rgba(161,207,211,.06))` —
 * a 36% white wash fading into teal. That was designed against a light-ish
 * surface; on the studio's #0a0a0b page it renders as a milky grey blob with
 * a green tinge at the bottom, and thirty of them at once is the whole
 * landing screen.
 *
 * They are objects on a plane, so they are drawn the way every other object
 * in this product is drawn: one surface token, one border, no wash. The
 * hierarchy comes from the border lifting on hover, not from a gradient
 * shouting at rest.
 */
const tileBase =
  'rounded-xl border border-[var(--kt-border)] bg-[var(--kt-surface)] ' +
  'transition-colors duration-150 hover:border-[var(--kt-border-strong)] hover:bg-[var(--kt-hover)]'

function PromptRowWithCopy({
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
  return (
    <div className={`flex items-center gap-2 min-h-[56px] overflow-hidden group touch-manipulation ${tileBase}`}>
      <button
        type="button"
        onClick={onUse}
        disabled={isLoading}
        className="flex-1 w-full text-left px-4 py-3 rounded-xl text-[var(--kt-text-dim)] disabled:opacity-50 disabled:cursor-not-allowed min-h-[56px] flex items-center"
      >
        <span className="flex-1 text-sm leading-relaxed transition-colors group-hover:text-[var(--kt-text)]">
          {prompt}
        </span>
      </button>
      <button
        type="button"
        onClick={handleCopy}
        aria-label={copied ? 'Copied' : 'Copy prompt'}
        aria-live="polite"
        className="flex-shrink-0 p-2 rounded-lg text-[var(--kt-text-muted)] hover:text-[var(--kt-text)] transition-colors mr-1.5"
      >
        {copied ? (
          <span className="text-xs text-[var(--kt-accent)] font-medium">Copied</span>
        ) : (
          <Copy className="h-4 w-4" />
        )}
      </button>
    </div>
  )
}

interface CategoryTilesProps {
  categories: Category[]
  selectedCategory: string | null
  onCategorySelect: (categoryId: string) => void
  onPromptClick: (prompt: string, categoryId: string) => void
  isLoading: boolean
}

export default function CategoryTiles({
  categories,
  selectedCategory,
  onCategorySelect,
  onPromptClick,
  isLoading
}: CategoryTilesProps) {
  // Calculate number of rows needed for 2 columns layout
  const totalTiles = categories.length
  const tilesPerRow = 2
  const totalRows = Math.ceil(totalTiles / tilesPerRow)

  return (
    <div className="pb-1 mb-1">
      {/* Category Tiles */}
      {/* Mobile: center 4 tiles on first page; 5th appears on swipe */}
      <div className="block sm:hidden scrollbar-minimal overflow-x-auto pb-2 snap-x snap-mandatory overscroll-x-contain w-full">
        <div className="flex" style={{ width: `${Math.max(2, Math.ceil(totalRows / 2)) * 100}%` }}>
          {(() => {
            const pageCount = Math.max(2, Math.ceil(totalRows / 2));
            const columns = Array.from({ length: totalRows }).map((_, colIndex) => {
              const startIndex = colIndex * tilesPerRow
              const colTiles = categories.slice(startIndex, startIndex + tilesPerRow)
              return (
                <div key={`col-${colIndex}`} className="flex flex-col gap-3 min-w-0">
                  {colTiles.map((category) => (
                    <Card
                      key={category.id}
                      className="cursor-pointer bg-transparent border-none shadow-none p-0 w-full touch-manipulation"
                      onClick={() => onCategorySelect(category.id)}
                    >
                      <div className={`min-h-[80px] active:scale-[0.99] ${tileBase}`}>
                        <CardHeader className="pb-3 pt-3 px-3 h-full flex flex-col justify-center">
                          <CardTitle className="text-xs font-medium text-[var(--kt-text)] flex items-center gap-2 mb-1">
                            {category.icon.startsWith('/') ? (
                              <img src={category.icon} alt={category.title} className="h-4 w-4 flex-shrink-0 opacity-70" />
                            ) : (
                              <span className="text-base flex-shrink-0">{category.icon}</span>
                            )}
                            <span className="truncate">{category.title}</span>
                          </CardTitle>
                          <CardDescription className="text-xs text-[var(--kt-text-muted)] leading-tight line-clamp-2">
                            {category.description}
                          </CardDescription>
                        </CardHeader>
                      </div>
                    </Card>
                  ))}
                </div>
              )
            })

            const pages = [] as React.ReactNode[]
            for (let i = 0; i < columns.length; i += 2) {
              const second = columns[i + 1]
              pages.push(
                <div key={`page-${i / 2}`} className="snap-start px-4 flex-shrink-0" style={{ flexBasis: `${100 / pageCount}%`, minWidth: `${100 / pageCount}%` }}>
                  {/* Two-column grid: lone column on last page stays half-width (matches other tiles) */}
                  <div className="grid grid-cols-2 gap-3 w-full">
                    {columns[i]}
                    {second}
                  </div>
                </div>
              )
            }
            return pages
          })()}
        </div>
      </div>

      {/* Desktop grid.
       *
       * Was `grid-cols-3 md:grid-cols-4 lg:grid-cols-5` inside an 820px reading
       * column, which gave each tile ~145px and truncated every single title:
       * "Fund Operatio…", "Strategy & Ba…", "Technical Ana…". Three columns at
       * this width leaves ~225px of text per tile, which every title clears —
       * so nothing needs `truncate` any more, and a title that grows a word
       * later wraps instead of silently losing its ending. */}
      <div className="hidden w-full sm:grid sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
        {categories.map((category) => (
          <Card
            key={category.id}
            className="cursor-pointer bg-transparent border-none shadow-none p-0 touch-manipulation"
            onClick={() => onCategorySelect(category.id)}
          >
            <div className={`h-full active:scale-[0.99] ${tileBase}`}>
              <CardHeader className="flex h-full flex-col justify-start gap-1 px-3.5 py-3">
                <CardTitle className="flex items-center gap-2 text-[13px] font-medium text-[var(--kt-text)]">
                  {category.icon.startsWith('/') ? (
                    <img src={category.icon} alt="" aria-hidden className="h-4 w-4 flex-shrink-0 opacity-60" />
                  ) : (
                    <span className="text-base flex-shrink-0">{category.icon}</span>
                  )}
                  <span>{category.title}</span>
                </CardTitle>
                <CardDescription className="text-xs leading-snug text-[var(--kt-text-muted)]">
                  {category.description}
                </CardDescription>
              </CardHeader>
            </div>
          </Card>
        ))}
      </div>

      {/* Prompts Modal */}
      {selectedCategory && (
        <div
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 px-4 pb-28 backdrop-blur-sm sm:px-4 sm:pb-8 sm:pt-4"
          onClick={() => onCategorySelect('')}
        >
          <Card
            className="w-full max-w-md sm:max-w-2xl h-[80vh] sm:h-auto sm:max-h-[80vh] rounded-2xl border border-[var(--kt-border)] bg-[var(--kt-surface)] shadow-[0_20px_60px_rgba(0,0,0,0.5)]"
            onClick={(e) => e.stopPropagation()}
          >
            <CardHeader className="border-b border-[var(--kt-border)] p-4 sm:px-6 sm:py-5">
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <CardTitle className="text-base text-[var(--kt-text)] flex items-center gap-2">
                    {(() => {
                      const category = categories.find(c => c.id === selectedCategory);
                      const icon = category?.icon;
                      return icon?.startsWith('/') ? (
                        <img src={icon} alt={category?.title} className="h-5 w-5 flex-shrink-0 opacity-70" />
                      ) : (
                        <span className="text-xl flex-shrink-0">{icon}</span>
                      );
                    })()}
                    <span className="truncate">{categories.find(c => c.id === selectedCategory)?.title}</span>
                  </CardTitle>
                  <CardDescription className="text-[var(--kt-text-muted)] mt-1 text-xs sm:text-sm line-clamp-2">
                    {categories.find(c => c.id === selectedCategory)?.description}
                  </CardDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onCategorySelect('')}
                  className="text-[var(--kt-text-muted)] hover:text-[var(--kt-text)] hover:bg-[var(--kt-hover)] h-8 w-8 p-0 ml-2 flex-shrink-0 touch-manipulation"
                >
                  <img src="/cross.svg" alt="Close" className="h-5 w-5 opacity-70" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-4 p-4 sm:p-6 max-h-[calc(85vh-120px)] sm:max-h-[60vh] overflow-y-auto">
              <div className="space-y-3">
                {categories.find(c => c.id === selectedCategory)?.prompts.map((prompt, index) => (
                  <PromptRowWithCopy
                    key={index}
                    prompt={prompt}
                    isLoading={isLoading}
                    onUse={() => onPromptClick(prompt, selectedCategory as string)}
                  />
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
