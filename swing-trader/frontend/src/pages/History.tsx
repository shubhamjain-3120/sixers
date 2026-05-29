import { useEffect, useState } from 'react'
import { getClosedTrades, getStatsSummary, getEquityCurve, getTradeDetail } from '../api/client'
import type { ClosedTrade, StatsSummary, EquityPoint, TradeDetail } from '../types'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  ComposedChart, Bar, ReferenceLine,
} from 'recharts'
import { format } from 'date-fns'

export default function History() {
  const [trades, setTrades] = useState<ClosedTrade[]>([])
  const [stats, setStats] = useState<StatsSummary | null>(null)
  const [equity, setEquity] = useState<EquityPoint[]>([])
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<TradeDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    getClosedTrades().then(setTrades).catch(() => {})
    getStatsSummary().then(setStats).catch(() => {})
    getEquityCurve(90).then(setEquity).catch(() => {})
  }, [])

  function toggleDetail(id: number) {
    if (expandedId === id) {
      setExpandedId(null)
      setDetail(null)
      return
    }
    setExpandedId(id)
    setDetail(null)
    setDetailLoading(true)
    getTradeDetail(id)
      .then(d => { setDetail(d); setDetailLoading(false) })
      .catch(() => setDetailLoading(false))
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold text-white mb-6">Trade History</h1>

      {/* Stats summary */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <StatCard label="Total Trades" value={stats.total_closed_trades.toString()} />
          <StatCard label="Win Rate" value={`${(stats.win_rate * 100).toFixed(1)}%`}
            color={stats.win_rate >= 0.5 ? 'text-green-400' : 'text-red-400'} />
          <StatCard label="Avg Win" value={`+${stats.avg_win_pct.toFixed(2)}%`} color="text-green-400" />
          <StatCard label="Avg Loss" value={`${stats.avg_loss_pct.toFixed(2)}%`} color="text-red-400" />
          <StatCard label="Expectancy" value={`${stats.expectancy_pct.toFixed(2)}%`}
            color={stats.expectancy_pct >= 0 ? 'text-green-400' : 'text-red-400'} />
          <StatCard label="Target hits" value={stats.by_exit_reason.target.toString()} />
          <StatCard label="Stop losses" value={stats.by_exit_reason.stop_loss.toString()} />
        </div>
      )}

      {/* By LLM verdict breakdown */}
      {stats && Object.keys(stats.by_llm_verdict).length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-6">
          <h2 className="text-xs text-gray-400 uppercase mb-3">Win rate by LLM verdict</h2>
          <div className="flex flex-wrap gap-4">
            {Object.entries(stats.by_llm_verdict).map(([verdict, vs]) => (
              <div key={verdict} className="text-sm">
                <span className="text-gray-500">{verdict}: </span>
                <span className="text-white font-mono">{vs.trades} trades</span>
                <span className="text-gray-500 mx-1">·</span>
                <span className={vs.win_rate >= 0.5 ? 'text-green-400' : 'text-red-400'}>
                  {(vs.win_rate * 100).toFixed(0)}% WR
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Equity curve */}
      {equity.length > 1 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-6">
          <h2 className="text-sm text-gray-400 mb-3">Equity Curve (90d)</h2>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={equity}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 10 }} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #374151', color: '#fff' }}
                formatter={(v: number) => [`₹${v.toLocaleString('en-IN')}`, 'P&L']}
              />
              <Line type="monotone" dataKey="equity_inr" stroke="#3b82f6" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Trade table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border border-gray-800 rounded-lg overflow-hidden">
          <thead className="bg-gray-900 text-gray-400 text-xs uppercase">
            <tr>
              <th className="px-3 py-2 w-6" />
              {['Symbol', 'Entry', 'Exit', 'Entry ₹', 'Exit ₹', 'P&L%', 'P&L ₹', 'Days', 'Reason', 'Pull', 'Shub'].map(h => (
                <th key={h} className="px-3 py-2 text-left">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trades.map(t => {
              const pnl = t.pnl_pct ?? 0
              const pnlColor = pnl >= 0 ? 'text-green-400' : 'text-red-400'
              const isExpanded = expandedId === t.id
              return (
                <>
                  <tr
                    key={t.id}
                    className={`border-t border-gray-800 cursor-pointer transition-colors ${isExpanded ? 'bg-gray-900' : 'hover:bg-gray-900/50'}`}
                    onClick={() => toggleDetail(t.id)}
                  >
                    <td className="px-3 py-2 text-gray-600 text-xs">{isExpanded ? '▲' : '▶'}</td>
                    <td className="px-3 py-2 font-semibold text-white">{t.symbol}</td>
                    <td className="px-3 py-2 text-gray-400">{t.entry_date ? format(new Date(t.entry_date), 'dd MMM') : '–'}</td>
                    <td className="px-3 py-2 text-gray-400">{t.exit_date ? format(new Date(t.exit_date), 'dd MMM') : '–'}</td>
                    <td className="px-3 py-2">₹{t.entry_price.toFixed(1)}</td>
                    <td className="px-3 py-2">{t.exit_price ? `₹${t.exit_price.toFixed(1)}` : '–'}</td>
                    <td className={`px-3 py-2 font-mono ${pnlColor}`}>{pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}%</td>
                    <td className={`px-3 py-2 font-mono ${pnlColor}`}>
                      {t.pnl_inr != null ? `${t.pnl_inr >= 0 ? '+' : ''}₹${t.pnl_inr.toFixed(0)}` : '–'}
                    </td>
                    <td className="px-3 py-2 text-gray-400">{t.days_held ?? '–'}</td>
                    <td className="px-3 py-2 text-xs text-gray-500">{t.exit_reason ?? '–'}</td>
                    <td className="px-3 py-2 font-mono text-blue-300">
                      {t.pullback_score_at_entry != null ? t.pullback_score_at_entry.toFixed(0) : '–'}
                    </td>
                    <td className="px-3 py-2 font-mono text-purple-300">
                      {t.shubham_score_at_entry != null ? t.shubham_score_at_entry.toFixed(0) : '–'}
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr key={`${t.id}-detail`} className="border-t border-gray-800 bg-gray-950">
                      <td colSpan={12} className="p-4">
                        {detailLoading && <p className="text-gray-500 text-sm">Loading...</p>}
                        {detail && detail.id === t.id && <TradeDetailPanel detail={detail} />}
                      </td>
                    </tr>
                  )}
                </>
              )
            })}
          </tbody>
        </table>
        {trades.length === 0 && (
          <p className="text-gray-600 text-sm text-center py-8">No closed trades yet.</p>
        )}
      </div>
    </div>
  )
}

function TradeDetailPanel({ detail }: { detail: TradeDetail }) {
  const chartData = detail.ohlcv.map(b => ({
    date: b.date,
    // recharts Bar needs [low, high] as a range — encode as [open, close] for candle-like bars
    range: [b.low, b.high] as [number, number],
    body: [Math.min(b.open ?? 0, b.close ?? 0), Math.max(b.open ?? 0, b.close ?? 0)] as [number, number],
    close: b.close,
    isGreen: (b.close ?? 0) >= (b.open ?? 0),
  }))

  const hasChart = chartData.length > 1

  return (
    <div className="flex flex-col gap-4">
      {/* Key levels */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <InfoCell label="Qty" value={detail.qty.toString()} />
        <InfoCell label="Capital" value={`₹${detail.capital_deployed.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`} />
        <InfoCell label="Initial target" value={detail.initial_target_price ? `₹${detail.initial_target_price.toFixed(1)}` : '–'} />
        <InfoCell label="Initial SL" value={detail.initial_sl_price ? `₹${detail.initial_sl_price.toFixed(1)}` : '–'} />
        <InfoCell label="LLM verdict" value={detail.llm_verdict_at_entry ?? '–'} />
        {detail.notes && <InfoCell label="Notes" value={detail.notes} />}
      </div>

      {/* Price chart with entry/exit/target/SL reference lines */}
      {hasChart && (
        <div>
          <p className="text-xs text-gray-500 mb-2">Close price · {detail.symbol} · entry→exit</p>
          <ResponsiveContainer width="100%" height={160}>
            <ComposedChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 9 }} interval="preserveStartEnd" />
              <YAxis
                tick={{ fill: '#6b7280', fontSize: 9 }}
                domain={['auto', 'auto']}
                width={55}
                tickFormatter={(v: number) => `₹${v.toFixed(0)}`}
              />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #374151', color: '#fff', fontSize: 11 }}
                formatter={(v: number) => [`₹${v.toFixed(1)}`]}
              />
              <Line type="monotone" dataKey="close" stroke="#60a5fa" dot={false} strokeWidth={1.5} />
              {detail.entry_price && (
                <ReferenceLine y={detail.entry_price} stroke="#facc15" strokeDasharray="4 2"
                  label={{ value: 'Entry', fill: '#facc15', fontSize: 9, position: 'insideTopLeft' }} />
              )}
              {detail.initial_target_price && (
                <ReferenceLine y={detail.initial_target_price} stroke="#4ade80" strokeDasharray="4 2"
                  label={{ value: 'Target', fill: '#4ade80', fontSize: 9, position: 'insideTopLeft' }} />
              )}
              {detail.initial_sl_price && (
                <ReferenceLine y={detail.initial_sl_price} stroke="#f87171" strokeDasharray="4 2"
                  label={{ value: 'SL', fill: '#f87171', fontSize: 9, position: 'insideTopLeft' }} />
              )}
              {detail.exit_price && (
                <ReferenceLine y={detail.exit_price} stroke="#c084fc" strokeDasharray="4 2"
                  label={{ value: 'Exit', fill: '#c084fc', fontSize: 9, position: 'insideBottomLeft' }} />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
      {!hasChart && (
        <p className="text-xs text-gray-600">No OHLCV data available for this trade period.</p>
      )}
    </div>
  )
}

function InfoCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-sm text-white font-mono">{value}</div>
    </div>
  )
}

function StatCard({ label, value, color = 'text-white' }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-lg font-bold font-mono ${color}`}>{value}</div>
    </div>
  )
}
