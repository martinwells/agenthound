export default function Timeline({ steps, activeIndex, onSelect }) {
  return (
    <div className="flex flex-col gap-0.5 py-2 overflow-y-auto">
      {steps.map((step, idx) => {
        const isActive = idx === activeIndex
        const hasError = step.error != null
        const hasToolCalls =
          step.tool_calls && step.tool_calls.length > 0
        const toolName = hasToolCalls ? step.tool_calls[0].tool_name : null

        return (
          <button
            key={idx}
            onClick={() => onSelect(idx)}
            className={`flex items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors
              ${isActive
                ? 'bg-emerald-400/10 border-l-2 border-emerald-400'
                : 'border-l-2 border-transparent hover:bg-zinc-800/50'
              }`}
          >
            {/* Step indicator dot */}
            <div
              className={`w-2.5 h-2.5 rounded-full shrink-0
                ${hasError
                  ? 'bg-red-400'
                  : isActive
                    ? 'bg-emerald-400'
                    : 'bg-zinc-600'
                }`}
            />

            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                {/* Type icon */}
                <span className="text-xs">
                  {hasToolCalls ? (
                    <svg className="w-3.5 h-3.5 text-zinc-400 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17l-5.384 3.081A1 1 0 015 17.394V6.606a1 1 0 011.036-.857l5.384 3.081M17.5 12h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  ) : (
                    <svg className="w-3.5 h-3.5 text-zinc-400 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  )}
                </span>

                <span className={`font-mono text-xs truncate ${
                  hasError ? 'text-red-400' : isActive ? 'text-zinc-100' : 'text-zinc-400'
                }`}>
                  {toolName || 'Response'}
                </span>
              </div>

              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[10px] text-zinc-500">
                  Step {idx + 1}
                </span>
                {step.duration_ms != null && (
                  <span className="text-[10px] text-zinc-500">
                    {(step.duration_ms / 1000).toFixed(2)}s
                  </span>
                )}
              </div>
            </div>
          </button>
        )
      })}
    </div>
  )
}
