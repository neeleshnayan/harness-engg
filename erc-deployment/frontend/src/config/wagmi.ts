import { createConfig, http } from 'wagmi';
import { mainnet, sepolia } from 'wagmi/chains';
import { coinbaseWallet, injected, metaMask, walletConnect } from 'wagmi/connectors';
import { defineChain } from 'viem';
import { env } from './env';

const knownChains = [sepolia, mainnet];

const resolved = knownChains.find((chain) => chain.id === env.chainId);

const fallback = defineChain({
  id: env.chainId,
  name: `Chain ${env.chainId}`,
  nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
  rpcUrls: {
    default: { http: env.rpcUrl ? [env.rpcUrl] : [] },
    public: { http: env.rpcUrl ? [env.rpcUrl] : [] },
  },
});

const activeChain = resolved ?? fallback;

const fallbackDefault = resolved?.rpcUrls?.default?.http?.[0];
const fallbackRpc = env.rpcUrl || fallbackDefault || 'https://ethereum.publicnode.com';

const walletConnectConnector = env.walletConnectProjectId
  ? [
      walletConnect({
        projectId: env.walletConnectProjectId,
        showQrModal: true,
        metadata: {
          name: 'MAVC Vault Control Center',
          description: 'Interact with the MAVC 50/50 USDC/WETH vault.',
          url: 'https://mavc.example',
          icons: ['https://avatars.githubusercontent.com/u/11297142?s=200&v=4'],
        },
      }),
    ]
  : [];

export const wagmiConfig = createConfig({
  chains: [activeChain],
  transports: {
    [activeChain.id]: http(fallbackRpc),
  },
  connectors: [
    metaMask({ dappMetadata: { name: 'MAVC Vault Control Center' } }),
    injected({ shimDisconnect: true }),
    coinbaseWallet({ appName: 'MAVC Vault Control Center' }),
    ...walletConnectConnector,
  ],
  ssr: false,
});
