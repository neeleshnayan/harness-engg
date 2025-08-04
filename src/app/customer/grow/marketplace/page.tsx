"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Rocket, HeartPulse, Cpu, Leaf, Loader2 } from "lucide-react";
import { MarketplaceService, MarketplaceCategories } from "@/lib/marketplace";

// Icon mapping for categories
const getCategoryIcon = (categoryName: string) => {
  switch (categoryName.toLowerCase()) {
    case "fintech":
      return <Rocket className="h-10 w-10 text-cyan-300 group-hover:text-cyan-400 transition-all" />;
    case "healthtech":
      return <HeartPulse className="h-10 w-10 text-pink-300 group-hover:text-pink-400 transition-all" />;
    case "ai & data":
      return <Cpu className="h-10 w-10 text-purple-300 group-hover:text-purple-400 transition-all" />;
    case "sustainability":
      return <Leaf className="h-10 w-10 text-green-300 group-hover:text-green-400 transition-all" />;
    default:
      return <Rocket className="h-10 w-10 text-gray-300 group-hover:text-gray-400 transition-all" />;
  }
};

// Description mapping for categories
const getCategoryDescription = (categoryName: string) => {
  switch (categoryName.toLowerCase()) {
    case "fintech":
      return "Innovative startups in payments, lending, and digital banking.";
    case "healthtech":
      return "Startups transforming healthcare and wellness.";
    case "ai & data":
      return "Cutting-edge companies in artificial intelligence and analytics.";
    case "sustainability":
      return "Green tech and eco-friendly innovation startups.";
    default:
      return "Explore promising startups in this category.";
  }
};

export default function MarketplaceCategoriesPage() {
  const router = useRouter();
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCategories = async () => {
      try {
        setLoading(true);
        const categoriesData = await MarketplaceService.getCategories();
        setCategories(categoriesData.categories);
      } catch (err) {
        console.error('Failed to fetch categories:', err);
        setError('Failed to load categories. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchCategories();
  }, []);

  const handleCategoryClick = (categoryName: string) => {
    const slug = categoryName.toLowerCase().replace(/[^a-z0-9]/g, '-');
    router.push(`/customer/grow/marketplace/${slug}`);
  };

  if (loading) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-gradient-to-br from-black via-zinc-900 to-neutral-900 p-8">
        <Loader2 className="h-12 w-12 text-cyan-400 animate-spin mb-4" />
        <p className="text-zinc-400 text-lg">Loading marketplace categories...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-gradient-to-br from-black via-zinc-900 to-neutral-900 p-8">
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
    <div className="min-h-screen w-full flex flex-col items-center justify-center bg-gradient-to-br from-black via-zinc-900 to-neutral-900 p-8">
      <h1 className="text-4xl sm:text-5xl font-extrabold text-white mb-4 text-center drop-shadow-lg">
        Sharktank 3.0
      </h1>
      <p className="text-zinc-400 text-lg mb-12 text-center max-w-xl">
        Choose a startup category to explore investment opportunities.
      </p>
      <div className="grid grid-cols-2 grid-rows-2 gap-8 w-full max-w-3xl">
        {categories.map((categoryName) => (
          <button
            key={categoryName}
            className="bg-white/10 border border-white/20 rounded-3xl p-8 flex flex-col items-center justify-center shadow-xl hover:bg-cyan-400/10 hover:border-cyan-400/40 transition-all duration-200 backdrop-blur-xl group focus:outline-none focus:ring-2 focus:ring-cyan-400"
            style={{ WebkitBackdropFilter: 'blur(24px)', backdropFilter: 'blur(24px)' }}
            onClick={() => handleCategoryClick(categoryName)}
          >
            <div className="w-16 h-16 rounded-full bg-cyan-400/20 flex items-center justify-center mb-6 group-hover:bg-cyan-400/30 transition-all">
              {getCategoryIcon(categoryName)}
            </div>
            <span className="text-2xl font-bold text-white mb-2">{categoryName}</span>
            <span className="text-zinc-400 text-base text-center">
              {getCategoryDescription(categoryName)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
} 