/* STRICTER interception probe.
 *
 * The first probe counted an element as intercepted whenever its
 * getBoundingClientRect extended into the rail's band and elementFromPoint
 * there returned the rail. That over-counts: an element inside a container
 * with overflow-x:auto has an UNTRUNCATED bounding box, so a wide table cell
 * "reaches" under the rail while being clipped and unpainted there.
 *
 * This version only counts a point as intercepted if the point lies inside
 * every clipping ancestor's rect — i.e. the element really is painted there
 * and the rail really is taking the click.
 *
 * usage: node cdp_strict.js <baseUrl> <width> [pages csv]
 */
const WS = require("ws");
const http = require("http");
const [, , BASE, W, PAGES_CSV] = process.argv;
const width = parseInt(W || "1024", 10);
const PAGES = (PAGES_CSV || "/clark/studio,/clark/studio/desk/ceo,/clark/studio/desk,/clark/studio/allocate,/clark/studio/risk,/clark/studio/lab").split(",");

function get(path) {
  return new Promise((res, rej) => {
    http.get({ host: "127.0.0.1", port: 9222, path }, (r) => {
      let b = ""; r.on("data", (d) => (b += d)); r.on("end", () => res(JSON.parse(b)));
    }).on("error", rej);
  });
}

const PROBE = `(() => {
  const rail = [...document.querySelectorAll('aside')].find(a => getComputedStyle(a).position === 'fixed');
  if (!rail) return JSON.stringify({ err: 'no rail' });
  const rr = rail.getBoundingClientRect();
  const clipRect = (el) => {
    // Intersect the rects of every scroll/clip ancestor.
    let x0 = 0, y0 = 0, x1 = window.innerWidth, y1 = window.innerHeight;
    for (let p = el.parentElement; p; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (/(auto|scroll|hidden|clip)/.test(cs.overflowX + ' ' + cs.overflowY)) {
        const r = p.getBoundingClientRect();
        x0 = Math.max(x0, r.left); y0 = Math.max(y0, r.top);
        x1 = Math.min(x1, r.right); y1 = Math.min(y1, r.bottom);
      }
    }
    return { x0, y0, x1, y1 };
  };
  const bad = [];
  const seen = new Set();
  for (const el of document.querySelectorAll('body *')) {
    if (rail.contains(el) || seen.has(el)) continue;
    seen.add(el);
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || cs.pointerEvents === 'none') continue;
    const b = el.getBoundingClientRect();
    if (b.width < 8 || b.height < 4) continue;
    if (!(b.right > rr.left + 1 && b.left < rr.right)) continue;
    const c = clipRect(el);
    // The band of this element that is BOTH painted (inside every clip) and
    // inside the rail's box.
    const px0 = Math.max(b.left, rr.left + 1, c.x0);
    const px1 = Math.min(b.right, rr.right, c.x1);
    const py0 = Math.max(b.top, c.y0, 1);
    const py1 = Math.min(b.bottom, c.y1, window.innerHeight - 1);
    if (px1 - px0 < 2 || py1 - py0 < 2) continue;
    const px = Math.min(px0 + 2, px1 - 1);
    const py = (py0 + py1) / 2;
    const top = document.elementFromPoint(px, py);
    if (top && rail.contains(top)) {
      bad.push({
        tag: el.tagName,
        text: (el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 50),
        band: Math.round(px1 - px0),
      });
    }
  }
  return JSON.stringify({
    railLeft: Math.round(rr.left), railWidth: Math.round(rr.width),
    pad: getComputedStyle(document.body).paddingRight,
    intercepted: bad.length, sample: bad.slice(0, 5),
  });
})()`;

(async () => {
  const targets = await get("/json/list");
  const page = targets.find((t) => t.type === "page");
  const ws = new WS(page.webSocketDebuggerUrl, { maxPayload: 256 * 1024 * 1024 });
  let id = 0; const waiters = new Map();
  ws.on("message", (m) => { const msg = JSON.parse(m); if (msg.id && waiters.has(msg.id)) { waiters.get(msg.id)(msg); waiters.delete(msg.id); } });
  const send = (method, params = {}) => new Promise((res) => { const i = ++id; waiters.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
  await new Promise((r) => ws.on("open", r));
  await send("Page.enable"); await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: false });
  await send("Page.navigate", { url: `${BASE}/clark/studio` });
  await new Promise((r) => setTimeout(r, 2500));
  await send("Runtime.evaluate", { expression: `localStorage.setItem("clark.rail.open","1")` });
  for (const p of PAGES) {
    await send("Page.navigate", { url: `${BASE}${p}` });
    await new Promise((r) => setTimeout(r, 8000));
    const r = await send("Runtime.evaluate", { expression: PROBE, returnByValue: true });
    console.log(p.padEnd(26), r.result.result.value);
  }
  ws.close();
})();
