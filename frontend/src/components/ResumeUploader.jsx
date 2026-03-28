import { useState } from 'react'
import { Upload, FileText, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'

export default function ResumeUploader({ onResumeParsed }) {
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [uploadSuccess, setUploadSuccess] = useState(false)

  const handleDragEnter = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const validateFile = (file) => {
    // Check file type
    if (file.type !== 'application/pdf') {
      return `Invalid file type. Expected PDF, got ${file.type}`
    }

    // Check file size (10MB max)
    const maxSize = 10 * 1024 * 1024 // 10MB in bytes
    if (file.size > maxSize) {
      const sizeMB = (file.size / (1024 * 1024)).toFixed(2)
      return `File too large. Maximum size is 10MB, got ${sizeMB}MB`
    }

    return null
  }

  const uploadResume = async (file) => {
    // Validate file
    const validationError = validateFile(file)
    if (validationError) {
      setUploadError(validationError)
      return
    }

    setUploading(true)
    setUploadError(null)
    setUploadSuccess(false)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/resume/parse', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || `Upload failed: ${response.status}`)
      }

      const parsedData = await response.json()
      setUploadSuccess(true)
      if (parsedData?.profile) {
        onResumeParsed(parsedData)
      } else {
        onResumeParsed({ profile: parsedData, resume: null })
      }

      // Clear success message after 3 seconds
      setTimeout(() => setUploadSuccess(false), 3000)
    } catch (err) {
      setUploadError(err.message)
    } finally {
      setUploading(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) {
      uploadResume(files[0])
    }
  }

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files)
    if (files.length > 0) {
      uploadResume(files[0])
    }
  }

  return (
    <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6 card-hover">
      <div className="flex items-center gap-2 mb-5">
        <div className="w-2 h-2 rounded-full bg-[#22c55e]" />
        <h2 className="text-lg font-semibold font-mono">Quick Setup</h2>
      </div>

      <div
        className={`
          border-2 border-dashed rounded-lg p-8 text-center transition-colors
          ${isDragging
            ? 'border-[#22c55e]/50 bg-[#22c55e]/5'
            : 'border-[#27272a] hover:border-[#22c55e]/50'
          }
          ${uploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => !uploading && document.getElementById('resume-input').click()}
      >
        <input
          id="resume-input"
          type="file"
          accept="application/pdf"
          onChange={handleFileSelect}
          className="hidden"
          disabled={uploading}
        />

        <div className="flex flex-col items-center gap-3">
          {uploading ? (
            <>
              <Loader2 className="w-10 h-10 text-[#22c55e] animate-spin" />
              <p className="text-white font-medium">Parsing your resume...</p>
              <p className="text-[#71717a] text-sm">This may take a few seconds</p>
            </>
          ) : uploadSuccess ? (
            <>
              <CheckCircle className="w-10 h-10 text-[#22c55e]" />
              <p className="text-[#22c55e] font-medium">Resume parsed successfully!</p>
              <p className="text-[#71717a] text-sm">Review and edit your profile below</p>
            </>
          ) : (
            <>
              <div className="p-3 bg-[#09090b] rounded-full">
                <Upload className="w-6 h-6 text-[#22c55e]" />
              </div>
              <div>
                <p className="text-white font-medium mb-1">
                  Drop your resume here or click to browse
                </p>
                <p className="text-[#71717a] text-sm">
                  PDF only, max 10MB
                </p>
              </div>
              <div className="flex items-center gap-2 text-xs text-[#52525b]">
                <FileText className="w-3 h-3" />
                <span>Auto-fill profile from your resume with AI</span>
              </div>
            </>
          )}
        </div>
      </div>

      {uploadError && (
        <div className="mt-4 bg-red-900/20 border border-red-500/50 rounded-lg p-3 text-red-400 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span className="text-sm">{uploadError}</span>
        </div>
      )}
    </div>
  )
}
