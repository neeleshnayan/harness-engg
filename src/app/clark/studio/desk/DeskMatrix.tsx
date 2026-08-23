"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { DeskCategory, DeskEngineItem, DeskMatrix as DeskMatrixData } from "@/lib/fund_api";
import { KT } from "../theme";
import { money } from "../format";
import { SeatFace } from "./SeatFace";
import {
  CATEGORY_LABELS, MatrixRow, cellKey, expandable, matrixRows, truncationNote,
} from "./deskEngine";

/**
 * THE MATRIX — the firm's ticket board, seats down, categories across.
 *
 * CEO instruction, 2026-08-23, verbatim: *"like put a matrix view that shows
 * intra-team ticket count -> I click it expands the list; then different
 * categories for whats closed, whats ticking, whats blocking, whats open"* —
 * given after the page it replaces earned *"this feels like an infine scroll.
 * We need better organisation here too!"*
 *
 * THREE PROPERTIES, each answering a specific way this could go wrong:
 *
 *  1. **Nothing renders unbounded on first paint.** What you see is one row
 *     per seat and four numbers. Every list is behind a click, and every list
 *     is itself capped by the spine with `shown` / `total` on the wire — so a
 *     cap can never be read as a count. The previous page put the first Accept
 *     button 11,608px down; this one puts every number in one screenful.
 *  2. **The count and the list are the SAME list.** Both come from
 *     `desk_matrix`'s cell. This component classifies nothing, sorts nothing
 *     and counts nothing — it renders a fold. A page that re-derived any of
 *     those would be the 11-vs-6 defect at four times the surface area.
 *  3. **A column's meaning is rendered, not assumed.** The definitions come
 *     from the spine and sit under the header, because "blocking" is a
 *     judgement and a reader is entitled to see the predicate.
 *
 * Hierarchy from type and space, never colour (the design brief). A zero is
 * dimmed rather than hidden — an empty cell is a measured fact here, since the
 * fold's own contract is that every item lands in exactly one column.
 */

const ORDER: DeskCategory[] = ["open", "ticking", "blocking", "closed"];

export function DeskMatrix({ matrix, onOpenItem }: {
  matrix: DeskMatrixData | null;
  onOpenItem?: (item: DeskEngineItem) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const rows = matrixRows(matrix);

  if (!matrix) {
    return (
      <div className={`${KT.panel} p-4`}>
        <p className={`text-sm ${KT.sev.warn}`}>
          The ticket board could not be read, so it is showing nothing rather
          than an empty firm. An unreadable board is not a clear one.
        </p>
      </div>
    );
  }
  if (rows.length === 0) {
    return (
      <div className={`${KT.panel} p-4`}>
        <p className={`text-sm ${KT.muted}`}>
          The board was read and holds no tickets. That is a measurement, not a
          gap.
        </p>
      </div>
    );
  }

  const cats = (matrix.categories?.length ? matrix.categories : ORDER);

  // overflow-x-AUTO, not hidden, and the reason is measured. At a 1024px
  // viewport the Studio's Clark rail begins at x=589 while this board's last
  // column reaches x=968 — so 379px of it, which is ALL FOUR NUMBERS, sits
  // under the rail. `overflow-hidden` would clip the data silently; a scroll
  // keeps it reachable. (The clipping itself is the page shell's, not this
  // component's: the risk bar and the seat cards are cut at the same x. It is
  // reported, not fixed here.)
  return (
    <div className={`${KT.panel} overflow-x-auto`}>
      <div className="grid min-w-[30rem] grid-cols-[minmax(0,1fr)_repeat(4,minmax(2.75rem,4.5rem))] items-end gap-x-2 border-b border-[var(--kt-border)] px-4 py-3">
        <p className={KT.label}>Seat</p>
        {cats.map((c) => (
          <p key={c} className={`${KT.label} text-right`}>{CATEGORY_LABELS[c]}</p>
        ))}
      </div>

      {rows.map((row) => (
        <SeatRow key={row.seat} row={row} cats={cats} open={open}
                 setOpen={setOpen} onOpenItem={onOpenItem} />
      ))}

      <div className="border-t border-[var(--kt-border)] px-4 py-3">
        <div className="grid min-w-[30rem] grid-cols-[minmax(0,1fr)_repeat(4,minmax(2.75rem,4.5rem))] items-baseline gap-x-2">
          <p className={`text-xs font-medium ${KT.muted}`}>
            {matrix.items_classified} ticket(s), every one in exactly one column
          </p>
          {cats.map((c) => (
            <p key={c} className={`${KT.number} text-right text-[var(--kt-text-strong)]`}>
              {matrix.totals?.[c] ?? 0}
            </p>
          ))}
        </div>
        <dl className="mt-3 space-y-1">
          {cats.map((c) => (
            <div key={c} className="flex gap-2 text-[11px] leading-relaxed">
              <dt className={`w-16 shrink-0 font-mono uppercase tracking-[0.1em] ${KT.muted}`}>
                {CATEGORY_LABELS[c]}
              </dt>
              <dd className={KT.muted}>{matrix.definitions?.[c]}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}

function SeatRow({ row, cats, open, setOpen, onOpenItem }: {
  row: MatrixRow;
  cats: DeskCategory[];
  open: string | null;
  setOpen: (k: string | null) => void;
  onOpenItem?: (item: DeskEngineItem) => void;
}) {
  const expandedCat = cats.find((c) => open === cellKey(row.seat, c)) ?? null;
  const cell = expandedCat ? row.cells[expandedCat] : null;

  return (
    <div className="border-b border-[var(--kt-border)] last:border-b-0">
      <div className="grid min-w-[30rem] grid-cols-[minmax(0,1fr)_repeat(4,minmax(2.75rem,4.5rem))] items-center gap-x-2 px-4 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <SeatFace actor={row.seat} size={26} />
          <span className="truncate text-sm">{row.seat}</span>
          <span className={`shrink-0 font-mono text-[10px] ${KT.muted}`}>
            {row.live} live
          </span>
        </div>
        {cats.map((c) => {
          const cl = row.cells[c];
          const key = cellKey(row.seat, c);
          const on = open === key;
          const can = expandable(cl);
          return (
            <button
              key={c}
              type="button"
              disabled={!can}
              onClick={() => setOpen(on ? null : key)}
              aria-expanded={on}
              aria-label={`${row.seat} ${CATEGORY_LABELS[c]}: ${cl.count}`}
              className={`rounded-lg px-2 py-1 text-right font-mono tabular-nums text-sm transition-colors ${
                can
                  ? on
                    ? "bg-[var(--kt-accent-bg)] text-[var(--kt-accent)]"
                    : "text-[var(--kt-text-strong)] hover:bg-[var(--kt-hover)]"
                  : `${KT.muted} cursor-default`
              }`}
            >
              {cl.count}
            </button>
          );
        })}
      </div>

      {expandedCat && cell && (
        <div className={`${KT.inset} mx-4 mb-3 p-0`}>
          <div className="flex items-center gap-1.5 border-b border-[var(--kt-border)] px-3 py-2">
            <ChevronDown size={12} className={KT.muted} />
            <p className={KT.label}>
              {row.seat} · {CATEGORY_LABELS[expandedCat]} · {cell.count}
            </p>
          </div>
          {/* THE PANEL SCROLLS; THE BOARD DOES NOT MOVE.
              Measured with a CDP probe: expanding builder's 30-row BLOCKING
              cell pushed the remaining twelve seats ~1,000px down the page,
              which rebuilds the scroll the board was built to replace — one
              click in. A bounded panel keeps the matrix in place, and the cap
              beneath it still states `shown of count` so nothing is hidden. */}
          <ul className="max-h-[26rem] divide-y divide-[var(--kt-border)] overflow-y-auto">
            {cell.items.map((it, i) => (
              <ItemRow key={it.ref ?? it.item_id ?? i} item={it}
                       onOpen={onOpenItem} />
            ))}
          </ul>
          {truncationNote(cell) && (
            <p className={`px-3 py-2 text-[11px] italic ${KT.muted}`}>
              {truncationNote(cell)}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function ItemRow({ item, onOpen }: {
  item: DeskEngineItem;
  onOpen?: (item: DeskEngineItem) => void;
}) {
  const href = item.source === "recommendation" && item.run_id
    ? `/clark/studio/desk/${item.seat ?? "cto"}`
    : null;
  const body = (
    <>
      <p className="text-xs leading-relaxed text-[var(--kt-text)]">
        {(item.title ?? "").slice(0, 220) || (
          <span className={KT.muted}>this row carries no text</span>
        )}
      </p>
      <p className={`mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] ${KT.muted}`}>
        <span>{item.source}</span>
        <span>{item.status}</span>
        {/* Absent is rendered as a WORD. A blank cell where a date should be
            reads as "soon"; a blank where money should be reads as zero. */}
        <span>{item.due_date ? `due ${item.due_date}` : "no date"}</span>
        <span>
          {typeof item.money_at_stake === "number"
            ? money(item.money_at_stake)
            : "no figure stated"}
        </span>
        {item.next_actor_resolved && <span>→ {item.next_actor_resolved}</span>}
      </p>
      {item.category_why && (
        <p className={`mt-1 text-[10px] italic ${KT.muted}`}>{item.category_why}</p>
      )}
    </>
  );
  if (onOpen) {
    return (
      <li>
        <button type="button" onClick={() => onOpen(item)}
                className="block w-full px-3 py-2 text-left hover:bg-[var(--kt-hover)]">
          {body}
        </button>
      </li>
    );
  }
  return (
    <li className="px-3 py-2">
      {href ? (
        <Link href={href} className="block hover:opacity-80">
          <span className="flex items-start gap-1.5">
            <ChevronRight size={11} className={`mt-1 shrink-0 ${KT.muted}`} />
            <span className="min-w-0 flex-1">{body}</span>
          </span>
        </Link>
      ) : body}
    </li>
  );
}
