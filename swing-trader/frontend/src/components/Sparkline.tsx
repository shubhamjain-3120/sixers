interface SparklineProps {
  data: number[]
  width?: number
  height?: number
}

export default function Sparkline({ data, width = 80, height = 24 }: SparklineProps) {
  if (!data || data.length < 2) return <svg width={width} height={height} />

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1

  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - ((v - min) / range) * height
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })

  const color = data[data.length - 1] >= data[0] ? '#22c55e' : '#ef4444'

  return (
    <svg width={width} height={height} className="inline-block">
      <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  )
}
