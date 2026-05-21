import { useParams, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { getCandidateDetail, getOhlcv, getBlockDeals, triggerNewsClassify } from '../api/client'
import type { CandidateDetail, OhlcvBar, BlockDealOut } from '../types'
import Badge from '../components/Badge'
import PlaceOrderModal from '../components/PlaceOrderModal'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, ReferenceLine,
} from 'recharts'

const VERDICT_STYLES: Record<string, { border: string; bg: string; text: string; label: string }> = {
  NOISE:             { border: 'border-green-700', bg: 'bg-green-950/40', text: 'text-green-300', label: 'NOISE' },
  FUNDAMENTAL_RISK:  { border: 'border-red-700',   bg: 'bg-red-950/40',   text: 'text-red-300',   label: 'FUNDAMENTAL RISK' },
  MIXED:             { border: 'border-yellow-700', bg: 'bg-yellow-950/40',text: 'text-yellow-300',label: 'MIXED' },
  INSUFFICIENT_DATA: { border: 'border-gray-700',  bg: 'bg-gray-800/40',  text: 'text-gray-400',  label: 'INSUFFICIENT DATA' },
}

function VerdictCallout({ verdict, confidence, summary }: { verdict: string; confidence: number | null; summary: string | null }) {
  const s = VERDICT_STYLES[verdict] ?? VERDICT_STYLES.INSUFFICIENT_DATA
  return (
    <div className={`border rounded-lg px-4 py-3 ${s.border} ${s.bg}`}>
      <div className="flex items-center gap-3 mb-1">
        <span className={`text-xs font-bold tracking-widest ${s.text}`}>{s.label}</span>
        {confidence != null && (
          <span className="text-xs text-gray-500">confidence {(confidence * 100).toFixed(0)}%</span>
        )}
      </div>
      {summary && <p className="text-sm text-gray-300 italic">"{summary}"</p>}
    </div>
  )
}

const CLS_STYLES: Record<string, { bg: string; text: string; short: string }> = {
  NOISE:                { bg: 'bg-blue-900/50',   text: 'text-blue-300',   short: 'N' },
  FUNDAMENTAL_NEGATIVE: { bg: 'bg-red-900/50',    text: 'text-red-300',    short: 'F−' },
  FUNDAMENTAL_POSITIVE: { bg: 'bg-green-900/50',  text: 'text-green-300',  short: 'F+' },
  IRRELEVANT:           { bg: 'bg-gray-800',       text: 'text-gray-500',   short: 'IR' },
}

function HeadlineBadge({ cls }: { cls: string }) {
  const s = CLS_STYLES[cls] ?? { bg: 'bg-gray-800', text: 'text-gray-400', short: '?' }
  return (
    <span className={`flex-shrink-0 mt-0.5 w-7 h-5 flex items-center justify-center rounded text-xs font-bold ${s.bg} ${s.text}`}>
      {s.short}
    </span>
  )
}

function fmt(n: number | null | undefined, dec = 2, prefix = '₹') {
  if (n == null) return '–'
  return `${prefix}${n.toFixed(dec)}`
}

function pctFmt(n: number | null | undefined) {
  if (n == null) return '–'
  const sign = n >= 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}%`
}

function sma(closes: number[], period: number, idx: number): number | null {
  if (idx < period - 1) return null
  const slice = closes.slice(idx - period + 1, idx + 1)
  return slice.reduce((a, b) => a + b, 0) / period
}

export default function CandidateDetail() {
  const { symbol } = useParams<{ symbol: string }>()
  const navigate = useNavigate()
  const [detail, setDetail] = useState<CandidateDetail | null>(null)
  const [ohlcv, setOhlcv] = useState<OhlcvBar[]>([])
  const [deals, setDeals] = useState<BlockDealOut[]>([])
  const [showModal, setShowModal] = useState(false)
  const [loading, setLoading] = useState(true)
  const [classifying, setClassifying] = useState(false)

  useEffect(() => {
    if (!symbol) return
    setLoading(true)
    Promise.all([
      getCandidateDetail(symbol),
      getOhlcv(symbol, 90),
      getBlockDeals(symbol),
    ]).then(([d, o, bl]) => {
      setDetail(d)
      setOhlcv(o)
      setDeals(bl)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [symbol])

  if (loading) {
    return <div className="max-w-4xl mx-auto px-4 py-10 text-gray-400">Loading {symbol}…</div>
  }
  if (!detail) {
    return <div className="max-w-4xl mx-auto px-4 py-10 text-gray-400">No scan data for {symbol}.</div>
  }

  const closes = ohlcv.map(r => r.close ?? 0)
  const chartData = ohlcv.map((r, i) => ({
    date: r.date,
    close: r.close,
    sma20: sma(closes, 20, i),
    sma50: sma(closes, 50, i),
  }))

  const signals = [
    { label: 'LTP', value: fmt(detail.ltp) },
    { label: 'Prev Close', value: fmt(detail.prev_close) },
    { label: 'Change today', value: pctFmt(detail.pct_change_today), color: (detail.pct_change_today ?? 0) >= 0 ? 'text-green-400' : 'text-red-400' },
    { label: 'Score', value: detail.score.toFixed(1), color: 'text-blue-300' },
    { label: 'RSI 14', value: detail.rsi_14?.toFixed(1) ?? '–', color: (detail.rsi_14 ?? 50) < 35 ? 'text-orange-400' : undefined },
    { label: '% Below 20D High', value: `${detail.pct_below_20d_high?.toFixed(2) ?? '–'}%`, color: 'text-orange-300' },
    { label: '% Below 50D High', value: `${detail.pct_below_50d_high?.toFixed(2) ?? '–'}%` },
    { label: 'Dist from 20DMA', value: pctFmt(detail.dist_from_20dma_pct) },
    { label: 'Dist from 50DMA', value: pctFmt(detail.dist_from_50dma_pct) },
    { label: 'Volume Ratio', value: detail.volume_ratio?.toFixed(2) ?? '–', color: (detail.volume_ratio ?? 0) >= 1.5 ? 'text-yellow-400' : undefined },
    { label: 'Support (S1)', value: fmt(detail.support) },
    { label: 'Support % away', value: pctFmt(detail.support_pct_away), color: 'text-red-300' },
    { label: 'Resistance (R1)', value: fmt(detail.resistance) },
    { label: 'Resistance % away', value: pctFmt(detail.resistance_pct_away), color: 'text-green-300' },
    { label: '30D Swing Low', value: fmt(detail.swing_low_30d) },
    { label: '30D Swing High', value: fmt(detail.swing_high_30d) },
    { label: 'Green After Red', value: detail.green_after_red ? 'Yes ✓' : 'No', color: detail.green_after_red ? 'text-green-400' : undefined },
    { label: 'Scan Date', value: detail.scan_date },
  ]

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <button onClick={() => navigate(-1)} className="text-gray-500 hover:text-white text-sm mb-4">← Back</button>

      <div className="flex flex-wrap items-center gap-3 mb-6">
        <h1 className="text-2xl font-bold text-white">{detail.symbol}</h1>
        {detail.name && <span className="text-gray-400 text-sm">{detail.name}</span>}
        {detail.sector && <span className="text-gray-500 text-xs">· {detail.sector}</span>}
        <Badge badge={detail.badge} />
        {detail.segment === 'ETF' && (
          <span className="text-xs text-blue-400 border border-blue-800 rounded px-1">ETF</span>
        )}
      </div>

      {/* 90-day chart */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <h2 className="text-sm text-gray-400 mb-1">90-day Close · <span className="text-amber-400">── 20DMA</span> · <span className="text-purple-400">── 50DMA</span></h2>
        {detail.support && (
          <p className="text-xs text-gray-600 mb-3">
            S1 ₹{detail.support.toFixed(2)} · R1 ₹{detail.resistance?.toFixed(2) ?? '–'}
          </p>
        )}
        <ResponsiveContainer width="100%" height={240}>
          <ComposedChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis
              dataKey="date"
              tick={{ fill: '#6b7280', fontSize: 9 }}
              tickFormatter={v => v.slice(5)}
              interval={Math.floor(chartData.length / 6)}
            />
            <YAxis domain={['auto', 'auto']} tick={{ fill: '#6b7280', fontSize: 10 }} width={55} />
            <Tooltip
              contentStyle={{ background: '#111827', border: '1px solid #374151', color: '#fff', fontSize: 12 }}
              formatter={(v: number, name: string) => [`₹${v?.toFixed(2)}`, name]}
              labelFormatter={l => `Date: ${l}`}
            />
            <Bar dataKey="close" fill="#3b82f6" opacity={0.55} name="Close" />
            {detail.support && (
              <ReferenceLine y={detail.support} stroke="#ef4444" strokeDasharray="4 2" strokeWidth={1} />
            )}
            {detail.resistance && (
              <ReferenceLine y={detail.resistance} stroke="#22c55e" strokeDasharray="4 2" strokeWidth={1} />
            )}
            <Line type="monotone" dataKey="sma20" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="20DMA" connectNulls />
            <Line type="monotone" dataKey="sma50" stroke="#a855f7" dot={false} strokeWidth={1.5} name="50DMA" connectNulls />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Full signals table */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">All Signals</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-2">
          {signals.map(({ label, value, color }) => (
            <div key={label}>
              <div className="text-xs text-gray-500">{label}</div>
              <div className={`text-sm font-mono ${color ?? 'text-gray-200'}`}>{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Block deals */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Block / Bulk Deals (last 5 days)
        </h2>
        {deals.length === 0 ? (
          <p className="text-gray-600 text-sm">No block or bulk deals found.</p>
        ) : (
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="pb-2 pr-4">Date</th>
                <th className="pb-2 pr-4">Client</th>
                <th className="pb-2 pr-4">Type</th>
                <th className="pb-2 pr-4 text-right">Qty</th>
                <th className="pb-2 pr-4 text-right">Price</th>
                <th className="pb-2">Source</th>
              </tr>
            </thead>
            <tbody>
              {deals.map((d, i) => (
                <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="py-1.5 pr-4 text-gray-300">{d.deal_date}</td>
                  <td className="py-1.5 pr-4 text-gray-200 max-w-[160px] truncate">{d.client_name ?? '–'}</td>
                  <td className={`py-1.5 pr-4 font-semibold ${d.deal_type === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                    {d.deal_type ?? '–'}
                  </td>
                  <td className="py-1.5 pr-4 text-right text-gray-300">
                    {d.quantity != null ? d.quantity.toLocaleString('en-IN') : '–'}
                  </td>
                  <td className="py-1.5 pr-4 text-right text-gray-300">
                    {d.price != null ? `₹${d.price.toFixed(2)}` : '–'}
                  </td>
                  <td className="py-1.5 text-gray-500 uppercase">{d.source ?? '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* News + LLM classification */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">News & LLM Classification</h2>
          <button
            onClick={() => { setClassifying(true); triggerNewsClassify().finally(() => setClassifying(false)) }}
            disabled={classifying}
            className="text-xs text-blue-400 hover:text-blue-300 disabled:text-gray-600 border border-blue-900 hover:border-blue-700 rounded px-2 py-1"
          >
            {classifying ? 'Classifying…' : 'Classify now'}
          </button>
        </div>

        {/* Verdict callout */}
        {detail.news_verdict ? (
          <VerdictCallout
            verdict={detail.news_verdict}
            confidence={detail.news_confidence}
            summary={detail.llm_summary}
          />
        ) : (
          <p className="text-gray-600 text-sm mb-3">No classification available — run the 18:00 IST job or trigger manually.</p>
        )}

        {/* Per-headline list */}
        {(detail.news_headlines ?? []).length > 0 && (
          <div className="mt-3 space-y-2">
            {(detail.news_headlines ?? []).map(h => (
              <div key={h.idx} className="flex gap-3 text-sm">
                <HeadlineBadge cls={h.classification} />
                <div className="min-w-0">
                  <p className="text-gray-200 leading-snug">{h.headline}</p>
                  <p className="text-gray-500 text-xs mt-0.5 italic">{h.reason}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {detail.badge !== 'RED' && (
        <button
          onClick={() => setShowModal(true)}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-bold"
        >
          Place Order — {detail.symbol}
        </button>
      )}
      {detail.badge === 'RED' && (
        <div className="w-full py-3 bg-red-900/30 border border-red-800 rounded-lg text-red-400 text-center text-sm">
          RED badge — order placement blocked
        </div>
      )}

      {showModal && (
        <PlaceOrderModal
          candidate={detail}
          onClose={() => setShowModal(false)}
          onSuccess={() => navigate('/dashboard')}
        />
      )}
    </div>
  )
}
