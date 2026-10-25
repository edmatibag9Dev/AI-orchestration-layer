---
name: project-start
description: Start a new project, or adopt an existing folder or repo as one, by writing its project.toml manifest (SPEC-project-manifest) so every later session loads the right memory scope, skills, engagement record, Ringer steps, review gates and done criteria. Use whenever the user says "start a project", "new project", "set up a project for X", "adopt this folder as a project", "add a project.toml", "make this a managed project", or begins work that will span many sessions in a folder that has no project.toml — even if they don't say "manifest". Calls repo-standard when a repo is needed. Not for one-off tasks, and not for editing an existing project.toml beyond what its owner asks.
---

# project-start — write a project's manifest

A project's `project.toml` tells every future session, through a SessionStart hook, what engages
when work happens there: which memory buckets load, which skills fit, whether sessions read and
update an engagement record, where Ringer steps are declared, which adversarial reviews are
required, what "done" means, and where output may go. The contract is
`SPEC-project-manifest.md` in the `AI-orchestration-layer` repo; this skill is its writer (§5.2).

The manifest is small, but two of its sections are **authorization**: `[memory]` widens what memory
every session in the project can see, and `[review]` decides which gates are mandatory. That is why
the owner confirms them, and why nothing is written before the owner has seen the values.

## Workflow

### 1. Classify the work

If this is client presales work, the owner's project-routing rule (Rule 0 in the global
instructions) decides which repo owns it; follow that first. Otherwise, confirm with the owner what
the project is and which folder it lives in. If a `project.toml` already exists in that folder, stop
and show it: this skill creates manifests; it does not silently rewrite them.

### 2. Repo or no repo

- **Already a git repo:** `kind = "repo"`; the writer reads `owner/name` from the `origin` remote.
- **Needs a repo:** use the `repo-standard` skill to create or standardize it first, then come back.
- **No repo:** ask the owner why, in one sentence, and record it as `no_repo_reason`. A missing
  repo is fine; an unexplained one is drift.

### 3. Propose the values

Draft every field from what you know about the project, then show the owner a short table. Useful
sources:

| Field | Where to look |
|---|---|
| `standing_scope` | The memory index's bucket list (`cold_boot_index`). Pick the one or two buckets the project's topic lives in. Never a Sensitive-rank bucket (Trading, Short Trading, Business): those need a live confirm every time, so the writer refuses them. |
| `recall` | Two or three short queries a session would want answered before starting work. |
| `prefer` / `avoid` | Skills this work uses; sibling skills that must not run here (e.g. another presales project's skill). |
| `engagement` | `per-prospect` for client engagements that span sessions and repos; otherwise `none`. |
| `triggers` | Only Ringer steps already declared as headings in this project's `SKILL.md` files. Never invent one; the validator checks each anchor exists. |
| `review` | `design` / `change`: `required`, `optional` or `off`. Required where a wrong design or change is costly. |
| `done` | Criteria in plain words, plus the commands that prove them (the repo-standard check for repo projects). |
| `outputs` | The folders this project may write to. |

Ask the owner to confirm `[memory]` and `[review]` explicitly. Everything else they can wave
through.

### 4. Write it with the bundled writer

```bash
python3 <this-skill>/scripts/write_manifest.py --dir <project-folder> \
  --id <slug> --name "<name>" [--no-repo-reason "<why>"] \
  [--scope "<bucket>"]... [--recall "<query>"]... [--prefer <skill>]... [--avoid <skill>]... \
  [--engagement per-prospect] [--trigger "<path>#<anchor>"]... [--task-type <type>]... \
  [--review-design required] [--review-change optional] [--lens <lens>]... \
  [--done "<criterion>"]... [--check "<command>"]... [--output <folder/>]... \
  [--routine <scheduled-task-id>]... [--dry-run]
```

Run it with `--dry-run` first and show the owner the file it would write. Then run it for real.
The writer detects git and the `origin` remote itself, refuses Sensitive buckets and existing
manifests (unless `--force`), checks the engagement folder and its `_TEMPLATE/`, writes to
`project.toml.new`, runs the validator (`checks/manifest_check.py`), and only renames the file to
`project.toml` when the validator passes. On failure it prints every validator line and leaves
nothing behind, so a broken manifest never reaches the hook.

### 5. Show what the next session will see

Run the installed hook against the folder and show the owner the block it prints:

```bash
echo '{"cwd":"<project-folder>"}' | ~/.claude/hooks/project-manifest-bootstrap.sh
```

If it prints nothing, the hook is not installed or the manifest did not land; say which.

### 6. Record it (repo projects)

Add a `project.toml` row to the project's `AGENTS.md` file map, then commit `project.toml` and
`AGENTS.md` by name following the repo's `CONTRIBUTING.md` — only after the owner says to. For a
folder project there is nothing to commit.

## What this skill never does

- Create a prospect's engagement record. The first session for a prospect does that, from
  `_TEMPLATE`, inside the engagement folder — never inside a repo.
- Put a Sensitive-rank bucket in `standing_scope`, or change `[memory]` / `[review]` without the
  owner's explicit OK.
- Add a Ringer trigger that is not already a heading in the project's `SKILL.md`. The manifest
  indexes triggers; the skill file owns them.
- Commit, push, or install anything without the owner's go-ahead.
