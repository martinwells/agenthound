import { useState, useEffect } from 'react'
import SessionList from './components/SessionList'
import Debugger from './components/Debugger'
import LiveIndicator from './components/LiveIndicator'
import Stats from './components/Stats'

function getInitialFixture() {
  const hash = window.location.hash
  const match = hash.match(/fixture=([^&]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

function getInitialView() {
  const hash = window.location.hash
  if (hash.includes('view=stats')) return 'stats'
  return 'sessions'
}

export default function App() {
  const [selectedFixture, setSelectedFixture] = useState(getInitialFixture)
  const [liveEnabled, setLiveEnabled] = useState(true)
  const [fixtures, setFixtures] = useState([])
  const [activeView, setActiveView] = useState(getInitialView)

  useEffect(() => {
    fetch('/api/fixtures')
      .then((res) => res.ok ? res.json() : [])
      .then((data) => {
        data.sort((a, b) => {
          const ta = a.recorded_at ? new Date(a.recorded_at).getTime() : 0
          const tb = b.recorded_at ? new Date(b.recorded_at).getTime() : 0
          return tb - ta
        })
        setFixtures(data)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    function onHashChange() {
      const fixture = getInitialFixture()
      setSelectedFixture(fixture)
      setActiveView(getInitialView())
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  function handleSelect(name) {
    setSelectedFixture(name)
    setActiveView('sessions')
    window.location.hash = `fixture=${encodeURIComponent(name)}`
  }

  function handleNewFixture(payload) {
    if (!payload || !payload.summary) return
    const summary = payload.summary
    setFixtures((prev) => {
      const idx = prev.findIndex((f) => f.name === summary.name)
      if (idx >= 0) {
        const updated = [...prev]
        updated[idx] = summary
        return updated
      }
      return [summary, ...prev]
    })
  }

  function switchView(view) {
    setActiveView(view)
    if (view === 'stats') {
      setSelectedFixture(null)
      window.location.hash = 'view=stats'
    } else {
      window.location.hash = ''
    }
  }

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100">
      {/* Left sidebar — always visible */}
      <div className="w-72 flex-shrink-0 border-r border-zinc-800 flex flex-col bg-zinc-900/50">
        {/* Header */}
        <div className="px-4 py-4 border-b border-zinc-800">
          <h1 className="text-lg font-bold text-zinc-100 mb-3">
            <span className="text-emerald-400">AgentHound</span> Debugger
          </h1>
          <div className="flex items-center justify-between">
            <button
              onClick={() => setLiveEnabled((v) => !v)}
              className={`flex items-center gap-2 px-2.5 py-1 text-xs font-medium rounded-full
                           border transition-colors ${
                             liveEnabled
                               ? 'bg-emerald-400/10 border-emerald-400/30 text-emerald-400 hover:bg-emerald-400/20'
                               : 'bg-zinc-800 border-zinc-700 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-300'
                           }`}
            >
              <span
                className={`inline-block h-1.5 w-1.5 rounded-full ${
                  liveEnabled ? 'bg-emerald-400' : 'bg-zinc-500'
                }`}
              />
              {liveEnabled ? 'Live' : 'Live Off'}
            </button>
            <span className="text-xs text-zinc-500">
              {fixtures.length} session{fixtures.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>

        {/* Stats link */}
        <button
          onClick={() => switchView('stats')}
          className={`w-full px-4 py-2.5 text-left text-xs font-medium border-b border-zinc-800 transition-colors ${
            activeView === 'stats'
              ? 'text-emerald-400 bg-emerald-400/5'
              : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50'
          }`}
        >
          <svg className="inline-block w-3.5 h-3.5 mr-1.5 -mt-px" viewBox="0 0 16 16" fill="currentColor">
            <rect x="1" y="9" width="3" height="6" rx="0.5" />
            <rect x="6" y="5" width="3" height="10" rx="0.5" />
            <rect x="11" y="1" width="3" height="14" rx="0.5" />
          </svg>
          Stats
        </button>

        {/* Sessions header */}
        <div className="px-4 py-2 border-b border-zinc-800 text-[10px] uppercase tracking-wider text-zinc-500">
          Sessions
        </div>

        {/* Session list — always visible */}
        <div className="flex-1 overflow-y-auto">
          <SessionList
            fixtures={fixtures}
            selected={activeView === 'sessions' ? selectedFixture : null}
            onSelect={handleSelect}
            liveEnabled={liveEnabled}
          />
        </div>

        {/* Live indicator (hidden, just for SSE connection) */}
        {liveEnabled && (
          <LiveIndicator enabled onNewFixture={handleNewFixture} />
        )}
      </div>

      {/* Right content */}
      <div className="flex-1 min-w-0">
        {activeView === 'stats' ? (
          <Stats />
        ) : selectedFixture ? (
          <Debugger fixtureName={selectedFixture} onBack={() => {
            setSelectedFixture(null)
            window.location.hash = ''
          }} />
        ) : (
          <div className="flex items-center justify-center h-full text-zinc-500">
            {fixtures.length === 0
              ? (liveEnabled ? 'Waiting for LLM calls...' : 'No sessions recorded yet.')
              : 'Select a session to inspect'}
          </div>
        )}
      </div>
    </div>
  )
}
