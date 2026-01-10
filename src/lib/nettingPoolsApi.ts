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

export interface PoolState {
  pool_address: string;
  token0_symbol: string;
  token1_symbol: string;
  token0_address: string;
  token1_address: string;
  reserves: string[];
  spot_price: string;
  oracle_rate: string | null;
  is_initialized: boolean;
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
  async quoteSwap(params: {
    pool_address: string;
    token_in_address: string;
    token_out_address: string;
    amount_in: number;
  }): Promise<SwapQuote> {
    const response = await kryptonWeb3Api.post('/netting-pools/quote-swap', params);
    return response.data;
  },

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

  async executeSwap(params: {
    pool_address: string;
    token_in_address: string;
    token_out_address: string;
    amount_in: number;
    min_amount_out: number;
    username: string;
  }): Promise<AdminOperationResponse> {
    const response = await kryptonWeb3Api.post('/netting-pools/pool/swap', params);
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

  async multiHopSwap(params: {
    token_path: string[];
    amount_in: number;
    min_amount_out: number;
    username: string;
  }): Promise<AdminOperationResponse> {
    const response = await kryptonWeb3Api.post('/netting-pools/pool/multi-hop-swap', params);
    return response.data;
  },
};

