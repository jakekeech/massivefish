import { Zap, RotateCcw } from 'lucide-react'

export default function Header({ onReset }) {
  return (
    <header className="border-b border-[#27272a] bg-[#18181b]/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Zap className="w-7 h-7 text-[#22c55e]" />
            <div className="absolute inset-0 blur-md bg-[#22c55e]/30 -z-10" />
          </div>
          <div>
            <h1 className="text-xl font-bold font-display tracking-tight">
              Intern<span className="text-[#22c55e]">Ship</span>
            </h1>
            <p className="text-[10px] text-[#71717a] font-mono uppercase tracking-widest">
              TinyFish-Guided Career Search
            </p>
          </div>
        </div>
        {onReset && (
          <button
            onClick={onReset}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-[#a1a1aa] hover:text-white hover:bg-[#27272a] rounded transition-all"
          >
            <RotateCcw className="w-4 h-4" />
            New Voyage
          </button>
        )}
      </div>
    </header>
  )
}
