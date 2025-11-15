// Static mapping of k-token addresses to their symbols
export const K_TOKEN_ADDRESSES: Record<string, string> = {
  '0x05B028e473aaad016C1D058A6BFDe24e718E3244': 'kUSD',
  '0x13536b6c8f7588511a840874e68adD8198285855': 'kEUR',
  '0x9fBFb6Ca7A4bA04d614f92607a2555b20094d562': 'kGBP',
  '0xaf7C7521306d2c9EAA3F4c6083C53fE11aB397a2': 'kAED',
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

