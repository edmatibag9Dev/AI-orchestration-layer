#!/usr/bin/env python3
"""Judge/owner agreement report — the Phase 2 graduation instrument.

Shadow mode's product is not the judge's scores; it is the AGREEMENT RATE
between the judge and the owner on the same artifact. This joins the two row
kinds in runs/judge-shadow.jsonl and prints what the graduation decision needs:

    python3 checks/agreement.py [--rubric-version morning-briefing v2]

  * agreement rate over paired artifacts (BUILD-PLAN gate: >=80% before the
    judge gates internal work)
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
GRADUATION_THRESHOLD = 0.80

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
    status = "MEETS" if rate >= GRADUATION_THRESHOLD else "BELOW"
    print(f"\n  AGREEMENT RATE: {rate:.0%}  ({len(agree)}/{len(pairs)})   "
          f"{status} the {GRADUATION_THRESHOLD:.0%} graduation gate")
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
