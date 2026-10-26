# SPEC-project-manifest.md — `project.toml`, the project manifest

*Owner: the owner · Drafted: 2026-10-25 · Status: BUILT 2026-10-25 — validator, hook (installed), skill (installed), adopted on five projects, Codex portability test passed; memory-first gate (§5.4) installed; exit check passed on the second attempt · spec_version 1*

One small file per project that says which pieces of the stack engage when a session works on it:
which memory buckets load, which skills to prefer, where its Ringer steps are declared, which review
gates apply, which task-board tag and scheduled routines belong to it, what "done" means, and where
its output may go. Decided 2026-10-25 (BUILD-PLAN, "Decisions made (2026-10-25)"); the lifecycle it
serves is drawn in [`docs/architecture-flow.html`](docs/architecture-flow.html).

The manifest **declares**. It never runs anything, never grants a tool permission, and never moves
an escalation lane. Readers (§5) turn it into instructions at session start.

---

## 1. Where it lives and how it is found

- **File:** `project.toml` in the project root, next to `AGENTS.md`. Plain TOML so any agent (Claude
  Code, Codex, a local model) can read it without a library beyond the standard one.
- **Repo projects:** committed. It must stay publishable (invariant 1).
- **Non-repo projects** (a working folder with no git): the same file in the folder root, with
  `kind = "folder"`, `repo = "none"` and a required `no_repo_reason`.
- **Lookup:** walk up from the session's working directory to the first `project.toml`; stop at
  `$HOME`. None found → no manifest, and the session runs exactly as it does today.
- **One manifest per project.** Engagement records are per prospect, not per project; a manifest only
  says whether the project takes part in engagements and where the records live (§3, `[engagement]`).

## 2. Inputs — who writes it

| Writer | When | May change |
|---|---|---|
| project-start skill (§5.2) | Project creation, or adopting an existing project | Everything, then shows the owner the file before commit |
| The owner | Any time | Everything |
| Any other agent | Only with the owner's explicit OK in the session | Everything except `[memory]` and `[review]`, which stay owner-only (invariant 6) |

## 3. Contract — fields

`R` = required. Unknown keys are allowed and ignored by readers (forward compatibility).

| Key | Type | R | Meaning | Read by |
|---|---|---|---|---|
| `[project] spec_version` | int | R | Manifest format version. This spec = `1`. | hook, validator |
| `[project] id` | slug | R | Lowercase, hyphens. Stable; used as the task-board tag default. | all |
| `[project] name` | string | R | Human name. | hook |
| `[project] kind` | `"repo"` \| `"folder"` | R | Git repo or plain working folder. | validator |
| `[project] repo` | `"<owner>/<name>"` \| `"none"` | R | GitHub repo, or `"none"`. | validator, skill |
| `[project] no_repo_reason` | string | R if `repo = "none"` | Why there is no repo. A missing repo is a recorded decision, never drift. | validator |
| `[project] status` | `"active"` \| `"paused"` \| `"retired"` | R | Retired projects load nothing beyond the default. | hook |
| `[memory] standing_scope` | list of bucket names | — | Buckets unlocked for every session in this project (SPEC-activation §2.2 "standing" tier). Never a Sensitive-rank bucket (invariant 2). | hook → cold-boot adapter |
| `[memory] recall` | list of strings | — | Seed queries for `search_thoughts` at session start. | hook |
| `[skills] prefer` | list of skill names | — | Skills this project's work normally uses. | hook |
| `[skills] avoid` | list of skill names | — | Skills that must not run here (e.g. a sibling project's skill). | hook |
| `[engagement] mode` | `"none"` \| `"per-prospect"` | — | Whether sessions read and update an engagement record. Default `"none"`. | hook |
| `[engagement] root` | path | R if `per-prospect` | Folder of engagement records, outside every repo. | hook, validator |
| `[ringer] task_types` | list of strings | — | Ringer `task_type` values this project produces, so its eval rows are findable. | validator |
| `[ringer] triggers` | list of `"path#anchor"` | — | Index of the Ringer steps declared in this project's `SKILL.md` files. The trigger itself stays in the skill (invariant 4). | validator, hook |
| `[review] design` | `"required"` \| `"optional"` \| `"off"` | — | Adversarial review of a design before it is built (lifecycle step 4). Default `"optional"`. | hook |
| `[review] change` | same | — | Adversarial review of a finished change before merge or release (step 6). Default `"optional"`. | hook |
| `[review] lenses` | list of strings | — | Review lenses, one reviewer each (e.g. `"abuse"`, `"coherence"`). Every name must be in the lens registry `checks/review_lenses.toml`. | review gate (§5.5), validator |
| `[review] egress` | `"local"` \| `"external"` | — | Where reviewers run. `"local"` (default): in-session subagents, nothing new leaves the machine. `"external"`: a Ringer swarm, one model family per lens — honoured only in a public repo and never for a path under `[outputs] allowed`. | review gate (§5.5) |
| `[review] surface` | `"commits"` \| `"outputs"` | — | What `change` review covers: code and spec changes (`"commits"`, default) or deliverables kept out of git (`"outputs"`), reviewed from the skill's pre-delivery step. | review gate (§5.5) |
| `[board] tag` | string | — | Written to a task's `metadata.project` on the task board. Default: `[project] id`. | skill, board |
| `[loops] routines` | list of scheduled-task ids | — | Scheduled routines this project owns, so Mission Control can group them. | Mission Control |
| `[done] criteria` | list of strings | — | What must be true before work counts as done. | hook |
| `[done] checks` | list of shell commands | — | Commands that prove it (e.g. the repo-standard check). Run by the agent, never by the hook. | agent, validator |
| `[outputs] allowed` | list of paths | — | Where this project may write output, relative to its root. Mirrors the owner's project-routing rule. | hook |

## 4. Examples

**A repo project that takes part in engagements** (bucket names are placeholders here because this
file is public):

```toml
[project]
spec_version = 1
id = "meeting-research"
name = "Meeting participant research"
kind = "repo"
repo = "edmatibag9Dev/Meeting-participant-analysis"
status = "active"

[memory]
standing_scope = ["<client-bucket>"]
recall = ["meeting research lessons", "participant brief accuracy"]

[skills]
prefer = ["meeting-research"]
avoid = ["demo-prep", "competitive-gap-analysis"]

[engagement]
mode = "per-prospect"
root = "~/Documents/Claude/Engagements"

[ringer]
task_types = ["research"]
triggers = ["skills/meeting-research/SKILL.md#how-to-run-it--ringer-verification-swarm-default-for-rule-2"]

[review]
design = "required"
change = "optional"
lenses = ["accuracy", "coherence"]
surface = "outputs"

[board]
tag = "meeting-research"

[done]
criteria = [
  "All three documents produced and validated",
  "Every spoken-aloud number re-derived by a verifier that did not see the research",
]
checks = [
  "node skills/meeting-research/scripts/validate_meeting_docs.js <meeting-folder>",
  "python3 ~/.claude/skills/repo-standard/scripts/repo-check.py .",
]

[outputs]
allowed = ["Meetings/"]
```

**A folder project with no repo:**

```toml
[project]
spec_version = 1
id = "home-network-monitor"
name = "Home network monitor"
kind = "folder"
repo = "none"
no_repo_reason = "Temporary troubleshooting tool; scheduled for removal once the network is stable."
status = "active"

[loops]
routines = ["network-monitor-weekend-report"]

[outputs]
allowed = ["logs/", "reports/"]
```

## 5. Readers

### 5.1 SessionStart hook — `hooks/project-manifest-bootstrap.sh` (built and installed 2026-10-25)

A third SessionStart hook, after `coldboot-bootstrap.sh`. Same posture as that hook: **echo-only, no
credentials, never touches a store, fail-open, exit 0 always.**

1. Find the manifest (§1 lookup). None → print nothing, exit 0.
2. Parse with `python3` `tomllib`. On any parse or validation error print one line —
   `project.toml invalid: <reason>; proceeding without it` — and exit 0.
3. Skip everything below if `status = "retired"`.
4. Print one instruction block (target under 250 tokens; empty sections omitted):

```
[project manifest · <id> · spec v1]
Memory: after the default-scope cold boot, call cold_boot_index again with scope=<standing_scope>
  (standing tier, announce it once); then search_thoughts for: <recall>.
Skills: prefer <prefer>; do not use <avoid>.
Engagement: read <root>/<prospect-slug>/ENGAGEMENT.md before work (create from _TEMPLATE if
  missing); update it before the session ends; pointers only.
Ringer steps declared in: <triggers>.
Review: design=<design>, change=<change>, lenses=<lenses>.
Done when: <criteria>. Prove with: <checks>.
Output only to: <allowed>.
```

As built: the working directory comes from the hook payload's `cwd` (falling back to the shell's);
a Sensitive bucket in `standing_scope` is dropped with a one-line note even if the validator was
skipped (defense in depth for invariant 2); check commands print in backticks. About 65 ms per run;
the fullest example prints about 248 tokens. Regression test: `python3 checks/test_manifest_bootstrap.py`.

The hook never runs `[done] checks` and never calls Ringer. The model acts on the block; the
existing gates (scope gate, escalation lanes, permission prompts) still decide what is allowed.

`--json` (v1.1, 2026-10-25): the same lookup and checks, printed as one JSON object for the gate
(§5.4) — `{path, root, id, status, repo, standing_scope, dropped, recall, memory_sha256, review,
review_sha256, outputs}`, `{}` when there is no manifest or it is retired, `{"error": ...}` when it is
invalid. `review`, `review_sha256` and `outputs` are what the review gate (§5.5) reads; `outputs` is
always present (an empty list when the manifest has no `[outputs]`), and the review gate treats a
missing key as unreadable. One parser serves all readers, so the gates inherit the Sensitive drop.
Still echo-only.

### 5.2 project-start skill — `skills/project-start/` (built and installed 2026-10-25)

Triggered by "start a project", "new project <X>", or "adopt <folder> as a project".

1. Classify the work (for client presales, the owner's project-routing rule first).
2. Decide repo or no repo with the owner. No repo → write the reason.
3. Repo → scaffold or check it with the `repo-standard` skill.
4. Write `project.toml` from the template, proposing `standing_scope` from the project's topic.
   The owner confirms the buckets; a Sensitive-rank bucket is refused, not proposed.
5. `per-prospect` engagement mode → make sure `[engagement] root` and its `_TEMPLATE/` exist. Never
   create a prospect record at project start; the first session for a prospect does that.
6. Run the validator (§5.3). Show the owner the file. Commit only on the owner's OK (repo projects).
7. Add a link to `project.toml` in the project's `AGENTS.md` file map.

As built: steps 4–6 run through `skills/project-start/scripts/write_manifest.py`, which writes
`project.toml.new`, runs the validator, and renames it only on a pass, so a rejected manifest never
reaches the hook. A folder inside a repo but not at its top level counts as a folder project.
Regression test: `python3 checks/test_project_start.py`.

### 5.3 Validator — `checks/manifest_check.py` (built 2026-10-25)

Exit 0 only when: required keys present and typed; `id` is a slug; `repo = "none"` has a reason;
`[engagement] root` exists and is outside every git repo; every `[ringer] triggers` entry resolves to
a heading anchor in a file that exists; every `[review] lenses` entry is in the lens registry
(`checks/review_lenses.toml`, §5.5); no `standing_scope` bucket appears on the local Sensitive
list; no line matches the public-repo scrub patterns. Prints every failure, one per line.

As built: exit `0` pass, `1` fail, `2` usage error. The Sensitive list defaults to the three
Sensitive-rank buckets in the memory system's classification spec; `--sensitive-file` replaces it
(one bucket per line). Owner-specific identifiers are added through `$SCRUB_PATTERN`, so they are
never committed. Regression test: `python3 checks/test_manifest_check.py` (17 cases: fixtures,
including an unregistered lens, plus run-time cases).

### 5.4 Memory-first gate — `hooks/memory-first-gate.sh` (built, tested and installed 2026-10-25)

**Why.** The first exit check (2026-10-25) showed the §5.1 block alone is not enough. In one pilot
project the session used the standing scope but never announced it. In the other, whose task was a
plain file read, the session made no memory call at all — not even the default cold boot that
`coldboot-bootstrap.sh` asks for. Printed instructions are skipped when the task does not itself need
memory.

**What.** A PreToolUse hook (matcher `*`) plus a PostToolUse / PostToolUseFailure hook (matcher
`mcp__open-brain__cold_boot_index|ToolSearch`). In an **attended** session whose manifest the owner
**approved**, it denies ordinary tool calls, with the load steps as the reason Claude reads, until
the session has called the memory server's `cold_boot_index` with default scope and with exactly the
standing scope (either order). Then it adds one context line — *announce "Memory scope: <buckets>
(standing, from project.toml)" once* — and is silent for the rest of the session.

| Rule | Behaviour |
|---|---|
| Attended, not scheduled | Gated only when `CLAUDE_CODE_SESSION_ATTENDED=1` and the session is not a scheduled run. Headless and scheduled runs are Safe-only and ignore standing scopes (SPEC-activation §2.4), so they are never pushed to widen. The desktop app's scheduled runs report as attended, so the gate reads the session's transcript once (`transcript_path`): a first user prompt that starts with `<scheduled-task ` marks the session scheduled, it is never held, and the first time it enters an approved project the audit records `skipped-scheduled`. An unreadable transcript is asked again on the next call and gated meanwhile. |
| Owner approval | A manifest counts only if its path and a SHA-256 of its `[memory]` table are in `~/.claude/state/memory-gate/approved.json`. `memory-first-gate.sh approve <folder>` writes the entry; it refuses without an interactive terminal, so the owner runs it, not an agent. Unlisted or edited `[memory]` → gate off, audited once as `unapproved`. |
| Exact scope | The scoped call must equal the standing set. A superset (for example one adding a Sensitive bucket) does not count. The announce text comes from the manifest, never from call arguments. |
| One server | Only `mcp__open-brain__` counts and is allow-listed; sibling memory servers do neither. |
| Always allowed | `ToolSearch` (loads the deferred memory tools), every `mcp__open-brain__` tool, the app's plan and wrap-up tools, and every subagent call (`agent_id` present; the parent passed before it could call Agent). |
| Attempt, not result | An errored cold boot counts (PostToolUseFailure). A `select:` ToolSearch for `cold_boot_index` that returns no match means the server is missing → release. Availability stays fail-open (SPEC-activation C11). |
| Hold cap | Holds are counted per user prompt (`prompt_id`), so parallel calls in one message are one hold. Release on the 3rd held prompt; inside one prompt, release on the 5th separate burst (held calls more than 2 s apart). Releases are audited as `exhausted`. |
| Folder changes | The manifest is re-resolved whenever the payload `cwd` changes, so a session that starts in a parent folder is gated once it moves into the project. |
| Fail-open | Bad payload, missing python3, crash or timeout → the call is allowed. Kill switch: `MEMORY_GATE=off` in the environment. |

**State.** `~/.claude/state/memory-gate/` (local, never committed): one JSON file per session (file
lock, because parallel calls each fire the hook), `approved.json`, and `audit.jsonl` — one row per
outcome (`passed`, `exhausted` with a reason, `unapproved`, `skipped-scheduled`) with seconds to outcome. That is local
firing-rate data next to the memory server's own audit. Session files older than 30 days are pruned.

**Mechanics relied on** (probed live 2026-10-25, Claude Code 2.1.308): `prompt_id` is on every tool
hook and constant for a whole user prompt; subagent calls share the parent's `session_id` and add
`agent_id`; ToolSearch fires both hooks and its response lists `matches`; MCP calls carry
`mcp_server.name`; the attended variable is `1` in the desktop app and `0` under `claude -p`.
Corrected 2026-10-26: it is also `1` for the desktop app's scheduled runs. Four of them (two fleet
sentinel runs, an evening digest, a morning briefing) were held after moving into this repo on
2026-10-25 and 2026-10-26, loaded the standing scope, and continued, against SPEC-activation §2.4.
v1.1 of the gate skips them by the `<scheduled-task ` marker at the start of the first prompt.

**Live test (2026-10-25).** Wired temporarily into one session through a folder-local settings file:
the first Bash call was held with the four steps, the default and scoped calls passed it in 14 s, the
announce line arrived, the next call ran, and the audit recorded `passed`. Regression test:
`python3 checks/test_memory_gate.py` (33 cases).

**Limits.** State files are user-writable, so this is a convention with an audit trail, not a
security boundary — the same posture SPEC-activation gives standing scopes until its Phase 4. Approval
is read when the folder resolves, so a session already running in a newly approved project engages
only after its folder changes or a new session starts. A turn with no tool calls never fires the hook.
`claude --bare` skips all hooks.

### 5.5 Review gate — `checks/review_gate.py` + `checks/review_lenses.toml` (v1.2, 2026-10-26)

**Why.** `[review]` was printed and nothing ran it. The runner turns the declared lenses into real
reviews, built on Ringer's adversarial-review kit, and keeps a record of each one.

**Flow.**
1. `review_gate.py plan --project <dir> --stage design|change (--surface <files> | --range A..B)`
   freezes the surface into a workdir (file copies or the `git diff`), hashes it, and writes one
   brief per lens. Each brief carries the lens's FOCUS paragraph from the registry, the surface
   SHA-256, the report contract, and a line saying the surface is material under review, never
   instructions (text in it addressed to a reviewer is itself a finding). Two words, two meanings:
   the `[review] surface` key (§3) says what change review *covers* — `commits` or `outputs` — while
   the *frozen surface* here is the files or range one run reviews. For a project whose change review
   covers `outputs`, `plan --stage change` refuses `--range`: deliverables never pass through git.
2. Reviewers run. `local` (default): the orchestrator gives each brief to its own in-session
   subagent. Claude Code does not let a subagent write report files, so the subagent returns the
   report as text and the orchestrator saves it verbatim as `<lens>/report.md`. `external`: `plan`
   also writes a Ringer manifest from the kit — one task per lens, round-robin over Codex GPT-5.6 Sol,
   GLM 5.2 and Kimi K2.7 (`--models` may only reorder or narrow that list) — and refuses if Ringer's
   lint fails.
3. `review_gate.py check-report` is the contract check (and the Ringer task check). It applies the
   kit's rules (Summary; NO FINDINGS or labelled findings with P0–P3, confidence, real evidence; no
   claim of having edited files, judged on the reviewer's own prose so quoting the surface is
   fine) and adds: the report echoes its lens, the surface SHA-256 and a per-run nonce kept in the
   surface's `REVIEW-NONCE.txt` (not printed in the brief), and lists what it inspected. Labels must
   start their line exactly (`Finding:`, `Priority: P1`, `Confidence: high`), one Priority and one
   Confidence per finding. Any label-like line in another form — bold, bulleted, heading, indented,
   numbered (`Finding 2:`) or another case (`FINDING:`) — fails, so no finding can hide from the
   parser; prose that merely starts with the word ("Finding labels that …") is left alone. A report
   with no findings has a line that begins with `NO FINDINGS`, and no Priority line anywhere.
4. `review_gate.py synthesize` lists every finding in `synthesis.md`, pinned to each report's
   SHA-256. The orchestrator sets each one's Disposition (confirmed / dismissed), Resolution for
   confirmed ones (fixed / deferred / accepted) and a Reason.
5. `review_gate.py record` prints every reason it refuses: the frozen surface or a report changed
   since synthesis; a finding missing, re-prioritised, or without a disposition and reason; a
   confirmed P0/P1 deferred, or marked fixed while the live source is identical to the reviewed
   surface or cannot be read. The live hash is built the same way as the reviewed one: the same files
   now, or for a range the diff from the same base to the working tree, so an unchanged source hashes
   equal. A P0/P1 that is dismissed or accepted needs the owner (`--owner`, interactive terminal).
   Counts are derived from `synthesis.md`. One row goes to `~/.claude/state/review-gate/records.jsonl`:
   project, stage, approved-policy hash, lenses, mode, models, reviewed surface hash, live source hash
   and `source_changed`, counts (incl. P0/P1 confirmed and dismissed), owner sign-offs, report and
   synthesis hashes.
6. `review_gate.py waive` (interactive terminal only) writes a reasoned waiver for one surface,
   1 to 30 days. `review_gate.py status` lists a project's records, marks expired waivers, shows
   P0/P1 dismissals, re-hashes the live source to say whether it has changed since review now (or
   that it cannot be read), and skips unreadable lines.

**Policy is owner-approved.** `memory-first-gate.sh approve` now records `[review]` and its hash
next to `[memory]`. `plan` uses the approved `[review]`; an edit takes effect only after the owner
approves again, so a change cannot switch off its own review. No approval → `plan` refuses.

**Egress.** Local unless every condition holds: the approved policy says `egress = "external"`; the
checkout's `origin` is the manifest's repo; `gh` reports it PUBLIC; the branch has an upstream; and
the surface is already published — every file inside the repo, tracked, and identical to its upstream
copy, or a range whose start (its diff base) and end commits are both already upstream — with no
path (including every path a range touches, read NUL-separated so spaces survive) under
`[outputs] allowed`. Otherwise it falls back to local and says why. Unpushed work is never "already
public". Known gaps, deferred because no approved manifest sets `egress = "external"` (2026-10-26):
"upstream" is the local remote-tracking ref, which a local process can move without pushing; `plan.json`
is not pinned and external workers share the run folder; `[outputs]` is read from the live manifest,
not an approved copy. Close them before any project is approved for external review.

**What is enforced, and what is not.** Nothing holds a push or a delivery yet. The design review
(2026-10-25, three model families, 26 findings) showed a command-string push gate is bypassable and
no current manifest needs one: this repo's `change` is optional, and the four presales repos review
outputs, which never pass through git. A future push gate would be git's own `pre-push` hook,
installed globally, keyed to the exact ref range. `design = "required"` has no mechanical boundary.
The four presales repos set `surface = "outputs"`, and each skill's pre-delivery step calls `plan`
(2026-10-25). Records are user-writable, and in local mode the orchestrator saves the reports, so this
is a convention with an audit trail, not a security boundary. The owner checks (`record --owner`,
`waive`) test only that stdin and stdout are a terminal; a pseudo-terminal wrapper meets that, so
`owner_signed` records that a terminal answered yes, not who did.

**Reviewed (2026-10-25).** The design: a Ringer run with one model family per lens (26 findings,
confirmed ones folded in before building). v1.0 of the code: a local end-to-end run on a throwaway
project, one subagent per lens (abuse, coherence, enforceability). It found 23 issues, including two
P1s — a dismissed P0/P1 skipped the owner, and a lower-case priority skipped the P0/P1 rules — and
caught itself: the abuse report quoted the self-fix pattern and failed v1.0's own check. All 23 were
fixed in v1.1, and the run was recorded through `record` with `source_changed = true` (in the throwaway
project's own state folder, so no row survives).

**Reviewed again (2026-10-26).** v1.1, local, the same three lenses, run through the gate itself as
this repo's first durable record. 19 findings, 14 distinct after merging duplicates, all confirmed.
Two P1s: range surfaces hashed the reviewed and live source two different ways, so "fixed with no
change" was never caught on a range (three reviewers found it); and a finding label in another form
(indented, upper-case, numbered) was invisible to the parser, so a P0 could hide beside `NO FINDINGS`.
The same parser also failed honest prose — a summary bullet starting with the word "Finding" — which
this run hit. v1.2 fixes both P1s and the smaller findings; the three external-mode gaps above are
deferred.

Regression test: `python3 checks/test_review_gate.py` (56 cases).

## 6. Invariants

1. **Publishable.** No secrets, keys, prospect or client names, personal identifiers, or private
   paths beyond `~/`. The file is committed, and some repos are public.
2. **Never Sensitive.** `standing_scope` never names a Sensitive-rank bucket; those always need a live
   in-session confirm (SPEC-activation §2.2). An unknown bucket is not resolved locally: the memory
   server hard-errors it and the session proceeds at default scope.
3. **Declares, never grants.** A manifest cannot widen tool permissions, skip an escalation lane, or
   approve a prospect-facing release.
4. **One home per trigger.** Ringer steps are declared in the project's `SKILL.md`. `[ringer] triggers`
   is an index the validator checks against those files, never a second trigger.
5. **Fail-open.** A missing, malformed, or retired manifest never blocks or slows a session; it only
   removes the extra instructions.
6. **Authorization surfaces are owner-only.** `[memory]` and `[review]` change only with the owner's
   explicit OK.
7. **Portable.** Plain TOML, standard-library parsing, no harness-specific fields. A Codex session must
   be able to act on it from `AGENTS.md` alone.
8. **Versioned.** Readers check `spec_version`; a higher version than they know → treat as malformed
   (fail-open) and say so once.

## 7. Relationship to existing rules

| Existing rule | Today | With the manifest |
|---|---|---|
| Standing scope (SPEC-activation §2.2) | A `scope: [...]` line in the project's `CLAUDE.md` (until 2026-10-25) | `[memory] standing_scope`, owner-approved by hash. SPEC-activation v2.2 (2026-10-25) made this the only home; the one `CLAUDE.md` declaration was migrated, so the interim intersection rule is gone. |
| Project routing (owner's global instructions) | Output paths listed in a global table | `[outputs] allowed` per project; the global table stays the source for presales routing. |
| Engagement record | Global instruction steps + each presales repo's scope gate | `[engagement]` makes it machine-readable, so non-presales projects can opt in. |
| Ringer triggers | Declared in `SKILL.md` | Unchanged; indexed in `[ringer] triggers`. |
| Adversarial review | Required in one repo by its own `AGENTS.md` | `[review]` per project; the requiring repo keeps its rule. |

## 8. Build order and exit criteria

1. `checks/manifest_check.py` with fixtures (one valid, one per failure class). **Done 2026-10-25.**
2. `project-manifest-bootstrap.sh` in `hooks/`, installed as the third SessionStart hook. **Built, tested and installed 2026-10-25.**
3. project-start skill. **Built, tested and installed 2026-10-25** (`~/.claude/skills/project-start` links to this repo).
4. Adopt on two projects: meeting research (engagement, Ringer, review) and this repo (no engagement). **Done 2026-10-25:** both manifests written through the project-start skill; the hook prints about 251 and 185 tokens.
   **Extended 2026-10-25** to the owner's three other presales repos (demo prep, RFx gap analysis,
   competitive gap analysis), same skill and validator. Each has a per-prospect engagement record,
   change review required, and the sibling presales skills listed as `avoid`; none declares a Ringer
   trigger yet. The hook prints about 234, 209 and 202 tokens. The owner approved all five manifests
   for the memory-first gate (§5.4).
5. Portability test: a Codex session in each project reads the manifest and states what it would load.
   **Passed 2026-10-25** (Ringer run `manifest-readability`, Codex `gpt-5.6-sol`): given only `AGENTS.md`
   and `project.toml`, with no global instructions and no hook, each session reproduced every manifest
   field verbatim on its first attempt (an executed check compared all fields with the real file),
   found the manifest through the `AGENTS.md` file-map row, and reported nothing unclear. In the
   meeting-research repo it also applied the scope gate first, from the `AGENTS.md` mirror of the
   routing rule.
   **Finding — the manifest carries the *what*; the harness carries the *how*.** Codex named the
   right buckets but not the memory tool or its two-call order (default scope first, then the
   standing scope); that instruction lives only in this harness's hook. A non-Claude session acts on
   `[memory]` only when its own session adapter supplies the how. Tracked in §9.

6. Exit check, first attempt 2026-10-25: **failed.** Both pilot sessions printed the block; one used
   the standing scope without announcing it, the other made no memory call at all. Response: the
   memory-first gate (§5.4), built and tested the same day.
   Second attempt 2026-10-25, after the gate was installed and the owner approved both manifests:
   **passed.** In each project the gate held the first prompt's tool calls; the session ran
   ToolSearch, the default cold boot, the standing-scope cold boot and the recall searches, announced
   "Memory scope: <bucket> (standing, from project.toml)" once, and every later call ran. The gate
   audit recorded `passed` with one held prompt (15.9 s and 11.5 s). One of the two was an earlier
   session continued rather than a new one; the gate engaged because that session had no gate state
   yet. The broken-manifest part of the exit criterion is covered by the bootstrap regression test
   (13/13), not a live session.

**Exit:** in both projects a fresh session announces the standing scope without a manual step, follows
the engagement and review lines, and a deliberately broken manifest produces the one-line notice and
nothing else.

## 9. Open questions

- **Memory "how" for non-Claude agents.** The step 5 test showed a Codex session reads `[memory]`
  correctly but has no instruction for the memory tool or its call order. The Codex session adapter
  (a pilot in the memory system) has to supply it; the manifest stays harness-neutral by design.

- **Local Sensitive list.** The validator needs the Sensitive-rank bucket names without calling the
  memory server. Options: a small file in AI-Memory-System it can read, or the validator skips the
  check and relies on the server.
- ~~**SPEC-activation amendment.**~~ Closed 2026-10-25: SPEC-activation v2.2 moves the standing-scope
  home to `project.toml` (§2.2) and records the memory-first gate's enforced attempt in C11.
- **Task-board filter.** Tasks are memory-store thoughts with free-form `metadata`; nothing writes
  `metadata.project` yet and the board has no project filter. The ai-task-manager repo owns that
  change.
- **Mission Control grouping** by `[loops] routines` is owned by Mission-Control-Dashboard.
