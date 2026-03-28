import { useState } from 'react'
import { Terminal, CheckCircle } from 'lucide-react'
import HuntButton from './HuntButton'
import ProfileForm from './ProfileForm'
import ResumeUploader from './ResumeUploader'
import SearchConfig from './SearchConfig'

export default function ProfileSetup({
  profile,
  setProfile,
  searchConfig,
  setSearchConfig,
  onStartHunt,
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [resumeSuccess, setResumeSuccess] = useState(false)

  const canHunt = searchConfig.role.trim() && searchConfig.location.trim()

  const handleResumeParsed = (parsedData) => {
    setProfile(parsedData)
    setResumeSuccess(true)
    // Clear success message after 3 seconds
    setTimeout(() => setResumeSuccess(false), 3000)
  }

  const handleHunt = async () => {
    if (!canHunt) return

    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      })

      if (!response.ok) {
        const responseText = await response.text()
        throw new Error(`Profile save failed: ${response.status} ${responseText}`)
      }

      onStartHunt('pending')
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 bg-[#22c55e]/10 border border-[#22c55e]/20 rounded-full text-sm text-[#22c55e] font-mono mb-4">
          <Terminal className="w-4 h-4" />
          <span>TinyFish Powered</span>
        </div>
        <h1 className="text-4xl md:text-5xl font-bold mb-3">
          Deploy Your <span className="text-gradient">Job Hunt Swarm</span>
        </h1>
        <p className="text-[#a1a1aa] text-lg max-w-xl mx-auto">
          LinkedIn-only debug mode is enabled so we can verify the full TinyFish workflow
          <span className="text-white font-medium"> end to end</span>
        </p>
      </div>

      <div className="space-y-6">
        <ResumeUploader onProfileParsed={handleResumeParsed} />

        {resumeSuccess && (
          <div className="bg-[#22c55e]/10 border border-[#22c55e]/50 rounded-xl p-4 text-[#22c55e] flex items-center gap-3">
            <CheckCircle className="w-5 h-5 flex-shrink-0" />
            <span>Resume parsed successfully! Review your profile below.</span>
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-6">
          <ProfileForm profile={profile} setProfile={setProfile} />
          <SearchConfig config={searchConfig} setConfig={setSearchConfig} />
        </div>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-500/50 rounded-xl p-4 text-red-400 flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-red-500" />
          {error}
        </div>
      )}

      <HuntButton onClick={handleHunt} disabled={!canHunt} loading={loading} />

      <div className="flex justify-center gap-6 pt-4">
        <div className="text-xs text-[#22c55e] font-mono uppercase tracking-wider">
          LinkedIn
        </div>
      </div>
    </div>
  )
}
