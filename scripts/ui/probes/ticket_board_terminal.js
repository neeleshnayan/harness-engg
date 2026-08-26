/* THE TERMINAL-CARD PROOF, driven not asserted.

   Picks the `done` option in the board's state filter, waits, and then reports
   whether ANY rendered card offers a control. The whole point of the ticket
   card contract is that this number is zero for every terminal state, and a
   probe that only READ the default view would never see a terminal row at all
   — the board excludes them from "all working" on purpose.

   It also opens the first card's lineage, so the fenced sentence can be
   counted on a real row rather than asserted from the source. */
(() => {
  const sel = document.querySelector("select");
  if (!sel) return JSON.stringify({ error: "no state filter on this page" });
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLSelectElement.prototype, "value").set;
  setter.call(sel, "done");
  sel.dispatchEvent(new Event("change", { bubbles: true }));
  return JSON.stringify({ picked: sel.value });
})()
