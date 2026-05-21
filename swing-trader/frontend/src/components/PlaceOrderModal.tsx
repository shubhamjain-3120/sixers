import { useState, useEffect } from 'react'
import { placeTrade, getConfig, getStatsSummary } from '../api/client'
import type { CandidateDetail, Config, StatsSummary } from '../types'

interface Props {
  candidate: CandidateDetail
  onClose: () => void
  onSuccess: () => void
}

export default function PlaceOrderModal({ candidate, onClose, onSuccess }: Props) {
  const [cfg, setCfg] = useState<Config | null>(null)
  const [stats, setStats] = useState<StatsSummary | null>(null)
  const [customCapital, setCustomCapital] = useState('')
  const [status, setStatus] = useState<'idle' | 'placing' | 'done' | 'error'>('idle')
  const [error, setError] = useState('')

  useEffect(() => {
    getConfig().then(d => { setCfg(d); }).catch(() => {})
    getStatsSummary().then(setStats).catch(() => {})
  }, [])

  const ltp = candidate.ltp ?? 0
  const defaultCapital = cfg ? (cfg.total_capital_inr * cfg.nifty50_alloc_pct) / 100 : 0
  const capitalAvailable = stats?.capital_available ?? null

  // Allow user to override capital; clamp to available
  const parsedCustom = parseFloat(customCapital)
  const capital = customCapital !== '' && !isNaN(parsedCustom) ? parsedCustom : defaultCapital

  const qty = ltp > 0 && capital > 0 ? Math.floor(capital / ltp) : 0
  const entryEst = ltp * 1.001
  const targetEst = cfg ? entryEst * (1 + cfg.target_pct / 100) : 0
  const slEst = cfg ? entryEst * (1 - cfg.stop_loss_pct / 100) : 0
  const capitalDeployed = entryEst * qty

  const handleConfirm = async () => {
    setStatus('placing')
    setError('')
    try {
      await placeTrade(candidate.symbol)
      setStatus('done')
      setTimeout(() => { onSuccess(); onClose() }, 1500)
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || 'Order failed'
      setError(msg)
      setStatus('error')
    }
  }

  const fmt = (n: number | null | undefined, digits = 2) =>
    n != null ? `₹${n.toFixed(digits)}` : '–'

  const fmtPct = (n: number | null | undefined) =>
    n != null ? `${n >= 0 ? '+' : ''}${n.toFixed(2)}%` : '–'

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-white">Place Order — {candidate.symbol}</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl">✕</button>
        </div>

        {/* Price context */}
        <div className="space-y-1.5 text-sm mb-4">
          <Row label="Segment" value={candidate.segment} />
          <Row label="Current LTP" value={fmt(ltp)} />
          <Row label="Entry (limit +0.1%)" value={fmt(entryEst)} />
          <Row
            label="vs 20 DMA"
            value={fmtPct(candidate.dist_from_20dma_pct)}
            color={(candidate.dist_from_20dma_pct ?? 0) < 0 ? 'text-yellow-400' : 'text-gray-300'}
          />
          <Row
            label="vs 50 DMA"
            value={fmtPct(candidate.dist_from_50dma_pct)}
            color={(candidate.dist_from_50dma_pct ?? 0) < 0 ? 'text-yellow-400' : 'text-gray-300'}
          />
        </div>

        {/* Capital & quantity */}
        <div className="border-t border-gray-800 pt-4 space-y-1.5 text-sm mb-4">
          {capitalAvailable != null && (
            <Row label="Capital available" value={`₹${capitalAvailable.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`} />
          )}
          <Row label="Default allocation" value={`₹${defaultCapital.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`} />

          {/* Editable capital override */}
          <div className="flex justify-between items-center">
            <span className="text-gray-400">Capital to deploy</span>
            <input
              type="number"
              min={0}
              step={1000}
              value={customCapital}
              onChange={e => setCustomCapital(e.target.value)}
              placeholder={defaultCapital.toFixed(0)}
              className="w-32 bg-gray-800 border border-gray-600 rounded px-2 py-0.5 text-right text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          <Row label="Quantity" value={qty.toString()} highlight />
          <Row
            label="Capital deployed"
            value={`₹${capitalDeployed.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`}
          />
        </div>

        {/* GTT bracket preview */}
        <div className="border-t border-gray-800 pt-4 space-y-1.5 text-sm mb-4">
          <Row
            label={`Target (+${cfg?.target_pct ?? 2}%)`}
            value={fmt(targetEst)}
            color="text-green-400"
          />
          <Row
            label={`Stop Loss (−${cfg?.stop_loss_pct ?? 4}%)`}
            value={fmt(slEst)}
            color="text-red-400"
          />
          <p className="text-xs text-gray-500 pt-1">
            GTT bracket order will be placed at Zerodha immediately after fill.
          </p>
        </div>

        {error && (
          <div className="bg-red-950 border border-red-800 rounded p-3 text-red-400 text-sm mb-4 break-words">
            {error}
          </div>
        )}
        {status === 'done' && <p className="text-green-400 text-sm mb-4">Order placed successfully!</p>}

        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded border border-gray-700 text-gray-400 hover:bg-gray-800"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={status === 'placing' || status === 'done' || qty < 1}
            className="flex-1 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white font-semibold disabled:opacity-50"
          >
            {status === 'placing' ? 'Placing…' : `Confirm Buy ${qty > 0 ? `(${qty} shares)` : ''}`}
          </button>
        </div>
      </div>
    </div>
  )
}

function Row({
  label, value, highlight, color,
}: {
  label: string; value: string; highlight?: boolean; color?: string
}) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-400">{label}</span>
      <span className={color ?? (highlight ? 'text-white font-bold' : 'text-gray-200')}>{value}</span>
    </div>
  )
}
