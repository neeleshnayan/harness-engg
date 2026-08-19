# Cost model — what a run of this firm actually costs

**Measured 2026-08-20 from the token usage recorded on every real dispatch this
week. This is the theoretical foundation the CEO asked for before scaling the
run: spend distribution first, then execution. Status: finding — per-dispatch
figures are measured; monthly figures are cadence assumptions × measured costs
and are labelled as such.**

## API pricing in force (Anthropic first-party, checked 2026-08-20)

| model | input $/MTok | output $/MTok | notes |
|---|---|---|---|
| Fable 5 | $10.00 | $50.00 | 2× Opus on input, 2× on output |
| Opus 5 | $5.00 | $25.00 | the bench default |
| Sonnet 5 | $3.00 | $15.00 | intro $2/$10 through 2026-08-31 |
| Haiku 4.5 | $1.00 | $5.00 | structured/simple tasks |
| prompt caching | writes ~1.25× input, reads ~0.1× input | | biggest single lever on long sessions |

## Measured: what one dispatch costs

Every dispatch this week, with its recorded token total:

| dispatch | seat | tokens | tool uses |
|---|---|---|---|
| Dalio-lens review | (consultant) | 121,601 | 20 |
| Griffin-lens review | (consultant) | 103,322 | 23 |
| VRP proposal | mechanism | 67,513 | 7 |
| Gate v5 kill, round 1 | adversary | 116,972 | 11 |
| VRP kill (live data) | adversary | 89,981 | 19 |
| Gate v5 kill, round 2 | adversary | 76,953 | 8 |
| First portfolio review | pm | 107,119 | 12 |
| First thesis (SRPT) | analyst | 118,763 | 23 |

**Central figure: ~100k tokens per dispatch** (range 67–122k), remarkably stable
across seat types.

**Honest limitation:** the recorded figure is a token *total*; the input/output
split was not captured. Agentic work is typically input-heavy (context re-reads).
Bounds per 100k-token dispatch:

| model | all-input (floor) | 90/10 in/out (realistic) | all-output (ceiling) |
|---|---|---|---|
| Opus 5 | $0.50 | **~$0.70** | $2.50 |
| Fable 5 | $1.00 | **~$1.40** | $5.00 |
| Haiku 4.5 | $0.10 | ~$0.14 | $0.50 |

**Working number: ~$0.70 per Opus dispatch. A full mechanism → adversary →
verdict chain: ~$1.50. The week's entire bench output — two consultant reviews,
one proposal, three kills, one PM review, one thesis — cost roughly $6–8 at Opus
rates.** The bench is cheap. That is the first structural finding.

**Confessed error, priced:** the PM and analyst first runs inherited the Fable
main-session model because the CTO failed to pin them — roughly 2× overpay,
~$1.50 wasted. Fixed; all dispatches pin Opus explicitly, and the seat
definitions carry `model: opus`.

## Where the money actually goes

| layer | cost driver | monthly estimate (assumptions stated) |
|---|---|---|
| **CTO session (Fable)** | the dominant cost, 10–50× the bench: long-lived context, every verification, every build | not directly measurable from here; the lever list below targets it |
| **The bench (7 seats, Opus)** | ~$0.70/dispatch | PM daily (30) + analyst 3/wk (13) + adversary ~20 reviews + mechanism 4 + quant 4 + validator 4 + riskofficer 4 ≈ **80 dispatches ≈ $55–60/mo** |
| **Filings extraction** | **$0 — already local** (Ollama qwen3.5:9b on the 4090; `observations.py` `_default_model`). The 863-obs corpus cost ~nothing in API terms | $0 |
| **LEAN belt** | local Docker CPU — electricity only | ~$0 |
| **Market data** | Alpaca/Yahoo free tiers; Polygon free | $0 until we buy history |

The structural picture: **compute that judges (bench) is cheap; the expensive
thing is the orchestrator (CTO on Fable); the volume work is already free.**

## The distribution policy — what runs where and why

| tier | runs on | what | rationale |
|---|---|---|---|
| 0 | deterministic code | auto-policy, gate, sieve, all ticks | correct by construction; $0; the sieve already replaced ~$0.35 of LEAN-adjacent judgement per organism with ~1ms of CPU |
| 1 | **local 4090** (qwen-class) | filings extraction (done), corpus tagging/dedup, first-pass summarisation, observation enrichment | high-volume, verifiable-output, low-stakes. Every output is checkable (quote-verification already enforces this for extraction). Known quirk: qwen3.5 needs think=false on no-tool steps |
| 2 | Haiku 4.5 | rigidly-specified structured tasks if local quality fails a spot-check | $0.14/dispatch; only where a wrong answer is cheaply detectable |
| 3 | **Opus 5** | all seven seats | judgement work where being wrong costs money; ~$0.70/dispatch is already cheap enough that economising here is optimising the small number |
| 4 | Fable 5 | CTO chair only, and only for genuinely hard design (gate redesigns, constitutional changes) | routine CTO ops (verification, wiring, dispatch) run fine on Opus at half price — switch with /model |
| never local / never downgraded | — | adversary verdicts, anything in the approval chain | a kill must be trustworthy; the auto-policy is code, not a model, precisely so this row stays empty |

## Levers, ranked by expected savings

1. **CTO chair on Opus for routine sessions** (~50% of the dominant cost).
   Fable by explicit choice for design-heavy days.
2. **Dispatch context discipline** — the memory-file protocol exists partly for
   this: a seat reads its own state file instead of having history re-narrated
   into its prompt. Target: keep dispatch prompts under ~3k tokens.
3. **Session hygiene** — long CTO sessions re-carry giant context; prompt
   caching absorbs most re-reads (~0.1×) but fresh sessions after major
   milestones reset the growth curve.
4. **Local tier expansion, measured not assumed** — before moving any task to
   the 4090, run 10 outputs against Opus on the same inputs and diff. Move only
   what passes; the extraction pipeline is the template (its quote-verification
   makes wrong outputs self-evident).
5. **Batch API (50% off)** exists for non-urgent, non-agentic API work — nothing
   in the current design qualifies (the belt is local), noted for when
   API-driven research sweeps appear.

## The cost ledger, going forward

Every dispatch resolution already flows through the CTO; from now the resolve
step records `tokens` into the seat's state file alongside the artifact, so this
model gets re-measured from operations rather than reconstructed. Re-baseline
monthly; a dispatch drifting past ~150k tokens is a prompt-discipline finding,
not a billing fact to absorb.

## What this does NOT cover

- The CTO session's own token consumption — the dominant cost — is not visible
  from inside the session. The levers target it directionally; measuring it
  needs the console/usage page, which is the CEO's view, not this repo's.
- Input/output split per dispatch (bounded above instead).
- Cadences are assumptions; the ledger replaces them with measurements as the
  firm actually runs.
