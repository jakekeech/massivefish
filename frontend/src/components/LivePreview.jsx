export default function LivePreview({ title, url, message }) {
  return (
    <section className="bg-[#18181b] border border-[#27272a] rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-[#27272a]">
        <h3 className="text-sm font-mono uppercase tracking-[0.2em] text-[#60a5fa]">
          {title}
        </h3>
        <p className="text-xs text-[#71717a] mt-1">
          Live view from the TinyFish school
        </p>
      </div>

      {!url ? (
        <div className="px-4 py-8 text-sm text-[#6b7280] font-mono">
          {message || 'Waiting for a TinyFish to surface a streaming URL...'}
        </div>
      ) : (
        <div className="aspect-video bg-[#09090b]">
          <iframe
            src={url}
            title={title}
            className="w-full h-full border-0"
            allow="clipboard-read; clipboard-write"
          />
        </div>
      )}
    </section>
  )
}
