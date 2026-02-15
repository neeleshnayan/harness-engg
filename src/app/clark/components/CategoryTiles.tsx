"use client"

import React, { useState } from 'react'
import { Copy } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Category } from '../types'

const promptRowGradient =
  'linear-gradient(180deg, rgba(255, 255, 255, 0.36) 0%, rgba(161, 207, 211, 0.06) 100%)'

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
    <div
      className="flex items-center gap-2 rounded-xl min-h-[60px] overflow-hidden group touch-manipulation"
      style={{ background: promptRowGradient }}
    >
      <button
        type="button"
        onClick={onUse}
        disabled={isLoading}
        className="flex-1 w-full text-left p-4 rounded-xl transition-all duration-200 text-white disabled:opacity-50 disabled:cursor-not-allowed min-h-[60px] flex items-center"
      >
        <div className="flex items-start gap-3 w-full">
          <span className="text-white/80 font-bold text-sm mt-1 flex-shrink-0">•</span>
          <span className="flex-1 text-sm sm:text-base group-hover:text-white transition-colors leading-relaxed">
            {prompt}
          </span>
        </div>
      </button>
      <button
        type="button"
        onClick={handleCopy}
        aria-label={copied ? 'Copied' : 'Copy prompt'}
        aria-live="polite"
        className="flex-shrink-0 p-2 rounded-lg text-white/50 hover:text-white hover:bg-white/10 transition-colors mr-1"
      >
        {copied ? (
          <span className="text-xs text-teal-300 font-medium">Copied!</span>
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
      <div className="block sm:hidden scrollbar-minimal overflow-x-auto pb-2 -mx-2 snap-x snap-mandatory">
        <div className="flex w-[100vw]">
          {(() => {
            const columns = Array.from({ length: totalRows }).map((_, colIndex) => {
              const startIndex = colIndex * tilesPerRow
              const colTiles = categories.slice(startIndex, startIndex + tilesPerRow)
              return (
                <div key={`col-${colIndex}`} className="flex flex-col gap-3">
                  {colTiles.map((category) => (
                    <Card
                      key={category.id}
                      className="cursor-pointer bg-transparent border-none shadow-none p-0 w-[calc(50vw-1.5rem)] touch-manipulation"
                      onClick={() => onCategorySelect(category.id)}
                    >
                      <div
                        className="rounded-xl backdrop-blur-xl min-h-[80px] transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] hover:shadow-lg"
                        style={{
                          background:
                            'linear-gradient(180deg, rgba(255, 255, 255, 0.36) 0%, rgba(161, 207, 211, 0.06) 100%)',
                        }}
                      >
                        <CardHeader className="pb-3 pt-3 px-3 h-full flex flex-col justify-center">
                          <CardTitle className="text-xs text-white flex items-center gap-2 mb-1">
                            {category.icon.startsWith('/') ? (
                              <img src={category.icon} alt={category.title} className="h-4 w-4 flex-shrink-0" />
                            ) : (
                              <span className="text-base flex-shrink-0">{category.icon}</span>
                            )}
                            <span className="truncate">{category.title}</span>
                          </CardTitle>
                          <CardDescription className="text-xs text-white/60 leading-tight line-clamp-2">
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
              const hasSecondColumn = Boolean(columns[i + 1])
              pages.push(
                <div key={`page-${i/2}`} className="min-w-full snap-start px-2">
                  <div className={`flex ${hasSecondColumn ? 'justify-center' : 'justify-start'} gap-3`}>
                    {columns[i]}
                    {columns[i + 1]}
                  </div>
                </div>
              )
            }
            return pages
          })()}
        </div>
      </div>
      
      {/* Desktop: Responsive grid */}
      <div className="hidden sm:grid grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 w-full max-w-6xl mx-auto px-0">
        {categories.map((category) => (
          <Card
            key={category.id}
            className="cursor-pointer bg-transparent border-none shadow-none p-0 touch-manipulation"
            onClick={() => onCategorySelect(category.id)}
          >
            <div
              className="rounded-xl backdrop-blur-xl min-h-[90px] transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] hover:shadow-lg"
              style={{
                background:
                  'linear-gradient(180deg, rgba(255, 255, 255, 0.36) 0%, rgba(161, 207, 211, 0.06) 100%)',
              }}
            >
              <CardHeader className="pb-3 pt-3 px-3 h-full flex flex-col justify-center">
                <CardTitle className="text-sm text-white flex items-center gap-2 mb-1">
                  {category.icon.startsWith('/') ? (
                    <img src={category.icon} alt={category.title} className="h-5 w-5 flex-shrink-0" />
                  ) : (
                    <span className="text-lg flex-shrink-0">{category.icon}</span>
                  )}
                  <span className="truncate">{category.title}</span>
                </CardTitle>
                <CardDescription className="text-xs text-white/60 leading-tight line-clamp-2">
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
          className="fixed inset-0 bg-[#001C1B]/85 backdrop-blur-md z-50 flex items-end sm:items-center justify-center px-4 pb-28 sm:pb-8 sm:px-4 sm:pt-4"
          onClick={() => onCategorySelect('')}
        >
          <Card
            className="w-full max-w-md sm:max-w-2xl h-[80vh] sm:h-auto sm:max-h-[80vh] bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80 shadow-[0_20px_60px_rgba(0,0,0,0.6)] backdrop-blur-xl rounded-2xl border-0"
            onClick={(e) => e.stopPropagation()}
          >
            <CardHeader className="border-b border-white/15 p-4 sm:p-6">
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <CardTitle className="text-base sm:text-lg text-white flex items-center gap-2">
                    {(() => {
                      const category = categories.find(c => c.id === selectedCategory);
                      const icon = category?.icon;
                      return icon?.startsWith('/') ? (
                        <img src={icon} alt={category?.title} className="h-5 w-5 sm:h-6 sm:w-6 flex-shrink-0" />
                      ) : (
                        <span className="text-xl sm:text-2xl flex-shrink-0">{icon}</span>
                      );
                    })()}
                    <span className="truncate">{categories.find(c => c.id === selectedCategory)?.title}</span>
                  </CardTitle>
                  <CardDescription className="text-white/60 mt-1 text-xs sm:text-sm line-clamp-2">
                    {categories.find(c => c.id === selectedCategory)?.description}
                  </CardDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onCategorySelect('')}
                  className="text-white/70 hover:text-white h-8 w-8 p-0 ml-2 flex-shrink-0 touch-manipulation"
                >
                  <img src="/cross.svg" alt="cross" className="h-6 w-6" />
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
