import { useEffect, useState } from 'react'
import { getAuthStatus, getStatsSummary, getKiteLoginUrl } from '../api/client'
import type { AuthStatus, StatsSummary } from '../types'
import { format } from 'date-fns'

export default function StatusBar() {
  const [auth, setAuth] = useState<AuthStatus | null>(null)
  const [stats, setStats] = useState<StatsSummary | null>(null)

  useEffect(() => {
    getAuthStatus().then(setAuth).catch(() => {})
    getStatsSummary().then(setStats).catch(() => {})
  }, [])

  const handleLogin = async () => {
    try {
      const { login_url } = await getKiteLoginUrl()
      window.location.href = login_url
    } catch {}
  }

  if (auth && !auth.authenticated) {
    return (
      <div className="flex items-center gap-3 bg-red-950 border border-red-800 rounded-lg px-4 py-2 text-sm mb-4">
        <span className="text-red-400">🔴 Kite session expired — trading paused. Existing GTTs at Zerodha are safe.</span>
        <button
          onClick={handleLogin}
          className="ml-auto bg-red-700 hover:bg-red-600 text-white text-xs px-3 py-1 rounded"
        >
          Login to Kite
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-4 bg-gray-900 border border-gray-800 rounded-lg px-4 py-2 text-sm mb-4">
      <span className="text-green-400">
        🟢 Kite connected
      </span>
      {stats && (
        <>
          <span className="text-gray-400">
            Capital: <span className="text-white">₹{stats.capital_deployed.toLocaleString('en-IN')}</span>
            {' / '}
            <span className="text-gray-500">₹{(stats.capital_deployed + stats.capital_available).toLocaleString('en-IN')}</span>
            {' deployed'}
          </span>
          <span className="text-gray-400">
            Positions: <span className="text-white">{stats.open_positions}</span>
          </span>
          <span className={stats.todays_pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
            Today P&L: {stats.todays_pnl >= 0 ? '+' : ''}₹{stats.todays_pnl.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
          </span>
        </>
      )}
    </div>
  )
}
