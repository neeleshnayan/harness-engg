"use client"

import { useMemo } from 'react'
import { ChatMessage, ScreenerCrypto } from '../types'
import { detectBacktestTopPattern, mapCryptoNameToBackendFormat } from '../utils'

export const useQueryTransformation = (messages: ChatMessage[]) => {
  // Helper function to get the most recent screener results
  const getLatestScreenerResults = (): ScreenerCrypto[] | null => {
    const screenerMessages = messages
      .filter(m => m.screenerResult)
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
    
    if (screenerMessages.length > 0) {
      return screenerMessages[0].screenerResult!.results
    }
    
    return null
  }

  // Helper function to transform backtest query with specific crypto symbols
  const transformBacktestQuery = (originalQuery: string): string => {
    const patternMatch = detectBacktestTopPattern(originalQuery)
    
    if (!patternMatch) {
      return originalQuery
    }
    
    const screenerResults = getLatestScreenerResults()
    
    if (!screenerResults || screenerResults.length === 0) {
      return originalQuery
    }
    
    const { count, weight } = patternMatch
    const topCryptos = screenerResults.slice(0, count)
    
    if (topCryptos.length === 0) {
      return originalQuery
    }
    
    // Create allocation strings for each crypto in the format expected by backend
    const allocations = topCryptos.map(crypto => {
      const mappedName = mapCryptoNameToBackendFormat(crypto)
      return `${mappedName} ${weight}%`
    }).join(', ')
    
    // Replace the "backtest top X" part with specific crypto allocations
    let transformedQuery = originalQuery
    const replacePatterns = [
      /backtest\s+(?:the\s+)?top\s+(\d+|\w+)(?:\s+with\s+\d+%\s+weightage)?/i,
      /backtest\s+(?:the\s+)?top\s+(\d+|\w+)(?:\s+with\s+\d+%\s+weight)?/i,
      /backtest\s+(?:the\s+)?top\s+(\d+|\w+)(?:\s+\d+%)?/i
    ]
    
    for (const pattern of replacePatterns) {
      if (pattern.test(originalQuery)) {
        transformedQuery = originalQuery.replace(pattern, `Backtest ${allocations}`)
        break
      }
    }
    
    return transformedQuery
  }

  return {
    transformBacktestQuery,
    getLatestScreenerResults
  }
}
