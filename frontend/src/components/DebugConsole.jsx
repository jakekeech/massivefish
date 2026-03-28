export default function DebugConsole({ entries, phase }) {
  return (
    <section className="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#1f2937]">
        <div>
          <h3 className="text-sm font-mono uppercase tracking-[0.2em] text-[#93c5fd]">
            Workflow Console
          </h3>
          <p className="text-xs text-[#6b7280] mt-1">
            Live client-side trace of the InternShip voyage
          </p>
        </div>
        <span className="px-2 py-1 rounded-full bg-[#1e3a8a]/40 text-[#93c5fd] text-xs font-mono uppercase">
          {phase}
        </span>
      </div>

      <div className="max-h-72 overflow-y-auto">
        {entries.length === 0 ? (
          <div className="px-4 py-6 text-sm text-[#6b7280] font-mono">
            Waiting for TinyFish signals...
          </div>
        ) : (
          entries.map((entry, index) => (
            <div
              key={`${entry.time}-${index}`}
              className="px-4 py-3 border-b border-[#1f2937]/80 font-mono text-xs"
            >
              <div className="flex items-center gap-3">
                <span className="text-[#60a5fa] shrink-0">{entry.time}</span>
                <span className="text-white">{entry.label}</span>
              </div>
              {entry.details && (
                <pre className="mt-2 text-[#9ca3af] whitespace-pre-wrap break-words">
                  {JSON.stringify(entry.details, null, 2)}
                </pre>
              )}
            </div>
          ))
        )}
      </div>
    </section>
  )
}
