#!/bin/bash
# CLASI E2E — Validate the test run against the rubric
# Run this AFTER all 4 sprints are complete.
set -euo pipefail

CONTAINER_NAME="clasi-e2e"
PASS=0
FAIL=0
TOTAL=0

check() {
    local desc="$1"
    local cmd="$2"
    TOTAL=$((TOTAL + 1))
    if docker exec "$CONTAINER_NAME" bash -c "$cmd" >/dev/null 2>&1; then
        echo "  [PASS] $desc"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $desc"
        FAIL=$((FAIL + 1))
    fi
}

check_content() {
    # Check that a file exists AND contains a pattern
    local desc="$1"
    local file="$2"
    local pattern="$3"
    TOTAL=$((TOTAL + 1))
    if docker exec "$CONTAINER_NAME" bash -c "test -f '$file' && grep -qi '$pattern' '$file'" >/dev/null 2>&1; then
        echo "  [PASS] $desc"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $desc"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== CLASI E2E Validation ==="
echo ""

# --- Prerequisites ---
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: Container '$CONTAINER_NAME' is not running."
    exit 1
fi

echo "--- Process Artifacts ---"
check      "overview.md exists" \
           "test -f /project/docs/clasi/overview.md"
check      "Sprint 001 plan" \
           "test -d /project/docs/clasi/sprints/001/planning-docs && ls /project/docs/clasi/sprints/001/planning-docs/*.md 2>/dev/null"
check      "Sprint 002 plan" \
           "test -d /project/docs/clasi/sprints/002/planning-docs && ls /project/docs/clasi/sprints/002/planning-docs/*.md 2>/dev/null"
check      "Sprint 003 plan" \
           "test -d /project/docs/clasi/sprints/003/planning-docs && ls /project/docs/clasi/sprints/003/planning-docs/*.md 2>/dev/null"
check      "Sprint 004 plan" \
           "test -d /project/docs/clasi/sprints/004/planning-docs && ls /project/docs/clasi/sprints/004/planning-docs/*.md 2>/dev/null"

echo ""
echo "--- Ticket Lifecycle ---"
check      "Sprint 001 has tickets" \
           "ls /project/docs/clasi/sprints/001/tickets/*.md 2>/dev/null"
check      "Sprint 002 has tickets" \
           "ls /project/docs/clasi/sprints/002/tickets/*.md 2>/dev/null"
check      "Sprint 003 has tickets" \
           "ls /project/docs/clasi/sprints/003/tickets/*.md 2>/dev/null"
check      "Sprint 004 has tickets" \
           "ls /project/docs/clasi/sprints/004/tickets/*.md 2>/dev/null"

check_content "Ticket files mention 'done'" \
              "/project/docs/clasi/sprints/001/tickets" "done"
check      "Ticket files have acceptance criteria" \
           "grep -rli 'acceptance criteria\|Acceptance Criteria\|AC:' /project/docs/clasi/sprints/*/tickets/*.md 2>/dev/null"

echo ""
echo "--- Sprint Closure ---"
check      "Sprint 001 close report" \
           "test -f /project/docs/clasi/sprints/001/close-report.md"
check      "Sprint 002 close report" \
           "test -f /project/docs/clasi/sprints/002/close-report.md"
check      "Sprint 003 close report" \
           "test -f /project/docs/clasi/sprints/003/close-report.md"
check      "Sprint 004 close report" \
           "test -f /project/docs/clasi/sprints/004/close-report.md"

echo ""
echo "--- Code Quality ---"
check      "guessing_game package exists" \
           "test -d /project/guessing_game && test -f /project/guessing_game/__main__.py"
check      "Menu displays on run" \
           "cd /project && python -m guessing_game <<< 'q' 2>&1 | grep -qi 'Guessing Games'"
check      "q quits cleanly" \
           "cd /project && python -m guessing_game <<< 'q' 2>&1 | grep -qi 'Thanks for playing'"
check      "Tests pass" \
           "cd /project && python -m pytest 2>&1 | grep -E '[0-9]+ passed'"

echo ""
echo "--- Git Hygiene ---"
check      "At least 4 commits" \
           "cd /project && test \$(git rev-list --count HEAD) -ge 4"
check      "No uncommitted changes" \
           "cd /project && git diff --quiet && git diff --cached --quiet"

echo ""
echo "============================================"
echo "  Results: $PASS / $TOTAL passed"
if [ "$FAIL" -eq 0 ]; then
    echo "  Status:  ALL CHECKS PASSED "
    echo "============================================"
    exit 0
else
    echo "  Status:  $FAIL FAILURES"
    echo "============================================"
    exit 1
fi