# BUILD-PLAN.md — AI Orchestration Layer

**Date:** 2026-07-15 · **Status:** Planning locked, Phase 1 approved
**Sources:** Ringer guide (Nate B. Jones), harness anatomy (Claire Vo / Claude Agent SDK), loop-of-loops, 4 Patterns, steer-vs-dispatch Run Spec.

---

## The stack (target state)

The four architecture shapes are layers, not competitors. Build bottom-up, router last.

```
Layer 4  CHIEF OF AGENTS (router)          ← deferred until scoreboard has data
         Classifies incoming work, routes to a loop, harness, or swarm.
         Routing comes from Ringer's per-model pass-rate scoreboard, not intuition.

Layer 3  HARNESSES (one per recurring job)  ← Phase 3
         Claude Agent SDK. Fixed stages, opinionated adapters, tool policies,
         artifact store. First harness: presales gap-analysis pipeline.

Layer 2  LOOPS (recurring jobs w/ memory)   ← partially exists today
         Scheduled tasks upgraded to loop specs: trigger, sources, memory,
         safe actions, stop points, record. Thin attention layer on top.
         Research & briefings live here.

Layer 1  RINGER (batch dispatch + eval log) ← Phase 1, now
         Frontier model writes specs & reviews; cheap parallel workers
         implement; checks verify. The eval log is the compounding asset.

Layer 0  EXISTING FOUNDATION
         Knowledge base (memory) · Claude Code/Cowork (orchestrator seat) ·
         Skills · Scheduled tasks
```

**Workload mapping:** code/repo work → Ringer swarms · presales deliverables → harness (calls Ringer for parallelizable sub-work) · research & briefings → loops.

## Decisions made (2026-07-15)

1. First workloads: research & briefings, presales deliverables, code/repo work.
2. Build order: Ringer first, on code work only — the novel part (judge checks) ships on proven plumbing.
3. Verification for non-code work: LLM-as-judge rubric with mandatory shadow-mode calibration before gating.
4. Token reality: frontier plan caps are hit regularly → cheap lanes (OpenRouter via OpenCode) have real ROI. Frontier budget reserved for specs + review.
5. Router deferred: a router with nothing to route to is meta-work. Built when the scoreboard answers "which model owns which task type" from verified history.

## Phase 1 — Ringer on code work (weeks 1–2)

Goal: proven plumbing + eval log accumulating.

- Clone `github.com/NateBJones-Projects/ringer`, run `./ringer.py demo`.
- Wire the OpenRouter lane (OpenCode CLI, small prepaid credit; key stays in OpenCode's auth store). Prove with a one-task manifest.
- First real manifest: 2–4 independent repo/tooling tasks from the actual backlog. Lint before running.
- `./ringer.py install-agent` so the orchestrating agent reaches for Ringer on swarm-shaped work.
- **Exit criteria:** one real swarm, all tasks verified by executed checks, results reviewed in Ringside, eval rows in the JSONL.
- **Kill signal:** two weeks without a genuine swarm-shaped batch → the code workload is thinner than assumed; rebalance toward Phases 2–3. Do not invent demo tasks.
- **Status (2026-07-15): plumbing proven, both lanes live.** Ringer cloned (`~/Documents/Claude/ringer`), config installed, demo verified in Ringside. Setup finding: the demo initially failed 0/3 because Codex CLI 0.139.0 predates its own default model (`gpt-5.6-sol` rejects older CLIs) — fixed by the CLI's self-updater (→0.144.4); keep worker CLIs current. OpenRouter lane wired (OpenCode 1.18.2 via Homebrew, Seatbelt wrapper from the Ringer clone, default `z-ai/glm-5.2`) and proven with a one-task manifest: executed check PASS on attempt 1, 9,480 tokens, ≈$0.012. Grok lane declined (no plan). Spec-craft lesson from the demo itself: a spec ending "…containing exactly: alpha ready." sometimes gets the trailing period written into the artifact — the executed check caught it every time; keep literal content on its own line or in delimiters. **Remaining for exit:** first real 2–4-task manifest from the backlog, reviewed in Ringside; `./ringer.py install-agent`.

Guardrails inherited from Ringer: stdin closed, sandbox explicit, verification executes the artifact, raw logs only. Worktree footgun: checks copy deliverables out before exit 0.

## Phase 2 — LLM-judge check pattern (weeks 3–5)

Goal: extend the check contract to judgment work without trusting an unverified judge. Interface in `SPEC-judge-check.md`.

- Judge check = script sending artifact + rubric to a judge model; exit 0/1; prints the failing rubric line.
- Judge ≠ producer, ever. One rubric per deliverable type. Failure output feeds the retry.
- **Shadow mode (2–3 weeks):** judge scores everything, owner still reviews everything, agreement logged per artifact. Judge gates internal work only at ≥80% agreement; overrides keep being logged after graduation.
- Budget note: judging is frontier-quality work and eats plan budget — correct per the thesis, but realized savings < the pitch. Track in the token dashboard.

## Phase 3 — Presales harness (weeks 6+)

- Claude Agent SDK. Candidate: gap-analysis pipeline (intake requirements → requirement matrix → ratings → internal + external docs).
- Opinionated adapters (exact fields per stage), draft-only tool policies, artifact store for cross-run memory.
- Parallelizable stages dispatch through Ringer manifests with judge checks.
- Permanent human gate on anything prospect-facing, regardless of judge score.
- Build the harness *with* the agent so the agent can maintain it (Pattern 3).

## Phase 4 — Loops upgrade + router (later)

- Rewrite scheduled tasks as loop specs (trigger, sources, memory, safe actions, stop points, record, handoffs) with an attention-layer summary: ran clean / changed / repaired / needs judgment / stopped on failed check.
- Chief-of-Agents router built only once `./ringer.py models` has real per-task-type history.

### Phase 4a — Self-healing scheduled jobs (sentinel/repair loop) — can pilot after Phase 1

Goal: a scheduled job that errors gets diagnosed and fixed by an agent, unattended; the owner sees only what the agent could not safely fix.

- **Wrapper per job:** run → on failure capture raw error/logs → repair agent diagnoses → classify:
  - **Class 1 (environmental/transient):** timeout, expired auth, source format drift, path/dependency breakage → agent applies fix from a bounded fix policy, re-runs, verifies against the job's own check, logs the repair. No human.
  - **Class 2 (spec/logic):** anything that changes what the job *does* → never auto-fixed; stop and file one attention-layer line.
- **Invariants:**
  1. The job's check/success definition is **read-only to the repair agent** — it may fix the job, never the test (agents will otherwise redefine success to clear the error).
  2. Every repair appends to a repair log (what broke, what was changed, proof the check passed) — no silent self-correction.
  3. Same job repaired ≥N times in a window → escalate anyway: recurring repair means the spec is broken, not the environment.
- **Dependencies:** mechanical jobs (data pulls, dashboards, token tracking) need only Phase 1 check discipline — pilot one job ~week 3. Judgment jobs (briefings) need Phase 2 judge checks before the repair agent can verify its own fixes.
- **Exit criteria:** one scheduled job runs 4 consecutive weeks where every failure was either auto-repaired-and-verified or correctly escalated — zero failures the owner had to diagnose himself.
- **Status: PILOT LIVE (2026-07-15).** The daily token-dashboard refresh job was hardened with the Repair Protocol (upstream-ingest kickstart, bounded fetch retries, append-only repair log, 3-in-7-days tripwire) and a 7:20 PM sentinel task now verifies the run landed and re-executes it if not. Interface documented in `SPEC-self-healing-loop.md`. Root-cause finding from transcript archaeology: the most common "needs manual restart" failure was runs stalling on unapproved tool permissions — fixed by one-time permission prestaging, not by repair logic.

## Risks & open questions

- Judge false-pass rate unknown until shadow mode ends — judge never gates external work.
- Review-cost economics: a swarm producing 7 artifacts creates 7 review burdens. Every manifest answers "how much review am I willing to spend?" before running.
- Infrastructure without workload: Phase 1 exit criteria require real backlog tasks.
- Compounding check: in 6 months the system should know which models own which task types, which spec styles pass first-try, and which rubric lines get overridden. If those aren't accumulating, it's a tool, not infrastructure.
- Lock-in: architecture is portable, tools are not. Ringer, the SDK, and OpenRouter are current implementations, not the architecture.

## Success metrics

- Phase 1: ≥1 real swarm/week; first-try pass rate visible; frontier tokens on mechanical work trending down.
- Phase 2: judge/owner agreement measured; ≥80% before gating internal work.
- Phase 3: gap-analysis cycle time vs. baseline; zero re-explaining of job setup per run.
- Standing: plan-cap hits on mechanical work down; review time per accepted artifact down.
