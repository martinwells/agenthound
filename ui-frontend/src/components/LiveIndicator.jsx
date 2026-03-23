import { useState, useEffect, useRef } from 'react'

export default function LiveIndicator({ enabled, onNewFixture }) {
  const [connected, setConnected] = useState(false)
  const [sessionCount, setSessionCount] = useState(0)
  const eventSourceRef = useRef(null)
  const retryTimeoutRef = useRef(null)
  const onNewFixtureRef = useRef(onNewFixture)
  onNewFixtureRef.current = onNewFixture

  useEffect(() => {
    if (!enabled) {
      // Clean up when disabled
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current)
        retryTimeoutRef.current = null
      }
      setConnected(false)
      return
    }

    function connect() {
      const es = new EventSource('/api/live')
      eventSourceRef.current = es

      es.onopen = () => {
        setConnected(true)
      }

      es.addEventListener('fixture_update', (e) => {
        try {
          const payload = JSON.parse(e.data)
          if (payload.type === 'new') {
            setSessionCount((c) => c + 1)
          }
          if (onNewFixtureRef.current) {
            onNewFixtureRef.current(payload)
          }
        } catch {
          // ignore parse errors
        }
      })

      es.onerror = () => {
        setConnected(false)
        es.close()
        eventSourceRef.current = null
        // Retry after 3 seconds
        retryTimeoutRef.current = setTimeout(connect, 3000)
      }
    }

    connect()

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current)
        retryTimeoutRef.current = null
      }
    }
  }, [enabled])  // eslint-disable-line react-hooks/exhaustive-deps

  if (!enabled) return null

  return (
    <div className="flex items-center gap-2">
      {connected ? (
        <>
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
          </span>
          <span className="text-xs text-emerald-400 font-medium">Live</span>
        </>
      ) : (
        <>
          <span className="relative flex h-2.5 w-2.5">
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-zinc-500" />
          </span>
          <span className="text-xs text-zinc-500 font-medium">Reconnecting...</span>
        </>
      )}
      {sessionCount > 0 && (
        <span className="text-xs text-zinc-500">
          +{sessionCount} new
        </span>
      )}
    </div>
  )
}
