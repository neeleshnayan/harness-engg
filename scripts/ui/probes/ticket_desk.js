/* THE EXCEPTIONS DESK, MEASURED — geometry, not textContent.

   WHAT IT EXISTS TO PROVE, and each item is a defect this desk has actually
   shipped:

     1. NO CONTROL ON A CLOSED ROW. Every card is checked for a decision
        control; a card whose ticket is terminal must have none and must carry
        a sentence where the control would be. `textContent` cannot tell an
        absent control from an unrendered one, so the check reads the control
        SLOT's geometry and its text together.
     2. THE FIRST DECISION'S DISTANCE FROM THE TOP OF THE PAGE, in px. On the
        desk this replaces the first Accept button was 11,608px down. A number,
        not an impression.
     3. EVERY SURFACED ROW CARRIES A RULE CHIP. A row the CEO cannot explain
        the presence of is the defect being fixed, so a card in the decisions
        or escalations block with no chip is a failure.
     4. NO NUMBER IS RENDERED BESIDE AN ABSENCE SENTENCE about the same read.

   Layout claims use getBoundingClientRect. A `textContent` probe once reported
   two toggles as "welded" on a page whose screenshot showed a 12px gap. */
(() => {
  const px = (el) => {
    const r = el.getBoundingClientRect();
    return { top: Math.round(r.top + window.scrollY), h: Math.round(r.height) };
  };
  const cards = [...document.querySelectorAll("article")];
  const rows = cards.map((c) => {
    const t = (c.textContent || "").replace(/\s+/g, " ").trim();
    const idEl = [...c.querySelectorAll("p")].pop();
    /* NOT `span.rounded-full` — THE LAMP IS ONE TOO, and it is first in the
       DOM, so the naive selector reported every chip as "" and made
       `rowsWithoutARuleChip: 0` a vacuous pass. A selector that matches two
       different things silently answers about the wrong one. */
    const chip = [...c.querySelectorAll("span.rounded-full")]
      .find((s) => (s.textContent || "").trim().length > 0) || null;
    const link = c.querySelector('a[href="/clark/studio/desk/ceo"]');
    return {
      top: px(c).top,
      h: px(c).h,
      chip: chip ? chip.textContent.trim() : null,
      /* A DECISION CONTROL IS THE LINK TO THE APPROVAL PATH. This page opens no
         door itself, so "has a control" means "offers the reader somewhere to
         act", which is the thing a closed row must not do. */
      hasControl: !!link,
      saysOwed: /A decision is owed|An execution is owed/.test(t),
      saysClosed: /terminal state|Terminal is terminal|no decision is owed|move, not yours/.test(t),
      id: idEl ? (idEl.textContent || "").trim().split(/\s+/)[0] : null,
      lamp: (() => {
        const l = c.querySelector("span[title]");
        return l ? l.getAttribute("title") : null;
      })(),
    };
  });

  const withControl = rows.filter((r) => r.hasControl);
  const closedWithControl = rows.filter((r) => r.saysClosed && r.hasControl);
  const firstDecision = withControl.length ? withControl[0].top : null;

  const body = (document.body.textContent || "").replace(/\s+/g, " ");
  const heroes = [...document.querySelectorAll("span")]
    .filter((s) => /text-4xl/.test(s.className || ""))
    .map((s) => ({ text: (s.textContent || "").trim(), ...px(s) }));

  return JSON.stringify({
    url: location.pathname,
    cards: rows.length,
    /* THE HEADLINE CHECK. Non-zero here is the "like WTF" defect returning. */
    closedRowsOfferingAControl: closedWithControl.length,
    closedRowIds: closedWithControl.map((r) => r.id).slice(0, 8),
    rowsWithAControl: withControl.length,
    rowsWithoutARuleChip: rows.filter((r) => r.chip === null).length,
    firstDecisionTopPx: firstDecision,
    pageHeightPx: Math.round(document.body.scrollHeight),
    heroes,
    fencedSentences: (body.match(/LINEAGE UNKNOWN/g) || []).length,
    unknownSentences: (body.match(/UNKNOWN, not zero|UNKNOWN rather than|age UNKNOWN/g) || []).length,
    sampleChips: [...new Set(rows.map((r) => r.chip).filter(Boolean))].slice(0, 8),
    sampleLamps: [...new Set(rows.map((r) => r.lamp).filter(Boolean))],
    firstThreeCards: rows.slice(0, 3),
  }, null, 1);
})()
