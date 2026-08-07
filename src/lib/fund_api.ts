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

export interface BacktestSummary {
  total_return: number;
  sharpe: number;
  max_drawdown: number;
  n_trades: number;
  final_equity: number;
  bars: number;
}

export interface StrategyView {
  strategy_id: string;
  name: string;
  state: StrategyState;
  allocation_pct: number;
  actual_pct?: number;
  exposure_usd?: number;
  pnl_usd?: number;
  positions?: Record<string, { qty?: number; avg_price?: number }>;
  backtest?: BacktestSummary | null;
  // Layered cake (nested strategies)
  parent_id?: string | null;
  children?: string[];
  is_container?: boolean;
  depth?: number;
  rolled_exposure_usd?: number;
  rolled_pnl_usd?: number;
  rolled_actual_pct?: number;
}

export interface StrategiesResponse {
  nav_usd: number;
  strategies: StrategyView[];
  discretionary?: { exposure_usd?: number; pnl_usd?: number } | null;
}

export interface NavPosition {
  symbol: string;
  qty: number;
  mark: number;
  usd_value: number;
}

export interface NavSnapshot {
  ts?: string;
  total_nav_usd: number;
  units_outstanding: number;
  nav_per_unit: number;
  breakdown: { positions: number; cash: number };
  positions: NavPosition[];
}

export interface NavResponse {
  live: NavSnapshot;
  last_struck: NavSnapshot | null;
}

export interface LpView {
  lp_id: string;
  name?: string;
  units: number;
  value_usd: number;
  ownership_pct?: number;
}

export interface PendingOrder {
  order_id: string;
  symbol: string;
  side: 'buy' | 'sell';
  qty: number;
  strategy_id?: string | null;
  impact_preview?: {
    quote_price?: number;
    notional_usd?: number;
    nav_before?: number;
    cash_before?: number;
    cash_after?: number;
  };
  ts?: string;
}

export interface BacktestResult {
  total_return: number;
  sharpe: number;
  max_drawdown: number;
  n_trades: number;
  final_equity: number;
  bars: number;
}

export type StrategyTemplate =
  | 'sma' | 'buy_hold' | 'rsi' | 'breakout' | 'macd' | 'bollinger' | 'momentum' | 'atr_trail';

export interface StrategyParams {
  strategy: StrategyTemplate;
  fast?: number;
  slow?: number;
  rsi_period?: number;
  rsi_low?: number;
  rsi_high?: number;
  breakout_lookback?: number;
  macd_fast?: number;
  macd_slow?: number;
  macd_signal?: number;
  boll_period?: number;
  boll_k?: number;
  momentum_lookback?: number;
  atr_period?: number;
  atr_mult?: number;
  actor?: string;
}

export interface BacktestRunBody extends StrategyParams {
  prices: number[];
}

export interface BacktestBySymbolBody extends StrategyParams {
  symbol: string;
  lookback_days?: number;
}

export interface BacktestBySymbolResponse {
  result: BacktestResult;
  strategy: StrategyView;
  source: string;
  symbol: string;
  bars: { closes: number[]; dates: string[] | null; start: string | null; end: string | null };
}

export const fundApiClient = {
  getNav: async (): Promise<NavResponse> => (await fundApi.get(`${P}/nav`)).data,

  getStrategies: async (): Promise<StrategiesResponse> =>
    (await fundApi.get(`${P}/strategies`)).data,

  getLps: async (): Promise<{ nav_per_unit: number; lps: LpView[] }> =>
    (await fundApi.get(`${P}/lps`)).data,

  getPending: async (): Promise<{ pending: PendingOrder[] }> =>
    (await fundApi.get(`${P}/orders/pending`)).data,

  getBars: async (
    symbol: string,
    lookbackDays = 180,
  ): Promise<{ symbol: string; source: string; closes: number[]; dates: string[] | null; start: string | null; end: string | null }> =>
    (await fundApi.get(`${P}/marketdata/bars`, { params: { symbol, lookback_days: lookbackDays } })).data,

  registerStrategy: async (name: string, parentId?: string | null, actor = 'operator') =>
    (await fundApi.post(`${P}/strategies`, { name, parent_id: parentId ?? null, actor })).data,

  runBacktest: async (
    strategyId: string,
    body: BacktestRunBody,
  ): Promise<{ result: BacktestResult; strategy: StrategyView }> =>
    (await fundApi.post(`${P}/strategies/${strategyId}/backtest/run`, {
      actor: 'operator',
      ...body,
    })).data,

  runBacktestBySymbol: async (
    strategyId: string,
    body: BacktestBySymbolBody,
  ): Promise<BacktestBySymbolResponse> =>
    (await fundApi.post(`${P}/strategies/${strategyId}/backtest/by_symbol`, {
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

  approveOrder: async (orderId: string, approver = 'operator') =>
    (await fundApi.post(`${P}/orders/${orderId}/approve`, { approver })).data,

  declineOrder: async (orderId: string, approver = 'operator') =>
    (await fundApi.post(`${P}/orders/${orderId}/decline`, { approver })).data,

  settle: async () => (await fundApi.post(`${P}/orders/settle`)).data,
};

export default fundApi;
