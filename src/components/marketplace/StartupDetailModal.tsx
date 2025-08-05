"use client";

import React, { useState } from "react";
import { X, ExternalLink, DollarSign, Tag, Globe, Linkedin, Youtube, Twitter, Play } from "lucide-react";
import { MarketplaceItem } from "@/lib/marketplace";
import BuyTokenModal from "./BuyTokenModal";

interface StartupDetailModalProps {
  startup: MarketplaceItem | null;
  isOpen: boolean;
  onClose: () => void;
  onBuy: (startupId: string, tokenCount: number, sellTarget: number) => void;
}

export default function StartupDetailModal({ startup, isOpen, onClose, onBuy }: StartupDetailModalProps) {
  const [showBuyModal, setShowBuyModal] = useState(false);

  if (!isOpen || !startup) return null;

  const handleBuyClick = () => {
    setShowBuyModal(true);
  };

  const handleBuyModalClose = () => {
    setShowBuyModal(false);
  };

  const handleBuyTokens = async (startupId: string, tokenCount: number, sellTarget: number) => {
    await onBuy(startupId, tokenCount, sellTarget);
  };

  const openSocialLink = (url: string) => {
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  };

  // Function to extract YouTube video ID from URL
  const getYouTubeVideoId = (url: string): string | null => {
    if (!url) return null;
    
    // More comprehensive regex pattern for YouTube URLs
    const patterns = [
      /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/|youtube\.com\/watch\?.*&v=)([^#&?]*)/,
      /youtube\.com\/watch\?.*v=([^#&?]*)/
    ];
    
    for (const pattern of patterns) {
      const match = url.match(pattern);
      if (match && match[1] && match[1].length === 11) {
        return match[1];
      }
    }
    
    return null;
  };

  const pitchVideoId = startup.pitch_video ? getYouTubeVideoId(startup.pitch_video) : null;

  return (
    <>
      <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
        <div className="bg-white/10 border border-white/20 rounded-3xl p-8 max-w-4xl w-full max-h-[90vh] overflow-y-auto backdrop-blur-xl">
          {/* Header */}
          <div className="flex justify-between items-start mb-6">
            <div>
              <h2 className="text-3xl font-bold text-white mb-2">{startup.name}</h2>
              <div className="flex items-center gap-2 text-zinc-400">
                <Tag className="h-4 w-4" />
                <span className="text-sm">{startup.category}</span>
                <span className="text-sm">•</span>
                <span className={`text-sm font-semibold ${startup.is_minting_active ? 'text-green-400' : 'text-red-400'}`}>
                  {startup.is_minting_active ? "Minting Active" : "Minting Inactive"}
                </span>
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

          {/* Pitch Video Section */}
          {pitchVideoId && (
            <div className="mb-8">
              <h3 className="text-lg font-semibold text-white mb-3">Pitch Video</h3>
              <div className="relative w-full h-0 pb-[56.25%] rounded-xl overflow-hidden">
                <iframe
                  src={`https://www.youtube.com/embed/${pitchVideoId}`}
                  title={`${startup.name} Pitch Video`}
                  className="absolute top-0 left-0 w-full h-full rounded-xl"
                  frameBorder="0"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                ></iframe>
              </div>
            </div>
          )}
          
          {/* Debug: Show pitch video info even if ID extraction fails */}
          {startup.pitch_video && !pitchVideoId && (
            <div className="mb-8">
              <h3 className="text-lg font-semibold text-white mb-3">Pitch Video</h3>
              <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
                <p className="text-red-400 text-sm">
                  Video URL detected but could not extract video ID: {startup.pitch_video}
                </p>
                <a 
                  href={startup.pitch_video} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-cyan-400 hover:text-cyan-300 underline mt-2 inline-block"
                >
                  Open Video in New Tab
                </a>
              </div>
            </div>
          )}

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
          </div>

          {/* Social Media Links */}
          <div className="mb-8">
            <h3 className="text-lg font-semibold text-white mb-3">Social Media</h3>
            <div className="flex gap-3">
              <button
                onClick={() => startup.linkedin ? openSocialLink(startup.linkedin) : null}
                disabled={!startup.linkedin}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                  startup.linkedin
                    ? 'bg-blue-600 hover:bg-blue-700 text-white cursor-pointer'
                    : 'bg-gray-600 text-gray-400 cursor-not-allowed opacity-50'
                }`}
              >
                <Linkedin className="h-4 w-4" />
                {/* <span>LinkedIn</span> */}
                {startup.linkedin && <ExternalLink className="h-3 w-3" />}
              </button>
              <button
                onClick={() => startup.youtube ? openSocialLink(startup.youtube) : null}
                disabled={!startup.youtube}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                  startup.youtube
                    ? 'bg-red-600 hover:bg-red-700 text-white cursor-pointer'
                    : 'bg-gray-600 text-gray-400 cursor-not-allowed opacity-50'
                }`}
              >
                <Youtube className="h-4 w-4" />
                {/* <span>YouTube</span> */}
                {startup.youtube && <ExternalLink className="h-3 w-3" />}
              </button>
              <button
                onClick={() => startup.x ? openSocialLink(startup.x) : null}
                disabled={!startup.x}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                  startup.x
                    ? 'bg-black hover:bg-gray-800 text-white cursor-pointer'
                    : 'bg-gray-600 text-gray-400 cursor-not-allowed opacity-50'
                }`}
              >
                <Twitter className="h-4 w-4" />
                {/* <span>X (Twitter)</span> */}
                {startup.x && <ExternalLink className="h-3 w-3" />}
              </button>
            </div>
          </div>

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

      {/* Buy Token Modal */}
      <BuyTokenModal
        startup={startup}
        isOpen={showBuyModal}
        onClose={handleBuyModalClose}
        onBuy={handleBuyTokens}
      />
    </>
  );
} 