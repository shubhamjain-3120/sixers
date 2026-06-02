import { useEffect, useState } from 'react'
import { getConfig, updateConfig, getKiteLoginUrl, refreshUniverse, testTelegram, triggerScan, getScanStatus } from '../api/client'
import type { Config, ScanStatus } from '../types'
import { useTheme, type Theme } from '../context/ThemeContext'

export default function Settings() {
  const [cfg, setCfg] = useState<Config | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [msg, setMsg] = useState('')
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)

  useEffect(() => {
    const defaults = { sl_mode: 'atr' as const, atr_sl_multiplier: 2.5, sl_floor_pct: 3.0, sl_cap_pct: 6.0 }
    getConfig().then(c => setCfg({ ...defaults, ...c })).catch(() => {})
    getScanStatus().then(s => { setScanStatus(s); setLastRefresh(new Date()) }).catch(() => {})
  }, [])

  const handleChange = (key: keyof Config, value: string) => {
    if (!cfg) return
    setCfg({ ...cfg, [key]: key.endsWith('_days') || key === 'total_capital_inr' || key === 'max_concurrent_positions' ? parseInt(value) : parseFloat(value) })
  }

  const handleMode = (value: string) => cfg && setCfg({ ...cfg, sl_mode: value as 'atr' | 'fixed' })

  const handleSave = async () => {
    if (!cfg) return
    setSaving(true)
    try {
      const updated = await updateConfig(cfg)
      setCfg(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e: any) {
      setMsg(`Save failed: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleKiteLogin = async () => {
    try {
      const { login_url } = await getKiteLoginUrl()
      window.location.href = login_url
    } catch (e: any) {
      setMsg(`Login URL fetch failed: ${e.message}`)
    }
  }

  const handleRefreshUniverse = async () => {
    try {
      await refreshUniverse()
      setMsg('Universe refresh started (runs in background).')
    } catch (e: any) {
      setMsg(`Refresh failed: ${e.message}`)
    }
  }

  const handleTestTelegram = async () => {
    try {
      await testTelegram()
      setMsg('Telegram test message sent!')
    } catch (e: any) {
      setMsg(`Telegram test failed: ${e?.response?.data?.detail || e.message}`)
    }
  }

  const handleRunScan = async () => {
    try {
      await triggerScan()
      setMsg('Scan started (runs in background). Check the dashboard in a few minutes.')
    } catch (e: any) {
      setMsg(`Scan failed to start: ${e.message}`)
    }
  }

  if (!cfg) return <div className="max-w-xl mx-auto px-4 py-10 text-gray-600 dark:text-gray-400">Loading…</div>

  return (
    <div className="max-w-xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold text-gray-900 dark:text-white mb-6">Settings</h1>

      {/* Appearance */}
      <Section title="Appearance">
        <ThemeToggle />
      </Section>

      {/* Kite Auth */}
      <Section title="Kite Connect">
        <button onClick={handleKiteLogin} className="btn-primary">Login to Kite</button>
      </Section>

      {/* Capital & Trading */}
      <Section title="Capital & Trading">
        <Field label="Total Capital (₹)" value={cfg.total_capital_inr} onChange={v => handleChange('total_capital_inr', v)} />
        <Field label="Allocation per trade (%)" value={cfg.nifty50_alloc_pct} onChange={v => handleChange('nifty50_alloc_pct', v)} step={0.5} />
        <Field label="Max concurrent positions" value={cfg.max_concurrent_positions} onChange={v => handleChange('max_concurrent_positions', v)} />
        <Field label="Min pullback score" value={cfg.min_score_threshold} onChange={v => handleChange('min_score_threshold', v)} />
        <Field label="Min Shubham score" value={cfg.min_shubham_score_threshold} onChange={v => handleChange('min_shubham_score_threshold', v)} />
      </Section>

      {/* Exit Rules */}
      <Section title="Exit Rules">
        <Field label="Target (%)" value={cfg.target_pct} onChange={v => handleChange('target_pct', v)} step={0.1} />
        <div className="flex items-center justify-between gap-4">
          <label className="text-sm text-gray-300 flex-1">Stop-loss mode</label>
          <select value={cfg.sl_mode} onChange={e => handleMode(e.target.value)}
            className="w-28 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-white">
            <option value="atr">Volatility (ATR)</option>
            <option value="fixed">Fixed %</option>
          </select>
        </div>
        {(!cfg.sl_mode || cfg.sl_mode === 'atr') ? (
          <>
            <Field label="ATR multiplier" value={cfg.atr_sl_multiplier} onChange={v => handleChange('atr_sl_multiplier', v)} step={0.1} />
            <Field label="SL floor (%)" value={cfg.sl_floor_pct} onChange={v => handleChange('sl_floor_pct', v)} step={0.1} />
            <Field label="SL cap (%)" value={cfg.sl_cap_pct} onChange={v => handleChange('sl_cap_pct', v)} step={0.1} />
          </>
        ) : (
          <Field label="Stop loss (%)" value={cfg.stop_loss_pct} onChange={v => handleChange('stop_loss_pct', v)} step={0.1} />
        )}
        <Field label="Time stop (trading days)" value={cfg.time_stop_days} onChange={v => handleChange('time_stop_days', v)} />
      </Section>

      {msg && <p className="text-sm text-blue-600 dark:text-blue-400 mb-4">{msg}</p>}

      <button
        onClick={handleSave}
        disabled={saving}
        className="btn-primary w-full mb-6"
      >
        {saving ? 'Saving…' : saved ? '✓ Saved' : 'Save Settings'}
      </button>

      {/* Utility actions */}
      <Section title="Actions">
        <div className="flex flex-wrap gap-3 mb-3">
          <button onClick={handleRefreshUniverse} className="btn-secondary">Refresh Universe</button>
          <button onClick={handleRunScan} className="btn-secondary">Run Scan</button>
          <button onClick={handleTestTelegram} className="btn-secondary">Test Telegram</button>
        </div>
        <div className="flex flex-wrap gap-4 text-xs text-gray-500">
          {scanStatus?.last_scan_at && (
            <span>Last scan: <span className="text-gray-700 dark:text-gray-300">{scanStatus.last_scan_at}</span></span>
          )}
          {lastRefresh && (
            <span>Last refresh: <span className="text-gray-700 dark:text-gray-300">{lastRefresh.toLocaleTimeString()}</span></span>
          )}
        </div>
      </Section>
    </div>
  )
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const options: { value: Theme; label: string }[] = [
    { value: 'light', label: '☀️ Light' },
    { value: 'dark', label: '🌙 Dark' },
  ]
  return (
    <div className="inline-flex rounded-lg border border-gray-300 dark:border-gray-700 overflow-hidden">
      {options.map(opt => (
        <button
          key={opt.value}
          onClick={() => setTheme(opt.value)}
          className={`px-4 py-2 text-sm transition-colors ${
            theme === opt.value
              ? 'bg-blue-600 text-white'
              : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-4 mb-4">
      <h2 className="text-sm font-semibold text-gray-600 dark:text-gray-400 mb-3 uppercase tracking-wider">{title}</h2>
      <div className="space-y-3">{children}</div>
    </div>
  )
}

function Field({ label, value, onChange, step = 1 }: { label: string; value: number; onChange: (v: string) => void; step?: number }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <label className="text-sm text-gray-700 dark:text-gray-300 flex-1">{label}</label>
      <input
        type="number"
        value={value}
        step={step}
        onChange={e => onChange(e.target.value)}
        className="w-28 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded px-2 py-1 text-sm text-gray-900 dark:text-white text-right"
      />
    </div>
  )
}
