#!/usr/bin/env bash
# Hidden verifier: restores the project's original tests, adds the hidden ones, runs everything.
# Agent edits to test files do not count. Reward 1 only if every test passes.
set -uo pipefail
APP="${APP_DIR:-/app}"; T="${TESTS_DIR:-/tests}"; LOGS="${LOGS_DIR:-/logs/verifier}"
mkdir -p "$LOGS"; cd "$APP" || exit 1
export GOTOOLCHAIN=local GOFLAGS=-mod=mod
find . -name '*_test.go' -not -path './.git/*' -delete
cp -r "$T/visible/." "$APP/"
cp -r "$T/hidden/." "$APP/"
timeout 600 go test -count=1 -timeout 180s  -v ./internal/pkg/table/... ./pkg/packet/... ./pkg/apiutil/... ./pkg/zebra/... ./cmd/gobgp/... ./pkg/config/oc/... > "$LOGS/go-test.log" 2>&1
status=$?
timeout 300 go test -count=1 -timeout 120s  -v -run '^TestSessionOptions' ./pkg/server/ >> "$LOGS/go-test.log" 2>&1 || status=$?

failed=$(grep -oE '^[[:space:]]*--- FAIL: [A-Za-z0-9_]+' "$LOGS/go-test.log" | awk '{print $3}' | sort -u | tr '\n' ' ')
grep -qE '\[(build|setup) failed\]' "$LOGS/go-test.log" && failed="$failed build_failed"
grep -q 'panic: test timed out' "$LOGS/go-test.log" && failed="$failed test_timeout"
[ "$status" -eq 124 ] && failed="$failed verifier_timeout"
[ "$status" -ne 0 ] && [ -z "${failed// /}" ] && failed="test_binary_failed"
total=$(grep -cE '^[[:space:]]*--- (PASS|FAIL): ' "$LOGS/go-test.log")
passed=$(grep -cE '^[[:space:]]*--- PASS: ' "$LOGS/go-test.log")
list=$(for f in $failed; do printf '"%s",' "$f"; done); list="[${list%,}]"
printf '{"checks_total": %s, "checks_passed": %s, "failed_checks": %s}\n' "$total" "$passed" "$list" > "$LOGS/results.json"
if [ "$status" -eq 0 ]; then echo 1 > "$LOGS/reward.txt"; else echo 0 > "$LOGS/reward.txt"; fi
grep -E '^(ok|FAIL|---)' "$LOGS/go-test.log" | grep -v -- '--- PASS' | tail -n 20
