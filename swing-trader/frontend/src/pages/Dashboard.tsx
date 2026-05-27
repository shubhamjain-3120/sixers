import { useState } from 'react'
import StatusBar from '../components/StatusBar'
import NetPnLSection from '../components/NetPnLSection'
import OpenPositions from '../components/OpenPositions'
import CandidatesTable from '../components/CandidatesTable'

export default function Dashboard() {
  const [statsKey, setStatsKey] = useState(0)
  const refresh = () => setStatsKey(k => k + 1)

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold text-white mb-4">Swing Trader</h1>
      <StatusBar refreshKey={statsKey} />
      <NetPnLSection refreshKey={statsKey} />
      <OpenPositions onTradeChange={refresh} />
      <CandidatesTable onTradeChange={refresh} />
    </div>
  )
}
