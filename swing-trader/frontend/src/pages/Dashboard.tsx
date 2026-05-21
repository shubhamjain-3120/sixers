import StatusBar from '../components/StatusBar'
import OpenPositions from '../components/OpenPositions'
import CandidatesTable from '../components/CandidatesTable'

export default function Dashboard() {
  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold text-white mb-4">Swing Trader</h1>
      <StatusBar />
      <OpenPositions />
      <CandidatesTable />
    </div>
  )
}
