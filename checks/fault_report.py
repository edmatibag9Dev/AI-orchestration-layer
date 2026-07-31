#!/usr/bin/env python3
"""Fault-attribution report — Phase 2.6 eval amendment.

    python3 checks/fault_report.py [--days 30]

The amendment says every reviewed failure gets tagged `fault: spec | worker |
check`, so the flywheel can separate ambiguous specs from weak models from
broken checks. Attribution lands in an append-only sidecar next to Ringer's
scoreboard (Ringer owns runs.jsonl's schema; foreign rows there would count as
"unattributed" and skew the very routing data this exists to sharpen).

This is the reader. Without it the sidecar is write-only data — the same
mistake as a shadow log with no owner verdicts.

Reports: attribution counts by class, fault by model and task_type (the
routing signal), and the UNATTRIBUTED BACKLOG — failed scoreboard rows with no
attribution yet, which is the work the amendment actually asks for.
"""
import argparse
import collections
import datetime
import json
import os
import sys

RINGER_STATE = os.path.expanduser(os.environ.get("RINGER_STATE_DIR", "~/.ringer"))
SCOREBOARD = os.path.join(RINGER_STATE, "runs.jsonl")
FAULT_LOG = os.path.join(RINGER_STATE, "fault-attribution.jsonl")
CLASSES = ("spec", "worker", "check")


def read_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def is_failure(row):
    v = str(row.get("verdict", "")).upper()
    return v not in ("PASS", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=None, help="only rows this recent")
    ap.add_argument("--scoreboard", default=SCOREBOARD)
    ap.add_argument("--faults", default=FAULT_LOG)
    a = ap.parse_args()

    board = read_jsonl(a.scoreboard)
    faults = read_jsonl(a.faults)

    if a.days:
        cutoff = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(days=a.days)).isoformat()
        board = [r for r in board if str(r.get("logged_at", "")) >= cutoff]
        faults = [r for r in faults if str(r.get("ts", "")) >= cutoff]

    attributed = {(f.get("run_id"), f.get("task_key")): f for f in faults}
    failures = [r for r in board if is_failure(r)]
    unattributed = [r for r in failures
                    if (r.get("run_id"), r.get("task_key")) not in attributed]

    print("FAULT ATTRIBUTION (Phase 2.6 eval amendment)")
    print(f"  scoreboard rows: {len(board)}   failures: {len(failures)}   "
          f"attributions: {len(faults)}")

    if not faults:
        print("\n  NO ATTRIBUTIONS YET — the amendment is declared but not practiced.")
        print("  Every reviewed failure should carry spec | worker | check, or the")
        print("  scoreboard cannot tell an ambiguous spec from a weak model.")
    else:
        by_class = collections.Counter(f.get("fault") for f in faults)
        print("\n  BY CLASS:")
        for k in CLASSES:
            print(f"    {k:<7} {by_class.get(k, 0)}")
        other = {k: v for k, v in by_class.items() if k not in CLASSES}
        if other:
            print(f"    (off-taxonomy: {other})")

        pairs = collections.Counter(
            (f.get("model") or "?", f.get("task_type") or "(untyped)", f.get("fault"))
            for f in faults)
        print("\n  BY MODEL × TASK TYPE (the routing signal):")
        for (model, tt, cls), n in sorted(pairs.items(), key=lambda kv: -kv[1]):
            print(f"    {model} / {tt}: {cls} ×{n}")

        worker_faults = by_class.get("worker", 0)
        if faults and worker_faults / len(faults) < 0.5:
            print("\n  NOTE: most failures are NOT the worker's fault. Routing to a")
            print("  stronger model would not have fixed them — fix the specs and checks.")

    if unattributed:
        print(f"\n  UNATTRIBUTED BACKLOG ({len(unattributed)}):")
        for r in unattributed[:20]:
            print(f"    - {r.get('run_id')} / {r.get('task_key')} "
                  f"[{r.get('model')}, {r.get('task_type')}] verdict={r.get('verdict')}")
        if len(unattributed) > 20:
            print(f"    ... and {len(unattributed) - 20} more")
    elif failures:
        print("\n  Every recorded failure is attributed.")

    sys.exit(0)


if __name__ == "__main__":
    main()
