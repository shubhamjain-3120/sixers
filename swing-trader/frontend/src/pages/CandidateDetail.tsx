import { useParams, useNavigate } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'
import { getCandidateDetail, getOhlcv, triggerNewsClassify } from '../api/client'
import type { CandidateDetail, OhlcvBar } from '../types'
import PlaceOrderModal from '../components/PlaceOrderModal'
import PriceChart, { ChartPoint } from '../components/candidateDetail/PriceChart'
import SignalsTable from '../components/candidateDetail/SignalsTable'
import NewsSection from '../components/candidateDetail/NewsSection'

function sma(closes: number[], period: number, idx: number): number | null {
  if (idx < period - 1) return null
  const slice = closes.slice(idx - period + 1, idx + 1)
  return slice.reduce((a, b) => a + b, 0) / period
}

function buildChartData(ohlcv: OhlcvBar[]): ChartPoint[] {
  const closes = ohlcv.map(r => r.close ?? 0)
  return ohlcv.map((r, i) => ({
    date: r.date,
    close: r.close,
    sma20: sma(closes, 20, i),
    sma50: sma(closes, 50, i),
  }))
}

export default function CandidateDetail() {
  const { symbol } = useParams<{ symbol: string }>()
  const navigate = useNavigate()
  const [detail, setDetail] = useState<CandidateDetail | null>(null)
  const [ohlcv, setOhlcv] = useState<OhlcvBar[]>([])
  const [showModal, setShowModal] = useState(false)
  const [loading, setLoading] = useState(true)
  const [classifying, setClassifying] = useState(false)

  useEffect(() => {
    if (!symbol) return
    setLoading(true)
    Promise.all([
      getCandidateDetail(symbol),
      getOhlcv(symbol, 90),
    ]).then(([d, o]) => {
      setDetail(d)
      setOhlcv(o)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [symbol])

  const chartData = useMemo(() => buildChartData(ohlcv), [ohlcv])
  const lastSma20 = useMemo(
    () => [...chartData].reverse().find(d => d.sma20 != null)?.sma20 ?? null,
    [chartData],
  )
  const lastSma50 = useMemo(
    () => [...chartData].reverse().find(d => d.sma50 != null)?.sma50 ?? null,
    [chartData],
  )

  if (loading) {
    return <div className="max-w-4xl mx-auto px-4 py-10 text-gray-400">Loading {symbol}…</div>
  }
  if (!detail) {
    return <div className="max-w-4xl mx-auto px-4 py-10 text-gray-400">No scan data for {symbol}.</div>
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <button onClick={() => navigate(-1)} className="text-gray-500 hover:text-white text-sm mb-4">← Back</button>

      <div className="flex flex-wrap items-center gap-3 mb-6">
        <h1 className="text-2xl font-bold text-white">{detail.symbol}</h1>
        {detail.name && <span className="text-gray-400 text-sm">{detail.name}</span>}
        {detail.sector && <span className="text-gray-500 text-xs">· {detail.sector}</span>}
        {detail.segment === 'ETF' && (
          <span className="text-xs text-blue-400 border border-blue-800 rounded px-1">ETF</span>
        )}
      </div>

      <PriceChart chartData={chartData} support={detail.support} resistance={detail.resistance} />
      <SignalsTable detail={detail} lastSma20={lastSma20} lastSma50={lastSma50} />
      <NewsSection
        detail={detail}
        classifying={classifying}
        onReanalyze={async () => {
          setClassifying(true)
          try {
            await triggerNewsClassify()
            await new Promise(r => setTimeout(r, 3000))
            const d = await getCandidateDetail(symbol!)
            setDetail(d)
          } finally {
            setClassifying(false)
          }
        }}
      />

      <button
        onClick={() => setShowModal(true)}
        className="w-full py-3 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-bold"
      >
        Place Order — {detail.symbol}
      </button>

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
