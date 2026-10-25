#!/usr/bin/env python3
"""Regression test for checks/manifest_check.py.

    python3 checks/test_manifest_check.py

Runs the validator on every fixture in checks/fixtures/manifest/ and asserts
the exit code and the failing rule. Three cases are built at run time because
they depend on the machine: an engagement root outside git (must pass), a
--sensitive-file override, and $SCRUB_PATTERN. Exit 0 only if every case
behaves as expected.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECK = HERE / "manifest_check.py"
FIX = HERE / "fixtures" / "manifest"

# fixture -> (expected exit code, substrings that must all appear in the output)
CASES = {
    "valid.toml": (0, ["PASS"]),
    "fail-parse.toml": (1, ["FAIL parse"]),
    "fail-version.toml": (1, ["FAIL version project.spec_version"]),
    "fail-required.toml": (1, ["FAIL required project.name: missing",
                               "FAIL required project.status"]),
    "fail-slug.toml": (1, ["FAIL slug project.id"]),
    "fail-no-repo.toml": (1, ["FAIL no-repo project.no_repo_reason"]),
    "fail-engagement-missing.toml": (1, ["FAIL engagement engagement.root", "does not exist"]),
    "fail-engagement-in-git.toml": (1, ["FAIL engagement engagement.root", "inside the git repo"]),
    "fail-triggers.toml": (1, ["no heading with anchor #no-such-step",
                               "missing-file.md does not exist"]),
    "fail-sensitive.toml": (1, ["FAIL sensitive memory.standing_scope", "Short Trading"]),
    "fail-scrub.toml": (1, ["FAIL scrub", "home path"]),
    "fail-lenses.toml": (1, ["FAIL lenses review.lenses", "no-such-lens"]),
    "fail-review-enums.toml": (1, ["FAIL required review.egress", "FAIL required review.surface"]),
}


def run(manifest, *extra, env=None):
    r = subprocess.run([sys.executable, str(CHECK), str(manifest), *extra],
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def expect(name, got_code, out, want_code, needles, results):
    missing = [n for n in needles if n not in out]
    ok = got_code == want_code and not missing
    results.append(ok)
    print(f"{'ok  ' if ok else 'FAIL'} {name}: exit {got_code} (want {want_code})"
          + (f"; missing {missing}" if missing else ""))
    if not ok:
        print("     " + out.strip().replace("\n", "\n     "))


def main():
    results = []
    listed = set(CASES)
    on_disk = {p.name for p in FIX.glob("*.toml")}
    if listed != on_disk:
        print(f"FAIL fixture list out of sync: untested {sorted(on_disk - listed)}, "
              f"missing {sorted(listed - on_disk)}")
        results.append(False)

    for name, (code, needles) in CASES.items():
        got, out = run(FIX / name)
        expect(name, got, out, code, needles, results)

    base = (FIX / "valid.toml").read_text()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "Engagements"
        root.mkdir()
        m = Path(tmp) / "project.toml"
        m.write_text(base.replace('mode = "none"', f'mode = "per-prospect"\nroot = "{root}"')
                         .replace('triggers = ["SKILL.fixture.md#verify-each-source"]', "triggers = []"))
        got, out = run(m)
        expect("runtime: engagement root outside git", got, out, 0, ["PASS"], results)

        sens = Path(tmp) / "sensitive.txt"
        sens.write_text("# test list\nAI Orchestration\n")
        got, out = run(FIX / "valid.toml", "--sensitive-file", str(sens))
        expect("runtime: --sensitive-file override", got, out, 1,
               ["FAIL sensitive", "'AI Orchestration'"], results)

    env = dict(os.environ, SCRUB_PATTERN="example-owner")
    got, out = run(FIX / "valid.toml", env=env)
    expect("runtime: $SCRUB_PATTERN", got, out, 1, ["matches $SCRUB_PATTERN"], results)

    got, out = run(FIX / "no-such-file.toml")
    expect("usage: missing file", got, out, 2, ["usage error"], results)

    passed = sum(results)
    print(f"\n{passed}/{len(results)} cases passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
