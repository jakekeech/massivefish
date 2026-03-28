import { useEffect, useState } from 'react'
import {
  Bot,
  CheckCircle2,
  ExternalLink,
  FileText,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  TriangleAlert,
  X,
} from 'lucide-react'
import LivePreview from './LivePreview'
import { consumeEventBlocks, parseEventBlock } from '../lib/sse'

function getStatusClasses(status) {
  const tone = {
    ready_for_review: 'bg-[#22c55e]/10 text-[#86efac] border-[#22c55e]/30',
    partial: 'bg-[#eab308]/10 text-[#fde047] border-[#eab308]/30',
    login_required: 'bg-[#f97316]/10 text-[#fdba74] border-[#f97316]/30',
    manual_required: 'bg-[#ef4444]/10 text-[#fca5a5] border-[#ef4444]/30',
    openai: 'bg-[#3b82f6]/10 text-[#93c5fd] border-[#3b82f6]/30',
    template: 'bg-[#27272a] text-[#d4d4d8] border-[#3f3f46]',
  }

  return tone[status] || 'bg-[#27272a] text-[#d4d4d8] border-[#3f3f46]'
}

function formatStatusLabel(status) {
  if (!status) return 'In Progress'
  return status
    .split('_')
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(' ')
}

function ChipList({ items, emptyLabel }) {
  if (!items || items.length === 0) {
    return <p className="text-sm text-[#71717a]">{emptyLabel}</p>
  }

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className="px-2.5 py-1 rounded-full text-xs font-mono bg-[#09090b] border border-[#27272a] text-[#d4d4d8]"
        >
          {item}
        </span>
      ))}
    </div>
  )
}

export default function ApplicationCopilot({ job, onClose }) {
  const [runKey, setRunKey] = useState(0)
  const [phase, setPhase] = useState('Booting')
  const [statusMessage, setStatusMessage] = useState('Starting the TinyFish application copilot...')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const [finalStatus, setFinalStatus] = useState(null)
  const [blocked, setBlocked] = useState(null)
  const [preview, setPreview] = useState(null)
  const [trace, setTrace] = useState([])
  const [inspection, setInspection] = useState(null)
  const [coverLetter, setCoverLetter] = useState('')
  const [coverLetterSource, setCoverLetterSource] = useState(null)
  const [fillResult, setFillResult] = useState(null)

  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [])

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  useEffect(() => {
    if (!job) return undefined

    const controller = new AbortController()
    let cancelled = false

    setPhase('Starting')
    setStatusMessage(`Launching TinyFish against ${job.company_name}...`)
    setRunning(true)
    setError(null)
    setFinalStatus(null)
    setBlocked(null)
    setPreview(null)
    setTrace([])
    setInspection(null)
    setCoverLetter('')
    setCoverLetterSource(null)
    setFillResult(null)

    const appendTrace = (entry) => {
      setTrace((previous) => [...previous, entry].slice(-14))
    }

    const handleEvent = (eventName, data) => {
      if (eventName === 'apply_started') {
        setPhase('Starting')
        setStatusMessage(`TinyFish is preparing an application run for ${data.company_name}.`)
        return
      }

      if (eventName === 'apply_phase') {
        setPhase(data.phase || 'Running')
        setStatusMessage(data.message || 'TinyFish is working through the application flow.')
        return
      }

      if (eventName === 'apply_trace') {
        const text = data.message || data.purpose || data.error || data.tinyfish_type
        if (!text) return

        appendTrace({
          id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
          stage: data.stage || 'run',
          text,
        })
        return
      }

      if (eventName === 'apply_preview' && data.streaming_url) {
        setPreview({
          url: data.streaming_url,
          label: data.label || `${job.company_name} TinyFish`,
          stage: data.stage || 'run',
        })
        return
      }

      if (eventName === 'apply_inspection') {
        setInspection(data)
        setStatusMessage(data.reason || 'TinyFish mapped the visible application flow.')
        return
      }

      if (eventName === 'cover_letter_ready') {
        setCoverLetter(data.cover_letter || '')
        setCoverLetterSource(data.source || null)
        setStatusMessage('OpenAI drafted a tailored cover letter for this role.')
        return
      }

      if (eventName === 'apply_fill_result') {
        setFillResult(data)
        return
      }

      if (eventName === 'apply_blocked') {
        setRunning(false)
        setFinalStatus(data.status || 'manual_required')
        setBlocked(data)
        setPhase('Action Needed')
        setStatusMessage(data.reason || 'A manual step is required before TinyFish can continue.')
        return
      }

      if (eventName === 'apply_complete') {
        setRunning(false)
        setFinalStatus(data.status || 'ready_for_review')
        setPhase(data.status === 'ready_for_review' ? 'Ready' : 'Paused')
        setStatusMessage(data.message || 'Application copilot finished its pass.')
        return
      }

      if (eventName === 'apply_error') {
        setRunning(false)
        setFinalStatus('manual_required')
        setPhase('Error')
        setError(data.error || 'The application stream failed unexpectedly.')
        setStatusMessage('The application run failed before TinyFish could finish.')
      }
    }

    const startApply = async () => {
      try {
        const response = await fetch('/api/apply', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ job_id: job.id }),
          signal: controller.signal,
        })

        if (!response.ok) {
          const responseText = await response.text()
          throw new Error(`Application failed: ${response.status} ${responseText}`)
        }

        if (!response.body) {
          throw new Error('Application response body is not streamable')
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()

          if (done) {
            buffer = consumeEventBlocks(buffer, ({ eventName, data }) => handleEvent(eventName, data))
            if (buffer.trim()) {
              const parsed = parseEventBlock(buffer)
              if (parsed) {
                handleEvent(parsed.eventName, parsed.data)
              }
            }
            break
          }

          buffer += decoder.decode(value, { stream: true })
          buffer = consumeEventBlocks(buffer, ({ eventName, data }) => handleEvent(eventName, data))
        }
      } catch (err) {
        if (controller.signal.aborted || cancelled) {
          return
        }

        setRunning(false)
        setFinalStatus('manual_required')
        setPhase('Error')
        setError(err.message || 'Application stream failed')
        setStatusMessage('The application copilot could not complete the current run.')
      }
    }

    startApply()

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [job, runKey])

  const applicationUrl = fillResult?.application_url || blocked?.application_url || inspection?.application_url || job.job_url

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm p-4 md:p-6">
      <div className="max-w-7xl mx-auto h-full bg-[#09090b] border border-[#27272a] rounded-2xl overflow-hidden shadow-2xl">
        <div className="px-5 py-4 border-b border-[#27272a] flex items-start justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#3b82f6]/10 border border-[#3b82f6]/20 text-[#93c5fd] text-xs font-mono uppercase tracking-[0.2em]">
              <Bot className="w-4 h-4" />
              Application Copilot
            </div>
            <h2 className="text-2xl font-display font-bold mt-3">{job.job_title}</h2>
            <p className="text-[#a1a1aa] mt-1">{job.company_name}</p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-xl border border-[#27272a] text-[#a1a1aa] hover:text-white hover:border-[#3f3f46] transition-colors"
            aria-label="Close application copilot"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="grid lg:grid-cols-[1.1fr_0.9fr] h-[calc(100%-81px)]">
          <div className="overflow-y-auto p-5 space-y-5">
            <section className="bg-[#18181b] border border-[#27272a] rounded-xl p-5">
              <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                <div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-sm font-mono uppercase tracking-[0.2em] text-[#60a5fa]">
                      {phase}
                    </span>
                    <span className={`px-3 py-1 rounded-full text-xs font-mono border ${getStatusClasses(finalStatus || (running ? 'openai' : null))}`}>
                      {running ? 'In Progress' : formatStatusLabel(finalStatus)}
                    </span>
                  </div>
                  <p className="text-[#e4e4e7] text-lg mt-3">{statusMessage}</p>
                </div>

                {running && (
                  <div className="inline-flex items-center gap-2 px-4 py-3 rounded-xl bg-[#0f172a] border border-[#1e293b] text-sm font-mono text-[#93c5fd]">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    TinyFish live
                  </div>
                )}
              </div>

              <div className="flex flex-wrap gap-3 mt-5">
                <a
                  href={applicationUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#27272a] hover:bg-[#3f3f46] transition-colors text-sm font-medium"
                >
                  Open Posting
                  <ExternalLink className="w-4 h-4" />
                </a>
                {preview?.url && (
                  <a
                    href={preview.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#0f172a] border border-[#1e293b] text-[#93c5fd] hover:border-[#3b82f6] transition-colors text-sm font-medium"
                  >
                    Open Live Preview
                    <ExternalLink className="w-4 h-4" />
                  </a>
                )}
                {!running && (
                  <button
                    type="button"
                    onClick={() => setRunKey((current) => current + 1)}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#22c55e] text-black hover:bg-[#16a34a] transition-colors text-sm font-semibold"
                  >
                    <RefreshCw className="w-4 h-4" />
                    Retry Run
                  </button>
                )}
              </div>
            </section>

            {error && (
              <section className="bg-red-900/20 border border-red-500/40 rounded-xl p-5 text-red-300">
                <div className="flex items-start gap-3">
                  <TriangleAlert className="w-5 h-5 mt-0.5 flex-shrink-0" />
                  <div>
                    <h3 className="font-semibold">Application run failed</h3>
                    <p className="mt-1 text-sm">{error}</p>
                  </div>
                </div>
              </section>
            )}

            {blocked && !error && (
              <section className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-5">
                <div className="flex items-start gap-3">
                  <ShieldAlert className="w-5 h-5 mt-0.5 text-amber-300 flex-shrink-0" />
                  <div>
                    <h3 className="font-semibold text-amber-100">Manual step required</h3>
                    <p className="mt-1 text-sm text-amber-200">{blocked.reason}</p>
                    <p className="mt-3 text-sm text-[#d4d4d8]">
                      If the live preview accepts interaction, finish the login or blocker there, then hit <span className="font-semibold text-white">Retry Run</span>.
                    </p>
                  </div>
                </div>
              </section>
            )}

            {inspection && (
              <section className="bg-[#18181b] border border-[#27272a] rounded-xl p-5 space-y-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-[#22c55e]" />
                  <h3 className="font-semibold text-lg">Application Snapshot</h3>
                </div>

                <div className="grid md:grid-cols-2 gap-4 text-sm">
                  <div className="bg-[#09090b] border border-[#27272a] rounded-xl p-4">
                    <div className="text-[#71717a] font-mono uppercase tracking-wider text-xs mb-2">Platform</div>
                    <div className="text-white">{inspection.application_platform || 'Unknown'}</div>
                  </div>
                  <div className="bg-[#09090b] border border-[#27272a] rounded-xl p-4">
                    <div className="text-[#71717a] font-mono uppercase tracking-wider text-xs mb-2">Status</div>
                    <div className="text-white">{formatStatusLabel(inspection.status)}</div>
                  </div>
                </div>

                <div>
                  <div className="text-[#71717a] font-mono uppercase tracking-wider text-xs mb-2">Detected Fields</div>
                  <ChipList
                    items={inspection.fields_detected}
                    emptyLabel="TinyFish did not identify any named fields on this first pass."
                  />
                </div>

                {inspection.notes?.length > 0 && (
                  <div>
                    <div className="text-[#71717a] font-mono uppercase tracking-wider text-xs mb-2">Notes</div>
                    <ChipList items={inspection.notes} emptyLabel="No extra notes." />
                  </div>
                )}
              </section>
            )}

            {coverLetter && (
              <section className="bg-[#18181b] border border-[#27272a] rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-[#22c55e]" />
                    <h3 className="font-semibold text-lg">Cover Letter Draft</h3>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-xs font-mono border ${getStatusClasses(coverLetterSource)}`}>
                    {coverLetterSource === 'openai' ? 'OpenAI Drafted' : 'Template Fallback'}
                  </span>
                </div>

                <textarea
                  value={coverLetter}
                  readOnly
                  className="w-full min-h-72 bg-[#09090b] border border-[#27272a] rounded-xl p-4 text-sm leading-6 text-[#e4e4e7] resize-y"
                />
              </section>
            )}

            {fillResult && (
              <section className="bg-[#18181b] border border-[#27272a] rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-[#60a5fa]" />
                    <h3 className="font-semibold text-lg">Autofill Summary</h3>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-xs font-mono border ${getStatusClasses(fillResult.status)}`}>
                    {formatStatusLabel(fillResult.status)}
                  </span>
                </div>

                <p className="text-sm text-[#d4d4d8]">{fillResult.reason}</p>

                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <div className="text-[#71717a] font-mono uppercase tracking-wider text-xs mb-2">Filled Fields</div>
                    <ChipList
                      items={fillResult.filled_fields}
                      emptyLabel="No safe fields were confirmed as filled in this pass."
                    />
                  </div>
                  <div>
                    <div className="text-[#71717a] font-mono uppercase tracking-wider text-xs mb-2">Remaining Fields</div>
                    <ChipList
                      items={fillResult.remaining_fields}
                      emptyLabel="No remaining blockers were reported."
                    />
                  </div>
                </div>

                {fillResult.final_page_summary && (
                  <div className="bg-[#09090b] border border-[#27272a] rounded-xl p-4 text-sm text-[#d4d4d8]">
                    {fillResult.final_page_summary}
                  </div>
                )}

                {fillResult.notes?.length > 0 && (
                  <div>
                    <div className="text-[#71717a] font-mono uppercase tracking-wider text-xs mb-2">Notes</div>
                    <ChipList items={fillResult.notes} emptyLabel="No extra notes." />
                  </div>
                )}
              </section>
            )}

            {trace.length > 0 && (
              <section className="bg-[#18181b] border border-[#27272a] rounded-xl p-5">
                <h3 className="font-semibold text-lg mb-4">Live Agent Trace</h3>
                <div className="space-y-3">
                  {trace.map((entry) => (
                    <div
                      key={entry.id}
                      className="flex items-start gap-3 p-3 rounded-xl bg-[#09090b] border border-[#27272a]"
                    >
                      <span className="mt-1 w-2 h-2 rounded-full bg-[#22c55e] flex-shrink-0" />
                      <div>
                        <div className="text-xs font-mono uppercase tracking-wider text-[#71717a] mb-1">
                          {entry.stage}
                        </div>
                        <div className="text-sm text-[#e4e4e7]">{entry.text}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>

          <div className="border-l border-[#27272a] p-5 bg-[#050507] overflow-y-auto">
            <LivePreview
              title={preview?.label ? `${preview.label} Live Preview` : `${job.company_name} Live Preview`}
              url={preview?.url}
              message={running
                ? 'Waiting for TinyFish to surface a live browser stream...'
                : 'This run finished without exposing a new preview URL.'}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
