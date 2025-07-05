import React from "react";
import { FaArrowUp } from "react-icons/fa";
import { ArrowUpRight } from "lucide-react";

interface QuickActionsProps {
  setShowSendForm: (show: boolean) => void;
  payLabel?: string;
}

const QuickActions: React.FC<QuickActionsProps> = ({ setShowSendForm, payLabel = "Pay" }) => {
  return (
    <div className="flex flex-row gap-4 mb-8 w-full">
      <button
        onClick={() => setShowSendForm(true)}
        className="flex-1 bg-gradient-to-r from-blue-600 to-purple-700 hover:from-blue-700 hover:to-purple-800 text-white py-6 px-8 rounded-3xl font-semibold transition-all duration-300 shadow-lg hover:shadow-xl transform hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center text-lg"
      >
        <FaArrowUp className="mr-3" />
        {payLabel}
      </button>
      <button
        disabled
        className="flex-1 bg-zinc-800 text-zinc-400 py-6 px-8 rounded-3xl font-semibold transition-all duration-300 shadow-lg opacity-60 cursor-not-allowed flex items-center justify-center text-lg"
      >
        <ArrowUpRight className="mr-3 h-6 w-6 text-green-400" />
        Grow
      </button>
    </div>
  );
};

export default QuickActions; 