#!/usr/bin/env python3
"""Judge/owner agreement report — the Phase 2 graduation instrument.

Shadow mode's product is not the judge's scores; it is the AGREEMENT RATE
between the judge and the owner on the same artifact. This joins the two row
kinds in runs/judge-shadow.jsonl and prints what the graduation decision needs:

    python3 checks/agreement.py [--rubric-version morning-briefing v2]

  * agreement rate over paired artifacts, checked against all three graduation
    conditions — not the rate alone. An 80% rate is satisfiable by a judge
    hardcoded to return PASS if every pair in the set is PASS/PASS, so
    graduation also requires a minimum sample and a minimum number of pairs
    where the two sides COULD have diverged (a FAIL on either side).
  * every disagreement, with the judge's failed lines and the owner's note
  * per-rubric-line flag counts, split by whether the owner still accepted the
    artifact — this is the "which rubric lines get overridden" signal that
    drives rubric revisions
  * artifacts still missing an owner verdict (the unpaired backlog)

Reporting only: always exits 0. It never gates anything.
"""
import argparse
import collections
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(REPO_ROOT, "runs", "judge-shadow.jsonl")
# Graduation conditions (BUILD-PLAN Phase 2, amended 2026-07-31). The rate alone
# is degenerate: the 2026-07-31 backfill scored 100% over 12 pairs in which every
# single value on both sides was PASS — a constant-PASS judge scores identically.
GRADUATION_THRESHOLD = 0.80
MIN_PAIRS = 10
MIN_DIVERGENCE_OPPORTUNITIES = 2  # pairs carrying a FAIL on either side

ap = argparse.ArgumentParser()
ap.add_argument("--log", default=LOG_PATH)
ap.add_argument("--rubric-version", default=None,
                help="restrict to judge rows from one rubric version, e.g. 'morning-briefing v2'")
a = ap.parse_args()

if not os.path.exists(a.log):
    print(f"no shadow log at {a.log}")
    sys.exit(0)

judge_rows, owner_rows = collections.defaultdict(list), {}
for line in open(a.log):
    line = line.strip()
    if not line:
        continue
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        continue
    art = row.get("artifact", "")
    if row.get("kind") == "judge":
        if a.rubric_version and row.get("rubric_version") != a.rubric_version:
            continue
        judge_rows[art].append(row)
    elif row.get("kind") == "owner":
        # last verdict wins: the owner may revise after a closer read
        owner_rows[art] = row

# Pair each artifact's LATEST judge row with the owner's verdict. Re-scores of
# the same artifact under a newer rubric supersede older ones.
latest = {art: max(rows, key=lambda r: r.get("ts", "")) for art, rows in judge_rows.items()}

pairs, unpaired = [], []
for art, jrow in sorted(latest.items()):
    orow = owner_rows.get(art)
    (pairs.append((art, jrow, orow)) if orow else unpaired.append((art, jrow)))

scope = f" [{a.rubric_version}]" if a.rubric_version else ""
print(f"JUDGE/OWNER AGREEMENT{scope}")
print(f"  judged artifacts: {len(latest)}   owner verdicts: {len(owner_rows)}   paired: {len(pairs)}")

if not pairs:
    print("\n  AGREEMENT RATE: UNMEASURABLE — no artifact carries both a judge row and an owner verdict.")
    print("  The judge cannot graduate on judge scores alone. Log owner verdicts with:")
    print("      checks/verdict.sh <today|YYYY-MM-DD> <pass|fail> [note]")
else:
    agree = [p for p in pairs if p[1]["verdict"] == p[2]["verdict"]]
    rate = len(agree) / len(pairs)
    # A pair only tests agreement if at least one side said FAIL. All-PASS pairs
    # are consistent with a judge that cannot fail anything.
    divergent = [p for p in pairs if "FAIL" in (p[1]["verdict"], p[2]["verdict"])]

    conditions = [
        (rate >= GRADUATION_THRESHOLD,
         f"agreement {rate:.0%} >= {GRADUATION_THRESHOLD:.0%}   ({len(agree)}/{len(pairs)} pairs)"),
        (len(pairs) >= MIN_PAIRS,
         f"sample {len(pairs)} >= {MIN_PAIRS} paired artifacts"),
        (len(divergent) >= MIN_DIVERGENCE_OPPORTUNITIES,
         f"divergence opportunities {len(divergent)} >= {MIN_DIVERGENCE_OPPORTUNITIES} "
         f"(pairs with a FAIL on either side)"),
    ]
    print(f"\n  AGREEMENT RATE: {rate:.0%}  ({len(agree)}/{len(pairs)})")
    print("  GRADUATION CONDITIONS:")
    for ok, desc in conditions:
        print(f"    [{'x' if ok else ' '}] {desc}")

    print("    [ ] checks/rubric-regression.sh passes on the current rubric version "
          "(costs a judge call — run it, this tool cannot)")

    if all(ok for ok, _ in conditions):
        print("\n  VERDICT: READY on the log-measurable conditions — confirm the regression")
        print("           check, then the judge may gate INTERNAL work only; prospect-facing")
        print("           deliverables keep a permanent human gate.")
    elif not divergent:
        print("\n  VERDICT: DEGENERATE — every pair is PASS/PASS. This rate is not evidence:")
        print("           a judge hardcoded to return PASS scores identically on this set.")
        print("           What it does show: no false FAILs on accepted work. The false-PASS")
        print("           rate remains unmeasured until the owner rejects something the judge")
        print("           passed, or the judge fails something the owner accepts.")
    else:
        print("\n  VERDICT: NOT READY — conditions unchecked above are unmet.")
    disagreements = [p for p in pairs if p[1]["verdict"] != p[2]["verdict"]]
    if disagreements:
        print(f"\n  DISAGREEMENTS ({len(disagreements)}):")
        for art, j, o in disagreements:
            kind = "FALSE PASS" if j["verdict"] == "PASS" else "FALSE FAIL"
            print(f"  - {os.path.basename(art)}  judge={j['verdict']} ({j.get('score')})  "
                  f"owner={o['verdict']}   <-- {kind}")
            for f in j.get("failed", []):
                print(f"      judge flagged {f.get('id')}: {str(f.get('evidence',''))[:120]}")
            if o.get("note"):
                print(f"      owner: {o['note']}")

# Per-line flag counts. A line flagged on an artifact the owner still accepted
# is a revision candidate, not proof of a bug — read it with the evidence.
flagged = collections.Counter()
flagged_owner_passed = collections.Counter()
for art, jrow in sorted(latest.items()):
    orow = owner_rows.get(art)
    for f in jrow.get("failed", []):
        lid = f.get("id", "?")
        flagged[lid] += 1
        if orow and orow["verdict"] == "PASS":
            flagged_owner_passed[lid] += 1
if flagged:
    print("\n  RUBRIC LINES FLAGGED (across latest judge row per artifact):")
    for lid, n in sorted(flagged.items(), key=lambda kv: (-kv[1], kv[0])):
        seen = flagged_owner_passed[lid]
        tail = f"   ({seen} on artifacts the owner still accepted)" if seen else ""
        print(f"  - {lid}: {n}{tail}")

if unpaired:
    print(f"\n  AWAITING OWNER VERDICT ({len(unpaired)}):")
    for art, j in unpaired:
        print(f"  - {os.path.basename(art)}  judge={j['verdict']} ({j.get('score')})")

sys.exit(0)
