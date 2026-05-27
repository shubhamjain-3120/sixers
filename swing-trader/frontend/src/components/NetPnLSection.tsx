import { useEffect, useState } from 'react'
import { getStatsSummary, getOpenPositions } from '../api/client'
import type { StatsSummary, OpenPosition } from '../types'

interface Props {
  refreshKey?: number
}

function fmt(n: number) {
  return (n >= 0 ? '+' : '') + '₹' + Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })
}

function PnLCard({ label, value }: { label: string; value: number | null }) {
  if (value === null) {
    return (
      <div className="flex flex-col gap-1">
        <span className="text-xs text-gray-500 uppercase tracking-wider">{label}</span>
        <span className="text-lg font-semibold text-gray-600">—</span>
      </div>
    )
  }
  const color = value >= 0 ? 'text-green-400' : 'text-red-400'
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-gray-500 uppercase tracking-wider">{label}</span>
      <span className={`text-lg font-semibold ${color}`}>{fmt(value)}</span>
    </div>
  )
}

export default function NetPnLSection({ refreshKey = 0 }: Props) {
  const [stats, setStats] = useState<StatsSummary | null>(null)
  const [positions, setPositions] = useState<OpenPosition[] | null>(null)

  useEffect(() => {
    getStatsSummary().then(setStats).catch(() => {})
    getOpenPositions().then(setPositions).catch(() => {})
  }, [refreshKey])

  // Compute FY label e.g. "FY 26-27"
  const today = new Date()
  const fyStartYear = today.getMonth() >= 3 ? today.getFullYear() : today.getFullYear() - 1
  const fyLabel = `FY ${String(fyStartYear).slice(2)}-${String(fyStartYear + 1).slice(2)}`

  const runningPnl =
    positions === null
      ? null
      : positions.reduce((sum, p) => sum + (p.pnl_inr ?? 0), 0)

  const thisMonthPnl = stats?.this_month_pnl ?? null
  const thisFyPnl = stats?.this_fy_pnl ?? null

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg px-5 py-3 mb-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-widest">Net P&amp;L</span>
      </div>
      <div className="flex gap-8">
        <PnLCard label="Running Trades" value={runningPnl} />
        <div className="w-px bg-gray-800 self-stretch" />
        <PnLCard label="This Month" value={thisMonthPnl} />
        <div className="w-px bg-gray-800 self-stretch" />
        <PnLCard label={fyLabel} value={thisFyPnl} />
      </div>
    </div>
  )
}
