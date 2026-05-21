import { useEffect, useState, useCallback } from 'react'
import { getOpenPositions, forceExit } from '../api/client'
import type { OpenPosition } from '../types'

function pctColor(v: number | null) {
  if (v == null) return 'text-gray-400'
  return v >= 0 ? 'text-green-400' : 'text-red-400'
}

function fmtPct(v: number | null, plus = false) {
  if (v == null) return '–'
  return `${plus && v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

export default function OpenPositions() {
  const [positions, setPositions] = useState<OpenPosition[]>([])
  const [loading, setLoading] = useState(false)

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
    } catch (e: any) {
      alert(`Force exit failed: ${e?.response?.data?.detail || e.message}`)
    }
  }

  if (!positions.length) return null

  return (
    <section className="mb-6">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
          Open Positions ({positions.length})
        </h2>
        <button
          onClick={load}
          disabled={loading}
          className="text-xs px-2 py-1 rounded border border-gray-700 text-gray-400 hover:bg-gray-800 disabled:opacity-40"
        >
          {loading ? 'Refreshing…' : '↻ Refresh'}
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border border-gray-800 rounded-lg overflow-hidden">
          <thead className="bg-gray-900 text-gray-400 text-xs uppercase">
            <tr>
              {['Symbol', 'Entry', 'LTP', 'P&L%', 'Target', '→ Target', 'Curr SL', '→ SL', 'Days', 'State', ''].map(h => (
                <th key={h} className="px-3 py-2 text-left whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {positions.map(p => (
              <tr key={p.id} className="border-t border-gray-800 hover:bg-gray-900/50">
                <td className="px-3 py-2 font-semibold text-white">{p.symbol}</td>
                <td className="px-3 py-2 text-gray-300">₹{p.entry_price.toFixed(1)}</td>
                <td className="px-3 py-2 text-white font-mono">
                  {p.ltp ? `₹${p.ltp.toFixed(1)}` : '–'}
                </td>
                <td className={`px-3 py-2 font-mono ${pctColor(p.pnl_pct)}`}>
                  {fmtPct(p.pnl_pct, true)}
                </td>
                <td className="px-3 py-2 text-green-500">
                  {p.initial_target_price ? `₹${p.initial_target_price.toFixed(1)}` : '–'}
                </td>
                <td className="px-3 py-2 text-green-400 font-mono text-xs">
                  {fmtPct(p.pct_to_target, true)}
                </td>
                <td className="px-3 py-2 text-red-400">
                  {p.current_sl_price ? `₹${p.current_sl_price.toFixed(1)}` : '–'}
                </td>
                <td className="px-3 py-2 text-red-400 font-mono text-xs">
                  {fmtPct(p.pct_to_sl)}
                </td>
                <td className="px-3 py-2 text-gray-400">{p.days_held ?? '–'}</td>
                <td className="px-3 py-2 text-xs">
                  <span className={p.trailing_state === 'trailing' ? 'text-blue-400' : 'text-gray-500'}>
                    {p.trailing_state}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <button
                    onClick={() => handleForceExit(p.id, p.symbol)}
                    className="text-xs px-2 py-1 rounded border border-red-800 text-red-400 hover:bg-red-900/30 whitespace-nowrap"
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
