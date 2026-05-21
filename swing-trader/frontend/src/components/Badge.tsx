interface BadgeProps {
  badge: 'GREEN' | 'YELLOW' | 'RED'
  tooltip?: string
  compact?: boolean
}

const dotColor = {
  GREEN:  'bg-green-400',
  YELLOW: 'bg-yellow-400',
  RED:    'bg-red-400',
}

const fullStyle = {
  GREEN:  'inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-semibold bg-green-900/40 text-green-300 border-green-700',
  YELLOW: 'inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-semibold bg-yellow-900/40 text-yellow-300 border-yellow-700',
  RED:    'inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-semibold bg-red-900/40 text-red-300 border-red-700',
}

export default function Badge({ badge, tooltip, compact }: BadgeProps) {
  if (compact) {
    return (
      <span
        className={`inline-block w-2.5 h-2.5 rounded-full ${dotColor[badge]}`}
        title={tooltip ?? badge}
      />
    )
  }
  return (
    <span className={fullStyle[badge]} title={tooltip}>
      {badge}
    </span>
  )
}
