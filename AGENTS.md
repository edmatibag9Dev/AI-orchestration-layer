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
| `SPEC-presales-harness.md` | yes | Phase 3 harness design: stage map, adapters, tool policy, gates, checks. |
| `ESCALATION-POLICY.md` | yes | Decision-rights contract: four escalation lanes, sampling plan, fault attribution (Phase 2.6). |
| `checks/judge.py` | yes | LLM-judge check runner implementing SPEC-judge-check (Phase 2, shadow mode). Also logs owner verdicts (`--owner-verdict`). |
| `checks/verdict.sh` | yes | Owner-verdict shortcut — the human half of shadow mode (`verdict.sh today pass`). |
| `checks/agreement.py` | yes | Judge/owner agreement report — the Phase 2 graduation instrument (≥80% gate). |
| `checks/rubric-regression.sh` | yes | Proves a revised rubric line still FAILS a real violation (anti-over-correction test). |
| `harness/run.py` | yes | Phase 3 stage-3 driver: gate → batch → Ringer manifest → merge → integration gate. |
| `checks/rate_check.py` | yes | Stage-3 rating check — resolves every Green/Amber citation verbatim against the library. |
| `checks/matrix_check.py` | yes | Integration gate — system-level check on the merged matrix (Phase 3 requirement). |
| `checks/fault_report.py` | yes | Reads the fault-attribution sidecar: class counts, model×task_type signal, unattributed backlog. |
| `rubrics/` | yes | Judge rubrics, one per deliverable type. Line IDs are stable across versions. |
| `samples/sample.swarm.json` | yes | Scrubbed reference manifest. |
| `CONTRIBUTING.md` | yes | Commit format + README standards (canonical copy). |
| `CHANGELOG.md` | yes | Dated change log. |
| `manifests/` | **no (gitignored)** | Real swarm manifests — reference live work and client context. |
| `runs/`, `*.jsonl`, `*.log` | **no (gitignored)** | Eval logs and run artifacts — machine-local history. |
| `CONFIG.local.md` | **no (gitignored)** | Real values for scrubbed placeholders. |

The Phase-4 attention layer (Ops Watcher engine + Mission Control dashboard) was **extracted 2026-07-28** to its own repo: `edmatibag9Dev/Mission-Control-Dashboard` (`~/Documents/Claude/Projects/Mission-Control-Dashboard`). `runs/digest.jsonl` stays here — the Lane-2 queue is owned by ESCALATION-POLICY.md; Mission Control reads it cross-repo.

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
- Agreement is measured over artifacts carrying **both** a judge row and an owner verdict. Judge scores alone measure nothing — a run of clean scores is not calibration evidence.
- Eval logs are append-only; never rewrite history. **Ringer owns `runs.jsonl`'s schema** — fault
  attribution goes to the `fault-attribution.jsonl` sidecar and joins on `(run_id, task_key)`;
  appending foreign rows to the scoreboard would count as "unattributed" and skew routing. Synthetic/test judge runs use `--log <scratch>`; they never touch `runs/judge-shadow.jsonl`.
- Rubric revisions that remove false positives must be shown to still fail a real violation (`checks/rubric-regression.sh`) — never soften a line to clear a failure the producer actually earned.

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
