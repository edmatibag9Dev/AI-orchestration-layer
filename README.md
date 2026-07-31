# AI Orchestration Layer

A phased orchestration stack: a frontier model plans and reviews, cheap verified workers execute, and every layer is built bottom-up on evidence from an eval log — Ringer dispatch first, LLM-judge verification second, workflow harnesses third, a Chief-of-Agents router last.

## Overview / Purpose

This repo is the planning and build home for the next layer of a personal AI harness stack. The existing foundation (memory layer, skills, scheduled tasks) handles recurring individual jobs; this project adds the orchestration layer above it — dispatching batches of work to inexpensive parallel worker models, verifying every result, and accumulating the pass-rate history that eventually makes routing a query instead of a debate. It exists because frontier-plan token caps are regularly hit on mechanical work, and because the four architecture patterns in circulation (batch dispatcher, harness, loop-of-loops, router) are usually conflated when they should be layered.

## Features

- **Phased build plan** (`BUILD-PLAN.md`): Ringer on code work → LLM-judge check pattern → presales harness → loops upgrade + router, with exit criteria and kill signals per phase.
- **Judge-check specification** (`SPEC-judge-check.md`): the interface for extending Ringer's exit-code verification contract to judgment work (documents, research, briefings) via rubric-scoring judge models — including mandatory shadow-mode calibration.
- **Escalation policy** (`ESCALATION-POLICY.md`): the decision-rights contract (Phase 2.6) — four lanes (auto-proceed+log / digest / block-and-ask / never-automate), post-graduation sampling plan, fault attribution, and the owner-interrupt metric. v1.1 hardened by a 3-model adversarial review swarm the day it was written.
- **Self-healing loop specification** (`SPEC-self-healing-loop.md`): the sentinel/repair pattern that lets scheduled jobs diagnose and fix their own transient failures unattended — two-error-class rule, immutable gates, append-only repair log, recurrence tripwire. Piloted live on a daily dashboard job 2026-07-15.
- **Ops Watcher + Mission Control** — built here as the Phase 4 attention layer (live 2026-07-27), **extracted 2026-07-28 to its own repo `Mission-Control-Dashboard`**. The escalation wiring stays: worker routines file Lane-2 findings into this repo's `runs/digest.jsonl` and the `evening-digest` task delivers them; Mission Control reads the queue cross-repo.
- **Sample manifest** (`samples/sample.swarm.json`): a reference Ringer manifest showing spec / check / expect_files / verified fields, including one judge-checked task.
- **Verification-first design**: exit code 0 or a calibrated judge verdict are the only accepted proofs; worker self-reports are never trusted.

## Files

| File | Role |
|---|---|
| `AGENTS.md` | Canonical guide for AI agents working in this repo — file map, data contract, invariants. |
| `README.md` | This human quickstart. |
| `llms.txt` | Machine-readable index. |
| `BUILD-PLAN.md` | Architecture, phased plan, decisions, risks, success metrics. |
| `ESCALATION-POLICY.md` | Decision-rights contract: four lanes, sampling plan, fault attribution, interrupt metric (Phase 2.6). |
| `SPEC-judge-check.md` | Interface contract for the LLM-judge check pattern (Phase 2). |
| `SPEC-self-healing-loop.md` | Sentinel/repair pattern for scheduled jobs (Phase 4a — pilot live). |
| `checks/judge.py` | LLM-judge runner (shadow scoring + owner-verdict logging). |
| `checks/verdict.sh` | One-line owner verdict: `checks/verdict.sh today pass`. |
| `checks/agreement.py` | Judge/owner agreement report — the ≥80% graduation instrument. |
| `checks/rubric-regression.sh` | Regression test proving a revised rubric line still fails a real violation. |
| `rubrics/morning-briefing.md` | Briefing rubric (v2, 2026-07-31). Line IDs stable across versions. |
| `samples/sample.swarm.json` | Reference manifest (committed sample; real manifests are gitignored). |
| `CONTRIBUTING.md` | Commit format + README standards (canonical copy). |
| `CHANGELOG.md` | Dated log of notable changes. |
| `manifests/` | Real swarm manifests (gitignored — reference live work). |
| `runs/`, `*.jsonl` | Eval logs and run artifacts (gitignored). |

## How to Use

```bash
# Phase 1 prerequisite: Ringer itself (separate clone, not vendored here)
git clone https://github.com/NateBJones-Projects/ringer
cd ringer && ./ringer.py demo

# Then draft manifests in this repo's manifests/ dir, lint, and run:
./ringer.py lint ../AI-orchestration-layer/manifests/<name>.swarm.json
./ringer.py run  ../AI-orchestration-layer/manifests/<name>.swarm.json
```

Start with `BUILD-PLAN.md` for the current phase and its exit criteria. Manifest craft: every check must print WHY it fails (the failure output feeds the retry prompt).

**Mission Control dashboard:** now lives in the `Mission-Control-Dashboard` repo — open `~/Documents/Claude/Projects/Mission-Control-Dashboard/mission-control.html`.

## Data Sources

Architecture synthesized from: the Ringer guide (unlock-ai.natebjones.com/guides/ringer, verified 2026-07-10), Claire Vo's harness-anatomy build (How I AI), Nate B. Jones's loop-of-loops and 4-Patterns videos, and the steer-vs-dispatch Run Spec framework. Source syntheses live in the owner's knowledge base, not in this repo.

## Known Limitations / Workarounds

- The LLM-judge false-pass rate is unknown until shadow-mode calibration completes; the judge gates nothing until judge/owner agreement is ≥80%. Externally facing deliverables keep a permanent human gate regardless.
- **Shadow mode measures nothing without owner verdicts.** The first 12 shadow rows (2026-07-19..07-30) accumulated with zero owner verdicts — `--owner-verdict` existed but was never surfaced where the owner reads the artifact, so the agreement rate stayed unmeasurable rather than merely unmet. Fixed 2026-07-31 (`checks/verdict.sh` + a mandatory prompt line in the briefing pipeline); `python3 checks/agreement.py` reports the rate, the disagreements, and the unpaired backlog.
- Rubric revisions can over-correct: removing a false positive can leave a line that no longer fails anything. `checks/rubric-regression.sh` injects a known violation and asserts the line still fires.
- Worker CLIs must be kept current: an out-of-date Codex CLI (0.139.0) was rejected wholesale by its own default model (`gpt-5.6-sol` requires a newer CLI) — every demo task failed until the CLI self-updated to 0.144.4.
- Ringer worktree footgun: passing tasks get their worktrees deleted — checks must copy deliverables out before exiting 0.
- A Cowork sandbox cannot run git on mounted folders; commits and pushes are run by the owner in Terminal.

## Build Notes

Phase 1 plumbing is live as of 2026-07-15: Ringer demo verified, and two worker lanes proven end to end — Codex CLI (plan-billed) and OpenCode + OpenRouter (`z-ai/glm-5.2`, ≈$0.01 per verified task; key held in OpenCode's auth store, never in this repo). As of 2026-07-22 the first runtime code lives here: `checks/judge.py` (the SPEC-judge-check LLM-judge, live in shadow mode against the morning briefing) and `rubrics/morning-briefing.md` (rubric **v2** as of 2026-07-31, revised from 12 shadow rows); shadow verdicts accumulate in the gitignored `runs/judge-shadow.jsonl`, and owner verdicts land beside them via `checks/verdict.sh`. Phase 1 adopts Ringer as-is (single-file Python orchestrator, Python 3.11+) rather than building a dispatcher; Phase 2 adds the only novel component (judge checks) as plain shell/Python scripts conforming to `SPEC-judge-check.md`; Phase 3 builds one harness on the Claude Agent SDK. The router is deliberately last: routing decisions come from accumulated per-model, per-task-type pass rates, not intuition.

## Update / Refresh Instructions

Update `BUILD-PLAN.md` when a phase completes or a decision changes, add a dated `CHANGELOG.md` entry, and refresh this README on every `feat`/`fix`/`data` commit. Real manifests and eval logs stay out of git; commit a scrubbed sample instead when a new pattern is worth preserving.

---
*Last updated: 2026-07-31 (rubric v2 + owner-verdict wiring)*
