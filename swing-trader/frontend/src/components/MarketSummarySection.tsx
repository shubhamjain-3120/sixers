import { useEffect, useState } from 'react'
import { getNiftySummary } from '../api/client'
import type { NiftySummary } from '../api/client'

function DirectionBadge({ direction }: { direction: 'up' | 'down' | 'flat' }) {
  if (direction === 'up') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-green-900/50 text-green-400 border border-green-800">
        ▲ UP
      </span>
    )
  }
  if (direction === 'down') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-red-900/50 text-red-400 border border-red-800">
        ▼ DOWN
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-gray-800 text-gray-400 border border-gray-700">
      → FLAT
    </span>
  )
}

function timeAgo(isoString: string): string {
  const diffMs = Date.now() - new Date(isoString).getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin === 1) return '1 min ago'
  if (diffMin < 60) return `${diffMin} min ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr === 1) return '1 hr ago'
  return `${diffHr} hr ago`
}

export default function MarketSummarySection() {
  const [data, setData] = useState<NiftySummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [headlinesOpen, setHeadlinesOpen] = useState(false)

  const load = (force: boolean) => {
    setLoading(true)
    setError(false)
    getNiftySummary(force)
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
            Nifty Market Summary
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
          Fetching headlines and generating summary…
        </div>
      )}

      {error && !loading && (
        <p className="text-sm text-red-400/70 py-1">
          Could not load market summary. Check backend logs or try refreshing.
        </p>
      )}

      {data && !loading && (
        <div className="space-y-3">
          {/* Summary paragraph */}
          <p className="text-sm text-gray-300 leading-relaxed">{data.summary}</p>

          {/* Collapsible headlines */}
          <div>
            <button
              onClick={() => setHeadlinesOpen(o => !o)}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              <svg
                className={`h-3 w-3 transition-transform ${headlinesOpen ? 'rotate-90' : ''}`}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
              {data.headlines.length} headline{data.headlines.length !== 1 ? 's' : ''}
            </button>

            {headlinesOpen && (
              <ul className="mt-2 space-y-1.5 pl-1">
                {data.headlines.map((h, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-gray-400">
                    <span className="text-gray-600 mt-0.5 shrink-0">
                      {new Date(h.published_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                    </span>
                    {h.url ? (
                      <a
                        href={h.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:text-gray-200 hover:underline leading-snug"
                      >
                        {h.title}
                      </a>
                    ) : (
                      <span className="leading-snug">{h.title}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Footer: last updated */}
          <p className="text-xs text-gray-600">
            Updated {timeAgo(data.fetched_at)}
            {data.cached && <span className="ml-1 text-gray-700">· cached</span>}
          </p>
        </div>
      )}
    </div>
  )
}
