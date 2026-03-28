import { Database, Filter, TrendingUp } from 'lucide-react'

export default function StatsRow({ totalScraped, totalAfterDedup, avgScore }) {
  const stats = [
    {
      label: 'Total Scraped',
      value: totalScraped,
      icon: Database,
      color: '#22c55e',
      bgColor: 'rgba(34, 197, 94, 0.1)',
    },
    {
      label: 'After Dedup',
      value: totalAfterDedup,
      icon: Filter,
      color: '#fafafa',
      bgColor: 'rgba(255, 255, 255, 0.05)',
    },
    {
      label: 'Avg Match',
      value: `${avgScore}%`,
      icon: TrendingUp,
      color: avgScore >= 70 ? '#22c55e' : avgScore >= 50 ? '#eab308' : '#71717a',
      bgColor: avgScore >= 70 ? 'rgba(34, 197, 94, 0.1)' : avgScore >= 50 ? 'rgba(234, 179, 8, 0.1)' : 'rgba(113, 113, 122, 0.1)',
    },
  ]

  return (
    <div className="grid grid-cols-3 gap-4">
      {stats.map((stat, i) => (
        <div
          key={stat.label}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-5 text-center relative overflow-hidden group card-hover"
        >
          {/* Background Icon */}
          <stat.icon
            className="absolute -right-4 -bottom-4 w-20 h-20 text-white/[0.02] group-hover:text-white/[0.04] transition-colors"
          />

          {/* Content */}
          <div
            className="text-3xl font-bold font-mono mb-1"
            style={{ color: stat.color }}
          >
            {stat.value}
          </div>
          <div className="text-sm text-[#71717a] font-mono uppercase tracking-wider">
            {stat.label}
          </div>

          {/* Accent dot */}
          <div
            className="absolute top-4 left-4 w-2 h-2 rounded-full"
            style={{ backgroundColor: stat.color }}
          />
        </div>
      ))}
    </div>
  )
}
