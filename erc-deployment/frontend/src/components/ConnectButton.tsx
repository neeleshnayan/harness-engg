import { useEffect, useMemo, useState } from 'react';
import {
  useAccount,
  useChainId,
  useConnect,
  useDisconnect,
  useSwitchChain,
} from 'wagmi';
import type { Connector } from 'wagmi';
import { env } from '@/config/env';
import { formatAddress } from '@/lib/format';

const connectorLabels: Record<string, string> = {
  injected: 'Browser Wallet',
  walletConnect: 'WalletConnect',
  'io.metamask': 'MetaMask',
  coinbaseWalletSDK: 'Coinbase Wallet',
};

const getConnectorLabel = (connector: Connector) => connectorLabels[connector.id] ?? connector.name;

export const ConnectButton = () => {
  const { address, status } = useAccount();
  const activeChainId = useChainId();
  const { disconnect } = useDisconnect();
  const { switchChain, isPending: isSwitching } = useSwitchChain();
  const { connectors, connectAsync, status: connectStatus, error } = useConnect();

  const [showConnectorList, setShowConnectorList] = useState(false);
  const [showAccountActions, setShowAccountActions] = useState(false);
  const [connectingId, setConnectingId] = useState<string | null>(null);

  useEffect(() => {
    if (status === 'connected') {
      setShowConnectorList(false);
    }
  }, [status]);

  const availableConnectors = useMemo(() => {
    const unique: Connector[] = [];
    const seen = new Set<string>();

    for (const connector of connectors) {
      if (seen.has(connector.id)) continue;
      seen.add(connector.id);
      unique.push(connector);
    }

    const priority = ['io.metamask', 'coinbaseWalletSDK', 'walletConnect', 'injected'];
    unique.sort((a, b) => {
      const aPriority = priority.indexOf(a.id);
      const bPriority = priority.indexOf(b.id);

      if (aPriority === -1 && bPriority === -1) return a.name.localeCompare(b.name);
      if (aPriority === -1) return 1;
      if (bPriority === -1) return -1;
      return aPriority - bPriority;
    });

    return unique;
  }, [connectors]);

  const handleConnect = async (connector: Connector) => {
    try {
      setConnectingId(connector.id);
      await connectAsync({ connector });
    } catch (err) {
      console.error(err);
    } finally {
      setConnectingId(null);
    }
  };

  const isPending = connectStatus === 'pending';

  if (status === 'connected' && address) {
    const wrongNetwork = env.chainId && activeChainId && env.chainId !== activeChainId;

    return (
      <div className="relative z-40 flex items-center gap-3">
        {wrongNetwork && (
          <button
            type="button"
            onClick={() => switchChain?.({ chainId: env.chainId })}
            className="rounded-full bg-amber-500/20 px-4 py-2 text-sm font-semibold text-amber-200 shadow shadow-amber-500/20 transition hover:bg-amber-500/30"
            disabled={isSwitching}
          >
            {isSwitching ? 'Switching...' : 'Switch Network'}
          </button>
        )}
        <button
          type="button"
          onClick={() => setShowAccountActions((prev) => !prev)}
          className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-white transition hover:border-white/30 hover:bg-white/10"
        >
          {formatAddress(address)}
        </button>
        {showAccountActions && (
          <div className="absolute right-0 top-12 z-50 w-48 rounded-2xl border border-white/10 bg-surface p-3 text-sm text-white shadow-xl">
            <button
              type="button"
              onClick={() => disconnect()}
              className="block w-full rounded-xl bg-white/5 px-4 py-2 text-left font-semibold text-white/80 transition hover:bg-white/10"
            >
              Disconnect
            </button>
          </div>
        )}
      </div>
    );
  }

  if (!availableConnectors.length) {
    return (
      <button
        type="button"
        className="rounded-full bg-white/5 px-4 py-2 text-sm font-semibold text-white/70"
        disabled
      >
        No Wallet Detected
      </button>
    );
  }

  return (
    <div className="relative z-40">
      <button
        type="button"
        onClick={() => setShowConnectorList((prev) => !prev)}
        className="rounded-full bg-accent px-6 py-2 text-sm font-semibold text-white shadow-glow transition hover:bg-accentSoft"
      >
        {connectingId ? 'Connecting...' : 'Connect Wallet'}
      </button>

      {showConnectorList && (
        <div className="absolute right-0 top-12 z-50 w-64 space-y-2 rounded-3xl border border-white/10 bg-surface p-4 shadow-2xl">
          <p className="text-xs uppercase tracking-[0.2em] text-white/50">Choose wallet</p>
          <div className="space-y-2">
            {availableConnectors.map((connector) => {
              const isBrowserInjected = connector.type === 'injected' || connector.id === 'io.metamask';
              const isWalletConnect = connector.id === 'walletConnect';
              const isConnectorReady = connector.ready || isBrowserInjected;
              const isButtonDisabled =
                (isPending && connectingId !== connector.id) || connectingId === connector.id || (!isConnectorReady && isWalletConnect);

              return (
                <button
                  key={connector.id}
                  type="button"
                  onClick={() => handleConnect(connector)}
                  className="flex w-full items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-semibold text-white transition hover:border-accent/40 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={isButtonDisabled}
                >
                  <span>{getConnectorLabel(connector)}</span>
                  {connectingId === connector.id ? (
                    <span className="text-xs text-white/60">Connecting...</span>
                  ) : isConnectorReady ? (
                    <span className="text-xs text-white/40">Ready</span>
                  ) : (
                    <span className="text-xs text-white/50">Install required</span>
                  )}
                </button>
              );
            })}
          </div>
          {error && <p className="text-xs text-rose-300/80">{error.message}</p>}
          {!env.walletConnectProjectId && (
            <p className="text-[11px] text-white/50">
              Set VITE_WALLETCONNECT_PROJECT_ID in your .env to enable WalletConnect QR connections.
            </p>
          )}
        </div>
      )}
    </div>
  );
};
