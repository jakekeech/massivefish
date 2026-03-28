export function parseEventBlock(block) {
  const lines = block.split('\n')
  let eventName = 'message'
  const dataLines = []

  for (const line of lines) {
    if (!line.trim()) continue
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim()
      continue
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim())
    }
  }

  if (dataLines.length === 0) {
    return null
  }

  try {
    const rawData = dataLines.join('\n')
    return {
      eventName,
      data: JSON.parse(rawData),
    }
  } catch {
    return null
  }
}

export function consumeEventBlocks(buffer, onEventBlock) {
  let workingBuffer = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  let separatorIndex = workingBuffer.indexOf('\n\n')

  while (separatorIndex !== -1) {
    const block = workingBuffer.slice(0, separatorIndex)
    workingBuffer = workingBuffer.slice(separatorIndex + 2)

    if (block.trim()) {
      const parsed = parseEventBlock(block)
      if (parsed) {
        onEventBlock(parsed)
      }
    }

    separatorIndex = workingBuffer.indexOf('\n\n')
  }

  return workingBuffer
}
