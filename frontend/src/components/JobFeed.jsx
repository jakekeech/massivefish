import { Loader2, SearchX } from 'lucide-react'
import JobCard from './JobCard'

export default function JobFeed({ jobs, loading }) {
  if (loading) {
    return (
      <div className="text-center py-16">
        <div className="inline-flex items-center gap-3 px-6 py-3 bg-[#18181b] border border-[#27272a] rounded-full">
          <Loader2 className="w-5 h-5 text-[#22c55e] animate-spin" />
          <span className="text-[#a1a1aa] font-mono">
            Scoring jobs with AI...
          </span>
        </div>
      </div>
    )
  }

  if (!jobs || jobs.length === 0) {
    return (
      <div className="text-center py-16">
        <SearchX className="w-12 h-12 text-[#3f3f46] mx-auto mb-4" />
        <p className="text-[#71717a] font-mono">
          No jobs found yet. The swarm is still hunting...
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-mono text-[#71717a] uppercase tracking-wider">
          Results ({jobs.length})
        </h3>
        <span className="text-xs text-[#52525b] font-mono">
          Sorted by relevance
        </span>
      </div>
      {jobs.map((job, index) => (
        <JobCard key={job.id} job={job} index={index} />
      ))}
    </div>
  )
}
