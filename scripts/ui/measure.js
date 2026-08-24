/**
 * MEASURE A RENDERED PAGE — the Studio's layout claims, as numbers.
 *
 * WHY THIS IS IN THE REPO AND NOT IN A SCRATCHPAD. Seven comments in
 * `src/app/clark/studio/desk/**` cite measurements to probe scripts that live
 * in a session temp directory — `scratchpad/d42_probe_width.js`,
 * `scratchpad/d42_recount.mjs`, and four more. Every one of those citations is
 * dead the moment the session ends, so a number a future reader wants to check
 * is a number they must re-invent the instrument for. A citation that cannot
 * outlive its session is a citation to nothing.
 *
 * WHAT IT IS FOR. `textContent` cannot see a CSS gap and cannot see a type
 * scale: a check written on extracted text once reported two toggles as
 * "welded" on a page whose screenshot showed a 12px gap between them. Layout
 * claims need geometry — `getBoundingClientRect` and computed styles — and
 * this is how you get them without a headless-browser test framework.
 *
 * USAGE
 *   1. Start a dev server, and a Chrome with the debugger open:
 *        chrome --headless=new --remote-debugging-port=9222 --window-size=1440,2400
 *   2. node scripts/ui/measure.js <url> <probe.js> [outPng] [width] [height]
 *
 *   The probe file is a JS EXPRESSION evaluated in the page (see
 *   `scripts/ui/probes/`), and whatever it returns is printed.
 *
 * IT ONLY READS. It navigates, waits, evaluates and screenshots; it dispatches
 * no input events, so it cannot click a control on the fund's approval path.
 *
 * NOTE ON THE WAIT: the fixed settle below is what makes an in-flight arm
 * measurable at all — point the app at a spine that never answers and shoot at
 * 9s, and you have the loading state on record. It is also the trap: on a
 * COLD route the same 9s catches Next still compiling, and the page you
 * measure is the loading state whatever the spine is doing. Navigate twice.
 */
const path = require("path");
const fs = require("fs");
const WebSocket = require("ws");

const [, , url, probeFile, outPng, wArg, hArg] = process.argv;
const W = Number(wArg || 1440);
const H = Number(hArg || 2400);
const SETTLE_MS = Number(process.env.KT_SETTLE_MS || 9000);

if (!url || !probeFile) {
  console.error("usage: node scripts/ui/measure.js <url> <probe.js> [outPng] [w] [h]");
  process.exit(2);
}

function rpc(ws, id, method, params) {
  return new Promise((resolve, reject) => {
    const onMsg = (raw) => {
      const m = JSON.parse(raw);
      if (m.id !== id) return;
      ws.off("message", onMsg);
      m.error ? reject(new Error(`${method}: ${JSON.stringify(m.error)}`))
        : resolve(m.result);
    };
    ws.on("message", onMsg);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

(async () => {
  const list = await (await fetch("http://127.0.0.1:9222/json/list")).json();
  const page = list.find((t) => t.type === "page");
  if (!page) throw new Error("no page target on 9222 — is chrome running with "
    + "--remote-debugging-port=9222?");
  const ws = new WebSocket(page.webSocketDebuggerUrl,
    { maxPayload: 256 * 1024 * 1024 });
  await new Promise((r) => ws.on("open", r));
  let id = 1;
  await rpc(ws, id++, "Page.enable", {});
  await rpc(ws, id++, "Runtime.enable", {});
  await rpc(ws, id++, "Emulation.setDeviceMetricsOverride",
    { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  await rpc(ws, id++, "Page.navigate", { url });
  await new Promise((r) => setTimeout(r, SETTLE_MS));

  const expr = fs.readFileSync(probeFile, "utf8");
  const res = await rpc(ws, id++, "Runtime.evaluate",
    { expression: expr, returnByValue: true, awaitPromise: true });
  if (res.exceptionDetails) {
    console.log("PROBE EXCEPTION:",
      JSON.stringify(res.exceptionDetails).slice(0, 1500));
    process.exitCode = 1;
  } else {
    console.log(typeof res.result.value === "string"
      ? res.result.value : JSON.stringify(res.result.value, null, 1));
  }

  if (outPng) {
    const shot = await rpc(ws, id++, "Page.captureScreenshot",
      { format: "png", captureBeyondViewport: true });
    // An ABSOLUTE path: Chrome's own --screenshot flag fails with Access
    // Denied on a relative one, and this keeps the two paths interchangeable.
    fs.writeFileSync(path.resolve(outPng), Buffer.from(shot.data, "base64"));
    console.log(`WROTE ${path.resolve(outPng)}`);
  }
  ws.close();
})().catch((e) => { console.error("FAILED", e.message); process.exit(1); });
