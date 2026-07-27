# BUILD-PLAN.md — AI Orchestration Layer

**Date:** 2026-07-15 · **Status:** Phase 1 COMPLETE (2026-07-22) · Phase 2 STARTED (2026-07-22) — shadow mode live on the morning briefing · Phase 2.5 INSTALLED (2026-07-24) · Phase 2.6 slotted (2026-07-24)
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
- **Status (2026-07-22): PHASE 1 COMPLETE — exit criteria met.** `install-agent` run (skill + hooks live). Two real swarms from the genuine backlog, all verified by executed checks, reviewed in Ringside:
  - `repo-backlog-sweep` (4 tasks, Codex + GLM): regenerated ai-task-manager's drifted AGENTS.md file map (pushed); root-caused the token-dashboard usage-breakdown bug — `run-all.sh` never invoked `ingest-usage.mjs`; a sandbox reproduction proved the ingester itself works (fix shipped + verified end-to-end same day); audited all 25 active repos' AGENTS.md file maps against their real trees — 21 of 25 drifted.
  - `agents-drift-fix` (20 tasks, 15 GLM / 5 Codex): regenerated every drifted File map to the `Path | Committed? | Purpose` standard. 16 first-try, 4 retry-rescued, 0 final failures; all 20 pushed.
  - Eval log at 46 rows across 4 task types. First real routing evidence — docs work: GLM 5.2 0.76 first-try at ~23k tokens/task (~1–2¢), Codex 0.83 first-try at ~78k tokens. Recurring worker failure mode both models share: attempt 1 occasionally produces *no output file*; executed checks caught it every time.
  - Check-craft lessons: scope path extraction to the table's Path column (backticked prose in other columns caused a false FAIL); have workers write deliverables in their own task dir and let the check copy into the target repo — sidesteps sandbox write restrictions on every engine.

Guardrails inherited from Ringer: stdin closed, sandbox explicit, verification executes the artifact, raw logs only. Worktree footgun: checks copy deliverables out before exit 0.

## Phase 2 — LLM-judge check pattern (weeks 3–5)

Goal: extend the check contract to judgment work without trusting an unverified judge. Interface in `SPEC-judge-check.md`.

- Judge check = script sending artifact + rubric to a judge model; exit 0/1; prints the failing rubric line.
- Judge ≠ producer, ever. One rubric per deliverable type. Failure output feeds the retry.
- **Shadow mode (2–3 weeks):** judge scores everything, owner still reviews everything, agreement logged per artifact. Judge gates internal work only at ≥80% agreement; overrides keep being logged after graduation.
- Budget note: judging is frontier-quality work and eats plan budget — correct per the thesis, but realized savings < the pitch. Track in the token dashboard.
- **Status (2026-07-22): STARTED — judge live in shadow mode.** `checks/judge.py` implements SPEC-judge-check exactly (exit 0/1/2, mandatory FAILED LINES, `--shadow` always-0 + append-only `runs/judge-shadow.jsonl`, `--owner-verdict` for agreement rows). First rubric: `rubrics/morning-briefing.md` v1 (10 lines from briefing editorial spec v2.5). Judge = GLM 5.2 via OpenCode (judge ≠ producer: briefing is Claude-produced; key stays in OpenCode's auth store). Calibration on the 4 archived editions (07-19..07-22): scores 1.00 / 0.90 / 0.90 / 0.90, all shadow-PASS. Signal quality on day one: one real catch (07-22 has bare unlinked tickers in take bodies — verified true, violates the briefing spec), one rubric-wording gap (R4 conflates content phrases like "GA unconfirmed" with publication-date hedges — revision candidate per invariant 6), one judge inconsistency (R10 marked fail with evidence that says pass — logged, this is what shadow mode measures). Probe lesson recorded: judge.py must run check-side (orchestrator), never inside a sandboxed worker — worker sandboxes cannot append the shadow log, and the script now exits 2 loudly in that case.

## Phase 2.5 — Globalize read-side bootstrap (before Phase 3; ~1 session)

Slotted 2026-07-24. Gap: agents only consult Open Brain when Ed directs them — the read-side
adapter SPEC-activation §4 (C11) designed is installed solely in the AI-Memory-System project
CLAUDE.md; global sessions start memory-blind. Design lives in the AI-Memory-System repo; this
item is the install/sequencing home.

- Three-layer recall stack (agreed 2026-07-24): (A) deterministic session-start cold-boot
  globally, (B) Tier-1 live-retrieval skill unchanged for mid-session recall — explicitly NOT
  per-prompt retrieval (noise/latency; honest-expectations clause), (C) Tier-2 manifest as
  fixed stage 0 of every recurring task and Phase-3 harness.
- Cross-agent rule: Ringer workers never read Open Brain; the orchestrator assembles context
  into worker specs. Direct non-Claude readers remain a memory-system Phase 4 feature.
- Mechanism for (A) — DECIDED 2026-07-24: **B1** — SessionStart hook injects the cold-boot
  *instruction*; the model makes the gated MCP call itself. No credentials in the hook, one
  server-side enforcement point (scope gate + activation_audit) preserved, firing measurable.
  One-line global CLAUDE.md backstop for surfaces where hooks don't run. B2 (hook curls the
  Edge Function directly, key in macOS Keychain) is the escalation path only if measured
  firing rate < 95% — taken with a mini-eval, not pre-emptively.
- **Status (2026-07-24): INSTALLED.** Canonical script `AI-Memory-System/hooks/coldboot-bootstrap.sh`
  (v1.0) → installed at `~/.claude/hooks/`, wired as a second SessionStart hook in
  `~/.claude/settings.json` (10s timeout; echo-only, fail-open by construction). Backstop line
  added to global CLAUDE.md. `cold_boot_index` verified live from this session (default scope,
  sub-second, 722 activatable rows indexed).
- Exit criteria: new ad-hoc session calls `cold_boot_index` unprompted; firing rate ≥95%
  measured from `activation_audit` after ~2 weeks; 5s timeout fail-open honored.

## Phase 2.6 — Escalation policy + sampling plan (before Phase 3; ~1 session)

Slotted 2026-07-24 (adversarial review). Gap: owner attention is the scarcest resource in the
system and the only one not instrumented — every agent re-derives when to interrupt Ed, and
review is all-or-nothing (review-everything now, review-nothing after judge graduation).

- **One decision-rights contract**, versioned here as `ESCALATION-POLICY.md`, classifying every
  decision an agent can hit into four lanes:
  1. **Auto-proceed + log** — reversible, in-spec, covered by an executed check.
  2. **Batch to digest** — noteworthy, not blocking; lands as a digest line, never an interrupt.
  3. **Block-and-ask** — scope changes, irreversible or outward-facing actions, spend above threshold.
  4. **Never automate** — permanent human gates (prospect-facing sends, financial actions, phase starts).
- **Sampling plan** replaces review-everything after judge graduation: audit N% of *passing*
  artifacts, escalate the rate when a sample fails, decay it when clean. Counters Goodhart on
  executed checks — quality dimensions not encoded in the check otherwise degrade silently.
- **Eval-log amendment (effective immediately):** every reviewed failure gets tagged
  `fault: spec | worker | check`, so the flywheel can separate ambiguous specs from weak models
  from broken checks. Without attribution the scoreboard can't compound.
- **Metric:** Ed-interrupts per build, tracked alongside tokens — trending down without
  under-asking incidents.
- The policy is an input to every Phase-3 harness spec and every scheduled-task prompt:
  enforced by manifest/harness design (agents read it at dispatch), not by model memory.
- **Exit criteria:** policy file committed; the four lanes referenced from ≥1 live manifest and
  ≥1 scheduled task; sampling active on the first post-graduation judge workload; `fault` field
  appearing in new eval rows.
- **Status (2026-07-24): POLICY BUILT — `ESCALATION-POLICY.md` v1.1 committed.** Parameters set
  by Ed ($5/objective gate, evening Slack digest, 20%→5% sampling, all-outbound Lane 3).
  Hardened same-day by a 3-lens adversarial Ringer swarm (Codex abuse / GLM coherence / Kimi
  K2.7 enforceability — Kimi's first audition, first-try pass): 31 findings, confirmed ones
  folded into v1.1, incl. two P1 spec-contradictions (Lane-3 scope-widening line vs
  SPEC-activation's silent standing scopes; Class-2 repairs → Lane 2, not 3). **Wiring
  (2026-07-24, Ed's Lane-3 yes):** new `evening-digest` scheduled task (daily 7:05 PM) owns the
  Lane-2 mechanics — reads `runs/digest.jsonl`, severity-gates, delivers the single Slack
  message to Ed, marks expiring/stale, Sunday interrupt+sampling rollup; references the policy
  by path (scheduled-task exit criterion MET). Digest seeded with 3 standing items.
  **Remaining for exit:** policy reference in the next live manifest; sampling activates at
  first judge graduation; Ed to click "Run now" once on `evening-digest` to prestage tool
  permissions (the Phase-4a lesson).

## Phase 3 — Presales harness (weeks 6+)

- Claude Agent SDK. Candidate: gap-analysis pipeline (intake requirements → requirement matrix → ratings → internal + external docs).
- Opinionated adapters (exact fields per stage), draft-only tool policies, artifact store for cross-run memory.
- Parallelizable stages dispatch through Ringer manifests with judge checks.
- Permanent human gate on anything prospect-facing, regardless of judge score.
- Build the harness *with* the agent so the agent can maintain it (Pattern 3).
- **Requirement (added 2026-07-24) — integration gate:** a final stage merges all passing tasks
  and executes the *system-level* check (full suite / end-to-end run) before the build counts as
  done. Task-level exit 0 is not build-level proof; worktree merge conflicts surface here, not at
  delivery.
- **Requirement (added 2026-07-24) — security lint:** the default check template for any worker
  code that gets committed includes a mechanical secrets/dependency scan.
- **Context stage (added 2026-07-24, per Phase 2.5):** stage 0 of every harness is a Tier-2
  Open Brain manifest; workers never read the Brain — the orchestrator injects context.

## Phase 4 — Loops upgrade + router (later)

- Rewrite scheduled tasks as loop specs (trigger, sources, memory, safe actions, stop points, record, handoffs) with an attention-layer summary: ran clean / changed / repaired / needs judgment / stopped on failed check.
- Chief-of-Agents router built only once `./ringer.py models` has real per-task-type history.
- **(added 2026-07-24) Attention layer upgraded to a proposal queue:** the system maintains the
  backlog (capstone open-items, repo TODOs, standing flags) and proposes next swarm manifests
  with cost estimates; Ed approves a queue instead of initiating every build. Inverts intake —
  arguably the router's real MVP.
- **(added 2026-07-24) Routing economics:** extend the scoreboard to **cost per verified pass**
  (pass rate per dollar, queryable from existing eval rows), and track interactive-session vs
  headless-run spend — moving workloads to headless + digest + exception escalation is the
  single biggest token lever available.
- **Status (2026-07-27): ATTENTION-LAYER PILOT LIVE (pulled forward, Ed's Lane-3 yes).**
  Trigger: Ed had no unified view of routine health — per-run Slack notifications only, and a
  silently-missed run was invisible. Shipped: `ops-watcher` scheduled task (daily 8:04 AM) +
  deterministic health engine `ops/watch.py` + generated `mission-control.html` dashboard.
  The engine computes per-routine health (OK / in-window / MISSED / disabled) from cron
  schedule vs `lastRunAt` — no notification parsing as primary signal — plus digest-queue
  aging; the watcher routes per ESCALATION-POLICY.md severity gate (urgent → one Slack DM;
  noteworthy → Lane-2 digest rows delivered by evening-digest; healthy days → dashboard
  update only, no ping). Loop-spec rewrite, proposal queue, and router remain open.

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
- Phase 2.5: bootstrap firing rate ≥95% from `activation_audit` (~2 weeks of data).
- Phase 2.6: Ed-interrupts per build measured and trending down; sampled-audit failure rate low and stable.
- Phase 3: gap-analysis cycle time vs. baseline; zero re-explaining of job setup per run.
- Standing: plan-cap hits on mechanical work down; review time per accepted artifact down.
- Standing (added 2026-07-24): cost per verified pass per model × task type visible; share of work run headless vs. interactive trending up.
