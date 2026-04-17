#!/bin/bash
#
# Sonar Stop-hook verification script.
#
# Runs the Cherny "give Claude a feedback loop" pattern: after Claude finishes
# a turn, run the fastest-signal checks first (pytest, then tsc), and block
# Stop if any step fails so Claude sees the output and fixes before returning
# control. Idempotent — safe to run repeatedly.
#
# Runs:
#   1. docker compose exec -T api pytest -q  (backend unit tests)
#   2. cd frontend && npx tsc --noEmit        (frontend type check, if node_modules present)
#
# Exit codes:
#   0 — all steps passed (or skipped because stack wasn't relevant)
#   2 — a step failed; Claude Code surfaces stderr as "block" reason
#
# Skip conditions (exit 0 silently):
#   - Not in the Sonar repo root (no docker-compose.yml or backend/pyproject.toml)
#   - api container isn't running (can't exec pytest; don't block Claude on infra)
#   - No uncommitted + no unpushed changes in backend/** or frontend/**  (nothing to verify)
#
# If this script turns out to be annoyingly slow, the most common tuning is
# (a) replace `pytest -q` with a smaller filtered invocation, or
# (b) add stricter path-based skip conditions at the top.

set -u

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" || exit 0

[ -f "docker-compose.yml" ] || exit 0
[ -f "backend/pyproject.toml" ] || exit 0

# Skip if there are no relevant changes to verify. Uses `git status --porcelain`
# so it catches tracked-file edits AND untracked new files in backend/frontend —
# new files are the most common case when Claude is scaffolding (e.g., a new
# model module that hasn't been `git add`ed yet).
has_local_changes() {
  git status --porcelain backend/ frontend/ 2>/dev/null | grep -q .
}
has_unpushed_code_commits() {
  local upstream
  upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null) || return 1
  git log "$upstream..HEAD" --name-only --pretty=format: 2>/dev/null \
    | grep -qE '^(backend|frontend)/'
}
if ! has_local_changes && ! has_unpushed_code_commits; then
  exit 0
fi

# Abort gracefully if the stack isn't up. We don't want to block Claude on
# infrastructure that just isn't running.
if ! docker compose ps api 2>/dev/null | grep -qE '(Up|running)'; then
  echo "verify.sh: api container not running — skipping verification (start with: docker compose up -d api postgres redis)" >&2
  exit 0
fi

FAILED_STEPS=""
OUTPUT=""

# 1. Backend unit tests
TEST_OUT=$(docker compose exec -T api pytest -q --tb=short 2>&1)
TEST_EXIT=$?
if [ $TEST_EXIT -ne 0 ]; then
  FAILED_STEPS="$FAILED_STEPS pytest"
  OUTPUT="$OUTPUT
--- pytest (exit $TEST_EXIT) ---
$(echo "$TEST_OUT" | tail -40)
"
fi

# 2. Frontend tsc --noEmit (only if node_modules already installed — don't
#    install deps from a Stop hook, that'd be a surprise for the user).
if [ -d "frontend/node_modules" ]; then
  TSC_OUT=$(cd frontend && npx --no-install tsc --noEmit 2>&1)
  TSC_EXIT=$?
  if [ $TSC_EXIT -ne 0 ]; then
    FAILED_STEPS="$FAILED_STEPS tsc"
    OUTPUT="$OUTPUT
--- tsc --noEmit (exit $TSC_EXIT) ---
$(echo "$TSC_OUT" | tail -40)
"
  fi

  # 3. Frontend unit tests (vitest) — only if any *.test.* files exist under src/.
  #    Keep this FAST: we use `vitest run` (single pass, no watch).
  if find frontend/src -name '*.test.*' -print -quit 2>/dev/null | grep -q .; then
    VITEST_OUT=$(cd frontend && npm run --silent test:run 2>&1)
    VITEST_EXIT=$?
    if [ $VITEST_EXIT -ne 0 ]; then
      FAILED_STEPS="$FAILED_STEPS vitest"
      OUTPUT="$OUTPUT
--- vitest (exit $VITEST_EXIT) ---
$(echo "$VITEST_OUT" | tail -40)
"
    fi
  fi
fi

if [ -n "$FAILED_STEPS" ]; then
  cat >&2 <<EOF
✗ Sonar Stop-hook verification FAILED.
Failed steps:$FAILED_STEPS
$OUTPUT

Per sonar/CLAUDE.md Engineering Standards: "Green main, always." Fix these
before the task is considered complete.
EOF
  exit 2
fi

# Success path — quiet by default, one confirmation line listing every step that ran.
STEPS_PASSED="pytest"
[ -n "${TSC_EXIT+x}" ] && STEPS_PASSED="$STEPS_PASSED + tsc"
[ -n "${VITEST_EXIT+x}" ] && STEPS_PASSED="$STEPS_PASSED + vitest"
PYTEST_SUMMARY=$(echo "$TEST_OUT" | tail -1)
echo "✓ Sonar Stop-hook verified ($STEPS_PASSED): $PYTEST_SUMMARY" >&2
exit 0
