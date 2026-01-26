"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Loader2, DollarSign, Flame } from "lucide-react";
import { MarketplaceService, MarketplaceItem } from "@/lib/marketplace";
import StartupDetailModal from "@/components/marketplace/StartupDetailModal";
import api, { getUserInfo } from "@/lib/api";
import ReactCountryFlag from "react-country-flag";
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faFire } from '@fortawesome/free-solid-svg-icons';

const countryCodes = ["US", "GB", "DE", "IN", "FR", "JP", "CN", "BR", "AU", "ZA"];
const fireList = [0, 1, 3, 5, 6]

function getRandomCountryCode() {
  return countryCodes[Math.floor(Math.random() * countryCodes.length)];
}

function getCategoryTitle(slug: string) {
  // Convert slug back to category name
  const categoryMap: Record<string, string> = {
    "fintech": "Fintech",
    "healthtech": "Healthtech",
    "ai-data": "AI & Data",
    "sustainability": "Sustainability"
  };
  return categoryMap[slug] || slug.charAt(0).toUpperCase() + slug.slice(1).replace(/-/g, ' ');
}

export default function MarketplaceCategoryPage() {
  const params = useParams();
  const rawSlug = params.category;
  const slug = typeof rawSlug === 'string' ? rawSlug : Array.isArray(rawSlug) && rawSlug.length > 0 ? rawSlug[0] : '';
  const title = getCategoryTitle(slug);

  const [startups, setStartups] = useState<MarketplaceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStartup, setSelectedStartup] = useState<MarketplaceItem | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    const fetchStartups = async () => {
      if (!slug) return;

      try {
        setLoading(true);
        // Convert slug back to category name for API call
        const categoryMap: Record<string, string> = {
          "fintech": "Fintech",
          "healthtech": "Healthtech",
          "ai-data": "AI & Data",
          "sustainability": "Sustainability"
        };
        const categoryName = categoryMap[slug] || slug;
        const startupsData = await MarketplaceService.getMarketplaceItemsByCategory(categoryName);
        setStartups(startupsData);
      } catch (err) {
        console.error('Failed to fetch startups:', err);
        setError('Failed to load startups. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchStartups();
  }, [slug]);

  const handleStartupClick = (startup: MarketplaceItem) => {
    setSelectedStartup(startup);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setSelectedStartup(null);
  };

  const handleBuyStartup = async (startupId: string, tokenCount: number, sellTarget: number) => {
    // Token minting via mint_exchange_usdc is temporarily disabled during backend migration
    // See SMARTTOKEN_MIGRATION.md for details
    alert('Token minting is coming soon! This feature is currently being upgraded.');
    throw new Error('Feature coming soon');
  };

  if (loading) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#001C1B] p-8">
        <Loader2 className="h-12 w-12 text-cyan-400 animate-spin mb-4" />
        <p className="text-zinc-400 text-lg">Loading {title} startups...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#001C1B] p-8">
        <p className="text-red-400 text-lg mb-4">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-6 py-3 bg-cyan-400 text-black rounded-lg hover:bg-cyan-300 transition-colors"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#001C1B] p-8">
      <h1 className="text-4xl sm:text-5xl font-extrabold text-white mb-4 text-center drop-shadow-lg">
        {title} Startups
      </h1>
      <p className="text-zinc-400 text-lg mb-12 text-center max-w-xl">
        Explore promising startups in the {title} sector.
      </p>
      <div className="w-full max-w-3xl mt-4 mb-12">
        <div className="flex items-center bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-zinc-400 backdrop-blur-lg shadow-lg">
          <span className="mr-3 text-white font-medium">GenAI Assistant:</span>
          <input
            type="text"
            disabled
            placeholder="Ask the assistant to find startups based on your use-case..."
            className="flex-grow bg-transparent text-zinc-400 placeholder-zinc-500 outline-none"
          />
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 w-full max-w-3xl">
        {startups.map((startup, idx) => (
          <button
            key={startup.id}
            onClick={() => handleStartupClick(startup)}
            className="bg-white/10 border border-white/20 rounded-3xl p-8 flex flex-col items-start shadow-xl hover:bg-cyan-400/10 hover:border-cyan-400/40 transition-all duration-200 backdrop-blur-xl group text-left focus:outline-none focus:ring-2 focus:ring-cyan-400"
            style={{ WebkitBackdropFilter: 'blur(24px)', backdropFilter: 'blur(24px)' }}
          >
            <div className="flex justify-between items-start w-full mb-2">
              <span className="text-xl font-bold text-white group-hover:text-cyan-300 transition-colors">{startup.name}
              <span className={`text-sm font-semibold ${startup.is_minting_active ? 'text-green-400' : 'text-red-400'}`}>
                &nbsp;&nbsp;{startup.is_minting_active ? "Minting Active" : "Minting Inactive"}
              </span>
              </span>
              <div className="flex items-center text-green-400 font-semibold">
                <DollarSign className="h-4 w-4 mr-1" />
                {startup.price.toLocaleString()}
              </div>
            </div>
             <span className="mb-2 flex">
              <ReactCountryFlag
                countryCode={startup?.countryCode? startup.countryCode : getRandomCountryCode()}
                svg
                style={{
                  width: "1.5em",
                  height: "1.5em"
                }}
                title={getRandomCountryCode()}
              />
              {
                (fireList.includes(idx) || startup.name.toLowerCase().includes("krypton")) &&
                // <span className="flex items-center text-red-400 font-semibold">
                //   &nbsp;&nbsp;<Flame className="h-4 w-4 mr-1" />
                // </span>
                <span className="flex items-center text-red-400 font-semibold">
                  &nbsp;&nbsp;<FontAwesomeIcon icon={faFire} className="h-4 w-4 mr-1" />
                </span>
              }
            </span>
            <span className="text-zinc-400 text-base group-hover:text-zinc-300 transition-colors">
              {startup.description}
            </span>
            <div className="mt-4 w-full">
              <div className="text-sm text-zinc-500 group-hover:text-zinc-400 transition-colors">
                Click to view details
              </div>
            </div>
          </button>
        ))}
        {startups.length === 0 && (
          <div className="text-zinc-400 text-center col-span-2">No startups found for this category.</div>
        )}
      </div>

      {/* Startup Detail Modal */}
      <StartupDetailModal
        startup={selectedStartup}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        onBuy={handleBuyStartup}
      />
    </div>
  );
}