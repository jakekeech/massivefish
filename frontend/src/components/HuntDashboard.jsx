import { useEffect, useRef, useState } from 'react'
import { Activity, Radar, Target } from 'lucide-react'
import JobFeed from './JobFeed'
import LivePreview from './LivePreview'
import StatsRow from './StatsRow'
import SwarmStatusBar from './SwarmStatusBar'

function parseEventBlock(block) {
  const lines = block.split('\n')
  let eventName = 'message'
  const dataLines = []

  for (const line of lines) {
    if (!line.trim()) continue
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim()
      continue
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim())
    }
  }

  if (dataLines.length === 0) {
    return null
  }

  const rawData = dataLines.join('\n')
  return {
    eventName,
    data: JSON.parse(rawData),
  }
}

function consumeEventBlocks(buffer, onEventBlock) {
  let workingBuffer = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  let separatorIndex = workingBuffer.indexOf('\n\n')

  while (separatorIndex !== -1) {
    const block = workingBuffer.slice(0, separatorIndex)
    workingBuffer = workingBuffer.slice(separatorIndex + 2)

    if (block.trim()) {
      const parsed = parseEventBlock(block)
      if (parsed) {
        onEventBlock(parsed)
      }
    }

    separatorIndex = workingBuffer.indexOf('\n\n')
  }

  return workingBuffer
}

export default function HuntDashboard({ huntId, searchConfig }) {
  const [statuses, setStatuses] = useState({})
  const [jobs, setJobs] = useState([])
  const [totalScraped, setTotalScraped] = useState(0)
  const [scoring, setScoring] = useState(false)
  const [complete, setComplete] = useState(false)
  const [error, setError] = useState(null)
  const [phase, setPhase] = useState('Booting')
  const [statusMessage, setStatusMessage] = useState('Preparing the InternShip voyage...')
  const [linkedinPreviewUrl, setLinkedinPreviewUrl] = useState(null)
  const [linkedinPreviewMessage, setLinkedinPreviewMessage] = useState('Waiting for a TinyFish to surface a streaming URL...')
  const startedRef = useRef(false)

  useEffect(() => {
    if (huntId === 'pending' && !startedRef.current) {
      startedRef.current = true
      startHunt()
    }
  }, [huntId])

  const startHunt = async () => {
    setPhase('Starting')
    setStatusMessage('Opening the TinyFish automation stream...')
    setError(null)

    try {
      const response = await fetch('/api/hunt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role: searchConfig.role,
          location: searchConfig.location,
          keywords: searchConfig.keywords,
          target_urls: searchConfig.target_urls,
        }),
      })

      if (!response.ok) {
        const responseText = await response.text()
        throw new Error(`Hunt failed: ${response.status} ${responseText}`)
      }

      if (!response.body) {
        throw new Error('Hunt response body is not streamable')
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
      setPhase('Error')
      setError(err.message)
      setStatusMessage('The InternShip voyage failed before results could render.')
    }
  }

  const handleEvent = (eventName, data) => {
    if (eventName === 'agent_started' && data.platform) {
      setPhase('Queued')
      setStatusMessage(`${data.label || 'This TinyFish'} is queued and ready to swim.`)
      setStatuses((previous) => ({
        ...previous,
        [data.platform]: { status: 'queued', jobs: 0, label: data.label || data.platform },
      }))
      return
    }

    if (eventName === 'agent_running' && data.platform) {
      setPhase('Scraping')
      setStatusMessage(`${data.label || 'This TinyFish'} is navigating the current and collecting listings.`)
      setStatuses((previous) => ({
        ...previous,
        [data.platform]: {
          ...(previous[data.platform] || {}),
          label: data.label || previous[data.platform]?.label || data.platform,
          status: 'running',
          jobs: previous[data.platform]?.jobs || 0,
        },
      }))
      return
    }

    if (eventName === 'agent_preview' && data.platform?.startsWith('linkedin_')) {
      if (data.streaming_url) {
        setLinkedinPreviewUrl(data.streaming_url)
        setLinkedinPreviewMessage('TinyFish preview connected.')
      }
      return
    }

    if (eventName === 'agent_preview_missing' && data.platform?.startsWith('linkedin_')) {
      setLinkedinPreviewMessage(data.message || 'This TinyFish did not emit a streaming URL.')
      return
    }

    if (eventName === 'agent_complete' && data.platform) {
      setStatusMessage(`${data.label || 'This TinyFish'} surfaced ${data.jobs_found} roles.`)
      setStatuses((previous) => ({
        ...previous,
        [data.platform]: {
          label: data.label || previous[data.platform]?.label || data.platform,
          status: 'completed',
          jobs: data.jobs_found,
          elapsed: data.elapsed,
        },
      }))
      return
    }

    if (eventName === 'agent_failed' && data.platform) {
      setPhase('Error')
      setStatusMessage(`${data.label || 'This TinyFish'} drifted off course before results were returned.`)
      setStatuses((previous) => ({
        ...previous,
        [data.platform]: {
          label: data.label || previous[data.platform]?.label || data.platform,
          status: 'failed',
          jobs: 0,
          elapsed: data.elapsed,
          error: data.error,
        },
      }))
      setError(data.error || 'TinyFish scraping failed')
      return
    }

    if (eventName === 'scoring') {
      setPhase('Scoring')
      setScoring(true)
      setStatusMessage(data.message || 'Scoring jobs with AI...')
      return
    }

    if (eventName === 'hunt_complete' && data.hunt_id) {
      setPhase('Finishing')
      setScoring(false)
      setComplete(true)
      setTotalScraped(data.total_scraped || 0)
      setStatusMessage('The InternShip voyage is complete. Loading results...')
      fetchJobs(data.hunt_id)
      return
    }

    if (eventName === 'hunt_error') {
      setPhase('Error')
      setScoring(false)
      setStatusMessage('The backend reported a voyage error.')
      setError(data.error || 'Unknown voyage error')
    }
  }

  const fetchJobs = async (id) => {
    try {
      const response = await fetch(`/api/jobs?hunt_id=${id}`)
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || `Failed to fetch jobs: ${response.status}`)
      }

      setJobs(data.jobs || [])
      setPhase('Complete')
      setStatusMessage(`Loaded ${data.jobs?.length || 0} results from the InternShip voyage.`)
    } catch (err) {
      setPhase('Error')
      setError(err.message || 'Failed to fetch jobs')
      setStatusMessage('The voyage finished, but the frontend could not load the results.')
    }
  }

  const totalJobs = Object.values(statuses).reduce((sum, status) => sum + (status.jobs || 0), 0)
  const avgScore = jobs.length > 0
    ? Math.round(jobs.reduce((sum, job) => sum + job.relevance_score, 0) / jobs.length)
    : 0

  return (
    <div className="space-y-6">
      <div className="text-center mb-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 bg-[#3b82f6]/10 border border-[#3b82f6]/20 rounded-full text-sm text-[#3b82f6] font-mono mb-3">
          <Target className="w-4 h-4" />
          <span>InternShip Voyage</span>
        </div>
        <h1 className="text-3xl font-bold font-display tracking-tight">
          <span className="text-gradient">{searchConfig.role}</span>
        </h1>
        <p className="text-[#a1a1aa] mt-1">{searchConfig.location}</p>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-500/50 rounded-xl p-4 text-red-400 flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-red-500" />
          {error}
        </div>
      )}

      <section className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 text-sm font-mono text-[#60a5fa] uppercase tracking-[0.2em]">
              <Radar className="w-4 h-4" />
              {phase}
            </div>
            <p className="text-[#e4e4e7] text-lg mt-3">{statusMessage}</p>
          </div>
          <div className="inline-flex items-center gap-2 px-4 py-3 rounded-xl bg-[#0f172a] border border-[#1e293b] text-sm font-mono text-[#93c5fd]">
            <Activity className="w-4 h-4" />
            {linkedinPreviewUrl ? 'TinyFish view connected' : 'Waiting for a TinyFish view'}
          </div>
        </div>
      </section>

      <LivePreview
        title="TinyFish Live Preview"
        url={linkedinPreviewUrl}
        message={linkedinPreviewMessage}
      />

      <SwarmStatusBar
        statuses={statuses}
        totalJobs={totalJobs}
        targetUrls={searchConfig.target_urls}
      />

      {complete && (
        <StatsRow
          totalScraped={totalScraped}
          totalAfterDedup={jobs.length}
          avgScore={avgScore}
        />
      )}

      <JobFeed jobs={jobs} loading={scoring} />
    </div>
  )
}
