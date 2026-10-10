#!/usr/bin/env python3
"""repo_sweep.py — check every owner repo against the repo standard (monthly maintenance, Phase C).

Usage:
  repo_sweep.py --staging DIR --out OUT.json [--no-fetch]

What it does (report-only; it never edits a working tree you use):
  1. Lists the authenticated owner's GitHub repos (`gh repo list`).
  2. Finds a local clone for each one under the search roots below.
  3. Owner repos with no local clone are cloned (or refreshed) into DIR/clones/<name>,
     a staging area nobody works in, so they can be checked and later fixed there.
  4. Runs repo-check.py on every clone and records FAIL/WARN lines, dirty state and branch.
  5. Writes OUT.json and prints a one-line-per-repo summary.

Excluded: forks, archived repos (listed only), repos owned by someone else, clones with no
remote. Standard library only (Python 3.9+); needs an authenticated `gh` CLI.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
REPO_CHECK = HOME / ".claude/skills/repo-standard/scripts/repo-check.py"
STANDARD = HOME / ".claude/REPO-STANDARD.md"
# (root, max depth) pairs searched for clones.
ROOTS = [(HOME / "Documents", 6), (HOME, 2)]
SKIP_NAMES = {"Library", ".Trash", "node_modules", "_archive", "_gsdata_", "ringer-jobs",
              "_maintenance-staging", ".git", ".venv", "Mobile Documents", "Applications"}
SKIP_SUBPATHS = (".claude/worktrees",)
# Preferred home for a clone when the same repo is cloned twice.
PREFERRED = HOME / "Documents" / "Claude"


def run(args, cwd=None, check=False):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"{' '.join(args)} failed: {r.stderr.strip()}")
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def slug_of(repo: Path) -> str:
    code, url, _ = run(["git", "-C", str(repo), "remote", "get-url", "origin"])
    if code:
        return ""
    m = re.search(r"github\.com[:/]+([^/]+/[^/]+?)(?:\.git)?/?$", url)
    return m.group(1) if m else ""


def find_clones() -> dict:
    found = {}
    for root, depth in ROOTS:
        base = len(root.parts)
        for cur, dirs, _ in os.walk(root):
            p = Path(cur)
            if any(s in p.as_posix() for s in SKIP_SUBPATHS):
                dirs[:] = []
                continue
            if ".git" in dirs:
                found.setdefault(p, None)
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if d not in SKIP_NAMES and not d.startswith(".")]
            if len(p.parts) - base >= depth:
                dirs[:] = []
    by_slug, no_remote = {}, []
    for p in sorted(found):
        s = slug_of(p)
        if not s:
            no_remote.append(str(p))
            continue
        by_slug.setdefault(s.lower(), []).append(p)
    return by_slug, no_remote


def pick(paths):
    pref = [p for p in paths if str(p).startswith(str(PREFERRED))]
    return (pref or paths)[0]


def stage_clone(slug: str, branch: str, staging: Path) -> Path:
    dest = staging / "clones" / slug.split("/")[1]
    if (dest / ".git").exists():
        run(["git", "-C", str(dest), "fetch", "--quiet", "origin"], check=True)
        run(["git", "-C", str(dest), "checkout", "--quiet", "-B", branch, f"origin/{branch}"], check=True)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["gh", "repo", "clone", slug, str(dest), "--", "--quiet"], check=True)
    return dest


def check(path: Path, fetch: bool) -> dict:
    args = [sys.executable, str(REPO_CHECK), str(path), "--quiet"] + (["--fetch"] if fetch else [])
    _, out, err = run(args)
    fails = [ln.strip()[6:] for ln in out.splitlines() if ln.strip().startswith("FAIL")]
    warns = [ln.strip()[6:] for ln in out.splitlines() if ln.strip().startswith("WARN")]
    _, status, _ = run(["git", "-C", str(path), "status", "--porcelain"])
    _, branch, _ = run(["git", "-C", str(path), "branch", "--show-current"])
    return {"fails": fails, "warns": warns, "dirty_files": len(status.splitlines()) if status else 0,
            "branch": branch, "error": err if not out else ""}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staging", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args()

    _, owner, _ = run(["gh", "api", "user", "-q", ".login"], check=True)
    _, raw, _ = run(["gh", "repo", "list", owner, "--limit", "300", "--json",
                     "name,visibility,isArchived,isFork,defaultBranchRef"], check=True)
    repos = json.loads(raw)
    by_slug, no_remote = find_clones()
    std = re.search(r"^# Standard version:\s*(\S+)", STANDARD.read_text(), re.M)

    result = {"owner": owner, "standard_version": std.group(1) if std else "unknown",
              "repos": [], "skipped": [], "duplicate_clones": [], "no_remote_clones": no_remote}
    for r in sorted(repos, key=lambda x: x["name"].lower()):
        slug = f"{owner}/{r['name']}"
        if r["isFork"]:
            result["skipped"].append({"repo": r["name"], "reason": "fork"})
            continue
        if r["isArchived"]:
            result["skipped"].append({"repo": r["name"], "reason": "archived (read-only on GitHub)"})
            continue
        paths = by_slug.get(slug.lower(), [])
        if len(paths) > 1:
            result["duplicate_clones"].append({"repo": r["name"], "paths": [str(p) for p in paths]})
        branch = (r.get("defaultBranchRef") or {}).get("name") or "main"
        entry = {"repo": r["name"], "visibility": r["visibility"], "default_branch": branch}
        try:
            if paths:
                entry.update(kind="local", path=str(pick(paths)))
            else:
                entry.update(kind="staging", path=str(stage_clone(slug, branch, a.staging)))
            entry.update(check(Path(entry["path"]), fetch=not a.no_fetch))
        except RuntimeError as e:
            entry.update(kind=entry.get("kind", "staging"), error=str(e), fails=[], warns=[])
        result["repos"].append(entry)

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2))
    print(f"repo_sweep · owner {owner} · standard {result['standard_version']} · "
          f"{len(result['repos'])} checked · {len(result['skipped'])} skipped")
    for e in result["repos"]:
        tag = "ERR " if e.get("error") else ("FAIL" if e["fails"] else "pass")
        print(f"  {tag}  {len(e['fails'])}F {len(e['warns'])}W  {e['kind']:7} {e['repo']}"
              + (f"  (dirty {e['dirty_files']})" if e.get("dirty_files") else ""))
    for s in result["skipped"]:
        print(f"  skip  {s['repo']}: {s['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
