export const chainlinkOracleAbi = [
  {
    inputs: [{ internalType: 'string', name: 'symbol', type: 'string' }],
    name: 'getPrice',
    outputs: [{ internalType: 'uint256', name: 'price', type: 'uint256' }],
    stateMutability: 'view',
    type: 'function',
  },
  {
    inputs: [],
    name: 'getDaiPrice',
    outputs: [{ internalType: 'uint256', name: 'price', type: 'uint256' }],
    stateMutability: 'view',
    type: 'function',
  },
  {
    inputs: [],
    name: 'getEurPrice',
    outputs: [{ internalType: 'uint256', name: 'price', type: 'uint256' }],
    stateMutability: 'view',
    type: 'function',
  },
  {
    inputs: [],
    name: 'getDetailedPrices',
    outputs: [
      { internalType: 'uint256', name: 'daiPrice', type: 'uint256' },
      { internalType: 'uint256', name: 'eurPrice', type: 'uint256' },
      { internalType: 'uint256', name: 'eurDaiPrice', type: 'uint256' },
      { internalType: 'uint256', name: 'daiTimestamp', type: 'uint256' },
      { internalType: 'uint256', name: 'eurTimestamp', type: 'uint256' },
    ],
    stateMutability: 'view',
    type: 'function',
  },
  {
    inputs: [],
    name: 'isHealthy',
    outputs: [{ internalType: 'bool', name: 'healthy', type: 'bool' }],
    stateMutability: 'view',
    type: 'function',
  },
] as const;
