// Static mapping of k-token addresses to their symbols
export const K_TOKEN_ADDRESSES: Record<string, string> = {
  '0xda0a97267334450A65480138272880b8639541BF': 'kUSD',
  '0xEfC3D4f8e34719F4c333Ab0751B6a7cd95e8C93B': 'kEUR',
  '0x830B57829515D6CC2AeA7E59c54DFd8F4Bf913ba': 'kGBP',
  '0x816886d27de24B1F3fBd840ef5E1d046378361f1': 'kAED',
};

// Mapping of k-token addresses to their symbols in lowercase
export const K_TOKEN_ADDRESSES_LOWERCASE: Record<string, string> = Object.fromEntries(
  Object.entries(K_TOKEN_ADDRESSES).map(([address, symbol]) => [address.toLowerCase(), symbol]));

// Reverse mapping: symbol to address
export const K_TOKEN_SYMBOLS: Record<string, string> = Object.fromEntries(Object.entries(K_TOKEN_ADDRESSES).map(([address, symbol]) => [symbol, address]));

// Mapping of k-token symbols to their addresses in lowercase
export const K_TOKEN_SYMBOLS_LOWERCASE: Record<string, string> = Object.fromEntries(
  Object.entries(K_TOKEN_SYMBOLS).map(([symbol, address]) => [symbol, address.toLowerCase()]));

// Array of supported k-token symbols
export const K_TOKEN_SYMBOL_LIST = Object.keys(K_TOKEN_SYMBOLS);

// Currency symbol map for display
export const CURRENCY_SYMBOLS: Record<string, string> = {
  'USD': '$',
  'EUR': '€',
  'GBP': '£',
  'AED': 'د.إ',
};

