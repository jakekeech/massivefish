import { Zap, Loader2 } from 'lucide-react'

export default function HuntButton({ onClick, disabled, loading }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`
        relative w-full py-4 rounded-xl font-bold text-lg font-mono
        flex items-center justify-center gap-3
        transition-all duration-300 overflow-hidden
        ${disabled || loading
          ? 'bg-[#27272a] text-[#71717a] cursor-not-allowed'
          : 'bg-[#22c55e] text-black hover:bg-[#16a34a] glow-green'
        }
      `}
    >
      {/* Animated background gradient when active */}
      {!disabled && !loading && (
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full animate-[scan_2s_ease-in-out_infinite]" />
      )}

      {loading ? (
        <>
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Deploying Swarm...</span>
        </>
      ) : (
        <>
          <Zap className="w-5 h-5" />
          <span>Hunt Jobs</span>
          <span className="text-black/50 text-sm font-normal ml-1">
            (6 platforms)
          </span>
        </>
      )}
    </button>
  )
}
