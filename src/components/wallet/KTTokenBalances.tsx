import React, { useEffect, useMemo, useState } from "react";
import { FaCoins } from "react-icons/fa";
import { listERC20Tokens } from "@/lib/api";

interface KTTokenBalance {
  symbol: string;
  balance: string;
}

interface KTTokenBalancesProps {
  balance: any;
  className?: string;
}

const KTTokenBalances: React.FC<KTTokenBalancesProps> = ({ balance, className = "" }) => {
  const [addressToSymbol, setAddressToSymbol] = useState<Record<string, string>>({});

  useEffect(() => {
    let isMounted = true;
    (async () => {
      try {
        const data = await listERC20Tokens();
        const map: Record<string, string> = {};
        if (data && Array.isArray(data.tokens)) {
          for (const t of data.tokens) {
            if (t?.address && t?.symbol) {
              map[String(t.address).toLowerCase()] = String(t.symbol);
            }
          }
        }
        if (isMounted) setAddressToSymbol(map);
      } catch (e) {
        console.error('Failed to load ERC20 tokens list:', e);
      }
    })();
    return () => { isMounted = false; };
  }, []);

  // Extract k-token balances from the balance data
  const kTokenBalances = useMemo(() => {
    if (!balance || !balance.tokenBalances || !Array.isArray(balance.tokenBalances)) {
      return [];
    }

    const balances: KTTokenBalance[] = [];
    for (const tb of balance.tokenBalances) {
      const tokenAddress = tb?.token?.tokenAddress?.toLowerCase();
      const symbol = tokenAddress ? addressToSymbol[tokenAddress] : undefined;
      if (symbol && parseFloat(tb.amount) > 0) {
        balances.push({ symbol, balance: tb.amount });
      }
    }
    return balances;
  }, [balance, addressToSymbol]);

  console.log(kTokenBalances);
  if (kTokenBalances.length === 0) {
    return null; // Don't show anything if user has no k-tokens
  }

  return (
    <div className={`mt-4 pt-4 border-t border-zinc-700/50 ${className}`}>
      <div className="mb-2">
        <div className="flex items-center text-zinc-400 text-sm">
          <FaCoins className="mr-2" />
          All Currencies
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {kTokenBalances.map((token) => (
          <div
            key={token.symbol}
            className="bg-zinc-800/60 border border-zinc-700/50 rounded-lg px-3 py-2 flex items-center"
          >
            <span className="text-white font-medium text-sm">
              {parseFloat(token.balance).toFixed(2)} {token.symbol.replace(/^k/, '')}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default KTTokenBalances;

