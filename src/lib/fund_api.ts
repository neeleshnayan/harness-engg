import axios from 'axios';

// ClarkHarness (fund spine). In the dev browser go through the Next rewrite
// (/proxy/harness) to avoid CORS; otherwise use the configured harness URL.
// Mirror of the /proxy/{main,hedge,web3} pattern in next.config.ts.
const IS_DEV = process.env.NODE_ENV === 'development';
const IS_BROWSER = typeof window !== 'undefined';

const HARNESS_BASE_URL =
  IS_DEV && IS_BROWSER
    ? '/proxy/harness'
    : (process.env.NEXT_PUBLIC_HARNESS_API_URL || 'http://127.0.0.1:8000');

const fundApi = axios.create({
  baseURL: HARNESS_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60000,
});

const P = '/api/v1/fund';

export type StrategyState = 'draft' | 'backtested' | 'deployed' | 'paused';

export interface StrategyView {
  strategy_id: string;
  name: string;
  state: StrategyState;
  allocation_pct: number;
  actual_pct?: number;
  exposure_usd?: number;
  pnl_usd?: number;
  backtest?: Record<string, unknown> | null;
}

export interface StrategiesResponse {
  nav_usd: number;
  strategies: StrategyView[];
  discretionary?: { exposure_usd?: number; pnl_usd?: number } | null;
}

export interface BacktestResult {
  total_return: number;
  sharpe: number;
  max_drawdown: number;
  n_trades: number;
  final_equity: number;
  bars: number;
}

export interface BacktestRunBody {
  prices: number[];
  strategy: 'sma' | 'buy_hold';
  fast?: number;
  slow?: number;
  actor?: string;
}

export const fundApiClient = {
  getNav: async () => (await fundApi.get(`${P}/nav`)).data,

  getStrategies: async (): Promise<StrategiesResponse> =>
    (await fundApi.get(`${P}/strategies`)).data,

  registerStrategy: async (name: string, actor = 'operator') =>
    (await fundApi.post(`${P}/strategies`, { name, actor })).data,

  runBacktest: async (
    strategyId: string,
    body: BacktestRunBody,
  ): Promise<{ result: BacktestResult; strategy: StrategyView }> =>
    (await fundApi.post(`${P}/strategies/${strategyId}/backtest/run`, {
      actor: 'operator',
      ...body,
    })).data,

  setState: async (strategyId: string, state: StrategyState, actor = 'operator') =>
    (await fundApi.post(`${P}/strategies/${strategyId}/state`, { state, actor })).data,

  setAllocation: async (strategyId: string, targetPct: number, actor = 'operator') =>
    (await fundApi.post(`${P}/strategies/${strategyId}/allocation`, {
      target_pct: targetPct,
      actor,
    })).data,
};

export default fundApi;
