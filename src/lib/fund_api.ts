import axios from 'axios';

// ClarkHarness (fund spine). In the dev browser go through the Next rewrite
// (/proxy/harness) to avoid CORS; otherwise use the configured harness URL.
// Mirror of the /proxy/{main,hedge,web3} pattern in next.config.ts.
const IS_DEV = process.env.NODE_ENV === 'development';
const IS_BROWSER = typeof window !== 'undefined';

const HARNESS_BASE_URL =
  IS_DEV && IS_BROWSER
    ? '/proxy/harness'
    : (process.env.NEXT_PUBLIC_HARNESS_API_URL || 'http://127.0.0.1:8090');

const fundApi = axios.create({
  baseURL: HARNESS_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60000,
});

const P = '/api/v1/fund';

export type StrategyState = 'draft' | 'backtested' | 'deployed' | 'paused';

export interface SpineEvent {
  event_id: string;
  seq: number;
  aggregate_id: string;
  aggregate_type: string;
  type: string;
  payload: Record<string, any>;
  actor: string;
  ts: string;
}

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
  assets?: string[];             // scoped asset universe
  // Layered cake (nested strategies) — many-to-many composition
  parent_id?: string | null;   // back-compat: first parent
  parents?: string[];          // full membership set (a strategy can have several)
  archived?: boolean;
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
  thesis_id?: string | null;
  impact_preview?: {
    quote_price?: number;
    notional_usd?: number;
    nav_before?: number;
    cash_before?: number;
    cash_after?: number;
  };
  ts?: string;
}

export type ThesisStatus = 'draft' | 'active' | 'invalidated' | 'exited' | 'reviewed';

export interface ThesisView {
  thesis_id: string;
  title: string;
  status: ThesisStatus;
  claim?: string | null;
  assets?: string[] | null;
  strategy_id?: string | null;
  owner?: string | null;
  horizon?: string | null;
  entry_rationale?: string | null;
  key_risks?: string[] | null;
  invalidation_conditions?: string[] | null;
  target_exposure_pct?: number | null;
  review_cadence?: string | null;
  order_ids?: string[];
  memo_ids?: string[];
  has_postmortem?: boolean;
}

export type MemoStatus = 'draft' | 'final';

export interface MemoView {
  memo_id: string;
  thesis_id: string;
  title: string;
  status: MemoStatus;
  recommendation?: string | null;
  conviction?: 'low' | 'medium' | 'high' | null;
  summary?: string | null;
  sections?: Record<string, string> | null;
  sources?: string[] | null;
  author?: string | null;
}

export interface RiskScenario {
  label: string;
  symbol?: string | null;
  pct: number;
  pnl_usd: number;
  nav_before: number;
  nav_after: number;
  nav_change_pct: number;
  nav_per_unit_before: number;
  nav_per_unit_after: number;
  affected: { symbol: string; shocked_mark: number; pnl_usd: number }[];
}

export interface RiskAnalytics {
  nav_usd: number;
  gross_exposure_usd: number;
  gross_exposure_pct: number;
  cash_usd: number;
  cash_pct: number;
  n_positions: number;
  largest_position?: { symbol: string; qty: number; mark: number; usd_value: number; weight_pct: number } | null;
  concentration_hhi: number;
  positions: { symbol: string; qty: number; mark: number; usd_value: number; weight_pct: number }[];
  flags: string[];
  scenarios: RiskScenario[];
}

export interface Postmortem {
  postmortem_id: string;
  thesis_id: string;
  verdict: 'correct' | 'partially_correct' | 'wrong' | 'invalidated' | 'too_early';
  outcome_pnl_usd: number;
  what_happened?: string | null;
  lessons?: string[];
  predicted_claim?: string | null;
  invalidation_conditions?: string[];
}

export interface OrderHistoryRow {
  order_id: string;
  symbol: string;
  side: 'buy' | 'sell';
  qty: number;
  strategy_id?: string | null;
  thesis_id?: string | null;
  status: 'pending' | 'approved' | 'working' | 'partial' | 'filled' | 'failed' | 'rejected' | 'declined';
  filled_qty?: number | null;
  avg_price?: number | null;
  ts?: string | null;
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

// --- strategy-level risk & bars (asset-scoped) ---
export interface FrontierPoint {
  target_return: number;
  return: number;
  volatility: number;
  sharpe: number;
  weights: Record<string, number>;
}

export interface StrategyOptimizeResponse {
  method?: string;
  weights?: Record<string, number>;
  optimal_weights?: Record<string, number>;
  expected_sharpe?: number;
  frontier_points?: FrontierPoint[];
  correlation?: Record<string, Record<string, number>>;
  cv_metrics?: {
    oos_sharpe?: number;
    oos_annual_return?: number;
    oos_max_drawdown?: number;
    pbo?: number;
    folds?: Array<{ fold: number; is_sharpe: number; oos_sharpe: number; weights: Record<string, number> }>;
  };
}

export interface StrategyRiskAsset {
  symbol: string; qty: number; mark: number; value_usd: number;
  weight_pct: number; shock_10_pct: number; shock_20_pct: number;
}

export interface StrategyRiskResponse {
  strategy_id: string; name: string; state: string;
  exposure_usd: number; pnl_usd: number; concentration_hhi: number;
  n_assets: number; assets: StrategyRiskAsset[];
  flags: string[];
  scenarios: { label: string; pnl_usd: number; exposure_after: number }[];
}

export interface StrategyBarsResponse {
  strategy_id: string; assets: string[];
  bars: Record<string, { closes: number[]; dates: string[] | null; source: string; start?: string | null; end?: string | null; error?: string }>;
}

export interface PositionImpact {
  symbol: string;
  qty: number;
  mark_before: number;
  mark_after: number;
  value_before: number;
  value_after: number;
  pnl_usd: number;
  shock_pct: number;
  sensitivities: {
    market_beta: number;
    oil_beta: number;
    duration: number;
  };
}

export interface HedgingProposal {
  proposal_id: string;
  title: string;
  description: string;
  actions: Array<{
    strategy_name: string;
    current_pct: number;
    recommended_pct: number;
  }>;
  expected_beta_after: number;
  mitigated_drawdown_usd: number;
  mitigated_drawdown_pct: number;
}

export interface SimulationResponse {
  preset?: { key: string; name: string; description: string };
  inputs: {
    crude_oil_price: number;
    yield_10y_bps: number;
    market_shock_pct: number;
    vix_spike_pct: number;
    crypto_shock_pct: number;
  };
  summary: {
    nav_usd_before: number;
    nav_usd_after: number;
    drawdown_usd: number;
    drawdown_pct: number;
    portfolio_beta: number;
    sharpe_before: number;
    sharpe_after: number;
    cash_usd: number;
  };
  position_impacts: PositionImpact[];
  warnings: string[];
  hedging_proposals: HedgingProposal[];
}

export interface SentinelSignal {
  signal_id: string;
  symbol: string;
  title: string;
  source: string;
  conviction_score: number;
  summary: string;
  details?: Record<string, string>;
  target_exposure_pct: number;
  target_upside_pct: number;
  invalidation_criteria?: string[];
  status: string;
  created_at: string;
  thesis_id?: string | null;
  memo_id?: string | null;
}

export interface RiskAlarmItem {
  key: string;
  type: string;
  severity: 'info' | 'warn' | 'critical' | string;
  message: string;
  metric: number;
  threshold: number;
  symbol?: string | null;
  strategy_id?: string | null;
  ts?: string;
}

export interface RiskMonitorDrawdown {
  peak_nav: number;
  current_nav: number;
  drawdown_pct: number;
  max_drawdown_pct: number;
  limit_pct: number;
  utilization: number;
}

export interface RiskMonitorPosition {
  symbol: string;
  qty: number;
  mark: number;
  value_usd: number;
  weight_pct: number;
  unrealized_pnl_pct: number;
  shock_20_usd: number;
}

export interface RiskMonitorStrategy {
  strategy_id: string;
  name: string;
  exposure_usd: number;
  weight_pct: number;
  pnl_usd: number;
  limit_pct: number;
  utilization: number;
  breach: boolean;
}

export interface RiskLimitsConfig {
  max_position_pct: number;
  min_cash_buffer: number;
  max_order_notional_pct: number;
  max_strategy_pct: number;
  min_cash_pct: number;
  max_drawdown_pct: number;
  max_daily_loss_pct: number;
  underwater_pct: number;
}

export interface RiskMonitorResponse {
  nav_usd: number;
  cash_usd: number;
  cash_pct: number;
  gross_exposure_usd: number;
  gross_exposure_pct: number;
  halted: boolean;
  drawdown: RiskMonitorDrawdown;
  positions: RiskMonitorPosition[];
  strategies: RiskMonitorStrategy[];
  limits: RiskLimitsConfig;
  utilization: {
    max_position_pct: number;
    max_strategy_pct: number;
    min_cash_pct: number;
    max_drawdown_pct: number;
  };
  alarms: RiskAlarmItem[];
  worst_position: RiskMonitorPosition | null;
  ts: string;
}

export const fundApiClient = {
  getNav: async (): Promise<NavResponse> => (await fundApi.get(`${P}/nav`)).data,

  getNavHistory: async (limit = 90): Promise<{ history: NavSnapshot[] }> =>
    (await fundApi.get(`${P}/nav/history`, { params: { limit } })).data,

  getOrderHistory: async (strategyId?: string | null, limit = 200): Promise<{ orders: OrderHistoryRow[] }> =>
    (await fundApi.get(`${P}/orders/history`, {
      params: { ...(strategyId ? { strategy_id: strategyId } : {}), limit },
    })).data,

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

  registerStrategy: async (name: string, definition: string = "Sandbox", parentId?: string, actor = 'operator'): Promise<StrategyView> =>
    (await fundApi.post(`${P}/strategies`, { name, definition, parent_id: parentId, actor })).data,

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

  renameStrategy: async (strategyId: string, name: string, actor = 'operator') =>
    (await fundApi.post(`${P}/strategies/${strategyId}/rename`, { name, actor })).data,

  archiveStrategy: async (strategyId: string, actor = 'operator') =>
    (await fundApi.post(`${P}/strategies/${strategyId}/archive`, { actor })).data,

  addStrategyParent: async (strategyId: string, parentId: string, actor = 'operator') =>
    (await fundApi.post(`${P}/strategies/${strategyId}/parents`, { parent_id: parentId, actor })).data,

  removeStrategyParent: async (strategyId: string, parentId: string, actor = 'operator') =>
    (await fundApi.post(`${P}/strategies/${strategyId}/parents/remove`, { parent_id: parentId, actor })).data,

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

  // --- theses (the versioned investment idea a trade references) ---
  getTheses: async (): Promise<{ theses: ThesisView[] }> =>
    (await fundApi.get(`${P}/theses`)).data,

  getThesis: async (thesisId: string): Promise<ThesisView> =>
    (await fundApi.get(`${P}/theses/${thesisId}`)).data,

  createThesis: async (body: Partial<ThesisView> & { title: string; actor?: string }): Promise<ThesisView> =>
    (await fundApi.post(`${P}/theses`, { actor: 'operator', ...body })).data,

  setThesisStatus: async (thesisId: string, status: ThesisStatus, note?: string, actor = 'operator') =>
    (await fundApi.post(`${P}/theses/${thesisId}/status`, { status, note, actor })).data,

  getThesisMemos: async (thesisId: string): Promise<{ memos: MemoView[] }> =>
    (await fundApi.get(`${P}/theses/${thesisId}/memos`)).data,

  getPostmortem: async (thesisId: string): Promise<Postmortem> =>
    (await fundApi.get(`${P}/theses/${thesisId}/postmortem`)).data,

  recordPostmortem: async (
    thesisId: string,
    body: { verdict: Postmortem['verdict']; what_happened?: string; lessons?: string[]; actor?: string },
  ): Promise<ThesisView> =>
    (await fundApi.post(`${P}/theses/${thesisId}/postmortem`, { actor: 'operator', ...body })).data,

  // --- memos (the written case for a trade) ---
  getMemo: async (memoId: string): Promise<MemoView> =>
    (await fundApi.get(`${P}/memos/${memoId}`)).data,

  createMemo: async (body: Partial<MemoView> & { thesis_id: string; title: string; actor?: string }): Promise<MemoView> =>
    (await fundApi.post(`${P}/memos`, { actor: 'operator', ...body })).data,

  finalizeMemo: async (memoId: string, actor = 'operator'): Promise<MemoView> =>
    (await fundApi.post(`${P}/memos/${memoId}/finalize`, { actor })).data,

  // --- risk analytics (concentration + scenario shocks) ---
  getRiskAnalytics: async (): Promise<RiskAnalytics> =>
    (await fundApi.get(`${P}/risk/analytics`)).data,

  runRiskShock: async (symbol: string | null, pct: number): Promise<RiskScenario> =>
    (await fundApi.post(`${P}/risk/shock`, { symbol, pct })).data,

  // --- strategy asset scoping, risk & bars ---
  setStrategyAssets: async (strategyId: string, symbols: string[], actor = 'operator') =>
    (await fundApi.post(`${P}/strategies/${strategyId}/assets`, { symbols, actor })).data,

  optimizeStrategy: async (strategyId: string, method: 'max_sharpe' | 'min_volatility' = 'max_sharpe', lookbackDays = 365): Promise<StrategyOptimizeResponse> =>
    (await fundApi.post(`${P}/strategies/${strategyId}/optimize`, { method, lookback_days: lookbackDays })).data,

  getStrategyRisk: async (strategyId: string): Promise<StrategyRiskResponse> =>
    (await fundApi.get(`${P}/strategies/${strategyId}/risk`)).data,

  getStrategyBars: async (
    strategyId: string,
    lookbackDays = 180,
  ): Promise<StrategyBarsResponse> =>
    (await fundApi.get(`${P}/strategies/${strategyId}/bars`, { params: { lookback_days: lookbackDays } })).data,

  getEvents: async (limit = 100, sinceSeq = 0): Promise<{ events: SpineEvent[] }> =>
    (await fundApi.get(`${P}/events`, { params: { limit, since_seq: sinceSeq } })).data,

  // --- simulation & sentinel ---
  simulateRisk: async (body: {
    scenario?: string;
    crude_oil_price?: number;
    yield_10y_bps?: number;
    market_shock_pct?: number;
    vix_spike_pct?: number;
    crypto_shock_pct?: number;
  }): Promise<SimulationResponse> =>
    (await fundApi.post(`${P}/risk/simulate`, body)).data,

  getSentinelSignals: async (): Promise<{ signals: SentinelSignal[] }> =>
    (await fundApi.get(`${P}/sentinel/signals`)).data,

  scanSentinel: async (symbol?: string): Promise<{ status: string; total_signals_scanned: number; newly_drafted_theses: any[]; signals: SentinelSignal[] }> =>
    (await fundApi.post(`${P}/sentinel/scan`, null, { params: { symbol } })).data,

  // --- risk monitor & kill-switch controls ---
  getRiskMonitor: async (): Promise<RiskMonitorResponse> =>
    (await fundApi.get(`${P}/risk/monitor`)).data,

  getRiskAlerts: async (): Promise<{ active: RiskAlarmItem[] }> =>
    (await fundApi.get(`${P}/risk/alerts`)).data,

  getRiskAlertHistory: async (limit = 100): Promise<{ history: SpineEvent[] }> =>
    (await fundApi.get(`${P}/risk/alerts/history`, { params: { limit } })).data,

  runRiskMonitor: async (actor = 'operator'): Promise<{ raised: RiskAlarmItem[]; cleared: string[]; halted: boolean; active: RiskAlarmItem[] }> =>
    (await fundApi.post(`${P}/risk/monitor/run`, { actor })).data,

  getRiskLimits: async (): Promise<RiskLimitsConfig> =>
    (await fundApi.get(`${P}/risk/limits`)).data,

  setRiskLimits: async (patch: Partial<RiskLimitsConfig>, actor = 'operator'): Promise<RiskLimitsConfig> =>
    (await fundApi.post(`${P}/risk/limits`, { patch, actor })).data,

  haltTrading: async (reason: string, actor = 'operator'): Promise<{ status: string; reason: string; halted: boolean }> =>
    (await fundApi.post(`${P}/risk/halt`, { reason, actor })).data,

  resumeTrading: async (actor = 'operator'): Promise<{ status: string; halted: boolean }> =>
    (await fundApi.post(`${P}/risk/resume`, { actor })).data,
};

export default fundApi;
