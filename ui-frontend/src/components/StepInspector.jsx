import { useState } from 'react'

function TokenBar({ input, output }) {
  const total = (input || 0) + (output || 0)
  if (total === 0) return null
  const inputPct = ((input || 0) / total) * 100
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-emerald-400/60 rounded-l-full"
          style={{ width: `${inputPct}%` }}
        />
      </div>
      <span className="text-[10px] text-zinc-500 whitespace-nowrap">
        {total.toLocaleString()} total
      </span>
    </div>
  )
}

function CollapsibleSection({ title, defaultOpen = false, children, variant }) {
  const [open, setOpen] = useState(defaultOpen)
  const borderColor = variant === 'error' ? 'border-red-400/30' : 'border-zinc-800'
  const titleColor = variant === 'error' ? 'text-red-400' : 'text-zinc-300'

  return (
    <div className={`border ${borderColor} rounded-lg overflow-hidden`}>
      <button
        onClick={() => setOpen(!open)}
        className={`w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium
          ${titleColor} hover:bg-zinc-800/50 transition-colors`}
      >
        <span>{title}</span>
        <svg
          className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="px-4 pb-4 border-t border-zinc-800/50 max-h-[50vh] overflow-y-auto">
          {children}
        </div>
      )}
    </div>
  )
}

export default function StepInspector({ step, stepIndex, totalSteps }) {
  if (!step) {
    return (
      <div className="flex items-center justify-center h-full text-zinc-400">
        Select a step to inspect
      </div>
    )
  }

  const inputTokens = step.input_tokens || 0
  const outputTokens = step.output_tokens || 0

  return (
    <div className="flex flex-col gap-4 p-5 overflow-y-auto h-full">
      {/* Metadata grid */}
      <div className="grid grid-cols-2 gap-3">
        {step.model && (
          <div className="bg-zinc-800/50 rounded-lg px-3 py-2">
            <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-0.5">Model</div>
            <div className="text-sm font-mono text-zinc-200">{step.model}</div>
          </div>
        )}
        {step.provider && (
          <div className="bg-zinc-800/50 rounded-lg px-3 py-2">
            <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-0.5">Provider</div>
            <div className="text-sm font-mono text-zinc-200">{step.provider}</div>
          </div>
        )}
        {step.duration_ms != null && (
          <div className="bg-zinc-800/50 rounded-lg px-3 py-2">
            <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-0.5">Duration</div>
            <div className="text-sm font-mono text-zinc-200">{(step.duration_ms / 1000).toFixed(2)}s</div>
          </div>
        )}
      </div>

      {/* Token counts */}
      <div className="bg-zinc-800/50 rounded-lg px-3 py-2">
        <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Tokens</div>
        <div className="flex gap-4 text-sm font-mono">
          <span className="text-emerald-400">{inputTokens.toLocaleString()} in</span>
          <span className="text-zinc-400">/</span>
          <span className="text-zinc-200">{outputTokens.toLocaleString()} out</span>
        </div>
        <TokenBar input={inputTokens} output={outputTokens} />
      </div>

      {/* Messages in (request) */}
      {step.messages_in && step.messages_in.length > 0 && (
        <CollapsibleSection title={`Messages In (${step.messages_in.length})`}>
          <div className="flex flex-col gap-2 mt-3">
            {step.messages_in.map((msg, i) => (
              <div key={i} className="bg-zinc-900 rounded p-2">
                <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">
                  {msg.role || 'unknown'}
                </div>
                <pre className="font-mono text-xs text-zinc-300 whitespace-pre-wrap break-words">
                  {typeof msg.content === 'string'
                    ? msg.content
                    : JSON.stringify(msg.content, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Tool calls */}
      {step.tool_calls && step.tool_calls.length > 0 && (
        <CollapsibleSection title={`Tool Calls (${step.tool_calls.length})`} defaultOpen>
          <div className="flex flex-col gap-3 mt-3">
            {step.tool_calls.map((tc, i) => (
              <div key={i} className="bg-zinc-900 rounded-lg p-3">
                <div className="text-sm font-mono text-emerald-400 mb-2">
                  {tc.tool_name}
                </div>
                {tc.arguments && Object.keys(tc.arguments).length > 0 && (
                  <div className="mb-2">
                    <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Arguments</div>
                    <pre className="font-mono text-xs text-zinc-300 bg-zinc-950 rounded p-2 overflow-x-auto whitespace-pre-wrap break-words">
                      {formatJson(tc.arguments)}
                    </pre>
                  </div>
                )}
                {tc.result != null && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Result</div>
                    <pre className="font-mono text-xs text-zinc-300 bg-zinc-950 rounded p-2 overflow-x-auto whitespace-pre-wrap break-words">
                      {formatJson(tc.result)}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Response text */}
      <CollapsibleSection
        title="Response"
        defaultOpen={!step.tool_calls || step.tool_calls.length === 0}
      >
        <div className="mt-3">
          {step.response_text ? (
            <pre className="font-mono text-xs text-zinc-300 whitespace-pre-wrap break-words">
              {step.response_text}
            </pre>
          ) : (
            <div className="text-zinc-500 text-sm italic">
              (empty - tool call only)
            </div>
          )}
        </div>
      </CollapsibleSection>

      {/* Error */}
      {step.error && (
        <CollapsibleSection title="Error" defaultOpen variant="error">
          <pre className="font-mono text-sm text-red-400 mt-3 whitespace-pre-wrap break-words">
            {typeof step.error === 'string'
              ? step.error
              : JSON.stringify(step.error, null, 2)}
          </pre>
        </CollapsibleSection>
      )}
    </div>
  )
}

function formatJson(value) {
  if (value == null) return ''
  if (typeof value === 'string') {
    try {
      return JSON.stringify(JSON.parse(value), null, 2)
    } catch {
      return value
    }
  }
  return JSON.stringify(value, null, 2)
}
