/* THE THREE-STATE PROOF, read off the rendered page — the instrument behind
   ticket fccb9cf3's acceptance.

   Run against three arms of the same page and compare:
     LOADED    a live spine                   -> numbers, pendingWords 0
     FAILED    a spine that 502s everything   -> failureWords > 0, pendingWords 0
     IN FLIGHT a spine that never answers     -> pendingWords > 0, failureWords 0

   THE ONE PROPERTY IT EXISTS TO CHECK: the two vocabularies must never both be
   non-zero on one arm. A page saying "still reading" and "could not be read"
   about the same fetch is the defect this ticket repaired, and the count is
   the cheapest way to see it.

   For the in-flight arm you need a spine that ACCEPTS and never responds; a
   dev-server restart also produces the state for a few seconds, which is
   exactly how the CEO met it. Shoot within the client's 60s axios timeout
   (src/lib/fund_api.ts) — after that the read has genuinely failed and the
   failure language is CORRECT.

   NOTE: this counts words across the whole body, so a page that legitimately
   QUOTES the failure language (the ticket's own text on a desk card) counts
   too. Read `leaves` before concluding — a count without its sentences cannot
   tell a defect from a quotation. */
(() => {
  const leaves = [];
  for (const n of document.querySelectorAll("p,span,div,h1,h2")) {
    if (n.children.length > 0) continue;          // leaves only, no double-count
    const t = (n.textContent || "").replace(/\s+/g, " ").trim();
    if (!t) continue;
    if (/could not be read|unreadable|UNKNOWN|Reading the|Not counted yet|has not been counted yet|not worked out yet|Not read yet|still being read|reading the/i.test(t)) {
      leaves.push(t.length > 130 ? `${t.slice(0, 127)}...` : t);
    }
  }
  const all = (document.body.textContent || "").replace(/\s+/g, " ");
  const failureWords = (all.match(/could not be read|is unreadable|unreachable/gi) || []).length;
  const pendingWords = (all.match(/Reading the desk|reading the event log|reading the flight recorder|Not counted yet|has not been counted yet|not worked out yet|Not read yet|still being read|not read yet/gi) || []).length;
  return JSON.stringify({
    url: location.pathname,
    bodyChars: all.length,
    failureWords,
    pendingWords,
    /* THE INSTRUMENT REFUSES TO CONCLUDE when both vocabularies are present.
       Measured on the live CEO desk 2026-08-24: 3 and 2, with the whole
       overlap coming from a desk CARD quoting this very ticket — the page was
       rendering the bug report about the sentences, not the sentences. A count
       that cannot tell a defect from a quotation must say so where the count
       is, not only in a comment at the top of the file. */
    caution: failureWords > 0 && pendingWords > 0
      ? "BOTH vocabularies are on this page. That is either the defect or a "
        + "quotation — read `leaves` and decide; do not read the counts alone."
      : null,
    leaves: leaves.slice(0, 16),
  }, null, 1);
})()
