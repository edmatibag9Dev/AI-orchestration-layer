# SPEC-project-manifest.md — `project.toml`, the project manifest

*Owner: the owner · Drafted: 2026-10-25 · Status: DRAFT — validator built 2026-10-25; hook built and installed 2026-10-25; skill built 2026-10-25, not installed · spec_version 1*

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
| `[review] lenses` | list of strings | — | Review lenses, one reviewer per model family (e.g. `"abuse"`, `"coherence"`). | skill, Ringer manifest |
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

### 5.2 project-start skill — `skills/project-start/` (built 2026-10-25, not installed)

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
a heading anchor in a file that exists; no `standing_scope` bucket appears on the local Sensitive
list; no line matches the public-repo scrub patterns. Prints every failure, one per line.

As built: exit `0` pass, `1` fail, `2` usage error. The Sensitive list defaults to the three
Sensitive-rank buckets in the memory system's classification spec; `--sensitive-file` replaces it
(one bucket per line). Owner-specific identifiers are added through `$SCRUB_PATTERN`, so they are
never committed. Regression test: `python3 checks/test_manifest_check.py` (11 fixtures plus 4
run-time cases).

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
| Standing scope (SPEC-activation §2.2) | A `scope: [...]` line in the project's `CLAUDE.md` | `[memory] standing_scope`. Until AI-Memory-System amends §2.2, both are valid; if both exist and differ, the hook uses their **intersection** and prints the conflict. |
| Project routing (owner's global instructions) | Output paths listed in a global table | `[outputs] allowed` per project; the global table stays the source for presales routing. |
| Engagement record | Global instruction steps + each presales repo's scope gate | `[engagement]` makes it machine-readable, so non-presales projects can opt in. |
| Ringer triggers | Declared in `SKILL.md` | Unchanged; indexed in `[ringer] triggers`. |
| Adversarial review | Required in one repo by its own `AGENTS.md` | `[review]` per project; the requiring repo keeps its rule. |

## 8. Build order and exit criteria

1. `checks/manifest_check.py` with fixtures (one valid, one per failure class). **Done 2026-10-25.**
2. `project-manifest-bootstrap.sh` in `hooks/`, installed as the third SessionStart hook. **Built, tested and installed 2026-10-25.**
3. project-start skill. **Built and tested 2026-10-25; installing (the `~/.claude/skills/` symlink) waits for the owner.**
4. Adopt on two projects: meeting research (engagement, Ringer, review) and this repo (no engagement). **Done 2026-10-25:** both manifests written through the project-start skill; the hook prints about 251 and 185 tokens.
5. Portability test: a Codex session in each project reads the manifest and states what it would load.

**Exit:** in both projects a fresh session announces the standing scope without a manual step, follows
the engagement and review lines, and a deliberately broken manifest produces the one-line notice and
nothing else.

## 9. Open questions

- **Local Sensitive list.** The validator needs the Sensitive-rank bucket names without calling the
  memory server. Options: a small file in AI-Memory-System it can read, or the validator skips the
  check and relies on the server.
- **SPEC-activation amendment.** §2.2 names `CLAUDE.md` as the standing-scope home. AI-Memory-System
  owns that change.
- **Task-board filter.** Tasks are memory-store thoughts with free-form `metadata`; nothing writes
  `metadata.project` yet and the board has no project filter. The ai-task-manager repo owns that
  change.
- **Mission Control grouping** by `[loops] routines` is owned by Mission-Control-Dashboard.
