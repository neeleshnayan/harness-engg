"use client";

import React from "react";
import { X, ExternalLink, DollarSign, Tag, Globe, Linkedin, Youtube, Twitter } from "lucide-react";
import { MarketplaceItem } from "@/lib/marketplace";

interface StartupDetailModalProps {
  startup: MarketplaceItem | null;
  isOpen: boolean;
  onClose: () => void;
  onBuy: (startupId: string) => void;
}

export default function StartupDetailModal({ startup, isOpen, onClose, onBuy }: StartupDetailModalProps) {
  if (!isOpen || !startup) return null;

  const handleBuyClick = () => {
    onBuy(startup.id);
  };

  const openSocialLink = (url: string) => {
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white/10 border border-white/20 rounded-3xl p-8 max-w-2xl w-full max-h-[90vh] overflow-y-auto backdrop-blur-xl">
        {/* Header */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-3xl font-bold text-white mb-2">{startup.name}</h2>
            <div className="flex items-center gap-2 text-zinc-400">
              <Tag className="h-4 w-4" />
              <span className="text-sm">{startup.category}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-white transition-colors p-2 hover:bg-white/10 rounded-full"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* Description */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold text-white mb-3">About</h3>
          <p className="text-zinc-300 leading-relaxed">{startup.description}</p>
        </div>

        {/* Token Information */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold text-white mb-3">Token Information</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <div className="flex items-center gap-2 text-zinc-400 mb-1">
                <Tag className="h-4 w-4" />
                <span className="text-sm">Token Name</span>
              </div>
              <p className="text-white font-semibold">
                {startup.token_name || "Not specified"}
              </p>
            </div>
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <div className="flex items-center gap-2 text-zinc-400 mb-1">
                <DollarSign className="h-4 w-4" />
                <span className="text-sm">Token Price</span>
              </div>
              <p className="text-green-400 font-semibold">
                ${startup.price.toLocaleString()}
              </p>
            </div>
          </div>
          <div className="mt-4 bg-white/5 border border-white/10 rounded-xl p-4">
            <div className="flex items-center gap-2 text-zinc-400 mb-1">
              <Globe className="h-4 w-4" />
              <span className="text-sm">Minting Status</span>
            </div>
            <p className={`font-semibold ${startup.is_minting_active ? 'text-green-400' : 'text-red-400'}`}>
              {startup.is_minting_active ? "Active" : "Inactive"}
            </p>
          </div>
        </div>

        {/* Social Media Links */}
        {(startup.linkedin || startup.youtube || startup.x) && (
          <div className="mb-8">
            <h3 className="text-lg font-semibold text-white mb-3">Social Media</h3>
            <div className="flex gap-3">
              {startup.linkedin && (
                <button
                  onClick={() => openSocialLink(startup.linkedin!)}
                  className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  <Linkedin className="h-4 w-4" />
                  <span>LinkedIn</span>
                  <ExternalLink className="h-3 w-3" />
                </button>
              )}
              {startup.youtube && (
                <button
                  onClick={() => openSocialLink(startup.youtube!)}
                  className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  <Youtube className="h-4 w-4" />
                  <span>YouTube</span>
                  <ExternalLink className="h-3 w-3" />
                </button>
              )}
              {startup.x && (
                <button
                  onClick={() => openSocialLink(startup.x!)}
                  className="flex items-center gap-2 bg-black hover:bg-gray-800 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  <Twitter className="h-4 w-4" />
                  <span>X (Twitter)</span>
                  <ExternalLink className="h-3 w-3" />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Buy Button */}
        <div className="flex gap-4">
          <button
            onClick={handleBuyClick}
            disabled={!startup.is_minting_active}
            className={`flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-semibold transition-all ${
              startup.is_minting_active
                ? 'bg-cyan-400 hover:bg-cyan-300 text-black'
                : 'bg-gray-600 text-gray-400 cursor-not-allowed'
            }`}
          >
            <DollarSign className="h-5 w-5" />
            {startup.is_minting_active ? 'Buy Tokens' : 'Minting Inactive'}
          </button>
          <button
            onClick={onClose}
            className="px-6 py-3 border border-white/20 text-white hover:bg-white/10 rounded-xl transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
} 