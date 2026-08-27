# ADVERSARY — batch blind review: P1 (ETH staking wrapper) + the NAV-hole alarm design

**Run**: `run-adversary-batch-p1-navalarm`, 2026-08-27 — the review-batching
rule's first use: two artifacts, one dispatch.

**VERDICTS: P1 SURVIVES · the NAV-hole WARN alarm design KILLED (narrow,
two grounds of one class).**

**CTO VERIFICATION NOTE (chair, at resolve)**: three mechanics re-verified
before filing — `riskmonitor.py` raises only on `new_keys = current −
active` (the saturation ground is real); `navgap.DEFAULT_LOOKBACK_HOURS =
21*24` (the "self-clear" is a calendar timer); `held: false / held_count: 0`
on ETHA live (P1 is a NEW position, not a switch). **Chair dispositions**:
P1 routes to Stan in tomorrow's post-exit PM batch AS A NEW ETH POSITION
decision (~70%/yr vol first, the 1.9%/yr wrapper edge as free improvement
on it — the adversary's re-label adopted verbatim); F1's replacement
(declared distributions, not coin-per-share, after Grayscale's 2026-08-06
amendment) is Ed's task due 09-05; the alarm redesign requirements are
recorded below and desk request b0d07e67 stays OPEN pending a design that
answers both grounds. The seat's first-ever SURVIVES-by-primary-filings is
noted for the record: both author-named attacks executed against SEC
disclosures and both returned empty.

---

## A — P1: SURVIVES, confirmed four ways, six residuals filed

**Reproduction exact** (pre −0.1065 vs filed −0.107; post +1.874 vs
+1.863; DiD +1.981 vs +1.969; monthly t +4.14 vs +4.22; 10/11 months).

**Attack 1 (issuer-disclosed ETH-per-share — no prices anywhere)**: from
matched SEC 10-Q/10-K quarter-ends, the mini/ETHA coin-per-share ratio
grew **+1.510 / +1.834 / +1.981 %/yr** across the three post-staking
quarters against a **+0.030%/yr pre-staking control**, ramping
monotonically with the staked share. F1 passes every post-staking 90-day
window. **The attack fails.**

**Attack 2 (re-rating)**: the exact decomposition (price ratio =
coin-per-share ratio × premium-spread ratio; the ETH price cancels) puts
premium drift at 10–20% of the effect, sign-flipping every quarter
(+0.920 / −0.657 / +1.072 %/yr). Not a re-rating. **The attack fails.**
(The adversary's own first attempt at this attack — filed-NAV
premium/discount — was WRONG and discarded before filing: ETHA's filed
NAV is struck at 11:59 p.m. ET; comparing it to a 4 p.m. close measures
the overnight move.)

**Two instruments the author never used, both confirming**: declared cash
distributions — ETHE's seven regular monthly pays = **1.660%/yr**, ETHB's
two full months = **1.651%/yr** — and the ETHE/ETHA differential improving
+1.73pp/yr against a 2.35pp fee headwind. Four instruments, one answer:
~1.65–2.0%/yr. Leave-one-month-out: +1.476%/yr (no single event).
Liquidity at $471: 0.0014% of the mini's $33.8M median daily volume.
Counterparty story holds: BlackRock deliberately kept ETHA spot-only and
launched ETHB as a separate product.

**Residuals (filed, not grounds)**:
- **A-R1, the important one**: Grayscale's Third A&R Trust Agreement
  (2026-08-06, 8-K Item 1.01) mandates converting staking rewards to cash
  and distributing monthly — **F1 (coin-per-share) is ORPHANED**: on the
  fee-gap-only regime it kills one of three clean windows and cannot tell
  +0.06%/yr from +1.98%/yr. The live instrument is declared distributions.
  Monitoring must run on TOTAL RETURN, not price.
- **A-R2**: the ETHB "weak leg" was zero-POWER, not weak (se ±3.55%/yr on
  116 sessions); its distributions settle it at 1.651%/yr. And ETHB is a
  staking product — never a control.
- **A-R3**: the fund holds NO ETHA — "a 10bps switch repaid in 4 weeks"
  prices a decision nobody has taken. The real decision is a new long-ETH
  position at ~70%/yr vol, with the wrapper choice as ~1.9%/yr of free
  improvement on it.
- **A-R4**: the price instrument's lag-1 autocorrelation is −0.384 — the
  monthly-over-daily argument is correct and only safe because the
  price-free instruments agree.
- **A-R5**: the ~10bps switch cost is UNVERIFIED (no bid/ask reachable —
  Yahoo 401, Grayscale behind a bot checkpoint, our quotes endpoint serves
  last price only). Absent, not zero.
- **A-R6**: Grayscale's aggregate cut is 6% of gross rewards (10-Q) —
  better than ETHB's ~82% payout; the circulating "2.75% gross / 79.63%
  staked" figures are secondary and unverified.

## B — the NAV-hole WARN alarm design: KILL

**Ground 1 — saturation.** The alarm machinery is key-based and
level-triggered (`new_keys = current − active`). The live record holds 11
holes, so one `nav_record_holes` key is present from the day the rule
ships — and **a twelfth hole emits ZERO raised events**, defeating the
design's own stated purpose ("new holes should now mean something real").
And "self-clears when the record is whole" is really **a 21-day calendar
timer** (`DEFAULT_LOOKBACK_HOURS`): demonstrated by extending the live
record with perfect strikes — lit at +20d, clear at +21d, nothing an
operator does shortens it. Root cause: one key fuses two different facts —
the LIVE trailing hole (the fund is not marking NOW; 2.53 trading-hours
old at review time; plausibly critical) and HISTORICAL between-strikes
holes (unrepairable data-quality findings; warn is right).

**Ground 2 — `undetermined` renders as silence.** The reader returns four
states; the design named two. The same 3-day hole fires WARN with the
heartbeat budget key present and reports `undetermined` — silent — with it
absent; and the alarm goes permanently silent after
`CALENDAR_LAST_DAY = 2027-12-31`. A rename in an unrelated work-layer
module would disable a control.

**Honest negatives**: every briefed false-fire mode is CLEAN (fresh fund
with one strike, restart, the 65h weekend, the Christmas half-day+holiday,
overnight — all `complete`); `unreadable` is a proper distinct state;
`completeness()` is <1ms on 76 rows (the fold is 31ms warm / ~1.3s cold);
the 300s cache is structurally unreachable from the alarm path (import
direction) and its TTL equals the monitor cadence.

**Redesign requirements, recorded for the eventual build**: (1) split
keys — the live trailing hole is its own alarm (severity worth the CEO's
re-look) and historical holes carry a COUNT or newest-hole identity in the
key so a new hole changes `new_keys`; (2) every one of the reader's four
states gets an explicit disposition, with `undetermined` as its own
visible condition, never silence; (3) the verdict arrives as an injected
input to `evaluate_alarms` (the cache is unreachable by import direction);
(4) what physically clears each key is stated, and none of them may be
"a lookback window" dressed as a repair.

---

*STATE appended and BINDS carried at the chair's resolve, same session.
Probes promoted: the XBRL companyfacts wrapper-vs-wrapper instrument, the
price = accrual × premium decomposition, the four-state alarm false-fire
grid, the saturation/self-clear timeline.*
