"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { Rocket, HeartPulse, Cpu, Leaf } from "lucide-react";

const categories = [
  {
    name: "Fintech",
    icon: <Rocket className="h-10 w-10 text-cyan-300 group-hover:text-cyan-400 transition-all" />,
    description: "Innovative startups in payments, lending, and digital banking."
  },
  {
    name: "HealthTech",
    icon: <HeartPulse className="h-10 w-10 text-pink-300 group-hover:text-pink-400 transition-all" />,
    description: "Startups transforming healthcare and wellness."
  },
  {
    name: "AI & Data",
    icon: <Cpu className="h-10 w-10 text-purple-300 group-hover:text-purple-400 transition-all" />,
    description: "Cutting-edge companies in artificial intelligence and analytics."
  },
  {
    name: "Sustainability",
    icon: <Leaf className="h-10 w-10 text-green-300 group-hover:text-green-400 transition-all" />,
    description: "Green tech and eco-friendly innovation startups."
  }
];

export default function MarketplaceCategoriesPage() {
  const router = useRouter();
  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center bg-gradient-to-br from-black via-zinc-900 to-neutral-900 p-8">
      <h1 className="text-4xl sm:text-5xl font-extrabold text-white mb-4 text-center drop-shadow-lg">
        Private Marketplace
      </h1>
      <p className="text-zinc-400 text-lg mb-12 text-center max-w-xl">
        Choose a startup category to explore investment opportunities.
      </p>
      <div className="grid grid-cols-2 grid-rows-2 gap-8 w-full max-w-3xl">
        {categories.map((cat) => (
          <button
            key={cat.name}
            className="bg-white/10 border border-white/20 rounded-3xl p-8 flex flex-col items-center justify-center shadow-xl hover:bg-cyan-400/10 hover:border-cyan-400/40 transition-all duration-200 backdrop-blur-xl group focus:outline-none focus:ring-2 focus:ring-cyan-400"
            style={{ WebkitBackdropFilter: 'blur(24px)', backdropFilter: 'blur(24px)' }}
            onClick={() => router.push(`/customer/grow/marketplace/${cat.name.toLowerCase().replace(/[^a-z0-9]/g, '-')}`)}
          >
            <div className="w-16 h-16 rounded-full bg-cyan-400/20 flex items-center justify-center mb-6 group-hover:bg-cyan-400/30 transition-all">
              {cat.icon}
            </div>
            <span className="text-2xl font-bold text-white mb-2">{cat.name}</span>
            <span className="text-zinc-400 text-base text-center">
              {cat.description}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
} 