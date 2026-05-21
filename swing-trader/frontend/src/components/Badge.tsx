interface BadgeProps {
  badge: 'GREEN' | 'YELLOW' | 'RED'
  tooltip?: string
}

const config = {
  GREEN: { dot: '🟢', bg: 'bg-green-900/40 text-green-300 border-green-700' },
  YELLOW: { dot: '🟡', bg: 'bg-yellow-900/40 text-yellow-300 border-yellow-700' },
  RED: { dot: '🔴', bg: 'bg-red-900/40 text-red-300 border-red-700' },
}

export default function Badge({ badge, tooltip }: BadgeProps) {
  const c = config[badge]
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-semibold ${c.bg}`}
      title={tooltip}
    >
      {c.dot} {badge}
    </span>
  )
}
