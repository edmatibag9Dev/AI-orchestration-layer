#!/usr/bin/env bash
# Rubric regression test — proves a revised rubric line still FAILS a real
# violation, not just that it got quieter.
#
#   checks/rubric-regression.sh [YYYY-MM-DD]
#
# Every rubric revision that removes false positives risks over-correcting into
# a line that can no longer fail anything (v1's R4 fired 4x on compliant text;
# the v2 rewrite had to be shown to still bite). This takes a real archived
# edition, injects known violations, and asserts the judge catches them.
# Synthetic runs log to a scratch file — never to runs/judge-shadow.jsonl.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVE="${BRIEFING_ARCHIVE:-$HOME/Documents/Claude/Projects/ai-briefing/archive}"
MODEL="${JUDGE_MODEL:-openrouter/z-ai/glm-5.2}"
DATE="${1:-$(ls "$ARCHIVE" | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}\.html$' | sort | tail -1 | sed 's/\.html//')}"
SRC="$ARCHIVE/$DATE.html"
[ -f "$SRC" ] || { echo "no archived edition at $SRC" >&2; exit 2; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# R4 violations: a literal unresolved placeholder AND an unsourced GA date.
# R10 violation: a weekday that does not match its calendar date
# (2026-09-24 was a Thursday) — scored mechanically since rubric v4.
python3 - "$SRC" "$TMP/violation.html" <<'PY'
import sys
src = open(sys.argv[1], errors="replace").read()
i = src.find("Executive Summary")
inject = ('<p>OpenAI GPT-6 reaches general availability on August 12, 2026 '
          '(date unconfirmed) — source date?</p>'
          '<p>Edition note: Friday, September 24, 2026</p>')
open(sys.argv[2], "w").write(src[:i] + inject + src[i:] if i >= 0 else inject + src)
PY

echo "regression: $DATE + injected R4 and R10 violations"
OUT="$(python3 "$REPO_ROOT/checks/judge.py" --rubric "$REPO_ROOT/rubrics/morning-briefing.md" \
        --artifact "$TMP/violation.html" --judge-model "$MODEL" --log "$TMP/regression.jsonl" || true)"
echo "$OUT"

RC=0
if ! echo "$OUT" | grep -q '^- R4 '; then
  echo "FAIL: R4 did not fire on an artifact carrying a placeholder and an unsourced GA date."
  echo "      The rewrite has over-corrected — the line can no longer catch what it exists to catch."
  RC=1
elif ! echo "$OUT" | grep -q 'VERDICT: FAIL'; then
  echo "FAIL: R4 fired but the page still PASSED — the rubric's hard_fail: R4 rule is not being enforced."
  RC=1
else
  echo "PASS: R4 still fails a real violation, and the hard_fail rule fails the page"
fi
if echo "$OUT" | grep -q '^- R10 .*mechanical: .*states Friday, computed Thursday'; then
  echo "PASS: R10's mechanical check catches a weekday/date mismatch"
else
  echo "FAIL: R10 did not report the injected 'Friday, September 24, 2026' mismatch mechanically."
  RC=1
fi
exit $RC
