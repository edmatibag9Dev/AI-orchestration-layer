#!/bin/bash
# prep_branch.sh — open a fix branch for one repo without touching its working tree (Phase D).
#
# Usage: prep_branch.sh <repo-path> <branch> <staging-dir>
#
# Creates (or reuses) a git worktree at <staging-dir>/worktrees/<repo-name>, on <branch>
# started from origin's default branch. The clone you work in keeps its checked-out branch
# and uncommitted files untouched. Prints the worktree path. Never pushes.
set -euo pipefail

repo="$1"; branch="$2"; staging="$3"
name="$(basename "$(git -C "$repo" remote get-url origin)" .git)"
wt="$staging/worktrees/$name"

git -C "$repo" fetch --quiet origin
default="$(git -C "$repo" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || true)"
if [ -z "$default" ]; then
  git -C "$repo" remote set-head origin --auto >/dev/null
  default="$(git -C "$repo" symbolic-ref --short refs/remotes/origin/HEAD)"
fi

if [ -e "$wt/.git" ]; then
  echo "$wt"
  exit 0
fi
mkdir -p "$staging/worktrees"
if git -C "$repo" show-ref --verify --quiet "refs/heads/$branch"; then
  git -C "$repo" worktree add --quiet "$wt" "$branch"
else
  git -C "$repo" worktree add --quiet -b "$branch" "$wt" "$default"
fi
echo "$wt"
