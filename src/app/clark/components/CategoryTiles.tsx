"use client"

import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Category } from '../types'

interface CategoryTilesProps {
  categories: Category[]
  selectedCategory: string | null
  onCategorySelect: (categoryId: string) => void
  onPromptClick: (prompt: string) => void
  isLoading: boolean
}

export default function CategoryTiles({
  categories,
  selectedCategory,
  onCategorySelect,
  onPromptClick,
  isLoading
}: CategoryTilesProps) {
  return (
    <div className="pb-1 mb-1">
      {/* Category Tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 sm:gap-4 w-full max-w-6xl mx-auto px-2 sm:px-0">
        {categories.map((category) => (
          <Card
            key={category.id}
            className="cursor-pointer hover:bg-zinc-800/60 active:bg-zinc-700/60 transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] hover:shadow-lg border-zinc-700/50 bg-zinc-800/30 backdrop-blur-sm min-h-[80px] sm:min-h-[90px] touch-manipulation"
            onClick={() => onCategorySelect(category.id)}
          >
            <CardHeader className="pb-3 pt-3 px-3 h-full flex flex-col justify-center">
              <CardTitle className="text-xs sm:text-sm text-white flex items-center gap-2 mb-1">
                {category.icon.startsWith('/') ? (
                  <img src={category.icon} alt={category.title} className="h-4 w-4 sm:h-5 sm:w-5 flex-shrink-0" />
                ) : (
                  <span className="text-base sm:text-lg flex-shrink-0">{category.icon}</span>
                )}
                <span className="truncate">{category.title}</span>
              </CardTitle>
              <CardDescription className="text-xs text-zinc-400 leading-tight line-clamp-2">
                {category.description}
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>

      {/* Prompts Modal */}
      {selectedCategory && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
             onClick={() => onCategorySelect('')}>
          <Card className="w-full h-[85vh] sm:h-auto sm:max-h-[80vh] sm:max-w-2xl bg-zinc-900/95 border-zinc-700/50 shadow-2xl backdrop-blur-sm rounded-t-2xl sm:rounded-2xl"
                onClick={(e) => e.stopPropagation()}>
            <CardHeader className="border-b border-zinc-700/50 p-4 sm:p-6">
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
                  <CardDescription className="text-zinc-400 mt-1 text-xs sm:text-sm line-clamp-2">
                    {categories.find(c => c.id === selectedCategory)?.description}
                  </CardDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onCategorySelect('')}
                  className="text-zinc-400 hover:text-white h-8 w-8 p-0 ml-2 flex-shrink-0 touch-manipulation"
                >
                  ✕
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-4 p-4 sm:p-6 max-h-[calc(85vh-120px)] sm:max-h-[60vh] overflow-y-auto">
              <div className="space-y-3">
                {categories.find(c => c.id === selectedCategory)?.prompts.map((prompt, index) => (
                  <button
                    key={index}
                    onClick={() => onPromptClick(prompt)}
                    disabled={isLoading}
                    className="w-full text-left p-4 rounded-lg bg-zinc-800/40 hover:bg-zinc-700/60 active:bg-zinc-600/60 border border-zinc-700/50 hover:border-purple-500/50 transition-all duration-200 text-white disabled:opacity-50 disabled:cursor-not-allowed group touch-manipulation min-h-[60px] flex items-center"
                  >
                    <div className="flex items-start gap-3 w-full">
                      <span className="text-purple-400 font-bold text-sm mt-1 flex-shrink-0">•</span>
                      <span className="flex-1 text-sm sm:text-base group-hover:text-purple-300 transition-colors leading-relaxed">
                        {prompt}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
