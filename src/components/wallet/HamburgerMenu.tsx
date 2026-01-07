import React from "react";
import { FaTimes, FaSignOutAlt, FaCopy } from "react-icons/fa";
import { useRouter } from "next/navigation";

interface HamburgerMenuProps {
  visible: boolean;
  onClose: () => void;
  onLogout: () => void;
  accountData: any;
  onCopyAddress: () => void;
}

const HamburgerMenu: React.FC<HamburgerMenuProps> = ({
  visible,
  onClose,
  onLogout,
  accountData,
  onCopyAddress
}) => {
  const router = useRouter();

  if (!visible) return null;

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const handleModalClick = (e: React.MouseEvent) => {
    e.stopPropagation();
  };

  const handleCopyClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onCopyAddress();
  };

  const handleSignOutClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onLogout();
  };

  const handleNavigateToClark = (e: React.MouseEvent) => {
    e.stopPropagation();
    onClose();
    router.push('/clark');
  };

  const handleNavigateToLiquidityPools = (e: React.MouseEvent) => {
    e.stopPropagation();
    onClose();
    router.push('/liquidity-pools');
  };

  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-xl z-50"
      onClick={handleBackdropClick}
    >
      <div className="flex flex-col items-center justify-center min-h-screen p-6">
        <div
          className="w-full max-w-md bg-black/60 border border-white/10 rounded-3xl shadow-2xl backdrop-blur-xl p-8"
          onClick={handleModalClick}
        >
          {/* Header */}
          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold text-white mb-2">Menu</h2>
            <div className="w-16 h-1 bg-gradient-to-r from-cyan-400 to-green-400 mx-auto rounded-full"></div>
          </div>

          {/* Wallet Address Section */}
          <div className="mb-8">
            <h3 className="text-sm font-medium text-zinc-400 mb-4 text-center">Wallet Address</h3>
            <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-4">
              <div className="flex items-center justify-between">
                <p className="font-mono text-sm text-zinc-200 break-all flex-1 mr-3">
                  {accountData?.wallet_address}
                </p>
                <button
                  onClick={handleCopyClick}
                  className="text-cyan-400 hover:text-cyan-300 transition-colors p-2 rounded-xl hover:bg-cyan-900/30 flex-shrink-0"
                >
                  <FaCopy />
                </button>
              </div>
            </div>
          </div>

          {/* Navigation Section */}
          <div className="mb-8">
            <button
              onClick={handleNavigateToClark}
              className="flex items-center justify-center w-full text-cyan-400 hover:text-cyan-300 hover:bg-cyan-900/20 px-6 py-4 rounded-2xl transition-all duration-200 font-medium border border-cyan-900/30 hover:border-cyan-700/50 mb-4"
            >
              <img src="/clark.svg" alt="Clark" className="h-6 w-6 mr-3" />
              Open Clark AI
            </button>
            <button
              onClick={handleNavigateToLiquidityPools}
              className="flex items-center justify-center w-full text-blue-400 hover:text-blue-300 hover:bg-blue-900/20 px-6 py-4 rounded-2xl transition-all duration-200 font-medium border border-blue-900/30 hover:border-blue-700/50"
            >
              <span className="text-xl mr-3">○</span>
              Liquidity Pools
            </button>
          </div>

          {/* Sign Out Section */}
          <div className="mb-8">
            <button
              onClick={handleSignOutClick}
              className="flex items-center justify-center w-full text-red-400 hover:text-red-300 hover:bg-red-900/20 px-6 py-4 rounded-2xl transition-all duration-200 font-medium border border-red-900/30 hover:border-red-700/50"
            >
              <FaSignOutAlt className="mr-3" />
              Sign Out
            </button>
          </div>

          {/* Close Button */}
          <div className="text-center">
            <button
              onClick={onClose}
              className="text-zinc-400 hover:text-white transition-colors p-3 rounded-2xl hover:bg-white/10"
            >
              <FaTimes className="text-xl" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HamburgerMenu;