#!/usr/bin/env python3
"""Regression test for skills/project-start/scripts/write_manifest.py.

    python3 checks/test_project_start.py

Every case runs in a throwaway temporary folder (some with a scratch git repo), so no real
project is touched. The last case feeds a written manifest through the SessionStart hook, so the
writer, the validator and the hook are proven together. Exit 0 only if every case behaves.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRITER = ROOT / "skills" / "project-start" / "scripts" / "write_manifest.py"
HOOK = ROOT / "hooks" / "project-manifest-bootstrap.sh"
results = []


def write(folder, *args):
    r = subprocess.run([sys.executable, str(WRITER), "--dir", str(folder), *args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def git_repo(folder, remote=True):
    subprocess.run(["git", "init", "-q", str(folder)], check=True)
    if remote:
        subprocess.run(["git", "-C", str(folder), "remote", "add", "origin",
                        "git@github.com:example-owner/example-repo.git"], check=True)


def case(name, ok, detail=""):
    results.append(ok)
    print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f"\n     {detail}" if not ok and detail else ""))


def leftovers(folder):
    return sorted(p.name for p in folder.glob("project.toml*"))


def main():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        def fresh(name):
            d = tmp / name
            d.mkdir()
            return d

        d = fresh("folder-ok")
        code, out = write(d, "--id", "notes-project", "--name", "Notes",
                          "--no-repo-reason", "Scratch notes, nothing to version.",
                          "--scope", "AI Orchestration", "--output", "notes/")
        text = (d / "project.toml").read_text() if (d / "project.toml").exists() else ""
        case("folder project with a reason: written, kind=folder, repo=none",
             code == 0 and 'kind = "folder"' in text and 'repo = "none"' in text
             and leftovers(d) == ["project.toml"], out)

        d = fresh("folder-no-reason")
        code, out = write(d, "--id", "notes-project", "--name", "Notes")
        case("folder project without a reason: refused, nothing written",
             code == 1 and "no-repo-reason" in out and leftovers(d) == [], out)

        d = fresh("repo")
        git_repo(d)
        code, out = write(d, "--id", "example-repo", "--name", "Example repo",
                          "--review-design", "required", "--check", "python3 -m pytest")
        text = (d / "project.toml").read_text() if (d / "project.toml").exists() else ""
        case("git repo: kind=repo and owner/name read from origin",
             code == 0 and 'kind = "repo"' in text and 'repo = "example-owner/example-repo"' in text, out)

        d = fresh("repo-no-remote")
        git_repo(d, remote=False)
        code, out = write(d, "--id", "x", "--name", "X")
        case("git repo with no origin: refused", code == 1 and "no origin remote" in out
             and leftovers(d) == [], out)

        d = fresh("sensitive")
        code, out = write(d, "--id", "x", "--name", "X", "--no-repo-reason", "test",
                          "--scope", "AI Orchestration", "--scope", "Business")
        case("Sensitive bucket in scope: refused, nothing written",
             code == 1 and "Business" in out and leftovers(d) == [], out)

        d = fresh("exists")
        (d / "project.toml").write_text("# owner's existing manifest\n")
        code, out = write(d, "--id", "x", "--name", "X", "--no-repo-reason", "test")
        kept = (d / "project.toml").read_text() == "# owner's existing manifest\n"
        case("existing manifest: refused and left untouched", code == 1 and "already exists" in out
             and kept, out)
        code, out = write(d, "--id", "x", "--name", "X", "--no-repo-reason", "test", "--force")
        case("existing manifest with --force: replaced", code == 0
             and 'id = "x"' in (d / "project.toml").read_text(), out)

        eroot = tmp / "Engagements"
        (eroot / "_TEMPLATE").mkdir(parents=True)
        (eroot / "_TEMPLATE" / "ENGAGEMENT.md").write_text("# template\n")
        d = fresh("engagement-ok")
        code, out = write(d, "--id", "client-work", "--name", "Client work", "--no-repo-reason",
                          "test", "--engagement", "per-prospect", "--engagement-root", str(eroot))
        case("per-prospect with an engagement folder outside git: written",
             code == 0 and 'mode = "per-prospect"' in out, out)

        d = fresh("engagement-missing")
        code, out = write(d, "--id", "client-work", "--name", "Client work", "--no-repo-reason",
                          "test", "--engagement", "per-prospect",
                          "--engagement-root", str(tmp / "nowhere"))
        case("per-prospect without a template: refused", code == 1 and "_TEMPLATE" in out
             and leftovers(d) == [], out)

        d = fresh("bad-trigger")
        code, out = write(d, "--id", "x", "--name", "X", "--no-repo-reason", "test",
                          "--trigger", "skills/x/SKILL.md#step")
        case("trigger that does not resolve: validator rejects, no file and no .new left",
             code == 1 and "FAIL triggers" in out and leftovers(d) == [], out)

        d = fresh("bad-id")
        code, out = write(d, "--id", "Bad_ID", "--name", "X", "--no-repo-reason", "test")
        case("bad id: validator rejects, nothing written", code == 1 and "FAIL slug" in out
             and leftovers(d) == [], out)

        d = fresh("dry-run")
        code, out = write(d, "--id", "dry", "--name", "Dry", "--no-repo-reason", "test", "--dry-run")
        case("--dry-run: prints the file, writes nothing", code == 0 and "DRY RUN" in out
             and 'id = "dry"' in out and leftovers(d) == [], out)

        d = fresh("end-to-end")
        (d / "sub").mkdir()
        write(d, "--id", "end-to-end", "--name", "End to end", "--no-repo-reason", "test",
              "--scope", "AI Orchestration", "--prefer", "project-start", "--review-design",
              "required", "--done", "It works", "--output", "out/")
        r = subprocess.run(["/bin/bash", str(HOOK)], input=json.dumps({"cwd": str(d / "sub")}),
                           capture_output=True, text=True)
        want = ["[project manifest · end-to-end · spec v1]", 'scope=["AI Orchestration"]',
                "Skills: prefer project-start.", "Review: design=required", "Done when: It works.",
                "Output only to: out/."]
        missing = [w for w in want if w not in r.stdout]
        case("end to end: written manifest drives the hook", r.returncode == 0 and not missing,
             f"missing {missing}; got:\n{r.stdout}")

    passed = sum(results)
    print(f"\n{passed}/{len(results)} cases passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
