#!/bin/bash
# memory-first-gate.sh — PreToolUse / PostToolUse hook, SPEC-project-manifest.md §5.4
# v1.0 · built 2026-10-25 · canonical copy: AI-orchestration-layer/hooks/ · installed: ~/.claude/hooks/
#
# In an attended session whose project.toml the owner approved, holds ordinary tool calls until the
# session has called the memory server's cold_boot_index with default scope and with exactly the
# standing scope. Then silent for the rest of the session. Enforces the attempt, never the result:
# an errored call counts, and a missing memory server releases the gate (SPEC-activation C11).
# Fail-open by construction: bad payload, missing python3, crash or timeout → the call is allowed.
#
#   memory-first-gate.sh pre        PreToolUse, matcher "*"
#   memory-first-gate.sh post       PostToolUse + PostToolUseFailure, matcher "<cold_boot_index>|ToolSearch"
#   memory-first-gate.sh approve D  owner only, interactive terminal: approve D/project.toml's [memory]
#                                   and [review] (review_gate.py §5.5 enforces the approved [review])
#   memory-first-gate.sh list       show approved manifests
#
# Kill switch: MEMORY_GATE=off in the environment. State: ~/.claude/state/memory-gate/ (local only).

MODE="${1:-pre}"
[ "$MEMORY_GATE" = "off" ] && exit 0
command -v python3 >/dev/null 2>&1 || exit 0
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOT="$HERE/project-manifest-bootstrap.sh"

if [ "$MODE" = "approve" ] || [ "$MODE" = "list" ]; then
  if [ "$MODE" = "approve" ] && { [ ! -t 0 ] || [ ! -t 1 ]; }; then
    echo "approve needs an interactive terminal: the owner runs it, never an agent." >&2
    exit 1
  fi
  read -r -d '' APY <<'PYEOF'
import datetime, json, os, subprocess, sys
from pathlib import Path
mode, boot, target = sys.argv[1], sys.argv[2], sys.argv[3]
state = Path(os.environ.get("MEMORY_GATE_STATE") or Path.home() / ".claude/state/memory-gate")
reg_file = state / "approved.json"
try:
    reg = json.loads(reg_file.read_text())
except Exception:
    reg = {}
if mode == "list":
    for path, e in sorted(reg.items()):
        rv = e.get("review") or {}
        print(f"{e.get('id')}  scope={e.get('standing_scope')}  review={rv.get('lenses', 'not approved')}"
              f"  approved {e.get('approved_at')}  {path}")
    sys.exit(0)
d = Path(target or ".").expanduser().resolve()
d = d.parent if d.name == "project.toml" else d
r = subprocess.run(["bash", boot, "--json"], input=json.dumps({"cwd": str(d)}),
                   capture_output=True, text=True)
m = json.loads(r.stdout or "{}")
if m.get("error") or not m.get("path"):
    sys.exit(f"no usable project.toml at or above {d}: {m.get('error', 'none found')}")
if Path(m["path"]).parent != d:
    sys.exit(f"nearest project.toml is {m['path']}, not in {d}; run approve in that folder")
if not m["standing_scope"] and not m.get("review", {}).get("lenses"):
    sys.exit("this manifest has no standing_scope and no review lenses; nothing to approve")
rv = m.get("review", {})
print(f"Project:  {m['id']}\nManifest: {m['path']}\nStanding scope: {m['standing_scope']}"
      f"\nRecall:   {m['recall']}\nReview:   design={rv.get('design')} change={rv.get('change')} "
      f"lenses={rv.get('lenses')} egress={rv.get('egress')} surface={rv.get('surface')}")
try:
    answer = input("Approve these [memory] and [review] sections? Type yes: ")
except EOFError:
    answer = ""
if answer.strip() != "yes":
    sys.exit("not approved")
reg[m["path"]] = {"id": m["id"], "standing_scope": m["standing_scope"],
                  "memory_sha256": m["memory_sha256"],
                  "review": m.get("review"), "review_sha256": m.get("review_sha256"),
                  "approved_at": datetime.date.today().isoformat()}
state.mkdir(parents=True, exist_ok=True)
tmp = reg_file.with_suffix(".tmp")
tmp.write_text(json.dumps(reg, indent=1, sort_keys=True))
tmp.replace(reg_file)
print("approved")
PYEOF
  exec python3 -c "$APY" "$MODE" "$BOOT" "${2:-}"    # stdin stays the terminal for the prompt
fi

# Hook modes. Only attended (interactive) sessions are gated: scheduled and headless runs are
# Safe-only and ignore standing scopes (SPEC-activation §2.4).
[ "$CLAUDE_CODE_SESSION_ATTENDED" = "1" ] || exit 0

read -r -d '' PY <<'PYEOF'
import fcntl, json, os, re, subprocess, sys, time
from pathlib import Path

MODE, BOOT = sys.argv[1], sys.argv[2]
STATE = Path(os.environ.get("MEMORY_GATE_STATE") or Path.home() / ".claude/state/memory-gate")
SERVER = "open-brain"
MEM = f"mcp__{SERVER}__"                 # trailing __ keeps sibling servers out
COLD = MEM + "cold_boot_index"
ALWAYS = {"ToolSearch"}
ALWAYS_PREFIX = (MEM, "mcp__ccd_turn__")  # memory tools; the app's plan / wrap-up tools
HELD_PROMPTS_MAX = 2                      # D2: release on the 3rd held user prompt
BURSTS_MAX = 4                            # in-prompt valve: 5th separate held burst releases
BURST_GAP_S = 2.0                         # parallel calls arrive within ms → one burst
PRUNE_DAYS = 30

def done(obj=None):
    if obj is not None:
        print(json.dumps(obj))
    sys.exit(0)

d = json.loads(sys.stdin.read() or "{}")
sid = d.get("session_id")
if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", sid):
    done()
if d.get("agent_id"):                     # subagent: the parent already passed before calling Agent
    done()
tool = d.get("tool_name") or ""
server = (d.get("mcp_server") or {}).get("name") if isinstance(d.get("mcp_server"), dict) else None
is_cold = tool == COLD and server in (None, SERVER)

STATE.mkdir(parents=True, exist_ok=True)
lock = open(STATE / f"{sid}.lock", "w")
fcntl.flock(lock, fcntl.LOCK_EX)
sf = STATE / f"{sid}.json"
try:
    st = json.loads(sf.read_text())
except Exception:
    st = {"cwd": None, "m": None, "active": False, "default_done": False, "scoped_seen": [],
          "passed": [], "holds": {}, "tool_absent": False, "noted": []}
    cutoff = time.time() - PRUNE_DAYS * 86400
    for f in STATE.glob("*"):
        if f.suffix in (".json", ".lock") and f.name != "approved.json" and f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)

def save():
    tmp = sf.with_suffix(".tmp")
    tmp.write_text(json.dumps(st))
    tmp.replace(sf)

def audit(outcome, **kw):
    m = st.get("m") or {}
    row = {"ts": int(time.time()), "session_id": sid, "project": m.get("id"), "outcome": outcome,
           "held_prompts": len(st["holds"].get(m.get("path"), {}).get("prompts", []))}
    if st.get("t0"):
        row["seconds_to_outcome"] = round(time.time() - st["t0"], 1)
    row.update(kw)
    with open(STATE / "audit.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")

def approved(m):
    try:
        e = json.loads((STATE / "approved.json").read_text()).get(m["path"])
    except Exception:
        return False
    return isinstance(e, dict) and e.get("memory_sha256") == m.get("memory_sha256")

cwd = d.get("cwd") or os.getcwd()
if st["cwd"] != cwd:                      # re-resolve whenever the working folder changes
    st["cwd"] = cwd
    try:
        r = subprocess.run(["bash", BOOT, "--json"], input=json.dumps({"cwd": cwd}),
                           capture_output=True, text=True, timeout=3)
        m = json.loads(r.stdout or "{}")
    except Exception:
        m = {}
    m = m if m.get("path") and m.get("standing_scope") else None
    st["m"] = m
    st["active"] = bool(m and approved(m))
    if m and not st["active"] and m["path"] not in st["noted"]:
        st["noted"].append(m["path"])
        audit("unapproved")

m = st["m"]

if MODE == "post":
    if tool == "ToolSearch":
        q = str((d.get("tool_input") or {}).get("query", "")).strip()
        asked = [n.strip() for n in q[7:].split(",")] if q.startswith("select:") else []
        resp = d.get("tool_response")
        if COLD in asked and isinstance(resp, dict) and COLD not in (resp.get("matches") or []):
            st["tool_absent"] = True
        save(); done()
    if not is_cold:
        save(); done()
    scope = (d.get("tool_input") or {}).get("scope")
    if not scope:                          # None or [] → default scope (SPEC-activation §2.3)
        st["default_done"] = True
    elif m and isinstance(scope, list) and set(scope) == set(m["standing_scope"]):
        if m["path"] not in st["scoped_seen"]:
            st["scoped_seen"].append(m["path"])
    if (st["active"] and st["default_done"] and m["path"] in st["scoped_seen"]
            and m["path"] not in st["passed"]):
        st["passed"].append(m["path"])
        audit("passed")
        save()
        done({"hookSpecificOutput": {
            "hookEventName": d.get("hook_event_name") or "PostToolUse",
            "additionalContext": f'Announce once, in your next reply: "Memory scope: '
                                 f'{", ".join(m["standing_scope"])} (standing, from project.toml)."'}})
    save(); done()

# pre
if not st["active"] or m["path"] in st["passed"] or tool in ALWAYS or tool.startswith(ALWAYS_PREFIX):
    save(); done()

def release(outcome, reason):
    st["passed"].append(m["path"])
    audit(outcome, reason=reason)
    save(); done()

if st["tool_absent"]:
    release("exhausted", "memory-tool-missing")
h = st["holds"].setdefault(m["path"], {"prompts": [], "bursts": {}, "last": 0})
pid = str(d.get("prompt_id") or "?")
if pid not in h["prompts"]:
    h["prompts"].append(pid)
now = time.time()
if now - h["last"] > BURST_GAP_S:
    h["bursts"][pid] = h["bursts"].get(pid, 0) + 1
h["last"] = now
st.setdefault("t0", now)
if len(h["prompts"]) > HELD_PROMPTS_MAX:
    release("exhausted", "held-prompts")
if h["bursts"].get(pid, 0) > BURSTS_MAX:
    release("exhausted", "held-bursts")
save()
steps = [f'ToolSearch "select:{COLD},{MEM}search_thoughts"',
         "cold_boot_index with no scope",
         f"cold_boot_index with scope={json.dumps(m['standing_scope'])}"]
if m.get("recall"):
    steps.append("search_thoughts: " + "; ".join(m["recall"]))
done({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason":
        f"[memory-first gate · {m['id']}] Held until memory is loaded. Do these, then retry:\n"
        + "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
        + '\nIf the memory tools are missing or error, say "memory index unavailable" once and retry.'}})
PYEOF

python3 -c "$PY" "$MODE" "$BOOT" 2>/dev/null || true
exit 0
