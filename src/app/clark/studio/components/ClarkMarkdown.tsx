"use client";

import React from "react";

/**
 * The small slice of markdown Clark actually emits, rendered safely.
 *
 * Two deliberate constraints.
 *
 * **No `dangerouslySetInnerHTML`.** This renders model output. Even a local
 * model's text is untrusted input — it can repeat anything it read from a
 * quote feed, a filing, or a symbol name — and building React elements means
 * there is no HTML injection surface at all rather than one guarded by a
 * sanitiser we would have to keep correct.
 *
 * **No new dependency.** react-markdown plus remark plus rehype is a large
 * tree to add to a trading cockpit an hour before the open, for headings,
 * bullets, bold and tables. This handles what Clark produces; if it ever emits
 * something richer, the fallback is plain text, which is legible rather than
 * broken.
 */

type Props = { text: string; className?: string };

/** `**bold**`, `` `code` `` — applied within a line, in one pass. */
function inline(text: string, keyPrefix: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  // Split on bold or code, keeping the delimiters so they can be styled.
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  parts.forEach((p, i) => {
    if (!p) return;
    if (p.startsWith("**") && p.endsWith("**") && p.length > 4) {
      out.push(
        <strong key={`${keyPrefix}b${i}`} className="font-semibold">
          {p.slice(2, -2)}
        </strong>,
      );
    } else if (p.startsWith("`") && p.endsWith("`") && p.length > 2) {
      out.push(
        <code
          key={`${keyPrefix}c${i}`}
          className="rounded bg-[var(--kt-hover)] px-1 py-0.5 font-mono text-[11px]"
        >
          {p.slice(1, -1)}
        </code>,
      );
    } else {
      out.push(<React.Fragment key={`${keyPrefix}t${i}`}>{p}</React.Fragment>);
    }
  });
  return out;
}

export function ClarkMarkdown({ text, className = "" }: Props) {
  const lines = (text || "").replace(/\r\n/g, "\n").split("\n");
  const blocks: React.ReactNode[] = [];

  let bullets: string[] = [];
  let table: string[] = [];

  const flushBullets = (k: string) => {
    if (!bullets.length) return;
    blocks.push(
      <ul key={k} className="my-1 ml-4 list-disc space-y-1">
        {bullets.map((b, i) => (
          <li key={i} className="leading-relaxed">
            {inline(b, `${k}-${i}-`)}
          </li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  const flushTable = (k: string) => {
    if (table.length < 2) {
      // Not actually a table — a lone pipe line is more likely prose.
      table.forEach((t, i) =>
        blocks.push(
          <p key={`${k}p${i}`} className="my-1 leading-relaxed">
            {inline(t, `${k}p${i}-`)}
          </p>,
        ),
      );
      table = [];
      return;
    }
    const cells = (row: string) =>
      row.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
    const head = cells(table[0]);
    // Row 1 of a markdown table is the |---|---| separator; skip it if present.
    const body = table.slice(/^[\s|:-]+$/.test(table[1]) ? 2 : 1).map(cells);
    blocks.push(
      <div key={k} className="my-2 overflow-x-auto">
        <table className="w-full border-collapse text-[11px]">
          <thead>
            <tr>
              {head.map((h, i) => (
                <th
                  key={i}
                  className="border-b border-[var(--kt-border)] px-2 py-1 text-left font-semibold"
                >
                  {inline(h, `${k}h${i}-`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.map((r, ri) => (
              <tr key={ri}>
                {r.map((c, ci) => (
                  <td
                    key={ci}
                    className="border-b border-[var(--kt-border)] px-2 py-1 align-top tabular-nums"
                  >
                    {inline(c, `${k}c${ri}-${ci}-`)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    );
    table = [];
  };

  lines.forEach((raw, idx) => {
    const line = raw.trimEnd();
    const k = `l${idx}`;

    if (/^\s*\|.*\|\s*$/.test(line)) {
      flushBullets(`${k}fb`);
      table.push(line.trim());
      return;
    }
    flushTable(`${k}ft`);

    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    if (bullet) {
      bullets.push(bullet[1]);
      return;
    }
    flushBullets(`${k}fb2`);

    if (!line.trim()) return;

    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      const size = h[1].length <= 2 ? "text-[13px]" : "text-[12px]";
      blocks.push(
        <div key={k} className={`mt-2 mb-1 font-semibold ${size}`}>
          {inline(h[2], `${k}-`)}
        </div>,
      );
      return;
    }

    blocks.push(
      <p key={k} className="my-1 leading-relaxed">
        {inline(line, `${k}-`)}
      </p>,
    );
  });

  flushBullets("fb-end");
  flushTable("ft-end");

  return <div className={className}>{blocks}</div>;
}
