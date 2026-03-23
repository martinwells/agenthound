import { useState, useEffect, useCallback } from 'react'
import LiveIndicator from './LiveIndicator'

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (seconds < 5) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export default function FixtureList({ onSelect, liveEnabled }) {
  const [fixtures, setFixtures] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [, setTick] = useState(0)

  // Re-render every 10s to update relative times
  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 10000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    fetch('/api/fixtures')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data) => {
        // Sort newest first
        data.sort((a, b) => {
          const ta = a.recorded_at ? new Date(a.recorded_at).getTime() : 0
          const tb = b.recorded_at ? new Date(b.recorded_at).getTime() : 0
          return tb - ta
        })
        setFixtures(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  const handleNewFixture = useCallback((payload) => {
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
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-zinc-400 text-lg">Loading...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-red-400 text-lg">Error: {error}</div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-zinc-100">
            <span className="text-emerald-400">AgentHound</span> Debugger
          </h1>
          <LiveIndicator enabled={liveEnabled} onNewFixture={handleNewFixture} />
        </div>
      </div>

      {fixtures.length === 0 ? (
        <div className="text-zinc-500 text-center py-16">
          {liveEnabled
            ? 'Waiting for LLM calls...'
            : 'No sessions recorded yet.'}
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          {fixtures.map((fixture) => (
            <button
              key={fixture.name}
              onClick={() => onSelect(fixture.name)}
              className="flex items-center gap-4 px-4 py-3 rounded-lg text-left
                         hover:bg-zinc-800/80 transition-colors cursor-pointer group"
            >
              {/* Indicator dot */}
              <span className="flex-shrink-0 h-2 w-2 rounded-full bg-emerald-400/60 group-hover:bg-emerald-400" />

              {/* Main content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-zinc-200 group-hover:text-emerald-400 transition-colors">
                    {fixture.num_llm_calls || 0} call{fixture.num_llm_calls !== 1 ? 's' : ''}
                  </span>
                  {fixture.tags && fixture.tags.length > 0 && fixture.tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-1.5 py-0.5 text-[10px] rounded bg-zinc-800 text-zinc-400 border border-zinc-700"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              {/* Time ago */}
              <span className="flex-shrink-0 text-xs text-zinc-500 tabular-nums">
                {timeAgo(fixture.recorded_at)}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
