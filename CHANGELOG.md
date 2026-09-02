# Changelog

All notable changes to AI Orchestration Layer are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); dates are America/Los_Angeles.
Gitignored data/output files are never committed.

## [2026-09-02] — Scrub the two unscrubbed scheduled-task backups

The monthly skills-inventory-review of 2026-09-01 (finding F1) found that
`scheduled-tasks/ops-watcher/SKILL.md` and `scheduled-tasks/fleet-sentinel/SKILL.md` were
committed byte-identical to their runtime masters. Both were added during Phase 4b work on
2026-08-31, after the 2026-08-18 batch scrub that covered the other four files, so the scrub
never reached them. This repo is public.

### Fixed
- **`scheduled-tasks/ops-watcher/SKILL.md`, `scheduled-tasks/fleet-sentinel/SKILL.md`** —
  scrubbed to the convention already documented in README "Maintenance": 9 absolute
  `/Users/<account>/` paths to `~/`, the owner's first name to "the owner", the owner's email
  to `<OWNER_EMAIL>`, and the launchd label `com.<account>.fleet-watchdog` to
  `com.<OWNER>.fleet-watchdog`. Instruction content is unchanged — the diff is substitutions
  only, so both files remain accurate reference copies.
- Retained deliberately, matching the already-scrubbed `daily-ai-morning-briefing` backup:
  the Slack channel names `#ops-control` and `#ai-briefing` and the helper path
  `~/.claude/lib/slack_alert.py`. These are non-identifying and load-bearing for the
  instructions; no webhook URL or secret value has ever been in these files.

### Known limitations
- **This does not remove the data from git history.** The values remain reachable in commits
  `46ff440` (ops-watcher, 2026-08-31) and `546350a` (fleet-sentinel, 2026-08-31). Clearing
  history needs a rewrite or a fresh repo — the owner's call, not taken here.
- `com.<account>.slack-ops-poller` still appears twice in `SPEC-self-healing-loop.md`, and
  the GitHub account name appears in `AGENTS.md` and `CHANGELOG.md`. Out of scope for this
  commit; surfaced rather than changed.

## [2026-08-31] — Phase 4b: fleet sentinel + Slack command channel

Ed's decisions recorded same day, after the 8/19–8/30 `session_stale_relogin` outage left him
out of office with no way to trigger repairs.

### Added
- **`SPEC-self-healing-loop.md` Phase 4b** — fleet-wide sentinel restarts (2/day cap per
  routine, no-duplicate guard, Class-1 only, briefing noon cutoff, 3-in-7 tripwire) and the
  #ops-control command contract (Ed-only sender, closed grammar, queue file
  `runs/ops-commands.jsonl`, ledger `runs/repair.jsonl`).
- **`scheduled-tasks/fleet-sentinel/SKILL.md`** — backup of the new hourly executor task
  (cron `12 6-21 * * *`): drains the command queue every hour, sweeps + restarts at 9 AM/8 PM.

### Changed
- **`ESCALATION-POLICY.md` → v1.2** — records: fleet sentinel restarts are Lane-1 Class-1
  repairs; #ops-control approved as a standing surface in both directions; `fix` beyond
  re-running a routine's own prompt stays Lane 3 (held for discussion).
- **`scheduled-tasks/ops-watcher/SKILL.md`** backup refreshed: urgent alerts now go to
  #ops-control via the webhook identity (DM fallback until the webhook exists), and the
  watcher checks `repair.jsonl` before flagging something the sentinel already fixed.

## [2026-08-17] — Back up the four orchestration-substance routines

### Added
- Scrubbed backups of `ops-watcher`, `evening-digest`, `action-item-triage`, and
  `daily-ai-morning-briefing` under `scheduled-tasks/`. Selection criterion: of the 21 remaining
  scheduled tasks, 16 carry the attention-layer footer, but only these four have orchestration-layer
  substance — ops-watcher and evening-digest are the two halves of ESCALATION-POLICY.md's delivery
  contract, action-item-triage feeds the dashboard lifecycle, and the morning briefing is judged by
  this repo's own `checks/judge.py` and rubric. Trading, personal-capture, and key-rotation tasks
  were deliberately excluded (wrong repo or unscrubbable substance).

### Changed
- `scheduled-tasks/skills-inventory-review/SKILL.md` re-scrubbed from its runtime master: the
  master's duplicate-scan check now whitelists this repo's scrubbed mirrors (expected-different by
  design; flagged only when the master is newer than the last re-scrub), so the monthly report
  does not raise false drift findings on its own backups.

## [2026-08-17] — Back up the skills-inventory-review routine into the repo

### Added
- `scheduled-tasks/skills-inventory-review/SKILL.md` — a scrubbed backup of the monthly
  skill-library audit. The routine was previously single-copy: it existed only at
  `~/.claude/scheduled-tasks/skills-inventory-review/SKILL.md`, unversioned and unbacked, so a
  machine loss or an accidental overwrite would have taken the instructions with it.
- The routine lands here rather than in a repo of its own because it already depends on this one:
  its attention-layer footer files Lane-2 rows to `runs/digest.jsonl` under the contract in
  `ESCALATION-POLICY.md`, and its heartbeat goes to `Mission-Control-Dashboard`. The instructions
  now sit beside the policy they implement.
- `reports/` added to `.gitignore`. The task writes its output there, and that output quotes local
  absolute paths and (via diff excerpts) the owner's email address — on a public repo that is a
  leak, and the folder was untracked-but-not-ignored, so any `git add .` would have swept it in.

### Notes
- **Backup, not master.** The committed copy is scrubbed (absolute home paths normalized to `~/`,
  owner name replaced with "the owner", employer name generalized to "presales") and therefore differs from the executing file by design.
  The runtime master under `~/.claude/scheduled-tasks/` is authoritative; edit it first, then
  re-scrub into this repo. AGENTS.md and README record this direction so the copy does not quietly
  become the kind of stale mirror the routine itself exists to detect.
- Scrub verified against the AGENTS.md privacy gate: no owner email address, no `/Users/<name>` paths, no keys
  in the committed file. The only differences from the master are six scrubbed lines: two absolute home paths, three owner-name
  references, and one employer name — the last caught by the gate itself, not by the initial scrub pass.
- First run of the routine (2026-08-17) is recorded in the gitignored `reports/`: 13/13 skill
  symlinks intact, CLAUDE.md clean of `@` inline references, zero harness-redundancy true
  positives, and three findings queued to the Lane-2 digest.

## [2026-07-31e] — Fault attribution reaches the scoreboard; workers carry decision rights

### Added
- `checks/fault_report.py` — the **reader** for fault attribution: counts by class, the
  model × task_type breakdown that is the actual routing signal, and the unattributed backlog.
  Built because a log with no reader is write-only data — the same mistake the owner verdicts made.
  First run against the real scoreboard: **26 failures across 58 rows, none attributed.**
- Fault attribution now lands in an append-only **sidecar** `~/.ringer/fault-attribution.jsonl`,
  joined to Ringer's scoreboard on `(run_id, task_key)`. `harness/run.py merge` discovers the
  `run_id` by prefix-matching the manifest's `run_name`, and carries model / task_type / verdict /
  tokens into the run's eval rows.
- `harness/run.py fault` gains `--note` and `--by`, and warns loudly when a batch has no `run_id`
  (the attribution then stays run-local and teaches routing nothing).
- Worker specs now carry a **decision-rights block** derived from `ESCALATION-POLICY.md` v1.1:
  ambiguity is flagged, never resolved by the worker; no outward-facing actions; no scope widening.

### Notes
- **Deliberately NOT appending to `runs.jsonl`.** Ringer owns that schema and its accessors treat a
  row without `model` as "unattributed" — foreign rows would skew the very routing data this is
  meant to sharpen. Recorded in AGENTS.md as an invariant.
- This closes Phase 2.6's last open exit criterion the moment the first real manifest dispatches:
  the policy is now referenced from a live manifest, and the `fault` field has somewhere to land.
- Correction to the previous entry: the earlier claim that stage 3 "finally makes the eval amendment
  live" overstated it — attribution was run-local only until this change.

## [2026-07-31d] — Phase 3 slice built: stage-3 driver, rating check, integration gate

### Added
- `harness/run.py` — the stage-3 driver. `prepare` verifies the human gate, batches the approved
  requirements, writes a self-contained worker spec per batch, and emits a lint-clean Ringer
  manifest whose per-task check is `rate_check.py`. `merge` assembles the matrix and runs the
  integration gate. `fault` attributes a failed batch (`spec|worker|check`).
- `checks/rate_check.py` — six rules with per-requirement failure reasons: completeness (no drops,
  no inventions), vocabulary, **verbatim citation resolution**, path-to-fit on every Amber/Red,
  source-of-truth (evidence resolving outside the library fails), and no Green-at-Low-confidence.
  Reads `.md`/`.txt` and `.docx` (stdlib zip+regex extraction, no dependency); a citation target
  that cannot be read as text FAILS rather than passing unverified.
- `checks/matrix_check.py` — the integration gate: re-runs the per-task rules over the *assembled*
  matrix (so a merge that drops or duplicates records fails), checks RAG-count consistency, and
  scans a prospect-facing artifact for internal-only content.
- `samples/sample.requirements.json` — scrubbed stage-3 input adapter.

### Verified (against the real capability library, not a mock)
- Good fixture with real verbatim citations: **exit 0**. Bad fixture: **exit 1 with all six rules
  firing distinctly**, including a fabricated "bills the customer directly" claim — the exact
  overstatement the rulings file warns against — caught by the citation rule.
- Human gate blocks `prepare` with exit 2 until a person writes the token; it is never inferred.
- Missing batch output → INCOMPLETE, integration gate FAILS on post-merge coverage, and the driver
  refuses to call the build done. `fault` attribution round-trips into the eval row.
- Generated manifest passes `./ringer.py lint` clean (2 tasks).

### Fixed during the build
- `.docx` extractor matched `<w:tbl>`/`<w:tcPr>` as text runs, leaking raw XML into the body used
  for citation matching — would have made matching unreliable on the most-cited files. Tightened to
  `<w:t>` only.
- Added a whitespace-insensitive retry for `.docx` quotes: run boundaries can drop spaces during
  extraction, which would fail a correctly-copied quote for a reason that is not hallucination. The
  character sequence must still be present, so the anti-hallucination property is unchanged.

### Notes
- **The slice does not use the Claude Agent SDK.** Stage 3's model calls happen inside Ringer
  workers, which already supply the sandbox and executed checks; adding the SDK here would be
  ceremony. It becomes load-bearing when stages 1/2/4/5 arrive and need model turns with
  `can_use_tool` policies. Recorded so the next agent doesn't "fix" the omission.

## [2026-07-31c] — Phase 3 designed: presales harness spec

### Added
- `SPEC-presales-harness.md` — the Phase 3 design. Stage map (context → intake → extract →
  **rate** → render → verify), exact input/output adapters for stage 3, the `can_use_tool` tool
  policy table, file-token human gates, the Ringer dispatch shape, the integration gate, the
  security lint, and the artifact store with its cross-run memory file.

### Decided
- **Vertical slice first:** build stage 3 (RAG rating) only — the one genuinely parallelizable
  stage — rather than all five. The rest stay in the skill until the slice is proven on a live deal.
- **The skill stays canonical:** the harness calls `<vendor>-rfp-gap-analysis`; rating rules and
  prospect-facing rules keep one home. The harness adds sequencing, gates, dispatch, and proof.
- **Agent SDK over Managed Agents, for a stated reason:** CMA would supply harness + deployment
  plus rubric-graded Outcomes, but prospect RFPs are confidential client material and the whole
  pipeline is local. The 7/15 runtime choice is now validated rather than inherited.

### Notes
- The design's load-bearing idea: the skill's doctrine *"overstatement is failure"* becomes an
  executed check. `rate_check.py` resolves every Green/Amber citation **verbatim** against the
  capability library and rejects any evidence sourced from the prospect's own documents. That —
  not parallelism — is the real argument for putting this stage under Ringer.
- Stage 3 is the first workload to write the Phase-2.6 `fault: spec|worker|check` field.
- Exit criteria include an honest kill question: is the matrix *better*, or only more
  instrumented? And a kill signal if real RFPs turn out not to be fan-out shaped.

## [2026-07-31b] — Graduation gate amended: agreement rate alone is not a gate

### Changed
- `BUILD-PLAN.md` Phase 2 — graduation now requires four conditions, not one: ≥80% agreement, ≥10 paired
  artifacts, **≥2 pairs carrying a FAIL on either side**, and a passing `rubric-regression.sh`.
- `checks/agreement.py` — reports each condition as a checklist and returns **DEGENERATE** (never MEETS)
  when every pair is PASS/PASS, with an explicit statement of what such a set does and does not prove.

### Notes
- Trigger: Ed's 12-edition backfill paired 12/12 at **100% agreement** — every value on both sides PASS.
  A judge hardcoded to print PASS scores identically on that set, so the original ≥80% gate was passable
  by a constant function. All-PASS agreement evidences only the absence of false FAILs on accepted work;
  the false-PASS rate — the risk BUILD-PLAN lists first — stays unmeasured until a real divergence exists.
- The backfill stands as a recorded baseline, not as calibration evidence.

## [2026-07-31] — Rubric v2 + owner-verdict wiring: shadow mode can finally be measured

### Added
- `checks/verdict.sh` — one-line owner verdict (`verdict.sh today pass`, `verdict.sh yesterday fail "why"`),
  resolving the archive path so logging Ed's half of shadow mode costs two words instead of a 4-flag
  invocation. The friction was the reason 12 shadow rows carried zero owner verdicts.
- `checks/agreement.py` — the Phase 2 graduation instrument: joins judge and owner rows per artifact and
  reports agreement rate vs the ≥80% gate, every disagreement (labelled FALSE PASS / FALSE FAIL with the
  judge's failed lines and the owner's note), per-rubric-line flag counts split by whether the owner still
  accepted the artifact, and the unpaired backlog. Reports only; never gates.
- `checks/rubric-regression.sh` — injects a known violation into a real archived edition and asserts the
  revised line still FAILS. Guards against the failure mode a false-positive fix invites: a line that got
  quiet rather than accurate. Synthetic runs write to a scratch log.
- `checks/judge.py --log` — scratch-log override so regression runs never pollute `runs/judge-shadow.jsonl`.

### Changed
- `rubrics/morning-briefing.md` → **v2**, revised from 12 shadow rows (2026-07-19..07-30). Line IDs declared
  stable across versions so rows stay comparable.
  - **R4 rewritten** — v1 failed any date hedge anywhere on the page, contradicting the briefing spec's own
    requirement to hedge honestly about a source's publication date. It fired on compliant text 4× (07-21,
    07-26, 07-28, 07-30) and never on a real defect. Now scoped to source links and unsupported
    release/GA/availability claims, with honest publication-date hedging explicitly compliant.
  - **R1 tightened, not loosened** — its 07-28 failure was a genuine catch (7- and 6-sentence summaries against
    a 2-sentence spec), so the line was sharpened to a mechanical count that excludes "Why it matters" takes
    and "Verification note" blocks. Under v2 it also catches the 07-30 drift v1 missed.
  - **R10 evidence contract** — v1's only failure (07-20) cited self-refuting evidence; a fail now requires
    naming both the stated and the computed weekday.
- `checks/judge.py` — `--rubric`/`--judge-model` no longer required for the owner-verdict path (they were
  dead-weight friction), owner rows carry a free-text `note`, and an owner verdict against a nonexistent
  artifact now exits 2 instead of logging a row that could never pair.
- `ai-briefing` `pipeline/briefing-prompt.md` step 10 — every run must now end its summary with the exact
  copy-paste verdict command and the day's score. Explicit rule that Ed's verdict is never logged on his
  behalf and never inferred from the fact that the edition published.

### Verified
- v2 re-scored against the 5 affected editions: all four R4 false positives cleared, 07-20 R10 cleared
  (1.00), R1 now fails 07-28 and 07-30 with countable per-item evidence.
- Regression test on a synthetic violation: R4 fired on both injected cases and the run returned **the
  judge's first FAIL verdict in 17 scored runs** (0.70) — discriminating power confirmed, not assumed.

## [2026-07-28c] — Mission Control extracted to its own repo

### Removed
- `ops/watch.py` and the generated `mission-control.html` — moved (not copied; no drift) to the new
  `edmatibag9Dev/Mission-Control-Dashboard` repo along with watcher-owned runtime data (snapshot,
  heartbeat.jsonl, ops-status + history archives).

### Changed
- Boundary: `runs/digest.jsonl` stays HERE — the Lane-2 queue belongs to ESCALATION-POLICY.md and
  evening-digest; Mission Control reads it cross-repo. All 13 routine footers repointed their
  heartbeat path to the new repo; ops-watcher SKILL.md repointed (ROOT = Mission-Control-Dashboard,
  ORCH = this repo) the same hour.

## [2026-07-28b] — Mission Control V2 built (Ed's locked spec)

### Added
- Grouped layout: 8 purpose-group cards (AI Morning Briefing / Earnings Puts / Longboard /
  Mastermind / Open Brain / Token Dashboards / Ops & System / Personal), each with a mono
  health rollup; ungrouped tasks fall into an "Other" card.
- Script jobs (launchd) section: tokenburn pair keyed to the `last-success` stamp (the
  watchdog is silent-by-design — log mtime was a false-positive signal, corrected after
  investigation showed 287 clean hourly runs), openbrain.digest and the Sunday Python
  screener via evidence-file freshness.
- Servers section: local port probes (8765, 8787) + remote HTTP HEAD probe of
  eds-mac-studio.local:8080/latest.html with Last-Modified freshness (verified live:
  200 in 0.11s, content stamped Sun 6:12 PM). Remote unreachable = amber, not escalation.
- Staleness self-check: inline JS shows a red banner if the page is >26h old (watcher-down tell).
- Dated archives to runs/history/ops-status-<date>.json — data for the future run-history strip.

### Validated
- First live run: 15 routines (8 OK / 1 in-window / 6 awaiting first post-migration fire),
  4/4 script jobs OK, 3/3 servers up. Attention loop proven end-to-end same morning: the
  7:46 AM briefing run filed 4 real Lane-2 findings via its footer (stale Runtime RSS feed,
  Reddit metrics blocked, judge 0.80 borderline, HN roster gap) — delivery tonight via
  evening-digest.

## [2026-07-28] — Registry consolidation: 8 session-scoped Cowork tasks migrated

### Changed
- Migrated all session-scoped Cowork scheduled tasks into the shared `~/.claude/scheduled-tasks`
  registry (Ed's Lane-3 yes): action-item-triage, claude-token-dashboard-update,
  token-dashboard-sentinel, substack-inbox-watcher, weekly-saltwater-fishing-report,
  weekly-brain-review, open-brain-wiki-update, freshwater-trip-log (ad-hoc). Original prompts
  spliced verbatim from `~/Claude/Scheduled/`; attention-layer footers added; Ed deletes the
  old session-scoped copies in the Cowork UI to prevent double runs.
- `ops/watch.py`: new statuses — "Not yet run" (enabled cron task with no lastRunAt; prevents
  false MISSED on freshly created tasks) and "On-demand" (manual-only tasks, grouped out of
  the active fleet). Dashboard fleet now 15 active routines.
- Not migrated (flagged for Ed): booker-mastermind-daily-journal (superseded by
  mastermind-daily-capture) and token-dashboard-phase1-review (one-time, past).

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
