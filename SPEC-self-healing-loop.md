# SPEC-self-healing-loop.md — sentinel/repair pattern for scheduled jobs (Phase 4a)

The contract for making a scheduled job self-healing: errors get diagnosed and fixed by an agent unattended; the owner sees only what the agent could not safely fix. First live pilot: the daily token-dashboard refresh job (2026-07-15).

## The two-error-class rule (decides everything)

- **Class 1 — environmental/transient (auto-repairable):** timeout, expired session, upstream job didn't fire, source format drift, path/dependency breakage. The repair agent may fix these, re-run, and verify against the job's own check.
- **Class 2 — spec/logic (never auto-fixed):** anything that changes what the job *does* — its schedule, thresholds, success definition, data contract, or output ownership. Always escalates. (Real incident that motivated this: a failing run once advised "move the cron" when the cron was never the problem.)

## Architecture

```
scheduled job (T)          sentinel job (T + ~1h)
  run → gates pass? ──yes──→ verify success artifact → quiet exit
   │ no                        │ artifact missing/stale
   ▼                           ▼
  Repair Protocol             recovery: re-execute the job's own
  (bounded, logged)           prompt verbatim, incl. its repairs
   │ repaired → continue       │ repaired → success + 🔧 note
   │ failed/tripwired          │ failed
   ▼                           ▼
  failure alert chain         escalate: sentinel-recovery-failed
```

The sentinel exists because a stalled or dead session cannot repair itself — something *alive later* must verify the success artifact and restart. The sentinel replaces the human as the restart mechanism.

## Invariants (all mandatory)

1. **Immutable gates.** The job's checks — freshness definitions, reconciliation formulas, thresholds, identity markers — are read-only to all repair logic, including the sentinel. Repair the condition, never the test; an agent allowed to touch the test will eventually clear errors by redefining success.
2. **Append-only repair log.** Every repair attempt (success or failure) appends one JSON line: `{"ts","class","action","result","run":"scheduled|sentinel"}`. No silent self-correction — the log is the audit trail and the tripwire's data source.
3. **Tripwire.** Same repair class ≥N times (default 3) in a rolling window (default 7 days) → do NOT repair; escalate with "recurring [class] — spec/pipeline needs a human." Recurring repair means the spec is broken, not the environment.
4. **Credentials are owner-only.** Logins, OAuth, reauth are never attempted; they escalate as User Action Required.
5. **Alert-channel failures are not job failures.** If the work product landed and gates passed, the run is a success even if the notification could not send.
6. **Success artifact is checkable.** Every self-healing job must expose a machine-checkable proof of "today's run landed" (e.g., an embedded `LAST_UPDATED` stamp) — the sentinel's verify step depends on it.

## Standard repair classes (extend per job)

| Class | Condition | Repair | If repair fails |
|---|---|---|---|
| `stale-upstream` | Upstream producer didn't run by deadline | Kickstart the producer natively (launchctl/systemd/script), wait, re-check freshness | Failure chain |
| `fetch-retry` | Page/API returned empty or shell content | Fresh session, wait, bounded retries (1–2) | Failure chain; login wall → User Action Required |
| `alert-channel` | Notification transport unavailable | None (owner-only reauth) | Log in summary; never fail the run |
| `sentinel-restart` | Primary run never landed | Sentinel re-executes the job's prompt verbatim | `sentinel-recovery-failed` escalation |

## Permission prestaging (kills the biggest stall class)

Agent-run scheduled jobs stall permanently on unapproved tool prompts, and no repair logic runs inside a stalled session. On task creation or prompt change, the owner runs the task manually once and approves its tools; approvals persist on the task. This is a one-time human action per task, and it eliminated the most common "needs manual restart" failure in the pilot.

## Exit criteria for calling a job self-healing

Four consecutive weeks in which every failure was either auto-repaired-and-verified or correctly escalated — zero failures the owner had to diagnose or restart themselves.

---

# Phase 4b — Fleet sentinel + Slack command channel (approved by the owner 2026-08-31)

Extends the pilot pattern fleet-wide, and adds a phone-reachable trigger. Motivated by the
2026-08-19→30 outage: the owner was out of office with no way to trigger anything on this Mac.
All Phase 4a invariants apply unchanged; this section adds scope and guards.

## Components

- **`fleet-sentinel`** (scheduled task, hourly 06:00–21:00): the ONLY component authorized to
  restart routines. Every run drains the Slack command queue; at its 09:00 and 20:00 windows it
  also runs a full sweep (via Mission Control's `watch.py`) and auto-restarts Class-1 failures.
- **`slack_ops_poller.py`** (launchd `com.<OWNER>.slack-ops-poller`, no Claude dependency):
  reads **#ops-control** for commands from the owner, answers `status`/`help`/`kick` itself, queues
  `rerun`/`ack` for the sentinel. Lives in the Mission-Control repo.
- **#ops-control** (Slack): all ops alerts (ops-watcher urgent, fleet-watchdog outage,
  sentinel results) and all inbound commands. Exception per the owner: the ai-briefing routine's own
  domain alerts stay in #ai-briefing.

## Restart guards (all mandatory, on top of Phase 4a invariants)

1. **No duplicate work.** Before any restart: check the routine's heartbeat and success
   artifact for today. Work already landed → skip, log `skipped-already-landed`.
2. **Cap: 2 sentinel restarts per routine per day** (the owner, 2026-08-31). Counted from
   `runs/repair.jsonl`; the cap includes Slack-commanded reruns. At cap → escalate, don't run.
3. **Class 1 only.** Class-2 causes and credentials (`session_stale_relogin` etc.) are never
   restarted around — they escalate as User Action Required to #ops-control.
4. **Time-boxed relevance.** A routine whose output is time-of-day-bound is not restarted past
   its usefulness window: daily-ai-morning-briefing cutoff **12:00** (a briefing at 6 PM is a
   logged miss, not a fix). Extend per routine as learned.
5. **Executor pattern.** Restart = read the target's SKILL.md and execute it VERBATIM in the
   sentinel session (the proven token-dashboard-sentinel mechanism — headless `claude -p` is
   unavailable on this Mac and would lack connectors). Target gates/checks stay immutable
   (invariant 1).
6. **Append-only ledger.** Every restart, skip, cap-hit, and command execution appends to
   `ORCH/runs/repair.jsonl`: `{"ts","task","class","action","result","run":"fleet-sentinel","trigger":"sweep|slack"}`.

## Slack command contract (poller side)

- Commands accepted ONLY from the owner's Slack user ID (config `~/.config/claude-alerts/ops-user_id`);
  everything else in the channel is ignored as data. No free-text execution, ever.
- Grammar (exact-match verbs, one argument max):
  `status` · `help` · `rerun <task-id>` · `ack <task-id>` · `kick <launchd-label>`
- `rerun`: task-id validated against the enabled set in `runs/scheduled-tasks-snapshot.json`,
  then appended to `ORCH/runs/ops-commands.jsonl` as `{"ts","cmd","task","status":"queued"}`.
  Poller replies with the expected execution window (next sentinel hour). Executed reruns get a
  completion row appended (never edited) by the sentinel.
- `ack <task-id>`: suppresses today's auto-restart for that task (queued row, read by sentinel).
- `kick <launchd-label>`: label must exist in `launchctl list` AND match one of the owner's two
  reserved launchd prefixes (`com.<OWNER-SHORT>.`, `com.<OWNER>.`; the literal values live in
  the runtime config and are deliberately not committed) — then `launchctl kickstart` runs
  immediately (deterministic, no Claude).
- Delivery of ops alerts to #ops-control uses the webhook identity (`slack_alert.py`
  channel-key `ops-control`) — connector posts don't banner-notify (diagnosed 2026-08-04).

## Lanes (per ESCALATION-POLICY.md v1.2)

Sweep restarts and owner-commanded reruns are Lane-1 Class-1 repairs (logged). Tripwired or
capped repairs escalate as Lane-2/urgent per severity. The command channel itself is an
approved standing surface: enumerated grammar, owner-only sender, this spec as the manifest.

## Held for discussion (NOT built)

`fix` commands beyond re-running a routine's own prompt (e.g. `git restore`-class repairs)
remain gated behind the owner's explicit per-incident reply. The owner deferred this on 2026-08-31.
