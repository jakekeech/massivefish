import { useState } from 'react'
import { Globe, MapPin, Plus, Search, Tag, X } from 'lucide-react'

export default function SearchConfig({ config, setConfig }) {
  const [keywordInput, setKeywordInput] = useState('')
  const [urlInput, setUrlInput] = useState('')

  const handleChange = (field) => (event) => {
    setConfig({ ...config, [field]: event.target.value })
  }

  const addKeyword = () => {
    const value = keywordInput.trim()
    if (value && !config.keywords.includes(value)) {
      setConfig({ ...config, keywords: [...config.keywords, value] })
      setKeywordInput('')
    }
  }

  const removeKeyword = (keyword) => {
    setConfig({ ...config, keywords: config.keywords.filter((item) => item !== keyword) })
  }

  const addUrl = () => {
    const value = urlInput.trim()
    if (value && !config.target_urls.includes(value)) {
      setConfig({ ...config, target_urls: [...config.target_urls, value] })
      setUrlInput('')
    }
  }

  const removeUrl = (url) => {
    setConfig({ ...config, target_urls: config.target_urls.filter((item) => item !== url) })
  }

  const handleKeyDown = (event, onAdd) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      onAdd()
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
              onChange={(event) => setKeywordInput(event.target.value)}
              onKeyDown={(event) => handleKeyDown(event, addKeyword)}
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
              {config.keywords.map((keyword) => (
                <span
                  key={keyword}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-[#22c55e]/10 border border-[#22c55e]/20 rounded-full text-sm text-[#22c55e]"
                >
                  {keyword}
                  <button
                    onClick={() => removeKeyword(keyword)}
                    className="hover:text-red-400 transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="relative">
            <InputIcon icon={Globe} />
            <input
              type="text"
              value={urlInput}
              onChange={(event) => setUrlInput(event.target.value)}
              onKeyDown={(event) => handleKeyDown(event, addUrl)}
              className="w-full bg-[#09090b] border border-[#27272a] rounded-lg pl-10 pr-20 py-2.5 text-white placeholder:text-[#52525b] transition-colors"
              placeholder="Optional target URL"
            />
            <button
              onClick={addUrl}
              disabled={!urlInput.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1 bg-[#27272a] hover:bg-[#3f3f46] disabled:opacity-50 disabled:cursor-not-allowed rounded text-sm flex items-center gap-1 transition-colors"
            >
              <Plus className="w-3 h-3" />
              Add
            </button>
          </div>

          {config.target_urls.length === 0 && (
            <p className="text-xs text-[#71717a] mt-2">
              No URLs added. InternShip will use the default target source.
            </p>
          )}

          {config.target_urls.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {config.target_urls.map((url) => (
                <span
                  key={url}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-[#3b82f6]/10 border border-[#3b82f6]/20 rounded-full text-sm text-[#93c5fd]"
                >
                  {url}
                  <button
                    onClick={() => removeUrl(url)}
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
