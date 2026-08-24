/* THE CEO DESK'S HEADER, BLOCK BY BLOCK — the instrument behind every pixel
   figure quoted in `steerDemotion.test.ts`.

   Run:  node scripts/ui/measure.js http://127.0.0.1:3000/clark/studio/desk/ceo \
           scripts/ui/probes/header_geometry.js

   Prints, per paragraph in the page's own <header>: its rect, its computed
   font size and colour, its character count, and its text. Plus the header's
   total height and which block is tallest — the two numbers a demotion is
   judged on.

   THE HEADER IS FOUND FROM THE HERO, never `querySelector("header")`. The
   Studio shell renders its own <header> first, and the first cut of this probe
   measured that one and reported "no blocks" — a landmark that can match the
   wrong element is a probe that passes by not looking. If the hero stops being
   a `text-4xl` span this probe SAYS SO rather than returning an empty table. */
(() => {
  const hero = [...document.querySelectorAll("span")]
    .find((s) => /text-4xl/.test(s.className || ""));
  const header = hero ? hero.closest("header") : null;
  if (!header) {
    return JSON.stringify({
      error: "the hero span was not found — the page has not rendered, or the "
        + "hero stopped being a text-4xl span and this probe is stale",
      headersOnPage: document.querySelectorAll("header").length,
      bodyChars: (document.body.textContent || "").length,
    }, null, 1);
  }
  const blocks = [...header.querySelectorAll("p")].map((p, i) => {
    const r = p.getBoundingClientRect();
    const cs = getComputedStyle(p);
    const t = (p.textContent || "").replace(/\s+/g, " ").trim();
    return {
      i,
      topPx: Math.round(r.top), heightPx: Math.round(r.height),
      widthPx: Math.round(r.width),
      fontPx: cs.fontSize, colour: cs.color,
      chars: t.length,
      text: t.length > 130 ? `${t.slice(0, 127)}...` : t,
    };
  });
  const tallest = blocks.reduce((a, b) => (b.heightPx > a.heightPx ? b : a),
    { heightPx: -1, i: -1 });
  return JSON.stringify({
    headerHeightPx: Math.round(header.getBoundingClientRect().height),
    heroGlyph: (hero.textContent || "").trim(),
    heroFontPx: getComputedStyle(hero).fontSize,
    tallestBlock: { i: tallest.i, heightPx: tallest.heightPx },
    blocks,
  }, null, 1);
})()
