import { useState } from 'react'
import { Search, MapPin, Tag, X, Plus } from 'lucide-react'

export default function SearchConfig({ config, setConfig }) {
  const [keywordInput, setKeywordInput] = useState('')

  const handleChange = (field) => (e) => {
    setConfig({ ...config, [field]: e.target.value })
  }

  const addKeyword = () => {
    if (keywordInput.trim() && !config.keywords.includes(keywordInput.trim())) {
      setConfig({ ...config, keywords: [...config.keywords, keywordInput.trim()] })
      setKeywordInput('')
    }
  }

  const removeKeyword = (keyword) => {
    setConfig({ ...config, keywords: config.keywords.filter(k => k !== keyword) })
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addKeyword()
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
        <div className="w-2 h-2 rounded-full bg-[#3b82f6]" />
        <h2 className="text-lg font-semibold font-mono">Job Search</h2>
      </div>

      <div className="space-y-4">
        <div className="relative">
          <InputIcon icon={Search} />
          <input
            type="text"
            value={config.role}
            onChange={handleChange('role')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded-lg pl-10 pr-3 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
            placeholder="Role / Title *"
          />
          {config.role && (
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-[#22c55e] font-mono">
              Required
            </span>
          )}
        </div>

        <div className="relative">
          <InputIcon icon={MapPin} />
          <input
            type="text"
            value={config.location}
            onChange={handleChange('location')}
            className="w-full bg-[#09090b] border border-[#27272a] rounded-lg pl-10 pr-3 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
            placeholder="Location *"
          />
        </div>

        <div>
          <div className="relative">
            <InputIcon icon={Tag} />
            <input
              type="text"
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full bg-[#09090b] border border-[#27272a] rounded-lg pl-10 pr-20 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
              placeholder="Add keywords (Python, AI, React...)"
            />
            <button
              onClick={addKeyword}
              disabled={!keywordInput.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1 bg-[#27272a] hover:bg-[#3f3f46] disabled:opacity-50 disabled:cursor-not-allowed rounded text-sm flex items-center gap-1 transition-colors"
            >
              <Plus className="w-3 h-3" />
              Add
            </button>
          </div>

          {config.keywords.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {config.keywords.map(kw => (
                <span
                  key={kw}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-[#22c55e]/10 border border-[#22c55e]/20 rounded-full text-sm text-[#22c55e]"
                >
                  {kw}
                  <button
                    onClick={() => removeKeyword(kw)}
                    className="hover:text-red-400 transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
