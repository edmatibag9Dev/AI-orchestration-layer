# Changelog

All notable changes to AI Orchestration Layer are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); dates are America/Los_Angeles.
Gitignored data/output files are never committed.

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
