# AGENTS.md — guide for AI agents working in this repo

This file is the canonical entry point for any AI agent (Claude Code, Cowork, Codex, etc.)
asked to **use, reference, extend, or rebuild** this project. Read it before acting.

## What this repo is

The planning and build home for a personal AI orchestration layer: batch-dispatching work to cheap parallel worker models with executable or judge-based verification, layered bottom-up (Ringer → judge checks → harnesses → router). No runtime code yet — the current deliverables are the build plan, the judge-check spec, and reference manifests.

Design in one line: **frontier model writes specs and reviews; cheap verified workers execute; every attempt logs to an eval history that eventually drives routing.**

## File map

| Path | Committed? | Purpose |
|---|---|---|
| `AGENTS.md` | yes | This guide. |
| `README.md` | yes | Human quickstart. |
| `llms.txt` | yes | Machine-readable index. |
| `BUILD-PLAN.md` | yes | Architecture, phased plan, decisions, risks, metrics. |
| `SPEC-judge-check.md` | yes | Interface contract for LLM-judge checks (Phase 2). |
| `SPEC-self-healing-loop.md` | yes | Sentinel/repair pattern for scheduled jobs (Phase 4a). |
| `samples/sample.swarm.json` | yes | Scrubbed reference manifest. |
| `CHANGELOG.md` | yes | Dated change log. |
| `manifests/` | **no (gitignored)** | Real swarm manifests — reference live work and client context. |
| `runs/`, `*.jsonl`, `*.log` | **no (gitignored)** | Eval logs and run artifacts — machine-local history. |
| `CONFIG.local.md` | **no (gitignored)** | Real values for scrubbed placeholders. |

## The data contract (swarm manifest + judge check)

The stable interface is the Ringer manifest task object, extended by this project's judge-check convention (full detail in `SPEC-judge-check.md`):

```json
{
  "key": "briefing-2026-07-15",
  "spec": "Self-contained brief the worker executes.",
  "check": "python3 checks/judge.py --rubric rubrics/briefing.md --artifact out/briefing.md",
  "expect_files": ["out/briefing.md"],
  "verified": "Judge scored the briefing >= threshold against the briefing rubric.",
  "task_type": "research-briefing",
  "engine": "opencode",
  "model": "<cheap model>",
  "timeout_s": 900
}
```

Rules an agent must preserve:
- A check exits 0 **only** on a verified artifact; worker self-reports are never evidence.
- The judge model is **never** the model that produced the artifact.
- Failure output must print WHY (the rubric line that failed) — it feeds the retry prompt.
- Judge checks gate nothing until shadow-mode agreement ≥80%; externally facing deliverables always require a human gate.
- Eval logs are append-only; never rewrite history.

## How it works

1. Owner (or an orchestrating agent in Claude Code/Cowork) drafts a manifest of 2–4 independent tasks — native Mac, in a Ringer clone.
2. `./ringer.py lint` then `./ringer.py run`: parallel cheap workers execute, checks verify, one informed retry on failure.
3. Judge-checked tasks call a check script that sends artifact + rubric to a judge model and exits 0/1 with printed reasons.
4. Every attempt lands in the local eval JSONL; `./ringer.py models` turns history into routing.

## How to extend

- **New deliverable type:** add a rubric under `rubrics/`, a `task_type` name, and a sample manifest entry; follow `SPEC-judge-check.md`.
- **New phase decision:** update `BUILD-PLAN.md` and add a `CHANGELOG.md` entry in the same commit.
- **New worker lane:** it's a TOML engine block in the Ringer clone's config, not code in this repo — document the lane choice in `BUILD-PLAN.md`.

## Privacy — hard rules

- Never commit real manifests, eval logs, rubrics containing client/prospect names, employer-specific requirement text, emails, tokens, or keys. Public repo → placeholders only; real values live in gitignored `CONFIG.local.md`.
- Commit scrubbed `samples/` so the repo previews without leaking live work.

## Verification gates (run before declaring a change done)

1. `grep -rniE "kloudg.n|@gmail|xoxb-|\bsk-[a-z0-9]{8,}|api[_-]key\s*[:=]" --exclude=CONFIG.local.md --exclude=AGENTS.md .` returns no real identifiers in committed files (AGENTS.md excluded because this gate line matches itself; eyeball it manually).
2. Any committed sample manifest passes `./ringer.py lint` in a Ringer clone.
3. README updated and `CHANGELOG.md` has a dated entry for every `feat`/`fix`/`data` commit.
4. File map above still matches the working tree.
