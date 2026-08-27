"use client";

import React, { useEffect, useState } from "react";
import { fundApiClient } from "@/lib/fund_api";
import { KT } from "../theme";

/**
 * THE READING ROOM — the shelf of finished research, made reachable.
 *
 * CEO, 2026-08-27, verbatim: *"I thought we gave dedicated reading rooms aka
 * like a file vault to teams generating research or actual work product that I
 * could go in and read"*. He was right on both counts. Six house-styled PDFs
 * had been rendering to disk since 2026-08-23 and nothing in the studio linked
 * to a single one — a shelf nobody can reach is not a library, it is a
 * directory.
 *
 * DOES THIS FORM SERVE THIS CONTENT BETTER THAN A GENERIC LIST WOULD? The
 * content is a short shelf of finished documents, and the reader's question is
 * *what is here and is any of it new*. So: title first at reading weight, date
 * right-aligned in `tabular-nums` so recency is one downward scan, and the
 * whole row is the link — a shelf where you have to aim at a small word to
 * open a book is a shelf that does not want to be read. No thumbnails, no
 * cards: six rows do not need a grid, and a grid would make six documents look
 * like a product page.
 *
 * THIS IS THE VISIBLE HALF ONLY. The durable half of the charter (a table, an
 * ingest, per-seat partitioning) is chartered separately and is not built. The
 * room says nothing that implies otherwise.
 */

type Shelf = Awaited<ReturnType<typeof fundApiClient.getLibrary>>;

export function ReadingRoom() {
  /* THREE STATES, and the middle one is the whole point of the flag. `null`
     is "still reading"; a payload with `readable: false` is "the shelf could
     not be opened"; a payload with an empty list is "there is nothing on it
     yet". A component that collapsed the last two would report a permissions
     error as a fund that has written no research. */
  const [shelf, setShelf] = useState<Shelf | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    fundApiClient.getLibrary()
      .then((s) => { if (live) { setShelf(s); setErr(null); } })
      .catch((e) => { if (live) setErr(e instanceof Error ? e.message : "unreachable"); });
    return () => { live = false; };
  }, []);

  return (
    <section id="reading-room" className="mb-8">
      <div className="mb-2.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className={KT.label}>The reading room</span>
        <span className={`text-[11px] ${KT.muted}`}>
          Finished research, as it was written. Opens in a new tab.
        </span>
      </div>

      {err ? (
        <p className={`text-sm ${KT.sev.warn}`}>
          We could not reach the shelf, so what is on it is unknown — not
          nothing. {err}
        </p>
      ) : shelf === null ? (
        <p className={`text-sm ${KT.muted}`}>Opening the shelf…</p>
      ) : !shelf.readable ? (
        <p className={`text-sm ${KT.sev.warn}`}>{shelf.note}</p>
      ) : shelf.documents.length === 0 ? (
        <p className={`text-sm ${KT.muted}`}>{shelf.note}</p>
      ) : (
        <>
          <div className={`${KT.panel} overflow-hidden`}>
            {shelf.documents.map((d, i) => (
              <a
                key={d.name}
                href={fundApiClient.libraryDocumentUrl(d.name)}
                target="_blank"
                rel="noopener noreferrer"
                className={`flex items-baseline gap-3 px-5 py-3 transition-colors hover:bg-[var(--kt-hover)] ${
                  i === shelf.documents.length - 1
                    ? "" : "border-b border-[var(--kt-border)]/60"}`}
              >
                <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--kt-text-strong)]">
                  {/* `title`, NOT `display` — a look-pass repair. `display`
                      carries the date, and the date has its own column two
                      spans to the right, so the row read "Gold dossier v1 —
                      Aug 24 … 430 KB … Aug 24". The same fact twice on one
                      line is the reader's cue that a surface was assembled
                      rather than designed.
                      A title we READ, or the filename when we only guessed:
                      showing an invented title over a name we could not parse
                      would be tidier and would send the reader looking for a
                      document that is not called that. */}
                  {d.title_parsed
                    ? `${d.title}${d.version ? ` ${d.version}` : ""}`
                    : d.name}
                </span>
                <span className={`shrink-0 font-mono text-[10px] tabular-nums ${KT.muted}`}>
                  {sizeLabel(d.size_bytes)}
                </span>
                <span className={`w-16 shrink-0 text-right font-mono text-[10px] tabular-nums ${KT.muted}`}>
                  {d.date_display ?? "undated"}
                </span>
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none"
                     aria-hidden className={`shrink-0 ${KT.muted}`}>
                  <path d="M6.5 3.5h6v6M12.5 3.5L7 9M11 9.5v3h-8v-8h3"
                        stroke="currentColor" strokeWidth="1.25"
                        strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </a>
            ))}
          </div>
          {(shelf.unreadable ?? 0) > 0 && (
            <p className={`mt-2 text-[11px] ${KT.sev.warn}`}>{shelf.note}</p>
          )}
        </>
      )}
    </section>
  );
}

/** A file size the way a person says it. Never zero-padded, never bytes. */
function sizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
