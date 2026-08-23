/* CDP probe for D28: measure the Studio shell geometry at a given viewport.
 *
 * usage: node cdp28.js <url> <width> <height> [railPref] [shotPath]
 *   railPref: "1" | "0" | "none"  -> localStorage clark.rail.open
 *
 * Reports, from the REAL rendered DOM:
 *   - viewport / layout width
 *   - the rail's own quad (left edge, width, mode)
 *   - body paddingRight
 *   - the right edge of every non-rail element that has visible content
 *   - which of those elements is NOT the topmost at its own right-edge point
 *     (i.e. its clicks are intercepted) -- elementFromPoint, the real question
 */
const WS = require("ws");
const http = require("http");

const [, , URL_, W, H, PREF, SHOT] = process.argv;
const width = parseInt(W || "1024", 10);
const height = parseInt(H || "900", 10);

function get(path) {
  return new Promise((res, rej) => {
    http.get({ host: "127.0.0.1", port: 9222, path }, (r) => {
      let b = ""; r.on("data", (d) => (b += d)); r.on("end", () => res(JSON.parse(b)));
    }).on("error", rej);
  });
}

(async () => {
  const targets = await get("/json/list");
  const page = targets.find((t) => t.type === "page");
  const ws = new WS(page.webSocketDebuggerUrl, { maxPayload: 256 * 1024 * 1024 });
  let id = 0;
  const waiters = new Map();
  ws.on("message", (m) => {
    const msg = JSON.parse(m);
    if (msg.id && waiters.has(msg.id)) { waiters.get(msg.id)(msg); waiters.delete(msg.id); }
  });
  const send = (method, params = {}) =>
    new Promise((res) => { const i = ++id; waiters.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
  await new Promise((r) => ws.on("open", r));

  await send("Page.enable");
  await send("Runtime.enable");
  // Emulation persists across navigations and across runs -- always SET it.
  await send("Emulation.setDeviceMetricsOverride", {
    width, height, deviceScaleFactor: 1, mobile: false,
  });

  // Seed the rail preference on the origin before the app boots.
  await send("Page.navigate", { url: `http://127.0.0.1:3133/clark/studio` });
  await new Promise((r) => setTimeout(r, 2500));
  await send("Runtime.evaluate", {
    expression: PREF === "none"
      ? `localStorage.removeItem("clark.rail.open")`
      : `localStorage.setItem("clark.rail.open", ${JSON.stringify(PREF || "1")})`,
  });

  await send("Page.navigate", { url: URL_ });
  await new Promise((r) => setTimeout(r, 9000));

  const probe = `(() => {
    const rail = document.querySelector('aside.fixed.inset-y-0.right-0')
      || [...document.querySelectorAll('aside')].find(a => getComputedStyle(a).position === 'fixed');
    const rr = rail ? rail.getBoundingClientRect() : null;
    const out = {
      innerWidth: window.innerWidth,
      docWidth: document.documentElement.clientWidth,
      bodyPadRight: getComputedStyle(document.body).paddingRight,
      railPresent: !!rail,
      railLeft: rr ? Math.round(rr.left) : null,
      railWidth: rr ? Math.round(rr.width) : null,
      railZ: rail ? getComputedStyle(rail).zIndex : null,
      pillPresent: !!document.querySelector('button[title*="Ask Clark"]'),
      pref: localStorage.getItem("clark.rail.open"),
    };
    // Every element whose own box has visible content and is not inside the rail.
    const bad = [];
    let maxRight = 0, maxDesc = null;
    const all = document.querySelectorAll('main *, body > div *, header *, section *, nav *, p, h1, h2, table, td');
    const seen = new Set();
    for (const el of all) {
      if (rail && rail.contains(el)) continue;
      if (seen.has(el)) continue; seen.add(el);
      const b = el.getBoundingClientRect();
      if (b.width < 8 || b.height < 4) continue;
      if (b.right > maxRight) { maxRight = b.right; maxDesc = el.tagName + '.' + (el.className && el.className.toString ? el.className.toString().slice(0,60) : ''); }
      if (!rr) continue;
      // Does this element extend under the rail?
      if (b.right > rr.left + 1 && b.left < rr.right) {
        // Probe a point inside the overlap band, vertically centred on the element.
        const px = Math.min(b.right - 2, rr.left + Math.min(20, rr.width - 2));
        const py = Math.max(2, Math.min(window.innerHeight - 2, b.top + b.height / 2));
        const top = document.elementFromPoint(px, py);
        const intercepted = !!(top && rail.contains(top));
        if (intercepted) {
          bad.push({
            tag: el.tagName,
            cls: (el.className && el.className.toString ? el.className.toString() : '').slice(0, 70),
            text: (el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 60),
            right: Math.round(b.right), left: Math.round(b.left),
            top: Math.round(b.top),
          });
        }
      }
    }
    out.contentMaxRight = Math.round(maxRight);
    out.contentMaxRightEl = maxDesc;
    out.interceptedCount = bad.length;
    out.interceptedSample = bad.slice(0, 8);
    // The header number and the chip number, side by side.
    const hdr = document.body.innerText.match(/(\\S+)\\s+awaiting your decision/i);
    const chip = document.body.innerText.match(/(\\d+\\+?)\\s*\\/\\s*(\\d+)\\s+awaiting you/i);
    out.headerAwaiting = hdr ? hdr[1] : null;
    out.chipAwaiting = chip ? chip[1] : null;
    out.chipThreshold = chip ? chip[2] : null;
    out.singleSourceNote = /counter the spine serves|single source|the spine's own counter/i.test(document.body.innerText);
    return JSON.stringify(out);
  })()`;

  const r = await send("Runtime.evaluate", { expression: probe, returnByValue: true });
  const val = r.result && r.result.result && r.result.result.value;
  console.log(val || JSON.stringify(r.result));

  if (SHOT) {
    const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    require("fs").writeFileSync(SHOT, Buffer.from(shot.result.data, "base64"));
  }
  ws.close();
})();
