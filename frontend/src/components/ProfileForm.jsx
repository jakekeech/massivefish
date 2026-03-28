import { User, Mail, Briefcase, GraduationCap, Phone, MapPin, Linkedin, Github, Clock, Tag, X } from 'lucide-react'
import { useState } from 'react'

export default function ProfileForm({ profile, setProfile }) {
  const [skillInput, setSkillInput] = useState('')

  const handleChange = (field) => (e) => {
    setProfile({ ...profile, [field]: e.target.value })
  }

  const handleAddSkill = () => {
    if (skillInput.trim() && !profile.skills.includes(skillInput.trim())) {
      setProfile({ ...profile, skills: [...profile.skills, skillInput.trim()] })
      setSkillInput('')
    }
  }

  const handleRemoveSkill = (skillToRemove) => {
    setProfile({
      ...profile,
      skills: profile.skills.filter(skill => skill !== skillToRemove)
    })
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAddSkill()
    }
  }

  const InputIcon = ({ icon: Icon }) => (
    <div className="absolute left-3 top-1/2 -translate-y-1/2 text-[#71717a]">
      <Icon className="w-4 h-4" />
    </div>
  )

  return (
    <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6 card-hover">
      <div className="flex items-center gap-2 mb-5">
        <div className="w-2 h-2 rounded-full bg-[#22c55e]" />
        <h2 className="text-lg font-semibold font-mono">Your Profile</h2>
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="relative">
            <InputIcon icon={User} />
            <input
              type="text"
              value={profile.first_name}
              onChange={handleChange('first_name')}
              className="w-full bg-[#09090b] border border-[#27272a] rounded-lg pl-10 pr-3 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
              placeholder="First Name"
            />
          </div>
          <div>
            <input
              type="text"
              value={profile.last_name}
              onChange={handleChange('last_name')}
              className="w-full bg-[#09090b] border border-[#27272a] rounded-lg px-3 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
              placeholder="Last Name"
            />
          </div>
        </div>

        <div className="relative">
          <InputIcon icon={Mail} />
          <input
            type="email"
            value={profile.email}
            onChange={handleChange('email')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded-lg pl-10 pr-3 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
            placeholder="Email address"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="relative">
            <InputIcon icon={Phone} />
            <input
              type="tel"
              value={profile.phone}
              onChange={handleChange('phone')}
              className="w-full bg-[#09090b] border border-[#27272a] rounded-lg pl-10 pr-3 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
              placeholder="Phone"
            />
          </div>
          <div className="relative">
            <InputIcon icon={MapPin} />
            <input
              type="text"
              value={profile.location}
              onChange={handleChange('location')}
              className="w-full bg-[#09090b] border border-[#27272a] rounded-lg pl-10 pr-3 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
              placeholder="Location"
            />
          </div>
        </div>

        <div className="relative">
          <InputIcon icon={Linkedin} />
          <input
            type="url"
            value={profile.linkedin_url}
            onChange={handleChange('linkedin_url')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded-lg pl-10 pr-3 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
            placeholder="LinkedIn URL"
          />
        </div>

        <div className="relative">
          <InputIcon icon={Github} />
          <input
            type="url"
            value={profile.github_url}
            onChange={handleChange('github_url')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded-lg pl-10 pr-3 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
            placeholder="GitHub URL"
          />
        </div>

        <div className="relative">
          <InputIcon icon={Briefcase} />
          <input
            type="text"
            value={profile.current_title}
            onChange={handleChange('current_title')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded-lg pl-10 pr-3 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
            placeholder="Current Title (e.g. Software Engineer)"
          />
        </div>

        <div className="relative">
          <InputIcon icon={Clock} />
          <input
            type="text"
            value={profile.years_of_experience}
            onChange={handleChange('years_of_experience')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded-lg pl-10 pr-3 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
            placeholder="Years of Experience (e.g. 5)"
          />
        </div>

        <div className="relative">
          <InputIcon icon={GraduationCap} />
          <input
            type="text"
            value={profile.education}
            onChange={handleChange('education')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded-lg pl-10 pr-3 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
            placeholder="Education (e.g. BS CS, Stanford)"
          />
        </div>

        <div>
          <div className="relative">
            <InputIcon icon={Tag} />
            <input
              type="text"
              value={skillInput}
              onChange={(e) => setSkillInput(e.target.value)}
              onKeyPress={handleKeyPress}
              className="w-full bg-[#09090b] border border-[#27272a] rounded-lg pl-10 pr-20 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
              placeholder="Add a skill (e.g. React, Python)"
            />
            <button
              type="button"
              onClick={handleAddSkill}
              className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1 bg-[#22c55e] text-black text-sm font-medium rounded hover:bg-[#22c55e]/90 transition-colors"
            >
              Add
            </button>
          </div>
          {profile.skills.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {profile.skills.map((skill) => (
                <div
                  key={skill}
                  className="inline-flex items-center gap-1.5 px-3 py-1 bg-[#27272a] rounded-full text-sm text-white"
                >
                  <span>{skill}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveSkill(skill)}
                    className="hover:text-red-400 transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
