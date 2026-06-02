import { useEffect, useState } from 'react'
import { getTradeDetail } from '../api/client'
import type { TradeDetail } from '../types'

interface Props {
  tradeId: number
  onClose: () => void
}

function fmt(v: number | null | undefined, decimals = 1, prefix = '') {
  if (v == null) return '–'
  return `${prefix}${v.toFixed(decimals)}`
}

function fmtPct(v: number | null | undefined, plus = false) {
  if (v == null) return '–'
  return `${plus && v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

function pctColor(v: number | null | undefined) {
  if (v == null) return 'text-gray-600 dark:text-gray-400'
  return v >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
}

function verdictColor(v: string | null) {
  if (!v) return 'text-gray-600 dark:text-gray-400'
  if (v === 'NOISE') return 'text-gray-600 dark:text-gray-400'
  if (v === 'FUNDAMENTAL_RISK') return 'text-red-600 dark:text-red-400'
  if (v === 'MIXED') return 'text-amber-600 dark:text-yellow-400'
  return 'text-gray-600 dark:text-gray-400'
}

function Row({ label, value, valueClass = 'text-gray-900 dark:text-white' }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="flex justify-between items-center py-1 border-b border-gray-200 dark:border-gray-800 last:border-0">
      <span className="text-gray-600 dark:text-gray-400 text-xs">{label}</span>
      <span className={`text-xs font-mono ${valueClass}`}>{value}</span>
    </div>
  )
}

export default function PositionDetailModal({ tradeId, onClose }: Props) {
  const [detail, setDetail] = useState<TradeDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getTradeDetail(tradeId)
      .then(setDetail)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [tradeId])

  const ltp = detail?.exit_price ?? null  // for open trades exit_price is null
  // Compute live pnl from current_sl_price isn't available here; use stored pnl_pct
  const pnl = detail?.pnl_pct ?? null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={onClose}
    >
      <div
        className="bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-700 rounded-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-800">
          <div>
            <span className="text-gray-900 dark:text-white font-bold text-lg">{detail?.symbol ?? '…'}</span>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-900 dark:hover:text-white text-xl leading-none"
          >
            ×
          </button>
        </div>

        {loading && (
          <div className="px-5 py-8 text-center text-gray-500 text-sm">Loading…</div>
        )}

        {!loading && detail && (
          <div className="px-5 py-4 space-y-5">
            {/* Live Position */}
            <div>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Position</h3>
              <div className="space-y-0.5">
                <Row label="Entry" value={fmt(detail.entry_price, 2, '₹')} />
                <Row label="Entry Date" value={new Date(detail.entry_date).toLocaleDateString('en-IN')} />
                <Row label="Qty" value={String(detail.qty)} />
                <Row label="Capital" value={fmt(detail.capital_deployed, 0, '₹')} />
                <Row
                  label="P&L"
                  value={fmtPct(detail.pnl_pct, true)}
                  valueClass={pctColor(detail.pnl_pct)}
                />
                {detail.pnl_inr != null && (
                  <Row
                    label="P&L ₹"
                    value={fmt(detail.pnl_inr, 0, detail.pnl_inr >= 0 ? '+₹' : '₹')}
                    valueClass={pctColor(detail.pnl_inr)}
                  />
                )}
                <Row label="Target" value={fmt(detail.initial_target_price, 2, '₹')} valueClass="text-green-600 dark:text-green-400" />
                <Row label="Stop Loss" value={fmt(detail.initial_sl_price, 2, '₹')} valueClass="text-red-600 dark:text-red-400" />
                <Row label="Days Held" value={String(detail.days_held ?? '–')} />
              </div>
            </div>

            {/* At Entry Snapshot */}
            <div>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">At Entry (Snapshot)</h3>

              <div className="space-y-3">
                {/* Scores */}
                <div>
                  <p className="text-xs text-gray-600 uppercase mb-1">Scores</p>
                  <div className="space-y-0.5">
                    <Row label="Pullback Score" value={fmt(detail.pullback_score_at_entry, 1)} />
                    <Row label="Shubham Score" value={fmt(detail.shubham_score_at_entry, 1)} />
                    <Row label="RSI (14)" value={fmt(detail.rsi_at_entry, 1)} />
                    <Row
                      label="LLM Verdict"
                      value={detail.llm_verdict_at_entry ?? '–'}
                      valueClass={verdictColor(detail.llm_verdict_at_entry)}
                    />
                  </div>
                </div>

                {/* vs Highs */}
                <div>
                  <p className="text-xs text-gray-600 uppercase mb-1">vs Highs</p>
                  <div className="space-y-0.5">
                    <Row label="% below 20D High" value={fmtPct(detail.pct_below_20d_high_at_entry)} />
                    <Row label="% below 50D High" value={fmtPct(detail.pct_below_50d_high_at_entry)} />
                  </div>
                </div>

                {/* vs Moving Averages */}
                <div>
                  <p className="text-xs text-gray-600 uppercase mb-1">vs Moving Averages</p>
                  <div className="space-y-0.5">
                    <Row label="Dist from 20DMA" value={fmtPct(detail.dist_from_20dma_at_entry, true)} />
                    <Row label="Dist from 50DMA" value={fmtPct(detail.dist_from_50dma_at_entry, true)} />
                  </div>
                </div>

                {/* Levels */}
                <div>
                  <p className="text-xs text-gray-600 uppercase mb-1">Levels</p>
                  <div className="space-y-0.5">
                    <Row label="Pivot Support" value={fmt(detail.pivot_support_at_entry, 2, '₹')} />
                    <Row label="Pivot Resistance" value={fmt(detail.pivot_resistance_at_entry, 2, '₹')} />
                    <Row label="30D Swing Low" value={fmt(detail.swing_low_at_entry, 2, '₹')} />
                    <Row label="30D Swing High" value={fmt(detail.swing_high_at_entry, 2, '₹')} />
                  </div>
                </div>

                {/* Context */}
                <div>
                  <p className="text-xs text-gray-600 uppercase mb-1">Context</p>
                  <div className="space-y-0.5">
                    <Row label="Volume Ratio" value={fmt(detail.volume_ratio_at_entry, 2)} />
                    <Row
                      label="Green After Red"
                      value={detail.green_after_red_at_entry == null ? '–' : detail.green_after_red_at_entry ? 'Yes' : 'No'}
                      valueClass={detail.green_after_red_at_entry ? 'text-green-600 dark:text-green-400' : 'text-gray-600 dark:text-gray-400'}
                    />
                    <Row label="Scan LTP" value={fmt(detail.ltp_at_entry, 2, '₹')} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
