---
name: action-item-triage
description: Daily automated action item triage — auto-closes done and stale items using Open Brain evidence, writes closure thoughts before wiki regenerates
---

You are running the owner's automated daily action item triage. Run silently and autonomously — do not wait for input, do not show interactive prompts. Complete all steps and write results to Open Brain.

Two auto-closure types:
- auto-done — action item has clear evidence of completion found in Open Brain
- auto-dropped — action item is >45 days old with no related activity in the last 30 days

Do not modify any existing thought. Only write new closure thoughts.

## Step 1 — Fetch Candidates

Run in parallel:
- mcp__open-brain__list_thoughts({ type: 'action_item', limit: 50 })
- mcp__open-brain__list_thoughts({ type: 'task', limit: 50 })
- mcp__open-brain__search_thoughts({ query: 'ACTION CLOSED Resolution auto-done auto-dropped' }) → all existing closures
- mcp__open-brain__search_thoughts({ query: 'ACTION RECLASSIFIED project status record excluded from triage' }) → all reclassification markers

Deduplicate candidates by thought ID.

Build closed set: parse each closure thought for "Original ID: [uuid]" and collect those UUIDs.

Build reclassified set: parse each 🔁 ACTION RECLASSIFIED marker for "Original ID: [uuid]" and collect those UUIDs. These are items the owner has moved out of action-item status by hand; they are permanently out of scope, not pending.

Exclude from candidates:
- Any thought whose ID is in the closed set
- Any thought whose ID is in the reclassified set
- Any thought whose ID is in the PERMANENT EXCLUSIONS list below
- Any thought whose content starts with "✅ ACTION CLOSED:" (is itself a closure record)
- Any thought whose content starts with "🔁 ACTION RECLASSIFIED" or "🔄 ACTION REINSTATED" (is itself a status marker)
- Any thought of type observation, reference, or capture
- Any thought captured in the last 7 days (too fresh — never auto-close)

### PERMANENT EXCLUSIONS

Hardcoded here rather than derived from a marker search, because Open Brain retrieval is not
reliably complete — thoughts written 2026-07-28 through 2026-08-04 do not surface via list or
search, so a marker-only exclusion can silently fail and let an item be closed anyway.
Add an ID here whenever the owner reclassifies or otherwise permanently removes an item from triage.

- `fb8de9b7-26c0-481f-87e0-8bcf37da17ef` — PROJECT: eval-review. Reclassified by the owner 2026-08-06
  from action item to project status record, two days before it would have crossed the 45-day
  auto-drop threshold. Its remaining next-steps (Cowork JSON parser, MCP UUID→name alias map,
  GitHub repo) are project work, not triage-eligible action items. Never auto-close.

What remains is your open candidate list.

## Step 2 — Auto-Done Check

For each open candidate, extract 3–5 key terms from its title and first 100 chars of content. Run mcp__open-brain__search_thoughts({ query: [key terms] }).

From the results, look for thoughts captured AFTER the candidate's date that contain any of these completion signals: shipped, built, done, completed, live, launched, finished, deployed, created, set up, published.

All three criteria must be true to auto-close as done:
1. The matching thought was captured after the action item's date
2. The matching thought contains a completion signal
3. The matching thought's content clearly relates to the same topic (not a keyword coincidence — use judgment)

If all three → mark this candidate as auto-done, record the matching thought's first 60 chars as evidence.

## Step 3 — Auto-Dropped Check

For each remaining candidate not already marked auto-done, check BOTH conditions:
1. The candidate was captured more than 45 days ago
2. mcp__open-brain__search_thoughts({ query: [key terms] }) returns no thoughts from the last 30 days that relate to this item

If both true → mark as auto-dropped.
If either condition is false → leave open, do not touch.

## Step 4 — Write Closure Thoughts

For each candidate marked auto-done, call mcp__open-brain__capture_thought with:

✅ ACTION CLOSED: [first 80 chars of original title]
Resolution: auto-done
Original ID: [uuid]
Closed: [today's date YYYY-MM-DD]
Evidence: [first 60 chars of matching completion thought]
Auto-closed by: action-item-triage scheduled task

For each candidate marked auto-dropped, call mcp__open-brain__capture_thought with:

✅ ACTION CLOSED: [first 80 chars of original title]
Resolution: auto-dropped
Original ID: [uuid]
Closed: [today's date YYYY-MM-DD]
Reason: No activity in 45+ days
Auto-closed by: action-item-triage scheduled task

Write closures one at a time. If a write fails, log it in the summary and continue — do not stop the run.

## Step 5 — Write Triage Summary

After all closures are written, call mcp__open-brain__capture_thought once with:

## Action Item Auto-Triage — [today's date YYYY-MM-DD]

Auto-done: [N] items
[- [title] (Original ID: [first 8 chars of uuid])]

Auto-dropped: [N] items
[- [title] (Original ID: [first 8 chars of uuid])]

Remaining open: [N] items
Failed writes: [N] (list IDs if any)
Run by: action-item-triage scheduled task 7:00 AM

If zero items were closed in either category, still write the summary with N=0. This is the audit trail the weekly brain review reads.

## Guardrails

- Never auto-close items captured in the last 7 days
- Never auto-close thoughts of type observation, reference, or capture
- Auto-done requires ALL THREE criteria — when in doubt, leave open
- Auto-dropped requires BOTH conditions — age AND inactivity — not just age alone
- Never modify or delete existing thoughts
- Never auto-close an ID in the closed set, the reclassified set, or PERMANENT EXCLUSIONS — an
  item the owner has reclassified by hand is a decision, not a stale item, and must not be re-triaged
- Status changes are always a NEW marker thought (✅ ACTION CLOSED / 🔁 ACTION RECLASSIFIED /
  🔄 ACTION REINSTATED) carrying "Original ID: [uuid]" — never an edit to the original

## Alert Protocol — Email the owner When Blocked

Trigger when: Open Brain MCP unavailable, or 3+ consecutive capture_thought failures.

Email:
1. Navigate to https://mail.google.com/mail/u/0/#compose
2. To: <OWNER_EMAIL>
3. Subject: ⚠️ Action Item Triage — [issue]
4. Body: date/time, what failed, how many items processed before failure.

Fallback: mcp__Read_and_Write_Apple_Notes__add_note with title ⚠️ TASK ALERT: Action Item Triage — [Date].

After alert: stop.

---

ATTENTION-LAYER FOOTER (per ESCALATION-POLICY.md, added 2026-07-28 with the owner's approval):

1. Noteworthy but NON-BLOCKING findings from this run (skipped/malformed inputs, auth warnings, source-format drift, anything the owner should eventually see but that shouldn't interrupt him) -> append one Lane-2 JSON line to ~/Documents/Claude/Projects/AI-orchestration-layer/runs/digest.jsonl:
   {"ts": "<ISO-8601 local>", "severity": "info|minor", "category": "<short-kebab>", "text": "<standalone description>", "source": "action-item-triage", "status": "new"}
   Append-only: never edit, re-deliver, or delete existing rows -- the evening-digest task owns delivery and status transitions. Do not file duplicates of an item already in the queue.

2. If you CANNOT complete this job, say so explicitly in your final report AND file a Lane-2 row describing what failed (severity "minor"; use "major" only if data was lost).

3. ALWAYS end the run -- success or failure -- by appending one heartbeat line to ~/Documents/Claude/Projects/Mission-Control-Dashboard/runs/heartbeat.jsonl:
   {"task": "action-item-triage", "ts": "<ISO-8601 local>", "status": "ok|partial|failed", "note": "<one line>"}
   The ops-watcher reads this to distinguish a run that completed from one that started and died.
