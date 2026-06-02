import { useEffect, useState } from 'react'
import { getAuthStatus, getStatsSummary, getKiteLoginUrl, getFunds } from '../api/client'
import type { AuthStatus, StatsSummary } from '../types'
import { format } from 'date-fns'

interface Props {
  refreshKey?: number
}

export default function StatusBar({ refreshKey = 0 }: Props) {
  const [auth, setAuth] = useState<AuthStatus | null>(null)
  const [stats, setStats] = useState<StatsSummary | null>(null)
  const [kiteFunds, setKiteFunds] = useState<number | null>(null)

  useEffect(() => {
    getAuthStatus().then(setAuth).catch(() => {})
    getStatsSummary().then(setStats).catch(() => {})
    getFunds().then(d => setKiteFunds(d.kite_funds_available)).catch(() => {})
  }, [refreshKey])

  const handleLogin = async () => {
    try {
      const { login_url } = await getKiteLoginUrl()
      window.location.href = login_url
    } catch {}
  }

  if (auth && !auth.authenticated) {
    return (
      <div className="flex items-center gap-3 bg-red-50 dark:bg-red-950 border border-red-300 dark:border-red-800 rounded-lg px-4 py-2 text-sm mb-4">
        <span className="text-red-600 dark:text-red-400">🔴 Kite session expired — trading paused. Existing GTTs at Zerodha are safe.</span>
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
    <div className="flex flex-wrap items-center gap-4 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg px-4 py-2 text-sm mb-4">
      <span className="text-green-600 dark:text-green-400">
        🟢 Kite connected
      </span>
      {stats && (
        <>
          <span className="text-gray-600 dark:text-gray-400">
            Capital: <span className="text-gray-900 dark:text-white">₹{stats.capital_deployed.toLocaleString('en-IN')}</span>
            {' / '}
            <span className="text-gray-500">₹{(stats.capital_deployed + stats.capital_available).toLocaleString('en-IN')}</span>
            {' deployed'}
          </span>
          {kiteFunds != null && (
            <>
              <span className="text-gray-300 dark:text-gray-600">|</span>
              <span className="text-gray-600 dark:text-gray-400">
                Kite funds: <span className="text-gray-900 dark:text-white">₹{kiteFunds.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
              </span>
            </>
          )}
        </>
      )}
    </div>
  )
}
