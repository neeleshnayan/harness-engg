type Heading = {
  depth: 2 | 3
  text: string
  id: string
}

function slugify(input: string): string {
  return input
    .toLowerCase()
    .trim()
    .replace(/[`"'()[\]{}]/g, '')
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
}

export function extractHeadings(markdown: string): Heading[] {
  const lines = markdown.split(/\r?\n/)
  const out: Heading[] = []
  const seen = new Map<string, number>()

  for (const line of lines) {
    const trimmed = line.trim()
    const h2 = trimmed.match(/^##\s+(.+)$/)
    const h3 = trimmed.match(/^###\s+(.+)$/)
    const match = h2 ?? h3
    if (!match) continue

    const text = match[1].trim()
    const base = slugify(text)
    const n = (seen.get(base) ?? 0) + 1
    seen.set(base, n)
    const id = n === 1 ? base : `${base}-${n}`
    out.push({ depth: (h2 ? 2 : 3) as 2 | 3, text, id })
  }

  return out
}

export function markdownToHtml(markdown: string): string {
  if (!markdown) return ''

  const escapeHtml = (text: string) =>
    text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')

  const applyInline = (text: string) => {
    const escaped = escapeHtml(text)
    // links: [text](url)
    const withLinks = escaped.replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noreferrer" class="text-blue-600 hover:text-blue-800 hover:underline">$1</a>',
    )
    return withLinks
      .replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 rounded bg-gray-100 font-mono text-[0.9em] text-gray-800">$1</code>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/__(.+?)__/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/_(.+?)_/g, '<em>$1</em>')
  }

  const lines = markdown.split(/\r?\n/)
  const html: string[] = []
  const headingSeen = new Map<string, number>()

  let inList = false
  let inCodeFence = false
  let codeFenceLang = ''
  let codeLines: string[] = []

  const closeList = () => {
    if (inList) {
      html.push('</ul>')
      inList = false
    }
  }

  const closeCodeFence = () => {
    if (!inCodeFence) return
    const code = escapeHtml(codeLines.join('\n'))
    html.push(
      `<pre class="rounded-xl bg-gray-50 border border-gray-200 p-4 overflow-x-auto"><code class="font-mono text-xs text-gray-800" data-lang="${escapeHtml(codeFenceLang)}">${code}</code></pre>`,
    )
    inCodeFence = false
    codeFenceLang = ''
    codeLines = []
  }

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i]
    const trimmed = raw.trim()

    const fenceMatch = trimmed.match(/^```(\w+)?\s*$/)
    if (fenceMatch) {
      if (inCodeFence) {
        closeCodeFence()
      } else {
        closeList()
        inCodeFence = true
        codeFenceLang = fenceMatch[1] ?? ''
        codeLines = []
      }
      continue
    }

    if (inCodeFence) {
      codeLines.push(raw)
      continue
    }

    if (!trimmed) {
      closeList()
      html.push('<div class="h-3" aria-hidden="true"></div>')
      continue
    }

    // H1
    const h1 = trimmed.match(/^#\s+(.+)$/)
    if (h1) {
      closeList()
      html.push(`<h1 class="text-3xl font-semibold text-gray-900 tracking-tight mt-2 mb-3">${applyInline(h1[1])}</h1>`)
      continue
    }

    // H2/H3 (with ids)
    const h2 = trimmed.match(/^##\s+(.+)$/)
    const h3 = trimmed.match(/^###\s+(.+)$/)
    if (h2) {
      closeList()
      const text = h2[1].trim()
      const base = slugify(text)
      const n = (headingSeen.get(base) ?? 0) + 1
      headingSeen.set(base, n)
      const id = n === 1 ? base : `${base}-${n}`
      html.push(
        `<h2 id="${id}" class="scroll-mt-24 text-xl font-semibold text-gray-900 mt-10 mb-3">${applyInline(text)}</h2>`,
      )
      continue
    }
    if (h3) {
      closeList()
      const text = h3[1].trim()
      const base = slugify(text)
      const n = (headingSeen.get(base) ?? 0) + 1
      headingSeen.set(base, n)
      const id = n === 1 ? base : `${base}-${n}`
      html.push(
        `<h3 id="${id}" class="scroll-mt-24 text-base font-semibold text-gray-900 mt-6 mb-2">${applyInline(text)}</h3>`,
      )
      continue
    }

    // list items
    const li = trimmed.match(/^-\s+(.+)$/)
    if (li) {
      if (!inList) {
        html.push('<ul class="list-disc pl-6 space-y-1 text-gray-700 text-sm">')
        inList = true
      }
      html.push(`<li>${applyInline(li[1])}</li>`)
      continue
    }

    // blockquote
    const bq = trimmed.match(/^>\s?(.+)$/)
    if (bq) {
      closeList()
      html.push(
        `<blockquote class="border-l-4 border-gray-200 pl-4 py-1 text-gray-600 italic">${applyInline(bq[1])}</blockquote>`,
      )
      continue
    }

    // paragraph
    closeList()
    html.push(`<p class="text-gray-700 leading-relaxed">${applyInline(trimmed)}</p>`)
  }

  closeList()
  closeCodeFence()

  return html.join('\n')
}

