#!/usr/bin/env bash
# Hidden verifier. Writes 1 (pass) or 0 (fail) to $LOGS_DIR/reward.txt and details to results.json.
set -uo pipefail
LOGS_DIR="${LOGS_DIR:-/logs/verifier}"; mkdir -p "$LOGS_DIR"
python3 "${TESTS_DIR:-/tests}/grade.py" > "$LOGS_DIR/grade.log" 2>&1
status=$?
[ $status -eq 0 ] && echo 1 > "$LOGS_DIR/reward.txt" || echo 0 > "$LOGS_DIR/reward.txt"
tail -n 5 "$LOGS_DIR/grade.log"
