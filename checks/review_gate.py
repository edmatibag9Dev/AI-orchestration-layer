#!/usr/bin/env python3
"""Review gate — runs a project's declared [review] through adversarial reviewers (SPEC-project-manifest §5.5).

    review_gate.py plan --project DIR --stage design|change (--surface FILE ... | --range A..B)
                        [--workdir W] [--models engine:model,...]
    review_gate.py check-report --workdir W --lens LENS
    review_gate.py synthesize --workdir W [--force]
    review_gate.py record --workdir W [--run-id ID] [--owner]
    review_gate.py waive --project DIR --stage S (--surface FILE ... | --range A..B) --reason TEXT [--days 1-30]
    review_gate.py status --project DIR

plan      freezes the surface into a new workdir, reads the owner-approved [review] policy, and writes one
          brief per lens. Mode `local` (default): the orchestrator gives each brief to its own in-session
          subagent, which returns the report as text; the orchestrator saves it verbatim to
          <lens>/report.md. Mode `external`: also writes a Ringer manifest from the adversarial-review kit,
          lenses assigned round-robin over the model rotation (--models may only reorder or narrow it),
          and lints it. External needs the approved `egress = "external"`, a PUBLIC repo that matches the
          checkout's origin, and a surface that is already published: every file tracked, outside
          [outputs] allowed and identical to the upstream copy, or a range whose end is already upstream.
          Anything else falls back to local and says why.
check-report  the report contract: the kit's rules, plus the reviewer echoes its lens, the surface
          SHA-256 and the nonce from the surface's REVIEW-NONCE.txt, and lists what it inspected.
          It is the Ringer check in external mode and the gate for local reports.
synthesize  enumerates every finding into synthesis.md, pinned to the report hashes it read.
record    re-checks every report and refuses on any problem, printing every reason: the frozen surface
          or a report changed since synthesis; a finding without a disposition and reason; a confirmed
          P0/P1 that is deferred, or marked fixed while the live source is unchanged. A P0/P1 that is
          dismissed or accepted needs the owner (--owner, interactive terminal). One row is appended to
          the records log, with the live source hash next to the reviewed one.
waive     owner only, interactive terminal: a reasoned waiver for one surface, 1 to 30 days.

Exit 0 on success, 1 on a failed check or refusal (every reason printed), 2 on usage errors.
Records are a convention with an audit trail, not a security boundary: anything running as the
owner can write the state folder, and in local mode the orchestrator saves the reports (§5.5 Limits).
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

VERSION = "1.1"
HERE = Path(__file__).resolve().parent
BOOT = HERE.parent / "hooks" / "project-manifest-bootstrap.sh"
LENSES = HERE / "review_lenses.toml"
STATE = Path(os.environ.get("REVIEW_GATE_STATE") or Path.home() / ".claude/state/review-gate")
APPROVALS = Path(os.environ.get("MEMORY_GATE_STATE") or Path.home() / ".claude/state/memory-gate") / "approved.json"
RINGER = Path(os.path.expanduser(os.environ.get("RINGER_DIR", "~/Documents/Claude/ringer")))
ROTATION = [("codex", "gpt-5.6-sol"), ("opencode", "openrouter/z-ai/glm-5.2"),
            ("opencode", "openrouter/moonshotai/kimi-k2.7-code")]
NONCE_FILE = "REVIEW-NONCE.txt"
LABELS = ["Finding", "Evidence", "Impact", "Fix", "Priority", "Confidence"]
DISPOSITIONS, RESOLUTIONS = {"confirmed", "dismissed"}, {"fixed", "deferred", "accepted"}
SERIOUS = ("P0", "P1")
WAIVE_DAYS = range(1, 31)


def die(*lines, code=1):
    for line in lines:
        print(line)
    sys.exit(code)


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True)


def manifest(project):
    r = subprocess.run(["bash", str(BOOT), "--json"], input=json.dumps({"cwd": str(project)}),
                       capture_output=True, text=True)
    try:
        m = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        die(f"the manifest reader printed something that is not JSON: {r.stdout[:200]!r}")
    if m.get("error") or not m.get("path"):
        die(f"no usable project.toml at or above {project}: {m.get('error', 'none found')}")
    return m


def approved_policy(m):
    """The owner-approved [review]. A later edit to [review] never takes effect until re-approved."""
    try:
        e = json.loads(APPROVALS.read_text()).get(m["path"], {})
    except (OSError, json.JSONDecodeError):
        e = {}
    if not e.get("review"):
        die(f"[review] of {m['id']} is not owner-approved yet.",
            f'The owner runs: ~/.claude/hooks/memory-first-gate.sh approve "{Path(m["path"]).parent}"')
    if e.get("review_sha256") != m["review_sha256"]:
        print(f"note: [review] in {m['path']} differs from the approved version; using the approved one "
              f"until the owner re-approves.")
    return e["review"], e["review_sha256"]


def resolve_range(root, rng):
    """Both ends of an explicit A..B or A...B range, as commit ids, or die."""
    parts = re.split(r"\.{2,3}", rng)
    if len(parts) != 2 or not all(p.strip() for p in parts):
        die(f"--range must name two commits, as A..B or A...B (got {rng!r})")
    ends = []
    for p in parts:
        r = git(root, "rev-parse", "--verify", f"{p}^{{commit}}")
        if r.returncode != 0:
            die(f"--range end {p!r} is not a commit: {r.stderr.decode(errors='replace').strip()}")
        ends.append(r.stdout.decode().strip())
    return ends


def freeze(args, m, w):
    """Copy the surface into w/surface/ and return its description."""
    sdir = w / "surface"
    sdir.mkdir(parents=True, exist_ok=True)
    root = Path(m["root"])
    if args.range:
        ends = resolve_range(root, args.range)
        r = git(root, "diff", args.range)
        if r.returncode != 0:
            die(f"git diff {args.range} failed: {r.stderr.decode(errors='replace').strip()}")
        if not r.stdout.strip():
            die(f"git diff {args.range} is empty; nothing to review")
        (sdir / "surface.diff").write_bytes(r.stdout)
        paths = git(root, "diff", "--name-only", args.range).stdout.decode().split()
        return {"kind": "range", "range": args.range, "resolved": ends, "paths": paths, "files": ["surface.diff"]}
    names, sources = [], []
    for f in args.surface:
        src = Path(f).expanduser().resolve()
        if not src.is_file():
            die(f"surface file not found: {f}")
        if src.name == NONCE_FILE or (sdir / src.name).exists():
            die(f"surface file name {src.name} is taken; rename it")
        shutil.copy2(src, sdir / src.name)
        names.append(src.name)
        sources.append(str(src))
    return {"kind": "files", "files": names, "sources": sources}


def surface_sha(w, files):
    h = hashlib.sha256()
    for name in sorted(files):
        h.update(name.encode() + b"\0" + sha_bytes((w / "surface" / name).read_bytes()).encode())
    return h.hexdigest()


def live_sha(m, surface):
    """Hash of the surface as it is now in the project, to tell whether 'fixed' changed anything."""
    root = Path(m["root"]) if m else None
    if surface["kind"] == "range":
        r = git(root, "diff", f"{surface['resolved'][0]}..HEAD")
        return sha_bytes(r.stdout) if r.returncode == 0 else None
    h = hashlib.sha256()
    for name, src in sorted(zip(surface["files"], surface["sources"])):
        p = Path(src)
        h.update(name.encode() + b"\0" + (sha_bytes(p.read_bytes()) if p.is_file() else "missing").encode())
    return h.hexdigest()


def egress_mode(policy, m, surface):
    """External only when the surface is already published content of a public repo."""
    if policy.get("egress") != "external":
        return "local", None
    root = Path(m["root"]).resolve()
    outs = [(root / o).resolve() for o in m.get("outputs", [])]
    origin = git(root, "remote", "get-url", "origin").stdout.decode().strip()
    slug = re.sub(r"\.git$", "", re.sub(r"^.*github\.com[:/]", "", origin))
    if slug != m["repo"]:
        return "local", f"the checkout's origin ({origin or 'none'}) is not {m['repo']}"
    try:
        r = subprocess.run(["gh", "repo", "view", m["repo"], "--json", "visibility", "-q", ".visibility"],
                           capture_output=True, text=True, timeout=20)
        vis = r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return "local", f"could not ask gh for the repo's visibility ({e})"
    if vis != "PUBLIC":
        return "local", f"repo {m['repo']} is not public (gh says {vis or r.stderr.strip()!r})"
    upstream = git(root, "rev-parse", "--verify", "@{u}")
    if upstream.returncode != 0:
        return "local", "the branch has no upstream, so nothing in the surface is provably published"
    if surface["kind"] == "range":
        paths = [(root / p).resolve() for p in surface["paths"]]
        if git(root, "merge-base", "--is-ancestor", surface["resolved"][1], "@{u}").returncode != 0:
            return "local", "the range's end commit is not in the upstream branch yet (unpublished)"
    else:
        paths = [Path(s) for s in surface["sources"]]
        for p in paths:
            if not p.is_relative_to(root):
                return "local", f"{p} is outside the repo"
            rel = str(p.relative_to(root))
            if git(root, "ls-files", "--error-unmatch", rel).returncode != 0:
                return "local", f"{rel} is not tracked by git"
            if git(root, "diff", "--quiet", "@{u}", "--", rel).returncode != 0:
                return "local", f"{rel} differs from the upstream copy (unpublished changes)"
    for p in paths:
        if any(p.is_relative_to(o) for o in outs):
            return "local", f"{p} is under [outputs] allowed; output never goes external"
    return "external", None


def brief(lens, focus, m, stage, surface, sha, w, mode):
    files = "\n".join(f"- {w / 'surface' / f}" for f in [*surface["files"], NONCE_FILE])
    deliver = (f"Write your report to {w / lens / 'report.md'} and never modify any other file."
               if mode == "external" else
               f"Return the whole report as your final reply, nothing else; the orchestrator saves it verbatim to\n"
               f"{w / lens / 'report.md'}. Do not write or modify any file.")
    return f"""You are an adversarial reviewer on the `{lens}` lens. You are read-only. {deliver}

PROJECT: {m['id']} ({stage} review).
SURFACE (frozen copy, SHA-256 {sha}). Read every file in full:
{files}

FOCUS: {focus}
Stay inside this lens; other reviewers cover the other lenses.

TASK: review for concrete failures only: what the surface does or fails to do, who is affected, what
condition allows it, the practical outcome, and the specific fix. Quote the line you rely on. Do not
speculate beyond evidence, do not fetch anything from the network, and do not include patches.

OUTPUT CONTRACT for the report, in this order:
1. `Lens: {lens}`, `Surface: {sha}` and `Nonce: <the value in {NONCE_FILE}>`, each on its own line.
2. `## Summary`.
3. `## Inspected`: the files and sections you actually read, one per line.
4. Either a line that is exactly `NO FINDINGS` followed by what you checked, or one block per finding
   using exactly these labels, each at the very start of its own line (no bold, bullets or headings):
   Finding:, Evidence:, Impact:, Fix:, Priority:, Confidence:. Priority is P0, P1, P2 or P3.
   Confidence is high, medium or low. Evidence cites a file and section.
"""


def cmd_plan(args):
    m = manifest(Path(args.project).resolve())
    policy, policy_sha = approved_policy(m)
    if policy.get(args.stage, "optional") == "off":
        die(f"{args.stage} review is off for {m['id']}")
    lenses = policy.get("lenses") or []
    if not lenses:
        die(f"{m['id']} declares no [review] lenses")
    registry = tomllib.loads(LENSES.read_text())
    missing = [x for x in lenses if x not in registry]
    if missing:
        die(f"lens(es) not in {LENSES.name}: {', '.join(missing)}")
    models = ROTATION
    if args.models:
        models = [tuple(x.split(":", 1)) for x in args.models.split(",")]
        bad = [f"{e}:{mo}" for e, mo in models if (e, mo) not in ROTATION]
        if bad:
            die(f"--models may only reorder or narrow the rotation; not in it: {', '.join(bad)}")
    if args.workdir:
        w = Path(args.workdir).expanduser().resolve()
        w.parent.mkdir(parents=True, exist_ok=True)
        try:
            w.mkdir()
        except FileExistsError:
            die(f"workdir {w} already exists; give a new one")
    else:
        base = STATE / "runs" / f"{m['id']}-{args.stage}-{datetime.datetime.now():%Y%m%dT%H%M%S}"
        base.parent.mkdir(parents=True, exist_ok=True)
        n = 1
        while True:
            w = base if n == 1 else base.with_name(f"{base.name}-{n}")
            try:
                w.mkdir()
                break
            except FileExistsError:
                n += 1
    try:
        plan_into(w, args, m, policy, policy_sha, lenses, registry, models)
    except BaseException:
        shutil.rmtree(w, ignore_errors=True)
        raise


def plan_into(w, args, m, policy, policy_sha, lenses, registry, models):
    surface = freeze(args, m, w)
    sha = surface_sha(w, surface["files"])
    nonce = secrets.token_hex(8)
    (w / "surface" / NONCE_FILE).write_text(nonce + "\n")
    mode, why = egress_mode(policy, m, surface)
    if why:
        print(f"egress: external requested but using local: {why}")
    for lens in lenses:
        (w / lens).mkdir()
        (w / lens / "brief.md").write_text(brief(lens, registry[lens]["focus"], m, args.stage, surface, sha, w, mode))
    plan = {"version": VERSION, "project": m["id"], "manifest": m["path"], "repo": m["repo"],
            "stage": args.stage, "policy": policy, "policy_sha256": policy_sha, "lenses": lenses,
            "mode": mode, "surface": surface, "surface_sha256": sha, "nonce": nonce, "created": int(time.time())}
    self_cmd = f"python3 '{Path(__file__).resolve()}'"
    if mode == "external":
        if len(lenses) > len(set(models)):
            print(f"note: {len(lenses)} lenses over {len(set(models))} models; some models review two lenses")
        tasks = []
        for i, lens in enumerate(lenses):
            engine, model = models[i % len(models)]
            tasks.append({"key": lens, "engine": engine, "model": model, "task_type": "code-review",
                          "timeout_s": 1800, "expect_files": ["report.md"],
                          "spec": (w / lens / "brief.md").read_text(),
                          "check": f"{self_cmd} check-report --workdir '{w}' --lens {lens}",
                          "verified": f"report.md on the {lens} lens echoes its lens, the surface SHA and "
                                      "the nonce, lists what was inspected, and has NO FINDINGS or structured findings."})
        plan["models"] = {t["key"]: f"{t['engine']}:{t['model']}" for t in tasks}
        (w / "manifest.json").write_text(json.dumps(
            {"run_name": f"{m['id']}-{args.stage}-review", "workdir": str(w), "max_parallel": len(tasks),
             "tasks": tasks}, indent=2))
        if not (RINGER / "ringer.py").is_file():
            die(f"external mode needs Ringer at {RINGER} (set RINGER_DIR); manifest left at {w / 'manifest.json'}")
        r = subprocess.run([sys.executable, str(RINGER / "ringer.py"), "lint", str(w / "manifest.json")],
                           capture_output=True, text=True)
        print((r.stdout + r.stderr).strip())
        if r.returncode != 0:
            die("ringer lint failed; fix the manifest before running it")
    (w / "plan.json").write_text(json.dumps(plan, indent=2))
    print(f"plan: {m['id']} {args.stage} review · lenses {', '.join(lenses)} · mode {mode} · surface {sha[:12]}")
    print(f"workdir: {w}")
    if mode == "external":
        print(f"next: (cd '{RINGER}' && ./ringer.py run '{w / 'manifest.json'}')")
    else:
        print("next: give each brief to its own in-session subagent; save each reply verbatim as <lens>/report.md:")
        for lens in lenses:
            print(f"  {w / lens / 'brief.md'}")
    print(f"then: {self_cmd} synthesize --workdir '{w}', dispose every finding in synthesis.md, then record")


def own_prose(text):
    """Report text minus quoted material, so quoting the surface never trips the self-fix rule."""
    text = re.sub(r"(?s)```.*?```", " ", text)
    text = re.sub(r"`[^`\n]*`", " ", text)
    text = re.sub(r"\"[^\"\n]*\"|“[^”\n]*”", " ", text)
    return "\n".join(l for l in text.splitlines() if not re.match(r"(?i)^Evidence\s*:", l))


def report_problems(w, lens, plan):
    path = w / lens / "report.md"
    if not path.is_file():
        return [f"{lens}: report.md not found at {path}"]
    text = path.read_text(errors="replace")
    sha, fails = plan["surface_sha256"], []
    if not re.search(rf"(?im)^Lens\s*:\s*{re.escape(lens)}\s*$", text):
        fails.append(f"{lens}: missing 'Lens: {lens}' line")
    if not re.search(rf"(?im)^Surface\s*:\s*{sha}\s*$", text):
        fails.append(f"{lens}: missing 'Surface: {sha}' line (the reviewer must echo the frozen surface's SHA)")
    if plan.get("nonce") and not re.search(rf"(?im)^Nonce\s*:\s*{plan['nonce']}\s*$", text):
        fails.append(f"{lens}: missing or wrong 'Nonce:' line (the value is in the surface's {NONCE_FILE})")
    if not re.search(r"(?im)^#+\s*summary\b", text):
        fails.append(f"{lens}: missing ## Summary")
    ins = re.search(r"(?ims)^#+\s*inspected\b[^\n]*\n(.*?)(?=^#+\s|^Finding\s*:|^NO FINDINGS|\Z)", text)
    if not ins or not any(l.strip() for l in ins.group(1).splitlines()):
        fails.append(f"{lens}: missing or empty ## Inspected section")
    blocks = re.split(r"(?m)^Finding\s*:\s*", text)[1:]
    no_findings = bool(re.search(r"(?m)^NO FINDINGS\b", text))
    disguised = re.findall(r"(?im)^[ \t]*(?:[-*>#]+[ \t]*|\*\*|__)\**[ \t]*Finding\b", text)
    if disguised:
        fails.append(f"{lens}: {len(disguised)} finding label(s) not at the start of a line "
                     "(bold, bullet or heading); write 'Finding:' plainly")
    if not blocks and not no_findings:
        fails.append(f"{lens}: needs a 'NO FINDINGS' line or at least one Finding: block")
    if blocks and no_findings:
        fails.append(f"{lens}: has both NO FINDINGS and findings")
    for i, b in enumerate(blocks, 1):
        b = "Finding: " + b
        for label in LABELS:
            if not re.search(rf"(?m)^{label}\s*:", b):
                fails.append(f"{lens} finding {i}: missing {label}:")
        if not re.search(r"(?m)^Priority\s*:\s*P[0-3]\b", b):
            fails.append(f"{lens} finding {i}: Priority must be P0, P1, P2 or P3 (upper-case P)")
        if not re.search(r"(?m)^Confidence\s*:\s*(high|medium|low)\b", b):
            fails.append(f"{lens} finding {i}: Confidence must be high, medium or low (lower-case)")
        ev = re.search(r"(?ms)^Evidence\s*:\s*(.+?)(?=\n(?:Impact|Fix|Priority|Confidence)\s*:|\Z)", b)
        if ev and len(ev.group(1).strip()) < 20:
            fails.append(f"{lens} finding {i}: Evidence too thin; cite a file and section")
    if re.search(r"(?i)\b(i\s+(fixed|patched|committed|pushed|modified)|patched\s+the|committed\s+the)\b", own_prose(text)):
        fails.append(f"{lens}: the reviewer claims to have changed files; reviewers never fix")
    return fails


def findings(w, lens):
    text = (w / lens / "report.md").read_text(errors="replace")
    out = []
    for i, b in enumerate(re.split(r"(?m)^Finding\s*:\s*", text)[1:], 1):
        pr = re.search(r"(?im)^Priority\s*:\s*(P[0-3])", b)
        cf = re.search(r"(?im)^Confidence\s*:\s*(high|medium|low)", b)
        out.append({"id": f"{lens}-{i}", "priority": pr.group(1).upper() if pr else "?",
                    "confidence": cf.group(1).lower() if cf else "?", "title": b.strip().splitlines()[0][:200]})
    return out


def load_plan(w):
    try:
        return json.loads((w / "plan.json").read_text())
    except (OSError, json.JSONDecodeError) as e:
        die(f"no readable plan.json in {w}: {e}", code=2)


def cmd_check_report(args):
    w = Path(args.workdir).resolve()
    fails = report_problems(w, args.lens, load_plan(w))
    if fails:
        die("FAIL:", *[f" - {f}" for f in fails])
    n = len(findings(w, args.lens))
    print(f"PASS: {args.lens} report · {n} finding(s)" if n else f"PASS: {args.lens} report · NO FINDINGS")


def report_shas(w, plan):
    return {x: sha_bytes((w / x / "report.md").read_bytes()) for x in plan["lenses"]}


def cmd_synthesize(args):
    w = Path(args.workdir).resolve()
    plan = load_plan(w)
    fails = [f for lens in plan["lenses"] for f in report_problems(w, lens, plan)]
    if fails:
        die("cannot synthesize; fix the reports first:", *[f" - {f}" for f in fails])
    out = w / "synthesis.md"
    if out.exists() and not args.force:
        die(f"{out} exists; pass --force to rebuild it (dispositions would be lost)")
    lines = [f"# Synthesis — {plan['project']} {plan['stage']} review", "",
             f"Surface: {plan['surface_sha256']}",
             *[f"Report-SHA {lens}: {s}" for lens, s in report_shas(w, plan).items()], "",
             "For every finding set Disposition (confirmed | dismissed) and a Reason. A confirmed finding",
             "also needs Resolution (fixed | deferred | accepted). A P0/P1 cannot be deferred; a P0/P1",
             "dismissed or accepted needs the owner (record --owner). Do not edit the finding headings.", ""]
    for lens in plan["lenses"]:
        for f in findings(w, lens):
            lines += [f"### {f['id']} · {f['priority']} · {f['confidence']}", f"Finding: {f['title']}",
                      "Disposition: TODO", "Resolution:", "Reason:", ""]
    out.write_text("\n".join(lines))
    print(f"wrote {out} · {sum(len(findings(w, x)) for x in plan['lenses'])} finding(s) to dispose")


def parse_synthesis(text):
    rows = {}
    for block in re.split(r"(?m)^### ", text)[1:]:
        head = [x.strip() for x in block.splitlines()[0].split("·")]
        get = lambda k: (re.search(rf"(?im)^{k}\s*:[ \t]*(.*)$", block) or [None, ""])[1].strip()
        rows[head[0]] = {"priority": head[1] if len(head) > 1 else "?",
                         "disposition": get("Disposition").lower(), "resolution": get("Resolution").lower(),
                         "reason": get("Reason")}
    pinned = dict(re.findall(r"(?m)^Report-SHA (\S+):\s*([0-9a-f]{64})\s*$", text))
    return rows, pinned


def cmd_record(args):
    w = Path(args.workdir).resolve()
    plan = load_plan(w)
    fails = []
    if surface_sha(w, plan["surface"]["files"]) != plan["surface_sha256"]:
        fails.append("the frozen surface changed after planning; plan a new review")
    report_fails = [f for lens in plan["lenses"] for f in report_problems(w, lens, plan)]
    fails += report_fails
    syn = w / "synthesis.md"
    every, counts, owner_needed, rows = [], {k: 0 for k in ("confirmed", "dismissed", "fixed", "deferred", "accepted")}, [], {}
    if not syn.is_file():
        fails.append("no synthesis.md; run synthesize and dispose every finding")
    elif not report_fails:
        rows, pinned = parse_synthesis(syn.read_text())
        current = report_shas(w, plan)
        for lens, s in current.items():
            if pinned.get(lens) != s:
                fails.append(f"{lens}: report changed since synthesize (or its Report-SHA line is missing); "
                             "rerun synthesize --force and dispose again")
        every = [f for lens in plan["lenses"] for f in findings(w, lens)]
    try:
        m = manifest(Path(plan["manifest"]).parent)
        live = live_sha(m, plan["surface"])
    except SystemExit:
        live = None
    for f in every:
        r = rows.get(f["id"])
        if not r:
            fails.append(f"{f['id']}: missing from synthesis.md")
            continue
        if r["priority"] != f["priority"]:
            fails.append(f"{f['id']}: synthesis says {r['priority']} but the report says {f['priority']}")
        if r["disposition"] not in DISPOSITIONS:
            fails.append(f"{f['id']}: Disposition must be confirmed or dismissed (got {r['disposition']!r})")
        else:
            counts[r["disposition"]] += 1
        if len(r["reason"]) < 10:
            fails.append(f"{f['id']}: Reason missing or too short")
        serious = f["priority"] in SERIOUS
        if r["disposition"] == "dismissed" and serious:
            owner_needed.append(f"{f['id']} (dismissed)")
        if r["disposition"] == "confirmed":
            if r["resolution"] not in RESOLUTIONS:
                fails.append(f"{f['id']}: confirmed needs Resolution fixed, deferred or accepted")
            else:
                counts[r["resolution"]] += 1
            if serious and r["resolution"] == "deferred":
                fails.append(f"{f['id']}: confirmed {f['priority']} cannot be deferred; fix it or have the owner accept it")
            if serious and r["resolution"] == "accepted":
                owner_needed.append(f"{f['id']} (accepted)")
            if serious and r["resolution"] == "fixed" and live == plan["surface_sha256"]:
                fails.append(f"{f['id']}: marked fixed, but the live source is identical to the reviewed surface")
    if owner_needed and not args.owner:
        fails.append(f"owner sign-off needed for {', '.join(owner_needed)}: rerun with --owner in your terminal")
    if fails:
        die("record refused:", *[f" - {f}" for f in fails])
    if owner_needed:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            die("record refused: --owner needs an interactive terminal; the owner runs it, never an agent")
        if input(f"Sign off {', '.join(owner_needed)}? Type yes: ").strip() != "yes":
            die("record refused: owner did not sign off")
    serious_counts = {d: sum(1 for f in every if f["priority"] in SERIOUS and rows[f["id"]]["disposition"] == d)
                      for d in DISPOSITIONS}
    row = {"ts": int(time.time()), "type": "review", "version": VERSION, "project": plan["project"],
           "manifest": plan["manifest"], "stage": plan["stage"], "policy_sha256": plan["policy_sha256"],
           "lenses": plan["lenses"], "mode": plan["mode"], "models": plan.get("models"),
           "surface": plan["surface"], "surface_sha256": plan["surface_sha256"], "live_source_sha256": live,
           "source_changed": live is not None and live != plan["surface_sha256"], "run_id": args.run_id,
           "findings": len(every), **counts, "serious_confirmed": serious_counts["confirmed"],
           "serious_dismissed": serious_counts["dismissed"], "owner_signed": owner_needed,
           "reports_sha256": report_shas(w, plan), "synthesis_sha256": sha_bytes(syn.read_bytes()), "workdir": str(w)}
    STATE.mkdir(parents=True, exist_ok=True)
    with open(STATE / "records.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    print(f"recorded: {plan['project']} {plan['stage']} review · {len(every)} finding(s) · "
          f"{counts['confirmed']} confirmed ({counts['fixed']} fixed, {counts['deferred']} deferred, "
          f"{counts['accepted']} accepted) · {counts['dismissed']} dismissed"
          + (f" · owner signed {len(owner_needed)}" if owner_needed else ""))


def cmd_waive(args):
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        die("waive needs an interactive terminal: the owner runs it, never an agent.")
    if args.days not in WAIVE_DAYS:
        die(f"--days must be 1 to {WAIVE_DAYS[-1]}", code=2)
    if len(args.reason.strip()) < 10:
        die("give a reason of at least 10 characters", code=2)
    m = manifest(Path(args.project).resolve())
    policy, policy_sha = approved_policy(m)
    with tempfile.TemporaryDirectory() as tmp:
        w = Path(tmp)
        surface = freeze(args, m, w)
        sha = surface_sha(w, surface["files"])
    print(f"Waive the {args.stage} review of {m['id']} for surface {sha[:12]} for {args.days} day(s).\nReason: {args.reason}")
    if input("Type yes: ").strip() != "yes":
        die("not waived")
    row = {"ts": int(time.time()), "type": "waived", "version": VERSION, "project": m["id"],
           "manifest": m["path"], "stage": args.stage, "policy_sha256": policy_sha,
           "lenses": policy.get("lenses"), "surface": surface, "surface_sha256": sha,
           "reason": args.reason.strip(), "expires": int(time.time()) + args.days * 86400}
    STATE.mkdir(parents=True, exist_ok=True)
    with open(STATE / "records.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    print("waived")


def cmd_status(args):
    m = manifest(Path(args.project).resolve())
    rows, bad = [], 0
    try:
        lines = (STATE / "records.jsonl").read_text().splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            r = json.loads(line)
            if r.get("project") == m["id"]:
                rows.append(r)
        except json.JSONDecodeError:
            bad += 1 if line.strip() else 0
    if not rows:
        print(f"{m['id']}: no review records")
    now = time.time()
    for r in rows:
        when = datetime.datetime.fromtimestamp(r.get("ts", 0)).strftime("%Y-%m-%d %H:%M")
        if r.get("type") == "waived":
            state = "waived" if r.get("expires", 0) > now else "expired"
            extra = f"until {datetime.date.fromtimestamp(r.get('expires', 0))}: {r.get('reason')}"
        else:
            state = "review"
            extra = (f"{r.get('findings')} findings: {r.get('confirmed')} confirmed, {r.get('dismissed')} dismissed"
                     f" (P0/P1 dismissed {r.get('serious_dismissed', '?')}); owner signed {len(r.get('owner_signed') or r.get('owner_accepted') or [])}"
                     + ("; source changed since review" if r.get("source_changed") else ""))
        print(f"{when}  {state:7} {r.get('stage', '?'):6} {r.get('mode', '-'):8} "
              f"surface {str(r.get('surface_sha256', '?'))[:12]}  {extra}")
    if bad:
        print(f"note: skipped {bad} unreadable line(s) in records.jsonl")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--project", required=True)
    p.add_argument("--stage", required=True, choices=["design", "change"])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--surface", nargs="+")
    g.add_argument("--range")
    p.add_argument("--workdir")
    p.add_argument("--models", help="engine:model,... reorder or narrow the external rotation")
    p = sub.add_parser("check-report")
    p.add_argument("--workdir", required=True)
    p.add_argument("--lens", required=True)
    p = sub.add_parser("synthesize")
    p.add_argument("--workdir", required=True)
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("record")
    p.add_argument("--workdir", required=True)
    p.add_argument("--run-id")
    p.add_argument("--owner", action="store_true")
    p = sub.add_parser("waive")
    p.add_argument("--project", required=True)
    p.add_argument("--stage", required=True, choices=["design", "change"])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--surface", nargs="+")
    g.add_argument("--range")
    p.add_argument("--reason", required=True)
    p.add_argument("--days", type=int, default=7)
    p = sub.add_parser("status")
    p.add_argument("--project", required=True)
    args = ap.parse_args()
    {"plan": cmd_plan, "check-report": cmd_check_report, "synthesize": cmd_synthesize,
     "record": cmd_record, "waive": cmd_waive, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    main()
