#!/usr/bin/env python3
"""release_notes.py — Claude Code changelog entries since the last maintenance review (Phase A).

Usage:
  release_notes.py --state STATE.json --out OUT.json [--since YYYY-MM-DD]
  release_notes.py --state STATE.json --save-version X.Y.Z

Reads the public Claude Code CHANGELOG.md and returns every version newer than
`claude_code_last_version` in STATE.json. With no saved version, `--since` picks the version
that was current on that date (via the file's commit history). Each entry is tagged with
the instruction surfaces it may touch (keyword match) and given a priority: P1 (a feature
added, changed or removed: read every line), P2 (a fix or improvement touching hooks, skills,
scheduled runs, MCP or instruction files: scan), or drop (other platforms, unrelated fixes).
Every entry stays in OUT.json.

`--save-version` records the version reviewed. Call it only after the report is written,
so a failed run re-reads the same notes next time. Standard library + `gh` CLI.
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = "anthropics/claude-code"
RAW = "https://raw.githubusercontent.com/" + REPO + "/{ref}/CHANGELOG.md"
# Surface tag -> keywords. Case-insensitive substring match on each changelog line.
TAGS = {
    "hooks": ["hook", "sessionstart", "sessionend", "pretooluse", "posttooluse", "userpromptsubmit", "stop "],
    "skills": ["skill", "frontmatter", "slash command", "plugin"],
    "instructions": ["claude.md", "agents.md", "memory", "instruction", "system prompt", "output style"],
    "settings": ["settings", "permission", "environment variable", "env var", "allowedtools"],
    "scheduled": ["schedul", "routine", "cron", "headless", "background", "-p ", "print mode"],
    "mcp": ["mcp", "connector"],
    "subagents": ["subagent", "agent ", "agents", "workflow"],
    "git": ["git ", "worktree", "commit", "pull request"],
    "tools": ["read tool", "edit tool", "write tool", "bash", "webfetch", "websearch", "todo", "artifact"],
    "breaking": ["removed", "deprecat", "renamed", "no longer", "breaking", "now requires", "replaced"],
}


# Platforms not in use here (macOS desktop + CLI). Lines for them are dropped.
OTHER_PLATFORMS = ("[vscode]", "[jetbrains]", "windows:", "linux:", "self-hosted", "[cloud")
# First words that announce a behavior change worth reading in full.
CHANGE_VERBS = ("added", "changed", "removed", "deprecated", "renamed", "reverted", "updated", "replaced")
# Tags close enough to this setup that a fix or improvement is worth a scan.
CLOSE_TAGS = {"hooks", "skills", "scheduled", "mcp", "instructions"}


def priority(text: str, tags: list) -> str:
    """P1 = read every line; P2 = scan; drop = other platform or unrelated fix."""
    low = text.lower()
    if low.startswith(OTHER_PLATFORMS):
        return "drop"
    word = re.sub(r"^\[[^\]]*\]\s*", "", low).split(" ", 1)[0]
    if word in CHANGE_VERBS or ("breaking" in tags and word not in ("fixed", "improved")):
        return "P1"
    if (CLOSE_TAGS | {"breaking"}) & set(tags):
        return "P2"
    return "drop"


def fetch(ref: str) -> str:
    with urllib.request.urlopen(RAW.format(ref=ref), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parse(text: str) -> list:
    out, cur = [], None
    for ln in text.splitlines():
        m = re.match(r"^##\s+(\d+\.\d+\.\d+)", ln)
        if m:
            cur = {"version": m.group(1), "lines": []}
            out.append(cur)
        elif cur and ln.startswith("- "):
            cur["lines"].append(ln[2:].strip())
    return out


def vkey(v: str):
    return tuple(int(x) for x in v.split("."))


def version_at(date: str) -> str:
    q = f"repos/{REPO}/commits?path=CHANGELOG.md&until={date}T23:59:59Z&per_page=1"
    r = subprocess.run(["gh", "api", q, "-q", ".[0].sha"], capture_output=True, text=True)
    sha = r.stdout.strip()
    if not sha:
        raise SystemExit(f"no CHANGELOG commit found on or before {date}")
    return parse(fetch(sha))[0]["version"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--since")
    ap.add_argument("--save-version")
    a = ap.parse_args()
    state = json.loads(a.state.read_text()) if a.state.exists() else {}

    if a.save_version:
        state["claude_code_last_version"] = a.save_version
        a.state.write_text(json.dumps(state, indent=2) + "\n")
        print(f"saved claude_code_last_version = {a.save_version}")
        return 0
    if not a.out:
        ap.error("--out is required unless --save-version is given")

    base = state.get("claude_code_last_version") or (version_at(a.since) if a.since else None)
    if not base:
        ap.error("no saved version in state; pass --since YYYY-MM-DD")
    versions = [v for v in parse(fetch("main")) if vkey(v["version"]) > vkey(base)]
    entries = []
    for v in versions:
        for ln in v["lines"]:
            low = ln.lower()
            tags = [t for t, kws in TAGS.items() if any(k in low for k in kws)]
            entries.append({"version": v["version"], "priority": priority(ln, tags), "text": ln, "tags": tags})
    tagged = [e for e in entries if e["tags"]]
    p1 = sum(e["priority"] == "P1" for e in entries)
    p2 = sum(e["priority"] == "P2" for e in entries)
    result = {"from_version": base, "to_version": versions[0]["version"] if versions else base,
              "versions": len(versions), "entries": len(entries), "tagged_entries": len(tagged),
              "p1_read_all": p1, "p2_scan": p2,
              "items": entries}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2))
    print(f"release_notes · {base} -> {result['to_version']} · {len(versions)} versions · "
          f"{len(entries)} entries · P1 {p1} (read all) · P2 {p2} (scan) · rest dropped")
    counts = {}
    for e in tagged:
        for t in e["tags"]:
            counts[t] = counts.get(t, 0) + 1
    print("  tags: " + ", ".join(f"{t} {n}" for t, n in sorted(counts.items(), key=lambda x: -x[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
