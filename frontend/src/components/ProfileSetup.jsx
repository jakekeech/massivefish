import { useState } from 'react'
import { Terminal } from 'lucide-react'
import ProfileForm from './ProfileForm'
import SearchConfig from './SearchConfig'
import HuntButton from './HuntButton'

export default function ProfileSetup({
  profile,
  setProfile,
  searchConfig,
  setSearchConfig,
  onStartHunt,
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const canHunt = searchConfig.role.trim() && searchConfig.location.trim()

  const handleHunt = async () => {
    if (!canHunt) return

    setLoading(true)
    setError(null)

    try {
      // Save profile first
      await fetch('/api/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      })

      // Start hunt - pass 'pending' to trigger SSE in HuntDashboard
      onStartHunt('pending')
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 bg-[#22c55e]/10 border border-[#22c55e]/20 rounded-full text-sm text-[#22c55e] font-mono mb-4">
          <Terminal className="w-4 h-4" />
          <span>TinyFish Powered</span>
        </div>
        <h1 className="text-4xl md:text-5xl font-bold mb-3">
          Deploy Your <span className="text-gradient">Job Hunt Swarm</span>
        </h1>
        <p className="text-[#a1a1aa] text-lg max-w-xl mx-auto">
          6 AI agents scrape LinkedIn, Indeed, Wellfound, YC, Greenhouse & Lever
          <span className="text-white font-medium"> in parallel</span>
        </p>
      </div>

      {/* Forms Grid */}
      <div className="grid md:grid-cols-2 gap-6">
        <ProfileForm profile={profile} setProfile={setProfile} />
        <SearchConfig config={searchConfig} setConfig={setSearchConfig} />
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-900/20 border border-red-500/50 rounded-xl p-4 text-red-400 flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-red-500" />
          {error}
        </div>
      )}

      {/* Hunt Button */}
      <HuntButton onClick={handleHunt} disabled={!canHunt} loading={loading} />

      {/* Platform Icons */}
      <div className="flex justify-center gap-6 pt-4">
        {['LinkedIn', 'Indeed', 'Wellfound', 'YC', 'Greenhouse', 'Lever'].map((name, i) => (
          <div
            key={name}
            className="text-xs text-[#52525b] font-mono uppercase tracking-wider"
            style={{ animationDelay: `${i * 100}ms` }}
          >
            {name}
          </div>
        ))}
      </div>
    </div>
  )
}
