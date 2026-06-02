import { BrowserRouter, Routes, Route, Navigate, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import History from './pages/History'
import Settings from './pages/Settings'
import CandidateDetail from './pages/CandidateDetail'
import MarketNews from './pages/MarketNews'

function Nav() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded text-sm transition-colors ${isActive ? 'bg-gray-200 text-gray-900 dark:bg-gray-800 dark:text-white' : 'text-gray-500 hover:text-gray-900 dark:hover:text-white'}`

  return (
    <nav className="border-b border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-950 sticky top-0 z-10">
      <div className="max-w-6xl mx-auto px-4 flex items-center gap-1 h-12">
        <span className="text-gray-900 dark:text-white font-bold mr-4 text-sm">📈 SwingTrader</span>
        <NavLink to="/dashboard" className={linkClass}>Dashboard</NavLink>
        <NavLink to="/history" className={linkClass}>History</NavLink>
        <NavLink to="/settings" className={linkClass}>Settings</NavLink>
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/candidate/:symbol" element={<CandidateDetail />} />
        <Route path="/market-news" element={<MarketNews />} />
        <Route path="/history" element={<History />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </BrowserRouter>
  )
}
