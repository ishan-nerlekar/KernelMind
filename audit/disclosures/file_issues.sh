#!/usr/bin/env bash
# File the drafted issues on harbor-framework/terminal-bench-2 with the GitHub CLI, one at a time,
# asking before each. Needs: gh auth login (once).   Usage: file_issues.sh [task ...]
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO=harbor-framework/terminal-bench-2
command -v gh >/dev/null || { echo "install the GitHub CLI: brew install gh, then gh auth login"; exit 1; }
tasks=("$@"); [ ${#tasks[@]} -eq 0 ] && tasks=($(cd "$HERE" && ls -d */ | tr -d /))
for t in "${tasks[@]}"; do
  title="$(cat "$HERE/$t/ISSUE_TITLE.txt")"
  echo; echo "== $t: $title"
  read -r -p "File this issue? [y/N] " ok
  [ "$ok" = y ] || { echo "skipped"; continue; }
  url="$(gh issue create --repo "$REPO" --title "$title" --body-file "$HERE/$t/ISSUE_BODY.md")" && echo "$t $url" | tee -a "$HERE/FILED.txt"
done
