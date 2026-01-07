// Pool addresses and token addresses from backend
// All actual addresses are fetched dynamically from backend API

export const POOL_TOKENS = {
  kUSD: { symbol: 'kUSD', decimals: 18 },
  kEUR: { symbol: 'kEUR', decimals: 18 },
  kGBP: { symbol: 'kGBP', decimals: 18 },
  kAED: { symbol: 'kAED', decimals: 18 },
  USDC: { symbol: 'USDC', decimals: 6 },
} as const;

export type TokenSymbol = keyof typeof POOL_TOKENS;

// Helper functions
export function parseTokenAmount(amount: string | number, symbol: TokenSymbol): bigint {
  const decimals = POOL_TOKENS[symbol].decimals;
  const numAmount = typeof amount === 'string' ? parseFloat(amount) : amount;
  return BigInt(Math.floor(numAmount * Math.pow(10, decimals)));
}

export function formatTokenAmount(amount: bigint | string, symbol: TokenSymbol): string {
  const decimals = POOL_TOKENS[symbol].decimals;
  const amountBigInt = typeof amount === 'string' ? BigInt(amount) : amount;
  const divisor = BigInt(Math.pow(10, decimals));
  const whole = amountBigInt / divisor;
  const remainder = amountBigInt % divisor;
  const decimalStr = remainder.toString().padStart(decimals, '0');
  return `${whole}.${decimalStr.slice(0, 6)}`; // Show up to 6 decimal places
}

