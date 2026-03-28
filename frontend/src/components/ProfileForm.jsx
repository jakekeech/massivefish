import { User, Mail, Briefcase, GraduationCap, MapPin, Phone } from 'lucide-react'

export default function ProfileForm({ profile, setProfile }) {
  const handleChange = (field) => (e) => {
    setProfile({ ...profile, [field]: e.target.value })
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
              placeholder="Your Location"
            />
          </div>
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
          <InputIcon icon={GraduationCap} />
          <input
            type="text"
            value={profile.education}
            onChange={handleChange('education')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded-lg pl-10 pr-3 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
            placeholder="Education (e.g. BS CS, Stanford)"
          />
        </div>
      </div>
    </div>
  )
}
