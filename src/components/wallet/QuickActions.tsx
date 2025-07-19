import React from "react";
import { FaArrowUp } from "react-icons/fa";
import { ArrowUpRight } from "lucide-react";

interface QuickActionsProps {
  onSendUSDC: () => void;
  onBuyCrypto: () => void;
}

const QuickActions: React.FC<QuickActionsProps> = ({ onSendUSDC, onBuyCrypto }) => {
  return (
    <div className="flex flex-row gap-4 w-full">
      <button
        onClick={onSendUSDC}
        className="flex-1 bg-gradient-to-r from-blue-600 to-purple-700 hover:from-blue-700 hover:to-purple-800 text-white py-6 px-8 rounded-3xl font-semibold transition-all duration-300 shadow-lg hover:shadow-xl transform hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center text-lg"
      >
        <FaArrowUp className="mr-3" />
        Pay
      </button>
      <button
        onClick={onBuyCrypto}
        className="flex-1 bg-gradient-to-r from-green-600 to-emerald-700 hover:from-green-700 hover:to-emerald-800 text-white py-6 px-8 rounded-3xl font-semibold transition-all duration-300 shadow-lg hover:shadow-xl transform hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center text-lg"
      >
        <ArrowUpRight className="mr-3 h-6 w-6" />
        Buy
      </button>
    </div>
  );
};

export default QuickActions; 