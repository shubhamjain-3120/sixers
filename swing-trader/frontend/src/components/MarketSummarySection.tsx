import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getMarketNews } from '../api/client'
import type { MarketNews, MarketQuote } from '../api/client'
import { DirectionBadge, QuoteChip, timeAgo } from './marketUi'

/** Pick the headline cues for the compact dashboard strip. */
function cueChips(data: MarketNews): MarketQuote[] {
  const chips: MarketQuote[] = []
  if (data.global_cues.gift_nifty) chips.push(data.global_cues.gift_nifty)
  const byName = (rows: MarketQuote[], name: string) => rows.find(r => r.name === name)
  const dow = byName(data.global_cues.us, 'Dow Jones')
  const nasdaq = byName(data.global_cues.us, 'Nasdaq')
  const nikkei = byName(data.global_cues.asia, 'Nikkei 225')
  const hangSeng = byName(data.global_cues.asia, 'Hang Seng')
  // HDFC Bank ADR — largest Nifty/Bank Nifty weight with a US listing.
  const hdfc = byName(data.adrs, 'HDFC ADR')
  for (const q of [dow, nasdaq, nikkei, hangSeng, hdfc]) if (q) chips.push(q)
  return chips
}

export default function MarketSummarySection() {
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
    <div className="bg-gray-900 border border-gray-800 rounded-lg px-5 py-3 mb-4">
      {/* Header row */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-widest">
            Market News
          </span>
          {data && !loading && <DirectionBadge direction={data.direction} />}
        </div>
        <button
          onClick={() => load(true)}
          disabled={loading}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs text-gray-400 border border-gray-700 hover:border-gray-500 hover:text-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? (
            <>
              <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Fetching…
            </>
          ) : (
            <>
              <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh
            </>
          )}
        </button>
      </div>

      {/* Body */}
      {loading && !data && (
        <div className="flex items-center gap-2 text-gray-500 text-sm py-2">
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          Fetching global cues and generating pre-market read…
        </div>
      )}

      {error && !loading && (
        <p className="text-sm text-red-400/70 py-1">
          Could not load market news. Check backend logs or try refreshing.
        </p>
      )}

      {data && !loading && (
        <div className="space-y-3">
          {/* Unified pre-market read */}
          <p className="text-sm text-gray-300 leading-relaxed">{data.summary}</p>

          {/* Global cue strip */}
          {cueChips(data).length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {cueChips(data).map((q, i) => <QuoteChip key={i} quote={q} />)}
            </div>
          )}

          {/* Footer: show more + last updated */}
          <div className="flex items-center justify-between">
            <Link
              to="/market-news"
              className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              Show more
              <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </Link>
            <p className="text-xs text-gray-600">
              Updated {timeAgo(data.fetched_at)}
              {data.cached && <span className="ml-1 text-gray-700">· cached</span>}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
