import React from 'react';
import { motion } from 'framer-motion';
import { Loader2, CheckCircle, XCircle, Lock, Zap, Flame, DollarSign } from 'lucide-react';

export type BalanceTransactionStage =
  | 'idle'
  | 'approving'
  | 'approved'
  | 'processing'
  | 'confirming'
  | 'success'
  | 'error';

export type BalanceTransactionType = 'deposit' | 'withdraw';

interface BalanceStatusIndicatorProps {
  stage: BalanceTransactionStage;
  type: BalanceTransactionType;
  balance: string;
  showShimmer?: boolean;
  error?: string | null;
  tokenSymbol?: string;
}

export const BalanceStatusIndicator: React.FC<BalanceStatusIndicatorProps> = ({
  stage,
  type,
  balance,
  showShimmer = false,
  error = null,
  tokenSymbol = 'MAVC',
}) => {
  const isDeposit = type === 'deposit';

  // Get stage-specific icon and message
  const getStageDisplay = () => {
    switch (stage) {
      case 'approving':
        return {
          icon: Lock,
          message: 'Approving transaction...',
          color: 'text-blue-400',
          bgColor: 'bg-blue-500/20',
          borderColor: 'border-blue-500/30',
          progress: 25,
        };
      case 'approved':
        return {
          icon: CheckCircle,
          message: 'Approval confirmed',
          color: 'text-green-400',
          bgColor: 'bg-green-500/20',
          borderColor: 'border-green-500/30',
          progress: 40,
        };
      case 'processing':
        return {
          icon: isDeposit ? Zap : Flame,
          message: isDeposit ? `Minting ${tokenSymbol} tokens...` : `Burning ${tokenSymbol} tokens...`,
          color: isDeposit ? 'text-purple-400' : 'text-orange-400',
          bgColor: isDeposit ? 'bg-purple-500/20' : 'bg-orange-500/20',
          borderColor: isDeposit ? 'border-purple-500/30' : 'border-orange-500/30',
          progress: 60,
        };
      case 'confirming':
        return {
          icon: DollarSign,
          message: isDeposit ? 'Depositing USDC...' : 'Receiving USDC...',
          color: 'text-cyan-400',
          bgColor: 'bg-cyan-500/20',
          borderColor: 'border-cyan-500/30',
          progress: 80,
        };
      case 'success':
        return {
          icon: CheckCircle,
          message: 'Success! Balance updated',
          color: 'text-green-400',
          bgColor: 'bg-green-500/20',
          borderColor: 'border-green-500/30',
          progress: 100,
        };
      case 'error':
        return {
          icon: XCircle,
          message: error || 'Transaction failed',
          color: 'text-red-400',
          bgColor: 'bg-red-500/20',
          borderColor: 'border-red-500/30',
          progress: 0,
        };
      default:
        return null;
    }
  };

  const display = getStageDisplay();

  // Don't show anything if idle
  if (stage === 'idle' || !display) {
    return (
      <div className="flex items-center gap-2 bg-purple-500/20 text-purple-300 px-3 py-1 rounded-lg border border-purple-500/30">
        <span className="text-sm font-semibold">{balance} {tokenSymbol}</span>
      </div>
    );
  }

  const Icon = display.icon;
  const isLoading = ['approving', 'processing', 'confirming'].includes(stage);

  return (
    <div className="flex flex-col items-end gap-1">
      {/* Main Balance Badge with Status */}
      <motion.div
        initial={{ scale: 1 }}
        animate={
          stage === 'success'
            ? { scale: [1, 1.1, 1] }
            : stage === 'error'
            ? { x: [-2, 2, -2, 2, 0] }
            : {}
        }
        transition={
          stage === 'success'
            ? { duration: 0.5, ease: 'easeInOut' }
            : stage === 'error'
            ? { duration: 0.4 }
            : {}
        }
        className={`flex items-center gap-2 px-3 py-1 rounded-lg border ${display.bgColor} ${display.borderColor}`}
      >
        {/* Spinning icon for loading states */}
        {isLoading ? (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          >
            <Icon className={`w-4 h-4 ${display.color}`} />
          </motion.div>
        ) : (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 10 }}
          >
            <Icon className={`w-4 h-4 ${display.color}`} />
          </motion.div>
        )}

        {/* Balance with shimmer effect */}
        {showShimmer && isLoading ? (
          <div className="relative">
            <span className="text-sm font-semibold text-transparent bg-clip-text bg-gradient-to-r from-purple-300 via-white to-purple-300 animate-shimmer">
              {balance} {tokenSymbol}
            </span>
          </div>
        ) : (
          <span className={`text-sm font-semibold ${display.color}`}>
            {balance} {tokenSymbol}
          </span>
        )}
      </motion.div>

      {/* Status Message */}
      <motion.div
        initial={{ opacity: 0, y: -5 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -5 }}
        className="flex items-center gap-1"
      >
        <span className={`text-xs ${display.color} font-medium`}>
          {display.message}
          {isLoading && (
            <motion.span
              animate={{ opacity: [0, 1, 0] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            >
              ...
            </motion.span>
          )}
        </span>
      </motion.div>

      {/* Progress Bar */}
      {display.progress > 0 && (
        <div className="w-full h-1 bg-zinc-800/50 rounded-full overflow-hidden">
          <motion.div
            className={`h-full ${display.bgColor.replace('/20', '/60')}`}
            initial={{ width: 0 }}
            animate={{ width: `${display.progress}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          />
        </div>
      )}
    </div>
  );
};

export default BalanceStatusIndicator;
