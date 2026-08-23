"use client";

import React from "react";
import { TriangleAlert } from "lucide-react";
import { KT } from "../theme";
import { fmtAt } from "./seatLib";
import { supersessionChip } from "./deskEngine";
import type { Lineage, LineageStage } from "./lineage";
import {
  supersessionCheckIsAlarm, supersessionCheckSentence, unreadableStages,
} from "./lineage";

/**
 * THE CHAIN BEHIND ONE ROW, rendered INLINE under it.
 *
 * WHY INLINE AND NOT A SHEET, stated because it is a real design choice and
 * the brief left it open. The Studio shell docks Clark's rail on the right at
 * every breakpoint the D28 `railLayout` knows about (1024 / 1280 / 1440), so a
 * right-hand drawer would either sit under the rail or fight it for the same
 * pixels — and the occlusion probe that caught the last one exists precisely
 * because "it looked fine" is not a measurement. An inline panel is bounded by
 * the content column, so it survives all three widths by construction and adds
 * no new stacking context to test.
 *
 * HIERARCHY FROM TYPE AND SPACE. Seven stages, each a 10px uppercase mono
 * label over 12px body, separated by whitespace and a single hairline. No
 * colour is spent on structure: the ONE coloured thing in this component is a
 * supersession brake that was NOT consulted, which is the only sentence here
 * that means something is wrong.
 *
 * EVERY STAGE RENDERS EVEN WHEN EMPTY. That is the point of the component. A
 * chain that drew only the stages it found would make a firm with almost no
 * run→request edges look like a firm with tidy short chains — and the measured
 * truth (2 of 117 runs declare service) is the opposite.
 */

function StageBlock<T>({ title, stage, children }: {
  title: string;
  stage: LineageStage<T>;
  children?: React.ReactNode;
}) {
  return (
    <div className="border-t border-[var(--kt-border)] px-4 py-3 first:border-t-0">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p className={KT.label}>{title}</p>
        <p className={`font-mono text-[10px] uppercase tracking-[0.1em] ${
          stage.state === "unreadable" ? KT.sev.warn
            : stage.state === "found" ? KT.muted : KT.muted}`}>
          {/* UNREADABLE IS A WORD, and "none" is a different word from a
              blank. A stage that rendered nothing for both would collapse an
              outage into a clean record. */}
          {stage.state === "found" ? stage.rows.length
            : stage.state === "unreadable" ? "unreadable" : "none"}
        </p>
      </div>
      {stage.state === "found"
        ? <div className="mt-2 space-y-2">{children}</div>
        : (
          <p className={`mt-1 max-w-3xl text-[11px] leading-relaxed ${
            stage.state === "unreadable" ? KT.sev.warn : KT.muted}`}>
            {stage.note}
          </p>
        )}
      {stage.state === "found" && (
        <p className={`mt-2 text-[11px] italic leading-relaxed ${KT.muted}`}>
          {stage.note}
        </p>
      )}
    </div>
  );
}

/** One fact on a line: a small mono key and its value. */
function Line({ children }: { children: React.ReactNode }) {
  return (
    <p className={`font-mono text-[10px] leading-relaxed ${KT.muted}`}>
      {children}
    </p>
  );
}

/** The four-valued disclosure, rendered so only one of the four shouts. */
function BrakeLine({ check }: { check: Parameters<typeof supersessionCheckSentence>[0] }) {
  const alarm = supersessionCheckIsAlarm(check);
  return (
    <p className={`mt-1 flex items-start gap-1.5 text-[11px] leading-relaxed ${
      alarm ? KT.sev.warn : KT.muted}`}>
      {alarm && <TriangleAlert size={12} className="mt-0.5 shrink-0" />}
      <span>{supersessionCheckSentence(check)}</span>
    </p>
  );
}

export function LineageView({ lineage }: { lineage: Lineage }) {
  const outages = unreadableStages(lineage);
  return (
    <div className={`${KT.inset} mt-2 p-0`}>
      {outages.length > 0 && (
        <p className={`flex items-start gap-1.5 border-b border-[var(--kt-border)] px-4 py-2 text-[11px] leading-relaxed ${KT.sev.warn}`}>
          <TriangleAlert size={12} className="mt-0.5 shrink-0" />
          <span>
            {outages.join(" and ")} could not be read, so this chain is
            INCOMPLETE rather than short. What is missing below may exist.
          </span>
        </p>
      )}

      <StageBlock title="1 · the ask" stage={lineage.request}>
        {lineage.request.rows.map((r) => (
          <div key={r.requestId}>
            <p className={`text-[12px] leading-relaxed ${KT.body}`}>{r.subject}</p>
            <Line>
              {r.actor ?? "unattributed"} asked {r.seat ?? "—"} · {r.kind ?? "no kind"}
              {" · "}{r.at ? fmtAt(r.at) : "undated"} · {r.status ?? "no status"}
            </Line>
            <Line>
              {r.approvedBy
                ? `approved by ${r.approvedBy}${r.approvedAt ? ` · ${fmtAt(r.approvedAt)}` : ""}`
                : "not approved, or the approval recorded no actor"}
            </Line>
            {/* THE D22 DISCLOSURE, READ. Until this line existed,
                `supersession_readable: false` appeared in the repo only inside
                the sentence promising it. */}
            <BrakeLine check={r.approvalSupersessionReadable} />
          </div>
        ))}
      </StageBlock>

      <StageBlock title="2 · dispatched" stage={lineage.dispatches}>
        {lineage.dispatches.rows.map((d) => (
          <Line key={d.taskId}>
            {d.actor ?? "—"} dispatched {d.seat ?? "—"}
            {" · "}{d.at ? fmtAt(d.at) : "undated"} · {d.taskId}
          </Line>
        ))}
      </StageBlock>

      <StageBlock title="3 · what came back" stage={lineage.runs}>
        {lineage.runs.rows.map((r) => (
          <div key={r.runId}>
            <p className={`text-[12px] leading-relaxed ${KT.body}`}>{r.task}</p>
            {r.verdict && (
              <p className={`mt-0.5 text-[12px] leading-relaxed text-[var(--kt-text)]`}>
                {r.verdict}
              </p>
            )}
            <Line>
              {r.seat} · {r.runId} · {r.at ? fmtAt(r.at) : "undated"}
              {" · joined by "}{r.joinedBy}
              {r.artifactPath ? ` · ${r.artifactPath}` : " · no artifact filed"}
            </Line>
          </div>
        ))}
      </StageBlock>

      <StageBlock title="4 · what it recommended" stage={lineage.recommendations}>
        {lineage.recommendations.rows.map((r) => (
          <div key={`${r.run_id}#${r.rec_id}`}>
            <p className={`text-[12px] leading-relaxed ${KT.body}`}>{r.text}</p>
            <Line>
              {r.seat} · rec {r.rec_id} · {r.status}
              {" · "}{r.due_date ? `due ${r.due_date}` : "no date"}
              {" · "}{typeof r.money_at_stake === "number"
                ? `$${r.money_at_stake.toLocaleString("en-US")}`
                : "no figure stated"}
            </Line>
          </div>
        ))}
      </StageBlock>

      <StageBlock title="5 · what was decided" stage={lineage.decisions}>
        {lineage.decisions.rows.map((d, i) => (
          <div key={`${d.runId}#${d.recId}#${i}`}>
            <Line>
              {d.actor ?? "no actor recorded"} · {d.status} · rec {d.recId}
              {" · "}{d.at ? fmtAt(d.at) : "undated"}
            </Line>
            {/* VERBATIM, IN QUOTES, OR NOT AT ALL. 300 of 551 decision events
                carry one; empty quotation marks under the other 251 would
                suggest the decider said nothing when the record simply holds
                nothing. */}
            {d.verbatim ? (
              <p className={`mt-1 border-l border-[var(--kt-border)] pl-3 text-[12px] leading-relaxed ${KT.body}`}>
                “{d.verbatim}”
              </p>
            ) : (
              <p className={`mt-1 text-[11px] ${KT.muted}`}>
                no written instruction was recorded with this decision
              </p>
            )}
            <BrakeLine check={d.supersessionReadable} />
          </div>
        ))}
      </StageBlock>

      <StageBlock title="6 · evidence it was carried out" stage={lineage.execution}>
        {lineage.execution.rows.map((e, i) => (
          <div key={i}>
            <p className={`text-[12px] leading-relaxed ${KT.body}`}>{e.text}</p>
            <Line>
              {e.actor ?? "no actor recorded"} · {e.at ? fmtAt(e.at) : "undated"}
            </Line>
          </div>
        ))}
      </StageBlock>

      <StageBlock title="7 · replaced by, or replaces" stage={lineage.supersessions}>
        {lineage.supersessions.rows.map((e) => {
          const chip = supersessionChip(e);
          return (
            <div key={e.edge_id}>
              <p className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.sev.warn}`}>
                {chip?.label ?? e.mode}
              </p>
              <p className={`mt-0.5 text-[12px] leading-relaxed ${KT.body}`}>
                {chip?.detail ?? e.reason}
              </p>
              <Line>
                {e.target_ref}
                {e.superseder_ref
                  ? ` → replaced by ${e.superseder_ref}`
                  : " → no replacement (killed on its merits)"}
                {" · applied by "}{e.applied_by}
                {e.applied_at ? ` · ${fmtAt(e.applied_at)}` : ""}
              </Line>
              {chip?.diesAt && <Line>premise dies at: {chip.diesAt}</Line>}
              {chip?.revivesIf && <Line>revives if: {chip.revivesIf}</Line>}
            </div>
          );
        })}
      </StageBlock>

      <p className={`border-t border-[var(--kt-border)] px-4 py-2 text-[11px] italic leading-relaxed ${KT.muted}`}>
        {lineage.joinNote}
      </p>
    </div>
  );
}
