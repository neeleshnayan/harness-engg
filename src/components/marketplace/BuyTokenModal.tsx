"use client";

import React, { useState, useEffect } from "react";
import { X, DollarSign, Calculator, Target } from "lucide-react";
import { MarketplaceItem } from "@/lib/marketplace";
import api from "@/lib/api";

interface BuyTokenModalProps {
  startup: MarketplaceItem | null;
  isOpen: boolean;
  onClose: () => void;
  onBuy: (startupId: string, tokenCount: number, sellTarget: number) => void;
}

export default function BuyTokenModal({ startup, isOpen, onClose, onBuy }: BuyTokenModalProps) {
  const [tokenCount, setTokenCount] = useState<string>("");
  const [sellTarget, setSellTarget] = useState<string>("");
  const [tokenQuote, setTokenQuote] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && startup) {
      // Reset form when modal opens
      setTokenCount("");
      setSellTarget("");
      setTokenQuote("");
      setError(null);
      // Fetch token quote when modal opens
      fetchTokenQuote();
    }
  }, [isOpen, startup]);

  const fetchTokenQuote = async () => {
    if (!startup) return;

    setQuoteLoading(true);
    try {
      const response = await api.get('/api/v1/smarttoken/price/' + startup.address);
      setTokenQuote(response.data.current_price);
    } catch (err) {
      console.error('Failed to fetch token quote:', err);
      setTokenQuote("Quote unavailable");
    } finally {
      setQuoteLoading(false);
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
    setError(null);
    onClose();
  };

  const calculateTotalCost = () => {
    if (!tokenCount || !startup) return "0";
    const count = parseFloat(tokenCount);
    if (isNaN(count)) return "0";
    return (count * parseFloat(tokenQuote.replace(/[$,]/g, ''))).toFixed(2);
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
              className="w-full bg-white/5 border border-white/20 rounded-xl px-4 py-3 text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400 focus:border-transparent"
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
          <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 flex items-center justify-between">
            <span className="text-zinc-400 text-sm">Estimated Quote</span>
            <span className="text-cyan-400 font-semibold">
              {quoteLoading ? (
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-cyan-400 border-t-transparent"></div>
              ) : (
                tokenQuote || "Loading..."
              )}
            </span>
          </div>
        </div>

        {/* Total Cost */}
        {tokenCount && (
          <div className="mb-4">
            <div className="bg-gradient-to-r from-cyan-400/10 to-purple-400/10 border border-cyan-400/20 rounded-xl px-4 py-3 flex items-center justify-between">
              <span className="text-white text-sm font-medium">Total Cost</span>
              <span className="text-cyan-400 font-bold text-lg">${calculateTotalCost()}</span>
            </div>
          </div>
        )}

        {/* Sell Target */}
        <div className="mb-6">
          <label className="block text-white text-sm font-medium mb-2">
            Sell Target
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
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-current border-t-transparent"></div>
                Processing...
              </>
            ) : (
              <>
                <DollarSign className="h-5 w-5" />
                Buy Tokens
              </>
            )}
          </button>
          <button
            onClick={handleClose}
            className="px-6 py-3 border border-white/20 text-white hover:bg-white/10 rounded-xl transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}