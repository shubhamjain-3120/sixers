import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Badge from './Badge'
import PlaceOrderModal from './PlaceOrderModal'
import type { CandidateRow as CandidateRowType } from '../types'

interface Props {
  candidate: CandidateRowType
  onOrderPlaced: () => void
}

function fmt(n: number | null | undefined, dec = 2, prefix = '₹') {
  if (n == null) return '–'
  return `${prefix}${n.toFixed(dec)}`
}

function pct(n: number | null | undefined) {
  if (n == null) return <span className="text-gray-600">–</span>
  const sign = n >= 0 ? '+' : ''
  return <span>{sign}{n.toFixed(1)}%</span>
}

function dmaCell(n: number | null | undefined) {
  if (n == null) return <span className="text-gray-600">–</span>
  const sign = n >= 0 ? '+' : ''
  const color = n >= 0 ? 'text-green-400' : 'text-red-400'
  return <span className={color}>{sign}{n.toFixed(1)}%</span>
}

function highCell(n: number | null | undefined) {
  if (n == null) return <span className="text-gray-600">–</span>
  // pct_below_20d_high is always >= 0 (distance below high)
  const color = n <= 3 ? 'text-green-400' : n <= 8 ? 'text-yellow-400' : 'text-red-400'
  return <span className={color}>-{n.toFixed(1)}%</span>
}

export default function CandidateRow({ candidate, onOrderPlaced }: Props) {
  const [showModal, setShowModal] = useState(false)
  const navigate = useNavigate()
  const canTrade = candidate.badge !== 'RED'
  const ltpColor = (candidate.pct_change_today ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'

  return (
    <>
      <tr
        className="border-b border-gray-800 hover:bg-gray-800/60 cursor-pointer transition-colors"
        onClick={() => navigate(`/candidate/${candidate.symbol}`)}
      >
        <td className="py-2.5 pl-3 pr-2">
          <Badge badge={candidate.badge} tooltip={candidate.llm_summary ?? undefined} />
        </td>
        <td className="py-2.5 pr-4 font-bold text-white whitespace-nowrap">
          {candidate.symbol}
          {candidate.segment === 'ETF' && (
            <span className="ml-1 text-xs text-blue-400 border border-blue-800 rounded px-1">ETF</span>
          )}
        </td>
        <td className="py-2.5 pr-4 font-mono text-right whitespace-nowrap">
          <span className="text-white">{fmt(candidate.ltp, 2)}</span>
          <span className={`ml-1 text-xs ${ltpColor}`}>{candidate.pct_change_today != null ? `${(candidate.pct_change_today >= 0 ? '+' : '')}${candidate.pct_change_today.toFixed(1)}%` : ''}</span>
        </td>
        <td className="py-2.5 pr-4 font-mono text-right whitespace-nowrap">
          <span className="text-gray-300">{fmt(candidate.high_20d, 2)}</span>
          <span className="ml-1 text-xs">{highCell(candidate.pct_below_20d_high)}</span>
        </td>
        <td className="py-2.5 pr-4 font-mono text-right text-sm">{dmaCell(candidate.dist_from_20dma_pct)}</td>
        <td className="py-2.5 pr-4 font-mono text-right text-sm">{dmaCell(candidate.dist_from_50dma_pct)}</td>
        <td className="py-2.5 pr-4 font-mono text-right text-sm text-green-300 whitespace-nowrap">
          {fmt(candidate.resistance, 2)}
          <span className="ml-1 text-xs text-gray-500">{candidate.resistance_pct_away != null ? `(${candidate.resistance_pct_away >= 0 ? '+' : ''}${candidate.resistance_pct_away.toFixed(1)}%)` : ''}</span>
        </td>
        <td className="py-2.5 pr-4 font-mono text-right text-sm text-red-300 whitespace-nowrap">
          {fmt(candidate.support, 2)}
          <span className="ml-1 text-xs text-gray-500">{candidate.support_pct_away != null ? `(${candidate.support_pct_away >= 0 ? '+' : ''}${candidate.support_pct_away.toFixed(1)}%)` : ''}</span>
        </td>
        <td className={`py-2.5 pr-4 font-mono text-right ${(candidate.rsi_14 ?? 50) < 35 ? 'text-orange-400' : 'text-gray-200'}`}>
          {candidate.rsi_14?.toFixed(0) ?? '–'}
        </td>
        <td className="py-2.5 pr-4 font-mono text-right text-blue-300 font-bold">
          {candidate.score.toFixed(0)}
        </td>
        <td className="py-2.5 pr-4 font-mono text-right text-purple-300 font-bold">
          {candidate.shubham_score != null ? candidate.shubham_score.toFixed(0) : '–'}
        </td>
        <td className="py-2.5 pr-3 text-right">
          <button
            onClick={e => { e.stopPropagation(); setShowModal(true) }}
            disabled={!canTrade}
            className="px-3 py-1 rounded bg-blue-700 hover:bg-blue-600 text-white text-xs font-semibold disabled:opacity-30 disabled:cursor-not-allowed whitespace-nowrap"
          >
            Buy
          </button>
        </td>
      </tr>

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
