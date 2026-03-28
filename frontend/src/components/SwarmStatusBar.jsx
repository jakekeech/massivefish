import { Check, X, Loader2, Radio } from 'lucide-react'

const PLATFORMS = [
  { id: 'linkedin', name: 'LinkedIn', color: '#0a66c2' },
  { id: 'indeed', name: 'Indeed', color: '#2164f3' },
  { id: 'wellfound', name: 'Wellfound', color: '#000000' },
  { id: 'yc_waas', name: 'YC Startups', color: '#f26522' },
  { id: 'greenhouse', name: 'Greenhouse', color: '#3ab549' },
  { id: 'lever', name: 'Lever', color: '#1da1b4' },
]

export default function SwarmStatusBar({ statuses, totalJobs }) {
  const completedCount = Object.values(statuses).filter(s => s.status === 'completed').length
  const failedCount = Object.values(statuses).filter(s => s.status === 'failed').length
  const runningCount = Object.values(statuses).filter(s => s.status === 'running').length

  return (
    <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Radio className="w-5 h-5 text-[#22c55e]" />
            {runningCount > 0 && (
              <span className="absolute -top-1 -right-1 w-2 h-2 bg-[#22c55e] rounded-full animate-ping" />
            )}
          </div>
          <h2 className="text-lg font-bold font-mono">
            SWARM <span className="text-[#22c55e]">DEPLOYED</span>
          </h2>
        </div>
        <div className="flex items-center gap-4 text-sm font-mono">
          <span className="text-[#a1a1aa]">
            <span className="text-white font-bold">{totalJobs}</span> jobs found
          </span>
          <span className="text-[#22c55e]">{completedCount}/6</span>
        </div>
      </div>

      {/* Agent Lanes */}
      <div className="space-y-3">
        {PLATFORMS.map((platform, index) => {
          const status = statuses[platform.id] || { status: 'queued', jobs: 0 }
          const isCompleted = status.status === 'completed'
          const isFailed = status.status === 'failed'
          const isRunning = status.status === 'running'
          const isQueued = status.status === 'queued'

          return (
            <div
              key={platform.id}
              className="flex items-center gap-4"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              {/* Platform Name */}
              <span className="w-28 text-sm text-[#a1a1aa] font-mono truncate">
                {platform.name}
              </span>

              {/* Progress Bar */}
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
                           '15%'
                  }}
                />
                {/* Glow effect for completed */}
                {isCompleted && (
                  <div className="absolute inset-0 bg-[#22c55e]/20 blur-sm" />
                )}
              </div>

              {/* Status */}
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

              {/* Time */}
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
