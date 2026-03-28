import { useState } from 'react'
import { Terminal, CheckCircle } from 'lucide-react'
import HuntButton from './HuntButton'
import ProfileForm from './ProfileForm'
import ResumeUploader from './ResumeUploader'
import SearchConfig from './SearchConfig'
import { DEFAULT_TARGETS_LABEL } from '../lib/defaultTargets'

export default function ProfileSetup({
  profile,
  setProfile,
  resume,
  setResume,
  searchConfig,
  setSearchConfig,
  onStartHunt,
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [resumeSuccess, setResumeSuccess] = useState(false)

  const canHunt = searchConfig.role.trim() && searchConfig.location.trim()

  const handleResumeParsed = ({ profile: parsedProfile, resume: parsedResume }) => {
    setProfile((currentProfile) => ({
      ...currentProfile,
      ...parsedProfile,
      first_name: parsedProfile.first_name || currentProfile.first_name,
      last_name: parsedProfile.last_name || currentProfile.last_name,
      email: parsedProfile.email || currentProfile.email,
      phone: parsedProfile.phone || currentProfile.phone,
      location: parsedProfile.location || currentProfile.location,
      linkedin_url: parsedProfile.linkedin_url || currentProfile.linkedin_url,
      github_url: parsedProfile.github_url || currentProfile.github_url,
      current_title: parsedProfile.current_title || currentProfile.current_title,
      years_of_experience: parsedProfile.years_of_experience || currentProfile.years_of_experience,
      education: parsedProfile.education || currentProfile.education,
      skills: parsedProfile.skills?.length ? parsedProfile.skills : currentProfile.skills,
    }))
    setResume(parsedResume || null)
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
          <span>TinyFish Hatchery</span>
        </div>
        <h1 className="text-4xl md:text-5xl font-bold font-display tracking-tight mb-3">
          Set Sail with <span className="text-gradient">InternShip</span>
        </h1>
        <p className="text-[#a1a1aa] text-lg max-w-xl mx-auto">
          Release a school of TinyFish to scout internships and early-career roles tailored to your profile
          <span className="text-white font-medium"> end to end</span>
        </p>
      </div>

      <div className="space-y-6">
        <ResumeUploader onResumeParsed={handleResumeParsed} />

        {resumeSuccess && (
          <div className="bg-[#22c55e]/10 border border-[#22c55e]/50 rounded-xl p-4 text-[#22c55e] flex items-center gap-3">
            <CheckCircle className="w-5 h-5 flex-shrink-0" />
            <span>
              {resume?.filename
                ? `Resume parsed and stored: ${resume.filename}. Review your profile below.`
                : 'Resume parsed successfully! Review your profile below.'}
            </span>
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
          {searchConfig.target_urls.length > 0
            ? `${searchConfig.target_urls.length} Target${searchConfig.target_urls.length === 1 ? '' : 's'} Configured`
            : `Default Swarm: ${DEFAULT_TARGETS_LABEL}`}
        </div>
      </div>
    </div>
  )
}
