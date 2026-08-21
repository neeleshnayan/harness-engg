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
