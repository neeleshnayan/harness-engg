import React from "react";
import { FaTimes, FaSignOutAlt, FaCopy } from "react-icons/fa";
import { ArrowUpRight } from "lucide-react";
import { useRouter } from "next/navigation";

interface HamburgerMenuProps {
  visible: boolean;
  onClose: () => void;
  onLogout: () => void;
  accountData: any;
  onCopyAddress: () => void;
  onOpenQuestionnaire?: () => void;
}

const HamburgerMenu: React.FC<HamburgerMenuProps> = ({
  visible,
  onClose,
  onLogout,
  accountData,
  onCopyAddress,
  onOpenQuestionnaire
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

  const handleOpenQuestionnaire = (e: React.MouseEvent) => {
    e.stopPropagation();
    onClose();
    onOpenQuestionnaire?.();
  };

  const neutralGlass =
    "rounded-2xl bg-gradient-to-br from-white/[0.06] to-white/[0.02] backdrop-blur-xl transition-all duration-200";
  const iconPill =
    "inline-flex items-center justify-center w-10 h-10 rounded-xl text-teal-400/90 flex-shrink-0";
  const iconPillStyle = {
    background: "rgba(45, 212, 191, 0.08)",
    boxShadow: "inset 0 1px 0 rgba(255, 255, 255, 0.1)",
  };

  return (
    <div
      className="fixed inset-0 z-50 backdrop-blur-xl"
      style={{ background: "rgba(0, 0, 0, 0.5)" }}
      onClick={handleBackdropClick}
    >
      <div className="flex flex-col items-center justify-center min-h-screen p-6">
        <div
          className="w-full max-w-md rounded-[28px] p-8 bg-[hsl(var(--brand-bg))]/70 backdrop-blur-xl"
          style={{ boxShadow: "0 24px 48px -12px rgba(0, 0, 0, 0.5)" }}
          onClick={handleModalClick}
        >
          {/* Header - Apple-style minimal title */}
          <div className="text-center mb-10">
            <h2 className="text-xl font-semibold tracking-tight text-[hsl(var(--brand-accent))]">
              Menu
            </h2>
          </div>

          {/* Wallet Address - matches token portfolio glass */}
          <div className="mb-6">
            <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3 text-center">
              Wallet Address
            </p>
            <div className={`rounded-2xl p-5 ${neutralGlass}`}>
              <div className="flex items-center justify-between gap-3">
                <p className="font-mono text-sm text-white/90 break-all flex-1 min-w-0">
                  {accountData?.wallet_address}
                </p>
                <button
                  onClick={handleCopyClick}
                  className={`${iconPill} hover:bg-teal-500/15 active:scale-[0.97] transition-transform`}
                  style={iconPillStyle}
                >
                  <FaCopy className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>

          {/* Navigation - unified glass list */}
          <div className="space-y-3 mb-6">
            {onOpenQuestionnaire && (
              <button
                onClick={handleOpenQuestionnaire}
                className={`flex items-center justify-center w-full text-white/90 hover:text-white px-6 py-4 rounded-2xl font-medium text-[15px] ${neutralGlass} active:scale-[0.99]`}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="mr-3 flex-shrink-0 opacity-80"
                >
                  <line x1="4" y1="6" x2="20" y2="6" />
                  <line x1="4" y1="12" x2="20" y2="12" />
                  <line x1="4" y1="18" x2="20" y2="18" />
                </svg>
                Hedge Fund Questionnaire
              </button>
            )}
            <button
              onClick={handleNavigateToClark}
              className={`flex items-center justify-between w-full text-white/90 hover:text-white px-6 py-4 rounded-2xl font-medium text-[15px] ${neutralGlass} active:scale-[0.99]`}
            >
              <div className="flex items-center flex-1 justify-center min-w-0 mr-3">
                <img
                  src="/Krypton Clark.svg"
                  alt="Clark"
                  className="h-12 w-12 mr-3 flex-shrink-0"
                />
                <span>Clark AI</span>
              </div>
              <span className={iconPill} style={iconPillStyle}>
                <ArrowUpRight className="h-5 w-5" />
              </span>
            </button>
          </div>

          {/* Sign Out */}
          <div className="mb-8">
            <button
              onClick={handleSignOutClick}
              className="flex items-center justify-center w-full px-6 py-4 rounded-2xl font-medium text-[15px] border border-[#604038] text-[#ED7771] hover:text-[#F08A84] hover:border-[#6B4A42] active:scale-[0.99] transition-all duration-200"
              style={{ background: "rgba(239, 68, 68, 0.06)" }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "rgba(239, 68, 68, 0.12)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "rgba(239, 68, 68, 0.06)")
              }
            >
              <FaSignOutAlt className="mr-3 h-[18px] w-[18px]" />
              Sign Out
            </button>
          </div>

          {/* Close - minimal Apple-style control */}
          <div className="flex justify-center">
            <button
              onClick={onClose}
              className="flex items-center justify-center h-10 w-10 rounded-full text-zinc-500 hover:text-white/90 transition-all duration-200 hover:bg-white/[0.06] active:scale-95"
              aria-label="Close menu"
            >
              <FaTimes className="text-lg" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HamburgerMenu;