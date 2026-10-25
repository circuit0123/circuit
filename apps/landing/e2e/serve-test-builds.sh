#!/usr/bin/env bash
# Builds the landing site twice with test URLs and serves both builds: feature flags ON on :3101, OFF on :3102.
# The flags come from a stand-in for GET /api/config (mock-config.mjs) that only lives while the builds run.
set -euo pipefail
cd "$(dirname "$0")/.."

export NEXT_PUBLIC_APP_URL=http://app.test
export NEXT_PUBLIC_LANDING_URL=http://localhost:3101
export NEXT_PUBLIC_CONTACT_EMAIL=hello@example.com

node e2e/mock-config.mjs 3201 on >/dev/null & ON=$!
node e2e/mock-config.mjs 3202 off >/dev/null & OFF=$!
trap 'kill $ON $OFF 2>/dev/null || true' EXIT
sleep 1

NEXT_DIST_DIR=.out-on  NEXT_PUBLIC_API_URL=http://127.0.0.1:3201 pnpm build
NEXT_DIST_DIR=.out-off NEXT_PUBLIC_API_URL=http://127.0.0.1:3202 pnpm build
kill $ON $OFF 2>/dev/null || true
trap - EXIT

python3 -m http.server 3101 -d .out-on >/dev/null 2>&1 &
exec python3 -m http.server 3102 -d .out-off
