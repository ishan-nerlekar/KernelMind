#!/usr/bin/env bash
# Run a TB2 task's tests natively (no Docker) against one solution, with /app rewritten to a scratch dir.
#   check.sh <task_dir> <solve.sh> <tests_dir> [python]
# Prints PASS/FAIL. For quick local validation of test fixes only; Harbor (repro.sh) is the real check.
set -u
task=$1 solve=$2 tests=$3 py=${4:-python3}
W=$(mktemp -d); T=$(mktemp -d)
cp -R "$task/environment/." "$W/" 2>/dev/null; rm -f "$W/Dockerfile"
sed "s#/app#$W#g; s#/solution/#$task/solution/#g" "$solve" > "$W/.solve.sh"
cp -R "$tests/." "$T/"; find "$T" -type f -exec sed -i "s#/app#$W#g; s#/tests/#$T/#g" {} +
(cd "$W" && PATH="$(dirname "$py"):$PATH" bash .solve.sh >"$W/.solve.log" 2>&1) || { echo "SOLVE-FAILED $(tail -2 "$W/.solve.log")"; exit 2; }
if (cd "$W" && "$py" -m pytest -q -x "$T"/test_outputs.py ${K:+-k "$K"} -p no:cacheprovider >"$W/.pytest.log" 2>&1); then echo PASS; else echo "FAIL [$W/.pytest.log]: $(grep -E '^(FAILED|E )' "$W/.pytest.log" | head -2 | tr '\n' ' ' | cut -c1-200)"; fi
