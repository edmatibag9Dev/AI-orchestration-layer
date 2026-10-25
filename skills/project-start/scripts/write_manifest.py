#!/usr/bin/env python3
"""Write a project's project.toml (SPEC-project-manifest §5.2, project-start skill).

    write_manifest.py --dir <folder> --id <slug> --name "<name>" [options] [--dry-run] [--force]

Detects git and the origin remote, refuses Sensitive-rank buckets and existing manifests (unless
--force), checks the engagement folder, writes project.toml.new, runs checks/manifest_check.py on
it, and renames it to project.toml only when the validator passes. On any failure nothing is left
behind. Exit 0 written (or dry run printed), 1 refused or invalid.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = REPO_ROOT / "checks" / "manifest_check.py"
DEFAULT_SENSITIVE = ["Trading", "Short Trading", "Business"]
DEFAULT_ENGAGEMENT_ROOT = "~/Documents/Claude/Engagements"


def q(s):
    return json.dumps(s, ensure_ascii=False)


def qlist(xs):
    return "[" + ", ".join(q(x) for x in xs) + "]"


def git_info(folder):
    top = subprocess.run(["git", "-C", str(folder), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != folder.resolve():
        return None
    url = subprocess.run(["git", "-C", str(folder), "remote", "get-url", "origin"],
                         capture_output=True, text=True).stdout.strip()
    m = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def render(a, kind, repo):
    out = ["[project]", "spec_version = 1", f"id = {q(a.id)}", f"name = {q(a.name)}",
           f"kind = {q(kind)}", f"repo = {q(repo)}"]
    if repo == "none":
        out.append(f"no_repo_reason = {q(a.no_repo_reason or '')}")
    out.append(f"status = {q(a.status)}")

    def section(name, pairs):
        body = [f"{k} = {v}" for k, v in pairs if v is not None]
        if body:
            out.extend(["", f"[{name}]", *body])

    L = lambda xs: qlist(xs) if xs else None
    section("memory", [("standing_scope", L(a.scope)), ("recall", L(a.recall))])
    section("skills", [("prefer", L(a.prefer)), ("avoid", L(a.avoid))])
    if a.engagement == "per-prospect":
        section("engagement", [("mode", q("per-prospect")), ("root", q(a.engagement_root))])
    section("ringer", [("task_types", L(a.task_type)), ("triggers", L(a.trigger))])
    section("review", [("design", q(a.review_design) if a.review_design else None),
                       ("change", q(a.review_change) if a.review_change else None),
                       ("lenses", L(a.lens))])
    section("board", [("tag", q(a.board_tag) if a.board_tag else None)])
    section("loops", [("routines", L(a.routine))])
    section("done", [("criteria", L(a.done)), ("checks", L(a.check))])
    section("outputs", [("allowed", L(a.output))])
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--no-repo-reason")
    ap.add_argument("--status", default="active", choices=["active", "paused", "retired"])
    ap.add_argument("--engagement", default="none", choices=["none", "per-prospect"])
    ap.add_argument("--engagement-root", default=DEFAULT_ENGAGEMENT_ROOT)
    ap.add_argument("--review-design", choices=["required", "optional", "off"])
    ap.add_argument("--review-change", choices=["required", "optional", "off"])
    ap.add_argument("--board-tag")
    for flag in ("scope", "recall", "prefer", "avoid", "task-type", "trigger", "lens",
                 "routine", "done", "check", "output"):
        ap.add_argument(f"--{flag}", action="append", default=[])
    ap.add_argument("--sensitive-file")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    folder = Path(os.path.expanduser(a.dir)).resolve()
    if not folder.is_dir():
        print(f"REFUSED: {folder} is not a folder")
        return 1
    target = folder / "project.toml"
    if target.exists() and not a.force:
        print(f"REFUSED: {target} already exists. Show it to the owner; rerun with --force only "
              f"if they ask to replace it.")
        return 1

    sensitive = DEFAULT_SENSITIVE
    if a.sensitive_file:
        sensitive = [l.split("#")[0].strip() for l in Path(a.sensitive_file).read_text().splitlines()]
        sensitive = [s for s in sensitive if s]
    bad = [b for b in a.scope if b.lower() in {s.lower() for s in sensitive}]
    if bad:
        print(f"REFUSED: Sensitive-rank bucket(s) {', '.join(bad)} cannot be a standing scope; "
              f"they need a live confirm in each session.")
        return 1

    repo = git_info(folder)
    if repo is None:
        kind, repo = "folder", "none"
    elif repo == "":
        print("REFUSED: this folder is a git repo with no origin remote. Add the GitHub remote "
              "first (repo-standard skill), then rerun.")
        return 1
    else:
        kind = "repo"
    if repo == "none" and not (a.no_repo_reason or "").strip():
        print('REFUSED: no git repo here, so --no-repo-reason "<why>" is required. Ask the owner '
              "for one sentence.")
        return 1

    if a.engagement == "per-prospect":
        root = Path(os.path.expanduser(a.engagement_root))
        if not (root / "_TEMPLATE" / "ENGAGEMENT.md").is_file():
            print(f"REFUSED: {a.engagement_root}/_TEMPLATE/ENGAGEMENT.md not found. The engagement "
                  f"folder and its template must exist before a project opts in.")
            return 1

    text = render(a, kind, repo)
    staged = folder / "project.toml.new"
    staged.write_text(text)
    try:
        cmd = [sys.executable, str(VALIDATOR), str(staged)]
        if a.sensitive_file:
            cmd += ["--sensitive-file", a.sensitive_file]
        v = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        if a.dry_run:
            staged.unlink(missing_ok=True)
    if v.returncode != 0:
        staged.unlink(missing_ok=True)
        print("INVALID: the validator rejected the manifest; nothing was written.")
        print(v.stdout.strip())
        return 1

    if a.dry_run:
        print(f"DRY RUN (validator passed) — would write {target}:\n")
        print(text, end="")
        return 0
    staged.replace(target)
    print(f"WROTE {target} (validator passed):\n")
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
