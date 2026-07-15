# Changelog

All notable changes to AI Orchestration Layer are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); dates are America/Los_Angeles.
Gitignored data/output files are never committed.

## [2026-07-15] — Initial commit: locked architecture plan + Phase 4a pilot live

### Added
- `BUILD-PLAN.md`: four-layer target stack (Ringer → judge checks → harnesses → router), phased build with exit criteria and kill signals; decisions locked in the 2026-07-15 planning session (Ringer first on code work, LLM-judge with shadow-mode calibration, cheap OpenRouter lanes justified by plan caps, router deferred until scoreboard data exists).
- `BUILD-PLAN.md` Phase 4a + `SPEC-self-healing-loop.md`: sentinel/repair pattern for scheduled jobs — two-error-class rule (environmental auto-repaired, spec/logic always escalated), immutable gates, append-only repair log, 3-in-7-days recurrence tripwire, sentinel task as the restart mechanism. **Pilot live 2026-07-15** on a daily dashboard-refresh job; root cause of most manual restarts was permission-stalled runs, fixed by one-time permission prestaging.
- `SPEC-judge-check.md`: LLM-judge check interface — exit codes, mandatory failed-lines output, judge ≠ producer, shadow mode before gating, permanent human gate on external deliverables.
- `AGENTS.md`, `llms.txt`, `README.md`: agent guide with file map, manifest data contract, and verification gates; machine index; human quickstart.
- `samples/sample.swarm.json`: scrubbed reference manifest (exit-code task + judge-checked task).
- `.gitignore`: real manifests, eval JSONL/logs, run artifacts, and `CONFIG.local.md` excluded; scrubbed samples committed instead.
