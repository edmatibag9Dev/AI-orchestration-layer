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
