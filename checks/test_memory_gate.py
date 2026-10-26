#!/usr/bin/env python3
"""Regression test for hooks/memory-first-gate.sh (SPEC-project-manifest §5.4).

    python3 checks/test_memory_gate.py

Runs the gate the way Claude Code does (JSON payload on stdin, the attended-session env var) against
throwaway projects and a throwaway state folder. Asserts which calls are held, when the gate passes
or releases, what it writes to the audit log, and that it always exits 0. Exit 0 only if every case
behaves as expected.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "hooks" / "memory-first-gate.sh"
BOOT = ROOT / "hooks" / "project-manifest-bootstrap.sh"
COLD = "mcp__open-brain__cold_boot_index"
results = []

MANIFEST = """[project]
spec_version = 1
id = "demo-project"
name = "Demo"
kind = "repo"
repo = "owner/demo"
status = "{status}"

[memory]
standing_scope = {scope}
recall = ["demo lessons"]
"""


class Env:
    def __init__(self, tmp):
        self.tmp = Path(tmp)
        self.state = self.tmp / "state"
        self.env = {k: v for k, v in os.environ.items() if k != "MEMORY_GATE"}
        self.env.update(CLAUDE_CODE_SESSION_ATTENDED="1", MEMORY_GATE_STATE=str(self.state))

    def project(self, name, scope='["Bucket A"]', status="active", approve=True):
        d = self.tmp / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "project.toml").write_text(MANIFEST.format(scope=scope, status=status))
        if approve:
            self.approve(d)
        return d

    def approve(self, d):
        m = json.loads(subprocess.run(["bash", str(BOOT), "--json"], capture_output=True, text=True,
                                      input=json.dumps({"cwd": str(d)})).stdout)
        self.state.mkdir(parents=True, exist_ok=True)
        f = self.state / "approved.json"
        reg = json.loads(f.read_text()) if f.exists() else {}
        reg[m["path"]] = {"id": m["id"], "standing_scope": m["standing_scope"],
                          "memory_sha256": m["memory_sha256"], "approved_at": "2026-10-25"}
        f.write_text(json.dumps(reg))

    def run(self, mode, payload, env=None, raw=None, path=None):
        e = dict(self.env, **(env or {}))
        if path is not None:
            e["PATH"] = path
        r = subprocess.run(["/bin/bash", str(GATE), mode], capture_output=True, text=True, env=e,
                           input=raw if raw is not None else json.dumps(payload))
        try:
            out = json.loads(r.stdout) if r.stdout.strip() else None
        except Exception:
            out = {"unparsed": r.stdout}
        return r.returncode, out

    def audit(self):
        f = self.state / "audit.jsonl"
        return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []


def held(out):
    return bool(out) and out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


def call(sid, cwd, tool="Read", prompt="p1", **kw):
    p = {"session_id": sid, "cwd": str(cwd), "hook_event_name": "PreToolUse", "tool_name": tool,
         "tool_input": kw.pop("tool_input", {}), "prompt_id": prompt}
    p.update(kw)
    return p


def cold(sid, cwd, scope=None, prompt="p1", event="PostToolUse", server="open-brain", tool=COLD):
    ti = {} if scope is None else {"scope": scope}
    return {"session_id": sid, "cwd": str(cwd), "hook_event_name": event, "tool_name": tool,
            "tool_input": ti, "prompt_id": prompt, "mcp_server": {"name": server, "source": "sdk"}}


def transcript(e, first, as_list=False):
    """A transcript file like Claude Code writes: a hook line, then the first user prompt."""
    f = e.tmp / f"t-{uuid.uuid4().hex}.jsonl"
    content = [{"type": "text", "text": first}] if as_list else first
    f.write_text(json.dumps({"type": "system", "subtype": "hook", "content": "SessionStart"}) + "\n"
                 + json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n")
    return str(f)


def case(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not ok else ""))


def load(e, sid, cwd):
    """Default + exact standing scope, through the post hook. Returns the announce output."""
    e.run("post", cold(sid, cwd))
    return e.run("post", cold(sid, cwd, ["Bucket A"]))[1]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        e = Env(tmp)
        proj = e.project("proj")
        sid = lambda: uuid.uuid4().hex

        # 1 no manifest → allowed
        bare = e.tmp / "bare"; bare.mkdir()
        code, out = e.run("pre", call(sid(), bare))
        case("no manifest: call allowed", code == 0 and out is None, str(out))

        # 2 unattended / 3 kill switch / 4 garbage / 5 missing python3
        code, out = e.run("pre", call(sid(), proj), env={"CLAUDE_CODE_SESSION_ATTENDED": "0"})
        case("unattended session: gate off", code == 0 and out is None, str(out))
        code, out = e.run("pre", call(sid(), proj), env={"MEMORY_GATE": "off"})
        case("kill switch MEMORY_GATE=off", code == 0 and out is None, str(out))
        code, out = e.run("pre", None, raw="not json{")
        case("garbage payload: allowed, exit 0", code == 0 and out is None, str(out))
        code, out = e.run("pre", call(sid(), proj), path="/nonexistent")
        case("missing python3: allowed, exit 0", code == 0 and out is None, str(out))

        # 6 unapproved manifest → off, audited once
        unap = e.project("unapproved", approve=False)
        s = sid()
        o1, o2 = e.run("pre", call(s, unap))[1], e.run("pre", call(s, unap, prompt="p2"))[1]
        rows = [r for r in e.audit() if r["session_id"] == s]
        case("unapproved manifest: off, audited once",
             o1 is None and o2 is None and [r["outcome"] for r in rows] == ["unapproved"], str(rows))

        # 7 changed [memory] after approval → off
        chg = e.project("changed")
        (chg / "project.toml").write_text(MANIFEST.format(scope='["Bucket A", "Bucket B"]', status="active"))
        case("[memory] changed after approval: off", e.run("pre", call(sid(), chg))[1] is None)

        # 8 retired / Sensitive-only scope → off
        ret = e.project("retired")             # approved while active, then retired
        (ret / "project.toml").write_text(MANIFEST.format(scope='["Bucket A"]', status="retired"))
        case("approved then retired manifest: off", e.run("pre", call(sid(), ret))[1] is None)
        sens = e.project("sensitive", scope='["Trading"]')
        case("Sensitive-only scope: off", e.run("pre", call(sid(), sens))[1] is None)

        # 9 approved: first ordinary call held, with the load steps
        s = sid()
        code, out = e.run("pre", call(s, proj))
        reason = (out or {}).get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        case("approved: first call held with load steps",
             code == 0 and held(out) and f"select:{COLD}" in reason and '["Bucket A"]' in reason
             and "demo lessons" in reason, reason)

        # 10 always-allowed tools
        ok = all(e.run("pre", call(s, proj, tool=t))[1] is None
                 for t in ("ToolSearch", COLD, "mcp__open-brain__search_thoughts", "mcp__ccd_turn__update_plan"))
        case("ToolSearch, memory tools, plan tools allowed while held", ok)

        # 11 sibling memory server neither counts nor is allowed
        o = e.run("pre", call(s, proj, tool="mcp__open-brain-triage__cold_boot_index"))[1]
        e.run("post", cold(s, proj, tool="mcp__open-brain-triage__cold_boot_index", server="open-brain-triage"))
        e.run("post", cold(s, proj, ["Bucket A"], tool="mcp__open-brain-triage__cold_boot_index", server="open-brain-triage"))
        case("sibling server: held and not counted", held(o) and held(e.run("pre", call(s, proj))[1]))

        # 12 default only → still held
        e.run("post", cold(s, proj))
        case("default cold boot only: still held", held(e.run("pre", call(s, proj))[1]))

        # 13 superset scope → not counted
        e.run("post", cold(s, proj, ["Bucket A", "Trading"]))
        case("superset scope: not counted", held(e.run("pre", call(s, proj))[1]))

        # 14 exact scope → pass, announce from the manifest, audited
        out = e.run("post", cold(s, proj, ["Bucket A"]))[1]
        ctx = (out or {}).get("hookSpecificOutput", {}).get("additionalContext", "")
        after = e.run("pre", call(s, proj, prompt="p9"))[1]
        rows = [r["outcome"] for r in e.audit() if r["session_id"] == s]
        case("default + exact scope: pass, announce, audit",
             'Memory scope: Bucket A (standing, from project.toml)' in ctx and after is None
             and rows == ["passed"], f"{ctx!r} {after} {rows}")

        # 15 scoped first, then default (parallel order) → pass
        s = sid()
        e.run("post", cold(s, proj, ["Bucket A"]))
        e.run("post", cold(s, proj))
        case("scoped then default (any order): pass", e.run("pre", call(s, proj))[1] is None)

        # 16 scope [] counts as default
        s = sid()
        e.run("post", cold(s, proj, []))
        e.run("post", cold(s, proj, ["Bucket A"]))
        case("scope [] counts as the default call", e.run("pre", call(s, proj))[1] is None)

        # 17 PostToolUseFailure counts as an attempt
        s = sid()
        e.run("post", cold(s, proj, event="PostToolUseFailure"))
        out = e.run("post", cold(s, proj, ["Bucket A"], event="PostToolUseFailure"))[1]
        case("errored calls count (PostToolUseFailure)",
             e.run("pre", call(s, proj))[1] is None
             and (out or {}).get("hookSpecificOutput", {}).get("hookEventName") == "PostToolUseFailure")

        # 18 parallel burst in one prompt does not exhaust; 3rd prompt releases
        s = sid()
        burst = [held(e.run("pre", call(s, proj))[1]) for _ in range(5)]
        p2 = held(e.run("pre", call(s, proj, prompt="p2"))[1])
        p3 = e.run("pre", call(s, proj, prompt="p3"))[1]
        rows = [r for r in e.audit() if r["session_id"] == s]
        case("5 parallel calls held; prompt 2 held; prompt 3 released + audited",
             all(burst) and p2 and p3 is None and rows and rows[-1]["outcome"] == "exhausted"
             and rows[-1]["reason"] == "held-prompts", f"{burst} {p2} {p3} {rows}")

        # 19 in-prompt valve: 5th separate burst releases
        s = sid()
        st_file = e.state / f"{s}.json"
        outs = []
        for i in range(5):
            outs.append(held(e.run("pre", call(s, proj))[1]))
            st = json.loads(st_file.read_text())
            for h in st["holds"].values():
                h["last"] -= 10                     # simulate > 2 s between retries
            st_file.write_text(json.dumps(st))
        last = [r for r in e.audit() if r["session_id"] == s][-1]
        case("in-prompt valve: 4 bursts held, 5th released",
             outs == [True] * 4 + [False] and last["reason"] == "held-bursts", f"{outs} {last}")

        # 20 memory tool missing (ToolSearch miss) → release
        s = sid()
        e.run("pre", call(s, proj))
        e.run("post", {"session_id": s, "cwd": str(proj), "hook_event_name": "PostToolUse",
                       "tool_name": "ToolSearch", "tool_input": {"query": f"select:{COLD}"},
                       "tool_response": {"matches": [], "query": f"select:{COLD}"}, "prompt_id": "p1"})
        out = e.run("pre", call(s, proj))[1]
        last = [r for r in e.audit() if r["session_id"] == s][-1]
        case("ToolSearch shows memory tool missing: released + audited",
             out is None and last["reason"] == "memory-tool-missing", f"{out} {last}")

        # 21 ToolSearch miss on an unrelated or decoy query does not release
        s = sid()
        for q in ("select:mcp__open-brain__cold_boot_indexX", "cold_boot_index decoy"):
            e.run("post", {"session_id": s, "cwd": str(proj), "hook_event_name": "PostToolUse",
                           "tool_name": "ToolSearch", "tool_input": {"query": q},
                           "tool_response": {"matches": []}, "prompt_id": "p1"})
        case("decoy ToolSearch misses do not release", held(e.run("pre", call(s, proj))[1]))

        # 22 subagent calls allowed and their memory calls not counted for the parent
        s = sid()
        sub = e.run("pre", call(s, proj, agent_id="abc", agent_type="general-purpose"))[1]
        e.run("post", dict(cold(s, proj), agent_id="abc"))
        e.run("post", dict(cold(s, proj, ["Bucket A"]), agent_id="abc"))
        case("subagent: allowed, does not pass parent", sub is None and held(e.run("pre", call(s, proj))[1]))

        # 23 starting in a parent folder, then moving into the project → gated there
        s = sid()
        outside = e.run("pre", call(s, e.tmp))[1]
        (proj / "sub").mkdir()
        inside = e.run("pre", call(s, proj / "sub"))[1]
        case("cwd moves into an approved project: gate engages", outside is None and held(inside))

        # 23b scheduled runs are never held (SPEC-activation §2.4); audited once per project
        sched = '<scheduled-task name="evening-digest" file="/x/SKILL.md">\nThis is an automated run.'
        for label, tp in (("string content", transcript(e, sched)), ("list content", transcript(e, sched, True))):
            s = sid()
            outs = [e.run("pre", call(s, proj, transcript_path=tp))[1],
                    e.run("pre", call(s, proj, transcript_path=tp, prompt="p2"))[1]]
            rows = [r["outcome"] for r in e.audit() if r["session_id"] == s]
            case(f"scheduled run ({label}): never held, audited once as skipped-scheduled",
                 outs == [None, None] and rows == ["skipped-scheduled"], f"{outs} {rows}")
        s = sid()
        tp = transcript(e, sched)
        outside = e.run("pre", call(s, e.tmp, transcript_path=tp))[1]
        inside = e.run("pre", call(s, proj, transcript_path=tp))[1]
        case("scheduled run moving into an approved project: not held", outside is None and inside is None)
        s = sid()
        e.run("post", cold(s, proj) | {"transcript_path": transcript(e, sched)})
        out = e.run("post", cold(s, proj, ["Bucket A"]) | {"transcript_path": transcript(e, sched)})[1]
        case("scheduled run: no standing-scope announcement", out is None, str(out))
        for label, tp in (("ordinary first prompt", transcript(e, "Fix the bug in the gate.")),
                          ("marker later in the prompt", transcript(e, "Explain <scheduled-task name=x> to me")),
                          ("unreadable transcript", str(e.tmp / "missing.jsonl"))):
            case(f"{label}: still held", held(e.run("pre", call(sid(), proj, transcript_path=tp))[1]))

        # 24 approve refuses without a terminal
        r = subprocess.run(["/bin/bash", str(GATE), "approve", str(proj)], capture_output=True,
                           text=True, env=e.env, input="yes\n")
        case("approve refuses without an interactive terminal",
             r.returncode == 1 and "interactive terminal" in r.stderr, r.stderr)

        # 25 speed: passed-session call and held call each under 150 ms on average
        s = sid(); load(e, s, proj)
        t = time.time()
        for _ in range(10):
            e.run("pre", call(s, proj))
        fast = (time.time() - t) / 10
        case(f"passed session call averages under 150 ms ({fast * 1000:.0f} ms)", fast < 0.15)

    passed = sum(results)
    print(f"\n{passed}/{len(results)} cases passed")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
