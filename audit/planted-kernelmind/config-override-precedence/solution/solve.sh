#!/usr/bin/env bash
# Apply this fix to the workspace.
set -euo pipefail
cd "${APP_DIR:-/app}"
git apply --whitespace=nowarn "$(dirname "$0")/fix.patch"
