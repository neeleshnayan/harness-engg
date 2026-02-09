'use client';

import { useState, useEffect } from 'react';
import { nettingPoolsApi, OracleRateResponse } from '@/lib/nettingPoolsApi';
import { CURRENCY_SYMBOLS } from '@/lib/ratesApi';

interface PriceFeedCardProps {
  fxPair: string;
  symbol: string;
  currencySymbol?: string;
  refreshInterval?: number;
}

const GRADIENT_COLORS: Record<string, { from: string; to: string; textColor: string }> = {
  EUR: { from: 'from-indigo-500', to: 'to-purple-500', textColor: 'text-purple-400' },
  GBP: { from: 'from-green-500', to: 'to-emerald-500', textColor: 'text-green-400' },
  AED: { from: 'from-amber-500', to: 'to-orange-500', textColor: 'text-amber-400' },
  USD: { from: 'from-blue-500', to: 'to-indigo-500', textColor: 'text-blue-400' },
};

export default function PriceFeedCard({
  fxPair,
  symbol,
  currencySymbol,
  refreshInterval = 30000,
}: PriceFeedCardProps) {
  const [rateData, setRateData] = useState<OracleRateResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchRate = async () => {
    try {
      const data = await nettingPoolsApi.getOracleRate(fxPair);
      setRateData(data);
      setLastUpdated(new Date());
      setError('');
    } catch (err: any) {
      console.error(`Error fetching rate for ${fxPair}:`, err);
      setError('Failed to fetch rate');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRate();
    const interval = setInterval(fetchRate, refreshInterval);
    return () => clearInterval(interval);
  }, [fxPair, refreshInterval]);

  // Extract currency from pair (e.g., "USD/EUR" -> "EUR")
  const targetCurrency = fxPair.split('/')[1] || symbol;
  const displayCurrencySymbol = currencySymbol || CURRENCY_SYMBOLS[targetCurrency] || '$';
  const colors = GRADIENT_COLORS[targetCurrency] || GRADIENT_COLORS.USD;

  return (
    <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-5 hover:bg-white/[0.04] transition-all duration-300">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className={`w-10 h-10 rounded-full bg-gradient-to-br ${colors.from} ${colors.to} flex items-center justify-center shadow-lg`}
          >
            <span className="text-white text-lg font-light">{displayCurrencySymbol}</span>
          </div>
          <div>
            <h4 className="text-white text-base font-medium">{symbol}</h4>
            <p className={`${colors.textColor} text-xs font-mono`}>{fxPair}</p>
          </div>
        </div>
        <div
          className={`w-2 h-2 rounded-full ${
            loading ? 'bg-yellow-400 animate-pulse' : error ? 'bg-red-400' : 'bg-green-400'
          }`}
        />
      </div>

      <div className="space-y-3">
        {loading && !rateData ? (
          <div className="h-12 flex items-center">
            <div className="text-gray-400 text-sm">Loading...</div>
          </div>
        ) : error && !rateData ? (
          <div className="h-12 flex items-center">
            <div className="text-red-400 text-sm">{error}</div>
          </div>
        ) : (
          <>
            <div>
              <p className="text-gray-400 text-xs mb-1">Exchange Rate</p>
              <p className={`text-2xl font-semibold ${colors.textColor}`}>
                {parseFloat(rateData?.rate || '0').toFixed(6)}
              </p>
              <p className="text-gray-500 text-xs mt-1">
                1 USD = {(1 / (parseFloat(rateData?.rate || '1'))).toFixed(4)} {targetCurrency}
              </p>
            </div>

            <div className="pt-2 border-t border-white/[0.05]">
              <div className="flex justify-between items-center text-xs">
                <span className="text-gray-500">Source</span>
                <span className="text-gray-400">{rateData?.source || 'KryptonFXOracle'}</span>
              </div>
              {lastUpdated && (
                <div className="flex justify-between items-center text-xs mt-1">
                  <span className="text-gray-500">Updated</span>
                  <span className="text-gray-400">
                    {lastUpdated.toLocaleTimeString()}
                  </span>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

