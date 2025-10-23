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

