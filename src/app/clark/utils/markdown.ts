/**
 * Clark's markdown renderer.
 *
 * Lifted out of ResultsDisplay so the live streaming view and the committed
 * message can share it. They must: while a turn was streaming the operator saw
 * raw `## Fund Pass Summary` and `**Total NAV:**`, which then snapped to
 * rendered headings the instant the turn committed. Two renderers for the same
 * text is one renderer too many.
 */

export const markdownToHtml = (markdown: string): string => {
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
    return escaped
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/__(.+?)__/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/_(.+?)_/g, '<em>$1</em>')
  }

  /** Wrap numbers and percentages in paragraphs for .clark-num styling */
  const applyInlineWithNumWrap = (text: string) => {
    const numbers: string[] = []
    const pl = '\u0002'
    // Order matters: grouped thousands first, or `$2,028.34` matches only its
    // `028.34` tail and renders as proportional "$2," followed by a mono
    // fragment. Harmless while figures looked like prose; obvious the moment
    // they are set in a different face.
    const FIGURE =
      /(-?[$€£]?\d{1,3}(?:,\d{3})+(?:\.\d+)?\s*%?|-?[$€£]?\d+\.\d+\s*%?|-?\d+\s*%)/g
    const replaced = text.replace(FIGURE, (m) => {
      numbers.push(m)
      return `${pl}${numbers.length - 1}${pl}`
    })
    let out = applyInline(replaced)
    numbers.forEach((n, i) => {
      out = out.replace(`${pl}${i}${pl}`, `<span class="clark-num">${escapeHtml(n)}</span>`)
    })
    return out
  }

  const lines = markdown.split(/\n/)
  const htmlParts: string[] = []
  let inList = false
  let inTable = false
  let tableHeadDone = false

  const closeTable = () => {
    if (inTable) {
      if (tableHeadDone) {
        htmlParts.push('</tbody>')
      } else {
        htmlParts.push('</thead>')
      }
      htmlParts.push('</table>')
      inTable = false
      tableHeadDone = false
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    if (!trimmed) {
      if (inList) {
        htmlParts.push('</ul>')
        inList = false
      }
      closeTable()
      // Preserve paragraph spacing: empty line => small vertical gap
      htmlParts.push('<p class="h-2" aria-hidden="true"></p>')
      continue
    }

    // Headers (## or ###)
    const h2Match = trimmed.match(/^## (.+)$/)
    const h3Match = trimmed.match(/^### (.+)$/)
    if (h2Match) {
      if (inList) { htmlParts.push('</ul>'); inList = false }
      closeTable()
      htmlParts.push(`<h2 class="text-lg font-semibold text-[var(--kt-text-strong)] mt-4 mb-2">${applyInline(h2Match[1])}</h2>`)
      continue
    }
    if (h3Match) {
      if (inList) { htmlParts.push('</ul>'); inList = false }
      closeTable()
      htmlParts.push(`<h3 class="text-base font-semibold text-[var(--kt-text-strong)] mt-3 mb-1">${applyInline(h3Match[1])}</h3>`)
      continue
    }

    // Table: | a | b | (optional separator row |---|---|)
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      if (inList) { htmlParts.push('</ul>'); inList = false }
      const rawCells = trimmed.slice(1, -1).split('|').map((c) => c.trim())
      const isSeparator = rawCells.every((c) => /^[-:]+$/.test(c))
      if (isSeparator) {
        if (inTable && !tableHeadDone) {
          htmlParts.push('</thead><tbody>')
          tableHeadDone = true
        }
        continue
      }
      const cells = rawCells.map((c) => applyInline(c))
      if (!inTable) {
        htmlParts.push('<table class="w-full border-collapse border border-[var(--kt-border)] my-2 text-sm"><thead><tr class="border-b border-[var(--kt-border)] bg-[var(--kt-inset)]">')
        inTable = true
      }
      const useTh = !tableHeadDone
      if (useTh) {
        htmlParts.push(`<tr class="border-b border-[var(--kt-border)]/30">${cells.map((c) => `<th class="text-left py-2 px-3 font-semibold text-[var(--kt-accent-soft)]">${c}</th>`).join('')}</tr>`)
        tableHeadDone = true
        htmlParts.push('</thead><tbody>')
      } else {
        const cellClass = 'text-left py-2 px-3 border-t border-[var(--kt-border)]/40 text-[var(--kt-text)]'
        htmlParts.push(`<tr class="border-b border-[var(--kt-border)]/30">${cells.map((c) => `<td class="${cellClass}">${c}</td>`).join('')}</tr>`)
      }
      continue
    }

    if (inTable) {
      closeTable()
    }

    if (trimmed.startsWith('- ')) {
      if (!inList) {
        htmlParts.push('<ul class="list-disc pl-5 space-y-1">')
        inList = true
      }
      htmlParts.push(`<li>${applyInlineWithNumWrap(trimmed.slice(2).trim())}</li>`)
    } else {
      if (inList) {
        htmlParts.push('</ul>')
        inList = false
      }
      htmlParts.push(`<p class="mb-1">${applyInlineWithNumWrap(trimmed)}</p>`)
    }
  }

  if (inList) htmlParts.push('</ul>')
  closeTable()

  return htmlParts.join('')
}
