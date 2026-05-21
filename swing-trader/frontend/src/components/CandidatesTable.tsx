import { useEffect, useState } from 'react'
import { getCandidates } from '../api/client'
import type { CandidateRow } from '../types'
import CandidateRowComponent from './CandidateRow'

export default function CandidatesTable() {
  const [candidates, setCandidates] = useState<CandidateRow[]>([])
  const [showRed, setShowRed] = useState(false)
  const [sortBy, setSortBy] = useState<'score' | 'pct_change'>('score')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const data = await getCandidates(showRed)
      setCandidates(data)
    } catch {
      /* no-op */
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [showRed])

  const sorted = [...candidates].sort((a, b) => {
    if (sortBy === 'score') return b.score - a.score
    return (b.pct_change_today ?? 0) - (a.pct_change_today ?? 0)
  })

  const greenCount = candidates.filter(c => c.badge === 'GREEN').length
  const yellowCount = candidates.filter(c => c.badge === 'YELLOW').length
  const redCount = candidates.filter(c => c.badge === 'RED').length

  return (
    <section>
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
          Today's Candidates
          <span className="ml-2 text-gray-600 font-normal normal-case">
            🟢{greenCount} 🟡{yellowCount} 🔴{redCount}
          </span>
        </h2>
        <div className="flex gap-2 ml-auto">
          <label className="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={showRed}
              onChange={e => setShowRed(e.target.checked)}
              className="accent-red-500"
            />
            Show RED
          </label>
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value as any)}
            className="bg-gray-800 border border-gray-700 rounded text-xs text-gray-300 px-2 py-1"
          >
            <option value="score">Sort: Score</option>
            <option value="pct_change">Sort: % Change</option>
          </select>
        </div>
      </div>

      {loading ? (
        <p className="text-gray-500 text-sm">Loading candidates…</p>
      ) : sorted.length === 0 ? (
        <p className="text-gray-600 text-sm">No candidates above threshold. Run a scan or check back after 15:45 IST.</p>
      ) : (
        <div className="space-y-2">
          {sorted.map(c => (
            <CandidateRowComponent key={c.symbol} candidate={c} onOrderPlaced={load} />
          ))}
        </div>
      )}
    </section>
  )
}
