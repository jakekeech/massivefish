import { useState, useEffect, useRef } from 'react'
import { Target } from 'lucide-react'
import SwarmStatusBar from './SwarmStatusBar'
import StatsRow from './StatsRow'
import JobFeed from './JobFeed'

export default function HuntDashboard({ huntId, searchConfig }) {
  const [statuses, setStatuses] = useState({})
  const [jobs, setJobs] = useState([])
  const [totalScraped, setTotalScraped] = useState(0)
  const [scoring, setScoring] = useState(false)
  const [complete, setComplete] = useState(false)
  const [error, setError] = useState(null)
  const startedRef = useRef(false)

  useEffect(() => {
    if (huntId === 'pending' && !startedRef.current) {
      startedRef.current = true
      startHunt()
    }
  }, [huntId])

  const startHunt = async () => {
    try {
      // Use fetch with streaming response for SSE
      const response = await fetch('/api/hunt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role: searchConfig.role,
          location: searchConfig.location,
          keywords: searchConfig.keywords,
        }),
      })

      if (!response.ok) {
        throw new Error(`Hunt failed: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data:')) {
            try {
              const data = JSON.parse(line.slice(5).trim())
              handleEvent(data)
            } catch (e) {
              // Skip malformed JSON
            }
          }
        }
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const handleEvent = (data) => {
    // Determine event type from data content
    if (data.platform && data.status === 'queued') {
      setStatuses(prev => ({
        ...prev,
        [data.platform]: { status: 'queued', jobs: 0 }
      }))
    } else if (data.platform && data.jobs_found !== undefined) {
      setStatuses(prev => ({
        ...prev,
        [data.platform]: {
          status: 'completed',
          jobs: data.jobs_found,
          elapsed: data.elapsed
        }
      }))
    } else if (data.platform && data.error) {
      setStatuses(prev => ({
        ...prev,
        [data.platform]: {
          status: 'failed',
          jobs: 0,
          elapsed: data.elapsed,
          error: data.error
        }
      }))
    } else if (data.message && data.message.includes('Scoring')) {
      setScoring(true)
    } else if (data.hunt_id) {
      // Hunt complete
      setScoring(false)
      setComplete(true)
      setTotalScraped(data.total_scraped || 0)
      fetchJobs(data.hunt_id)
    }
  }

  const fetchJobs = async (id) => {
    try {
      const res = await fetch(`/api/jobs?hunt_id=${id}`)
      const data = await res.json()
      setJobs(data.jobs || [])
    } catch (err) {
      setError('Failed to fetch jobs')
    }
  }

  const totalJobs = Object.values(statuses).reduce((sum, s) => sum + (s.jobs || 0), 0)
  const avgScore = jobs.length > 0
    ? Math.round(jobs.reduce((sum, j) => sum + j.relevance_score, 0) / jobs.length)
    : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center mb-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 bg-[#3b82f6]/10 border border-[#3b82f6]/20 rounded-full text-sm text-[#3b82f6] font-mono mb-3">
          <Target className="w-4 h-4" />
          <span>Active Hunt</span>
        </div>
        <h1 className="text-3xl font-bold">
          <span className="text-gradient">{searchConfig.role}</span>
        </h1>
        <p className="text-[#a1a1aa] mt-1">{searchConfig.location}</p>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-900/20 border border-red-500/50 rounded-xl p-4 text-red-400 flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-red-500" />
          {error}
        </div>
      )}

      {/* Swarm Status */}
      <SwarmStatusBar statuses={statuses} totalJobs={totalJobs} />

      {/* Stats (only show when complete) */}
      {complete && (
        <StatsRow
          totalScraped={totalScraped}
          totalAfterDedup={jobs.length}
          avgScore={avgScore}
        />
      )}

      {/* Job Feed */}
      <JobFeed jobs={jobs} loading={scoring} />
    </div>
  )
}
