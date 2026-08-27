import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import {
  FLAT_RANGE_FRACTION, MIN_POINTS, SPARK_H, SPARK_PAD, SPARK_W,
  type SparkPoint, sparkChange, sparkline,
} from "./sparkline.ts";

const LIVE = JSON.parse(readFileSync(
  fileURLToPath(new URL("./__fixtures__/liveNav.json", import.meta.url)),
  "utf8")) as { history: SparkPoint[] };

/**
 * NAV AS A LINE — and the one mistake that would matter more than all the
 * others: drawing a losing fund as a winning one.
 */

test("the fund's OWN 76 strikes draw a line", () => {
  const s = sparkline(LIVE.history);
  assert.equal(s.state, "line");
  assert.equal(s.offered, 76);
  assert.equal(s.drawn, 76, "every live strike carries a readable figure");
  assert.ok(s.path!.startsWith("M"));
  assert.equal(s.path!.split("L").length, 76, "one L per point after the M");
  assert.equal(s.fromTs, LIVE.history[0].ts);
  assert.equal(s.toTs, LIVE.history[75].ts);
});

test("SVG Y GROWS DOWNWARD — a rising series must draw UPWARD", () => {
  /* The single worst thing this function could do is invert the axis, which
   * would render a losing fund as a winning one and look completely normal.
   * Asserted by construction: the HIGHEST value gets the SMALLEST y. */
  const rising = sparkline([
    { ts: "a", total_nav_usd: 100 },
    { ts: "b", total_nav_usd: 150 },
    { ts: "c", total_nav_usd: 200 },
  ]);
  const ys = rising.path!.match(/[ML]([\d.]+) ([\d.]+)/g)!
    .map((m) => Number(m.split(" ")[1]));
  assert.ok(ys[0] > ys[1] && ys[1] > ys[2],
            `a rising series must have falling y: ${ys}`);
  assert.equal(rising.last!.y, ys[2]);

  const falling = sparkline([
    { ts: "a", total_nav_usd: 200 },
    { ts: "b", total_nav_usd: 150 },
    { ts: "c", total_nav_usd: 100 },
  ]);
  const fys = falling.path!.match(/[ML]([\d.]+) ([\d.]+)/g)!
    .map((m) => Number(m.split(" ")[1]));
  assert.ok(fys[0] < fys[1] && fys[1] < fys[2],
            `a falling series must have rising y: ${fys}`);
});

test("the line stays inside its viewBox on both axes", () => {
  const s = sparkline(LIVE.history);
  const pts = s.path!.match(/[ML]([\d.]+) ([\d.]+)/g)!
    .map((m) => m.slice(1).split(" ").map(Number));
  for (const [x, y] of pts) {
    assert.ok(x >= 0 && x <= SPARK_W, `x ${x} outside 0..${SPARK_W}`);
    assert.ok(y >= 0 && y <= SPARK_H, `y ${y} outside 0..${SPARK_H}`);
    // The padding keeps a 1.5-weight stroke from being clipped at the edges.
    assert.ok(y >= SPARK_PAD - 1e-9 && y <= SPARK_H - SPARK_PAD + 1e-9,
              `y ${y} inside the stroke pad`);
  }
  assert.equal(pts[0][0], SPARK_PAD, "the first point sits on the left pad");
  assert.ok(Math.abs(pts[pts.length - 1][0] - (SPARK_W - SPARK_PAD)) < 1e-9,
            "and the last on the right pad");
});

test("the last point is where the emphasis dot goes", () => {
  const s = sparkline(LIVE.history);
  const last = s.path!.split(/[ML]/).pop()!.trim().split(" ").map(Number);
  assert.ok(Math.abs(s.last!.x - last[0]) < 0.01);
  assert.ok(Math.abs(s.last!.y - last[1]) < 0.01);
  assert.equal(s.lastUsd, LIVE.history[75].total_nav_usd);
});

/* ------------------------------------------------ the four states --------- */

test("UNREADABLE and NO-STRIKES-YET are different sentences", () => {
  const dead = sparkline(null);
  assert.equal(dead.state, "unreadable");
  assert.equal(dead.path, null);
  assert.equal(dead.offered, 0);
  assert.match(dead.note, /UNKNOWN/);
  assert.match(dead.note, /not flat/);

  const young = sparkline([]);
  assert.equal(young.state, "too_few");
  assert.match(young.note, /struck no NAV yet/);
  assert.notEqual(dead.note, young.note);
  assert.notEqual(dead.state, young.state);
});

test("the MIN_POINTS boundary is probed AT the boundary", () => {
  const pt = (v: number): SparkPoint => ({ ts: "t", total_nav_usd: v });
  const two = sparkline([pt(1), pt(2)]);
  assert.equal(two.state, "too_few");
  assert.match(two.note, /Two points is a line, not a track record/);
  const three = sparkline([pt(1), pt(2), pt(3)]);
  assert.equal(three.state, "line");
  assert.equal(MIN_POINTS, 3);
});

test("a DEAD FLAT series says so rather than drawing noise as signal", () => {
  /* Stretched to the box, $0.30 of drift on a $2,000 fund draws as a
   * mountain range. The state is the honest answer. */
  const flat = sparkline([
    { ts: "a", total_nav_usd: 2000.00 },
    { ts: "b", total_nav_usd: 2000.10 },
    { ts: "c", total_nav_usd: 2000.30 },
  ]);
  assert.equal(flat.state, "flat");
  assert.equal(flat.path, null);
  assert.match(flat.note, /flat at this scale/);
  // ...and the figures survive, so a caller can still print the range.
  assert.equal(flat.lowUsd, 2000);
  assert.equal(flat.highUsd, 2000.3);

  // Just past the threshold it draws. A flat test that never draws and one
  // that always draws are the same non-instrument.
  const moving = sparkline([
    { ts: "a", total_nav_usd: 2000 },
    { ts: "b", total_nav_usd: 2001 },
    { ts: "c", total_nav_usd: 2003 },
  ]);
  assert.equal(moving.state, "line");
  assert.equal(FLAT_RANGE_FRACTION, 0.0005);
});

test("a PERFECTLY constant series is flat, never a divide-by-zero", () => {
  const s = sparkline([{ total_nav_usd: 5 }, { total_nav_usd: 5 },
                       { total_nav_usd: 5 }]);
  assert.equal(s.state, "flat");
  assert.equal(s.path, null);
  assert.ok(!Number.isNaN(s.lowUsd!));
});

test("unreadable POINTS are dropped and the loss is STATED, not swallowed", () => {
  /* Two numbers, never one: a series that lost half its rows must not report
   * the survivors as the whole. */
  const s = sparkline([
    { ts: "a", total_nav_usd: 100 },
    { ts: "b", total_nav_usd: null },
    { ts: "c", total_nav_usd: 150 },
    { ts: "d", total_nav_usd: NaN },
    { ts: "e", total_nav_usd: 200 },
  ]);
  assert.equal(s.state, "line");
  assert.equal(s.offered, 5);
  assert.equal(s.drawn, 3);
  assert.match(s.note, /2 strike\(s\) carried no readable figure/);
  assert.match(s.note, /NOT drawn/);
});

test("a clean series says nothing about drops — zero is quiet", () => {
  const s = sparkline([{ total_nav_usd: 1 }, { total_nav_usd: 2 },
                       { total_nav_usd: 3 }]);
  assert.doesNotMatch(s.note, /NOT drawn/);
  assert.equal(s.offered, s.drawn);
});

/* --------------------------------------------------------- the change ----- */

test("the change is first-to-last and absent when it cannot be computed", () => {
  const s = sparkline(LIVE.history);
  const c = sparkChange(s)!;
  const expected = (LIVE.history[75].total_nav_usd! - LIVE.history[0].total_nav_usd!)
    / LIVE.history[0].total_nav_usd!;
  assert.ok(Math.abs(c - expected) < 1e-12);

  assert.equal(sparkChange(sparkline(null)), null);
  assert.equal(sparkChange(sparkline([{ total_nav_usd: 0 },
                                      { total_nav_usd: 0 },
                                      { total_nav_usd: 5 }])), null,
               "a zero base has no percentage change");
});

test("the shape constants are the ones the geometry uses", () => {
  // Proven by MOVING them through the arithmetic rather than by asserting
  // their literals, which a hardcoded duplicate would satisfy.
  const s = sparkline([{ total_nav_usd: 0 }, { total_nav_usd: 5 },
                       { total_nav_usd: 10 }]);
  const pts = s.path!.match(/[ML]([\d.]+) ([\d.]+)/g)!
    .map((m) => m.slice(1).split(" ").map(Number));
  assert.equal(pts[0][1], SPARK_H - SPARK_PAD, "the low sits on the bottom pad");
  assert.equal(pts[2][1], SPARK_PAD, "the high sits on the top pad");
  assert.equal(pts[1][0], SPARK_W / 2, "the middle point is centred");
});
