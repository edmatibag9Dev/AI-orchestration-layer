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
- mcp__open-brain__search_thoughts({ query: 'Action Item Auto-Triage Excluded from candidacy Remaining open' }) → prior triage summaries, the SECOND closed-set source (see below)

Deduplicate candidates by thought ID.

Build closed set FROM BOTH SOURCES. The closure search alone is not sufficient: Open Brain
retrieval is incomplete, and a closure record that does not come back leaves a long-closed item
looking genuinely open. That is not hypothetical — it re-closed 0527d081 twice (2026-08-15,
2026-08-18) before it was hardcoded below, and 64 of 94 triage summaries carry non-Safe
sensitivity and are invisible to the default-scope searches this step runs.

- Source A — closure records: parse each ✅ ACTION CLOSED thought for "Original ID: [uuid]".
- Source B — prior triage summaries: in each summary, read ONLY the "Excluded from candidacy"
  block (some runs title it "CANDIDATE RESOLUTION THIS RUN") and the "Auto-done:" / "Auto-dropped:"
  result lists. Then filter by REASON — an exclusion block lists several kinds of exclusion and
  only one of them means closed:
    ✅ ADD to the closed set — the ID's stated reason is closure: "closed", "auto-done",
       "auto-dropped", "already in closed set", "previously closed".
    ❌ DO NOT ADD — every other reason. In particular:
       · "too fresh" / "<7 days" — a TEMPORARY exclusion. The item re-enters candidacy a week
         later and is very likely still open.
       · "PERMANENT EXCLUSION" / "reclassified" — belongs to the reclassified set, not the
         closed set. Excluded either way, but do not mislabel it as closed.
       · "gated" / "outside default scope" / "did not surface" — a RETRIEVAL failure, the
         opposite of a state change. Such an item is open and invisible, not closed.
  UUIDs are usually 8-char prefixes in summaries — match on prefix against your candidate IDs.

  Worked example, from the real 2026-07-02 summary (fd02e1ec): "Excluded from candidacy:
  dff967bb + a85dbbc3 (captured 7/1, too fresh, <7 days); 37601f18, 550170d3, 1a420e43 (already
  in closed set); 0527d081 (already closed auto-done on 6/11)". Correct parse adds FOUR IDs —
  37601f18, 550170d3, 1a420e43, 0527d081. It adds NEITHER dff967bb NOR a85dbbc3: they were held
  out for freshness and are still live today. Taking that whole block as closed retires the only
  two live candidates this task has.

⚠️ DO NOT sweep a whole summary for UUIDs. A triage summary also contains a "Remaining open"
section, a forward-deadline paragraph and a run-notes section, and the IDs in those are LIVE
items, evidence thoughts and prior-summary references — the opposite of closed. dff967bb and
a85dbbc3 appear by name in every summary's "Remaining open" block; a naive grep for
"Original ID:" or for any UUID across the summary body puts them in the closed set and silently
retires the task's only live candidates. Parse the two named sections, nothing else. The same
trap applies to the reclassified set below, where only one of the eight IDs a blind grep returns
is attached to a real 🔁 marker.

If Source A and Source B disagree about an item, the item is CLOSED — a recorded exclusion or
closure is evidence of a state change; its absence from one retrieval is not evidence against it.

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

- `0527d081-0a90-48b5-a681-e89ae939d15d` — "build a daily email that summarizes research on AI
  news-related topics". CLOSED auto-done 2026-06-11, one day after capture, when the Daily
  Morning AI Briefing shipped. Its closure record is NOT retrievable by list_thoughts or
  search_thoughts, so the Step 1 closed-set parse misses it and the item re-enters candidacy
  looking genuinely open — it has done so on every run from 2026-08-15 onward, nine times as of
  2026-09-12. It has already been erroneously re-closed THREE times (2026-06-11 legitimately,
  then 2026-08-15 and 2026-08-18 in error). Its own topic search returns 97a7e8f3 (2026-06-10,
  "planned, built, and shipped in one day"), a clean-looking auto-done match that will produce a
  fourth duplicate closure on any run that reaches Step 2 with this item in the pool. The
  authoritative disposition is the 2026-08-18 self-correction 96d87941, corroborated by prior
  triage summaries fd02e1ec (2026-07-02) and 20ab50b4 (2026-07-13). Never auto-close. Added
  2026-09-12 per the owner's explicit instruction, applying the standing fix 96d87941 called for.

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
- Build the closed set from BOTH Step 1 sources (closure records AND the "Excluded from
  candidacy" / result lines of prior triage summaries). Relying on the closure search alone is
  what produced the duplicate closures of 0527d081
- When parsing summaries or markers for IDs, parse the NAMED sections only — never grep the whole
  body. "Remaining open" IDs are live items; a blind UUID sweep retires them silently
- Status changes are always a NEW marker thought (✅ ACTION CLOSED / 🔁 ACTION RECLASSIFIED /
  🔄 ACTION REINSTATED) carrying "Original ID: [uuid]" — never an edit to the original

## Alert Protocol — Email the Owner When Blocked

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

   **TIMESTAMP FORMAT — applies to EVERY `ts` this task writes (digest.jsonl and heartbeat.jsonl). Use a colon in the UTC offset.** Generate it with:
       /usr/bin/python3 -c "import datetime;print(datetime.datetime.now().astimezone().replace(microsecond=0).isoformat())"
   which yields `2026-08-30T12:29:48-07:00`. Do NOT use `date '+%Y-%m-%dT%H:%M:%S%z'` — BSD date emits `-0700` with no colon, which Python 3.9's strict `fromisoformat` rejects, and 3.9 is what `/usr/bin/python3` resolves to for launchd-run tooling. Do NOT use `date '+%:z'` either — GNU date supports `%:z`, macOS BSD date does NOT: it passes the literal through, producing a corrupt stamp like `2026-09-02T07:17:49:z` that every reader rejects (observed 2026-09-02, fleet-sentinel heartbeat). Shell `date` is the wrong tool here in all its forms; use the python one-liner above.
