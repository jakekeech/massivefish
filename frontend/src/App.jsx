import { useState } from 'react'
import Header from './components/Header'
import ProfileSetup from './components/ProfileSetup'
import HuntDashboard from './components/HuntDashboard'

export default function App() {
  const [step, setStep] = useState('setup') // 'setup' | 'hunting'
  const [huntId, setHuntId] = useState(null)
  const [profile, setProfile] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    location: '',
    linkedin_url: '',
    github_url: '',
    current_title: '',
    years_of_experience: '',
    education: '',
    skills: [],
  })
  const [searchConfig, setSearchConfig] = useState({
    role: '',
    location: '',
    keywords: [],
    target_urls: [],
  })

  const handleStartHunt = (newHuntId) => {
    setHuntId(newHuntId)
    setStep('hunting')
  }

  const handleReset = () => {
    setStep('setup')
    setHuntId(null)
  }

  return (
    <div className="min-h-screen bg-[#09090b] noise-overlay">
      <Header onReset={step === 'hunting' ? handleReset : null} />
      <main className="max-w-6xl mx-auto px-4 py-8">
        {step === 'setup' && (
          <ProfileSetup
            profile={profile}
            setProfile={setProfile}
            searchConfig={searchConfig}
            setSearchConfig={setSearchConfig}
            onStartHunt={handleStartHunt}
          />
        )}
        {step === 'hunting' && (
          <HuntDashboard
            huntId={huntId}
            searchConfig={searchConfig}
          />
        )}
      </main>
    </div>
  )
}
