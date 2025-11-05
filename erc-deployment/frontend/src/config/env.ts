const toAddress = (value?: string) => {
  if (!value) return undefined;
  return value.startsWith('0x') ? (value as `0x${string}`) : undefined;
};

const sanitizeUrl = (value?: string, placeholders: string[] = []) => {
  if (!value) return undefined;
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const defaultPlaceholders = ['YOUR_KEY', 'YOUR_PROJECT_ID', 'YOUR_RPC', 'YOUR_SUBGRAPH_ID'];
  const checks = placeholders.length > 0 ? placeholders : defaultPlaceholders;
  return checks.some((token) => trimmed.includes(token)) ? undefined : trimmed;
};

const sanitizeValue = (value?: string) => {
  if (!value) return undefined;
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  return trimmed;
};

const rawChainId = import.meta.env.VITE_CHAIN_ID ?? '11155111';

export const env = {
  chainId: Number(rawChainId),
  rpcUrl: sanitizeUrl(import.meta.env.VITE_RPC_URL),
  subgraphUrl: sanitizeUrl(import.meta.env.VITE_SUBGRAPH_URL),
  walletConnectProjectId: sanitizeValue(import.meta.env.VITE_WALLETCONNECT_PROJECT_ID),
  addresses: {
    vault: toAddress(import.meta.env.VITE_VAULT_ADDRESS),
    mavpVault: toAddress(import.meta.env.VITE_MAVP_VAULT_ADDRESS),
    usdc: toAddress(import.meta.env.VITE_USDC_ADDRESS),
    weth: toAddress(import.meta.env.VITE_WETH_ADDRESS),
    oracle: toAddress(import.meta.env.VITE_ORACLE_ADDRESS),
  },
} as const;

export const isEnvReady = () => Boolean(env.addresses.vault && env.addresses.usdc);
export const isMAVPEnvReady = () => Boolean(env.addresses.mavpVault && env.addresses.usdc);
