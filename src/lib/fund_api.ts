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
  /** Pooled total = realized + unrealized. */
  pnl_usd?: number;
  /** Locked in by sales (average-cost basis). */
  realized_pnl_usd?: number;
  /** Mark-to-market on the open position. */
  unrealized_pnl_usd?: number;
  /** Cost basis of the open position. */
  cost_basis_usd?: number;
  positions?: Record<string, { qty?: number; avg_price?: number }>;
  backtest?: BacktestSummary | null;
  assets?: string[];             // scoped asset universe
  // Layered cake (nested strategies) — many-to-many composition
  parent_id?: string | null;   // back-compat: first parent
  parents?: string[];          // full membership set (a strategy can have several)
  archived?: boolean;
  members?: { child_id: string; name: string; weight: number }[];
  member_weights?: Record<string, number>;
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

export interface MarketQuote {
  symbol: string;
  price: number | null;
  prev_close: number | null;
  prev_close_date?: string | null;
  change: number | null;
  change_pct: number | null;
  /** true when there is no live tick and price falls back to the last close */
  stale: boolean;
  ok: boolean;
  held: boolean;
  qty?: number;
  value_usd?: number;
  weight_pct?: number;
  unrealized_pnl_pct?: number;
}

/** The broker's view of what the account is allowed to do. Every field is
 *  nullable because "we could not read it" must stay distinguishable from any
 *  particular value — a null shorting_enabled is not permission. */
export interface ComplianceAccount {
  known: boolean;
  equity: number | null;
  daytrade_count: number | null;
  pattern_day_trader: boolean | null;
  trading_blocked: boolean | null;
  account_blocked: boolean | null;
  shorting_enabled: boolean | null;
  status: string | null;
  error: string | null;
}

/** The pattern-day-trader budget. A cliff, not a slope: the fourth day trade
 *  in five sessions restricts a sub-$25k account to closing-only for 90 days,
 *  so `remaining` is the number that matters. */
export interface ComplianceStatus {
  account: ComplianceAccount;
  pdt: {
    applies: boolean;
    equity_threshold: number;
    max_day_trades: number;
    used: number;
    remaining: number | null;
    broker_count: number | null;
    our_count: number;
    source: string;
    diverges: boolean;
  };
}

export interface MarketQuotesResponse {
  quotes: MarketQuote[];
  held_count: number;
  watch_count: number;
  unpriced: string[];
}

export interface BacktestTrade {
  entry_index: number;
  entry_price: number;
  exit_index: number;
  exit_price: number;
  side: "long" | "short";
  position: number;
  pnl_pct: number;
  bars_held: number;
}

export interface ResearchResult extends BacktestResult {
  equity_curve: number[];
  trades: BacktestTrade[];
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  exposure_pct: number;
  volatility: number;
}

export interface ResearchBacktestResponse {
  symbol: string;
  source: string;
  strategy: string;
  params: Record<string, any>;
  result: ResearchResult;
  benchmark: {
    label: string;
    total_return: number;
    sharpe: number;
    max_drawdown: number;
    equity_curve: number[];
  };
  bars: { closes: number[]; dates: string[] | null; start: string | null; end: string | null };
  signals: number[];
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

export interface CompositeMember {
  child_id: string;
  name: string;
  weight: number;
  exposure_usd?: number;
  pnl_usd?: number;
}

export interface BlendedEquityPoint {
  t: string;
  v: number;
}

export interface CompositeView {
  strategy_id: string;
  members: CompositeMember[];
  blended_equity: BlendedEquityPoint[];
  metrics: {
    total_return: number;
    sharpe: number;
    max_drawdown: number;
  };
  risk: {
    concentration_hhi: number;
    drawdown_pct: number;
    flags: string[];
  };
  weights_sum: number;
}

export interface ComposeWeightsResponse {
  weights: Record<string, number>;
  method: string;
  expected: {
    sharpe: number;
    vol: number;
    ret: number;
  };
  cv: {
    pbo: number;
    oos_sharpe: number;
  };
  skipped_members?: string[];
}

/** Every block degrades independently — `measurable: false` carries a `reason`,
 *  and MUST render as that reason, never as a zero. */
export interface Measurable { measurable: boolean; reason?: string }

export interface CorrelationView extends Measurable {
  symbols: string[];
  n_positions: number;
  n_obs: number;
  window_end: string | null;
  weights: Record<string, number>;
  annualised_vol_pct: Record<string, number>;
  matrix: number[][];
  pairs: { a: string; b: string; correlation: number }[];
  avg_pairwise_correlation: number;
  max_pair: { a: string; b: string; correlation: number } | null;
  portfolio_vol_pct: number;
  stressed_vol_pct: number;
  diversification_ratio: number;
  effective_bets: number;
  naive_bets: number;
  positions_covered_pct: number;
  excluded: Record<string, string>;
  interpretation: string[];
  strategy_overlap?: Measurable & {
    pairs?: {
      a: string; a_name: string; b: string; b_name: string;
      shared_exposure_pct: number; shared_symbols: string[];
      return_correlation: number | null;
    }[];
    worst_pair?: unknown;
    note?: string;
  };
}

export interface RiskContributionRow {
  symbol: string;
  capital_weight_pct: number;
  marginal_contribution: number;
  component_risk_pct: number;
  risk_share_pct: number;
  risk_vs_capital_gap_pct: number;
}

export interface FactorRow {
  key: string;
  label: string;
  proxy: string;
  beta: number;
  std_error: number;
  t_stat: number;
  significant: boolean;
  reads: string;
}

export interface FactorModelView extends Measurable {
  n_obs?: number;
  alpha_annual_pct?: number;
  alpha_t_stat?: number;
  alpha_significant?: boolean;
  r_squared?: number;
  idiosyncratic_share?: number;
  factors?: FactorRow[];
  dominant_factor?: FactorRow;
  verdict?: string[];
  caveats?: string[];
}

export interface FactorMap extends Measurable {
  symbols?: string[];
  n_obs?: number;
  explained_variance?: number[];
  cumulative_explained?: number;
  scree?: number[];
  points?: { symbol: string; weight_pct: number; loadings: number[] }[];
  interpretation?: string[];
}

export interface CandidateEvaluation {
  n_obs: number;
  factors: FactorModelView;
  fit: Measurable & {
    n_obs?: number;
    allocation_pct?: number;
    correlation_to_book?: number;
    per_strategy?: { strategy_id: string; name: string; correlation: number }[];
    before?: { vol_pct: number; expected_shortfall_usd: number | null; sharpe_annual: number | null };
    after?: { vol_pct: number; expected_shortfall_usd: number | null; sharpe_annual: number | null };
    improves_book?: boolean;
    effect?: "diversifying" | "return-seeking" | "risk-reducing" | "neither";
    verdict?: string[];
  };
}

export interface AdvancedRiskView {
  factor_model?: FactorModelView;
  factor_map?: FactorMap;
  nav_usd: number;
  /** Cache metadata — cached figures must never be presented as live. */
  computed_at?: string;
  cached?: boolean;
  cache_age_seconds?: number;
  ttl_seconds?: number;
  limits: Record<string, number>;
  alarms: RiskAlarmItem[];
  headlines: string[];
  correlation: CorrelationView;
  risk_contribution: Measurable & {
    portfolio_vol_pct?: number;
    contributions?: RiskContributionRow[];
    largest_risk_contributor?: RiskContributionRow;
    decomposition_residual?: number;
  };
  tail: Measurable & {
    n_obs?: number;
    headline?: string;
    worst_day_pct?: number;
    worst_day_usd?: number;
    worst_5day_pct?: number;
    worst_5day_usd?: number;
    caveats?: string[];
    levels?: Record<string, {
      confidence: number; var_pct: number; expected_shortfall_pct: number;
      var_usd?: number; expected_shortfall_usd?: number; tail_observations: number;
    }>;
  };
  vol_regime: Measurable & {
    equal_weighted_vol_pct?: number; ewma_vol_pct?: number;
    ratio?: number; lambda?: number; verdict?: string;
  };
  portfolio_turbulence: Measurable & {
    latest?: number; percentile?: number; elevated?: boolean; verdict?: string;
  };
  regime?: Measurable & {
    basket?: string[];
    interpretation?: string[];
    turbulence?: Measurable & {
      latest?: number; percentile?: number; recent_20d_percentile?: number;
      elevated?: boolean; verdict?: string; n_scored_days?: number;
    };
    absorption?: Measurable & {
      current?: number; standardised_shift?: number; threshold?: number;
      flagged?: boolean; verdict?: string; n_eigenvectors?: number; n_assets?: number;
    };
  };
  reverse_stress: Measurable & {
    headline?: string; daily_headline?: string;
    uniform_move_to_halt_pct?: number; loss_to_halt_usd?: number;
    already_breached?: boolean;
    single_name?: { symbol: string; exposure_usd: number; move_to_halt_pct: number | null; possible: boolean }[];
    single_name_note?: string;
  };
  historical?: Measurable & {
    worst_scenario?: HistoricalScenario;
    scenarios?: HistoricalScenario[];
    note?: string;
  };
  loss_surface: Measurable & {
    x_correlation?: number[];
    y_horizon_days?: number[];
    z_loss_usd?: number[][];
    measured_correlation?: number | null;
    tail_multiplier?: number;
    caveats?: string[];
    axis_labels?: { x: string; y: string; z: string };
  };
}

export interface HistoricalScenario extends Measurable {
  key: string; label: string; start: string; end: string; note: string;
  pnl_usd?: number; nav_change_pct?: number; nav_after?: number;
  coverage_pct?: number; caveat?: string; missing?: string[];
  worst_name?: { symbol: string; return_pct: number; pnl_usd: number };
  per_symbol?: { symbol: string; return_pct: number; pnl_usd: number }[];
}

export interface RiskShape {
  symbols: string[];
  weights_pct_of_nav: Record<string, number>;
  gross_exposure_pct_of_nav: number;
  effective_bets: number;
  portfolio_vol_pct: number;
  stressed_vol_pct: number;
  expected_shortfall_usd: number | null;
  expected_shortfall_pct: number | null;
  largest_risk_contributor?: RiskContributionRow;
  contributions?: RiskContributionRow[];
}

export interface RiskWhatIf extends Measurable {
  nav_usd?: number;
  before?: RiskShape;
  after?: RiskShape;
  deltas?: Record<string, number>;
  proposed_exposure_usd?: Record<string, number>;
  proposed_cash_usd?: number;
  proposed_cash_pct?: number | null;
  symbols_without_history?: string[];
  unallocatable?: string[];
  assumption?: string;
}

export interface RebalanceOrder {
  symbol: string;
  side: "buy" | "sell";
  qty: number;
  est_price: number;
  notional_usd: number;
  current_usd: number;
  target_usd: number;
  strategy_id?: string | null;
  order_id?: string;
  breaches?: string[];
}

export interface RebalanceMechanics {
  measurable?: boolean;
  reason?: string;
  before?: Record<string, number | null>;
  after?: Record<string, number | null>;
  deltas?: Record<string, number>;
}

export interface RebalancePlan {
  plan_id?: string;
  status?: "pending_approval" | "approved" | "declined";
  targets: Record<string, number>;
  orders: RebalanceOrder[];
  skipped: { symbol: string; delta_usd: number; reason: string }[];
  unallocatable: string[];
  /** Breaches of the DESTINATION against the mandate — things the per-order
   *  pre-trade gate structurally cannot see. */
  limit_warnings?: string[];
  nav_usd: number;
  cash_after_usd: number;
  cash_after_pct: number;
  turnover_usd: number;
  turnover_pct: number;
  assumption: string;
  note?: string | null;
  mechanics?: RebalanceMechanics | null;
  proposed_at?: string;
  proposed_by?: string;
  /** Decorations computed at read time — what changed while the plan sat. */
  age_minutes?: number | null;
  price_drift?: { symbol: string; est_price: number; price_now: number; move_pct: number }[];
  warnings?: string[];
  outcome?: RebalanceOutcome;
}

export interface RebalanceOutcome {
  status?: string;
  plan_id: string;
  approved_at?: string;
  approved_by?: string;
  self_approved?: boolean;
  placed: RebalanceOrder[];
  rejected: RebalanceOrder[];
  n_placed: number;
  n_rejected: number;
  turnover_usd: number;
}

export interface IntradayNavSeries {
  samples: { ts: string; total_nav_usd: number; nav_per_unit: number | null; cash_usd: number | null; struck: boolean }[];
  n: number;
  window_minutes: number;
  change_usd: number | null;
  change_pct: number | null;
  from_ts: string | null;
  to_ts: string | null;
  note: string;
}

/** One fill, exactly as the event log recorded it. */
export interface ExecutionFill {
  ts: string | null;
  seq: number | null;
  symbol: string;
  side: string;
  qty: number;
  price: number;
  notional_usd: number;
  fees_usd: number;
  order_id: string | null;
  venue: string | null;
}

/** A closed round-trip: what a sale (or a cover) actually realized. */
export interface RoundTrip {
  symbol: string;
  side: 'long' | 'short';
  qty: number;
  avg_entry_price: number;
  exit_price: number;
  /** Quantity-weighted, because a position built over several buys has no
   *  single entry moment. */
  avg_entry_ts: string | null;
  exit_ts: string | null;
  gross_pnl_usd: number;
  fees_usd: number;
  pnl_usd: number;
  pnl_pct: number;
  outcome: 'win' | 'loss' | 'breakeven';
  cost_basis_usd: number;
}

export interface ExecutionSummary {
  measurable: boolean;
  reason?: string;
  n_round_trips?: number;
  winners?: number;
  losers?: number;
  breakevens?: number;
  win_rate?: number;
  loss_rate?: number;
  breakeven_rate?: number;
  breakeven_band_pct?: number;
  total_realized_usd?: number;
  avg_win_usd?: number;
  avg_loss_usd?: number;
  expectancy_usd?: number;
  payoff_ratio?: number | null;
  profit_factor?: number | null;
  best_usd?: number;
  worst_usd?: number;
  top_trade_share_of_gross_profit?: number | null;
  worst_trade_share_of_gross_loss?: number | null;
  streaks?: {
    measurable: boolean;
    reason?: string;
    longest_win_streak?: number;
    longest_loss_streak?: number;
    current_streak?: number;
    current_streak_kind?: string | null;
  };
  holding?: {
    measurable: boolean;
    reason?: string;
    n_timed?: number;
    avg_days_all?: number | null;
    avg_days_winners?: number | null;
    avg_days_losers?: number | null;
    longest_days?: number;
  };
  distribution_pct?: {
    measurable: boolean;
    reason?: string;
    bins?: { from_pct: number; to_pct: number; count: number; sign: 'win' | 'loss' }[];
    min_pct?: number;
    max_pct?: number;
    mean_pct?: number;
  };
}

export interface StrategyExecutions {
  strategy_id: string;
  measurable: boolean;
  reason?: string;
  fills: ExecutionFill[];
  n_fills: number;
  round_trips: RoundTrip[];
  n_round_trips: number;
  open_positions: Record<string, { qty: number; cost_basis_usd: number }>;
  summary: ExecutionSummary;
  by_side?: { all: ExecutionSummary; long: ExecutionSummary; short: ExecutionSummary };
}

/** What one live strategy wants for one symbol, and why. */
export interface SignalDecision {
  strategy_id: string;
  strategy_name: string;
  symbol: string;
  /** null when the strategy could not be evaluated — never a flat 0. */
  signal: number | null;
  target_usd: number | null;
  current_usd: number | null;
  delta_usd: number | null;
  action: "buy" | "sell" | "hold" | "skip";
  reason: string;
}

/** A sized trade a signal implies, before anyone has proposed it. */
export interface SignalSizedRow extends SignalDecision {
  qty?: number;
  price?: number;
  dry_run?: boolean;
  status?: string;
  order_id?: string;
  breaches?: string[];
}

export interface SignalRunResult {
  dry_run: boolean;
  /** null when the venue clock was unreachable — NOT the same as closed. */
  market_open: boolean | null;
  evaluated: SignalDecision[];
  proposed: SignalSizedRow[];
  /** Wanted a trade but could not be sized or was already pending. */
  suppressed: SignalSizedRow[];
  /** Sized fine but the risk gate refused it — a result, not an error. */
  rejected: SignalSizedRow[];
  counts: { evaluated: number; proposed: number; suppressed: number; rejected: number };
  note: string;
}

/** OHLC bars for one symbol with our own fills placed on them. */
export interface ExecutionChartResponse {
  symbol: string;
  source: string;
  adjusted: boolean;
  adjustment: string;
  bars: {
    dates: string[];
    open: number[] | null;
    high: number[] | null;
    low: number[] | null;
    close: number[];
    volume: number[] | null;
    /** False when the source gives closes only — candles would be fabricated. */
    has_ohlc: boolean;
    start: string | null;
    end: string | null;
  };
  fills: {
    date: string | null;
    /** A fill outside the fetched window has no bar to sit on. */
    in_window: boolean;
    side: string;
    qty: number;
    price: number;
    strategy_id: string;
    ts: string | null;
  }[];
  n_fills_outside_window: number;
  round_trips: (RoundTrip & { strategy_id: string })[];
}

export const fundApiClient = {
  getNav: async (): Promise<NavResponse> => (await fundApi.get(`${P}/nav`)).data,

  /** What every live strategy currently wants. Reads bars; writes nothing. */
  getSignals: async (): Promise<{ decisions: SignalDecision[] }> =>
    (await fundApi.get(`${P}/signals`, { timeout: 120000 })).data,

  /** Evaluate the strategies and size the trades their signals imply.
   *
   *  `dryRun` (default) writes NOTHING — it returns what would be proposed,
   *  with the share count and price each order would carry. Only pass false to
   *  actually create proposals, and even then they wait for human approval. */
  runSignals: async (dryRun = true, actor = "operator"): Promise<SignalRunResult> =>
    (await fundApi.post(`${P}/signals/run`, { dry_run: dryRun, actor },
      { timeout: 180000 })).data,

  /** Propose ONE order. Passes the risk gate, then waits for approval. */
  proposeOrder: async (body: {
    symbol: string;
    side: "buy" | "sell";
    qty: number;
    venue?: string;
    strategy_id?: string | null;
    thesis_id?: string | null;
    discretionary?: boolean;
    actor?: string;
  }): Promise<{ status: string; order_id: string; breaches?: string[]; impact_preview?: Record<string, number> }> =>
    (await fundApi.post(`${P}/orders/propose`, {
      venue: "alpaca", actor: "operator", ...body,
    })).data,

  /** Candles for a symbol with our fills marked. Fills come from the event log. */
  getExecutionChart: async (
    symbol: string, strategyId?: string, lookbackDays = 180,
  ): Promise<ExecutionChartResponse> =>
    (await fundApi.get(`${P}/executions/chart`, {
      params: { symbol, ...(strategyId ? { strategy_id: strategyId } : {}), lookback_days: lookbackDays },
    })).data,

  /** Fills and closed round-trips, folded from the event log. Read-only. */
  getExecutions: async (strategyId?: string, limit = 500): Promise<
    StrategyExecutions | { strategies: StrategyExecutions[]; totals: ExecutionSummary }
  > =>
    (await fundApi.get(`${P}/executions`, {
      params: { ...(strategyId ? { strategy_id: strategyId } : {}), limit },
    })).data,

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

  /** Approve and send to the venue. The response carries the OUTCOME —
   *  'filled' with the qty and price it actually got, or 'working' if the venue
   *  has it but has not filled it yet. Surface it: an approval that silently
   *  succeeds leaves the operator with no idea what happened to their order. */
  approveOrder: async (orderId: string, approver = 'operator'): Promise<{
    status: 'filled' | 'working' | 'failed' | string;
    order_id: string;
    filled_qty?: number;
    avg_price?: number;
    reason?: string;
  }> =>
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

  /** Constraints imposed from OUTSIDE the mandate — the broker's and the
   *  regulator's, not ours. Distinct from getRiskMonitor: a risk limit is a
   *  number the fund chose and can change; these it cannot. */
  getCompliance: async (): Promise<ComplianceStatus> =>
    (await fundApi.get(`${P}/compliance`)).data,

  /** Which book this spine is reading and writing, and whether orders are real.
   *  The two facts that decide whether anything else on screen is a rehearsal. */
  getBookIdentity: async (): Promise<{
    project_id: string; env: string; is_production: boolean;
    venue?: string; orders_are_real?: boolean; seeder_may_run?: boolean;
  }> => (await fundApi.get(`${P}/book`)).data,

  getEvents: async (limit = 100, sinceSeq = 0): Promise<{ events: SpineEvent[] }> =>
    (await fundApi.get(`${P}/events`, { params: { limit, since_seq: sinceSeq } })).data,

  // --- simulation ---
  simulateRisk: async (body: {
    scenario?: string;
    crude_oil_price?: number;
    yield_10y_bps?: number;
    market_shock_pct?: number;
    vix_spike_pct?: number;
    crypto_shock_pct?: number;
  }): Promise<SimulationResponse> =>
    (await fundApi.post(`${P}/risk/simulate`, body)).data,

  // --- strategy composer methods ---
  setMemberWeight: async (parentId: string, childId: string, weight: number, actor = 'operator'): Promise<StrategyView> =>
    (await fundApi.post(`${P}/strategies/${parentId}/members`, { child_id: childId, weight, actor })).data,

  setMemberWeights: async (parentId: string, weights: Record<string, number>, actor = 'operator'): Promise<StrategyView> =>
    (await fundApi.post(`${P}/strategies/${parentId}/members/weights`, { weights, actor })).data,

  composeWeights: async (
    parentId: string,
    method: 'equal' | 'risk_parity' | 'hrp' | 'max_sharpe' | 'min_volatility' = 'hrp',
    lookbackDays = 365
  ): Promise<ComposeWeightsResponse> =>
    (await fundApi.post(`${P}/strategies/${parentId}/compose/weights`, { method, lookback_days: lookbackDays })).data,

  getComposite: async (parentId: string): Promise<CompositeView> =>
    (await fundApi.get(`${P}/strategies/${parentId}/composite`)).data,

  // --- risk monitor & kill-switch controls ---
  getMarketQuotes: async (): Promise<MarketQuotesResponse> =>
    (await fundApi.get(`${P}/market/quotes`)).data,

  /** Broker-vs-book drift. Read-only — writes no events. */
  getVenueReconcile: async (): Promise<{
    configured: boolean;
    book_nav?: number | null;
    broker_equity?: number | null;
    delta_usd?: number | null;
    delta_pct?: number | null;
    symbols_out_of_sync?: number;
    per_symbol?: { symbol: string; book_qty: number; broker_qty: number; drift: number; in_sync: boolean }[];
    as_of?: string;
    reason?: string;
  }> => (await fundApi.get(`${P}/venue/reconcile`)).data,

  /** Stateless backtest — registers nothing, touches no event log. */
  researchBacktest: async (body: BacktestBySymbolBody): Promise<ResearchBacktestResponse> =>
    (await fundApi.post(`${P}/research/backtest`, body)).data,

  getRiskMonitor: async (): Promise<RiskMonitorResponse> =>
    (await fundApi.get(`${P}/risk/monitor`)).data,

  /** Structural risk: correlation, risk contribution, ES, regime, stress.
   *  Reads market history, so it is slow (seconds) — never poll it tightly. */
  getRiskAdvanced: async (opts?: {
    lookbackDays?: number;
    includeRegime?: boolean;
    includeHistorical?: boolean;
    /** Bypass the server's 30-minute cache. Only for an explicit user action. */
    force?: boolean;
  }): Promise<AdvancedRiskView> =>
    (await fundApi.get(`${P}/risk/advanced`, {
      params: {
        lookback_days: opts?.lookbackDays ?? 250,
        include_regime: opts?.includeRegime ?? true,
        include_historical: opts?.includeHistorical ?? true,
        force: opts?.force ?? false,
      },
      timeout: 180000,
    })).data,

  /** Read-only: what the book WOULD look like at these strategy targets.
   *  Places no orders. */
  riskWhatIf: async (
    targets: Record<string, number>,
    lookbackDays = 250,
  ): Promise<RiskWhatIf> =>
    (await fundApi.post(`${P}/risk/whatif`,
      { targets, lookback_days: lookbackDays }, { timeout: 180000 })).data,

  // --- rebalance: a reviewable batch, not a button ---
  previewRebalance: async (targets: Record<string, number>): Promise<RebalancePlan> =>
    (await fundApi.post(`${P}/rebalance/preview`, { targets })).data,

  proposeRebalance: async (
    targets: Record<string, number>, actor: string, note?: string,
  ): Promise<RebalancePlan> =>
    (await fundApi.post(`${P}/rebalance/propose`, { targets, actor, note },
      { timeout: 180000 })).data,

  getPendingRebalances: async (): Promise<{ pending: RebalancePlan[] }> =>
    (await fundApi.get(`${P}/rebalance/pending`)).data,

  approveRebalance: async (planId: string, approver: string): Promise<RebalanceOutcome> =>
    (await fundApi.post(`${P}/rebalance/${planId}/approve`, { approver },
      { timeout: 180000 })).data,

  declineRebalance: async (planId: string, actor: string, reason?: string): Promise<unknown> =>
    (await fundApi.post(`${P}/rebalance/${planId}/decline`, { actor, reason })).data,

  /** Judge a candidate strategy: is it alpha or factor beta, and does adding it
   *  improve the fund? Stateless — registers nothing. */
  evaluateCandidate: async (body: {
    equity_curve?: number[];
    returns?: number[];
    dates: string[];
    allocation_pct?: number;
  }): Promise<CandidateEvaluation> =>
    (await fundApi.post(`${P}/research/evaluate`, body, { timeout: 180000 })).data,

  /** Register a researched strategy WITH its evidence and queue the sizing for
   *  review. Places no order. */
  promoteCandidate: async (body: {
    name: string;
    symbols: string[];
    definition: Record<string, unknown>;
    backtest?: Record<string, unknown>;
    allocation_pct?: number;
    actor?: string;
    note?: string;
  }): Promise<{ strategy_id: string; queued: boolean; reason?: string; plan?: RebalancePlan }> =>
    (await fundApi.post(`${P}/research/promote`, body, { timeout: 180000 })).data,

  /** Intraday NAV telemetry. NOT struck NAV — in-memory, lost on restart. */
  getIntradayNav: async (minutes = 180): Promise<IntradayNavSeries> =>
    (await fundApi.get(`${P}/nav/intraday`, { params: { minutes } })).data,

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
