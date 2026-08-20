import { redirect } from "next/navigation";

/**
 * Mechanics is no longer a tab. Its views moved to the seats that own them.
 *
 * The consolidation rule the CEO set: a chart stays only if it informs a
 * specific click or dispatch. Mechanics was the one surface you opened to
 * understand the SYSTEM rather than to operate it — which meant its funnel, its
 * causes of death and its gate lineage sat one navigation away from the place
 * they change a decision. They now render on the quant's seat page (the lane
 * that owns the belt) and the firm's story and ladder render on the Desk, which
 * became the office view.
 *
 * Kept as a redirect rather than deleted: the tab was linked and bookmarked,
 * and a 404 teaches nothing about where the content went. Same precedent as
 * /clark/studio/monitor.
 */
export default function Page() {
  redirect("/clark/studio/desk");
}
