import axios from 'axios'
import type { Config, AuthStatus, CandidateRow, CandidateDetail, OhlcvBar, BlockDealOut, OpenPosition, ClosedTrade, TradeDetail, StatsSummary, EquityPoint, PerHeadline } from '../types'

// VITE_API_URL is set at build time on Render (e.g. https://swing-trader-api.fly.dev).
// In local dev it is unset, so requests fall through to Vite's proxy → localhost:8000.
const api = axios.create({ baseURL: (import.meta.env.VITE_API_URL ?? '') + '/api' })

// Auth
export const getAuthStatus = () => api.get<AuthStatus>('/auth/status').then(r => r.data)
export const getKiteLoginUrl = () => api.get<{ login_url: string }>('/auth/kite/login').then(r => r.data)

// Config
export const getConfig = () => api.get<Config>('/config').then(r => r.data)
export const updateConfig = (data: Partial<Config>) => api.put<Config>('/config', data).then(r => r.data)

// Universe
export const refreshUniverse = () => api.post('/universe/refresh').then(r => r.data)

// Scan
export const getScanStatus = () => api.get<import('../types').ScanStatus>('/scan/status').then(r => r.data)
export const getCandidates = (includeRed = false) =>
  api.get<CandidateRow[]>('/scan/candidates', { params: { include_red: includeRed } }).then(r => r.data)
export const getCandidateDetail = (symbol: string) =>
  api.get<CandidateDetail>(`/scan/detail/${symbol}`).then(r => r.data)
export const getOhlcv = (symbol: string, days = 90) =>
  api.get<OhlcvBar[]>(`/scan/ohlcv/${symbol}`, { params: { days } }).then(r => r.data)
export const getBlockDeals = (symbol: string) =>
  api.get<BlockDealOut[]>(`/scan/block-deals/${symbol}`).then(r => r.data)
export const triggerScan = () => api.post('/scan/run').then(r => r.data)
export const getLiveLtp = (symbols: string[]) =>
  api.get<Record<string, number>>('/scan/ltp', { params: { symbols: symbols.join(',') } }).then(r => r.data)

// Trades
export const getOpenPositions = () => api.get<OpenPosition[]>('/trades/open').then(r => r.data)
export const getClosedTrades = () => api.get<ClosedTrade[]>('/trades/closed').then(r => r.data)
export const getTradeDetail = (tradeId: number) => api.get<TradeDetail>(`/trades/${tradeId}`).then(r => r.data)
export const placeTrade = (symbol: string, customCapital?: number) => api.post('/trades', { symbol, custom_capital: customCapital }).then(r => r.data)
export const forceExit = (tradeId: number) => api.post(`/trades/${tradeId}/force-exit`).then(r => r.data)

// Stats
export const getStatsSummary = () => api.get<StatsSummary>('/stats/summary').then(r => r.data)
export const getEquityCurve = (days = 90) => api.get<EquityPoint[]>('/stats/equity-curve', { params: { days } }).then(r => r.data)

// Telegram
export const testTelegram = () => api.post('/telegram/test').then(r => r.data)

// System
export const triggerPositionCycle = () => api.post('/system/position-cycle').then(r => r.data)
export const triggerTimestop = () => api.post('/system/time-stop').then(r => r.data)
export const triggerNewsClassify = () => api.post('/system/news-classify').then(r => r.data)
export const getHealth = () => api.get('/system/health').then(r => r.data)

// News
export interface TestClassifyRequest {
  symbol: string
  company_name?: string
  sector?: string
  headlines: string[]
  block_flag?: boolean
  sector_flag?: boolean
  ltp?: number
  pct_drop?: number
}
export interface TestClassifyResponse {
  verdict: string
  confidence: number
  summary: string
  per_headline: Array<{ idx: number; classification: string; reason: string }>
  badge: string
  block_flag: boolean
  sector_flag: boolean
}
export const testClassify = (req: TestClassifyRequest) =>
  api.post<TestClassifyResponse>('/news/test-classify', req).then(r => r.data)
