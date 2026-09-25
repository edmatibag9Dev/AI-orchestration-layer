#!/usr/bin/env python3
"""LLM-judge check — SPEC-judge-check.md implementation.

An ordinary Ringer check command: exit 0 = PASS, 1 = FAIL, 2 = judge error.
Sends artifact + rubric to a judge model via the OpenCode CLI (OpenRouter key
stays in OpenCode's auth store) and scores per rubric line.

    python3 checks/judge.py --rubric rubrics/<type>.md --artifact <path> \
        --judge-model openrouter/z-ai/glm-5.2 [--threshold 0.8] [--shadow]

Rubric-declared mechanical lines: a `mechanical: R10=weekday-date` header
scores that line in code (MECHANICAL_CHECKS below) instead of trusting the
model. The code result replaces the model's; any disagreement is logged.

Rubric-declared hard-fail lines: a `hard_fail: R4[, R7 ...]` header in the
rubric forces VERDICT: FAIL when any listed line fails, regardless of score.

With --shadow: always exits 0, but logs the real verdict to
runs/judge-shadow.jsonl (append-only). Owner verdicts get logged alongside via
--owner-verdict pass|fail (writes an owner row for the same artifact).
"""
import argparse
import datetime
import html
import json
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(REPO_ROOT, "runs", "judge-shadow.jsonl")
MAX_ARTIFACT_BYTES = 200_000
CALL_TIMEOUT_S = 300

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_WD = r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Tues|Wed|Thu|Thur|Thurs|Fri|Sat|Sun)"
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

def _weekday_index(name):
    n = name.lower()
    return next(i for i, w in enumerate(_WEEKDAYS) if w.startswith(n[:3]))

def check_weekday_date(artifact_text):
    """Every stated weekday+date pair on the visible page must agree with the calendar.

    Recognizes 'Thursday, September 24, 2026', 'Wednesday · July 15, 2026',
    'Thu, Sep 24, 2026' and 'Thursday 2026-09-24'. Pairs without a year are skipped (not computable).
    Returns (pass, evidence).
    """
    t = re.sub(r"<(script|style)\b.*?</\1>", " ", artifact_text, flags=re.S | re.I)
    t = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)))
    pairs = []
    for m in re.finditer(_WD + r"\.?\s*[,·—–-]?\s*([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", t):
        mon = _MONTHS.get(m.group(2)[:3].lower())
        if mon:
            pairs.append((m.group(0), m.group(1), int(m.group(4)), mon, int(m.group(3))))
    for m in re.finditer(_WD + r"\s*[,·—–]?\s*(\d{4})-(\d{2})-(\d{2})\b", t):
        pairs.append((m.group(0), m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))))
    if not pairs:
        return True, "mechanical: n/a — no weekday+date pair with a year found on the page"
    bad = []
    for text, wd, y, mo, d in pairs:
        try:
            actual = datetime.date(y, mo, d).weekday()
        except ValueError:
            bad.append(f"'{text}' is not a valid calendar date")
            continue
        if _weekday_index(wd) != actual:
            bad.append(f"'{text}' states {wd}, computed {_WEEKDAYS[actual].capitalize()}")
    if bad:
        return False, "mechanical: " + "; ".join(bad)
    first = pairs[0]
    return True, (f"mechanical: {len(pairs)} weekday+date pair(s) all match; page states "
                  f"'{first[0]}', computed {_WEEKDAYS[datetime.date(first[2], first[3], first[4]).weekday()].capitalize()}")

MECHANICAL_CHECKS = {"weekday-date": check_weekday_date}

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
ap.add_argument("--rubric", help="required when judging; optional with --owner-verdict")
ap.add_argument("--artifact", required=True)
ap.add_argument("--judge-model", help="required when judging; unused with --owner-verdict")
ap.add_argument("--threshold", type=float, default=0.8)
ap.add_argument("--shadow", action="store_true")
ap.add_argument("--owner-verdict", choices=["pass", "fail"],
                help="log the human owner's verdict for this artifact and exit (no judge call)")
ap.add_argument("--owner-note", default="",
                help="with --owner-verdict: why, in the owner's words (feeds rubric revision)")
ap.add_argument("--log", default=LOG_PATH,
                help="override the shadow log path — for rubric regression tests on synthetic "
                     "artifacts, which must never land in the calibration log")
a = ap.parse_args()

LOG_PATH = a.log

now = datetime.datetime.now(datetime.timezone.utc).isoformat()

if a.owner_verdict:
    # The artifact must exist: a verdict logged against a typo'd path can never
    # pair with a judge row, and would silently inflate the "unpaired" count.
    if not os.path.exists(a.artifact):
        die(2, f"JUDGE ERROR: artifact not found: {a.artifact}")
    log_row({"ts": now, "kind": "owner", "artifact": os.path.abspath(a.artifact),
             "verdict": a.owner_verdict.upper(), "note": a.owner_note})
    print(f"OWNER verdict logged for {a.artifact}: {a.owner_verdict.upper()}")
    sys.exit(0)

if not a.rubric:
    die(2, "JUDGE ERROR: --rubric is required when judging")
if not a.judge_model:
    die(2, "JUDGE ERROR: --judge-model is required when judging")
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
mm = re.search(r"^mechanical:\s*(.+)$", rubric, re.M)
mechanical = dict(re.findall(r"(R\d+)\s*=\s*([\w-]+)", mm.group(1))) if mm else {}
for lid, name in mechanical.items():
    if lid not in line_ids:
        die(2, f"JUDGE ERROR: mechanical names a line not in the rubric: {lid}")
    if name not in MECHANICAL_CHECKS:
        die(2, f"JUDGE ERROR: unknown mechanical check '{name}' for {lid}")
hm = re.search(r"^hard_fail:\s*(.+)$", rubric, re.M)
hard_ids = re.findall(r"R\d+", hm.group(1)) if hm else []
unknown = [i for i in hard_ids if i not in line_ids]
if unknown:
    die(2, f"JUDGE ERROR: hard_fail names lines not in the rubric: {unknown}")

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

overrides = []
for lid, name in mechanical.items():
    ok, ev = MECHANICAL_CHECKS[name](artifact)
    model_pass = bool(lines[lid].get("pass"))
    if model_pass != ok:
        overrides.append({"id": lid, "model_pass": model_pass,
                          "model_evidence": lines[lid].get("evidence", "")})
    lines[lid] = {"id": lid, "pass": ok, "evidence": ev}

failed = [lines[i] for i in line_ids if not lines[i].get("pass")]
score = (len(line_ids) - len(failed)) / len(line_ids)
hard_failed = [f_["id"] for f_ in failed if f_["id"] in hard_ids]
verdict = "PASS" if score >= a.threshold and not hard_failed else "FAIL"

print(f"JUDGE: {a.judge_model}  RUBRIC: {rubric_version}  SCORE: {score:.2f}  "
      f"THRESHOLD: {a.threshold:.2f}  VERDICT: {verdict}" + ("  (shadow)" if a.shadow else ""))
for o in overrides:
    print(f"MECHANICAL OVERRIDE: {o['id']} model said {'pass' if o['model_pass'] else 'fail'}, "
          f"code check says {'pass' if lines[o['id']]['pass'] else 'fail'} (code result used)")
if hard_failed:
    print(f"HARD FAIL: {', '.join(hard_failed)} (rubric hard_fail line failed; score ignored)")
if failed:
    print("FAILED LINES:")
    rub_lines = {i: re.search(rf"^{i}\.\s*(.+)$", rubric, re.M).group(1) for i in line_ids}
    for f_ in failed:
        req = rub_lines.get(f_["id"], "")[:80]
        print(f'- {f_["id"]} "{req}": {f_.get("evidence", "no evidence given")}')

log_row({"ts": now, "kind": "judge", "artifact": os.path.abspath(a.artifact),
         "judge_model": a.judge_model, "rubric_version": rubric_version,
         "score": round(score, 3), "verdict": verdict, "shadow": a.shadow,
         "threshold": a.threshold, "hard_failed": hard_failed,
         "mechanical_overrides": overrides,
         "failed": [{"id": f_["id"], "evidence": f_.get("evidence", "")} for f_ in failed]})

sys.exit(0 if (a.shadow or verdict == "PASS") else 1)
