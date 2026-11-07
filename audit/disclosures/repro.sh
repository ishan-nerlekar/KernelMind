#!/usr/bin/env bash
# Reproduce each verifier finding under Terminal-Bench's own harness (Harbor).
# For every task folder here: run the task's reference solution, then each wrong solution in place of
# solution/solve.sh, with Harbor's oracle agent. A finding is confirmed when the reference scores 1
# and the wrong solution also scores 1.
#
# With --fixed, the task's tests/ get its test_fix.patch first: then the reference should score 1 and
# every wrong solution 0, which checks the suggested fix under Harbor too.
#
#   uv tool install harbor            # once
#   audit/disclosures/repro.sh        # all findings, or name tasks: repro.sh regex-log prove-plus-comm
#   audit/disclosures/repro.sh --fixed headless-terminal
#   UV_HTTP_TIMEOUT=600 audit/disclosures/repro.sh torch-tensor-parallelism   # slow networks: the torch
#     tasks download ~3 GB at verify time; this exports the timeout inside the copied tests/test.sh only.
set -uo pipefail
FIXED=0; [ "${1:-}" = --fixed ] && { FIXED=1; shift; }
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
TB2="$REPO/external/tb2"
OUT="$REPO/results/harbor-repro"
WORK="$(mktemp -d)"
mkdir -p "$OUT"
command -v harbor >/dev/null || { echo "harbor not found: uv tool install harbor"; exit 1; }

reward() {  # reward from a trial's result.json, or the error if there is none
  python3 - "$1" <<'PY'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1]) / "result.json"
if not p.exists():
    print("no result"); sys.exit()
r = json.loads(p.read_text())
v = (r.get("verifier_result") or {}).get("rewards")
print(v if v is not None else f"error: {(r.get('exception_info') or {}).get('exception_message', '?')[:120]}")
PY
}

run() {  # task, case name, solve.sh to use ("" = the task's own reference)
  local task=$1 case=$2 solve=$3 dir="$WORK/$1-$2" name="$1-$2"
  cp -R "$TB2/$task" "$dir"
  if [ -n "${UV_HTTP_TIMEOUT:-}" ]; then  # install step only; the graded tests are unchanged
    f="$dir/tests/test.sh"; { head -n 1 "$f"; echo "export UV_HTTP_TIMEOUT=$UV_HTTP_TIMEOUT"; tail -n +2 "$f"; } > "$f.new"
    cat "$f.new" > "$f"  # cat keeps test.sh's permissions
  fi
  if [ $FIXED = 1 ]; then
    (cd "$dir" && patch -s -p2 < "$HERE/$task/test_fix.patch") || { echo "$task: test_fix.patch does not apply"; return; }
    name="$name-fixed"
  fi
  [ -n "$solve" ] && cp "$solve" "$dir/solution/solve.sh"
  harbor trial start -p "$dir" -a oracle --trials-dir "$OUT" --trial-name "$name" >/dev/null 2>&1
  printf '%-28s %-28s %s\n' "$task" "$case" "$(reward "$OUT/$name")"
}

tasks=("$@")
[ ${#tasks[@]} -eq 0 ] && tasks=($(cd "$HERE" && ls -d [a-z]*/ | tr -d /))
[ $FIXED = 1 ] && tasks=($(for t in "${tasks[@]}"; do [ -f "$HERE/$t/test_fix.patch" ] && echo "$t"; done))
printf '%-28s %-28s %s\n' TASK CASE REWARD
for t in "${tasks[@]}"; do
  run "$t" reference ""
  for s in "$HERE/$t"/*/solve.sh; do
    run "$t" "$(basename "$(dirname "$s")")" "$s"
  done
done
if [ $FIXED = 1 ]; then
  echo "trials in $OUT; with the fix, the reference should score 1 and every wrong solution 0"
else
  echo "trials in $OUT; a wrong solution with reward 1 confirms the finding under Harbor"
fi
