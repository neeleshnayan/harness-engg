import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatTokenBalance(balance: string): string {
  try {
    const numBalance = parseFloat(balance);
    if (isNaN(numBalance) || numBalance === 0) return '0.0000';

    // Handle very small numbers (e.g., ysMAVC with 18 decimals)
    // Show more precision for tiny amounts
    if (numBalance < 0.00000001) {
      // For extremely small numbers, show up to 12 decimal places
      return numBalance.toFixed(12).replace(/\.?0+$/, '');
    }
    if (numBalance < 0.0001) return numBalance.toFixed(8).replace(/\.?0+$/, '');
    if (numBalance < 0.01) return numBalance.toFixed(6).replace(/\.?0+$/, '');
    if (numBalance < 1) return numBalance.toFixed(4).replace(/\.?0+$/, '');
    if (numBalance < 100) return numBalance.toFixed(2).replace(/\.?0+$/, '');

    // For large amounts, add thousands separator for readability
    if (numBalance >= 1000) {
      return numBalance.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
    }

    return numBalance.toFixed(1).replace(/\.?0+$/, '');
  } catch {
    return '0.0000';
  }
}