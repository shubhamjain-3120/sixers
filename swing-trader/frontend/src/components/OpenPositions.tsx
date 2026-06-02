import { useEffect, useState, useCallback } from 'react'
import { getOpenPositions, forceExit } from '../api/client'
import type { OpenPosition } from '../types'
import PositionDetailModal from './PositionDetailModal'

function pctColor(v: number | null) {
  if (v == null) return 'text-gray-600 dark:text-gray-400'
  return v >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
}

function fmtPct(v: number | null, plus = false) {
  if (v == null) return '–'
  return `${plus && v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

function fmtInr(v: number | null) {
  if (v == null) return '–'
  return `${v >= 0 ? '+' : ''}₹${Math.abs(v).toFixed(0)}`
}

export default function OpenPositions({ onTradeChange }: { onTradeChange?: () => void }) {
  const [positions, setPositions] = useState<OpenPosition[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getOpenPositions()
      setPositions(data)
    } catch {}
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 60_000)
    return () => clearInterval(t)
  }, [load])

  const handleForceExit = async (id: number, symbol: string) => {
    if (!confirm(`Force exit ${symbol}? This places a market sell order immediately.`)) return
    try {
      await forceExit(id)
      load()
      onTradeChange?.()
    } catch (e: any) {
      alert(`Force exit failed: ${e?.response?.data?.detail || e.message}`)
    }
  }

  if (!positions.length) return null

  return (
    <section className="mb-6">
      {selectedId !== null && (
        <PositionDetailModal tradeId={selectedId} onClose={() => setSelectedId(null)} />
      )}
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider">
          Open Positions ({positions.length})
        </h2>
        <button
          onClick={() => { load(); onTradeChange?.() }}
          disabled={loading}
          className="text-xs px-2 py-1 rounded border border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-40"
        >
          {loading ? 'Refreshing…' : '↻ Refresh'}
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border border-gray-200 dark:border-gray-800 rounded-lg overflow-hidden">
          <thead className="bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-400 text-xs uppercase">
            <tr>
              {['Symbol', 'Entry', 'LTP', 'P&L%', 'P&L ₹', 'Target', '→ Target', '→ SL', 'Days', ''].map(h => (
                <th key={h} className="px-3 py-2 text-left whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {positions.map(p => (
              <tr
                key={p.id}
                className="border-t border-gray-200 dark:border-gray-800 hover:bg-white dark:hover:bg-gray-900/50 cursor-pointer"
                onClick={() => setSelectedId(p.id)}
              >
                <td className="px-3 py-2 font-semibold text-gray-900 dark:text-white">{p.symbol}</td>
                <td className="px-3 py-2 text-gray-700 dark:text-gray-300">₹{p.entry_price.toFixed(1)}</td>
                <td className="px-3 py-2 text-gray-900 dark:text-white font-mono">
                  {p.ltp ? `₹${p.ltp.toFixed(1)}` : '–'}
                </td>
                <td className={`px-3 py-2 font-mono ${pctColor(p.pnl_pct)}`}>
                  {fmtPct(p.pnl_pct, true)}
                </td>
                <td className={`px-3 py-2 font-mono ${pctColor(p.pnl_inr)}`}>
                  {fmtInr(p.pnl_inr)}
                </td>
                <td className="px-3 py-2 text-green-600 dark:text-green-500">
                  {p.initial_target_price ? `₹${p.initial_target_price.toFixed(1)}` : '–'}
                </td>
                <td className="px-3 py-2 text-green-600 dark:text-green-400 font-mono text-xs">
                  {fmtPct(p.pct_to_target, true)}
                </td>
                <td className="px-3 py-2 text-red-600 dark:text-red-400 font-mono text-xs">
                  {fmtPct(p.pct_to_sl)}
                </td>
                <td className="px-3 py-2 text-gray-600 dark:text-gray-400">{p.days_held ?? '–'}</td>
                <td className="px-3 py-2">
                  <button
                    onClick={e => { e.stopPropagation(); handleForceExit(p.id, p.symbol) }}
                    className="text-xs px-2 py-1 rounded border border-red-300 dark:border-red-800 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 whitespace-nowrap"
                  >
                    Exit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
