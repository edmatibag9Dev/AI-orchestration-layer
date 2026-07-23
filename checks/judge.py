#!/usr/bin/env python3
"""LLM-judge check — SPEC-judge-check.md implementation.

An ordinary Ringer check command: exit 0 = PASS, 1 = FAIL, 2 = judge error.
Sends artifact + rubric to a judge model via the OpenCode CLI (OpenRouter key
stays in OpenCode's auth store) and scores per rubric line.

    python3 checks/judge.py --rubric rubrics/<type>.md --artifact <path> \
        --judge-model openrouter/z-ai/glm-5.2 [--threshold 0.8] [--shadow]

With --shadow: always exits 0, but logs the real verdict to
runs/judge-shadow.jsonl (append-only). Owner verdicts get logged alongside via
--owner-verdict pass|fail (writes an owner row for the same artifact).
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(REPO_ROOT, "runs", "judge-shadow.jsonl")
MAX_ARTIFACT_BYTES = 200_000
CALL_TIMEOUT_S = 300

def die(code, msg):
    print(msg)
    sys.exit(code)

def log_row(row):
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(row) + "\n")
    except OSError as e:
        # Invariant 4: errors fail loudly. An unlogged judge call must not
        # count as a pass — a sandboxed caller cannot satisfy invariant 5.
        die(2, f"JUDGE ERROR: cannot append shadow log at {LOG_PATH}: {e}")

ap = argparse.ArgumentParser()
ap.add_argument("--rubric", required=True)
ap.add_argument("--artifact", required=True)
ap.add_argument("--judge-model", required=True)
ap.add_argument("--threshold", type=float, default=0.8)
ap.add_argument("--shadow", action="store_true")
ap.add_argument("--owner-verdict", choices=["pass", "fail"],
                help="log the human owner's verdict for this artifact and exit (no judge call)")
a = ap.parse_args()

now = datetime.datetime.now(datetime.timezone.utc).isoformat()

if a.owner_verdict:
    log_row({"ts": now, "kind": "owner", "artifact": os.path.abspath(a.artifact),
             "verdict": a.owner_verdict.upper()})
    print(f"OWNER verdict logged for {a.artifact}: {a.owner_verdict.upper()}")
    sys.exit(0)

if not os.path.exists(a.rubric):
    die(2, f"JUDGE ERROR: rubric not found: {a.rubric}")
if not os.path.exists(a.artifact):
    die(2, f"JUDGE ERROR: artifact not found: {a.artifact}")
artifact = open(a.artifact, errors="replace").read()
if len(artifact.encode()) > MAX_ARTIFACT_BYTES:
    die(2, f"JUDGE ERROR: artifact exceeds {MAX_ARTIFACT_BYTES} bytes")
rubric = open(a.rubric).read()
vm = re.search(r"^rubric:\s*(.+)$", rubric, re.M)
rubric_version = vm.group(1).strip() if vm else "unversioned"
line_ids = re.findall(r"^(R\d+)\.", rubric, re.M)
if not line_ids:
    die(2, "JUDGE ERROR: rubric has no numbered R-lines")

prompt = f"""You are a strict quality judge. Score the ARTIFACT against each numbered rubric requirement independently. Judge only what the rubric asks; do not invent requirements. For a FAIL you must cite concrete evidence from the artifact (quote or name the item/section). If a line is not applicable to this artifact (e.g. no ticker appears anywhere for a ticker rule), score it pass and note "n/a".

Respond with ONLY a JSON object, no prose before or after, in exactly this shape:
{{"lines": [{{"id": "R1", "pass": true, "evidence": "short reason or n/a"}}, ...]}}
Include every rubric line id exactly once: {", ".join(line_ids)}.

RUBRIC ({rubric_version}):
{rubric}

ARTIFACT ({os.path.basename(a.artifact)}):
{artifact}"""

try:
    proc = subprocess.run(
        ["opencode", "run", "-m", a.judge_model, prompt],
        capture_output=True, text=True, timeout=CALL_TIMEOUT_S,
        stdin=subprocess.DEVNULL)
except FileNotFoundError:
    die(2, "JUDGE ERROR: opencode CLI not found on PATH")
except subprocess.TimeoutExpired:
    die(2, f"JUDGE ERROR: judge call timed out after {CALL_TIMEOUT_S}s")
if proc.returncode != 0:
    die(2, f"JUDGE ERROR: opencode exited {proc.returncode}: {proc.stderr.strip()[:500]}")

m = re.search(r"\{.*\}", proc.stdout, re.S)
if not m:
    die(2, f"JUDGE ERROR: no JSON object in judge output: {proc.stdout.strip()[:500]}")
try:
    data = json.loads(m.group(0))
    lines = {l["id"]: l for l in data["lines"]}
except (json.JSONDecodeError, KeyError, TypeError) as e:
    die(2, f"JUDGE ERROR: malformed judge JSON ({e}): {m.group(0)[:500]}")
missing = [i for i in line_ids if i not in lines]
if missing:
    die(2, f"JUDGE ERROR: judge omitted rubric lines: {missing}")

failed = [lines[i] for i in line_ids if not lines[i].get("pass")]
score = (len(line_ids) - len(failed)) / len(line_ids)
verdict = "PASS" if score >= a.threshold else "FAIL"

print(f"JUDGE: {a.judge_model}  RUBRIC: {rubric_version}  SCORE: {score:.2f}  "
      f"THRESHOLD: {a.threshold:.2f}  VERDICT: {verdict}" + ("  (shadow)" if a.shadow else ""))
if failed:
    print("FAILED LINES:")
    rub_lines = {i: re.search(rf"^{i}\.\s*(.+)$", rubric, re.M).group(1) for i in line_ids}
    for f_ in failed:
        req = rub_lines.get(f_["id"], "")[:80]
        print(f'- {f_["id"]} "{req}": {f_.get("evidence", "no evidence given")}')

log_row({"ts": now, "kind": "judge", "artifact": os.path.abspath(a.artifact),
         "judge_model": a.judge_model, "rubric_version": rubric_version,
         "score": round(score, 3), "verdict": verdict, "shadow": a.shadow,
         "threshold": a.threshold,
         "failed": [{"id": f_["id"], "evidence": f_.get("evidence", "")} for f_ in failed]})

sys.exit(0 if (a.shadow or verdict == "PASS") else 1)
