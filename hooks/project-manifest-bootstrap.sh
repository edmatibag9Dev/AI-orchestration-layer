#!/bin/bash
# project-manifest-bootstrap.sh — SessionStart hook, SPEC-project-manifest.md §5.1
# v1.1 · built 2026-10-25, --json added 2026-10-25 · canonical copy: AI-orchestration-layer/hooks/ · installed: ~/.claude/hooks/
#
# Finds the project's project.toml (walk up from the session's cwd, stopping below $HOME) and prints
# one instruction block: memory scope, skills, engagement record, Ringer steps, review gates, done
# criteria, allowed output. Same posture as coldboot-bootstrap.sh: echo-only, no credentials, never
# touches a store, never runs [done] checks or Ringer. Fail-open by construction: a missing,
# malformed, retired or newer-version manifest prints at most one line, and the script always exits 0.
# Runs after coldboot-bootstrap.sh, which makes the default-scope cold-boot call first.
#
# `--json` (v1.1, for memory-first-gate.sh §5.4): same lookup and checks, but prints the resolved
# manifest as one JSON object — {} when there is none or it is retired, {"error": ...} when invalid.

PAYLOAD=""
MODE="${1:-}"
if [ ! -t 0 ]; then PAYLOAD="$(cat 2>/dev/null)"; fi

read -r -d '' PY <<'PYEOF'
import json, os, sys
from pathlib import Path

KNOWN = {1}
SENSITIVE = {"trading", "short trading", "business"}  # classification spec, Sensitive rank
REQUIRED = {"spec_version": int, "id": str, "name": str, "kind": str, "repo": str, "status": str}

JSON = len(sys.argv) > 2 and sys.argv[2] == "--json"

def say(line):
    print(json.dumps({"error": line}) if JSON else line)
    sys.exit(0)

def nothing():
    if JSON:
        print("{}")
    sys.exit(0)

try:
    cwd = json.loads(sys.argv[1]).get("cwd") if sys.argv[1].strip() else None
except Exception:
    cwd = None
here = Path(cwd or os.getcwd()).resolve()
home = Path.home().resolve()

manifest = None
for d in [here, *here.parents]:
    if d == home or d == d.parent:
        break
    if (d / "project.toml").is_file():
        manifest = d / "project.toml"
        break
if manifest is None:
    nothing()

try:
    import tomllib
except ImportError:
    say("project.toml invalid: python3 has no tomllib (needs 3.11+); proceeding without it")
try:
    doc = tomllib.loads(manifest.read_text(errors="replace"))
except Exception as e:
    say(f"project.toml invalid: {str(e).splitlines()[0]}; proceeding without it")

p = doc.get("project") if isinstance(doc.get("project"), dict) else {}
for key, typ in REQUIRED.items():
    if not isinstance(p.get(key), typ) or isinstance(p.get(key), bool):
        say(f"project.toml invalid: [project] {key} missing or not {typ.__name__}; proceeding without it")
if p["spec_version"] not in KNOWN:
    say(f"project.toml invalid: spec_version {p['spec_version']} is newer than this hook knows; proceeding without it")
if p["status"] == "retired":
    nothing()

def strs(sec, key):
    v = doc.get(sec, {}).get(key) if isinstance(doc.get(sec), dict) else None
    return [x for x in v if isinstance(x, str) and x.strip()] if isinstance(v, list) else []

def val(sec, key):
    v = doc.get(sec, {}).get(key) if isinstance(doc.get(sec), dict) else None
    return v if isinstance(v, str) and v.strip() else None

j = lambda xs: ", ".join(xs)
lines = [f"[project manifest · {p['id']} · spec v{p['spec_version']}]"]

scope = strs("memory", "standing_scope")
dropped = [b for b in scope if b.lower() in SENSITIVE]
scope = [b for b in scope if b.lower() not in SENSITIVE]
recall = strs("memory", "recall")
if JSON:
    import hashlib
    raw = doc.get("memory") if isinstance(doc.get("memory"), dict) else {}
    print(json.dumps({"path": str(manifest), "root": str(manifest.parent), "id": p["id"],
                      "status": p["status"], "standing_scope": scope, "dropped": dropped,
                      "recall": recall, "memory_sha256": hashlib.sha256(
                          json.dumps(raw, sort_keys=True).encode()).hexdigest()}))
    sys.exit(0)
if scope or recall:
    parts = []
    if scope:
        parts.append(f"after the default cold boot, call cold_boot_index with "
                     f"scope={json.dumps(scope)} (standing tier, announce once)")
    if recall:
        parts.append("search_thoughts: " + "; ".join(recall))
    lines.append("Memory: " + "; then ".join(parts) + ".")
if dropped:
    lines.append(f"Memory: dropped Sensitive bucket(s) {j(dropped)}; they need a live confirm, never a standing scope.")

prefer, avoid = strs("skills", "prefer"), strs("skills", "avoid")
if prefer or avoid:
    s = []
    if prefer: s.append(f"prefer {j(prefer)}")
    if avoid: s.append(f"do not use {j(avoid)}")
    lines.append("Skills: " + "; ".join(s) + ".")

if val("engagement", "mode") == "per-prospect" and val("engagement", "root"):
    root = val("engagement", "root").rstrip("/")
    lines.append(f"Engagement: read {root}/<prospect-slug>/ENGAGEMENT.md first (from _TEMPLATE "
                 f"if missing); update it before ending; pointers only.")

triggers = strs("ringer", "triggers")
if triggers:
    lines.append(f"Ringer steps declared in: {j(triggers)}.")

design, change, lenses = val("review", "design"), val("review", "change"), strs("review", "lenses")
if design or change or lenses:
    r = [f"design={design or 'optional'}", f"change={change or 'optional'}"]
    if lenses: r.append(f"lenses={j(lenses)}")
    lines.append("Review: " + ", ".join(r) + ".")

criteria, checks = strs("done", "criteria"), strs("done", "checks")
if criteria or checks:
    d = []
    if criteria: d.append("Done when: " + "; ".join(criteria) + ".")
    if checks: d.append("Prove with: " + ", ".join(f"`{c}`" for c in checks))
    lines.append(" ".join(d))

allowed = strs("outputs", "allowed")
if allowed:
    lines.append(f"Output only to: {j(allowed)}.")

print("\n".join(lines))
PYEOF

python3 -c "$PY" "$PAYLOAD" "$MODE" 2>/dev/null || true
exit 0
