import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getMarketNews } from '../api/client'
import type { MarketNews, MarketQuote } from '../api/client'
import { DirectionBadge, changeColor, fmtPct, timeAgo } from '../components/marketUi'

function QuoteTable({ rows }: { rows: MarketQuote[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-gray-600 py-2">No data available.</p>
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-xs text-gray-500 uppercase tracking-wider border-b border-gray-800">
          <th className="text-left font-medium py-2">Market</th>
          <th className="text-right font-medium py-2">Last</th>
          <th className="text-right font-medium py-2">Change</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((q, i) => (
          <tr key={i} className="border-b border-gray-800/50 last:border-0">
            <td className="py-2 text-gray-300">
              {q.name}
              {q.symbol && <span className="ml-2 text-xs text-gray-600">{q.symbol}</span>}
            </td>
            <td className="py-2 text-right tabular-nums text-gray-400">
              {q.last != null ? q.last.toLocaleString('en-IN') : '—'}
            </td>
            <td className={`py-2 text-right tabular-nums font-semibold ${changeColor(q.direction)}`}>
              {fmtPct(q.change_pct)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg px-5 py-4">
      <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-3">{title}</h2>
      {children}
    </div>
  )
}

export default function MarketNews() {
  const [data, setData] = useState<MarketNews | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const load = (force: boolean) => {
    setLoading(true)
    setError(false)
    getMarketNews(force)
      .then(d => { setData(d); setLoading(false) })
      .catch(() => { setError(true); setLoading(false) })
  }

  useEffect(() => { load(false) }, [])

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/dashboard" className="text-sm text-gray-500 hover:text-gray-300">← Dashboard</Link>
          <h1 className="text-xl font-bold text-white">Market News</h1>
          {data && !loading && <DirectionBadge direction={data.direction} />}
        </div>
        <button
          onClick={() => load(true)}
          disabled={loading}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs text-gray-400 border border-gray-700 hover:border-gray-500 hover:text-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Fetching…' : 'Refresh'}
        </button>
      </div>

      {loading && !data && (
        <p className="text-gray-500 text-sm">Fetching global cues and generating pre-market read…</p>
      )}
      {error && !loading && (
        <p className="text-sm text-red-400/70">Could not load market news. Check backend logs or try refreshing.</p>
      )}

      {data && !loading && (
        <>
          {/* Pre-market read */}
          <Section title="Pre-Market Read">
            <p className="text-sm text-gray-300 leading-relaxed">{data.summary}</p>
            <p className="text-xs text-gray-600 mt-3">
              Updated {timeAgo(data.fetched_at)}
              {data.cached && <span className="ml-1 text-gray-700">· cached</span>}
            </p>
          </Section>

          {/* 1. India / Nifty news */}
          <Section title="India / Nifty News">
            {data.headlines.length === 0 ? (
              <p className="text-sm text-gray-600">No recent headlines.</p>
            ) : (
              <ul className="space-y-2">
                {data.headlines.map((h, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-400">
                    <span className="text-gray-600 mt-0.5 shrink-0 text-xs">
                      {new Date(h.published_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                    </span>
                    {h.url ? (
                      <a href={h.url} target="_blank" rel="noopener noreferrer" className="hover:text-gray-200 hover:underline leading-snug">
                        {h.title}
                      </a>
                    ) : (
                      <span className="leading-snug">{h.title}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Section>

          {/* 2. Global markets */}
          <Section title="Global Markets — Cues for Nifty">
            {data.global_cues.gift_nifty && (
              <div className="mb-4">
                <p className="text-xs text-gray-500 mb-2">GIFT Nifty (pre-open predictor)</p>
                <QuoteTable rows={[data.global_cues.gift_nifty]} />
              </div>
            )}
            <div className="mb-4">
              <p className="text-xs text-gray-500 mb-2">US Markets (overnight close)</p>
              <QuoteTable rows={data.global_cues.us} />
            </div>
            <div className="mb-4">
              <p className="text-xs text-gray-500 mb-2">Asian Markets (live)</p>
              <QuoteTable rows={data.global_cues.asia} />
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-2">Macro (VIX · Crude · USD/INR)</p>
              <QuoteTable rows={data.global_cues.macro} />
            </div>
          </Section>

          {/* 3. Indian ADRs */}
          <Section title="Indian ADRs (overnight, US listing)">
            <QuoteTable rows={data.adrs} />
          </Section>
        </>
      )}
    </div>
  )
}
