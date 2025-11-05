import { formatUnits, parseUnits } from 'viem';

type FormatOptions = {
  maximumFractionDigits?: number;
  minimumFractionDigits?: number;
  fallback?: string;
};

type CurrencyOptions = FormatOptions & {
  fallback?: string;
};

const formatNumber = (value: number, options: FormatOptions) => {
  const { maximumFractionDigits = 2, minimumFractionDigits = 2, fallback = '0.00' } = options;
  if (!Number.isFinite(value)) return fallback;
  return new Intl.NumberFormat('en-US', {
    style: 'decimal',
    maximumFractionDigits,
    minimumFractionDigits,
  }).format(value);
};

export const formatToken = (
  value: bigint | undefined,
  decimals: number,
  options: FormatOptions = {},
) => {
  if (value === undefined) return options.fallback ?? '0.00';
  const parsed = Number(formatUnits(value, decimals));
  return formatNumber(parsed, options);
};

export const formatUsd = (
  value: bigint | undefined,
  decimals = 6,
  options: CurrencyOptions = {},
) => {
  if (value === undefined) return options.fallback ?? '$0.00';
  const parsed = Number(formatUnits(value, decimals));
  if (!Number.isFinite(parsed)) return options.fallback ?? '$0.00';
  const { maximumFractionDigits = 2, minimumFractionDigits = 2 } = options;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits,
    minimumFractionDigits,
  }).format(parsed);
};

export const formatPercent = (value?: number, digits = 1) => {
  if (value === undefined || Number.isNaN(value)) return '0%';
  return `${value.toFixed(digits)}%`;
};

export const formatAddress = (address?: string) => {
  if (!address) return '';
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
};

export const toBaseUnit = (value: string, decimals: number) => {
  const sanitized = value.replace(/,/g, '').trim();
  if (!sanitized) return 0n;
  return parseUnits(sanitized as `${number}${string}`, decimals);
};

export const toDisplayUnit = (value: bigint, decimals: number) => {
  return Number(formatUnits(value, decimals));
};
