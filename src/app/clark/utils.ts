import { ScreenerCrypto } from './types'

export const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

export const formatPercentage = (value: number) => {
  return `${value.toFixed(2)}%`
}

export const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString()
}

export const formatNumber = (num: number) => {
  if (num >= 1_000_000_000) {
    return `$${(num / 1_000_000_000).toFixed(2)}B`
  } else if (num >= 1_000_000) {
    return `$${(num / 1_000_000).toFixed(2)}M`
  } else if (num >= 1_000) {
    return `$${(num / 1_000).toFixed(2)}K`
  } else {
    return `$${num.toFixed(2)}`
  }
}

export const formatTimestamp = (timestamp: Date) => {
  return timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// Helper function to convert word numbers to digits
export const wordToNumber = (word: string): number => {
  const wordMap: { [key: string]: number } = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
  }
  return wordMap[word.toLowerCase()] || parseInt(word) || 0
}

// Helper function to detect if query contains "backtest top X" pattern
export const detectBacktestTopPattern = (query: string): { count: number; weight: number } | null => {
  const patterns = [
    /backtest\s+(?:the\s+)?top\s+(\d+|\w+)(?:\s+with\s+(\d+)%\s+weightage)?/i,
    /backtest\s+(?:the\s+)?top\s+(\d+|\w+)(?:\s+with\s+(\d+)%\s+weight)?/i,
    /backtest\s+(?:the\s+)?top\s+(\d+|\w+)(?:\s+(\d+)%)?/i
  ]
  
  for (const pattern of patterns) {
    const match = query.match(pattern)
    if (match) {
      const count = wordToNumber(match[1])
      const weight = match[2] ? parseInt(match[2]) : Math.floor(100 / count)
      return { count, weight }
    }
  }
  
  return null
}

// Helper function to map screener crypto names to backend expected names
export const mapCryptoNameToBackendFormat = (crypto: ScreenerCrypto): string => {
  const nameMapping: { [key: string]: string } = {
    'bitcoin': 'Bitcoin',
    'ethereum': 'Ethereum', 
    'binance coin': 'Binance',
    'solana': 'Solana',
    'cardano': 'Cardano',
    'ripple': 'Ripple',
    'tron': 'Tron',
    'dogecoin': 'Dogecoin',
    'polkadot': 'Polkadot',
    'tether': 'Stablecoin',
    'usd coin': 'Stablecoin',
    'chainlink': 'Chainlink',
    'litecoin': 'Litecoin',
    'uniswap': 'Uniswap',
    'avalanche': 'Avalanche'
  }
  
  const lowerName = crypto.name.toLowerCase()
  if (nameMapping[lowerName]) {
    return nameMapping[lowerName]
  }
  
  for (const [key, value] of Object.entries(nameMapping)) {
    if (lowerName.includes(key)) {
      return value
    }
  }
  
  return crypto.name
}
