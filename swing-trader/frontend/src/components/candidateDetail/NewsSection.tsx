import type { CandidateDetail } from '../../types'

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

type Props = {
  detail: CandidateDetail
  classifying: boolean
  onReanalyze: () => void
}

export default function NewsSection({ detail, classifying, onReanalyze }: Props) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">What's moving the stock</h2>
        <button
          onClick={onReanalyze}
          disabled={classifying}
          className="text-xs text-blue-400 hover:text-blue-300 disabled:text-gray-600 border border-blue-900 hover:border-blue-700 rounded px-2 py-1"
        >
          {classifying ? 'Analyzing…' : 'Re-analyze'}
        </button>
      </div>

      {detail.news_verdict ? (
        detail.llm_summary && detail.llm_summary.trim() ? (
          <p className="text-sm text-gray-200 leading-relaxed">{detail.llm_summary}</p>
        ) : (
          <p className="text-sm text-gray-500 italic">No clear news catalyst for the recent move — likely sector/macro or technical.</p>
        )
      ) : (
        <p className="text-gray-600 text-sm">Not analyzed yet — run the 18:00 IST job or click Re-analyze.</p>
      )}

      {(detail.news_headlines ?? []).length > 0 && (
        <details className="mt-3">
          <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-400">Show source headlines ({detail.news_headlines!.length})</summary>
          <div className="mt-2 space-y-2">
            {(detail.news_headlines ?? []).map(h => (
              <div key={h.idx} className="flex gap-3 text-sm">
                <HeadlineBadge cls={h.classification} />
                <div className="min-w-0">
                  <p className="text-gray-300 leading-snug">{h.headline}</p>
                  <p className="text-gray-500 text-xs mt-0.5 italic">{h.reason}</p>
                </div>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}
