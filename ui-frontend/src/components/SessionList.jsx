import { useState, useEffect, useMemo } from 'react'

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

export default function SessionList({ fixtures, selected, onSelect, liveEnabled }) {
  const [, setTick] = useState(0)
  const [activeTag, setActiveTag] = useState(null)

  // Re-render every 10s to update relative times
  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 10000)
    return () => clearInterval(interval)
  }, [])

  // Collect all unique tags
  const allTags = useMemo(() => {
    const tags = new Set()
    for (const f of fixtures) {
      for (const t of (f.tags || [])) tags.add(t)
    }
    return Array.from(tags).sort()
  }, [fixtures])

  // Filter fixtures by active tag
  const filtered = useMemo(() => {
    if (!activeTag) return fixtures
    return fixtures.filter((f) => (f.tags || []).includes(activeTag))
  }, [fixtures, activeTag])

  if (fixtures.length === 0) {
    return (
      <div className="px-4 py-8 text-center text-sm text-zinc-500">
        {liveEnabled ? 'Waiting for LLM calls...' : 'No sessions yet.'}
      </div>
    )
  }

  return (
    <div>
      {/* Tag filter pills */}
      {allTags.length > 1 && (
        <div className="flex flex-wrap gap-1.5 px-4 py-3 border-b border-zinc-800">
          <button
            onClick={() => setActiveTag(null)}
            className={`px-2 py-0.5 text-[11px] rounded-full border transition-colors ${
              activeTag === null
                ? 'bg-emerald-400/15 border-emerald-400/30 text-emerald-400'
                : 'bg-zinc-800/50 border-zinc-700 text-zinc-500 hover:text-zinc-300'
            }`}
          >
            All
          </button>
          {allTags.map((tag) => (
            <button
              key={tag}
              onClick={() => setActiveTag(activeTag === tag ? null : tag)}
              className={`px-2 py-0.5 text-[11px] rounded-full border transition-colors ${
                activeTag === tag
                  ? 'bg-emerald-400/15 border-emerald-400/30 text-emerald-400'
                  : 'bg-zinc-800/50 border-zinc-700 text-zinc-500 hover:text-zinc-300'
              }`}
            >
              {tag}
            </button>
          ))}
        </div>
      )}

      {/* Session rows */}
      <div className="py-1">
        {filtered.map((f) => {
          const isSelected = f.name === selected
          const inputK = f.input_tokens ? (f.input_tokens / 1000).toFixed(1) : null
          const outputK = f.output_tokens ? (f.output_tokens / 1000).toFixed(1) : null
          return (
            <button
              key={f.name}
              onClick={() => onSelect(f.name)}
              className={`w-full px-4 py-2.5 text-left transition-colors
                ${isSelected
                  ? 'bg-emerald-400/10 border-r-2 border-emerald-400'
                  : 'hover:bg-zinc-800/60 border-r-2 border-transparent'
                }`}
            >
              {/* Top line: tags + time */}
              <div className="flex items-center justify-between gap-2 mb-0.5">
                <div className="flex items-center gap-1.5 min-w-0">
                  {(f.tags || []).map((tag) => (
                    <span
                      key={tag}
                      className={`px-1.5 py-0 text-[10px] rounded font-medium ${
                        isSelected
                          ? 'bg-emerald-400/20 text-emerald-400'
                          : 'bg-zinc-800 text-zinc-400'
                      }`}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
                <span className="flex-shrink-0 text-[11px] text-zinc-500 tabular-nums">
                  {timeAgo(f.recorded_at)}
                </span>
              </div>

              {/* Bottom line: calls, tokens */}
              <div className="flex items-center gap-3 text-[11px] text-zinc-500 tabular-nums">
                <span>{f.num_llm_calls || 0} call{f.num_llm_calls !== 1 ? 's' : ''}</span>
                {inputK && outputK && (
                  <span>{inputK}k in / {outputK}k out</span>
                )}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
