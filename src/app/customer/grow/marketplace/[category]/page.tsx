"use client";

import React from "react";
import { useParams } from "next/navigation";

const startupData: Record<string, { name: string; description: string }[]> = {
  fintech: [
    { name: "PayFlow", description: "Instant cross-border payments for businesses and individuals." },
    { name: "Lendly", description: "Peer-to-peer lending platform with AI-powered risk assessment." },
    { name: "NeoBankX", description: "A digital-only bank for the next generation of savers." },
    { name: "BlockPay", description: "Blockchain-based payment gateway for global merchants." },
  ],
  "healthtech": [
    { name: "MediSync", description: "Telemedicine platform connecting patients to top doctors worldwide." },
    { name: "WellNest", description: "Personalized wellness plans powered by genomics and AI." },
    { name: "CareBotics", description: "Robotic assistants for elderly and in-home care." },
    { name: "PulseTrack", description: "Wearable health monitoring for chronic conditions." },
  ],
  "ai-data": [
    { name: "VisionaryAI", description: "Computer vision solutions for retail and logistics." },
    { name: "DataPulse", description: "Real-time analytics for small businesses made easy." },
    { name: "SynthMind", description: "Synthetic data generation for privacy-first machine learning." },
    { name: "LangGen", description: "AI-powered language generation for business automation." },
  ],
  sustainability: [
    { name: "EcoGrid", description: "Smart energy grids for sustainable cities." },
    { name: "GreenLoop", description: "Circular economy platform for recycling and reuse." },
    { name: "AgroNext", description: "Precision agriculture for water and resource conservation." },
    { name: "AquaSave", description: "Water-saving IoT solutions for urban environments." },
  ],
};

function getCategoryTitle(slug: string) {
  switch (slug) {
    case "fintech": return "Fintech";
    case "healthtech": return "HealthTech";
    case "ai-data": return "AI & Data";
    case "sustainability": return "Sustainability";
    default: return "Startups";
  }
}

export default function MarketplaceCategoryPage() {
  const params = useParams();
  const rawSlug = params.category;
  const slug = typeof rawSlug === 'string' ? rawSlug : Array.isArray(rawSlug) && rawSlug.length > 0 ? rawSlug[0] : '';
  const startups = slug ? startupData[slug] || [] : [];
  const title = getCategoryTitle(slug);

  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center bg-gradient-to-br from-black via-zinc-900 to-neutral-900 p-8">
      <h1 className="text-4xl sm:text-5xl font-extrabold text-white mb-4 text-center drop-shadow-lg">
        {title} Startups
      </h1>
      <p className="text-zinc-400 text-lg mb-12 text-center max-w-xl">
        Explore promising startups in the {title} sector.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 w-full max-w-3xl">
        {startups.map((startup: { name: string; description: string }) => (
          <div
            key={startup.name}
            className="bg-white/10 border border-white/20 rounded-3xl p-8 flex flex-col items-start shadow-xl hover:bg-cyan-400/10 hover:border-cyan-400/40 transition-all duration-200 backdrop-blur-xl group"
            style={{ WebkitBackdropFilter: 'blur(24px)', backdropFilter: 'blur(24px)' }}
          >
            <span className="text-xl font-bold text-white mb-2">{startup.name}</span>
            <span className="text-zinc-400 text-base">
              {startup.description}
            </span>
          </div>
        ))}
        {startups.length === 0 && (
          <div className="text-zinc-400 text-center col-span-2">No startups found for this category.</div>
        )}
      </div>
    </div>
  );
} 