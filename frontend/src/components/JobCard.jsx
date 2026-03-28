import { ExternalLink, MapPin, Clock, DollarSign, Briefcase, Sparkles } from 'lucide-react'

function getScoreColor(score) {
  if (score >= 90) return { text: 'text-[#22c55e]', bg: 'bg-[#22c55e]/10', border: 'border-[#22c55e]/30' }
  if (score >= 70) return { text: 'text-[#eab308]', bg: 'bg-[#eab308]/10', border: 'border-[#eab308]/30' }
  return { text: 'text-[#71717a]', bg: 'bg-[#71717a]/10', border: 'border-[#71717a]/30' }
}

function getCustomPlatformLabel(jobUrl) {
  if (!jobUrl) return 'Custom'

  try {
    const { hostname } = new URL(jobUrl)
    return hostname.replace('www.', '') || 'Custom'
  } catch {
    return 'Custom'
  }
}

function getPlatformLabel(platform, jobUrl) {
  const labels = {
    linkedin: 'LinkedIn',
    indeed: 'Indeed',
    wellfound: 'Wellfound',
    yc_waas: 'YC',
    greenhouse: 'Greenhouse',
    lever: 'Lever',
  }
  if (platform === 'custom') {
    return getCustomPlatformLabel(jobUrl)
  }
  return labels[platform] || platform
}

function getPlatformColor(platform) {
  const colors = {
    linkedin: '#0a66c2',
    indeed: '#2164f3',
    wellfound: '#000000',
    yc_waas: '#f26522',
    greenhouse: '#3ab549',
    lever: '#1da1b4',
  }
  return colors[platform] || '#71717a'
}

export default function JobCard({ job, index }) {
  const scoreStyle = getScoreColor(job.relevance_score)

  return (
    <div
      className="bg-[#18181b] border border-[#27272a] rounded-xl p-5 card-hover group"
      style={{ animationDelay: `${index * 50}ms` }}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-lg text-white group-hover:text-[#22c55e] transition-colors truncate">
            {job.job_title}
          </h3>
          <div className="flex items-center gap-2 mt-1 text-sm text-[#a1a1aa] flex-wrap">
            <span className="font-medium text-white">{job.company_name}</span>
            {job.location && (
              <>
                <span className="text-[#3f3f46]">·</span>
                <span className="flex items-center gap-1">
                  <MapPin className="w-3 h-3" />
                  {job.location}
                </span>
              </>
            )}
            {job.posted_time && (
              <>
                <span className="text-[#3f3f46]">·</span>
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {job.posted_time}
                </span>
              </>
            )}
          </div>
        </div>

        {/* Score Badge */}
        <div className={`px-3 py-1.5 rounded-lg font-mono text-sm font-bold border ${scoreStyle.text} ${scoreStyle.bg} ${scoreStyle.border}`}>
          {job.relevance_score}%
        </div>
      </div>

      {/* Tags Row */}
      <div className="flex items-center gap-2 flex-wrap mb-3">
        <span
          className="text-xs px-2 py-0.5 rounded-full font-mono"
          style={{
            backgroundColor: `${getPlatformColor(job.source_platform)}15`,
            color: getPlatformColor(job.source_platform),
            border: `1px solid ${getPlatformColor(job.source_platform)}30`,
          }}
        >
          {getPlatformLabel(job.source_platform, job.job_url)}
        </span>
        {job.employment_type && (
          <span className="text-xs px-2 py-0.5 rounded bg-[#27272a] text-[#a1a1aa] flex items-center gap-1">
            <Briefcase className="w-3 h-3" />
            {job.employment_type}
          </span>
        )}
        {job.salary && (
          <span className="text-xs px-2 py-0.5 rounded bg-[#22c55e]/10 text-[#22c55e] flex items-center gap-1">
            <DollarSign className="w-3 h-3" />
            {job.salary}
          </span>
        )}
      </div>

      {/* Match Reasons */}
      {job.match_reasons && job.match_reasons.length > 0 && (
        <div className="flex items-start gap-2 mb-4 text-sm">
          <Sparkles className="w-4 h-4 text-[#22c55e] mt-0.5 flex-shrink-0" />
          <p className="text-[#a1a1aa]">
            {job.match_reasons.join(' · ')}
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3 pt-2 border-t border-[#27272a]">
        <button
          disabled
          className="flex-1 py-2.5 rounded-lg bg-[#27272a] text-[#52525b] cursor-not-allowed text-sm font-medium"
          title="Coming Soon"
        >
          Apply For Me (Soon)
        </button>
        <a
          href={job.job_url}
          target="_blank"
          rel="noopener noreferrer"
          className="px-5 py-2.5 rounded-lg bg-[#27272a] hover:bg-[#3f3f46] transition-colors flex items-center gap-2 text-sm font-medium"
        >
          View
          <ExternalLink className="w-4 h-4" />
        </a>
      </div>
    </div>
  )
}
