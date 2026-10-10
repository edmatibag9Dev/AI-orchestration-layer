---
name: skills-inventory-review
description: Monthly (1st, 9:30 AM): Claude release-note impact, skill-library audit, repo-standard sweep of every owner repo, prepared (never pushed) fixes — part of AI Orchestration
---

Run the Monthly Maintenance Review. Bucket for session capture: AI Orchestration. The task ID stays `skills-inventory-review` on purpose: the Mission Control dashboard and the heartbeat log key on it. Only the title changed (2026-10-10).

Four phases: A release notes → B skill checks → C repo-standard sweep → D prepare fixes. Phases A–C are REPORT-ONLY. Phase D runs only when the state file says so, and only under its own rules below.

Paths used throughout:
- ORCH = ~/Documents/Claude/Projects/AI-orchestration-layer
- STATE = ORCH/runs/maintenance-state.json (`prepare_fixes`, `max_fix_repos`, `claude_code_last_version`, `repo_standard_version_last_seen`)
- STAGING = ~/Documents/Claude/Projects/_maintenance-staging (clones of GitHub-only repos + fix worktrees; nobody works in it)
- OUT = ORCH/reports/maintenance-<YYYY-MM-DD>/ (sweep JSON, release-notes JSON, patches/). Report: ORCH/reports/maintenance-review-<YYYY-MM-DD>.md
- BRANCH = maint/<YYYY-MM>

SCOPE GUARD (first, always):
- Live roots only: ~/.claude/skills, ~/.claude/scheduled-tasks, ~/.claude/*.md, ~/.claude/settings.json, ~/Documents/Claude, ~/Claude, the owner's repo clones that `repo_sweep.py` finds, and the claude.ai upload cache at ~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/*/*/skills/.
- NEVER read, cite, or act on anything under iCloud backup (~/Library/Mobile Documents/com~apple~CloudDocs/), any path containing _gsdata_/, any _archive/ folder, ~/Documents/Claude/ringer-jobs/ (job artifacts), or STAGING when scanning for skills (its clones are copies). Discard search hits from these.
- Never push, never force-push, never open pull requests, never edit a checked-out working tree, never edit ~/.claude/CLAUDE.md or any memory file. CLAUDE.md changes only when the owner says so (the owner's rule).

PHASE A — CLAUDE RELEASE NOTES (what changed in Claude since last month, and what it touches)
1. Run: `python3 ORCH/maintenance/release_notes.py --state STATE --out OUT/release-notes.json` (if STATE has no saved version, add `--since <date of last month's review>`).
2. Read every P1 entry (a feature added, changed or removed). Scan P2 entries (fixes touching hooks, skills, scheduled runs, MCP = Model Context Protocol servers, or instruction files). Ignore "drop".
3. Also WebFetch the Anthropic release-notes pages for the Claude apps and the API (start at https://docs.claude.com/en/release-notes/overview, follow redirects) for the same window. If a fetch fails, say so in the report; do not guess.
4. For each relevant entry, grep the instruction surfaces for the feature, setting, hook event, or tool name it mentions:
   - Layer 1 global rules: ~/.claude/CLAUDE.md, AGENTS.md, REPO-STANDARD.md, CONTRIBUTING.md, GITHUB-OPERATIONS.md, brand/BRAND.md
   - Layer 2 harness config: ~/.claude/settings.json (hooks, permissions) and the scripts its hooks call
   - Layer 3 skills: every SKILL.md behind ~/.claude/skills symlinks, plus the claude.ai upload cache
   - Layer 4 routine prompts: ~/.claude/scheduled-tasks/*/SKILL.md (enabled tasks first)
   - Layer 5 repo instructions: AGENTS.md in each clone from Phase C
5. Classify each match: BREAKS (a name, key, event, or behavior an instruction relies on changed — must fix), REDUNDANT (a built-in feature now does what a skill/rule does — candidate to retire or trim), IMPROVE (a new capability a skill could use — optional). Quote the release-note line and the instruction line side by side. A keyword hit is not a finding until you have read the instruction's surrounding lines.

PHASE B — SKILL CHECKS (run all six)
1. Symlink integrity — every entry in ~/.claude/skills should be a symlink into a project repo (the repo file IS the executing skill). Flag: broken links, and any entry that is a plain directory (drift risk — it was converted to symlinks on 2026-08-17).
2. Duplicate & drift scan — find all SKILL.md files across live roots, group by frontmatter `name:`, md5-hash each copy. Flag any same-name set with differing hashes; show each copy's path, mtime, and size. Known-good architecture: ~/.claude/scheduled-tasks/<task>/SKILL.md files are runtime masters; project-folder copies of weekly-brain-review (Dispatch to Open Brain, both roots) and the wiki skill are refresh-by-copy mirrors expected to drift — flag when they do so the owner can re-sync. The scrubbed public backups under ORCH/scheduled-tasks/ differ from their masters BY DESIGN (paths, owner name, employer name scrubbed for the public repo) — do not flag the content difference itself; flag a backup only when its master's mtime is newer than the backup's last commit, which means it needs a re-scrub.
3. Uploaded-skill duplicates — list skill names in the claude.ai upload cache; flag any name that also exists locally (a stale upload shadows the live copy and can silently run old behavior). Only the owner can delete these, at claude.ai → Settings → Skills.
4. Description token audit — for each installed skill, estimate description tokens (chars ÷ 4). Flag descriptions over 150 tokens; these load every session. Compression rule: keep every quoted trigger phrase and every routing boundary ("do NOT use for X"), cut workflow narration (the body loads on invocation anyway).
5. Harness-redundancy check — grep skill bodies for instruction patterns the Claude harness may now handle natively: file-conversion recipes (pdftotext/pandoc/markitdown), date-fetching workarounds, web-tool usage explanations, context/token-management advice, generic anti-hallucination boilerplate. Cross-reference Phase A's REDUNDANT list. CRITICAL: read the surrounding lines before flagging — domain logic is NOT boilerplate (e.g., Day One "never retry a mismatched write" rules, presales citation-required accuracy gates, Slack webhook-not-connector alerting). In the 2026-08-17 baseline audit, all such hits were legitimate domain logic; expect few true positives.
6. CLAUDE.md overhead — report the byte size of ~/.claude/CLAUDE.md and flag any `@` inline file references (there should be none; BRAND.md was deliberately de-inlined 2026-08-17).

PHASE C — REPO-STANDARD SWEEP (every owner repo, local or GitHub-only)
1. Run: `python3 ORCH/maintenance/repo_sweep.py --staging STAGING --out OUT/repo-sweep.json`. It checks every non-fork, non-archived owner repo with ~/.claude/skills/repo-standard/scripts/repo-check.py; repos with no local clone are cloned into STAGING/clones/.
2. Compare `standard_version` in the sweep with `repo_standard_version_last_seen` in STATE. If it changed (or STATE has none), say so at the top of the report and summarize what changed (`git -C ~/Documents/Claude/Projects/repo-standard log --since=<last review date> --oneline`).
3. Report per repo: FAIL lines, WARN lines, dirty-file count, local vs staging. Also list skipped repos (forks, archived), duplicate clones, and clones with no remote. Excluded by the owner's decision (2026-10-10): forks (mcp-dayone), third-party clones (ringer), the remote-less local Token Burn Dashboard folder — list them, never fix them.

PHASE D — PREPARE FIXES (only if STATE `prepare_fixes` is true; otherwise write "Phase D skipped: prepare_fixes is false" and go to OUTPUT)
Fixes are drafts: committed on BRANCH in a separate worktree, never pushed. the owner reviews and pushes in an interactive session ("apply this month's maintenance").
1. Scope: repos with FAIL lines from Phase C, plus BREAKS findings from Phase A that live in a repo. Order by FAIL count, highest first; stop at STATE `max_fix_repos` and list the rest as "deferred".
2. Per repo: `ORCH/maintenance/prep_branch.sh <repo-path> BRANCH STAGING` prints the worktree path. Work ONLY in that worktree. Read ~/.claude/skills/repo-standard/SKILL.md, the repo's AGENTS.md and ~/.claude/CONTRIBUTING.md first, then fix the FAIL lines the standard's procedures cover. Never invent repo facts: a README or AGENTS.md section you cannot fill from the repo's own files gets a clearly marked TODO and goes on the report's Open Questions list.
3. Run `python3 ~/.claude/skills/repo-standard/scripts/repo-check.py <worktree>` (add `--public` for public repos). Stage named paths only, confirm `git diff --cached --name-status --diff-filter=D` is empty, commit per CONTRIBUTING.md. Record branch, commit hash, and remaining FAIL lines.
4. Global files (Layers 1–2) and claude.ai uploads are NEVER edited: write proposed changes as unified-diff files under OUT/patches/<file>.patch and list them.
5. If a fix needs a judgment call (deleting content, changing a data contract, anything in a public repo's history), do not make it — list it under Open Questions.

OUTPUT
- Write ORCH/reports/maintenance-review-<YYYY-MM-DD>.md: a summary of at most 8 lines (counts per phase + total always-on token estimate + standard version), then one section per phase (Phase B keeps one sub-section per check), then "Prepared fixes" (repo · branch · commit · remaining FAILs), then "Open Questions". Findings ranked by impact: BREAKS first, then tokens saved per session, then drift risk. State plainly when a check found nothing. Follow the Communication Style section of ~/.claude/CLAUDE.md: answer first, no filler, define acronyms, label assumptions, no unevidenced judgments.
- Only after the report is written: `python3 ORCH/maintenance/release_notes.py --state STATE --save-version <to_version from OUT/release-notes.json>`, and set `repo_standard_version_last_seen` in STATE to the sweep's `standard_version`.
- Baseline for comparison (2026-08-17): 13 installed skills all symlinked, description total ~1,365 tokens, always-on overhead ~5,800 tokens/session after cleanup. Last month's report: the newest of ORCH/reports/maintenance-review-*.md or skills-review-*.md.

ATTENTION-LAYER FOOTER (per ESCALATION-POLICY.md):
1. For noteworthy NON-BLOCKING findings (BREAKS from release notes, new drift, new duplicate uploads, description bloat, broken symlink, repos failing the standard, prepared-fix branches awaiting review), append one Lane-2 JSON line per finding-group to ORCH/runs/digest.jsonl:
   {"ts": "<ISO-8601 local>", "severity": "info|minor", "category": "maintenance-review", "text": "<standalone description incl. report path>", "source": "skills-inventory-review", "status": "new"}
   Append-only; never edit or re-deliver existing rows; no duplicates of items already queued.
2. If the review cannot complete, say so explicitly in the final report AND file a Lane-2 row (severity "minor") describing what failed.
3. ALWAYS end — success or failure — by appending one heartbeat line to ~/Documents/Claude/Projects/Mission-Control-Dashboard/runs/heartbeat.jsonl:
   {"task": "skills-inventory-review", "ts": "<ISO-8601 local>", "status": "ok|partial|failed", "note": "<one line>"}

   **TIMESTAMP FORMAT — applies to EVERY `ts` this task writes (digest.jsonl and heartbeat.jsonl). Use a colon in the UTC offset.** Generate it with:
       /usr/bin/python3 -c "import datetime;print(datetime.datetime.now().astimezone().replace(microsecond=0).isoformat())"
   which yields `2026-08-30T12:29:48-07:00`. Do NOT use `date '+%Y-%m-%dT%H:%M:%S%z'` — BSD date emits `-0700` with no colon, which Python 3.9's strict `fromisoformat` rejects, and 3.9 is what `/usr/bin/python3` resolves to for launchd-run tooling. Do NOT use `date '+%:z'` either — GNU date supports `%:z`, macOS BSD date does NOT: it passes the literal through, producing a corrupt stamp like `2026-09-02T07:17:49:z` that every reader rejects (observed 2026-09-02, fleet-sentinel heartbeat). Shell `date` is the wrong tool here in all its forms; use the python one-liner above.