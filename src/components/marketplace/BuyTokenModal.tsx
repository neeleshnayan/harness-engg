"use client";

import React, { useState, useEffect } from "react";
import { X, DollarSign, Calculator, Target, Loader2 } from "lucide-react";
import { MarketplaceItem } from "@/lib/marketplace";
import api from "@/lib/api";

interface BuyTokenModalProps {
  startup: MarketplaceItem | null;
  isOpen: boolean;
  onClose: () => void;
  onBuy: (startupId: string, tokenCount: number, sellTarget: number) => void;
}

export default function BuyTokenModal({ startup, isOpen, onClose, onBuy }: BuyTokenModalProps) {
  const [tokenCount, setTokenCount] = useState<string>("1");
  const [sellTarget, setSellTarget] = useState<string>("");
  const [tokenQuote, setTokenQuote] = useState<string>("");
  const [tranchingCost, setTranchingCost] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [tranchingLoading, setTranchingLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && startup) {
      // Reset form when modal opens
      setTokenCount("1");
      setSellTarget("");
      setTokenQuote("");
      setTranchingCost(null);
      setError(null);
      // Fetch token quote when modal opens
      fetchTokenQuote();
    }
  }, [isOpen, startup]);

  useEffect(() => {
    if (startup && tokenCount && !isNaN(parseFloat(tokenCount))) {
      fetchTranchingDetails();
    } else {
      setTranchingCost(null);
    }
  }, [tokenCount, startup]);

  const fetchTokenQuote = async () => {
    if (!startup) return;

    setQuoteLoading(true);
    try {
      const response = await api.get('/api/v1/smarttoken/firebase_price/' + startup.address);
      setTokenQuote("$" + response.data.current_price.toString());
    } catch (err) {
      console.error('Failed to fetch token quote:', err);
      setTokenQuote("Quote unavailable");
    } finally {
      setQuoteLoading(false);
    }
  };

  const fetchTranchingDetails = async () => {
    if (!startup || !tokenCount) return;

    const count = parseFloat(tokenCount);
    if (isNaN(count) || count <= 0) return;

    setTranchingLoading(true);
    try {
      const response = await api.post('/api/v1/smarttoken/tranching_details', {
        token_address: startup.address,
        amount: count,
        business_id: startup.id
      });

      if (response.data.success) {
        setTranchingCost(response.data.total_cost_usdc);
      } else {
        setTranchingCost(null);
      }
    } catch (err) {
      console.error('Failed to fetch tranching details:', err);
      setTranchingCost(null);
    } finally {
      setTranchingLoading(false);
    }
  };

  const handleBuyClick = async () => {
    if (!startup) return;

    // Validation
    if (!tokenCount.trim()) {
      setError("Please enter the number of tokens");
      return;
    }

    const count = parseFloat(tokenCount);
    if (isNaN(count) || count <= 0) {
      setError("Please enter a valid number of tokens");
      return;
    }

    if (!sellTarget.trim()) {
      setError("Please enter a sell target");
      return;
    }

    const target = parseFloat(sellTarget);
    if (isNaN(target) || target <= 0) {
      setError("Please enter a valid sell target");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await onBuy(startup.id, count, target);
      onClose();
    } catch (err) {
      setError("Failed to purchase tokens. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setTokenCount("");
    setSellTarget("");
    setTokenQuote("");
    setTranchingCost(null);
    setError(null);
    onClose();
  };

  const calculateTotalCost = () => {
    if (tranchingCost !== null) {
      return tranchingCost.toFixed(2);
    }

    // Fallback to simple calculation if tranching cost is not available
    if (!tokenCount || !startup) return "0";
    const count = parseFloat(tokenCount);
    if (isNaN(count)) return "0";

    // Extract price from tokenQuote, handle edge cases
    const priceMatch = tokenQuote.match(/\$?([\d.]+)/);
    if (!priceMatch) return "0";

    const price = parseFloat(priceMatch[1]);
    if (isNaN(price)) return "0";

    return (count * price).toFixed(2);
  };

  const calculateCostPerToken = () => {
    const totalCost = calculateTotalCost();
    const totalCostNum = parseFloat(totalCost);
    if (isNaN(totalCostNum) || totalCostNum === 0) return "0";

    const count = parseFloat(tokenCount);
    if (isNaN(count) || count === 0) return "0";

    return (totalCostNum / count).toFixed(2);
  };

  if (!isOpen || !startup) return null;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white/10 border border-white/20 rounded-3xl p-6 max-w-md w-full backdrop-blur-xl">
        {/* Header */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-2xl font-bold text-white mb-1">Buy Tokens</h2>
            <p className="text-zinc-400 text-sm">{startup.name}</p>
          </div>
          <button
            onClick={handleClose}
            className="text-zinc-400 hover:text-white transition-colors p-2 hover:bg-white/10 rounded-full"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Token Information */}
        {/* <div className="mb-6">
          <div className="bg-white/5 border border-white/10 rounded-xl p-4 mb-4">
            <div className="flex items-center justify-between">
              <span className="text-zinc-400 text-sm">Current Price</span>
              <span className="text-green-400 font-semibold">${startup.price.toLocaleString()}</span>
            </div>
          </div>
        </div> */}

        {/* Number of Tokens */}
        <div className="mb-4">
          <label className="block text-white text-sm font-medium mb-2">
            Number of Tokens
          </label>
          <div className="relative">
            <input
              type="number"
              value={tokenCount}
              onChange={(e) => setTokenCount(e.target.value)}
              placeholder="Enter number of tokens"
              className="w-full bg-white/5 border border-white/20 rounded-xl px-4 py-3 text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400 focus:border-transparent [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              min="1"
              step="1"
            />
            <Calculator className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-zinc-400" />
          </div>
        </div>

        {/* Token Quote */}
        <div className="mb-4">
          <label className="block text-white text-sm font-medium mb-2">
            Token Quote
          </label>
          {/* <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 flex items-center justify-between">
            <span className="text-zinc-400 text-sm">Estimated Quote</span>
            <span className="text-cyan-400 font-semibold">
              {quoteLoading ? (
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-cyan-400 border-t-transparent"></div>
              ) : (
                tokenQuote || "Loading..."
              )}
            </span>
          </div> */}
        </div>

        {/* Cost Per Token */}
        {tokenCount && (
          <div className="mb-4">
            <div className="bg-gradient-to-r from-cyan-400/10 to-purple-400/10 border border-cyan-400/20 rounded-xl px-4 py-3 flex items-center justify-between">
              <span className="text-white text-sm font-medium">Estimated Cost Per Token</span>
              <span className="text-cyan-400 font-bold text-lg">
                {tranchingLoading || quoteLoading ? (
                  <div className="flex items-center gap-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-cyan-400 border-t-transparent"></div>
                    <span className="text-sm">Calculating...</span>
                  </div>
                ) : (
                  `$${calculateCostPerToken()}`
                )}
              </span>
            </div>
          </div>
        )}

        {/* Total Cost */}
        {tokenCount && (
          <div className="mb-4">
            <div className="bg-gradient-to-r from-cyan-400/10 to-purple-400/10 border border-cyan-400/20 rounded-xl px-4 py-3 flex items-center justify-between">
              <span className="text-white text-sm font-medium">Total Cost</span>
              <span className="text-cyan-400 font-bold text-lg">
                {tranchingLoading || quoteLoading ? (
                  <div className="flex items-center gap-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-cyan-400 border-t-transparent"></div>
                    <span className="text-sm">Calculating...</span>
                  </div>
                ) : (
                  `$${calculateTotalCost()}`
                )}
              </span>
            </div>
          </div>
        )}

        {/* Sell Target */}
        <div className="mb-6">
          <label className="block text-white text-sm font-medium mb-2">
            Sell Target per Token
          </label>
          <div className="relative">
            <input
              type="number"
              value={sellTarget}
              onChange={(e) => setSellTarget(e.target.value)}
              placeholder="Enter sell target price"
              className="w-full bg-white/5 border border-white/20 rounded-xl px-4 py-3 text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400 focus:border-transparent"
              min="0"
              step="0.01"
            />
            <Target className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-zinc-400" />
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3">
          <button
            onClick={handleBuyClick}
            disabled={loading || !startup.is_minting_active}
            className={`flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-semibold transition-all ${
              startup.is_minting_active && !loading
                ? 'bg-gradient-to-r from-cyan-400 to-purple-600 hover:from-cyan-500 hover:to-purple-700 text-black'
                : 'bg-gray-600 text-gray-400 cursor-not-allowed'
            }`}
          >
            <DollarSign className="h-5 w-5" />
            Buy Tokens
          </button>
          <button
            onClick={handleClose}
            className="px-6 py-3 border border-white/20 text-white hover:bg-white/10 rounded-xl transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>

      {/* Token Purchase Loading Modal */}
      {loading && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-2xl flex items-center justify-center z-50">
          <div className="bg-gradient-to-br from-zinc-900/90 via-zinc-800/80 to-cyan-900/60 border border-cyan-400/20 rounded-3xl p-10 w-full max-w-md mx-4 shadow-2xl ring-2 ring-cyan-400/10">
            <div className="flex flex-col items-center space-y-6">
              <div className="relative">
                <Loader2 className="h-16 w-16 text-cyan-400 animate-spin" />
                <div className="absolute inset-0 bg-cyan-400/20 rounded-full animate-pulse"></div>
              </div>
              <div className="text-center">
                <h3 className="text-2xl font-extrabold text-white mb-2 tracking-tight drop-shadow-lg">
                  Processing Purchase
                </h3>
                <p className="text-zinc-300 text-lg">
                  Deploying your transaction to the blockchain...
                </p>
                <p className="text-zinc-400 text-sm mt-2">
                  This may take a few moments
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}