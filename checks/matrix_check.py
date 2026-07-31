#!/usr/bin/env python3
"""Integration gate — SPEC-presales-harness.md §7.

Task-level exit 0 is not build-level proof. After the batches merge, this runs
the SYSTEM-level check on the assembled matrix: coverage survives the merge,
every citation still resolves, and no internal-only content leaked into an
artifact marked external.

    python3 checks/matrix_check.py --input <requirements.json> \
        --matrix <matrix.json> --library-root <path> [--external <file>]

Exit 0 only when every gate passes.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rate_check import check as rate_rules, norm, read_text  # noqa: E402

INTERNAL_ONLY_KEYS = ("internal_note", "confirm_with_product")
INTERNAL_MARKERS = ("confirm with product", "internal note", "confidential — internal",
                    "risk to us", "competitive positioning")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--matrix", required=True)
    ap.add_argument("--library-root", default=os.environ.get("HARNESS_LIBRARY_ROOT"))
    ap.add_argument("--external", help="prospect-facing artifact to scan for internal-only content")
    a = ap.parse_args()

    if not a.library_root:
        print("GATE ERROR: --library-root not given and HARNESS_LIBRARY_ROOT unset")
        sys.exit(2)
    lib = os.path.realpath(os.path.expanduser(a.library_root))
    payload = json.load(open(a.input))
    requirements = payload.get("requirements", [])
    matrix = json.load(open(a.matrix))

    gates = []

    # gate 1+2 — coverage and citations survived the merge (re-run the per-task rules
    # over the ASSEMBLED matrix; a merge that drops or duplicates records fails here)
    fails = rate_rules(requirements, matrix, lib)
    gates.append(("coverage + citations after merge", not fails,
                  f"{len(fails)} violation(s)"))

    # gate 3 — RAG counts are derivable and internally consistent
    counts = {}
    for rec in matrix:
        counts[rec.get("rating")] = counts.get(rec.get("rating"), 0) + 1
    total = sum(counts.values())
    gates.append(("RAG counts sum to the matrix", total == len(matrix),
                  f"{counts} sums to {total}, matrix has {len(matrix)}"))

    # gate 4 — no internal-only content in a prospect-facing artifact
    if a.external:
        body, err = read_text(a.external)
        if body is None:
            gates.append(("external artifact readable", False, err))
        else:
            n = norm(body).lower()
            leaked = [m for m in INTERNAL_MARKERS if m in n]
            notes = [r["req_id"] for r in matrix
                     if str(r.get("internal_note") or "").strip()
                     and norm(str(r["internal_note"])).lower() in n]
            ok = not leaked and not notes
            detail = ""
            if leaked:
                detail += f"internal markers present: {leaked}. "
            if notes:
                detail += f"internal_note text reproduced for: {notes[:5]}"
            gates.append(("no internal-only content in external artifact", ok,
                          detail or "clean"))

    print("INTEGRATION GATE")
    for name, ok, detail in gates:
        print(f"  [{'x' if ok else ' '}] {name} — {detail}")
    if fails:
        print("\n  post-merge violations:")
        for rid, rule, reason in fails[:40]:
            print(f"  - {rid} [{rule}]: {reason}")
        if len(fails) > 40:
            print(f"  ... and {len(fails) - 40} more")

    failed = [n for n, ok, _ in gates if not ok]
    if failed:
        print(f"\nGATE FAILED: {len(failed)} of {len(gates)} — the build is not done.")
        sys.exit(1)
    print(f"\nGATE PASSED: {len(gates)} of {len(gates)}.")
    sys.exit(0)


if __name__ == "__main__":
    main()
