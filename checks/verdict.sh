#!/usr/bin/env bash
# Owner-verdict shortcut — the human half of judge shadow mode.
#
#   checks/verdict.sh today pass
#   checks/verdict.sh yesterday fail "exec summaries ran 6-7 sentences"
#   checks/verdict.sh 2026-07-28 fail "R1 was right"
#
# Shadow mode only produces a graduation signal if BOTH verdicts exist for the
# same artifact. The judge logs itself automatically from the briefing pipeline;
# this is the two-word command that logs the owner's side while he reads the edition.
# Read the pair back with: python3 checks/agreement.py
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVE="${BRIEFING_ARCHIVE:-$HOME/Documents/Claude/Projects/ai-briefing/archive}"

usage() {
  echo "usage: $(basename "$0") <today|yesterday|YYYY-MM-DD> <pass|fail> [note]" >&2
  exit 2
}
[ $# -ge 2 ] || usage

case "$1" in
  today)     DATE="$(date +%F)" ;;
  yesterday) DATE="$(date -v-1d +%F 2>/dev/null || date -d yesterday +%F)" ;;
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) DATE="$1" ;;
  *) usage ;;
esac

VERDICT="$2"
case "$VERDICT" in pass|fail) ;; *) usage ;; esac
NOTE="${3:-}"

ARTIFACT="$ARCHIVE/$DATE.html"
if [ ! -f "$ARTIFACT" ]; then
  echo "no archived edition for $DATE at $ARTIFACT" >&2
  exit 2
fi

exec python3 "$REPO_ROOT/checks/judge.py" \
  --artifact "$ARTIFACT" --owner-verdict "$VERDICT" --owner-note "$NOTE"
