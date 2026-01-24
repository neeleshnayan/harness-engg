/**
 * Transaction Likelihood Estimation Service
 * Similar to MetaMask's transaction status indicators
 */

export type TransactionLikelihood =
  | 'very_likely'    // >90% chance of success
  | 'likely'         // 70-90% chance
  | 'uncertain'      // 40-70% chance
  | 'unlikely'       // 10-40% chance
  | 'very_unlikely'; // <10% chance

export interface TransactionRiskFactors {
  insufficientBalance: boolean;
  balanceMargin: number; // percentage above required amount
  networkCongestion: 'low' | 'medium' | 'high';
  estimatedGasCost: string;
  hasEnoughForGas: boolean;
  slippageTolerance: number;
  contractReachable: boolean;
  walletConnected: boolean;
}

export interface TransactionLikelihoodResult {
  likelihood: TransactionLikelihood;
  confidence: number; // 0-100
  riskFactors: TransactionRiskFactors;
  warnings: string[];
  estimatedSuccessRate: number; // 0-100
}

/**
 * Estimate the likelihood of a transaction succeeding
 */
export async function estimateTransactionLikelihood(
  params: {
    walletAddress: string;
    tokenAddress: string;
    amount: string;
    type: 'deposit' | 'withdraw';
    currentBalance: string;
    mavcPrice?: string;
  }
): Promise<TransactionLikelihoodResult> {
  const warnings: string[] = [];
  let score = 100; // Start with perfect score, deduct points for issues

  // Parse amounts
  const amountNum = parseFloat(params.amount);
  const balanceNum = parseFloat(params.currentBalance);

  // Check 1: Wallet connected
  const walletConnected = !!params.walletAddress;
  if (!walletConnected) {
    score -= 100;
    warnings.push('Wallet not connected');
  }

  // Check 2: Balance sufficiency
  const insufficientBalance = amountNum > balanceNum;
  const balanceMargin = ((balanceNum - amountNum) / amountNum) * 100;

  if (insufficientBalance) {
    score -= 80;
    warnings.push('Insufficient balance for transaction');
  } else if (balanceMargin < 1) {
    score -= 30;
    warnings.push('Balance is very close to required amount');
  } else if (balanceMargin < 5) {
    score -= 15;
    warnings.push('Low balance margin - consider leaving buffer for gas');
  }

  // Check 3: Amount validation
  if (amountNum <= 0) {
    score -= 50;
    warnings.push('Invalid transaction amount');
  }

  // Check 4: Estimate gas requirements (simplified)
  // In production, you'd call eth_estimateGas
  const estimatedGasCost = '0.002'; // Placeholder - should be dynamic
  const hasEnoughForGas = balanceMargin > 1; // Simplified check

  if (!hasEnoughForGas && params.type === 'withdraw') {
    score -= 20;
    warnings.push('May not have enough ETH for gas fees');
  }

  // Check 5: Network congestion (placeholder - could integrate with gas price APIs)
  // TODO: Implement actual network congestion detection via gas price APIs
  const networkCongestion: 'low' | 'medium' | 'high' = 'low';
  // Note: Currently hardcoded to 'low'. Future enhancement: integrate gas price APIs
  // to dynamically determine network congestion and adjust score accordingly

  // Check 6: Contract reachability (placeholder)
  const contractReachable = true; // Should check RPC connectivity
  if (!contractReachable) {
    score -= 60;
    warnings.push('Unable to reach blockchain network');
  }

  // Check 7: Slippage tolerance (for swaps, less relevant for deposits/withdrawals)
  const slippageTolerance = 0.5; // 0.5%

  // Calculate final likelihood
  const estimatedSuccessRate = Math.max(0, Math.min(100, score));
  const likelihood = calculateLikelihood(estimatedSuccessRate);

  const riskFactors: TransactionRiskFactors = {
    insufficientBalance,
    balanceMargin,
    networkCongestion,
    estimatedGasCost,
    hasEnoughForGas,
    slippageTolerance,
    contractReachable,
    walletConnected,
  };

  return {
    likelihood,
    confidence: estimatedSuccessRate,
    riskFactors,
    warnings,
    estimatedSuccessRate,
  };
}

/**
 * Convert numeric score to likelihood category
 */
function calculateLikelihood(score: number): TransactionLikelihood {
  if (score >= 90) return 'very_likely';
  if (score >= 70) return 'likely';
  if (score >= 40) return 'uncertain';
  if (score >= 10) return 'unlikely';
  return 'very_unlikely';
}

/**
 * Get display properties for likelihood
 */
export function getLikelihoodDisplay(likelihood: TransactionLikelihood) {
  const displays = {
    very_likely: {
      label: 'Ready to proceed',
      color: '#10B981', // green
      icon: '✓',
      emoji: '🟢',
    },
    likely: {
      label: 'Good to go',
      color: '#22C55E', // light green
      icon: '✓',
      emoji: '🟢',
    },
    uncertain: {
      label: 'Check details',
      color: '#F59E0B', // amber
      icon: '⚠',
      emoji: '🟡',
    },
    unlikely: {
      label: 'Review transaction',
      color: '#F97316', // orange
      icon: '⚠',
      emoji: '🟠',
    },
    very_unlikely: {
      label: 'Cannot proceed',
      color: '#EF4444', // red
      icon: '✗',
      emoji: '🔴',
    },
  };

  return displays[likelihood];
}

/**
 * Monitor transaction status during processing
 */
export interface TransactionStatusUpdate {
  stage: 'validating' | 'signing' | 'broadcasting' | 'confirming' | 'confirmed' | 'failed';
  likelihood: TransactionLikelihood;
  message: string;
  txHash?: string;
  confirmations?: number;
  error?: string;
}

export function getTransactionStageMessage(stage: TransactionStatusUpdate['stage']): string {
  const messages = {
    validating: 'Preparing transaction...',
    signing: 'Please approve in your wallet',
    broadcasting: 'Sending to blockchain network',
    confirming: 'Processing on blockchain',
    confirmed: 'Success! Transaction complete',
    failed: 'Transaction failed',
  };
  return messages[stage];
}