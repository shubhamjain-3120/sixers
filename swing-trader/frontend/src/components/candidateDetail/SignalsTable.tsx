import type { CandidateDetail } from '../../types'

function fmt(n: number | null | undefined, dec = 2, prefix = '₹') {
  if (n == null) return '–'
  return `${prefix}${n.toFixed(dec)}`
}

function pctFmt(n: number | null | undefined) {
  if (n == null) return '–'
  const sign = n >= 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}%`
}

type Props = {
  detail: CandidateDetail
  lastSma20: number | null
  lastSma50: number | null
}

export default function SignalsTable({ detail, lastSma20, lastSma50 }: Props) {
  const signalGroups = [
    {
      title: 'Price',
      items: [
        { label: 'LTP', value: fmt(detail.ltp) },
        { label: 'Prev Close', value: fmt(detail.prev_close) },
        { label: 'Change today', value: pctFmt(detail.pct_change_today), color: (detail.pct_change_today ?? 0) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400' },
      ],
    },
    {
      title: 'Scores',
      items: [
        { label: 'Pullback Score', value: detail.score.toFixed(1), color: 'text-blue-600 dark:text-blue-300' },
        { label: 'Shubham Score', value: detail.shubham_score != null ? detail.shubham_score.toFixed(1) : '–', color: 'text-purple-600 dark:text-purple-300' },
        { label: 'RSI 14', value: detail.rsi_14?.toFixed(1) ?? '–', color: (detail.rsi_14 ?? 50) < 35 ? 'text-orange-600 dark:text-orange-400' : undefined },
      ],
    },
    {
      title: 'vs Highs & MAs',
      cols: 2 as const,
      items: [
        { label: '% Below 20D High', value: `${detail.pct_below_20d_high?.toFixed(2) ?? '–'}%`, color: 'text-orange-600 dark:text-orange-300' },
        { label: '% Below 50D High', value: `${detail.pct_below_50d_high?.toFixed(2) ?? '–'}%` },
        { label: '20DMA', value: fmt(lastSma20) },
        { label: 'Dist from 20DMA', value: pctFmt(detail.dist_from_20dma_pct) },
        { label: '50DMA', value: fmt(lastSma50) },
        { label: 'Dist from 50DMA', value: pctFmt(detail.dist_from_50dma_pct) },
      ],
    },
    {
      title: 'Support / Resistance',
      cols: 2 as const,
      items: [
        { label: 'Support (S1)', value: fmt(detail.support) },
        { label: 'Support % away', value: pctFmt(detail.support_pct_away), color: 'text-red-600 dark:text-red-300' },
        { label: 'Resistance (R1)', value: fmt(detail.resistance) },
        { label: 'Resistance % away', value: pctFmt(detail.resistance_pct_away), color: 'text-green-600 dark:text-green-300' },
      ],
    },
    {
      title: 'Activity',
      items: [
        { label: 'Volume Ratio', value: detail.volume_ratio?.toFixed(2) ?? '–', color: (detail.volume_ratio ?? 0) >= 1.5 ? 'text-amber-600 dark:text-yellow-400' : undefined },
        { label: 'Green After Red', value: detail.green_after_red ? 'Yes ✓' : 'No', color: detail.green_after_red ? 'text-green-600 dark:text-green-400' : undefined },
        { label: 'Scan Date', value: detail.scan_date },
      ],
    },
  ]

  return (
    <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-4 mb-4">
      <h2 className="text-sm font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider mb-4">All Signals</h2>
      <div className="space-y-4">
        {signalGroups.map(group => (
          <div key={group.title}>
            <div className="text-[10px] font-semibold text-gray-600 uppercase tracking-widest mb-2 border-b border-gray-200 dark:border-gray-800 pb-1">
              {group.title}
            </div>
            <div className={`grid gap-x-6 gap-y-2 ${group.cols === 2 ? 'grid-cols-2' : 'grid-cols-2 md:grid-cols-3'}`}>
              {group.items.map(({ label, value, color }) => (
                <div key={label}>
                  <div className="text-xs text-gray-500">{label}</div>
                  <div className={`text-sm font-mono ${color ?? 'text-gray-800 dark:text-gray-200'}`}>{value}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
