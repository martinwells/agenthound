import { useState, useEffect, useCallback } from 'react'
import Timeline from './Timeline'
import StepInspector from './StepInspector'

function getInitialStep() {
  const hash = window.location.hash
  const match = hash.match(/step=(\d+)/)
  return match ? parseInt(match[1], 10) - 1 : 0
}

function updateStepInHash(stepIndex) {
  const hash = window.location.hash
  const stepStr = `step=${stepIndex + 1}`
  if (hash.includes('step=')) {
    window.location.hash = hash.replace(/step=\d+/, stepStr)
  } else {
    window.location.hash = hash + (hash ? '&' : '') + stepStr
  }
}

function formatTokens(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return `${n}`
}

export default function Debugger({ fixtureName, onBack }) {
  const [steps, setSteps] = useState([])
  const [activeStep, setActiveStep] = useState(getInitialStep)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`/api/fixtures/${encodeURIComponent(fixtureName)}/steps`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data) => {
        setSteps(data.steps || [])
        setLoading(false)
        // Clamp initial step to valid range
        const stepCount = (data.steps || []).length
        setActiveStep((prev) => Math.min(prev, Math.max(stepCount - 1, 0)))
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [fixtureName])

  const goToStep = useCallback(
    (idx) => {
      if (idx < 0 || idx >= steps.length) return
      setActiveStep(idx)
      updateStepInHash(idx)
    },
    [steps.length]
  )

  // Keyboard navigation
  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault()
        goToStep(activeStep - 1)
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault()
        goToStep(activeStep + 1)
      } else if (e.key === 'Home') {
        e.preventDefault()
        goToStep(0)
      } else if (e.key === 'End') {
        e.preventDefault()
        goToStep(steps.length - 1)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [activeStep, goToStep, steps.length])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-zinc-400 text-lg">Loading steps...</div>
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

  const currentStep = steps[activeStep] || null
  const totalInput = steps.reduce((sum, s) => sum + (s.input_tokens || 0), 0)
  const totalOutput = steps.reduce((sum, s) => sum + (s.output_tokens || 0), 0)

  return (
    <div className="flex flex-col h-screen">
      {/* Top bar with nav */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-800 bg-zinc-900 shrink-0">
        <button
          onClick={() => goToStep(activeStep - 1)}
          disabled={activeStep <= 0}
          className="flex items-center gap-1 px-2.5 py-1 text-xs rounded
                     bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100
                     disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Prev
        </button>

        <div className="flex items-center gap-4 text-xs">
          <span className="font-mono text-zinc-400">{fixtureName}</span>
          <span className="text-zinc-600">|</span>
          <span className="text-zinc-400">
            Step <span className="text-zinc-100 font-mono">{activeStep + 1}</span> of{' '}
            <span className="text-zinc-100 font-mono">{steps.length}</span>
          </span>
          <span className="text-zinc-600">|</span>
          <span className="font-mono">
            <span className="text-emerald-400">{formatTokens(totalInput)} in</span>
            {' / '}
            <span className="text-zinc-200">{formatTokens(totalOutput)} out</span>
          </span>
        </div>

        <button
          onClick={() => goToStep(activeStep + 1)}
          disabled={activeStep >= steps.length - 1}
          className="flex items-center gap-1 px-2.5 py-1 text-xs rounded
                     bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100
                     disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          Next
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {/* Main content area */}
      <div className="flex flex-1 min-h-0">
        {/* Timeline sidebar */}
        <div className="w-56 shrink-0 border-r border-zinc-800 bg-zinc-900/50 overflow-y-auto">
          <Timeline
            steps={steps}
            activeIndex={activeStep}
            onSelect={goToStep}
          />
        </div>

        {/* Step inspector */}
        <div className="flex-1 min-w-0 overflow-y-auto">
          <StepInspector
            step={currentStep}
            stepIndex={activeStep}
            totalSteps={steps.length}
          />
        </div>
      </div>
    </div>
  )
}
