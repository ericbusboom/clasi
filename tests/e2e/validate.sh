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
           "test -f /project/docs/design/overview.md"
check      "Sprint 001 planned" \
           "ls /project/clasi/sprints/{done/,}001-*/sprint.md 2>/dev/null"
check      "Sprint 002 planned" \
           "ls /project/clasi/sprints/{done/,}002-*/sprint.md 2>/dev/null"
check      "Sprint 003 planned" \
           "ls /project/clasi/sprints/{done/,}003-*/sprint.md 2>/dev/null"
check      "Sprint 004 planned" \
           "ls /project/clasi/sprints/{done/,}004-*/sprint.md 2>/dev/null"

echo ""
echo "--- Ticket Lifecycle ---"
check      "Sprint 001 has tickets" \
           "ls /project/clasi/sprints/{done/,}001-*/tickets/*.md /project/clasi/sprints/{done/,}001-*/tickets/done/*.md 2>/dev/null"
check      "Sprint 002 has tickets" \
           "ls /project/clasi/sprints/{done/,}002-*/tickets/*.md /project/clasi/sprints/{done/,}002-*/tickets/done/*.md 2>/dev/null"
check      "Sprint 003 has tickets" \
           "ls /project/clasi/sprints/{done/,}003-*/tickets/*.md /project/clasi/sprints/{done/,}003-*/tickets/done/*.md 2>/dev/null"
check      "Sprint 004 has tickets" \
           "ls /project/clasi/sprints/{done/,}004-*/tickets/*.md /project/clasi/sprints/{done/,}004-*/tickets/done/*.md 2>/dev/null"

check      "Sprint 001 tickets completed (status: done in tickets/done/)" \
           "grep -rli 'status: done' /project/clasi/sprints/{done/,}001-*/tickets/done/*.md 2>/dev/null"
check      "Ticket files have acceptance criteria" \
           "grep -rli 'acceptance criteria\|Acceptance Criteria\|AC:' /project/clasi/sprints/{done/,}*/tickets/*.md /project/clasi/sprints/{done/,}*/tickets/done/*.md 2>/dev/null"

echo ""
echo "--- Sprint Closure ---"
check      "Sprint 001 archived to clasi/sprints/done/" \
           "ls -d /project/clasi/sprints/done/001-* 2>/dev/null"
check      "Sprint 002 archived to clasi/sprints/done/" \
           "ls -d /project/clasi/sprints/done/002-* 2>/dev/null"
check      "Sprint 003 archived to clasi/sprints/done/" \
           "ls -d /project/clasi/sprints/done/003-* 2>/dev/null"
check      "Sprint 004 archived to clasi/sprints/done/" \
           "ls -d /project/clasi/sprints/done/004-* 2>/dev/null"

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
echo "--- Game Behavior (exact spec strings) ---"
check      "Correct-guess message matches spec exactly" \
           "grep -rq 'Correct! You got it!' /project/guessing_game/"
check      "Wrong-guess message matches spec exactly" \
           "grep -rq 'Nope, try again.' /project/guessing_game/"
check      "Out-of-guesses message matches spec exactly" \
           "grep -rq 'Sorry! The answer was 7.' /project/guessing_game/"
check      "Non-numeric-input message matches spec exactly" \
           "grep -rq 'Please enter a number.' /project/guessing_game/"

echo ""
echo "--- Git Hygiene ---"
check      "At least 4 commits" \
           "cd /project && test \$(git rev-list --count HEAD) -ge 4"
check      "No uncommitted changes" \
           "cd /project && git diff --quiet && git diff --cached --quiet"

echo ""
echo "--- OOP Change Resilience ---"
check      "OOP 1: menu uses title case (Guess My Favorite Number)" \
           "grep -q 'Guess My Favorite Number' /project/guessing_game/menu.py"
check      "OOP 2: __version__ present in __init__.py" \
           "grep -q '__version__' /project/guessing_game/__init__.py"
check      "OOP 3: TODO comment present in number_game.py" \
           "grep -q 'difficulty levels' /project/guessing_game/number_game.py"
check      "OOP 1: 'Guess My Favorite Color' also title case" \
           "grep -q 'Guess My Favorite Color' /project/guessing_game/menu.py"
check      "OOP 1: 'Guess Where I Live' also title case" \
           "grep -q 'Guess Where I Live' /project/guessing_game/menu.py"

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
