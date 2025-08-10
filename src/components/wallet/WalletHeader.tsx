import React from "react";
import { FaBars } from "react-icons/fa";

interface WalletHeaderProps {
  accountData: any;
  onLogout: () => void;
  onMenuToggle: () => void;
}

const WalletHeader: React.FC<WalletHeaderProps> = ({ accountData, onLogout, onMenuToggle }) => {
  return (
    // <header className="bg-gradient-to-br from-black via-zinc-900 to-neutral-900/90 backdrop-blur-xl sticky top-0 z-5">
    <header>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center py-0 min-h-[6rem]">
          <div className="flex items-center">
            <img
              src="/krypton_logo.svg"
              alt="Krypton Logo"
              className="h-24 w-auto drop-shadow-[0_2px_8px_rgba(16,255,180,0.18)]"
            />
          </div>
          <div className="flex items-center space-x-3">
            <div className="relative hamburger-menu">
              <button
                onClick={onMenuToggle}
                className="flex items-center bg-zinc-800 hover:bg-zinc-700 text-white px-4 py-2 rounded-xl transition-colors font-medium"
                aria-label="Open menu"
              >
                <FaBars />
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default WalletHeader; 