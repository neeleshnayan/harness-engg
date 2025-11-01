// Static mapping of k-token addresses to their symbols
export const K_TOKEN_ADDRESSES: Record<string, string> = {
  '0x68182a9785ff56c958f01a5c47e4cbb1f96cdac5': 'kUSD',
  '0x063374a52502816432c7cb3528a9275e6e043e1a': 'kEUR',
  '0xea3853446cc06961d836b76b178be4aa8b946cb2': 'kGBP',
  '0x21fc94f99cd8d7169f7df9878ae1426bdccc5cbf': 'kAED',
};

// Reverse mapping: symbol to address
export const K_TOKEN_SYMBOLS: Record<string, string> = {
  'kUSD': '0x68182a9785ff56c958f01a5c47e4cbb1f96cdac5',
  'kEUR': '0x063374a52502816432c7cb3528a9275e6e043e1a',
  'kGBP': '0xea3853446cc06961d836b76b178be4aa8b946cb2',
  'kAED': '0x21fc94f99cd8d7169f7df9878ae1426bdccc5cbf',
};

// Array of supported k-token symbols
export const K_TOKEN_SYMBOL_LIST = Object.keys(K_TOKEN_SYMBOLS);

