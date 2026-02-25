/**
 * Frontend chain constants.
 *
 * These mirror the core token addresses configured in
 * `Krypton_Web3/config/k_tokens.yaml` and `Krypton_Web3/config/rwa_tokens.yaml`,
 * with env overrides where appropriate so we don't hardcode per-environment
 * values throughout the UI.
 */

// ---- RPC / Network ----

export const DEFAULT_SEPOLIA_RPC_URL =
  process.env.NEXT_PUBLIC_RPC_URL || "https://ethereum-sepolia-rpc.publicnode.com";

// ---- Base currencies (k-tokens & USDC) ----

export const USDC_ADDRESS: string = (
  process.env.NEXT_PUBLIC_USDC_ADDRESS ||
  // k_tokens.USDC.address
  "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
).toLowerCase();

export const KUSD_ADDRESS: string = (
  process.env.NEXT_PUBLIC_KUSD_ADDRESS ||
  // k_tokens.kUSD.address
  "0xc1868b5BA545C18082510283FEeC1C8BA314591e"
).toLowerCase();

export const KEUR_ADDRESS: string = (
  process.env.NEXT_PUBLIC_KEUR_ADDRESS ||
  // k_tokens.kEUR.address
  "0x9d20B4982C2AA045C913907Eb0dd13203c14a474"
).toLowerCase();

export const KGBP_ADDRESS: string = (
  process.env.NEXT_PUBLIC_KGBP_ADDRESS ||
  // k_tokens.kGBP.address
  "0xeD40d78431Cc0183B3F7bdA5d7F1E461908cbf7B"
).toLowerCase();

export const KAED_ADDRESS: string = (
  process.env.NEXT_PUBLIC_KAED_ADDRESS ||
  // k_tokens.kAED.address
  "0xD9fef4C9d70EfA3da4ba08eDB01a0BD642cB8d8B"
).toLowerCase();

export const KINR_ADDRESS: string = (
  process.env.NEXT_PUBLIC_KINR_ADDRESS ||
  // k_tokens.kINR.address
  "0x989E1ff08B90001dE415fD9154A7F6aD913A9872"
).toLowerCase();

// ---- RWA tokens (GC, XAG, NVDA, ETH) ----

export const GC_RWA_ADDRESS: string = (
  process.env.NEXT_PUBLIC_GC_RWA_ADDRESS ||
  // rwa_tokens.GC.address
  "0x010A7d54F9756a3b3EbeC52998A2a09BaA37e829"
).toLowerCase();

export const XAG_RWA_ADDRESS: string = (
  process.env.NEXT_PUBLIC_XAG_RWA_ADDRESS ||
  // rwa_tokens.XAG.address
  "0x326251D13257939170769a8904614381736a0950"
).toLowerCase();

export const NVDA_RWA_ADDRESS: string = (
  process.env.NEXT_PUBLIC_NVDA_RWA_ADDRESS ||
  // rwa_tokens.NVDA.address
  "0x4275FCb5C9b42950EB23d9d07C6cAEe01865c090"
).toLowerCase();

export const ETH_RWA_ADDRESS: string = (
  process.env.NEXT_PUBLIC_ETH_RWA_ADDRESS ||
  // rwa_tokens.ETH.address
  "0x5890F38C551c435088b67210b29A911c3ce209d5"
).toLowerCase();

// ---- Known utility / strategy-related addresses ----

export const WETH_ADDRESS: string = (
  process.env.NEXT_PUBLIC_WETH_ADDRESS ||
  // Common Sepolia WETH used in hooks (see useTokenSymbol.ts)
  "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"
).toLowerCase();

// Yearn WETH strategy default address (can be overridden per env).
export const YEARN_WETH_STRATEGY_ADDRESS: string = (
  process.env.NEXT_PUBLIC_YEARN_WETH_STRATEGY_ADDRESS ||
  "0x6e2671D1B22b39d1b72a6A4E8Ed55309489BD448"
).toLowerCase();

