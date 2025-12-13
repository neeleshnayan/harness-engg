export interface BacktestRequest {
  strategy: 'conservative' | 'aggressive'
  start_date: string
  end_date: string
  initial_capital: number
  rebalance_frequency: string
}

export interface BacktestMetrics {
  total_return: number
  annualized_return: number
  volatility: number
  sharpe_ratio: number
  max_drawdown: number
  calmar_ratio: number
  win_rate: number
  best_month: number
  worst_month: number
  total_trades?: number | null
  winning_trades?: number | null
  losing_trades?: number | null
  avg_trade_return?: number | null
}

export interface BacktestAllocation {
  symbol: string
  allocation_percentage: number
  final_value: number
  total_return: number
}

export interface BacktestTrade {
  trade_number: number
  entry_date: string
  exit_date: string
  entry_price: number
  exit_price: number
  size: number
  pnl: number
  return_pct: number
  duration_days: number
  is_win: boolean
}

export interface TechnicalIndicators {
  sma_30?: number
  sma_100?: number
  sma_200?: number
  rsi?: number
  rsi_overbought: boolean
  rsi_oversold: boolean
  stochastic_rsi?: number
  stochastic_rsi_k?: number
  stochastic_rsi_d?: number
  stochastic_rsi_overbought: boolean
  stochastic_rsi_oversold: boolean
  bb_upper?: number
  bb_middle?: number
  bb_lower?: number
  bb_upper_break: boolean
  bb_lower_break: boolean
  macd?: number
  macd_signal?: number
  macd_histogram?: number
  macd_cross_up: boolean
  macd_cross_down: boolean
  adx?: number
  adx_strong_trend: boolean
  adx_weak_trend: boolean
  adx_plus_dmi?: number
  adx_minus_dmi?: number
  super_trend?: number
  super_trend_direction?: string
  super_trend_buy_signal: boolean
  super_trend_sell_signal: boolean
  current_price?: number
  entry_price?: number
  profit_percentage?: number
}

export interface BacktestDataPoint {
  date: string
  portfolio_value: number
  daily_return: number
  cumulative_return: number
  technical_indicators?: TechnicalIndicators
}

export interface CandleDataPoint {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume?: number | null
}

export interface CandleData {
  symbol: string
  candles: CandleDataPoint[]
}

export interface BacktestResult {
  success: boolean
  message: string
  strategy: string
  start_date: string
  end_date: string
  initial_capital: number
  final_capital: number
  total_days: number
  metrics: BacktestMetrics
  allocations: BacktestAllocation[]
  data_points: BacktestDataPoint[]
  include_technical_analysis: boolean
  technical_indicators_requested: string[]
  target_assets: string[]
  show_performance_stats: boolean
  trades: BacktestTrade[]
  candle_data?: CandleData[]
}

export interface ScreenerResult {
  screener_type: string
  range: string
  range_description: string
  total_found: number
  results: ScreenerCrypto[]
}

export interface ScreenerCrypto {
  symbol: string
  name: string
  price: number
  daily_change_percent: number
  market_cap: number
  volume_24h: number
  rank?: number
  high_52w?: number
  low_52w?: number
  percent_from_high?: number
  percent_from_low?: number
  rsi?: number
  sma_50?: number
  sma_200?: number
  ema_5?: number
  ema_10?: number
  // Stock-specific fields
  sector?: string
  industry?: string
  exchange?: string
  ceo?: string
  website?: string
  description?: string
  day_low?: number
  day_high?: number
  year_low?: number
  year_high?: number
}

export interface EconomicData {
  country: string
  indicator: string
  value: number | null
  previous_value?: number | null
  date?: string
  category?: string
  unit?: string
  frequency?: string
}

export interface EconomicResult {
  screener_type?: string
  indicator?: string
  indicator_name?: string
  total_found?: number
  results?: EconomicData[] | NewsData[] | CalendarData[]
  markdown?: string // For economic agent responses with markdown content
  raw_fmp?: any // Raw FMP data
  economic_data?: boolean // Flag to indicate economic data is present
}

export interface NewsData {
  id?: string
  title: string
  description?: string
  date: string
  country?: string
  category?: string
  url?: string
  importance?: number
}

export interface CalendarData {
  event_id?: string
  date: string
  country: string
  category: string
  event: string
  reference?: string
  source?: string
  actual?: number | null
  previous?: number | null
  forecast?: number | null
  te_forecast?: number | null
  url?: string
  importance?: number
  last_update?: string
}

export interface RegulationMatch {
  title: string
  url?: string
  source_title?: string
  description?: string
  snippet: string
  jurisdiction?: string
  score: number
}

export interface RegulationResult {
  query: string
  topic?: string | null
  jurisdiction?: string | null
  summary?: string
  matches: RegulationMatch[]
}

export interface ParameterMeta {
  description?: string
  example?: string
  type?: string
  label?: string
}

export interface ParameterRequest {
  service: string
  actionType?: string
  prompt?: string
  missingParameters: Record<string, ParameterMeta>
  receivedParameters: Record<string, unknown>
  requiredParameters: Record<string, ParameterMeta>
  context?: Record<string, unknown>
}

export interface AgentFlowStep {
  id: string
  name: string
  type: 'orchestrator' | 'specialized' | 'start' | 'end'
  tool_name?: string
  status: 'completed' | 'pending' | 'error' | 'failed' | 'in_progress'
  color?: string
  timestamp?: string | null
  timestamp_start?: string  // ISO timestamp when agent execution started
  timestamp_end?: string    // ISO timestamp when agent execution ended
  latency_ms?: number       // Execution latency in milliseconds
  input?: string  // Agent-specific query/input
  output?: {      // Agent result summary
    success: boolean
    message: string
    has_data: boolean
    data_keys?: string[] | null
    data?: any    // Full data returned by the agent
  }
}

export interface AgentFlowEdge {
  from: string
  to: string
}

export interface AgentFlowGraph {
  nodes: AgentFlowStep[]
  edges: AgentFlowEdge[]
  execution_order: string[]
  flow_type: 'single' | 'sequential' | 'parallel'
  steps: AgentFlowStep[]  // Flattened array for backwards compatibility
}

export interface AgentFlowEdge {
  from: string
  to: string
}

export interface AgentFlowGraph {
  nodes: AgentFlowStep[]
  edges: AgentFlowEdge[]
  execution_order: string[]
  flow_type: 'single' | 'sequential' | 'parallel'
  steps: AgentFlowStep[]  // Flattened array for backwards compatibility
}

export interface ChatMessage {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: Date
  parsedIntent?: any
  success?: boolean
  backtestResult?: BacktestResult
  screenerResult?: ScreenerResult
  economicResult?: EconomicResult
  regulationResult?: RegulationResult
  source?: string
  capabilitiesSummary?: string
  parameterRequest?: ParameterRequest
  agentFlow?: AgentFlowGraph | AgentFlowStep[]  // Support both old array and new graph format
}

export interface Category {
  id: string
  title: string
  icon: string
  description: string
  prompts: string[]
}
