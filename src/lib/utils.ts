import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatTokenBalance(balance: string): string {
  try {
    const numBalance = parseFloat(balance);
    if (isNaN(numBalance) || numBalance === 0) return '0.0000';

    // For very small amounts, show more decimal places
    if (numBalance < 0.0001) return numBalance.toFixed(6);
    if (numBalance < 0.01) return numBalance.toFixed(4);
    if (numBalance < 1) return numBalance.toFixed(3);
    if (numBalance < 100) return numBalance.toFixed(2);

    // For large amounts, add thousands separator for readability
    if (numBalance >= 1000) {
      return numBalance.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
    }

    return numBalance.toFixed(1);
  } catch {
    return '0.0000';
  }
}