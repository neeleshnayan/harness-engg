// Static mapping of k-token addresses to their symbols
export const K_TOKEN_ADDRESSES: Record<string, string> = {
  '0xc1868b5BA545C18082510283FEeC1C8BA314591e': 'kUSD',
  '0x9d20B4982C2AA045C913907Eb0dd13203c14a474': 'kEUR',
  '0xeD40d78431Cc0183B3F7bdA5d7F1E461908cbf7B': 'kGBP',
  '0xD9fef4C9d70EfA3da4ba08eDB01a0BD642cB8d8B': 'kAED',
};

// Mapping of k-token addresses to their symbols in lowercase
export const K_TOKEN_ADDRESSES_LOWERCASE: Record<string, string> = Object.fromEntries(
  Object.entries(K_TOKEN_ADDRESSES).map(([address, symbol]) => [address.toLowerCase(), symbol]));

// Reverse mapping: symbol to address
export const K_TOKEN_SYMBOLS: Record<string, string> = Object.fromEntries(Object.entries(K_TOKEN_ADDRESSES).map(([address, symbol]) => [symbol, address]));

// Array of supported k-token symbols
export const K_TOKEN_SYMBOL_LIST = Object.keys(K_TOKEN_SYMBOLS);

// Currency symbol map for display
export const CURRENCY_SYMBOLS: Record<string, string> = {
  'USD': '$',
  'EUR': '€',
  'GBP': '£',
  'AED': 'د.إ',
};

