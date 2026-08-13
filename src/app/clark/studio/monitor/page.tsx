import { redirect } from "next/navigation";

/**
 * Monitor is the Studio landing page now, not a tab you navigate to.
 *
 * The old IA opened on Decide — the approval queue alone — which made the fund's
 * rarest event the first thing you saw and put halt state, breaches and fills
 * one click away. This route is kept as a redirect because it was linked from
 * elsewhere and bookmarked; the content lives at /clark/studio.
 */
export default function Page() {
  redirect("/clark/studio");
}
