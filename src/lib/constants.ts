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

/* KUSD / KEUR / KGBP / KAED / KINR removed 2026-08-27. Zero references
   anywhere in the repository — including non-TypeScript files — and no
   hardcoded twin of any of the five addresses, checked case-insensitively.
   `USDC_ADDRESS` above and `WETH_ADDRESS` below are KEPT because they have
   live consumers, so this file already distinguishes used from unused and
   these five were the unused half. Git holds the addresses. */

// ---- RWA tokens (GC, XAG, NVDA, ETH) ----

export const XAG_RWA_ADDRESS: string = (
  process.env.NEXT_PUBLIC_XAG_RWA_ADDRESS ||
  // rwa_tokens.XAG.address
  "0x326251D13257939170769a8904614381736a0950"
).toLowerCase();

/* GC / NVDA / ETH RWA addresses removed 2026-08-27, same evidence as the
   k-tokens above. `XAG_RWA_ADDRESS` stays: it has a consumer. */

// ---- Known utility / strategy-related addresses ----

export const WETH_ADDRESS: string = (
  process.env.NEXT_PUBLIC_WETH_ADDRESS ||
  // Common Sepolia WETH used in hooks (see useTokenSymbol.ts)
  "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"
).toLowerCase();

/* NOT DELETED, THOUGH NOTHING IMPORTS IT — ITS DEATH IS THE DEFECT.
 *
 * `useStrategySubgraphData.ts:265` carries this exact address as a STRING
 * LITERAL:
 *
 *     const targetAddress = strategyAddress
 *       || (strategyName === 'YEARN_WETH' ? '0x6e2671…BD448' : '');
 *
 * So the constant is unreferenced not because the address is unused but
 * because the live path bypasses it — and `NEXT_PUBLIC_YEARN_WETH_STRATEGY_
 * ADDRESS` therefore cannot take effect on the one call site it exists for.
 * Deleting the constant would remove the evidence of intent and leave the
 * hardcode running.
 *
 * TWO REPAIRS, and picking between them is the wallet owner's call, not a
 * design dispatch's: (1) point line 265 at this constant, which is what the
 * env override was written for; or (2) delete the constant and record that
 * the address is deliberately not configurable. Reported, not chosen.
 */
// Yearn WETH strategy default address (can be overridden per env).
export const YEARN_WETH_STRATEGY_ADDRESS: string = (
  process.env.NEXT_PUBLIC_YEARN_WETH_STRATEGY_ADDRESS ||
  "0x6e2671D1B22b39d1b72a6A4E8Ed55309489BD448"
).toLowerCase();

