# AGENTS.md — guide for AI agents working in this repo
> Standard: REPO-STANDARD 2026-10-09 · Commits, README and staging: CONTRIBUTING.md

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
| `project.toml` | yes | This repo's own project manifest (SPEC-project-manifest): standing memory scope, preferred skills, Ringer task types, review gates (design review required), owned routines, done criteria and checks. Read at session start by the SessionStart hook. `[memory]` and `[review]` change only with the owner's OK. |
| `llms.txt` | yes | Machine-readable index. |
| `BUILD-PLAN.md` | yes | Architecture, phased plan, decisions, risks, metrics. |
| `docs/architecture-flow.html` | yes | Interactive engagement-lifecycle stepper (before / after / target views, status-as-of date). Self-contained single file; opens from disk. Keep it in step with BUILD-PLAN.md. |
| `SPEC-judge-check.md` | yes | Interface contract for LLM-judge checks (Phase 2). |
| `SPEC-self-healing-loop.md` | yes | Sentinel/repair pattern for scheduled jobs (Phase 4a). |
| `SPEC-presales-harness.md` | yes | Phase 3 harness design: stage map, adapters, tool policy, gates, checks. |
| `SPEC-project-manifest.md` | yes | `project.toml` contract (DRAFT, not built): fields, examples, SessionStart hook + project-start skill + validator readers, invariants. |
| `ESCALATION-POLICY.md` | yes | Decision-rights contract: four escalation lanes, sampling plan, fault attribution (Phase 2.6). |
| `checks/judge.py` | yes | LLM-judge check runner implementing SPEC-judge-check (Phase 2, shadow mode). Also logs owner verdicts (`--owner-verdict`). |
| `checks/verdict.sh` | yes | Owner-verdict shortcut — the human half of shadow mode (`verdict.sh today pass`). |
| `checks/agreement.py` | yes | Judge/owner agreement report — the Phase 2 graduation instrument (≥80% gate). |
| `checks/rubric-regression.sh` | yes | Proves a revised rubric line still FAILS a real violation (anti-over-correction test). |
| `harness/run.py` | yes | Phase 3 stage-3 driver: gate → batch → Ringer manifest → merge → integration gate. |
| `checks/rate_check.py` | yes | Stage-3 rating check — resolves every Green/Amber citation verbatim against the library. |
| `checks/matrix_check.py` | yes | Integration gate — system-level check on the merged matrix (Phase 3 requirement). |
| `checks/fault_report.py` | yes | Reads the fault-attribution sidecar: class counts, model×task_type signal, unattributed backlog. |
| `checks/manifest_check.py` | yes | `project.toml` validator (SPEC-project-manifest §5.3): nine rules — parse, version, required/typed/enums, slug, no-repo reason, engagement root outside git, trigger anchors resolve, no Sensitive standing scope, publishable scrub. Exit 0/1/2. |
| `checks/test_manifest_check.py` | yes | Regression test for the validator: every fixture plus three run-time cases. Must print `15/15 cases passed`. |
| `checks/fixtures/manifest/` | yes | Validator fixtures: `valid.toml`, one `fail-*.toml` per rule, and `SKILL.fixture.md` for trigger anchors. Generic placeholders only. |
| `hooks/project-manifest-bootstrap.sh` | yes | SessionStart hook (SPEC-project-manifest §5.1): finds `project.toml`, prints one instruction block under 250 tokens. Echo-only, fail-open, exit 0 always. Canonical copy; the installed copy lives in `~/.claude/hooks/` (installed 2026-10-25 as the third SessionStart hook). |
| `checks/test_manifest_bootstrap.py` | yes | Regression test for the hook: fixtures, both spec examples, nested folders, retired project, garbage payload, missing python3, `[done] checks` never run. Must print `13/13 cases passed`. |
| `skills/project-start/SKILL.md` | yes | project-start skill (SPEC-project-manifest §5.2): classify, repo or reasoned no-repo, propose values, owner confirms `[memory]`/`[review]`, write, show the hook block, record. Installed 2026-10-25 (`~/.claude/skills/project-start` links here). |
| `skills/project-start/scripts/write_manifest.py` | yes | The skill's writer: detects git and `origin`, refuses Sensitive buckets and existing manifests, checks the engagement template, writes `project.toml.new`, validates, renames only on pass. |
| `checks/test_project_start.py` | yes | Regression test for the writer on throwaway folders, ending with the hook end to end. Must print `13/13 cases passed`. |
| `rubrics/` | yes | Judge rubrics, one per deliverable type. Line IDs are stable across versions. |
| `samples/sample.swarm.json` | yes | Scrubbed reference manifest. |
| `samples/sample.requirements.json` | yes | Scrubbed stage-3 input adapter sample. |
| `maintenance/repo_sweep.py` | yes | Monthly Maintenance Review Phase C — repo-standard sweep of every owner repo (local or staging clone). |
| `maintenance/release_notes.py` | yes | Phase A — Claude Code changelog since the last saved version, tagged and prioritized. State lives in gitignored `runs/maintenance-state.json`. |
| `maintenance/prep_branch.sh` | yes | Phase D — fix branch in a separate worktree under the staging dir; never pushes. |
| `scheduled-tasks/skills-inventory-review/SKILL.md` | yes | Scrubbed backup of the Monthly Maintenance Review scheduled task (task ID unchanged: skills-inventory-review). Reference copy only — the runtime master lives at `~/.claude/scheduled-tasks/skills-inventory-review/SKILL.md` and is what actually executes. |
| `scheduled-tasks/ops-watcher/SKILL.md` | yes | Scrubbed backup of the daily 8:00 AM run-health sweep (heartbeat monitoring, dashboard regen, escalation per ESCALATION-POLICY.md). Reference copy only — runtime master under `~/.claude/scheduled-tasks/`. |
| `scheduled-tasks/evening-digest/SKILL.md` | yes | Scrubbed backup of the daily 7:05 PM Lane-2 digest assembly/delivery routine. Reference copy only — runtime master under `~/.claude/scheduled-tasks/`. |
| `scheduled-tasks/action-item-triage/SKILL.md` | yes | Scrubbed backup of the daily action-item triage (auto-close via Open Brain evidence, before wiki regen). Reference copy only — runtime master under `~/.claude/scheduled-tasks/`. |
| `scheduled-tasks/daily-ai-morning-briefing/SKILL.md` | yes | Scrubbed backup of the daily morning AI briefing routine (judged by this repo's `checks/judge.py` + `rubrics/morning-briefing.md`). Reference copy only — runtime master under `~/.claude/scheduled-tasks/`. |
| `scheduled-tasks/fleet-sentinel/SKILL.md` | yes | Scrubbed backup of the hourly fleet sentinel — the only component authorized to restart routines (Phase 4b). Reference copy only — runtime master under `~/.claude/scheduled-tasks/`. |
| `CONTRIBUTING.md` | yes | Commit format + README standards (canonical copy). |
| `CHANGELOG.md` | yes | Dated change log. |
| `manifests/` | **no (gitignored)** | Real swarm manifests — reference live work and client context. |
| `runs/`, `*.jsonl`, `*.log` | **no (gitignored)** | Eval logs and run artifacts — machine-local history. |
| `reports/` | **no (gitignored)** | Skills-review output — carries local paths and personal identifiers. |
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

## Verification gates

Run before declaring a change done:

1. `grep -rniE "kloudg.n|@gmail|xoxb-|\bsk-[a-z0-9]{8,}|api[_-]key\s*[:=]" --exclude=CONFIG.local.md --exclude=AGENTS.md .` returns no real identifiers in committed files (AGENTS.md excluded because this gate line matches itself; eyeball it manually).
2. Any committed sample manifest passes `./ringer.py lint` in a Ringer clone.
3. README updated and `CHANGELOG.md` has a dated entry for every `feat`/`fix`/`data` commit.
4. File map above still matches the working tree.
5. Staged named paths only, and `git diff --cached --name-status --diff-filter=D` prints nothing — staging rules: [CONTRIBUTING.md → What to Stage](CONTRIBUTING.md#what-to-stage--never-commit-blindly).
6. `python3 ~/.claude/skills/repo-standard/scripts/repo-check.py .` reports no FAIL lines.
