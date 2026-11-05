#!/usr/bin/env bash
# Overwrite the workspace files with this fix's versions.
set -euo pipefail
cp -r "$(dirname "$0")/files/." "${APP_DIR:-/app}/"
