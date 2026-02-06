import { kryptonWeb3Api } from '@/lib/api';

// Response types matching backend schemas
export interface PoolInfo {
  pool_address: string;
  token0_symbol: string;
  token1_symbol: string;
  token0_address: string;
  token1_address: string;
  rate_provider: string | null;
  fx_pair: string | null;
  is_initialized: boolean;
  rebalance_thresholds: {
    lower: number;
    upper: number;
  } | null;
}

export interface PoolParameters {
  pool_type: string;
  range_lower: number | null;
  range_upper: number | null;
  swap_fee: number;
  total_supply: string | null;
}

export interface ReserveBalance {
  symbol: string;
  balance: string;
  decimals: number;
}

export interface RebalanceStatus {
  threshold_lower: number;
  threshold_upper: number;
  token0_percent: number;
  token1_percent: number;
  is_balanced: boolean;
  strategy: string;
}

export interface OracleInfo {
  rate: string;
  live_rate: string | null;
  timestamp: number | null;
  deviation_percent: number | null;
}

export interface PoolState {
  pool_address: string;
  token0_symbol: string;
  token1_symbol: string;
  token0_address: string;
  token1_address: string;
  reserves: string[];
  total_value: string | null;
  spot_price: string;
  oracle_rate: string | null;
  oracle_info: OracleInfo | null;
  is_initialized: boolean;
  pool_parameters: PoolParameters | null;
  reserve_balances: ReserveBalance[] | null;
  reserve_wallet: string | null;
  rebalance_status: RebalanceStatus | null;
  rate_synced: boolean;
}

export interface TokenBalance {
  symbol: string;
  address: string;
  balance: string;
  decimals: number;
}

export interface SwapQuote {
  estimated_output: string;
  spot_price: string;
  fee_amount: string;
  price_impact?: string;
}

export interface DeviationResponse {
  pool_address: string;
  pool_spot_price: string;
  oracle_rate: string;
  deviation_percent: number;
  needs_rebalance: boolean;
  threshold_breached?: string;
}

export interface AdminOperationResponse {
  success: boolean;
  transaction_id: string;
  pool_address?: string;
  status: string;
  message: string;
}

export interface OracleRateResponse {
  fx_pair: string;
  rate: string;
  timestamp: number;
  source: string;
}

export interface DefaultSignerResponse {
  address: string;
  username: string | null;
}

// Read-only endpoints (all users)
export const nettingPoolsApi = {
  // Get default signer address (for displaying admin wallet balances)
  async getDefaultSigner(): Promise<DefaultSignerResponse> {
    const response = await kryptonWeb3Api.get('/netting-pools/default-signer');
    return response.data;
  },

  // List all pools
  async getPools(): Promise<PoolInfo[]> {
    const response = await kryptonWeb3Api.get('/netting-pools/pools');
    return response.data;
  },

  // Get pool state
  async getPoolState(poolAddress: string): Promise<PoolState> {
    const response = await kryptonWeb3Api.get(`/netting-pools/pool/${poolAddress}/state`);
    return response.data;
  },

  // Get spot price
  async getSpotPrice(poolAddress: string, tokenInAddress: string, tokenOutAddress: string) {
    const response = await kryptonWeb3Api.get(`/netting-pools/pool/${poolAddress}/spot-price`, {
      params: { token_in_address: tokenInAddress, token_out_address: tokenOutAddress }
    });
    return response.data;
  },

  // Quote swap


  // Get price deviation
  async getDeviation(poolAddress: string): Promise<DeviationResponse> {
    const response = await kryptonWeb3Api.get(`/netting-pools/pool/${poolAddress}/deviation`);
    return response.data;
  },

  // Get balances
  async getBalances(walletAddress: string): Promise<TokenBalance[]> {
    const response = await kryptonWeb3Api.get(`/netting-pools/balances/${walletAddress}`);
    return response.data;
  },

  // Get oracle rate
  async getOracleRate(fxPair: string): Promise<OracleRateResponse> {
    const response = await kryptonWeb3Api.get('/netting-pools/oracle/rate', {
      params: { fx_pair: fxPair }
    });
    return response.data;
  },

  // Get supported tokens configuration (dynamic from k_tokens.yaml)
  async getSupportedTokens(): Promise<{
    k_tokens: Record<string, {
      address: string;
      decimals: number;
      pool_address?: string;
      rate_provider?: string;
      fx_pair?: string;
    }>;
  }> {
    const response = await kryptonWeb3Api.get('/erc20/supported-tokens');
    return response.data;
  },

  // Admin operations (require authentication + manual whitelist)
  async initializePool(params: {
    token_symbol: string;
    token0_amount: number;
    token1_amount: number;
    username: string;
  }): Promise<AdminOperationResponse> {
    const response = await kryptonWeb3Api.post('/netting-pools/pool/initialize', params);
    return response.data;
  },

  async addLiquidity(params: {
    token_symbol: string;
    token0_amount: number;
    token1_amount: number;
    username: string;
  }): Promise<AdminOperationResponse> {
    const response = await kryptonWeb3Api.post('/netting-pools/pool/add-liquidity', params);
    return response.data;
  },

  async syncRate(params: {
    token_symbol: string;
    manual_rate?: number;
    username: string;
  }): Promise<AdminOperationResponse> {
    const response = await kryptonWeb3Api.post('/netting-pools/oracle/sync-rate', params);
    return response.data;
  },

  // STANDARD POOLS API - For k-token to k-token swaps (Balancer V3)
  // Uses main Krypton Web3 backend pools.py endpoints

  async estimateSwap(params: {
    from_token: string;
    to_token: string;
    amount: number;
    slippage_tolerance?: number;
  }): Promise<{
    estimated_output: number;
    min_amount_out: number;
    price_impact?: number;
    from_token: string;
    to_token: string;
  }> {
    const response = await kryptonWeb3Api.post('/pools/estimate', params);
    return response.data;
  },

  async executeSwap(params: {
    from_token: string;
    to_token: string;
    amount: number;
    wallet_username: string;
    slippage_tolerance?: number;
  }): Promise<{
    status: string;
    transaction_id?: string;
    estimated_output: number;
    message?: string;
  }> {
    const response = await kryptonWeb3Api.post('/pools/swap', params);
    return response.data;
  },



  // Legacy methods kept for compatibility but should be replaced
  async quoteSwap(params: any) {
    return this.quoteSwapLegacy(params);
  },

  async quoteSwapLegacy(params: {
    pool_address: string;
    token_in_address: string;
    token_out_address: string;
    amount_in: number;
  }): Promise<SwapQuote> {
    const response = await kryptonWeb3Api.post('/netting-pools/quote-swap', params);
    return response.data;
  },
};

