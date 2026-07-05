#!/usr/bin/env bash
# verify-build.sh — F6 verification: frontend builds cleanly.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "== F6 frontend build verification =="
npm install --silent
npm run build
echo "== F6 build OK =="
