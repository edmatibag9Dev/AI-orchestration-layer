---
name: skills-inventory-review
description: Monthly (1st, 9:30 AM): audit the skill library for drift, duplicates, token bloat, and harness redundancy — report-only, part of AI Orchestration
---

Run the monthly skills inventory review. Bucket for session capture: AI Orchestration. This task is REPORT-ONLY: never edit, move, delete, or "fix" any skill file — findings go in the report and the owner directs fixes.

SCOPE GUARD (first, always):
- Live roots only: ~/.claude/skills, ~/.claude/scheduled-tasks, ~/Documents/Claude, ~/Claude, and the claude.ai upload cache at ~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/*/*/skills/.
- NEVER read, cite, or act on anything under iCloud backup (~/Library/Mobile Documents/com~apple~CloudDocs/), any path containing _gsdata_/, any _archive/ folder, or ~/Documents/Claude/ringer-jobs/ (job artifacts). Discard search hits from these.

CHECKS (run all six):
1. Symlink integrity — every entry in ~/.claude/skills should be a symlink into a project repo (the repo file IS the executing skill). Flag: broken links, and any entry that is a plain directory (drift risk — it was converted to symlinks on 2026-08-17).
2. Duplicate & drift scan — find all SKILL.md files across live roots, group by frontmatter `name:`, md5-hash each copy. Flag any same-name set with differing hashes; show each copy's path, mtime, and size. Known-good architecture: ~/.claude/scheduled-tasks/<task>/SKILL.md files are runtime masters; project-folder copies of weekly-brain-review (Dispatch to Open Brain, both roots) and the wiki skill are refresh-by-copy mirrors expected to drift — flag when they do so the owner can re-sync.
3. Uploaded-skill duplicates — list skill names in the claude.ai upload cache; flag any name that also exists locally (a stale upload shadows the live copy and can silently run old behavior). Only the owner can delete these, at claude.ai → Settings → Skills.
4. Description token audit — for each installed skill, estimate description tokens (chars ÷ 4). Flag descriptions over 150 tokens; these load every session. Compression rule: keep every quoted trigger phrase and every routing boundary ("do NOT use for X"), cut workflow narration (the body loads on invocation anyway).
5. Harness-redundancy check — grep skill bodies for instruction patterns the Claude harness may now handle natively: file-conversion recipes (pdftotext/pandoc/markitdown), date-fetching workarounds, web-tool usage explanations, context/token-management advice, generic anti-hallucination boilerplate. CRITICAL: read the surrounding lines before flagging — domain logic is NOT boilerplate (e.g., Day One "never retry a mismatched write" rules, presales citation-required accuracy gates, Slack webhook-not-connector alerting). In the 2026-08-17 baseline audit, all such hits were legitimate domain logic; expect few true positives.
6. CLAUDE.md overhead — report the byte size of ~/.claude/CLAUDE.md and flag any `@` inline file references (there should be none; BRAND.md was deliberately de-inlined 2026-08-17).

OUTPUT:
- Write a Markdown report to ~/Documents/Claude/Projects/AI-orchestration-layer/reports/skills-review-<YYYY-MM-DD>.md with: a 5-line summary (counts + total always-on token estimate), then one section per check, findings ranked by impact (tokens saved per session, then drift risk). State plainly when a check found nothing. Follow the Communication Style section of ~/.claude/CLAUDE.md: answer first, no filler, define acronyms, label assumptions, no unevidenced judgments.
- Baseline for comparison (2026-08-17): 13 installed skills all symlinked, description total ~1,365 tokens, always-on overhead ~5,800 tokens/session after cleanup.

ATTENTION-LAYER FOOTER (per ESCALATION-POLICY.md):
1. For noteworthy NON-BLOCKING findings (new drift, new duplicate uploads, description bloat, broken symlink), append one Lane-2 JSON line per finding-group to ~/Documents/Claude/Projects/AI-orchestration-layer/runs/digest.jsonl:
   {"ts": "<ISO-8601 local>", "severity": "info|minor", "category": "skills-review", "text": "<standalone description incl. report path>", "source": "skills-inventory-review", "status": "new"}
   Append-only; never edit or re-deliver existing rows; no duplicates of items already queued.
2. If the review cannot complete, say so explicitly in the final report AND file a Lane-2 row (severity "minor") describing what failed.
3. ALWAYS end — success or failure — by appending one heartbeat line to ~/Documents/Claude/Projects/Mission-Control-Dashboard/runs/heartbeat.jsonl:
   {"task": "skills-inventory-review", "ts": "<ISO-8601 local>", "status": "ok|partial|failed", "note": "<one line>"}