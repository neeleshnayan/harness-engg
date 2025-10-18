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
    <div className="pb-6 mb-6">
      {/* Category Tiles */}
      <div className="grid grid-cols-5 gap-2 w-full max-w-6xl mx-auto">
        {categories.map((category) => (
          <Card
            key={category.id}
            className="cursor-pointer hover:bg-zinc-800/60 transition-all duration-200 hover:scale-[1.02] hover:shadow-lg border-zinc-700/50 bg-zinc-800/30 backdrop-blur-sm"
            onClick={() => onCategorySelect(category.id)}
          >
            <CardHeader className="pb-3 pt-3 px-3">
              <CardTitle className="text-sm text-white flex items-center gap-2">
                {category.icon.startsWith('/') ? (
                  <img src={category.icon} alt={category.title} className="h-4 w-4" />
                ) : (
                  <span className="text-lg">{category.icon}</span>
                )}
                {category.title}
              </CardTitle>
              <CardDescription className="text-xs text-zinc-400 leading-tight">
                {category.description}
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>

      {/* Prompts Modal */}
      {selectedCategory && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
             onClick={() => onCategorySelect('')}>
          <Card className="w-full max-w-2xl bg-zinc-900/95 border-zinc-700/50 shadow-2xl backdrop-blur-sm"
                onClick={(e) => e.stopPropagation()}>
            <CardHeader className="border-b border-zinc-700/50">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg text-white flex items-center gap-2">
                    {(() => {
                      const category = categories.find(c => c.id === selectedCategory);
                      const icon = category?.icon;
                      return icon?.startsWith('/') ? (
                        <img src={icon} alt={category?.title} className="h-6 w-6" />
                      ) : (
                        <span className="text-2xl">{icon}</span>
                      );
                    })()}
                    {categories.find(c => c.id === selectedCategory)?.title}
                  </CardTitle>
                  <CardDescription className="text-zinc-400 mt-1 text-sm">
                    {categories.find(c => c.id === selectedCategory)?.description}
                  </CardDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onCategorySelect('')}
                  className="text-zinc-400 hover:text-white h-8 w-8 p-0"
                >
                  ✕
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-4 max-h-[60vh] overflow-y-auto">
              <div className="space-y-2">
                {categories.find(c => c.id === selectedCategory)?.prompts.map((prompt, index) => (
                  <button
                    key={index}
                    onClick={() => onPromptClick(prompt)}
                    disabled={isLoading}
                    className="w-full text-left p-3 rounded-lg bg-zinc-800/40 hover:bg-zinc-700/60 border border-zinc-700/50 hover:border-purple-500/50 transition-all duration-200 text-white disabled:opacity-50 disabled:cursor-not-allowed group"
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-purple-400 font-bold text-xs mt-1">•</span>
                      <span className="flex-1 text-sm group-hover:text-purple-300 transition-colors leading-relaxed">
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
