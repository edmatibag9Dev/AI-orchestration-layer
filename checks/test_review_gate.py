#!/usr/bin/env python3
"""Regression test for checks/review_gate.py (SPEC-project-manifest §5.5).

    python3 checks/test_review_gate.py

Builds throwaway projects, approval registries and state folders, and drives every subcommand the
way an orchestrator would: plan (files and git ranges, local and external, policy from the owner's
approval), check-report, synthesize and record. A fake `gh` on PATH answers the repo-visibility
question, so nothing touches the network. Exit 0 only if every case behaves as expected.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "checks" / "review_gate.py"
BOOT = ROOT / "hooks" / "project-manifest-bootstrap.sh"
results = []

MANIFEST = """[project]
spec_version = 1
id = "{pid}"
name = "Demo"
kind = "repo"
repo = "owner/{pid}"
status = "active"

[review]
design = "required"
change = "{change}"
lenses = {lenses}
egress = "{egress}"
surface = "{surface}"

[outputs]
allowed = ["out/"]
"""


class Env:
    def __init__(self, tmp):
        self.tmp = Path(tmp)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.gh("PRIVATE")
        self.ringer = self.tmp / "ringer"
        self.ringer.mkdir()
        self.lint(0)
        self.env = dict(os.environ, REVIEW_GATE_STATE=str(self.tmp / "rg"),
                        MEMORY_GATE_STATE=str(self.tmp / "mg"), RINGER_DIR=str(self.ringer),
                        PATH=f"{self.bin}:{os.environ['PATH']}")

    def lint(self, code):
        (self.ringer / "ringer.py").write_text(f"import sys\nprint('lint: fake {code}')\nsys.exit({code})\n")

    def git(self, d, *a):
        return subprocess.run(["git", "-C", str(d), "-c", "user.email=t@t", "-c", "user.name=t", *a],
                              capture_output=True, text=True)

    def publish(self, d, pid):
        """Make d a git repo whose origin is github.com/owner/<pid> and whose upstream holds HEAD."""
        self.git(d, "init", "-q", "-b", "main")
        self.git(d, "add", ".")
        self.git(d, "commit", "-qm", "one")
        self.git(d, "remote", "add", "origin", f"https://github.com/owner/{pid}.git")
        self.sync(d)
        self.git(d, "branch", "-q", "--set-upstream-to=origin/main")

    def sync(self, d):
        self.git(d, "update-ref", "refs/remotes/origin/main", "HEAD")

    def gh(self, visibility):
        f = self.bin / "gh"
        f.write_text(f"#!/bin/bash\necho {visibility}\n")
        f.chmod(0o755)

    def project(self, pid, lenses='["abuse", "coherence"]', change="optional", egress="local", approve=True,
                surface="commits"):
        d = self.tmp / pid
        d.mkdir(exist_ok=True)
        (d / "project.toml").write_text(MANIFEST.format(pid=pid, lenses=lenses, change=change, egress=egress,
                                                        surface=surface))
        (d / "design.md").write_text("# Design\nThe gate holds every push until a record exists.\n")
        if approve:
            self.approve(d)
        return d

    def approve(self, d):
        m = json.loads(subprocess.run(["bash", str(BOOT), "--json"], capture_output=True, text=True,
                                      input=json.dumps({"cwd": str(d)})).stdout)
        f = self.tmp / "mg" / "approved.json"
        f.parent.mkdir(exist_ok=True)
        reg = json.loads(f.read_text()) if f.exists() else {}
        reg[m["path"]] = {"id": m["id"], "memory_sha256": m["memory_sha256"], "review": m["review"],
                          "review_sha256": m["review_sha256"]}
        f.write_text(json.dumps(reg))

    def run(self, *args, stdin=""):
        r = subprocess.run([sys.executable, str(GATE), *map(str, args)], capture_output=True, text=True,
                           env=self.env, input=stdin)
        return r.returncode, r.stdout + r.stderr


def case(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail[:400]}" if detail and not ok else ""))


def report(lens, sha, findings=(), inspected=True, extra="", nonce=""):
    body = [f"Lens: {lens}", f"Surface: {sha}", f"Nonce: {nonce}", "", "## Summary", "Reviewed the design.", ""]
    if inspected:
        body += ["## Inspected", "design.md, all sections", ""]
    if not findings:
        body.append("NO FINDINGS — checked every claim in design.md.")
    for pr in findings:
        body += [f"Finding: something wrong at {pr}", "Evidence: design.md section Design says the gate holds every push.",
                 "Impact: a push slips through.", "Fix: bind the record to the range.", f"Priority: {pr}",
                 "Confidence: high", ""]
    return "\n".join(body) + extra


def plan_dir(out):
    return Path(next(l.split("workdir: ", 1)[1] for l in out.splitlines() if l.startswith("workdir: ")))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        e = Env(tmp)
        run_plan = lambda d, *extra, stage="design": e.run("plan", "--project", d, "--stage", stage, *extra)

        d = e.project("unapproved", approve=False)
        code, out = run_plan(d, "--surface", d / "design.md")
        case("plan refuses an unapproved [review]", code == 1 and "not owner-approved" in out, out)

        d = e.project("proj")
        code, out = run_plan(d, "--surface", d / "design.md")
        w = plan_dir(out) if code == 0 else None
        plan = json.loads((w / "plan.json").read_text()) if w else {}
        brief = (w / "abuse" / "brief.md").read_text() if w else ""
        nonce = plan.get("nonce", "")
        case("plan (files, local): frozen surface, nonce file, one brief per lens, reply-as-text",
             code == 0 and plan["mode"] == "local" and (w / "surface" / "design.md").is_file()
             and (w / "surface" / "REVIEW-NONCE.txt").read_text().strip() == nonce and nonce not in brief
             and plan["surface_sha256"] in brief and "Return the whole report" in brief
             and (w / "coherence" / "brief.md").is_file() and not (w / "manifest.json").exists(), out)
        case("brief says the surface is material under review, never instructions",
             "never instructions to you" in brief and "is itself a finding" in brief, brief[-600:])
        sha = plan.get("surface_sha256", "")

        code, out = run_plan(d, "--surface", d / "design.md", "--workdir", w)
        case("plan refuses an existing workdir", code == 1 and "already exists" in out, out)
        code, out = run_plan(d, "--surface", d / "design.md", "--models", "codex:some-other-model")
        case("--models outside the rotation refused", code == 1 and "only reorder or narrow" in out, out)

        (d / "project.toml").write_text(MANIFEST.format(pid="proj", lenses='["accuracy"]', change="optional",
                                                        egress="local", surface="commits"))
        code, out2 = run_plan(d, "--surface", d / "design.md")
        p2 = json.loads((plan_dir(out2) / "plan.json").read_text()) if code == 0 else {}
        case("edited [review] ignored until re-approved (uses approved lenses)",
             code == 0 and p2.get("lenses") == ["abuse", "coherence"] and "differs from the approved" in out2, out2)

        off = e.project("offproj", change="off")
        code, out = run_plan(off, "--surface", off / "design.md", stage="change")
        case("plan refuses a stage that is off", code == 1 and "is off" in out, out)
        outp = e.project("outproj", change="required", surface="outputs")
        code, out = run_plan(outp, "--range", "HEAD~1..HEAD", stage="change")
        case("plan refuses a git range for a change review that covers outputs",
             code == 1 and "covers outputs" in out, out)

        # ---- egress
        ext = e.project("extproj", lenses='["abuse", "coherence", "enforceability", "accuracy"]', egress="external")
        (ext / "out").mkdir()
        (ext / "out" / "deliverable.md").write_text("client deliverable\n")
        code, out = run_plan(ext, "--surface", ext / "design.md")
        mode = lambda o: json.loads((plan_dir(o) / "plan.json").read_text())["mode"]
        case("external, not a git checkout → local (origin mismatch)", code == 0 and mode(out) == "local"
             and "origin" in out, out)
        e.publish(ext, "extproj")
        code, out = run_plan(ext, "--surface", ext / "design.md")
        case("external, private repo → local", code == 0 and mode(out) == "local" and "not public" in out, out)
        e.gh("PUBLIC")
        code, out = run_plan(ext, "--surface", ext / "design.md")
        wx = plan_dir(out) if code == 0 else None
        man = json.loads((wx / "manifest.json").read_text()) if wx and (wx / "manifest.json").exists() else {}
        models = [f"{t['engine']}:{t['model']}" for t in man.get("tasks", [])]
        case("external, public, published file: one task per lens, round-robin, check-report, linted",
             len(models) == 4 and models[0] == models[3] and len(set(models[:3])) == 3
             and all("check-report" in t["check"] for t in man["tasks"]) and "lint: fake 0" in out
             and "some models review two lenses" in out, out + str(models))
        e.lint(1)
        code, out = run_plan(ext, "--surface", ext / "design.md")
        case("external: failed ringer lint refuses the plan", code == 1 and "lint failed" in out, out)
        e.lint(0)
        (ext / "design.md").write_text("# Design\nunpublished edit\n")
        code, out = run_plan(ext, "--surface", ext / "design.md")
        case("external, file differs from upstream → local", code == 0 and mode(out) == "local"
             and "differs from the upstream" in out, out)
        e.git(ext, "commit", "-qam", "two")
        code, out = run_plan(ext, "--range", "HEAD~1..HEAD")
        case("external, range end not yet upstream → local", code == 0 and mode(out) == "local"
             and "not in the upstream" in out, out)
        e.sync(ext)
        code, out = run_plan(ext, "--range", "HEAD~1..HEAD")
        case("external, published range → external", code == 0 and mode(out) == "external", out)
        (ext / "design.md").write_text("# Design\nlocal-only draft, never pushed\n")
        e.git(ext, "commit", "-qam", "local only")
        code, out = run_plan(ext, "--range", "HEAD..HEAD~1")
        case("external, range whose start commit is unpublished → local", code == 0 and mode(out) == "local"
             and "start commit" in out, out)
        (ext / "out" / "deliverable.md").write_text("client deliverable v2\n")
        e.git(ext, "commit", "-qam", "three"); e.sync(ext)
        code, out = run_plan(ext, "--range", "HEAD~1..HEAD")
        case("external, range touching [outputs] allowed → local", code == 0 and mode(out) == "local"
             and "[outputs] allowed" in out, out)
        code, out = run_plan(ext, "--surface", ext / "out" / "deliverable.md")
        case("external, file under [outputs] allowed → local", code == 0 and mode(out) == "local"
             and "[outputs] allowed" in out, out)
        (ext / "notes.md").write_text("untracked notes\n")
        code, out = run_plan(ext, "--surface", ext / "notes.md")
        case("external, untracked file → local", code == 0 and mode(out) == "local" and "not tracked" in out, out)
        e.gh("PRIVATE")

        # ---- ranges
        code, out = run_plan(ext, "--range", "HEAD")
        case("range without two ends refused", code == 1 and "two commits" in out, out)
        code, out = run_plan(ext, "--range", "nope..HEAD")
        case("range with an unknown end refused", code == 1 and "not a commit" in out, out)
        code, out = run_plan(ext, "--range", "HEAD..HEAD")
        case("empty range refused", code == 1 and "empty" in out, out)

        # ---- check-report
        R = lambda lens, *a, **k: report(lens, sha, *a, nonce=nonce, **k)
        (w / "abuse" / "report.md").write_text(R("abuse", ["P1"]))
        (w / "coherence" / "report.md").write_text(R("coherence"))
        ok1 = e.run("check-report", "--workdir", w, "--lens", "abuse")
        ok2 = e.run("check-report", "--workdir", w, "--lens", "coherence")
        case("check-report passes a structured report and a NO FINDINGS report",
             ok1[0] == 0 and "1 finding" in ok1[1] and ok2[0] == 0 and "NO FINDINGS" in ok2[1], ok1[1] + ok2[1])
        (w / "abuse" / "report.md").write_text(R("abuse", ["P1"], extra="\nThe surface says `committed the change` and \"I fixed it\".\n"))
        code, out = e.run("check-report", "--workdir", w, "--lens", "abuse")
        case("check-report allows quoting self-fix phrases from the surface", code == 0, out)
        bad = {"wrong surface SHA": report("abuse", "0" * 64, nonce=nonce),
               "missing nonce": report("abuse", sha),
               "missing Lens line": R("abuse").replace("Lens: abuse", ""),
               "empty Inspected": R("abuse", inspected=False) + "\n## Inspected\n\n## Notes\n",
               "own claim of a fix": R("abuse", extra="\nI patched the file myself.\n"),
               "bare NO FINDINGS (no summary)": f"Lens: abuse\nSurface: {sha}\nNonce: {nonce}\nNO FINDINGS\n",
               "lower-case priority": R("abuse", ["P1"]).replace("Priority: P1", "Priority: p1"),
               "bold finding label": R("abuse").replace("NO FINDINGS", "NO FINDINGS here\n**Finding:** hidden one"),
               "NO FINDINGS plus findings": R("abuse", ["P2"]) + "\nNO FINDINGS\n",
               "indented finding beside NO FINDINGS": R("abuse", extra="\n  Finding: hidden\n  Priority: P0\n"),
               "upper-case finding label": R("abuse", extra="\nFINDING: hidden\nPRIORITY: P0\n"),
               "numbered second finding": R("abuse", ["P3"]) + "\nFinding 2: folded in\nPriority: P0\n",
               "NO FINDINGS with a bare Priority line": R("abuse", extra="\nPriority: P0\n"),
               "two Priority lines in one finding": R("abuse", ["P3"]).replace("Priority: P3", "Priority: P3\nPriority: P0")}
        for label, text in bad.items():
            (w / "abuse" / "report.md").write_text(text)
            code, out = e.run("check-report", "--workdir", w, "--lens", "abuse")
            case(f"check-report rejects: {label}", code == 1 and "FAIL" in out, out)
        prose = R("abuse").replace("Reviewed the design.", "- Finding labels in other forms are hidden from the parser.")
        (w / "abuse" / "report.md").write_text(prose)
        code, out = e.run("check-report", "--workdir", w, "--lens", "abuse")
        case("check-report allows a prose bullet that starts with the word Finding", code == 0, out)
        (w / "abuse" / "report.md").write_text(R("abuse", ["P1", "P3"]))

        # ---- synthesize + record
        code, out = e.run("synthesize", "--workdir", w)
        syn = (w / "synthesis.md").read_text() if code == 0 else ""
        case("synthesize lists every finding, pinned to report hashes",
             code == 0 and "### abuse-1 · P1" in syn and "### abuse-2 · P3" in syn
             and syn.count("Disposition: TODO") == 2 and "Report-SHA abuse:" in syn, out)
        code, out = e.run("synthesize", "--workdir", w)
        case("synthesize will not overwrite dispositions without --force", code == 1 and "--force" in out, out)
        code, out = e.run("record", "--workdir", w)
        case("record refuses TODO dispositions, printing every reason",
             code == 1 and out.count("Disposition must be") == 2 and out.count("Reason missing") == 2, out)

        def dispose(r1, r2="Disposition: dismissed\nResolution:\nReason: not reachable in this design"):
            parts = (w / "synthesis.md").read_text().split("### ")
            a1 = parts[1].split("Disposition:")[0] + r1 + "\n\n"
            a2 = parts[2].split("Disposition:")[0] + r2 + "\n"
            (w / "synthesis.md").write_text(parts[0] + "### " + a1 + "### " + a2)

        dispose("Disposition: confirmed\nResolution: deferred\nReason: will do it later on")
        code, out = e.run("record", "--workdir", w)
        case("record refuses a deferred confirmed P1", code == 1 and "cannot be deferred" in out, out)
        dispose("Disposition: dismissed\nResolution:\nReason: not a real problem here")
        code, out = e.run("record", "--workdir", w)
        case("record needs the owner for a dismissed P1", code == 1 and "owner sign-off needed" in out
             and "(dismissed)" in out, out)
        dispose("Disposition: confirmed\nResolution: accepted\nReason: owner accepts this risk")
        code, out = e.run("record", "--workdir", w, "--owner")
        case("record --owner refuses without an interactive terminal", code == 1 and "interactive terminal" in out, out)
        dispose("Disposition: confirmed\nResolution: fixed\nReason: range now bound in v2 design")
        code, out = e.run("record", "--workdir", w)
        case("record refuses a fixed P1 when the live source is unchanged", code == 1
             and "live source is identical" in out, out)
        (d / "design.md").write_text("# Design\nThe gate binds the record to the exact range.\n")
        code, out = e.run("record", "--workdir", w, "--run-id", "test-run")
        rows = [json.loads(l) for l in (e.tmp / "rg" / "records.jsonl").read_text().splitlines()] if code == 0 else []
        r = rows[-1] if rows else {}
        case("record writes a row with derived counts, live-source hash and pinned hashes",
             code == 0 and r.get("findings") == 2 and r.get("confirmed") == 1 and r.get("fixed") == 1
             and r.get("dismissed") == 1 and r.get("run_id") == "test-run" and r.get("surface_sha256") == sha
             and r.get("source_changed") is True and set(r.get("reports_sha256", {})) == {"abuse", "coherence"}
             and r.get("policy_sha256") and r.get("serious_confirmed") == 1, out)
        (w / "abuse" / "report.md").write_text(R("abuse", ["P0", "P3"]))
        code, out = e.run("record", "--workdir", w)
        case("record refuses when a report changed after synthesize", code == 1 and "changed since synthesize" in out, out)
        (w / "surface" / "design.md").write_text("tampered\n")
        code, out = e.run("record", "--workdir", w)
        case("record refuses when the frozen surface changed", code == 1 and "surface changed" in out, out)

        (e.tmp / "rg" / "records.jsonl").open("a").write("{truncated\n")
        code, out = e.run("status", "--project", d)
        case("status lists records and survives a broken line", code == 0 and sha[:12] in out
             and "source changed" in out and "skipped 1 unreadable" in out, out)
        (d / "design.md").write_text("# Design\nThe gate holds every push until a record exists.\n")
        code, out = e.run("status", "--project", d)
        case("status re-checks the live source now (reverted → unchanged)", code == 0
             and "source unchanged since review (now)" in out, out)

        # ---- range surfaces: reviewed and live hashes built the same way
        rp = e.project("rangeproj")
        e.git(rp, "init", "-q", "-b", "main"); e.git(rp, "add", "."); e.git(rp, "commit", "-qm", "one")
        (rp / "design.md").write_text("# Design\nThe gate records each review.\n")
        e.git(rp, "commit", "-qam", "two")
        code, out = run_plan(rp, "--range", "HEAD~1..HEAD", stage="change")
        wr = plan_dir(out) if code == 0 else None
        pr = json.loads((wr / "plan.json").read_text()) if wr else {}
        for lens, f in (("abuse", ["P1"]), ("coherence", [])):
            (wr / lens / "report.md").write_text(report(lens, pr.get("surface_sha256", ""), f, nonce=pr.get("nonce", "")))
        e.run("synthesize", "--workdir", wr)
        s = (wr / "synthesis.md").read_text()
        (wr / "synthesis.md").write_text(s.replace("Disposition: TODO\nResolution:\nReason:",
                                                   "Disposition: confirmed\nResolution: fixed\nReason: bound in the next commit"))
        code, out = e.run("record", "--workdir", wr)
        case("range: record refuses a fixed P1 when nothing changed", code == 1 and "live source is identical" in out, out)
        pj = json.loads((wr / "plan.json").read_text())
        good_root = pj["surface"]["root"]
        pj["surface"]["root"] = str(e.tmp / "nowhere")
        (wr / "plan.json").write_text(json.dumps(pj))
        code, out = e.run("record", "--workdir", wr)
        case("range: record refuses a fixed P1 when the live source cannot be read", code == 1
             and "could not be read" in out, out)
        pj["surface"]["root"] = good_root
        (wr / "plan.json").write_text(json.dumps(pj))
        (rp / "design.md").write_text("# Design\nThe gate records each review, bound to its range.\n")
        code, out = e.run("record", "--workdir", wr)
        rows = [json.loads(l) for l in (e.tmp / "rg" / "records.jsonl").read_text().splitlines() if l.startswith("{\"")]
        case("range: record accepts the fix once the source changed, source_changed true", code == 0
             and rows[-1].get("source_changed") is True, out)
        e.git(rp, "checkout", "-q", "--", "design.md")
        code, out = e.run("status", "--project", rp)
        case("range: status shows the source unchanged once the edit is reverted", code == 0
             and "source unchanged since review (now)" in out, out)
        code, out = e.run("waive", "--project", d, "--stage", "design", "--surface", d / "design.md",
                          "--reason", "owner says so today")
        case("waive refuses without an interactive terminal", code == 1 and "interactive terminal" in out, out)

    passed = sum(results)
    print(f"\n{passed}/{len(results)} cases passed")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
