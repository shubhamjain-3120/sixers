import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Badge from './Badge'
import Sparkline from './Sparkline'
import PlaceOrderModal from './PlaceOrderModal'
import type { CandidateRow as CandidateRowType } from '../types'

interface Props {
  candidate: CandidateRowType
  onOrderPlaced: () => void
}

function fmt(n: number | null | undefined, dec = 1, prefix = '₹') {
  if (n == null) return '–'
  return `${prefix}${n.toFixed(dec)}`
}

function pctFmt(n: number | null | undefined) {
  if (n == null) return '–'
  const sign = n >= 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}%`
}

export default function CandidateRow({ candidate, onOrderPlaced }: Props) {
  const [showModal, setShowModal] = useState(false)
  const navigate = useNavigate()
  const pctColor = (candidate.pct_change_today ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
  const canTrade = candidate.badge !== 'RED'

  return (
    <>
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-700">
        {/* Top row */}
        <div className="flex flex-wrap items-start gap-3">
          <div className="flex items-center gap-2 min-w-[140px]">
            <Badge badge={candidate.badge} tooltip={candidate.llm_summary ?? undefined} />
            <button
              className="font-bold text-white hover:text-blue-400 transition-colors"
              onClick={() => navigate(`/candidate/${candidate.symbol}`)}
            >
              {candidate.symbol}
            </button>
            {candidate.segment === 'ETF' && (
              <span className="text-xs text-blue-400 border border-blue-800 rounded px-1">ETF</span>
            )}
          </div>

          <div className="flex flex-wrap gap-4 text-sm flex-1">
            <div>
              <span className="text-gray-400">LTP </span>
              <span className="text-white font-mono">{fmt(candidate.ltp, 2)}</span>
              <span className={`ml-1 text-xs ${pctColor}`}>{pctFmt(candidate.pct_change_today)}</span>
            </div>
            <div>
              <span className="text-gray-400">20DH </span>
              <span className="text-white font-mono">{fmt(candidate.high_20d, 2)}</span>
              <span className="ml-1 text-xs text-orange-400">(-{candidate.pct_below_20d_high?.toFixed(1) ?? '–'}%)</span>
            </div>
            <div>
              <span className="text-gray-500">S </span>
              <span className="text-red-300 font-mono">{fmt(candidate.support, 2)}</span>
              {candidate.support_pct_away != null && (
                <span className="ml-1 text-xs text-gray-500">({pctFmt(candidate.support_pct_away)})</span>
              )}
            </div>
            <div>
              <span className="text-gray-500">R </span>
              <span className="text-green-300 font-mono">{fmt(candidate.resistance, 2)}</span>
              {candidate.resistance_pct_away != null && (
                <span className="ml-1 text-xs text-gray-500">({pctFmt(candidate.resistance_pct_away)})</span>
              )}
            </div>
            <div>
              <span className="text-gray-400">RSI </span>
              <span className={`font-mono ${(candidate.rsi_14 ?? 50) < 35 ? 'text-orange-400' : 'text-gray-200'}`}>
                {candidate.rsi_14?.toFixed(0) ?? '–'}
              </span>
            </div>
            <div>
              <span className="text-gray-400">Score </span>
              <span className="text-blue-300 font-bold">{candidate.score.toFixed(0)}</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Sparkline data={candidate.sparkline_data} />
            <button
              onClick={() => navigate(`/candidate/${candidate.symbol}`)}
              className="text-xs text-gray-500 hover:text-gray-300 px-2 py-1.5"
            >
              Details →
            </button>
            <button
              onClick={e => { e.stopPropagation(); setShowModal(true) }}
              disabled={!canTrade}
              className="px-3 py-1.5 rounded bg-blue-700 hover:bg-blue-600 text-white text-sm font-semibold disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Buy
            </button>
          </div>
        </div>

        {/* LLM summary */}
        {candidate.llm_summary && (
          <p className="mt-2 text-xs text-gray-500 italic">💡 "{candidate.llm_summary}"</p>
        )}
      </div>

      {showModal && (
        <PlaceOrderModal
          candidate={candidate}
          onClose={() => setShowModal(false)}
          onSuccess={onOrderPlaced}
        />
      )}
    </>
  )
}
