// Static mapping of k-token addresses to their symbols
export const K_TOKEN_ADDRESSES: Record<string, string> = {
  '0xdeb6029413304564C2f45663AB9f86ed94230932': 'kUSD',
  '0xCb268A23770aD6A5D3f534f6e1Ea8bA169C07f23': 'kEUR',
  '0x3aFD5C3cD38A1f69aD078aa036d12B0DAE2eD8e0': 'kGBP',
  '0xdF7fCDCA5C1FA9A4f172e68faE9598A5e9Cc58b7': 'kAED',
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

