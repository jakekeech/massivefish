import { Check, Loader2, Radio, X } from 'lucide-react'

const DEFAULT_LANES = [
  { id: 'linkedin_0', name: 'LinkedIn', color: '#0a66c2' },
]

function laneNameFromUrl(url, index) {
  try {
    const { hostname } = new URL(url.startsWith('http') ? url : `https://${url}`)
    return hostname.replace('www.', '') || `Target ${index + 1}`
  } catch {
    return `Target ${index + 1}`
  }
}

function laneIdFromUrl(url, index) {
  try {
    const { hostname } = new URL(url.startsWith('http') ? url : `https://${url}`)
    if (hostname.includes('linkedin.com')) return `linkedin_${index}`
    if (hostname.includes('indeed.com')) return `indeed_${index}`
  } catch {
    return `custom_${index}`
  }
  return `custom_${index}`
}

export default function SwarmStatusBar({ statuses, totalJobs, targetUrls = [] }) {
  const completedCount = Object.values(statuses).filter((status) => status.status === 'completed').length
  const runningCount = Object.values(statuses).filter((status) => status.status === 'running').length

  const configuredLanes = targetUrls.length > 0
    ? targetUrls.map((url, index) => ({
      id: laneIdFromUrl(url, index),
      name: laneNameFromUrl(url, index),
      color: '#3b82f6',
    }))
    : DEFAULT_LANES

  const dynamicLanes = Object.entries(statuses).map(([id, status]) => ({
    id,
    name: status.label || id,
    color: '#3b82f6',
  }))

  const seen = new Set()
  const lanes = [...configuredLanes, ...dynamicLanes].filter((lane) => {
    if (seen.has(lane.id)) return false
    seen.add(lane.id)
    return true
  })

  return (
    <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6 overflow-hidden">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Radio className="w-5 h-5 text-[#22c55e]" />
            {runningCount > 0 && (
              <span className="absolute -top-1 -right-1 w-2 h-2 bg-[#22c55e] rounded-full animate-ping" />
            )}
          </div>
          <h2 className="text-lg font-bold font-display tracking-tight">
            TINYFISH <span className="text-[#22c55e]">RELEASED</span>
          </h2>
        </div>
        <div className="flex items-center gap-4 text-sm font-mono">
          <span className="text-[#a1a1aa]">
            <span className="text-white font-bold">{totalJobs}</span> jobs found
          </span>
          <span className="text-[#22c55e]">{completedCount}/{lanes.length}</span>
        </div>
      </div>

      <div className="space-y-3">
        {lanes.map((lane, index) => {
          const status = statuses[lane.id] || { status: 'queued', jobs: 0, label: lane.name }
          const isCompleted = status.status === 'completed'
          const isFailed = status.status === 'failed'
          const isRunning = status.status === 'running'
          const isQueued = status.status === 'queued'

          return (
            <div
              key={lane.id}
              className="flex items-center gap-4"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <span className="w-28 text-sm text-[#a1a1aa] font-mono truncate">
                {status.label || lane.name}
              </span>

              <div className="flex-1 h-2.5 bg-[#27272a] rounded-full overflow-hidden relative">
                <div
                  className={`h-full transition-all duration-700 ease-out rounded-full ${
                    isCompleted ? 'bg-[#22c55e]' :
                    isFailed ? 'bg-red-500' :
                    isRunning ? 'progress-racing' :
                    'bg-[#3f3f46] w-[15%]'
                  }`}
                  style={{
                    width: isCompleted ? '100%' :
                      isFailed ? '100%' :
                        isRunning ? '65%' :
                          '15%',
                    backgroundColor: isCompleted || isFailed || isRunning ? undefined : lane.color,
                  }}
                />
                {isCompleted && (
                  <div className="absolute inset-0 bg-[#22c55e]/20 blur-sm" />
                )}
              </div>

              <div className="w-24 flex items-center justify-end gap-2 text-sm font-mono">
                {isCompleted && (
                  <span className="text-[#22c55e] flex items-center gap-1.5">
                    <Check className="w-4 h-4" />
                    {status.jobs}
                  </span>
                )}
                {isFailed && (
                  <span className="text-red-400 flex items-center gap-1.5">
                    <X className="w-4 h-4" />
                    failed
                  </span>
                )}
                {isRunning && (
                  <span className="text-[#3b82f6] flex items-center gap-1.5 pulse-active">
                    <Loader2 className="w-4 h-4 animate-spin" />
                  </span>
                )}
                {isQueued && (
                  <span className="text-[#52525b]">queued</span>
                )}
              </div>

              <span className="w-14 text-right text-xs text-[#52525b] font-mono">
                {status.elapsed ? `${status.elapsed}s` : '—'}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
