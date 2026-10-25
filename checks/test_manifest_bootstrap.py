#!/usr/bin/env python3
"""Regression test for hooks/project-manifest-bootstrap.sh (SPEC-project-manifest §5.1).

    python3 checks/test_manifest_bootstrap.py

Runs the hook the way Claude Code does (JSON payload on stdin, a working directory) against the
validator fixtures and the spec's two examples, built in temporary folders. Asserts what is
printed, what is not, the token budget, and that the hook always exits 0. Exit 0 only if every
case behaves as expected.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "project-manifest-bootstrap.sh"
FIX = ROOT / "checks" / "fixtures" / "manifest"
SPEC = ROOT / "SPEC-project-manifest.md"
BUDGET_TOKENS = 250
results = []


def run(cwd, payload_cwd=None, env=None, raw_payload=None):
    payload = raw_payload if raw_payload is not None else json.dumps(
        {"hook_event_name": "SessionStart", "cwd": str(payload_cwd or cwd)})
    r = subprocess.run(["/bin/bash", str(HOOK)], input=payload, capture_output=True,
                       text=True, cwd=cwd, env=env)
    return r.returncode, r.stdout


def case(name, code, out, has=(), lacks=(), lines=None, budget=False):
    problems = []
    if code != 0:
        problems.append(f"exit {code}, want 0")
    problems += [f"missing {h!r}" for h in has if h not in out]
    problems += [f"unexpected {l!r}" for l in lacks if l in out]
    n = len(out.strip().splitlines()) if out.strip() else 0
    if lines is not None and n != lines:
        problems.append(f"{n} lines, want {lines}")
    if budget and len(out) / 4 > BUDGET_TOKENS:
        problems.append(f"~{len(out) // 4} tokens, over {BUDGET_TOKENS}")
    results.append(not problems)
    print(f"{'ok  ' if not problems else 'FAIL'} {name}" + (f": {'; '.join(problems)}" if problems else ""))
    if problems:
        print("     " + (out.strip() or "<no output>").replace("\n", "\n     "))


def project(tmp, name, text):
    d = Path(tmp) / name
    d.mkdir()
    (d / "project.toml").write_text(text)
    return d


def main():
    examples = re.findall(r"```toml\n(.*?)```", SPEC.read_text(), re.S)
    with tempfile.TemporaryDirectory() as tmp:
        empty = Path(tmp) / "no-manifest"
        empty.mkdir()
        case("no manifest: prints nothing", *run(empty), lines=0)

        ex1 = project(tmp, "ex1", examples[0])
        deep = ex1 / "sub" / "deeper"
        deep.mkdir(parents=True)
        code, out = run(deep)
        case("spec example 1, from a nested folder", code, out, lines=8, budget=True, has=[
            "[project manifest · meeting-research · spec v1]",
            'scope=["<client-bucket>"]', "search_thoughts: meeting research lessons",
            "Skills: prefer meeting-research; do not use demo-prep, competitive-gap-analysis.",
            "Engagement: read ~/Documents/Claude/Engagements/<prospect-slug>/ENGAGEMENT.md first",
            "Ringer steps declared in: skills/meeting-research/SKILL.md#",
            "Review: design=required, change=optional, lenses=accuracy, coherence.",
            "Done when:", "Prove with: `node skills", "repo-check.py .`", "Output only to: Meetings/."],
            lacks=[".."])
        print(f"     ~{len(out) // 4} tokens for the fullest example")

        ex2 = project(tmp, "ex2", examples[1])
        case("spec example 2 (folder project): only what it declares", *run(ex2), lines=2,
             has=["[project manifest · home-network-monitor", "Output only to: logs/, reports/."],
             lacks=["Memory:", "Engagement:", "Skills:", "Review:", "routines"])

        v = project(tmp, "valid", (FIX / "valid.toml").read_text())
        case("valid fixture: mode none prints no engagement line", *run(v),
             has=["Memory:", "Ringer steps declared in", "Review: design=required"],
             lacks=["Engagement:"])

        for fx, needle in [("fail-parse.toml", "project.toml invalid:"),
                           ("fail-version.toml", "spec_version 2 is newer"),
                           ("fail-required.toml", "[project] name missing")]:
            d = project(tmp, fx[:-5], (FIX / fx).read_text())
            case(f"{fx}: one-line notice only", *run(d), lines=1,
                 has=[needle, "proceeding without it"])

        s = project(tmp, "sensitive", (FIX / "fail-sensitive.toml").read_text())
        case("Sensitive bucket dropped from scope", *run(s),
             has=['scope=["AI Orchestration"]', "dropped Sensitive bucket(s) Short Trading"],
             lacks=['"Short Trading"]'])

        retired = project(tmp, "retired", (FIX / "valid.toml").read_text()
                          .replace('status = "active"', 'status = "retired"'))
        case("retired project: prints nothing", *run(retired), lines=0)

        case("payload cwd wins over process cwd", *run(empty, payload_cwd=deep),
             has=["meeting-research"])
        case("garbage payload falls back to process cwd", *run(ex1, raw_payload="{not json"),
             has=["meeting-research"])

        no_py = dict(os.environ, PATH="/nonexistent")
        case("python3 missing: silent, exit 0", *run(ex1, env=no_py), lines=0)

        sentinel = Path(tmp) / "SENTINEL"
        trap = project(tmp, "trap", (FIX / "valid.toml").read_text()
                       + f'\n[done]\nchecks = ["touch {sentinel}"]\n')
        code, out = run(trap)
        results.append(not sentinel.exists())
        print(f"{'ok  ' if not sentinel.exists() else 'FAIL'} [done] checks are printed, never run")

    passed = sum(results)
    print(f"\n{passed}/{len(results)} cases passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
