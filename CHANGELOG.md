# Changelog

All notable changes to AI Orchestration Layer are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); dates are America/Los_Angeles.
Gitignored data/output files are never committed.

## [2026-07-27b] — Attention-layer footers + heartbeat channel (Ed's Lane-3 yes)

### Added
- Attention-layer footer appended to all 6 worker routine prompts (morning briefing,
  longboard, mastermind, 3 earnings-put tasks): (1) noteworthy non-blocking findings →
  Lane-2 rows in `runs/digest.jsonl`; (2) incompletable jobs must declare failure loudly AND
  file a Lane-2 row; (3) every run ends by appending `{task, ts, status: ok|partial|failed,
  note}` to `runs/heartbeat.jsonl`.
- `ops/watch.py` now reads `runs/heartbeat.jsonl`: a run whose `lastRunAt` stamped but whose
  latest heartbeat self-reports failed/partial overrides OK → FAILED/PARTIAL on the dashboard
  and in the escalate summary. Heartbeat absence is neutral (rollout-safe). Verified with a
  synthetic failed heartbeat: status flipped and ESCALATE-CANDIDATE fired; clean state restored.
- ops-watcher prompt updated to investigate FAILED/PARTIAL alongside MISSED.

### Rationale
- Closed two gaps found when Ed asked whether job-discovered issues get flagged: worker
  routines had no knowledge of the digest queue (findings scrolled by in per-run Slack
  notifications), and a run that started then died still read as healthy because `lastRunAt`
  stamps at run start.

## [2026-07-27] — Phase 4 attention-layer pilot: ops-watcher + Mission Control dashboard

### Added
- `ops/watch.py` — deterministic run-health engine (no dependencies): computes per-routine
  health (OK / in-window / MISSED / disabled) from each scheduled task's cron expression vs
  `lastRunAt` in local time, reads the Lane-2 `runs/digest.jsonl` queue with day-12/14 aging,
  writes `runs/ops-status.json`, renders the brand-styled `mission-control.html` dashboard,
  and prints an escalation-candidate summary for the watcher agent.
- `ops-watcher` scheduled task (daily 8:04 AM, lives in `~/.claude/scheduled-tasks/`):
  snapshots `list_scheduled_tasks` → runs the engine → investigates misses via session
  transcripts + Slack notifications → routes per ESCALATION-POLICY.md (urgent → one Slack DM
  to Ed; noteworthy → Lane-2 digest rows; healthy → dashboard only). Surface-not-fix: task
  changes stay Lane 3.
- AGENTS.md file map trued up: added missing `ESCALATION-POLICY.md`, `checks/judge.py`,
  `rubrics/`, plus the new `ops/watch.py` and gitignored `mission-control.html` rows
  (drift originally flagged 2026-07-12).

### Rationale
- Ed's routine fleet (7 active tasks) had per-run Slack notifications but no aggregate view;
  a missed run was only detectable by noticing an absent notification. This pulls
  BUILD-PLAN Phase 4's "attention layer" forward as a pilot.

## [2026-07-24b] — Phase 2.6 built: ESCALATION-POLICY.md v1.1, adversarially hardened same-day

### Added
- `ESCALATION-POLICY.md` v1.0 → v1.1: four decision lanes with definitions block, severity
  gate on the digest, objective-aggregate spend gate, sampling plan with anti-gaming rules,
  required fault attribution, two-counter interrupt metric, and a Mechanics section naming
  every record, schema, owner, and trigger. Parameters set by Ed: $5/objective spend gate,
  evening Slack digest, 20% sampling start (5% floor), all-outbound = Lane 3.
- Mini-eval: 3-lens adversarial Ringer swarm (`escalation-policy-review`) — Codex
  (abuse/loopholes, 16 findings first-try), GLM 5.2 (spec-coherence vs SPEC-activation /
  SPEC-self-healing / SPEC-judge-check, 4 findings, retry-rescued), Kimi K2.7 on its first
  audition (enforceability, 11 findings, first-try). 31 findings; v1.1 adopts the confirmed
  ones. Top catches: Lane 3 scope-widening line contradicted SPEC-activation's silent
  standing-scope rule; Class-2 repairs were mapped to Lane 3 when the SPEC makes them digest
  items; spend gate was splittable into sub-$5 runs; sampling decay counted zero-sample weeks
  as clean.
- Deliberate rejections recorded: default-branch pushes stay Lane 1 for Ed-owned doc/tool
  repos (interrupt economics; force/tags/deploy-triggering pushes excluded); full single-use
  approval bookkeeping deferred (binding-to-instance rule adopted instead); Kimi's P0 grades
  re-leveled to P1 (measurability, not safety).

## [2026-07-24] — Phase 2.5 installed (read-side bootstrap) · Phase 2.6 slotted (escalation policy)

### Added
- `BUILD-PLAN.md` Phase 2.5 — globalize read-side bootstrap: three-layer recall stack
  (session-start cold-boot / Tier-1 skill / Tier-2 manifest as harness stage 0), mechanism B1
  decided and INSTALLED same day (SessionStart hook injects the cold-boot instruction; no
  credentials; canonical script lives in the AI-Memory-System repo). Workers never read Open
  Brain — the orchestrator injects context.
- `BUILD-PLAN.md` Phase 2.6 — escalation policy + sampling plan, slotted from the 7/24
  adversarial review: four decision lanes (auto-proceed / digest / block-and-ask /
  never-automate), sampled audit of passing work post-judge-graduation, eval-log fault
  attribution (`spec|worker|check`, effective immediately), Ed-interrupts-per-build metric.
- Phase 3 requirements: integration gate (system-level check after merge), security lint in
  the default check template, Tier-2 manifest as stage 0.
- Phase 4: attention layer upgraded to a proposal queue; routing economics extended to cost
  per verified pass and headless-vs-interactive spend.

### Notes
- Adversarial-review thesis recorded: the stack is excellent at verifying work, still
  artisanal at deciding what work happens and what deserves the owner's eyes.
- Architecture flow chart published as a status-coded artifact (live / calibrating / planned /
  gap) for visual review.

## [2026-07-22b] — Phase 2 started: LLM-judge shadow mode live on the morning briefing

### Added
- `checks/judge.py` — SPEC-judge-check implementation (exit 0/1/2, FAILED LINES block,
  `--shadow` logging to gitignored `runs/judge-shadow.jsonl`, `--owner-verdict` agreement rows).
  Judge transport: OpenCode CLI (OpenRouter key never leaves its auth store).
- `rubrics/morning-briefing.md` v1 — 10 judge-checkable requirements distilled from the
  briefing editorial spec v2.5.
- Calibration: 4 archived editions scored in shadow mode (1.00/0.90/0.90/0.90); first real
  catch on day one (unlinked tickers in take bodies, verified) plus one rubric-revision
  candidate (R4 wording) and one logged judge inconsistency (R10).

## [2026-07-22] — Phase 1 COMPLETE: two real swarms verified, 21 repos fixed

### Added
- `BUILD-PLAN.md` Phase 1 exit status: `install-agent` run; `repo-backlog-sweep` (4 tasks) and
  `agents-drift-fix` (20 tasks) both fully verified by executed checks and reviewed in Ringside;
  eval log at 46 rows with first real per-model routing evidence (docs: GLM 0.76 first-try ~23k
  tok/task, Codex 0.83 first-try ~78k tok/task).

### Fixed (via verified swarm tasks, in their own repos)
- ai-task-manager AGENTS.md file map regenerated (was drifted since standardization).
- Token-Burn-Dashboard usage-breakdown staleness root-caused (`run-all.sh` omitted
  `ingest-usage.mjs` from its invocation list) and fixed the same day.
- 20 further repos' AGENTS.md File maps regenerated to the `Path | Committed? | Purpose`
  standard after a 25-repo drift audit found 21 drifted.

## [2026-07-15] — Phase 1 plumbing proven: demo verified, OpenRouter lane live

### Added
- `CONTRIBUTING.md`: canonical commit-format and README standards (was missing from the initial scaffold; required by the repo standard).
- `BUILD-PLAN.md` Phase 1 status block: Ringer cloned and demo verified in Ringside; OpenCode 1.18.2 + OpenRouter lane wired (Seatbelt wrapper, default `z-ai/glm-5.2`) and proven with a one-task manifest — executed check PASS on attempt 1, 9,480 tokens, ≈$0.012. Grok lane declined. Remaining for Phase 1 exit: first real 2–4-task manifest + `install-agent`.

### Changed
- `README.md`: Build Notes reflect live Phase 1 plumbing; Known Limitations adds the worker-CLI currency lesson (Codex 0.139.0 rejected by its own default model until self-updated to 0.144.4); Files table includes `CONTRIBUTING.md`.
- `AGENTS.md`: file map includes `CONTRIBUTING.md`.

### Fixed
- `samples/sample.swarm.json`: top-level field was `name`, but Ringer requires `run_name` — the committed sample failed `./ringer.py lint` (verification gate 2). Renamed; now lints clean (2 tasks) against Ringer at 2026-07-15.

## [2026-07-15] — Initial commit: locked architecture plan + Phase 4a pilot live

### Added
- `BUILD-PLAN.md`: four-layer target stack (Ringer → judge checks → harnesses → router), phased build with exit criteria and kill signals; decisions locked in the 2026-07-15 planning session (Ringer first on code work, LLM-judge with shadow-mode calibration, cheap OpenRouter lanes justified by plan caps, router deferred until scoreboard data exists).
- `BUILD-PLAN.md` Phase 4a + `SPEC-self-healing-loop.md`: sentinel/repair pattern for scheduled jobs — two-error-class rule (environmental auto-repaired, spec/logic always escalated), immutable gates, append-only repair log, 3-in-7-days recurrence tripwire, sentinel task as the restart mechanism. **Pilot live 2026-07-15** on a daily dashboard-refresh job; root cause of most manual restarts was permission-stalled runs, fixed by one-time permission prestaging.
- `SPEC-judge-check.md`: LLM-judge check interface — exit codes, mandatory failed-lines output, judge ≠ producer, shadow mode before gating, permanent human gate on external deliverables.
- `AGENTS.md`, `llms.txt`, `README.md`: agent guide with file map, manifest data contract, and verification gates; machine index; human quickstart.
- `samples/sample.swarm.json`: scrubbed reference manifest (exit-code task + judge-checked task).
- `.gitignore`: real manifests, eval JSONL/logs, run artifacts, and `CONFIG.local.md` excluded; scrubbed samples committed instead.
