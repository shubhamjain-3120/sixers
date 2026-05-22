import { useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, ReferenceLine, ReferenceArea,
} from 'recharts'

export type ChartPoint = {
  date: string
  close: number | null
  sma20: number | null
  sma50: number | null
}

type Props = {
  chartData: ChartPoint[]
  support: number | null
  resistance: number | null
}

export default function PriceChart({ chartData, support, resistance }: Props) {
  const [zoomLeft, setZoomLeft] = useState<string | null>(null)
  const [zoomRight, setZoomRight] = useState<string | null>(null)
  const [zoomDomain, setZoomDomain] = useState<[string, string] | null>(null)
  const [isSelecting, setIsSelecting] = useState(false)

  const visibleData = zoomDomain
    ? chartData.filter(d => d.date >= zoomDomain[0] && d.date <= zoomDomain[1])
    : chartData

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
      <div className="flex items-center gap-2 mb-1">
        <h2 className="text-sm text-gray-400">90-day Close</h2>
        {zoomDomain && (
          <button onClick={() => setZoomDomain(null)} className="text-xs text-blue-400 hover:text-blue-300">
            Reset zoom
          </button>
        )}
      </div>
      {support && (
        <p className="text-xs text-gray-600 mb-3">
          S1 ₹{support.toFixed(2)} · R1 ₹{resistance?.toFixed(2) ?? '–'}
        </p>
      )}
      <ResponsiveContainer width="100%" height={300}>
        <LineChart
          data={visibleData}
          margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
          style={{ cursor: isSelecting ? 'crosshair' : 'default' }}
          onMouseDown={e => {
            const label = e?.activeLabel as string | undefined
            if (!label) return
            setZoomLeft(label)
            setIsSelecting(true)
          }}
          onMouseMove={e => {
            if (!isSelecting) return
            const label = e?.activeLabel as string | undefined
            if (label) setZoomRight(label)
          }}
          onMouseUp={() => {
            if (isSelecting && zoomLeft && zoomRight && zoomLeft !== zoomRight) {
              const [a, b] = [zoomLeft, zoomRight].sort()
              setZoomDomain([a, b])
            }
            setIsSelecting(false)
            setZoomLeft(null)
            setZoomRight(null)
          }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis
            dataKey="date"
            tick={{ fill: '#6b7280', fontSize: 9 }}
            tickFormatter={v => v.slice(5)}
            interval={6}
          />
          <YAxis domain={['auto', 'auto']} tick={{ fill: '#6b7280', fontSize: 10 }} width={58} />
          <Tooltip
            contentStyle={{ background: '#111827', border: '1px solid #374151', color: '#fff', fontSize: 12 }}
            formatter={(v: number, name: string) => [`₹${v?.toFixed(2)}`, name]}
            labelFormatter={l => `Date: ${l}`}
          />
          {support && (
            <ReferenceLine y={support} stroke="#ef4444" strokeDasharray="4 2" strokeWidth={1} />
          )}
          {resistance && (
            <ReferenceLine y={resistance} stroke="#22c55e" strokeDasharray="4 2" strokeWidth={1} />
          )}
          <Line
            type="linear"
            dataKey="close"
            stroke="#60a5fa"
            strokeWidth={1.5}
            dot={{ r: 2, fill: '#60a5fa', strokeWidth: 0 }}
            activeDot={{ r: 4 }}
            name="Close"
            connectNulls
          />
          <Line type="monotone" dataKey="sma20" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="20DMA" connectNulls />
          <Line type="monotone" dataKey="sma50" stroke="#a855f7" dot={false} strokeWidth={1.5} name="50DMA" connectNulls />
          {isSelecting && zoomLeft && zoomRight && (
            <ReferenceArea x1={zoomLeft} x2={zoomRight} fill="#60a5fa" fillOpacity={0.1} strokeOpacity={0.3} />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
