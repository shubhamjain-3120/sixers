export interface Config {
  id: number
  total_capital_inr: number
  nifty50_alloc_pct: number
  target_pct: number
  stop_loss_pct: number
  time_stop_days: number
  trail_distance_pct: number
  trail_lock_floor_pct: number
  max_concurrent_positions: number
  min_score_threshold: number
  min_shubham_score_threshold: number
  updated_at: string | null
}

export interface AuthStatus {
  authenticated: boolean
  expires_at: string | null
}

export interface CandidateRow {
  symbol: string
  name: string | null
  segment: 'NIFTY50_STOCK' | 'ETF'
  ltp: number | null
  prev_close: number | null
  pct_change_today: number | null
  high_20d: number | null
  pct_below_20d_high: number | null
  support: number | null
  support_pct_away: number | null
  resistance: number | null
  resistance_pct_away: number | null
  rsi_14: number | null
  score: number
  shubham_score: number | null
  dist_from_20dma_pct: number | null
  dist_from_50dma_pct: number | null
  sparkline_data: number[]
  badge: 'GREEN' | 'YELLOW' | 'RED'
  llm_summary: string | null
  scan_date: string
}

export interface OpenPosition {
  id: number
  symbol: string
  segment: string | null
  entry_date: string
  entry_price: number
  ltp: number | null
  pnl_pct: number | null
  pnl_inr: number | null
  initial_target_price: number | null
  current_sl_price: number | null
  pct_to_target: number | null
  pct_to_sl: number | null
  trailing_state: string
  days_held: number | null
}

export interface ClosedTrade {
  id: number
  symbol: string
  entry_date: string
  exit_date: string | null
  entry_price: number
  exit_price: number | null
  qty: number
  pnl_inr: number | null
  pnl_pct: number | null
  exit_reason: string | null
  days_held: number | null
  badge_at_entry: string | null
  llm_verdict_at_entry: string | null
  pullback_score_at_entry: number | null
  shubham_score_at_entry: number | null
}

export interface StatsSummary {
  open_positions: number
  capital_deployed: number
  capital_available: number
  todays_pnl: number
  this_month_pnl: number
  this_fy_pnl: number
  total_closed_trades: number
  win_rate: number
  avg_win_pct: number
  avg_loss_pct: number
  expectancy_pct: number
  by_exit_reason: {
    target: number
    trailing_stop: number
    stop_loss: number
    time_stop: number
    manual: number
  }
  by_llm_verdict: Record<string, { trades: number; win_rate: number }>
}

export interface EquityPoint {
  date: string
  equity_inr: number
}

export interface PerHeadline {
  idx: number
  headline: string
  classification: 'NOISE' | 'FUNDAMENTAL_NEGATIVE' | 'FUNDAMENTAL_POSITIVE' | 'IRRELEVANT' | string
  reason: string
  published_at: string | null
}

export interface CandidateDetail extends CandidateRow {
  sector: string | null
  pct_below_50d_high: number | null
  volume_ratio: number | null
  swing_low_30d: number | null
  swing_high_30d: number | null
  green_after_red: boolean | null
  news_verdict: string | null
  news_confidence: number | null
  news_headlines: PerHeadline[]
}

export interface ScanStatus {
  last_scan_at: string | null
  candidate_count: number
  running: boolean
}

export interface OhlcvBar {
  date: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
}

export interface BlockDealOut {
  deal_date: string
  client_name: string | null
  deal_type: string | null
  quantity: number | null
  price: number | null
  source: string | null
}

export interface TradeDetail extends ClosedTrade {
  segment: string | null
  capital_deployed: number
  initial_target_price: number | null
  initial_sl_price: number | null
  current_sl_price: number | null
  high_water_mark: number | null
  trailing_state: string | null
  notes: string | null
  ltp_at_entry: number | null
  rsi_at_entry: number | null
  pct_below_20d_high_at_entry: number | null
  pct_below_50d_high_at_entry: number | null
  dist_from_20dma_at_entry: number | null
  dist_from_50dma_at_entry: number | null
  volume_ratio_at_entry: number | null
  swing_low_at_entry: number | null
  swing_high_at_entry: number | null
  pivot_support_at_entry: number | null
  pivot_resistance_at_entry: number | null
  green_after_red_at_entry: boolean | null
  ohlcv: OhlcvBar[]
}
