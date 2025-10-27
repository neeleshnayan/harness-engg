import React, { useMemo } from "react";
import { FaCoins } from "react-icons/fa";

interface KTTokenBalance {
  symbol: string;
  balance: string;
}

interface KTTokenBalancesProps {
  balance: any;
  className?: string;
}

// K-Token configuration - addresses loaded from env
const K_TOKEN_CONFIG = [
  { symbol: 'kUSD', envVar: 'NEXT_PUBLIC_KUSD_ADDRESS', fallback: '0x5C58471Bc18E004F02Bc0D68573BDcdFb9C0F5D2' },
  { symbol: 'kAED', envVar: 'NEXT_PUBLIC_KAED_ADDRESS', fallback: '0x0780c2f253126C25a579f8E99A1a7BEFa3ae440b' },
  { symbol: 'kGBP', envVar: 'NEXT_PUBLIC_KGBP_ADDRESS', fallback: '0x11F1C75e7D89a152953f2708B95B60caC6f13195' },
  { symbol: 'kEUR', envVar: 'NEXT_PUBLIC_KEUR_ADDRESS', fallback: '0x52c2B994E2151aE66763b7ab95E003a82d911e53' },
  { symbol: 'kJPY', envVar: 'NEXT_PUBLIC_KJPY_ADDRESS', fallback: '0x5678901234567890123456789012345678901234' },
  { symbol: 'kCAD', envVar: 'NEXT_PUBLIC_KCAD_ADDRESS', fallback: '0x6789012345678901234567890123456789012345' },
  { symbol: 'kAUD', envVar: 'NEXT_PUBLIC_KAUD_ADDRESS', fallback: '0x7890123456789012345678901234567890123456' },
  { symbol: 'kCHF', envVar: 'NEXT_PUBLIC_KCHF_ADDRESS', fallback: '0x8901234567890123456789012345678901234567' },
];

const KTTokenBalances: React.FC<KTTokenBalancesProps> = ({ balance, className = "" }) => {
  // Extract k-token balances from the balance data
  const kTokenBalances = useMemo(() => {
    if (!balance || !balance.tokenBalances || !Array.isArray(balance.tokenBalances)) {
      return [];
    }

    // Debug: Log all environment variables
    console.log('All NEXT_PUBLIC env vars:', Object.keys(process.env).filter(key => key.startsWith('NEXT_PUBLIC_')));

    // Get all k-token addresses from environment
    const kTokenAddresses = K_TOKEN_CONFIG
      .map(token => {
        const address = process.env[token.envVar as keyof typeof process.env] || token.fallback;
        console.log(`Environment variable ${token.envVar}:`, address);
        console.log(`Using fallback:`, !process.env[token.envVar as keyof typeof process.env]);
        return {
          symbol: token.symbol,
          address: address?.toLowerCase(),
        };
      })
      .filter(token => !!token.address);

    console.log('K-token addresses found:', kTokenAddresses);

    // Find matching k-tokens in balance data
    const balances: KTTokenBalance[] = [];

    for (const kToken of kTokenAddresses) {
      const tokenBalance = balance.tokenBalances.find((tb: any) => {
        const tokenAddress = tb.token?.tokenAddress?.toLowerCase();
        return tokenAddress === kToken.address;
      });

      if (tokenBalance && parseFloat(tokenBalance.amount) > 0) {
        balances.push({
          symbol: kToken.symbol,
          balance: tokenBalance.amount,
        });
      }
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
          K-Token Balances
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {kTokenBalances.map((token) => (
          <div
            key={token.symbol}
            className="bg-zinc-800/60 border border-zinc-700/50 rounded-lg px-3 py-2 flex items-center"
          >
            <span className="text-white font-medium text-sm">{token.symbol}</span>
            <span className="text-zinc-300 ml-2 text-sm">
              {parseFloat(token.balance).toFixed(2)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default KTTokenBalances;

