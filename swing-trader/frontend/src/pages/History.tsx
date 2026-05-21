import { useEffect, useState } from 'react'
import { getClosedTrades, getStatsSummary, getEquityCurve } from '../api/client'
import type { ClosedTrade, StatsSummary, EquityPoint } from '../types'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { format } from 'date-fns'

export default function History() {
  const [trades, setTrades] = useState<ClosedTrade[]>([])
  const [stats, setStats] = useState<StatsSummary | null>(null)
  const [equity, setEquity] = useState<EquityPoint[]>([])

  useEffect(() => {
    getClosedTrades().then(setTrades).catch(() => {})
    getStatsSummary().then(setStats).catch(() => {})
    getEquityCurve(90).then(setEquity).catch(() => {})
  }, [])

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold text-white mb-6">Trade History</h1>

      {/* Stats summary */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <StatCard label="Total Trades" value={stats.total_closed_trades.toString()} />
          <StatCard label="Win Rate" value={`${(stats.win_rate * 100).toFixed(1)}%`} color={stats.win_rate >= 0.5 ? 'text-green-400' : 'text-red-400'} />
          <StatCard label="Avg Win" value={`+${stats.avg_win_pct.toFixed(2)}%`} color="text-green-400" />
          <StatCard label="Avg Loss" value={`${stats.avg_loss_pct.toFixed(2)}%`} color="text-red-400" />
          <StatCard label="Expectancy" value={`${stats.expectancy_pct.toFixed(2)}%`} color={stats.expectancy_pct >= 0 ? 'text-green-400' : 'text-red-400'} />
          <StatCard label="Target hits" value={stats.by_exit_reason.target.toString()} />
          <StatCard label="Trail stops" value={stats.by_exit_reason.trailing_stop.toString()} />
          <StatCard label="Stop losses" value={stats.by_exit_reason.stop_loss.toString()} />
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
              {['Symbol', 'Entry', 'Exit', 'Entry ₹', 'Exit ₹', 'P&L%', 'Days', 'Reason', 'Badge'].map(h => (
                <th key={h} className="px-3 py-2 text-left">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trades.map(t => {
              const pnl = t.pnl_pct ?? 0
              const pnlColor = pnl >= 0 ? 'text-green-400' : 'text-red-400'
              return (
                <tr key={t.id} className="border-t border-gray-800 hover:bg-gray-900/50">
                  <td className="px-3 py-2 font-semibold text-white">{t.symbol}</td>
                  <td className="px-3 py-2 text-gray-400">{t.entry_date ? format(new Date(t.entry_date), 'dd MMM') : '–'}</td>
                  <td className="px-3 py-2 text-gray-400">{t.exit_date ? format(new Date(t.exit_date), 'dd MMM') : '–'}</td>
                  <td className="px-3 py-2">₹{t.entry_price.toFixed(1)}</td>
                  <td className="px-3 py-2">{t.exit_price ? `₹${t.exit_price.toFixed(1)}` : '–'}</td>
                  <td className={`px-3 py-2 font-mono ${pnlColor}`}>{pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}%</td>
                  <td className="px-3 py-2 text-gray-400">{t.days_held ?? '–'}</td>
                  <td className="px-3 py-2 text-xs text-gray-500">{t.exit_reason ?? '–'}</td>
                  <td className="px-3 py-2 text-xs">
                    {t.badge_at_entry && (
                      <span className={t.badge_at_entry === 'GREEN' ? 'text-green-400' : t.badge_at_entry === 'RED' ? 'text-red-400' : 'text-yellow-400'}>
                        {t.badge_at_entry}
                      </span>
                    )}
                  </td>
                </tr>
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

function StatCard({ label, value, color = 'text-white' }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-lg font-bold font-mono ${color}`}>{value}</div>
    </div>
  )
}
