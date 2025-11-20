import React, { useMemo } from "react";
import { FaCoins } from "react-icons/fa";
import { K_TOKEN_ADDRESSES_LOWERCASE } from "@/lib/kTokens";

interface KTTokenBalance {
  symbol: string;
  balance: string;
}

interface KTTokenBalancesProps {
  balance: any;
  className?: string;
}

const KTTokenBalances: React.FC<KTTokenBalancesProps> = ({ balance, className = "" }) => {
  // Extract k-token balances from the balance data
  const kTokenBalances = useMemo(() => {
    console.log("balance", balance);
    if (!balance || !balance.tokenBalances || !Array.isArray(balance.tokenBalances)) {
      return [];
    }

    const aggregatedBalances: Record<string, number> = {};
    let usdcTotal = 0;

    for (const tb of balance.tokenBalances) {
      const rawAmount = parseFloat(tb?.amount ?? "0");
      if (isNaN(rawAmount) || rawAmount <= 0) {
        continue;
      }

      const tokenAddress = tb?.token?.tokenAddress?.toLowerCase();
      const kTokenSymbol = tokenAddress ? K_TOKEN_ADDRESSES_LOWERCASE[tokenAddress] : undefined;
      const tokenSymbol = tb?.token?.symbol;

      if (kTokenSymbol) {
        aggregatedBalances[kTokenSymbol] = (aggregatedBalances[kTokenSymbol] || 0) + rawAmount;
        continue;
      }

      if (tokenSymbol === "USDC" || tokenSymbol === "TRNSK") {
        usdcTotal += rawAmount;
      }
    }

    const balances: KTTokenBalance[] = Object.entries(aggregatedBalances).map(([symbol, amount]) => ({
      symbol,
      balance: amount.toString(),
    }));

    if (usdcTotal > 0) {
      balances.push({ symbol: "USDC", balance: usdcTotal.toString() });
    }

    return balances;
  }, [balance]);

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

