import { useEffect, useState } from 'react'
import { getCandidates, getScanStatus } from '../api/client'
import type { CandidateRow, ScanStatus } from '../types'
import CandidateRowComponent from './CandidateRow'

export default function CandidatesTable() {
  const [candidates, setCandidates] = useState<CandidateRow[]>([])
  const [sortBy, setSortBy] = useState<'score' | 'shubham_score' | 'pct_change'>('shubham_score')
  const [loading, setLoading] = useState(true)
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [data, status] = await Promise.all([getCandidates(), getScanStatus()])
      setCandidates(data)
      setScanStatus(status)
      setLastRefresh(new Date())
    } catch {
      /* no-op */
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const sorted = [...candidates].sort((a, b) => {
    if (sortBy === 'score') return b.score - a.score
    if (sortBy === 'shubham_score') return (b.shubham_score ?? -1) - (a.shubham_score ?? -1)
    return (b.pct_change_today ?? 0) - (a.pct_change_today ?? 0)
  })

  return (
    <section>
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
          Today's Candidates
        </h2>
        <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500 ml-auto">
          {scanStatus?.last_scan_at && (
            <span>Last scan: <span className="text-gray-400">{scanStatus.last_scan_at}</span></span>
          )}
          {lastRefresh && (
            <span>Refreshed: <span className="text-gray-400">{lastRefresh.toLocaleTimeString()}</span></span>
          )}
          <button
            onClick={load}
            disabled={loading}
            className="px-2 py-1 rounded border border-gray-700 hover:border-gray-500 text-gray-400 hover:text-gray-200 disabled:opacity-40 transition-colors"
          >
            {loading ? '…' : '↻'}
          </button>
        </div>
        <div className="flex gap-2">
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value as any)}
            className="bg-gray-800 border border-gray-700 rounded text-xs text-gray-300 px-2 py-1"
          >
            <option value="score">Sort: Pullback</option>
            <option value="shubham_score">Sort: Shubham</option>
            <option value="pct_change">Sort: % Change</option>
          </select>
        </div>
      </div>

      {loading ? (
        <p className="text-gray-500 text-sm">Loading candidates…</p>
      ) : sorted.length === 0 ? (
        <p className="text-gray-600 text-sm">No candidates above threshold. Run a scan or check back after 15:45 IST.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-max text-sm">
            <thead>
              <tr className="border-b border-gray-700 text-gray-500 text-xs uppercase tracking-wider">
                <th className="py-2 pl-3 pr-4 text-center">Scrip</th>
                <th className="py-2 pr-4 text-center">LTP</th>
                <th className="py-2 pr-4 text-center">20DH</th>
                <th className="py-2 pr-4 text-center">20DMA</th>
                <th className="py-2 pr-4 text-center">50DMA</th>
                <th className="py-2 pr-4 text-center">Support</th>
                <th className="py-2 pr-4 text-center">Resistance</th>
                <th className="py-2 pr-4 text-center">Pullback</th>
                <th className="py-2 pr-4 text-center">Shubham</th>
                <th className="py-2 pl-2 pr-4 text-center min-w-[70px]"></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(c => (
                <CandidateRowComponent key={c.symbol} candidate={c} onOrderPlaced={load} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
