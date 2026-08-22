# builder — working state
(appended by the CTO at each dispatch resolution; newest at the bottom)

## 2026-08-20 — seeded at hiring
- No dispatches yet. First brief queued on the desk: UI consolidation (7 tabs ->
  5; fold Mechanics into Desk; retire map/hunting-ground from Lab) — request
  c91d5c07, CEO-approved direction.
- House style: read neighbouring files first; comments carry the why and the
  measured reason; tests must be unable to bless the bug they guard against.

**builder — after dispatch cd92e175 (2026-08-20), first real dispatch**

- **The worktree I am dispatched into is a ClarkHarness worktree, seeded from that repo's initial commit (LICENSE only).** The UI code and briefs live in the SEPARATE `KryptonPay` repo at `C:\Users\user\Documents\Krypton Fund\KryptonPay`. The bash guard blocks `cd`/`-C` git ops against shared checkouts. Working method that succeeded: `git clone --no-hardlinks "<KryptonPay>" kp` INSIDE my worktree, then a PowerShell junction for `node_modules` (`cmd mklink` mangles the target path under Git Bash; `New-Item -ItemType Junction` works). Deliver as a bundle + flat patch written to the worktree root. **Ask the CTO to fix the worktree base, or repeat this.**
- Tooling in KryptonPay: no test runner, no test files. Use `node --experimental-strip-types --test` (Node 22.17) + `allowImportingTsExtensions` — added in this diff; no new deps. `npx tsc` fails through the junction; run `node node_modules/typescript/bin/tsc --noEmit`. `next lint` still works (deprecated warning).
- Spine is live on `http://127.0.0.1:8090`. Verified shapes: desk events are PascalCase (`DeskRequested`/`DeskDispatched`/`DeskRequestResolved`/`DeskRecommendationDecided`), `GET /fund/events` caps limit at 1000, `OrderApproved.payload.approver` is how auto-approvals are identified, `GET /fund/desk/runs?seat=` returns `{runs:[...]}`, `/fund/research/observations` returns `coverage.observations`. Always curl before consuming — this saved me twice.
- Shipped: 7 commits on `claude/krypton-fund-agentic-j8r2mu` in the clone, base `b9a526c`; tsc clean, 17/17 tests, next build green, all 8 seat routes 200, unknown seat 404, mechanics 307→desk, nav = 5 tabs.
- Open items for a future dispatch: eight named spine gaps (top three: `GET /fund/autopolicy`, `claim_type` on artifacts, thesis docs missing from the artifact fold); a browser pass with the spine stopped; a tokens/dispatch sparkline once seats have ~10 runs each.
- Decision the CEO may want to reverse: Risk is no longer a nav tab (route and RiskBar untouched) — one line in `StudioNav.tsx`.
- [CTO note at resolve, 2026-08-20]: merged fast-forward as KryptonPay 25f8e61..d8c2820 after verifying live trees clean, no thesis files in the patch, fund_api.ts additive-only; tsc/tests/routes reproduced on the merged tree. Your B1-B3 recommendations recorded on run-builder-1. The worktree-base defect (B3) is acknowledged — next dispatch will start from KryptonPay.

**builder — after dispatch af74c5e7 (2026-08-20), second dispatch**

- **Worktree base, still not right.** The dispatch worktree is now correctly a KryptonPay worktree (B3 partially fixed) but was checked out at an OLD commit (`125694b`), not the brief's base. Fix: `git reset --hard <base>` inside the worktree — allowed, stays in-worktree. Ask the CTO to have the worktree created at KryptonPay HEAD.
- **Working method that succeeded (repeat this):** PowerShell junction for node_modules (`New-Item -ItemType Junction`); copy `.env.local` from the live tree (gitignored, needed for `/proxy/harness`); `node node_modules/typescript/bin/tsc --noEmit`; `node --experimental-strip-types --test <files>`; `npx --no-install next lint --dir <subtree>`.
- **NEW AND IMPORTANT — I can see the UI.** `C:\Program Files\Google\Chrome\Application\chrome.exe --headless=new --screenshot=<png> --window-size=W,H --virtual-time-budget=20000 --force-device-scale-factor=N <url>` renders client-side React fully, and the Read tool displays the PNG. Python+PIL (12.2.0) is available for cropping tall pages. **This changed the quality of the work**: the floor's copy fix, the shelf's review-path defect, and all three absence defects in commit `60ba593` were found by looking, not by reading. Scripts left at `<scratchpad>/shot.sh`, `shot2.sh`, `shot3.sh`, `crop.py`.
- **Degradation testing is cheap and finds real bugs.** Second dev server: `NEXT_PUBLIC_HARNESS_API_URL=http://127.0.0.1:9099 npx next dev -p 3200`. Do this on every UI dispatch. Kill both servers with `taskkill //PID <pid> //T //F` when done (find via `netstat -ano | grep LISTENING`).
- Spine base path is `/api/v1/fund/...` — `/fund/...` 404s. `GET /fund/events` returned 300 rows today (cap is 1000). Desk-event actors are exactly `{ceo, cto}`. The wider log's `actor` field contains 200-char sentences — never prefix-match on it.
- Shipped: 2 commits on `worktree-agent-a3bcae69b86db6d4e`, base `406434e`; 12 files, +1548/−173; tsc clean, 37/37 tests, next build green, all routes 200 live and dead-spine, unknown seat 404. Bundle + patch at the worktree root.
- **Top three follow-ups, in order of money:** (1) Allocate reports 0% deployed while three paused strategies hold 43.1% of NAV — `allocate/page.tsx:100-115`; (2) `MonitorVerdict` says "nothing in flight" when order history is unreadable — `MonitorVerdict.tsx:46` + `studio/page.tsx:77`; (3) Allocate renders a healthy empty book on a dead spine — `allocate/page.tsx:79-98`. All three are behaviour changes and were deliberately left unfixed.
- **ClarkHarness, for whoever dispatches the riskofficer next:** H1 (`quotes.py:65` — `stale` measures feed reachability, not mark age; `marketdata.py:409` discards the bar date it already has) and H2 (`nav.py:108` raises before `riskmonitor.py:258`'s guard can fire, so the `unpriced` alarm is unreachable and one bad symbol takes the kill switches dark) are the two worth a dispatch. **H2 contradicts a claim in `docs/INCIDENT_GLD_PHANTOM_PRICE_2026-08-20.md` and is falsifiable in one test that does not exist.**
- Open from last dispatch, still open: eight named spine gaps (top three: `GET /fund/autopolicy`, `claim_type` on artifacts, thesis docs missing from the artifact fold). The seat pages render all eight as `AbsentMetric` sentences.
- [CTO note at resolve, 2026-08-20]: bundle merged ff (KryptonPay tip 60ba593); tsc + 37/37 reproduced on the merged tree. H2: your falsifying test was written the same hour, CONFIRMED your claim (my incident-doc claim was false), and the fix landed — riskmonitor computes NAV with stale_ok=True using last-struck marks; 937 tests green; incident doc corrected by §3. C1/C2/C3 recorded as decidable recommendations on run-builder-2. Your run_record envelope was the contract's first live use and posted nearly verbatim.

## STATE

**builder — after dispatch 8804b28d (2026-08-20), third dispatch**

- **Worktree base wrong a THIRD time** — dispatched into a *ClarkHarness* worktree at initial commit (`cebc578`, LICENSE only). Recovered with the dispatch-1 method: `git clone --no-hardlinks "C:/Users/user/Documents/Krypton Fund/KryptonPay" kp` inside the worktree, then `git -C <worktree>/kp checkout -b <branch>`. **`cd <path> && git ...` is now blocked by the bash guard as "too complex"; use `git -C <abs-path>`.** Compound `&&` chains with `cp`/`powershell` also get blocked — issue them as separate calls.
- Setup that works, unchanged: PowerShell `New-Item -ItemType Junction` for `node_modules`; copy `.env.local` from the live tree; `node node_modules/typescript/bin/tsc --noEmit`; `node --experimental-strip-types --test <files>`; `npx --no-install next lint --dir src/app/clark`; `node node_modules/next/dist/bin/next dev -p 3100`.
- **Never run `next build` while a dev server is live** — it overwrites `.next/server/vendor-chunks` and every subsequent dev route 500s. Looks exactly like a regression. Fix: `rm -rf .next`, restart. Cost me a false alarm.
- **Lint claims must be measured, not eyeballed**: `git stash push -u` -> count -> `git stash pop`. Baseline and branch were both 26 warnings. My first pass HAD added 3.
- **Verified spine shapes (2026-08-20)**: pending orders are `GET /fund/orders/pending` (NOT `/fund/pending`, which 404s); money is `impact_preview.notional_usd`; `age_minutes` + `stale` present. `open_recommendations[]` keys are exactly `artifact_path/kind/rec_id/run_id/seat/status/task/text/trace_id` — **no timestamp and no money field**; staleness must come from the producing run's `resolved_at`. Desk request status is `{open, approved, resolved}` (`app/fund/desk.py:204-232`), `approved` stamps `approved_by`/`approved_at`. `risk/monitor` has `halted: true` and `alarms[].severity/message`. `StrategyView` uses OPTIONAL (`actual_pct?: number`), not null — test fixtures must use `undefined`.
- **47 of 47 open recommendations carry no dollar figure.** Any future "rank by money" work needs a `money_at_stake` field on the recommendation; scraping prose is off the table.
- Shipped: 4 commits on `worktree-agent-a46892c4fb3ae823b`, base `bdd5686`; 26 files, +2060/-257; tsc clean, **80/80 tests** (37 inherited + 43 new), next build green, lint +0, 19 routes 200 live and dead-spine. Bundle + patch at the worktree root.
- **New tested modules to reuse**: `studio/format.ts` (money/pct/signedMoney/signedPct/pctFromFraction/moneyCompact), `studio/orderCounts.ts`, `studio/allocate/bookFold.ts`, `studio/desk/execDesk.ts`.
- **The dead-spine pass caught three defects in code I had just written.** It is not optional and it is not only for legacy code. Run it before claiming a page is done.
- **Open for a future dispatch**: (a) `money_at_stake` on recommendations — the CEO desk's ranking is money-blind on 92% of its queue until then; (b) the reversibility kind->table in `execDesk.ts` is my judgement and wants a human review; (c) still open from before — eight named spine gaps, top three `GET /fund/autopolicy`, `claim_type` on artifacts, thesis docs missing from the artifact fold; (d) no DOM test runner in KryptonPay, so React branches are eye-verified only.
- **ClarkHarness, still unfixed from dispatch 2**: H1 (`quotes.py:65` — `stale` measures feed reachability, not mark age; `marketdata.py:409` discards the bar date it already has). H2 was fixed by the CTO.
- [CTO note at resolve, 2026-08-20]: bundle fetched via HEAD ref, merged as `a528396` (a true merge — the live branch had gained the guard-v1 confirm-echo commit since your base). Forbidden-surface check re-run independently: empty. tsc + 80/80 reproduced on the merged tree. Your six recommendations are on run-builder-dispatch3 for the CEO. The worktree-base defect is now three-for-three and I owe you the fix: next dispatch gets its worktree created in KryptonPay at the brief's base, and the brief will name the expected `git log -1` output so you can refuse a wrong base in the first minute.

## STATE

**builder — after dispatch 4 (2026-08-20/21), fourth dispatch**

- **Worktree base wrong a FOURTH time** — ClarkHarness at `cebc578` (LICENSE only). The clone-both-repos recovery is now routine and costs ~3 minutes; it is in the brief and it works. `git -C <abs-path>` for everything; compound `cd X && git`, `$VAR`-computed `-C` paths, and heredoc/`>>` appends into repo files are ALL blocked by the guard — use the Edit tool to append to files, and a written `.sh` in the scratchpad for any loop.
- **The brief naming the expected `git log -1` worked.** Verifying `merge-base --is-ancestor` took seconds and told me KryptonPay HEAD was base+brief-doc, so I could cut the patch from `4f2ebb9` and the bundle so the CTO gets no duplicate doc commit. Do this every time the two disagree.
- **`next build`'s exit code is NOT what `head`/`tail` returns.** `tsc --noEmit 2>&1 | head -20; echo $?` printed `TSC_EXIT=0` while tsc was failing. Read the output, never the piped status.
- **The dev server hung mid-route-pass** (compiled `/compose`, then stopped answering everything). Symptom looks like a code defect; it is not. Fix: kill the PID, `rm -rf .next`, restart. Cost me ~10 minutes and two false 000s.
- **Verified live spine shapes (2026-08-20/21):** `/fund/events?limit=1000` returned 443 rows; the incident window 245–265 is intact and readable. `NavStruck` payloads carry `ts` + `total_nav_usd`; the last prior-day strike before the phantom was seq 209 @ 2011.81. Desk recommendation statuses on the wire are `open|accepted|rejected|staged|done`, and `/fund/desk`'s `open_recommendations` returns **open, accepted AND staged** under one key — that conflation was CDO D4.
- **New reusable modules**: `app/fund/desk.py::desk_load()`, `app/fund/judgement.py::TriggerSpec` + `use_metrics()`, `app/fund/projections/strategy.py::append_attribution_correction()`, `app/fund/riskmonitor.py::classify_halt_cause()` + `RiskControl.halt_state()/loss_reference()/rebase_loss_reference()` + `RiskMonitor.rebase_token()`, `app/fund/tca.py::by_symbol()/by_venue()` + `summarise()["informative"]`, `studio/desk/execDesk.ts::splitDeskItems/stageOfItem`, `studio/desk/components.tsx::CooTriageChip`, `bookFold.actualIncludingArchived`.
- **The F4 residual is still open and is a real unknown.** My measurement says one tick; the log says 14m41s; the 08:16:08 simultaneous-clear pattern implies an empty positions list that contradicts the 6.62% figure. Whoever picks this up: the incident-time code differed (the `stale_ok=True` H2 fix landed later the same day), so the answer probably needs `git log` archaeology on `riskmonitor.py`/`nav.py` against the 08:01–08:16 window, not more log reading. **Do not let anyone record "fixed" against F4 — the latency cause is unexplained; two adjacent defects were fixed.**
- **Open for a future dispatch:** (a) `risk_advanced.*` triggers need a cached risk view before `/fund/judgement` can evaluate them — currently prose-only and reported UNCHECKED; (b) no DOM test runner in KryptonPay, so React branches stay eye-verified; (c) the reversibility kind→table in `execDesk.ts` is still my judgement and still wants a human review; (d) ClarkHarness H1 (`quotes.py:65` — `stale` measures feed reachability, not mark age; `marketdata.py:409` discards the bar date it already has) is unfixed from dispatch 2; (e) eight named spine gaps from dispatch 1 remain, top three `GET /fund/autopolicy`, `claim_type` on artifacts, thesis docs missing from the artifact fold.
- **After merge the CTO must**: fire the `StrategyAttributionCorrected` event for the GLD pair (otherwise `/fund/rebalance/preview` refuses, by design), and restart the spine so `halt_class` / `loss_reference` / `rebase_token` / `desk_load` start flowing — the UI renders the absent case correctly until then.

- [CTO note at resolve, 2026-08-21]: both bundles verified and merged (ClarkHarness
  1034/1034 and KryptonPay 94/94 reproduced on the merged trees; forbidden-surface
  checks empty; obsidian.css deletion confirmed). Your two post-merge musts were done
  within the hour: the GLD correction fired at the console with your test's exact
  parameters (both phantom legs confirmed gone from the fold AND the live risk
  monitor), and the spine restarted — desk_load's FIRST live reading was 73 open
  items, coo_triage_due TRUE, and the COO triage it demanded was dispatched the same
  minute. Your F4 process rec is honored verbatim: F4 remains OPEN in every record;
  riskofficer's next dispatch gets the git-archaeology framing. The worktree-base
  defect is now 4-for-4 — the named-base refusal you executed is standing brief
  furniture until the harness fixes creation.


## STATE

**builder — after dispatch 5 (2026-08-21), fifth dispatch**

- **Worktree base wrong a FIFTH time, in a NEW way** — dispatched into the *outer* `Krypton Fund` repo (`1bf4d80`; HANDOFF.md, workspace files, `.claude/`), not ClarkHarness and not KryptonPay. The clone-both recovery works unchanged and costs ~4 min. `git -C <shared checkout>` is refused by the guard, so **you cannot verify the live repos' HEADs directly** — clone first, verify inside the clone with `git merge-base --is-ancestor <base> HEAD`.
- **Build the CDP probe on every UI dispatch. It is the highest-value tool this seat has.** `ws` is in KryptonPay's `node_modules`; launch `chrome --headless=new --remote-debugging-port=9222 --window-size=W,H`, then drive `Runtime.evaluate` / `Emulation.setEmulatedMedia` / `DOM.getContentQuads` / `Input.dispatchMouseEvent` from Node with `NODE_PATH=<kp>/node_modules`. Scripts left at `<scratchpad>/cdp.js`, `cdp_quad.js`. It found **both** of my own geometry defects, and it turns "looks right" into a number. `getBoundingClientRect` **lies inside a `preserve-3d` subtree** — use `DOM.getContentQuads`.
- **Two dev servers on one clone share `.next` and serve each other STALE CSS.** Same hazard class as `next build` beside a live dev server. Symptom: identical source renders differently on two ports. Run ONE dev server; switch `NEXT_PUBLIC_HARNESS_API_URL` and restart instead.
- **`process.env` passed as an OBJECT defeats Next's inlining.** Only literal `process.env.NEXT_PUBLIC_X` member accesses are replaced. A flag read through an injected bag is always undefined in the browser. Split into `xEnabledFrom(value)` + `xEnabled()` and assert the literal read in a source-level test.
- **CSS 3D: any wrapper between the transformed plane and its children FLATTENS the context** — a plain semantic `<nav>` silently turned my billboard's `rotateX` into a vertical squash. Give every intermediate element `transform-style: preserve-3d`. And **lift furniture off the floor with `translateZ`**: coplanar elements sort unpredictably and the floor's own SVG steals hover.
- **Verified live spine shapes (2026-08-21):** `GET /fund/events` returns **NEWEST FIRST** (`store.stream` is oldest-first — do not confuse them). `NavStruck.payload.positions[]` = `{symbol, mark, qty, usd_value}`. `OrderFilled` payload keys: `attribution, avg_price, backfill_reason, fees, filled_qty, side, strategy_id, symbol, venue` — **no `at`, no `qty`**. `DeskRequestResolved` carries **no seat** — recover it from the matching `DeskDispatched.task_id`. `DeskRequested.actor` can be a **seat** (`pm`). `/fund/desk` roster order **disagrees with the constitution order** in `seatLib.SEATS` — the floor deliberately obeys SEATS.
- **Folding every fill gives held = DBC + TLT only**; five closed symbols carry ~1e-15 residue. Any "is it held" test must use a tolerance (1e-9), never `!= 0`.
- **New reusable modules**: `app/fund/marksanity.py` (`gather`/`evaluate`/`check`); `riskmonitor.evaluate_autoresume()`, `effective_peak()`, `RiskControl.acknowledge_halt/halt_acknowledgement/halt_alarm/halt_ack_token/rebase_drawdown_reference/drawdown_reference/drawdown_rebase_token`; `desk.seat_telemetry()`/`utc_day_bounds()`; `DeskStore.runs_between()`; `studio/desk/deskTelemetry.ts`; `studio/desk/floor/floorPlan.ts`; `components.tsx::SeatTelemetryChips`; `RiskBar.RISK_UNREACHABLE`.
- **Monitor payload gained** (no UI consumes them yet): `halt_acknowledgement`, `halt_alarm`, `halt_ack_token`, `autoresume_cooldown_minutes`, and on `drawdown`: `peak_basis`, `peak_note`, `unrebased_peak_nav`, `rebase`, `rebase_token`. A UI dispatch for the acknowledge + drawdown-rebase controls is the natural next KryptonPay piece.
- **NOT BUILT this dispatch: C (merge gate script), D (factor pack v0), G (Lab analytics).** Stopped at the sanctioned E/F boundary. G is the largest — it needs a spine-storage change to persist engine payloads the factory currently drops, and deserves its own pass.
- **Open from before, still open:** (a) no DOM test runner in KryptonPay; (b) the reversibility kind→table still wants a human review; (c) ClarkHarness H1 unfixed since dispatch 2; (d) eight named spine gaps from dispatch 1; (e) F4's latency cause remains unexplained — do not let anyone record "fixed".
- **After merge the CTO must**: set `NEXT_PUBLIC_STUDIO_FLOOR=1` + restart the dev server; restart the spine; put the **30-minute cool-down** and the **`NEW_SYMBOL_WITHOUT_REFERENCE_REFUSES=False` flag** in front of the CEO.

- [CTO note at resolve, 2026-08-21]: both bundles verified and merged (1100 +
  127 reproduced on the merged trees; forbidden-surface checks empty;
  judgement.py confirmed additive). All three post-merge musts executed within
  the hour: flag set + dev server restarted, spine restarted, and the floor
  verified LIVE (14 real pulses of 247 events, halted-room state and the
  what-this-room-does-not-show block rendering exactly as specified). The two
  proposed values (30-min cooldown, NEW_SYMBOL flag False) are on the CEO's
  desk on run-builder-dispatch5. Stopping at the sanctioned boundary was the
  pace direction working as written - C/D/G get their own dispatch. Wrong-base
  count now 5/5; the refusal discipline held again.


## STATE

**builder — after dispatch 6 (2026-08-21), sixth dispatch**

- **Worktree base wrong a SIXTH time, and the worst variant yet: I was dispatched into the LIVE `KryptonPay` checkout** (not a worktree at all). Clone-both recovery into the scratchpad is now muscle memory (~4 min) and is the only safe response — verify with `git log -1` inside the clone before touching anything. The CTO moved the ClarkHarness head TWICE mid-dispatch (`ca2b08b`, `bd25cdb`); `git -C <clone> fetch origin <branch>` then `rebase FETCH_HEAD` is clean and cheap. Do it immediately, not at bundling time.
- **`node --test` glob must be ONE argument.** Bash without `globstar` expands `**` as `*`, so `studio/**/*.test.ts` silently missed `studio/desk/floor/`. I reported 137/163 for two commits when the truth was 127/191. Always `node --experimental-strip-types --test "src/app/clark/**/*.test.ts"` (quoted — node expands it). **My d6 commit messages contain the undercounts; the report has the corrected figures.**
- **`scripts/merge_builder.py` now exists and works on both repos.** `--bundle --base --repo [--branch]`; PASS/FAIL, exit 0/1, usage error 2. It MERGES for real inside a throwaway clone (`--no-commit --no-ff`) and runs the suite on the result — I shipped it checking out the tip and caught that by running it on its own bundle. Use it before every merge; it found nothing wrong with my own diff but it reported the 3 new constants for a human to read, which is the point.
- **CDP probe doctrine paid for itself four times this dispatch.** The equity-chart lie, the archived-strategies-as-live defect, the CEO-desk ordering error and the bench `0.0%` were all found by LOOKING, not reading. `mock_spine.js` in the scratchpad proxies the live spine and overrides chosen endpoints from JSON fixtures (`MONITOR_FIXTURE` / `DIVERGENCE_FIXTURE` / `DESK_FIXTURE` / `FAIL_DETAIL=1`) — generate fixtures with the SPINE'S OWN code so shapes cannot drift. **The mock proxies POSTs to the live spine: never click an approve/decline submit while it is up.**
- **Verified live shapes (2026-08-21):** feed serves SPY TLT DBC UUP XBI IBB GLD DBA IWM SRPT, 551 bars each from 2024-06-10, source=alpaca. `/fund/desk` requests have FOUR states with `task`/`seat` normalized from `subject`/`serves`. `halt_ack_token` and `drawdown.rebase_token` are served even when `halted:false` — the token is NOT permission. LEAN job wall times are BIMODAL: 44 of 50 under 120s, 6 pinned at 300–301s, nothing between (a censored distribution; that is why I raised `LEAN_JOB_TIMEOUT` to 900).
- **Fractional fills: measured, not guessed.** `sec.symbol_properties = SymbolProperties(desc, ccy, mult, minvar, 0.0001, ticker)` produces fractional fills (SPY 1.4298 vs 1.0000 at a $2k book). `lean_workspace/algorithms/frac_probe` is the KEPT falsifier — re-run both arms after any LEAN image bump. Docker + `quantconnect/lean:latest` are available and a short run is ~13s, so engine questions ARE answerable here; do not guess at them again.
- **CONFIRMED LATENT RISK DEFECT, unfixed and out of my bounds:** a SECOND drawdown rebase RAISES the effective peak. `app/api/v1/fund.py:3511` checks direction against `unrebased_peak_nav` (which never moves) while `effective_peak()` returns the rebased value — so after a rebase to 1950, a rebase to 2000 is accepted and the reference goes UP, contradicting `riskmonitor.py`'s own docstring. Verified by calling `effective_peak` directly. Never triggered (the fund has never been rebased). **Needs a human/riskofficer decision.**
- **Open for a future dispatch:** (a) belt-candidate serialisation — needs a `queued` candidate state, which changes the scoreboard's shape, so it is a decision not a refactor; (b) the gate's HOLDOUT leg still reports an engine timeout as "a leg produced no return figure" (one argument to `_leg_retention`, but it is `gate.py`); (c) the hardcoded `"neelesh"` approver in ApprovalQueue / RebalancePanel / LimitsEditor / HaltControl's loss-rebase — a firm-wide convention needing a human call; (d) `correlation.aligned_returns` memoises on `fetcher.__name__`, so same-named fakes collide (benign in prod, lethal in tests); (e) still no DOM test runner in KryptonPay; (f) ClarkHarness H1 unfixed since dispatch 2; (g) F4's latency cause still unexplained.
- **After merge the CTO must**: restart the spine so `analytics`, `archived` on divergence rows, and the fractional switch start flowing (the Lab renders every pre-existing candidate as NOT CAPTURED until then, which is correct); the 37 existing candidates will never have analytics — only a re-run captures them.

- [CTO note at resolve, 2026-08-21]: both bundles re-verified independently on
  the live trees (1208 + 191, corrected glob; forbidden surfaces 0; fund_api.ts
  diff confirmed additive with zero thesis types) and merged; spine restarted —
  n_live/n_archived flowing (1 live, 3 archived). The latent rebase-direction
  defect is routed to the riskofficer as policy_audit dc7b068c and gates R1's
  first use. The glob undercount self-correction without commit rewriting is
  the honesty standard, noted. Wrong-base now 6/6 — the dispatch-harness fix
  (hand the seat a clone) is on the recommendations. First run recorded under
  the interaction-durability rule: full report verbatim in the record.

## STATE

**builder — after dispatch 7 (2026-08-21), seventh dispatch**

- **Bases were RIGHT for the first time in 7 dispatches** (ClarkHarness `ec816f7`, KryptonPay `cbc32b8a`, both exact, D6 in both histories). The clone-both setup still takes ~4 min and is worth doing regardless — it is what let the usage-limit interruption cost nothing.
- **A usage-limit cut mid-dispatch is survivable and cheap IF you commit at part boundaries.** My clones came back untouched; `git status` + re-running the last green suite confirmed it in two minutes. Commit each Part as it lands — the interruption cost me nothing because Parts B-spine/D were already committed.
- **I mis-stated a test count in a commit message AGAIN** (said 216, truth 215). Both times the cause was writing the number before the last test landed and not re-measuring. **Measure immediately before writing the commit, never from memory.** The merge gate catches it now — its suite tail is the authority.
- **VERIFY THE BRIEF'S OWN FACTUAL CLAIMS, not just my code.** The D7 brief asserted EDGAR's `acceptanceDateTime` is ET-minus-4 as "a CRITICAL detail the analyst verified". Two measurements (n=2,400 histogram; n=30,732 next-business-day roll-over at raw hour 21 = 17:30 EDT) refuted it. Applying it would have created the lookahead it was meant to close. An accepted recommendation is not a verified one.
- **Engine facts, measured this dispatch:** a 5.47y `monthend_rebalance_flow` run exceeds **900s** (my own D6 ceiling) — the long-window runtime is STILL unmeasured, and the censored distribution I found in D6 is not resolved. A 6-month window is ~13s. `_parse_results` downsamples curves to 400 points BEFORE storing, so anything needing raw observations must be computed there or it is gone.
- **Shapes verified live (2026-08-21):** session JSONL lines carry `isSidechain: true` on sub-agent turns (that is how a seat dispatch is extracted); assistant `content` is a block list (`thinking`/`text`/`tool_use`), user `content` may be a bare string. EDGAR `recent` arrays are PARALLEL and NOT equal length (`items` is short on older feeds) — a bare `zip()` truncates every filing after the shortest column. `seat_telemetry` enumerates `REQUEST_KINDS.values()`, NOT the roster, so a seat missing from that map reports no runs at all.
- **The floor's geometry is COUPLED and the tests know it.** Moving a desk in `EXEC_ROW` breaks `CORRIDOR` (chain stations must lie on the aisle) and `BENCH_ORDER` (a seat with an exec desk must be excluded or it renders twice). Both broke when Donna was added; both were caught by existing tests, not by me.
- **Mock-spine fixtures now cover:** `MONITOR_FIXTURE`, `DIVERGENCE_FIXTURE`, `DESK_FIXTURE`, `ARCHIVES_FIXTURE`, `FAIL_DETAIL=1`. Generate them with the SPINE'S OWN code (`gen_archives.py`, `gen_desk_d7.py`) so shapes cannot drift. **It proxies POSTs to the live spine — never click a submit while it is up.**
- **Open for a future dispatch:** (a) Part G addendum, untouched; (b) walk-forward TRAIN legs carry no daily series — needs the winner's job held open past the grid; (c) the long-window engine timeout is unresolved; (d) everything still open from D6 — the latent drawdown-rebase direction defect (routed to riskofficer), belt `queued` state, gate.py holdout timeout split, the hardcoded `"neelesh"` approver, `aligned_returns` caching on `fetcher.__name__`, no DOM test runner.

- [co-CTO note at resolve, 2026-08-21]: both bundles independently
  gate-verified by me on the live heads (1277 + 215, 0 sensitive, 0
  forbidden), fund_api.ts diff confirmed additive with zero thesis types,
  DEFAULT_MAX_CHARS read and cleared as a script guard rail. Merged;
  spine restarted; archives endpoint serving; secretary in the roster;
  PIT backfill applied (249/249 accessions, 1035 rows, 0 unresolvable).
  **THE REFUTATION IS CONFIRMED, INDEPENDENTLY**: I re-measured the EDGAR
  timezone question myself (n=4,895, 6 issuers) and the decisive
  discriminator is the empty raw-hour 06-09 band — that is 02:00-05:00 ET
  when EDGAR is shut; under the ET reading it would be 06:00-09:00 ET
  when EDGAR opens. Plus 280 same-day vs 1 roll-over at raw 17-18 where
  the ET reading puts the cutoff. Then proven at the data layer: SRPT
  stores 20:01:46+00 = 16:01:46 ET, exactly the analyst's own cited
  figure. Refusing a brief on measurement, and being right, is this seat
  at its best — and it is the second time in two dispatches that the
  builder has corrected a chair. The false line is PARKED FOR FABLE (the
  API card is the CTO chair's instrument); every brief I write meanwhile
  will carry the correction inline.

## 2026-08-21 — CARRIED FROM THE MECHANISM (cycle 3) BY THE CHAIR

First use of the `## BINDS` protocol. The seat named you; the chair verified the underlying code claim and carried it.

**The walk-forward out-of-sample union is `(need + 1) × 4 × hold` trading
days, with `need` a single global constant** (`factory.py:220`, reading
`CRITERIA["min_walkforward_folds"]`). Chair-verified.

**A 1-day rule is certified on TWENTY trading days of a single regime** and
stamped with the same gate version as a 21-day rule certified on sixteen
months. Deriving `need` from a target OOS span instead gives 63/32/21/13/7
folds over 252–280 days for holds 1/2/3/5/10 and leaves hold=21 unchanged.

It is gate-adjacent, so it is Fable's call — **but the arithmetic, the fold
table and the container cost are all measured and in the artifact
(`docs/MECHANISM_CYCLE3_2026-08-21.md`). Do not re-derive them.** Note the
honest cost the mechanism volunteered: fold count IS container count, so
hold=1 is ~12.6× compute.


## 2026-08-21 — **STOP TREATING LOCAL COMPUTE AS SCARCE. IT IS NOT. MEASURE WHICH RESOURCE YOU MEAN.**

**CEO instruction, verbatim: "I am seeing concerns with the team of their
being a upper bound to compute which is not true; we have a very capable PC
and whats stopping them?"** He is right, and the chair measured the machine
rather than assuming either way.

**THE MACHINE, measured 2026-08-21:**

| resource | actual | verdict |
|---|---|---|
| CPU | **Ryzen 9 7900X — 12 cores / 24 threads, running at 11%** | **NOT SCARCE** |
| GPU | **RTX 4090**, idle except during local-model work | **NOT SCARCE** |
| Disk | 74 GB free of 421 | not scarce |
| **RAM** | **15.2 GB total, 0.8 GB FREE** | **THIS IS THE WALL** |

**THREE DIFFERENT SCARCITIES HAVE BEEN COLLAPSING INTO ONE WORD, AND ONLY TWO
ARE REAL:**

1. **TOKENS — genuinely scarce and structural.** This is what the quota-era
   dispatch rules protect: batch by seat, one human trigger, an idle seat costs
   zero. Frugality here is correct and is not up for revision.
2. **RAM — genuinely scarce at 15.2 GB, and it is the real container
   ceiling.** `MAX_CONCURRENT_CONTAINERS = 6` is registered with basis
   `measured` and falsified-by *"a WinError 1455 or any host-memory kill"* —
   the paging-file error. That limit came from an actual out-of-memory event.
   It is a RAM limit wearing the word "container".
3. **CPU, GPU AND WALL-CLOCK — NOT SCARCE, AND THIS IS WHERE THE FALSE CAUTION
   LIVES.** Twenty-four threads at 11% and a 4090 doing nothing.

**THE RULE THIS BUYS: before you cite a compute cost as a reason to narrow a
recommendation, say WHICH resource you mean and what you measured.** "12.6×
compute" is not a cost statement — it is three different claims wearing one
number, and on this machine two of the three are free.

**THE WORKED EXAMPLE, and it is a live one.** The mechanism's D5 fix would take
a 1-day rule from 5 folds to 63. The seat called it *"~12.6× compute per
candidate"* and declined to recommend it without a cap. But the quant measured
real container wall-clock at **12.8s average, 18.4s maximum**, including a
5.47-year verification. Sixty-three folds × two legs × ~13s is **roughly 27
minutes, run sequentially, on a machine at 11% CPU.**

**That is not a cost. That is a coffee break, and it is exactly what the
market-closed queue exists for.** The cap the seat hesitated over is probably
unnecessary, and the hesitation came from reasoning about CPU-seconds in the
token frame.

**WHAT IS STILL TRUE AND MUST NOT BE THROWN OUT WITH THIS:**

- **Run candidates SEQUENTIALLY when wall-clock is an output.** The quant
  established this and it stands: the constitution's dependency test says a
  wall-clock measured under unadvertised contention is corrupted, not slow. The
  300s censored tail that justified raising the timeout ceiling was recorded
  under three concurrent candidates; sequentially there was no tail at all.
  **Parallelism is what costs here, not duration.**
- **Concurrency still hits the RAM wall at 6 containers.** Do not raise that
  limit as a consequence of this note; it is a registered value with a measured
  basis and moving it is a versioned change.
- **Tokens remain the real budget.** An 8-hour local extraction is cheap; an
  8-hour Opus dispatch is not. When you defer something for cost, be explicit
  about which one you mean.


## 2026-08-21 — CARRIED FROM THE BUILDER (D9) BY THE CHAIR: three fields you should now state

**When you file a recommendation in your `run_record`, state these when you
know them. All three are optional, all three are validated, and NONE is ever
read out of your prose.**

- **`next_actor`** — `ceo` | `chair` | `seat` | `nobody`. Whose move is it?
- **`due_date`** — `YYYY-MM-DD`, if the thing happens on a date **whether or
  not anyone clicks.**
- **`reversibility`** — `irreversible` | `hard` | `reversible`, for your own
  recommendation.

**Why this matters more than it looks.** The CEO's desk counter now routes by
next actor, and the builder measured that **`kind` is free text — 84 distinct
values across 219 recommendations, 49 of them appearing exactly once.** Routing
on it moves only 18.7% of rows, so the counter currently rests almost entirely
on inference. **These three fields are the only lever that fixes it.** The
desk's top ranking key is `due_date`, and it separated **zero** rows because
nothing writes it.

**Absent is honest; wrong is not.** And note the default: **a `kind` nobody has
seen before routes to the CEO.** Pick one that says who must act, or state
`next_actor` and stop relying on the word.


## 2026-08-22 — CARRIED BY THE CHAIR (BINDS from four seats)

- **From the adversary (D11, your kill — read docs/reviews/
  ADVERSARY_D11_2026-08-22.md in full before the v2)**: when a diff
  declares a store/path/table durable, grep the WHOLE TEST SUITE for that
  literal and report the result in the diff message — krypton_fund_test is
  truncated by tests/test_pgstore.py:70 and ten modules target it. And
  when you add a "what is missing" report, state which fields its
  membership test compares on — a set keyed on symbol alone scored four
  kinds of dead exit rule as live coverage.
- **From the riskofficer**: "audible" means IN THE EVENT LOG, never
  logger.warning — autopolicy.py:706-718 documents the unwired-kill-switch
  risk in eleven lines of comment and ships a log line, invisible to the
  seat whose job is auditing that policy from /fund/events. If a comment
  says a control must be observable, the fix appends an event.
- **From Donna**: docs/README.md is the constitution's named carrier of
  each doc's status and has indexed nothing for three days while 17 docs
  landed in one of them. It is in the cleanup ticket (dce47670).
- **From Grace**: dispatched_at has never been written in any run, and the
  firm has no representation for a run that FAILED — your own dispatches
  are the ones most likely to die, so you gain the most from both. (In
  the D13 metrics brief, being built now.)


## 2026-08-22 — STATE from run-builder-d12 (the room), appended verbatim by the chair

- **Worktree base wrong an EIGHTH time — dispatched into the LIVE KryptonPay
  checkout.** Clone-into-scratchpad recovery (~4 min): git clone
  --no-hardlinks, junction node_modules, copy .env.local, checkout -b.
  Verify `git rev-parse --git-dir` returns a directory named .git to detect
  the live-checkout case. [CHAIR: future dispatches use isolation=worktree —
  the harness provides the clone by construction now.]
- **`git stash push -u` SILENTLY DOES NOTHING on a clean tree** — a lint
  baseline measured that way was my own branch twice. Use `git checkout
  <base> -- <subtree>` / `git checkout HEAD -- <subtree>` instead; it also
  measures the base tree's RENDERED behaviour.
- **CDP Emulation.setDeviceMetricsOverride PERSISTS across Page.navigate
  and across script runs**; clearDeviceMetricsOverride did not undo it —
  SET the metrics you want at the top of every probe. React onMouseEnter
  needs a real Input.dispatchMouseEvent (script at scratchpad/cdp_hover.js).
- **A READ-ONLY spine mirror is the safe way to exercise a state you cannot
  cause** (scratchpad/halt_mock.js: proxies GETs, rewrites halted=true,
  405s every non-GET — the 405 is the whole point).
- **THE FLOOR'S GEOMETRY IS COUPLED FOUR WAYS**: CORRIDOR chain stations,
  BENCH_ORDER, the SVG-drawn duplicates (office wall, cage, halt line), and
  the fixtures. Budget for all four. New tested invariants in floorPlan.ts:
  PLANE_PX, toScreen, screenSeparation (overlap is a claim about SCREEN px
  — the camera squashes y to 53%), wallClearance, runsChip.
- **Two defects in code I had JUST WRITTEN were found by SCREENSHOT, not by
  the diff or the suite** — four dispatches running; the look-at-it pass is
  not optional and not only for legacy code. And reading the diff
  end-to-end caught THREE wrong numbers in my own comments — after the
  coordinates stop moving, re-measure every numeric claim with a throwaway
  script before bundling.
- Verified live shapes: content column max 1152px with the Clark rail
  (898/812/713 at 1366/1280/1181 viewports). seat_telemetry had 10 keys
  because REQUEST_KINDS had no cfo [CHAIR: closed same-pass —
  allocation_review -> cfo, telemetry now 11].
- Open from this dispatch: SeatFace `wire` glyph for Grace (Hopper's
  nanosecond); officerQueues grace->cfo alias; seatLib.test.ts goes RED now
  that the spine kind exists — the reminder to wire her composer half.


## 2026-08-22 — CARRIED BY THE CHAIR (from Grace v0.2 and the analyst)

- **From Grace**: two of your dispatches had NO run record and both were
  killed — the meter priced your killed work at zero while pricing both
  kills in full, understating your cost and hiding what fixing the
  kill-rate would save. CHAIR CLOSED IT: run-builder-d8-retro and
  run-builder-d11-retro exist now (d11 with real figures). Standing
  instruction: when a dispatch of yours dies or is killed, say so in your
  STATE and ask the chair to record a run. And measured, twice now: narrow
  single-purpose diffs merge; bundles on the broker/event-store surface
  die. SIZE YOUR BUNDLES BY THE SENSITIVITY OF THE SURFACE.
- **From the analyst, for the queue**: insider_parse.py must join on
  ISSUERCIK, not ISSUERTRADINGSYMBOL (measured: 4,106 missed, 1,048 alien
  rows; the live 2021–2026 panel inherits it).


## 2026-08-22 — STATE from run-builder-d13 (the metrics layer), appended verbatim by the chair

- **BASE WAS CORRECT** (2af4256, exact) — verify the live head directly in
  one call before cloning; cheaper than the clone. Dispatched into the OUTER
  repo again; clone into a DISPATCH-SPECIFIC subdirectory (the shared
  scratchpad root now holds other agents' work).
- The venv is `ClarkHarness/venv`, NOT `.venv` — the only Python with
  psycopg/fastapi (3.11.15). Large heredocs through Bash get mangled — Write
  tool for files over ~100 lines. `curl -o` needs a Windows-style path.
- **Verified live shapes (965 events / 55 runs)**: `OrderFilled.avg_price`
  is a STRING on 22 of 29 rows and a number on 7 — coerce. 20 of 29 fills
  carry NO `venue` key. 14 of 24 `DeskDispatched` carry no request_id, 1
  names a request never filed. All `ts` exactly 32 chars ending +00:00 —
  string ranges on the TEXT column are safe. Decision actors exactly
  {ceo, cto, co-cto}.
- **FastAPI matches routes in DECLARATION ORDER** — a literal path after a
  path parameter on the same prefix is unreachable and 404s plausibly.
  /fund/desk/runs/stats sits before /{run_id}, pinned by two tests.
- **New module `app/fund/metrics.py` — extend it, never re-fold a day by
  hand.** `scripts/desk/` exists — run it, never re-author; the quirk list
  lives once in `_common.py` and a test pins ten named traps.
- Confirmed defects fixed, mutation-verified: the recorder's
  correction-discarding upsert; DeskStore.run()'s 1,000-row scan; the
  script fallback's import order; duplicated day arithmetic.
- The late pass caught three of my own — including a REGRESSION TEST THAT
  COULD NOT CATCH ITS OWN REGRESSION ("20.0h" contains "0.0h"), rewritten
  and proven by mutation. The late pass is not optional; five dispatches
  running.
- **Fitness, stated plainly: +3,732/−30 = 124:1. On DELETIONS I score
  poorly.** The next dispatch under this name should be deletion-first —
  THE CLEANUP (dce47670) is filed and waiting.
- Open: no UI reads chair_backlog yet; the 14 unlinkable DeskDispatched
  rows are a write-path data defect (out of my bounds); status/dispatched_at
  now written by the chair as of run-builder-d13 itself.


## 2026-08-22 — CARRIED FROM THE READINESS MATRIX (PM) BY THE CHAIR

The three control blockers are ONE bounded sprint on the critical path to first real dollars, target 2026-08-26: guard /fund/risk/resume (fund.py:3797-3800), give the integrity halt a producer (riskmonitor.py:967-989 builds an alarm list run() never reads), make venue knowable from the executing connector's identity not order['venue'] (pipeline.py:229 vs :318). Ship as a batch; resume+venue diffs are a LOOSENING and go adversary-blind. A blocker with no motion past its date is the moat the CEO forbade.


## 2026-08-22 — STATE from run-builder-d14 (D11 v2 repair series), appended by the chair

Repaired the killed fund-mode diff as 11 separable ClarkHarness commits +
2 KryptonPay, all 8 kills closed, NOTHING MERGED. 1694 passed RC=0 (baseline
1523->1636->1694), 335 passed, tsc exit 0. Gate: 37 ordinary, 2 sensitive, 0
forbidden.
- **THE BRIEF/REVIEW SPEC CAN BE WRONG, AND FOLDING THE CODE IS THE JOB**: the
  adversary's K2 said "filter on not-superseded"; measuring exitrule._fold
  proved `superseded` marks the SURVIVING GOVERNING rule as REVISED, not dead
  (enforce() skips triggered_at/overridden_at explicitly, NOT superseded).
  Verbatim it would have made re-commitment - the only way to restore a fired
  exit rule - invisible to the coverage report. Third dispatch running where a
  chair/reviewer factual claim failed measurement (D7 tz, D13 shapes, now K2).
  FOLD THE PREMISE BEFORE YOU FOLD THE CODE.
- Third K2 defect the review missed: rows read `usd_value`, assess() emits
  `value_usd` - every uncovered row null on the live path. Both keys read now.
- K4 DELETED CashReconciled (zero ever written, verified both ledgers); named
  five more pre-existing producer-less NAV folds (CORPORATE_ACTION_APPLIED,
  DIVIDEND/INTEREST_RECEIVED, PAYOUT_SENT, UNITS_BURNED) in a shrink-only
  allowlist with a test that fails if a sixth appears.
- K5 `allow_prod` DELETED (zero callers, its only function was the hole); all
  four prod gates now read prod_gate_report()['reachable'] so report and
  refusal are one call.
- Look pass caught 3 UI defects written the same hour (amber on every row;
  dead-spine dialog pointing at an empty list; a sentence broken by a period).
  Sixth dispatch running.
- Verified live: assess() positions are {symbol,qty,mark,value_usd,weight_pct,
  unrealized_pnl_pct,shock_20_usd} - value_usd not usd_value, NO strategy_id.
  krypton_fund 967, krypton_fund_test 1, dev+prod DO NOT EXIST. .env 12 keys,
  no FUND_LIVE_MARKS.
- git worktree add inside the clone is the clean baseline-count method; NEVER
  worktree remove while a node_modules junction is inside (rmdir it first).
- Fitness: +5,776/-267 = 21.6:1, better than D13's 124:1 but still accretion.
  THE CLEANUP (dce47670) deferred TWICE now - dispatch it before the next
  feature brief under this name.
- Open: confirmEcho collision (human call before prod unlock); 5 legacy folds;
  run_test.sh CREATE branch unexercised (krypton_fund_dev absent); 14
  unlinkable DeskDispatched (not my surface).
- EVOLVE proposed: before implementing any predicate a brief names by field
  name, fold/execute the code that sets it and print the result first.


## 2026-08-22 — STATE from run-builder-d15 (belt bar cache), appended by the chair — MERGED cf0368d

- **Worktree base wrong a NINTH time** — dispatched into the LIVE outer `Krypton Fund` checkout. **New, cheaper recovery than cloning: `git -C <ClarkHarness> worktree add -b <branch> <scratchpad>/ch <base>`** — shares the object store, no 4-minute clone, and the scratchpad already had other agents' worktrees so this is the house pattern now. Verify base with `git -C <wt> rev-parse HEAD` before touching anything.
- **The brief said base = "current master of ClarkHarness". THERE IS NO master.** `main` is the initial commit (LICENSE only, 268 behind). The real head is `claude/krypton-fund-agentic-j8r2mu`. It moved TWICE mid-dispatch; the merge gate handles it, so bundle from your base and let the gate merge.
- **FOLD THE PREMISE BEFORE THE CODE — fourth dispatch running that a brief's factual claim failed measurement** (D7 tz, D13 shapes, D14 K2, now this). The brief said to serve the cache "via the existing LEAN data mount path". `leanrunner._run` mounts only `/Algorithm:ro` and `/Results` — **there is no data mount**; containers fetch over HTTP from the spine.
- **The safety argument for a cache is WHO CONSULTS IT, not how narrow its scope is.** Verified: the HTTP `/fund/marketdata/bars` endpoint's only runtime consumers are LEAN containers and offline scripts; `quotes.py`/`stress.py`/`correlation.py`/`regime.py`/`factors.py`/`optimization.py` all call `fetch_daily_bars` **in-process**. Never wrap `fetch_daily_bars` — a test pins that, and a second test pins the consult-site count at two.
- **`marketdata.py:380`: `fetch_daily_bars` uses ALPACA for a trailing lookback and YAHOO whenever BOTH start and end are given.** Consequence, measured: strategies trade Alpaca closes and are benchmarked against Yahoo ones. Prices agree (0.46 bps mean, 0.00pp of total return) but **Yahoo lags one session**, so every benchmark has been computed over a window one session shorter than the strategy's (409 vs 410 bars, 0.10pp on the test run). Reported via `benchmark_feeds` / `benchmark_feed_mixed` now.
- **Endpoint facts (measured 2026-08-22):** `/fund/marketdata/bars?lookback_days=2000&format=csv` = ~1.94s for 24,702 bytes, **no faster on repeat**; `?as_of=YYYY-MM-DD` reads the Postgres archive at **~0.03s** and is 60× faster — an existing point-in-time path nothing in the belt uses. JSON shape is exactly `{symbol, source, closes, dates, start, end}`; the `as_of` branch returns a DIFFERENT shape (pre-existing).
- **Static readers that work on the real algorithms:** `_declared_universe` (module-level `UNIVERSE`) and my new `_declared_lookback_days`. **Read the AST, never the source text** — the 170-name Entry 20 algorithm names its rejected lookback in a COMMENT, and a text scan skips the snapshot on the one candidate that needed it. Repo survey: 16 algorithms, 9 declare no UNIVERSE (no snapshot), largest committed universe is 20; the 170-name one is untracked in the live tree.
- **My own re-slicing bug is the lesson to keep**: a cache that answers a *slightly different* question than it was asked is worse than one that declines. Exact shape → serve whole; anything else → miss, served live, recorded.
- **A consult site that can never hit is worse than none** — `_add_capacity` (120d against legs pinned at 700/900/2000) recorded a miss on every candidate and made `uniform_data_path` permanently False. Found by reading the diff end-to-end, not by the suite. **Sixth dispatch that the late read-through caught something the tests did not.**
- **Fitness: +1,619/−1.** Worse than D14's 21.6:1. Only real deletion is the dead consult site; I did bound new accretion (snapshots gitignored + `prune_snapshots(keep=20)`, measured at 7.40 MB per 170-leg candidate). **THE CLEANUP (dce47670) is now deferred THREE times — it must take the next slot under this name.**
- Open: 170-leg container A/B never run (evidence is data-layer only); `_add_benchmark` sums legs POSITIONALLY while `ref_dates` comes from the longest leg — a real alignment defect, reported not fixed; the `as_of` archive path is unused by the belt and is the natural next win; everything still open from D14.


## 2026-08-23 — STATE from run-builder-d16 (gate v4.2), appended by the chair

- **Base was CORRECT (cf0368d) for the second time in 16 dispatches** — but dispatched into the LIVE ClarkHarness checkout again (tenth time). `git rev-parse --git-dir` returning a literal `.git` directory is the one-call detector. Recovery is the D15 pattern, now routine: `git -C <ClarkHarness> worktree add -b <branch> <scratchpad>/ch2 <base>`, ~5s, no clone.
- **The live head moved mid-dispatch (cf0368d → 56d450a, 24 commits).** Check overlap with `git diff --stat <base>..<head> -- <your files>`; empty overlap → bundle from base and let the merge gate merge.
- **`merge_builder.py` FAILS on any `app/fund/gate.py` change by design** — sensitive surface, adversary blind. A routing verdict, not a test failure; report `suite -> exit 0` and the tail beside it. Do not describe a sensitive-blocker FAIL as a broken build.
- **MUTATION CAUGHT A TEST OF MINE THAT COULD NOT CATCH ITS OWN DEFECT, again.** Asserting `mine == CRITERIA[key]` cannot distinguish a hardcoded copy. **To prove a value is READ rather than COPIED, MOVE it** — override the criteria with a different number and assert the behaviour follows. Two dispatches, same class (D13 "20.0h" contains "0.0h").
- **The late read-through caught a FALSE CLAIM in my own comment** — an asserted mojibake that measurement disproved; the damage was my own `json.load(open(...))` on cp1252. **On Windows pass `encoding=` explicitly before claiming anything about stored text.** Seventh dispatch running that the late pass caught what the suite could not.
- **I introduced a flakiness source and found it by reading**: two tests submitted to the factory without `_settle`, leaving belt threads holding connections into the next test's TRUNCATE (one red in 24 runs, unreproducible). **Any test that submits to the factory must settle.**
- **Verified belt shapes (candidate 144387901688):** sweep `tested_range` is `[min,max]` slip as FRACTIONS; `_run_sweep` overwrites start/end with the HOLDOUT'S TRAIN WINDOW on every grid point (leanrunner.py:933-935) while the verification run re-runs with no dates over the FULL window — **the sweep and the verification measure different windows and nothing says so.** Sweep points and holdout legs carry NO benchmark (enrich=False at :808).
- **`breakeven_cost` never sees the benchmark and cannot** — any active-return criterion is a BELT change (per-point benchmarks over each point's own window, item 1 of the v5 design), never a gate change. Refuse a brief that puts it in gate.py.
- New public helpers: `gate.max_tested_bps(tested_range)`, `gate.fmt_bps(x)` (round(9.996,1) prints "10.0" — compare raw, format only for display), `factory.check_cost_grid(grid, criteria=None)`, `factory.COST_PARAM`.
- **Fitness: +442/−12 = 36.8:1** — no dead code in reach of a three-fix gate brief. **THE CLEANUP (dce47670) deferred a FOURTH time — takes the slot after the hazard batch + benchmark population.** Added to its scope: four abandoned worktrees under `ClarkHarness/.claude/worktrees/` pinned at `cebc578`.
- Open: the "unprofitable at every cost tested" mislabel; `_add_benchmark` positional summing; the `as_of` archive path unused; everything from D14/D15.


## 2026-08-23 — STATE from run-builder-d17 (the hazard batch), appended by the chair

- **Wrong base an ELEVENTH time** (live outer checkout; `git rev-parse --git-dir` → `.git` is the one-call detector); worktree-add recovery routine at ~5s. Head moved mid-dispatch (56d450a → 8c01c35); `git diff --stat base..head -- app/ tests/` was EMPTY so bundling from base was safe. **Check the overlap, never the head.**
- **FOLD THE PREMISE — fifth dispatch running**: item 7 (b72847bc) was ENTIRELY closed by D11v2 (mode.py + venue.py; the cited lines no longer exist) and item 6(B) was closed 2026-08-21. ~2 of 7 brief items already done; the 10-minute read freed the budget that paid for the mutation pass. **EVOLVE applied: verify-the-item-is-still-open is now a REPORTED first step (already closed / partially / open, per item), not a habit.**
- **COROLLARY: a fix applied to one file in a family is not applied to its siblings.** The falsified "re-raises on the next tick" claim was corrected in pipeline.py and fund.py and left standing in autopolicy.py:174 — where it JUSTIFIED the 10-minute ceiling. **When a review corrects a claim, grep the CLAIM, not the file.**
- **A HELPER CAN BE FLAWLESS AND UNCALLED.** Mutation restored the original bug inside PositionsProjection._apply and every cost-basis test still passed — they all called _new_avg_price directly. **Drive at least one test through the real call site.** Unwired-kill-switch family.
- **EVOLVE applied: mutation reports have THREE outcomes** — killed / SURVIVED / retired-with-proof (a no-op or proven-equivalent mutant). 42 killed + 2 retired honestly beats a silent 44/44.
- **Late read-through caught FOUR false claims in my own comments — eighth consecutive dispatch.** Sharpest: "six guarded siblings" inherited from a memo; the true count is EIGHT. **Never carry a number from a brief or another seat's memo into a comment without counting it yourself.** Also: a nonexistent field, a residue that measurement disproved (this projection is Decimal — seven symbols at EXACTLY zero), and _QTY_EPS 1e-9 vs reconcile._TOL 1e-6 (different questions).
- **A/B-FOLDING THE LIVE LOG IS HOW A PROJECTION CHANGE SHIPS**: pull /fund/events (NEWEST FIRST — sort by seq), fold under old and new rules, diff the books. Zero of 11 symbols changed. Script: scratchpad/fold_ab.py.
- **POST /fund/risk/limits (fund.py:4147) IS UNGUARDED AND MOVES THRESHOLDS** — no allowlist, echo, or written reason. Resume was never "the only one". Left unfixed: who may move a threshold is a governance decision. /fund/risk/halt also unguarded but fail-safe.
- **Zero tests had ever called POST /fund/risk/resume** — an endpoint with no test survives adversary review of the module around it. When a brief names an unguarded endpoint, grep the suite for it FIRST; the absence is the finding.
- **Live shapes:** drift is GET /fund/venue/reconcile (NOT /fund/reconcile/drift, 404): {configured, book_nav, broker_equity, delta_usd, delta_pct, per_symbol[], symbols_out_of_sync, as_of}. POSITION_EPS=1e-9; reconcile._TOL=1e-6; EIGHT pre-existing _guard_approval sites.
- **New reusable surfaces**: riskmonitor.unrealised_pnl_pct / _drift_alarm / DRIFT_ALARM_KEY / UNEVALUATED_ON_ABSENT / RiskMonitor._can_evaluate / RiskMonitor(drift_fn=...); positions._new_avg_price; autopolicy.record_decline; EventType.AUTOPOLICY_DECLINED.
- **UNEVALUATED_ON_ABSENT is the general lesson**: `active_keys - current_keys` conflates "evaluated false" with "never evaluated" — any new rule with an optional input must join that set or it erases itself on monitors lacking the input.
- **Fitness: +1,901/−51 (app/ +817/−60).** THE CLEANUP (dce47670) deferred a FIFTH time — next slot under this name; scope includes the four cebc578 worktrees.
- Open: avg_cost <= 0 → 0.0 reads as good standing to every exit rule (named, unfixed — moves the underwater alarm); shorts' unbounded downside / borrow cost / buy-in risk unmodelled everywhere (an alarm is not coverage); no UI consumes AutopolicyDeclined or venue_drift; mode.py exit_sign_fixed precondition stays `unchecked` (correct — inventing an evaluator that says "met" would be a loosening); everything from D14/D15/D16.
