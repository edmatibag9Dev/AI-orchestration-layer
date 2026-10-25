#!/usr/bin/env python3
"""project.toml validator — SPEC-project-manifest.md §5.3.

    python3 checks/manifest_check.py <path/to/project.toml> [--sensitive-file <path>]

Exit 0 only when every rule below holds; exit 1 otherwise; exit 2 on usage
errors (file missing). Every failure prints on its own line as
`FAIL <rule> <key>: <why>`, so the output can feed a Ringer retry prompt.

  1 parse          the file is valid TOML
  2 version        [project] spec_version is a known version
  3 required       required keys present, with the right type and value set
  4 slug           [project] id is lowercase letters, digits and hyphens
  5 no-repo        repo = "none" carries a no_repo_reason
  6 engagement     per-prospect mode has a root that exists and is outside
                   every git repo
  7 triggers       every [ringer] triggers entry resolves to a heading anchor
                   in a file that exists (relative to the manifest)
  8 sensitive      no [memory] standing_scope bucket is Sensitive-rank
  9 scrub          no line carries an email, token, key or /Users/<name> path;
                   extra owner-specific patterns come from $SCRUB_PATTERN
 10 lenses         every [review] lenses entry is in the lens registry
                   (checks/review_lenses.toml, beside this script; §5.5)

The Sensitive list defaults to the Sensitive-rank buckets in the memory
system's classification spec. --sensitive-file (one bucket per line, # for
comments) replaces it; the spec leaves its permanent home open (§9).
"""
import argparse
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

KNOWN_VERSIONS = {1}
DEFAULT_SENSITIVE = ["Trading", "Short Trading", "Business"]
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SCRUB = [
    ("email address", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("Slack token", re.compile(r"xox[abprs]-[\w-]+")),
    ("API key", re.compile(r"\bsk-[A-Za-z0-9]{8,}")),
    ("key assignment", re.compile(r"api[_-]?key\s*[:=]", re.I)),
    ("home path", re.compile(r"/Users/[^/\s\"']+")),
]
ENUMS = {
    ("project", "kind"): {"repo", "folder"},
    ("project", "status"): {"active", "paused", "retired"},
    ("engagement", "mode"): {"none", "per-prospect"},
    ("review", "design"): {"required", "optional", "off"},
    ("review", "change"): {"required", "optional", "off"},
    ("review", "egress"): {"local", "external"},
    ("review", "surface"): {"commits", "outputs"},
}
LENS_REGISTRY = Path(__file__).resolve().parent / "review_lenses.toml"

REQUIRED = [("spec_version", int), ("id", str), ("name", str), ("kind", str),
            ("repo", str), ("status", str)]
LISTS = [("memory", "standing_scope"), ("memory", "recall"), ("skills", "prefer"),
         ("skills", "avoid"), ("ringer", "task_types"), ("ringer", "triggers"),
         ("review", "lenses"), ("loops", "routines"), ("done", "criteria"),
         ("done", "checks"), ("outputs", "allowed")]


def gh_slug(heading):
    """GitHub-style heading anchor."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def anchors(path):
    found, fence = set(), False
    for line in path.read_text(errors="replace").splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        elif not fence and re.match(r"^#{1,6} ", line):
            found.add(gh_slug(line.lstrip("#")))
    return found


def inside_git(path):
    r = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def load_sensitive(path):
    if not path:
        return DEFAULT_SENSITIVE, "default list"
    names = [l.split("#")[0].strip() for l in Path(path).read_text().splitlines()]
    return [n for n in names if n], str(path)


def check(manifest, sensitive):
    fails = []
    fail = lambda rule, key, why: fails.append(f"FAIL {rule} {key}: {why}")
    text = manifest.read_text(errors="replace")

    for n, line in enumerate(text.splitlines(), 1):
        for label, rx in SCRUB:
            if rx.search(line):
                fail("scrub", f"line {n}", f"{label} found; the manifest must stay publishable")
        extra = os.environ.get("SCRUB_PATTERN")
        if extra and re.search(extra, line, re.I):
            fail("scrub", f"line {n}", "matches $SCRUB_PATTERN (an owner-specific identifier)")

    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        fail("parse", "file", str(e))
        return fails

    proj = doc.get("project")
    if not isinstance(proj, dict):
        fail("required", "[project]", "section missing")
        return fails

    version = proj.get("spec_version")
    if isinstance(version, int) and version not in KNOWN_VERSIONS:
        fail("version", "project.spec_version",
             f"{version} is newer than this validator knows ({sorted(KNOWN_VERSIONS)})")

    for key, typ in REQUIRED:
        if key not in proj:
            fail("required", f"project.{key}", "missing")
        elif not isinstance(proj[key], typ) or isinstance(proj[key], bool):
            fail("required", f"project.{key}", f"must be {typ.__name__}, got {type(proj[key]).__name__}")

    for (sec, key), allowed in ENUMS.items():
        val = doc.get(sec, {}).get(key)
        if val is not None and val not in allowed:
            fail("required", f"{sec}.{key}", f"{val!r} not in {sorted(allowed)}")

    for sec, key in LISTS:
        val = doc.get(sec, {}).get(key)
        if val is not None and not (isinstance(val, list) and all(isinstance(v, str) for v in val)):
            fail("required", f"{sec}.{key}", "must be a list of strings")

    pid = proj.get("id")
    if isinstance(pid, str) and not SLUG.match(pid):
        fail("slug", "project.id", f"{pid!r} must be lowercase letters, digits and hyphens")

    repo = proj.get("repo")
    if isinstance(repo, str):
        if repo == "none":
            if not str(proj.get("no_repo_reason", "")).strip():
                fail("no-repo", "project.no_repo_reason", 'required when repo = "none"')
        elif not REPO.match(repo):
            fail("required", "project.repo", f'{repo!r} must be "<owner>/<name>" or "none"')
        if proj.get("kind") == "folder" and repo != "none":
            fail("no-repo", "project.repo", 'a folder project must have repo = "none"')

    eng = doc.get("engagement", {})
    if eng.get("mode") == "per-prospect":
        root = eng.get("root")
        if not isinstance(root, str) or not root.strip():
            fail("engagement", "engagement.root", "required when mode = \"per-prospect\"")
        else:
            p = Path(os.path.expanduser(root))
            p = p if p.is_absolute() else (manifest.parent / p)
            if not p.is_dir():
                fail("engagement", "engagement.root", f"{root} does not exist")
            elif (top := inside_git(p)) is not None:
                fail("engagement", "engagement.root",
                     f"{root} is inside the git repo {top}; records must never be committed")

    for trig in doc.get("ringer", {}).get("triggers", []) or []:
        if not isinstance(trig, str):
            continue
        path_part, _, anchor = trig.partition("#")
        target = manifest.parent / path_part
        if not anchor:
            fail("triggers", "ringer.triggers", f"{trig!r} needs a #heading-anchor")
        elif not target.is_file():
            fail("triggers", "ringer.triggers", f"{path_part} does not exist")
        elif anchor not in anchors(target):
            fail("triggers", "ringer.triggers", f"no heading with anchor #{anchor} in {path_part}")

    lenses = doc.get("review", {}).get("lenses", []) or []
    if lenses:
        try:
            known = set(tomllib.loads(LENS_REGISTRY.read_text()))
        except (OSError, tomllib.TOMLDecodeError) as e:
            known = None
            fail("lenses", "review.lenses", f"lens registry unreadable ({LENS_REGISTRY.name}): {e}")
        for lens in lenses:
            if known is not None and isinstance(lens, str) and lens not in known:
                fail("lenses", "review.lenses", f"{lens!r} is not in {LENS_REGISTRY.name}; add it there first")

    sens = {s.lower() for s in sensitive}
    for bucket in doc.get("memory", {}).get("standing_scope", []) or []:
        if isinstance(bucket, str) and bucket.lower() in sens:
            fail("sensitive", "memory.standing_scope",
                 f"{bucket!r} is Sensitive-rank; it needs a live confirm and never a standing scope")
    return fails


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("manifest")
    ap.add_argument("--sensitive-file")
    args = ap.parse_args()

    manifest = Path(args.manifest)
    if not manifest.is_file():
        print(f"usage error: {manifest} not found")
        return 2
    sensitive, source = load_sensitive(args.sensitive_file)
    fails = check(manifest.resolve(), sensitive)
    if fails:
        print("\n".join(fails))
        print(f"{len(fails)} failure(s) in {manifest}")
        return 1
    print(f"PASS: {manifest} (Sensitive list: {source})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
