import React, { memo } from "react";
import { useRouter } from "next/navigation";
import { SlidersHorizontal } from "lucide-react";

interface WalletHeaderProps {
  accountData: any;
  onLogout: () => void;
  onMenuToggle: () => void;
  onOpenQuestionnaire?: () => void;
  backRoute?: string;
  onBackClick?: () => void;
}

const WalletHeader: React.FC<WalletHeaderProps> = memo(({
  accountData,
  onLogout,
  onMenuToggle,
  onOpenQuestionnaire,
  backRoute,
  onBackClick
}) => {
  const router = useRouter();
  const handleBack = onBackClick ?? (backRoute ? () => router.push(backRoute) : undefined);
  return (
    // <header className="bg-gradient-to-br from-black via-zinc-900 to-neutral-900/90 backdrop-blur-xl sticky top-0 z-5">
    <header>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center py-0 min-h-[6rem]">
          <div className="flex items-center gap-3">
            {handleBack && (
              <button
                onClick={handleBack}
                className="hover:opacity-70 transition-opacity duration-200"
                aria-label="Go back"
              >
                <img
                  src="/hedge_fund/Back icon.svg"
                  alt=""
                  className="h-8 w-8"
                />
              </button>
            )}
            <img
              src="/Krypton logo.svg"
              alt="Krypton Logo"
              className="h-10 w-auto drop-shadow-[0_2px_8px_rgba(16,255,180,0.18)]"
            />
          </div>
          <div className="flex items-center space-x-3">
            {onOpenQuestionnaire && (
              <button
                onClick={onOpenQuestionnaire}
                className="hidden sm:flex bg-zinc-800/60 hover:bg-zinc-700/80 text-zinc-300 hover:text-white px-4 sm:px-6 py-2 rounded-xl border border-zinc-700/50 hover:border-zinc-600/50 transition-all duration-200 text-xs sm:text-sm justify-center items-center"
              >
                <SlidersHorizontal className="h-4 w-4 mr-2" />
              </button>
            )}
            <div className="relative hamburger-menu">
              <button
                onClick={onMenuToggle}
                className="flex items-center text-white px-4 py-2 rounded-xl transition-colors font-medium"
                aria-label="Open menu"
              >
                <img
                  src="/Burger.svg"
                  alt="Burger"
                  className="h-6 w-auto drop-shadow-[0_2px_8px_rgba(16,255,180,0.18)]"
                />
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
});

WalletHeader.displayName = 'WalletHeader';

export default WalletHeader; 