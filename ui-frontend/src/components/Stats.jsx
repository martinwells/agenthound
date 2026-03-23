import { useState, useEffect } from 'react'

const COLORS = [
  '#34d399', // emerald-400
  '#60a5fa', // blue-400
  '#f472b6', // pink-400
  '#fbbf24', // amber-400
  '#a78bfa', // violet-400
  '#fb923c', // orange-400
  '#2dd4bf', // teal-400
  '#e879f9', // fuchsia-400
]

function StatCard({ label, value, sub }) {
  return (
    <div className="bg-zinc-800/50 rounded-lg px-4 py-3">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">{label}</div>
      <div className="text-xl font-mono text-zinc-100">{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-0.5">{sub}</div>}
    </div>
  )
}

function formatTokens(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return `${n}`
}

// ── Donut Chart ─────────────────────────────────────────────────────

function DonutChart({ title, data }) {
  const [hovered, setHovered] = useState(null)

  if (!data || Object.keys(data).length === 0) return null

  const sorted = Object.entries(data).sort((a, b) => b[1] - a[1])
  const total = sorted.reduce((s, [, v]) => s + v, 0)

  // Build arc segments
  const size = 120
  const cx = size / 2
  const cy = size / 2
  const r = 44
  const stroke = 14
  const circumference = 2 * Math.PI * r
  let offset = 0
  const segments = sorted.map(([name, count], i) => {
    const pct = count / total
    const dashLen = pct * circumference
    const seg = { name, count, pct, color: COLORS[i % COLORS.length], offset, dashLen }
    offset += dashLen
    return seg
  })

  return (
    <div className="bg-zinc-800/50 rounded-lg px-4 py-3">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-3">{title}</div>
      <div className="flex items-center gap-4">
        {/* SVG donut */}
        <div className="relative shrink-0" style={{ width: size, height: size }}>
          <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
            {/* Background ring */}
            <circle cx={cx} cy={cy} r={r} fill="none" stroke="#27272a" strokeWidth={stroke} />
            {/* Data segments */}
            {segments.map((seg, i) => (
              <circle
                key={seg.name}
                cx={cx} cy={cy} r={r}
                fill="none"
                stroke={seg.color}
                strokeWidth={hovered === i ? stroke + 4 : stroke}
                strokeDasharray={`${seg.dashLen} ${circumference - seg.dashLen}`}
                strokeDashoffset={-seg.offset}
                transform={`rotate(-90 ${cx} ${cy})`}
                style={{ transition: 'stroke-width 0.15s', cursor: 'pointer' }}
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
                opacity={hovered !== null && hovered !== i ? 0.4 : 1}
              />
            ))}
          </svg>
          {/* Center label */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            {hovered !== null ? (
              <>
                <span className="text-sm font-mono text-zinc-100">{segments[hovered].count}</span>
                <span className="text-[9px] text-zinc-500">{(segments[hovered].pct * 100).toFixed(0)}%</span>
              </>
            ) : (
              <>
                <span className="text-sm font-mono text-zinc-100">{total}</span>
                <span className="text-[9px] text-zinc-500">total</span>
              </>
            )}
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-col gap-1.5 min-w-0">
          {segments.map((seg, i) => (
            <div
              key={seg.name}
              className="flex items-center gap-2 cursor-pointer"
              onMouseEnter={() => setHovered(i)}
              onMouseLeave={() => setHovered(null)}
            >
              <span
                className="inline-block w-2.5 h-2.5 rounded-sm shrink-0"
                style={{ background: seg.color, opacity: hovered !== null && hovered !== i ? 0.4 : 1 }}
              />
              <span className="text-xs text-zinc-300 truncate" title={seg.name}>{seg.name}</span>
              <span className="text-[10px] font-mono text-zinc-500 ml-auto shrink-0">{seg.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Bar Chart (tokens per session) ──────────────────────────────────

function TokenBarChart({ sessions }) {
  const [hovered, setHovered] = useState(null)

  if (!sessions || sessions.length === 0) return null

  const maxTokens = Math.max(...sessions.map((s) => (s.input_tokens || 0) + (s.output_tokens || 0)), 1)
  const barWidth = Math.max(Math.min(40, 600 / sessions.length - 2), 8)
  const chartHeight = 140
  const chartWidth = sessions.length * (barWidth + 2)

  return (
    <div className="bg-zinc-800/50 rounded-lg px-4 py-3">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-3">Tokens per Session</div>
      <div className="overflow-x-auto">
        <svg
          width={Math.max(chartWidth, 200)}
          height={chartHeight + 24}
          viewBox={`0 0 ${Math.max(chartWidth, 200)} ${chartHeight + 24}`}
        >
          {/* Bars */}
          {sessions.map((s, i) => {
            const inp = s.input_tokens || 0
            const outp = s.output_tokens || 0
            const total = inp + outp
            const fullH = (total / maxTokens) * chartHeight
            const inpH = total > 0 ? (inp / total) * fullH : 0
            const outH = fullH - inpH
            const x = i * (barWidth + 2)
            const isHovered = hovered === i

            return (
              <g
                key={i}
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Output (bottom) */}
                <rect
                  x={x} y={chartHeight - fullH}
                  width={barWidth} height={outH}
                  rx={2}
                  fill="#71717a"
                  opacity={isHovered ? 1 : 0.5}
                  style={{ transition: 'opacity 0.1s' }}
                />
                {/* Input (top) */}
                <rect
                  x={x} y={chartHeight - fullH + outH}
                  width={barWidth} height={inpH}
                  rx={2}
                  fill="#34d399"
                  opacity={isHovered ? 1 : 0.6}
                  style={{ transition: 'opacity 0.1s' }}
                />
                {/* Tooltip */}
                {isHovered && (
                  <g>
                    <rect
                      x={Math.min(x, chartWidth - 110)}
                      y={Math.max(chartHeight - fullH - 38, 0)}
                      width={108} height={32} rx={4}
                      fill="#27272a" stroke="#3f3f46" strokeWidth={1}
                    />
                    <text
                      x={Math.min(x, chartWidth - 110) + 6}
                      y={Math.max(chartHeight - fullH - 38, 0) + 13}
                      fill="#a1a1aa" fontSize={9} fontFamily="monospace"
                    >
                      in: {formatTokens(inp)} / out: {formatTokens(outp)}
                    </text>
                    <text
                      x={Math.min(x, chartWidth - 110) + 6}
                      y={Math.max(chartHeight - fullH - 38, 0) + 26}
                      fill="#d4d4d8" fontSize={9} fontFamily="monospace"
                    >
                      {s.num_calls} call{s.num_calls !== 1 ? 's' : ''}
                    </text>
                  </g>
                )}
              </g>
            )
          })}
          {/* X-axis line */}
          <line x1={0} y1={chartHeight} x2={Math.max(chartWidth, 200)} y2={chartHeight} stroke="#3f3f46" strokeWidth={1} />
          {/* Legend */}
          <rect x={0} y={chartHeight + 8} width={8} height={8} rx={2} fill="#34d399" opacity={0.6} />
          <text x={12} y={chartHeight + 16} fill="#71717a" fontSize={10}>Input</text>
          <rect x={50} y={chartHeight + 8} width={8} height={8} rx={2} fill="#71717a" opacity={0.5} />
          <text x={62} y={chartHeight + 16} fill="#71717a" fontSize={10}>Output</text>
        </svg>
      </div>
    </div>
  )
}

// ── Calls-per-Session Sparkline ─────────────────────────────────────

function CallsSparkline({ sessions }) {
  if (!sessions || sessions.length < 2) return null

  const values = sessions.map((s) => s.num_calls || 0)
  const max = Math.max(...values, 1)
  const w = 300
  const h = 48
  const step = w / (values.length - 1)

  const points = values.map((v, i) => `${i * step},${h - (v / max) * (h - 4)}`).join(' ')

  return (
    <div className="bg-zinc-800/50 rounded-lg px-4 py-3">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-2">LLM Calls per Session</div>
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="w-full" preserveAspectRatio="none">
        {/* Area fill */}
        <polygon
          points={`0,${h} ${points} ${w},${h}`}
          fill="#34d399" opacity={0.1}
        />
        {/* Line */}
        <polyline
          points={points}
          fill="none" stroke="#34d399" strokeWidth={1.5} strokeLinejoin="round"
        />
      </svg>
      <div className="flex justify-between text-[10px] text-zinc-600 mt-1">
        <span>oldest</span>
        <span>newest</span>
      </div>
    </div>
  )
}

// ── Main Stats Component ────────────────────────────────────────────

export default function Stats() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/api/stats')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data) => {
        setStats(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-zinc-400 text-lg">Loading stats...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-red-400 text-lg">Error: {error}</div>
      </div>
    )
  }

  if (!stats) return null

  const totalTokens = (stats.total_input_tokens || 0) + (stats.total_output_tokens || 0)

  return (
    <div className="flex flex-col h-screen">
      {/* Top bar */}
      <div className="flex items-center px-4 py-3 border-b border-zinc-800 bg-zinc-900 shrink-0">
        <span className="text-sm font-medium text-zinc-100">Dashboard</span>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto flex flex-col gap-6">
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Sessions" value={stats.total_fixtures || 0} />
            <StatCard label="LLM Calls" value={stats.total_llm_calls || 0} />
            <StatCard
              label="Tokens In"
              value={formatTokens(stats.total_input_tokens || 0)}
              sub={`${(stats.total_input_tokens || 0).toLocaleString()} total`}
            />
            <StatCard
              label="Tokens Out"
              value={formatTokens(stats.total_output_tokens || 0)}
              sub={`${(stats.total_output_tokens || 0).toLocaleString()} total`}
            />
          </div>

          {/* All graphs in 2-column grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Token distribution bar */}
            {totalTokens > 0 && (
              <div className="bg-zinc-800/50 rounded-lg px-4 py-3">
                <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-2">Token Distribution</div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-3 bg-zinc-900 rounded-full overflow-hidden flex">
                    <div
                      className="h-full bg-emerald-400/60"
                      style={{ width: `${((stats.total_input_tokens || 0) / totalTokens) * 100}%` }}
                    />
                    <div
                      className="h-full bg-zinc-500/60"
                      style={{ width: `${((stats.total_output_tokens || 0) / totalTokens) * 100}%` }}
                    />
                  </div>
                </div>
                <div className="flex justify-between mt-1.5 text-xs text-zinc-500">
                  <span>
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-400/60 mr-1" />
                    Input: {formatTokens(stats.total_input_tokens || 0)}
                  </span>
                  <span>
                    <span className="inline-block w-2 h-2 rounded-full bg-zinc-500/60 mr-1" />
                    Output: {formatTokens(stats.total_output_tokens || 0)}
                  </span>
                </div>
              </div>
            )}

            {/* Calls sparkline */}
            <CallsSparkline sessions={stats.sessions} />

            {/* Tokens per session bar chart */}
            <TokenBarChart sessions={stats.sessions} />

            {/* Donut charts */}
            <DonutChart title="Models" data={stats.models} />
            <DonutChart title="Providers" data={stats.providers} />
            {stats.tags && Object.keys(stats.tags).length > 0 && (
              <DonutChart title="Tags" data={stats.tags} />
            )}
          </div>

          {stats.latest_fixture && (
            <div className="text-xs text-zinc-500">
              Latest session: <span className="font-mono text-zinc-400">{stats.latest_fixture}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
