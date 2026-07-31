#!/usr/bin/env python3
"""Presales harness — stage 3 driver (SPEC-presales-harness.md).

The vertical slice: take an APPROVED requirement list, fan the rating work out
through Ringer, verify every rating with an executed check, merge, and run the
integration gate. Stages 0-2 and 4-5 stay in the skill for now.

    harness/run.py prepare --requirements <input.json> --run-dir <dir>
    # ... run the printed Ringer commands with Ringside up ...
    harness/run.py merge   --run-dir <dir>
    harness/run.py fault   --run-dir <dir> --batch batch-02 --class worker

Design rules this file enforces (not suggests):
  * The human gate is a FILE. Absent = stop. Never inferred from a stage
    completing, never synthesized by a model.
  * The driver owns stage order. The model does stage work, never stage control.
  * Deliverables are validated before they enter the artifact store.
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RATE_CHECK = os.path.join(REPO, "checks", "rate_check.py")
MATRIX_CHECK = os.path.join(REPO, "checks", "matrix_check.py")
GATE_REQUIREMENTS = "gate-requirements.approved.json"
DEFAULT_BATCH = 10

# Ringer owns the schema of runs.jsonl and treats a row with no `model` as
# "unattributed", so appending foreign rows would pollute the very scoreboard
# this is meant to make trustworthy. Fault attribution therefore lands in an
# append-only SIDECAR, joined to the scoreboard on (run_id, task_key).
RINGER_STATE = os.path.expanduser(os.environ.get("RINGER_STATE_DIR", "~/.ringer"))
SCOREBOARD = os.path.join(RINGER_STATE, "runs.jsonl")
FAULT_LOG = os.path.join(RINGER_STATE, "fault-attribution.jsonl")

POLICY_BLOCK = """## Decision rights (ESCALATION-POLICY.md v1.1, Lane summary)

You are a Lane-1 worker: your work is reversible, in-spec, and covered by an executed
check, so proceed without asking. Three things are NOT yours to decide:

- If the library is ambiguous about a capability, do NOT resolve it yourself. Rate it
  Amber "needs confirmation" or Red, set `confirm_with_product` true, and say what is
  ambiguous. Guessing here is the failure this whole pipeline exists to prevent.
- Never take an outward-facing action of any kind. You produce one file in your own task
  directory; nothing you write is ever sent, published, or shared.
- Never widen your own scope. Rate exactly the requirements listed, nothing more.
"""


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def die(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def load_input(path):
    try:
        payload = json.load(open(path))
    except (OSError, json.JSONDecodeError) as e:
        die(f"cannot parse requirements input: {e}")
    for field in ("run_id", "prospect_codename", "library_root", "requirements"):
        if not payload.get(field):
            die(f"input adapter missing required field: {field}")
    ids = [r.get("req_id") for r in payload["requirements"]]
    if len(ids) != len(set(ids)):
        die("input adapter has duplicate req_id values")
    if any(not i for i in ids):
        die("input adapter has a requirement with no req_id")
    return payload


def require_gate(run_dir, name, what):
    """Human gates are files. This is the only thing that opens them."""
    path = os.path.join(run_dir, name)
    if not os.path.exists(path):
        die(f"BLOCKED — {what}\n"
            f"  missing human gate: {path}\n"
            f"  This gate is cleared by a person, never by the harness. Write the file\n"
            f"  when the requirement list has been reviewed and approved:\n"
            f'    echo \'{{"approved_by":"ed","approved_at":"<ISO8601>"}}\' > {path}')
    try:
        token = json.load(open(path))
    except (OSError, json.JSONDecodeError) as e:
        die(f"gate token at {path} is not readable JSON: {e}")
    if not token.get("approved_by"):
        die(f"gate token at {path} has no approved_by — an unattributed gate is not a gate")
    return token


SPEC_TEMPLATE = """You are a solution-fit analyst rating prospect requirements against a
fixed vendor capability library. You are read-only over that library: never edit it.

## What you must produce

Write `ratings.json` in your task directory: a JSON array with EXACTLY one record per
requirement listed below, in this shape:

{{"req_id": "R-001",
  "rating": "Green|Amber|Red",
  "capability": "the specific vendor module or feature that addresses it",
  "evidence": {{"file": "<path relative to the library root>",
               "section": "<heading in that file>",
               "quote": "<a span copied VERBATIM from that file>"}},
  "confidence": "High|Medium|Low",
  "path_to_fit": "concrete route to satisfy it (REQUIRED for Amber and Red)",
  "internal_note": "candid risk or positioning comment",
  "confirm_with_product": false}}

## Rating rules (non-negotiable)

- Green  = native, standard capability today. MUST cite the library.
- Amber  = achievable via configuration, standard integration, or a named roadmap item.
           MUST cite the library AND state exactly what is required.
- Red    = not supported, needs custom development, or no supporting evidence found.
           State the gap plainly.

- No library support means NOT Green. Default to Amber "needs confirmation" or Red and
  set confirm_with_product true.
- NEVER cite the prospect's own documents as evidence of vendor capability. Their
  documents are the source of requirements only.
- The `quote` must be copied character-for-character out of the cited file. It is
  checked mechanically against the file. A paraphrase fails.
- Never soften a Red to Amber for optics; never inflate an Amber to Green.
- A Green at Low confidence is rejected — if the evidence is indirect, it is Amber.

## Library

Read only inside: {library_root}
Start with the settled-rulings file, then the capability reference; consult the help
documentation only to resolve something those two leave ambiguous.

{policy}
## Requirements to rate ({count})

{requirements}

## Hard rules

- Write ONLY `ratings.json` in your own task directory. Do not edit the library, do not
  touch any other repository, do not run git.
- Rate every requirement listed. Do not add requirements that are not listed.
"""


def cmd_prepare(a):
    payload = load_input(a.requirements)
    run_dir = os.path.abspath(a.run_dir)
    os.makedirs(run_dir, exist_ok=True)
    shutil.copy(a.requirements, os.path.join(run_dir, "input.requirements.json"))

    require_gate(run_dir, GATE_REQUIREMENTS,
                 "stage 3 cannot start until the requirement list is approved")

    lib = os.path.realpath(os.path.expanduser(payload["library_root"]))
    if not os.path.isdir(lib):
        die(f"library_root is not a directory: {lib}")

    reqs = payload["requirements"]
    size = a.batch_size
    batches = [reqs[i:i + size] for i in range(0, len(reqs), size)]
    tasks = []
    for n, batch in enumerate(batches, 1):
        key = f"batch-{n:02d}"
        bdir = os.path.join(run_dir, "batches", key)
        os.makedirs(bdir, exist_ok=True)
        binput = {**{k: v for k, v in payload.items() if k != "requirements"},
                  "requirements": batch}
        json.dump(binput, open(os.path.join(bdir, "input.json"), "w"), indent=2)
        listing = "\n".join(
            f"- {r['req_id']} [{r.get('category','?')}] {r['text']}" for r in batch)
        open(os.path.join(bdir, "spec.md"), "w").write(SPEC_TEMPLATE.format(
            library_root=lib, count=len(batch), requirements=listing,
            policy=POLICY_BLOCK))
        tasks.append({
            "key": key,
            "engine": a.engine,
            **({"model": a.model} if a.model else {}),
            "task_type": "gap-rating",
            "timeout_s": a.timeout,
            "expect_files": ["ratings.json"],
            "spec": open(os.path.join(bdir, "spec.md")).read(),
            "check": (f"python3 {RATE_CHECK} --input {os.path.join(bdir, 'input.json')} "
                      f"--output ratings.json --library-root {lib} "
                      f"&& cp ratings.json {os.path.join(bdir, 'ratings.json')}"),
            "verified": ("Every requirement in this batch is rated exactly once, each "
                         "Green/Amber cites a library file whose quoted span was found "
                         "verbatim, every Amber/Red carries a path to fit, and no "
                         "evidence came from a prospect document."),
        })

    manifest = {"run_name": f"gap-rating-{payload['prospect_codename']}",
                "workdir": os.path.join(run_dir, "work"),
                "max_parallel": a.max_parallel,
                "tasks": tasks}
    mpath = os.path.join(run_dir, "swarm.json")
    json.dump(manifest, open(mpath, "w"), indent=2)

    print(f"prepared {len(tasks)} task(s) over {len(reqs)} requirements → {run_dir}")
    print("\nRingside first, then lint, then run:\n")
    print("  ./ringer.py hud")
    print(f"  ./ringer.py lint {mpath}")
    print(f"  ./ringer.py run {mpath} --identity presales-harness")
    print(f"\nthen: {sys.argv[0]} merge --run-dir {run_dir}")


def scoreboard_rows(run_name):
    """Rows Ringer logged for this run, keyed by task_key.

    run_id looks like '<run_name>-<UTC stamp>-p<pid>', so the manifest's run_name
    is the prefix. Read-only: this never writes to Ringer's log.
    """
    by_task = {}
    if not os.path.exists(SCOREBOARD):
        return by_task
    for line in open(SCOREBOARD):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("run_id", "")).startswith(run_name) and row.get("task_key"):
            # later attempts (retries) supersede earlier ones for the same task
            by_task[row["task_key"]] = row
    return by_task


def cmd_merge(a):
    run_dir = os.path.abspath(a.run_dir)
    payload = load_input(os.path.join(run_dir, "input.requirements.json"))
    lib = os.path.realpath(os.path.expanduser(payload["library_root"]))
    bdir = os.path.join(run_dir, "batches")
    if not os.path.isdir(bdir):
        die(f"no batches/ in {run_dir} — run prepare first")

    run_name = f"gap-rating-{payload['prospect_codename']}"
    board = scoreboard_rows(run_name)
    if not board:
        print(f"note: no Ringer scoreboard rows found for run_name {run_name!r} — "
              f"eval rows will carry no run_id and fault attribution cannot join "
              f"to the scoreboard. Has the swarm actually run?")

    merged, missing, rows = [], [], []
    for key in sorted(os.listdir(bdir)):
        out = os.path.join(bdir, key, "ratings.json")
        sb = board.get(key, {})
        row = {"batch": key,
               "run_id": sb.get("run_id"),
               "model": sb.get("model"),
               "task_type": sb.get("task_type"),
               "ringer_verdict": sb.get("verdict"),
               "worker_tokens": sb.get("worker_tokens"),
               "fault": None}
        if not os.path.exists(out):
            missing.append(key)
            row["status"] = "no-output"
        else:
            merged += json.load(open(out))
            row["status"] = "verified"
        rows.append(row)

    matrix = os.path.join(run_dir, "matrix.json")
    json.dump(merged, open(matrix, "w"), indent=2)
    json.dump(rows, open(os.path.join(run_dir, "eval.jsonl"), "w"), indent=2)

    if missing:
        print(f"INCOMPLETE — {len(missing)} batch(es) produced no verified output: "
              f"{', '.join(missing)}")

    print(f"\nmerged {len(merged)} rating(s) → {matrix}\nrunning the integration gate:\n")
    sys.stdout.flush()  # else the child's output interleaves ahead of ours
    rc = subprocess.call([sys.executable, MATRIX_CHECK,
                          "--input", os.path.join(run_dir, "input.requirements.json"),
                          "--matrix", matrix, "--library-root", lib])
    if missing or rc != 0:
        print("\nBUILD NOT DONE — task-level exit 0 is not build-level proof.")
        unattributed = [r["batch"] for r in rows if r["status"] != "verified"]
        if unattributed:
            print("Attribute each failure before the eval row counts (Phase 2.6):")
            for b in unattributed:
                print(f"  {sys.argv[0]} fault --run-dir {run_dir} --batch {b} "
                      f"--class spec|worker|check")
        sys.exit(1)
    print("\nintegration gate PASSED — matrix is internally consistent and fully cited.")


def cmd_fault(a):
    """Attribute a failed batch — Phase 2.6 eval amendment.

    Writes in two places: the run's own eval rows, and the append-only sidecar
    beside Ringer's scoreboard so the attribution is joinable to the model and
    task_type that produced the failure. Without the sidecar the attribution is
    run-local and teaches routing nothing.
    """
    path = os.path.join(os.path.abspath(a.run_dir), "eval.jsonl")
    rows = json.load(open(path))
    hit = [r for r in rows if r["batch"] == a.batch]
    if not hit:
        die(f"no eval row for batch {a.batch}")
    row = hit[0]
    row["fault"] = a.klass
    row["fault_note"] = a.note or ""
    json.dump(rows, open(path, "w"), indent=2)

    if not row.get("run_id"):
        print(f"WARNING: batch {a.batch} has no run_id — the attribution stays run-local "
              f"and will NOT reach the scoreboard sidecar. Re-run merge after the swarm "
              f"has logged, or attribute by hand.")
        print(f"{a.batch}: fault={a.klass} (run-local only)")
        return

    os.makedirs(RINGER_STATE, exist_ok=True)
    with open(FAULT_LOG, "a") as f:
        f.write(json.dumps({
            "ts": _now(),
            "run_id": row["run_id"],
            "task_key": a.batch,
            "task_type": row.get("task_type"),
            "model": row.get("model"),
            "fault": a.klass,
            "note": a.note or "",
            "attributed_by": a.by,
        }) + "\n")
    print(f"{a.batch}: fault={a.klass} → {FAULT_LOG}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prepare", help="batch requirements and emit the Ringer manifest")
    p.add_argument("--requirements", required=True)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    p.add_argument("--engine", default="opencode")
    p.add_argument("--model", default=None, help="OpenRouter slug for the opencode engine")
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--max-parallel", type=int, default=4)
    p.set_defaults(func=cmd_prepare)

    m = sub.add_parser("merge", help="assemble the matrix and run the integration gate")
    m.add_argument("--run-dir", required=True)
    m.set_defaults(func=cmd_merge)

    f = sub.add_parser("fault", help="attribute a failed batch (Phase 2.6 eval amendment)")
    f.add_argument("--run-dir", required=True)
    f.add_argument("--batch", required=True)
    f.add_argument("--class", dest="klass", required=True,
                   choices=["spec", "worker", "check"])
    f.add_argument("--note", default="", help="one line on why, for the next orchestrator")
    f.add_argument("--by", default=os.environ.get("USER", "unknown"))
    f.set_defaults(func=cmd_fault)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
