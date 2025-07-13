import React from "react";
import { FaBars } from "react-icons/fa";

interface WalletHeaderProps {
  showMenu: boolean;
  setShowMenu: (show: boolean) => void;
  onBuyCrypto?: () => void;
}

const WalletHeader: React.FC<WalletHeaderProps> = ({ showMenu, setShowMenu, onBuyCrypto }) => {
  return (
    <header className="bg-gradient-to-br from-black via-zinc-900 to-neutral-900/90 backdrop-blur-xl sticky top-0 z-50">
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
            {onBuyCrypto && (
              <button
                onClick={onBuyCrypto}
                className="flex items-center bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-xl transition-colors font-medium mr-2"
              >
                Buy Crypto
              </button>
            )}
            <div className="relative hamburger-menu">
              <button
                onClick={() => setShowMenu(!showMenu)}
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