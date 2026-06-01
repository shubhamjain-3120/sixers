import type { MarketQuote } from '../api/client'

type Direction = 'up' | 'down' | 'flat'

export function DirectionBadge({ direction }: { direction: Direction }) {
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

export function changeColor(direction: Direction): string {
  if (direction === 'up') return 'text-green-400'
  if (direction === 'down') return 'text-red-400'
  return 'text-gray-400'
}

export function fmtPct(pct: number): string {
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`
}

/** Compact colored chip — used in the dashboard cue strip. */
export function QuoteChip({ quote }: { quote: MarketQuote }) {
  return (
    <span className={`inline-flex items-baseline gap-1.5 px-2 py-1 rounded border border-gray-700 bg-gray-950/60 text-xs ${changeColor(quote.direction)}`}>
      <span className="text-gray-400 font-medium">{quote.name}</span>
      <span className="font-semibold tabular-nums">{fmtPct(quote.change_pct)}</span>
    </span>
  )
}

export function timeAgo(isoString: string): string {
  const diffMs = Date.now() - new Date(isoString).getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin === 1) return '1 min ago'
  if (diffMin < 60) return `${diffMin} min ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr === 1) return '1 hr ago'
  return `${diffHr} hr ago`
}
