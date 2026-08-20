#!/bin/bash
# CLASI E2E — Validate the test run against the rubric
# Run this AFTER all 4 sprints are complete.
#
# Most checks read the host bind-mounted project directory directly, so
# validation still works after ./stop.sh has already removed the
# container (SUC-002). Three checks execute code (menu display, quit,
# pytest) and still require the running container — they FAIL by design
# once the container is gone, which is expected, not a bug in this
# script or a regression in the harness.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTAINER_NAME="clasi-e2e"
CANONICAL_DIR="$SCRIPT_DIR/e2e-project"

RUN_ID_OVERRIDE=""

usage() {
    echo "  Usage: ./validate.sh [--run-id <id>]" >&2
}

while [ $# -gt 0 ]; do
    case "$1" in
        --run-id)
            if [ $# -lt 2 ]; then
                echo "ERROR: --run-id requires a value." >&2
                usage
                exit 1
            fi
            RUN_ID_OVERRIDE="$2"
            shift 2
            ;;
        --*)
            echo "ERROR: Unknown argument '$1'." >&2
            usage
            exit 1
            ;;
        *)
            if [ -n "$RUN_ID_OVERRIDE" ]; then
                echo "ERROR: Unknown argument '$1'." >&2
                usage
                exit 1
            fi
            RUN_ID_OVERRIDE="$1"
            shift
            ;;
    esac
done

if [ ! -e "$CANONICAL_DIR" ]; then
    echo "ERROR: $CANONICAL_DIR does not exist; run ./start.sh first." >&2
    exit 1
fi
HOST_PROJECT_DIR="$(cd -P "$CANONICAL_DIR" && pwd)"

# --- Run-id resolution: explicit --run-id/positional wins; otherwise
# .e2e-runs/current. Same contract as run.sh/stop.sh. Fail loudly rather
# than silently operating on the wrong or a nonexistent run directory. ---
resolve_run_id() {
    local override="$1" project_dir="$2" current_file id
    if [ -n "$override" ]; then
        printf '%s\n' "$override"
        return 0
    fi
    current_file="$project_dir/.e2e-runs/current"
    if [ -f "$current_file" ]; then
        id="$(cat "$current_file")"
        if [ -n "$id" ]; then
            printf '%s\n' "$id"
            return 0
        fi
    fi
    return 1
}

if ! RUN_ID="$(resolve_run_id "$RUN_ID_OVERRIDE" "$HOST_PROJECT_DIR")"; then
    echo "ERROR: could not resolve a run id — no --run-id given and" >&2
    echo "  $HOST_PROJECT_DIR/.e2e-runs/current does not exist or is empty." >&2
    echo "  Run ./start.sh first, or pass --run-id <id> explicitly." >&2
    exit 1
fi
RUN_DIR="$HOST_PROJECT_DIR/.e2e-runs/$RUN_ID"
mkdir -p "$RUN_DIR"
VALIDATE_LOG="$RUN_DIR/validate.txt"

PASS=0
FAIL=0
TOTAL=0

check() {
    # docker-exec based: only for checks that must execute code inside the
    # container. Requires the container to still be running.
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

check_host() {
    # Host-path based: reads the bind-mounted project directly, so it
    # works whether or not the container is still running.
    local desc="$1"
    local cmd="$2"
    TOTAL=$((TOTAL + 1))
    if bash -c "$cmd" >/dev/null 2>&1; then
        echo "  [PASS] $desc"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $desc"
        FAIL=$((FAIL + 1))
    fi
}

main() {
    echo "=== CLASI E2E Validation ==="
    echo "  Run: $RUN_ID"
    echo "  Project dir: $HOST_PROJECT_DIR"
    echo ""

    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "  Container '$CONTAINER_NAME' is running — all checks active."
    else
        echo "  Container '$CONTAINER_NAME' is not running — the 3 checks that execute"
        echo "  code (menu display, quit, pytest) will FAIL by design; host-path"
        echo "  checks still run against $HOST_PROJECT_DIR."
    fi
    echo ""

    echo "--- Process Artifacts ---"
    check_host "overview.md exists" \
               "test -f '$HOST_PROJECT_DIR/docs/design/overview.md'"
    check_host "Sprint 001 planned" \
               "ls '$HOST_PROJECT_DIR'/clasi/sprints/{done/,}001-*/sprint.md 2>/dev/null"
    check_host "Sprint 002 planned" \
               "ls '$HOST_PROJECT_DIR'/clasi/sprints/{done/,}002-*/sprint.md 2>/dev/null"
    check_host "Sprint 003 planned" \
               "ls '$HOST_PROJECT_DIR'/clasi/sprints/{done/,}003-*/sprint.md 2>/dev/null"
    check_host "Sprint 004 planned" \
               "ls '$HOST_PROJECT_DIR'/clasi/sprints/{done/,}004-*/sprint.md 2>/dev/null"

    echo ""
    echo "--- Ticket Lifecycle ---"
    check_host "Sprint 001 has tickets" \
               "ls '$HOST_PROJECT_DIR'/clasi/sprints/{done/,}001-*/tickets/*.md '$HOST_PROJECT_DIR'/clasi/sprints/{done/,}001-*/tickets/done/*.md 2>/dev/null"
    check_host "Sprint 002 has tickets" \
               "ls '$HOST_PROJECT_DIR'/clasi/sprints/{done/,}002-*/tickets/*.md '$HOST_PROJECT_DIR'/clasi/sprints/{done/,}002-*/tickets/done/*.md 2>/dev/null"
    check_host "Sprint 003 has tickets" \
               "ls '$HOST_PROJECT_DIR'/clasi/sprints/{done/,}003-*/tickets/*.md '$HOST_PROJECT_DIR'/clasi/sprints/{done/,}003-*/tickets/done/*.md 2>/dev/null"
    check_host "Sprint 004 has tickets" \
               "ls '$HOST_PROJECT_DIR'/clasi/sprints/{done/,}004-*/tickets/*.md '$HOST_PROJECT_DIR'/clasi/sprints/{done/,}004-*/tickets/done/*.md 2>/dev/null"

    check_host "Sprint 001 tickets completed (status: done in tickets/done/)" \
               "grep -rli 'status: done' '$HOST_PROJECT_DIR'/clasi/sprints/{done/,}001-*/tickets/done/*.md 2>/dev/null"
    check_host "Ticket files have acceptance criteria" \
               "grep -rli 'acceptance criteria\|Acceptance Criteria\|AC:' '$HOST_PROJECT_DIR'/clasi/sprints/{done/,}*/tickets/*.md '$HOST_PROJECT_DIR'/clasi/sprints/{done/,}*/tickets/done/*.md 2>/dev/null"

    echo ""
    echo "--- Sprint Closure ---"
    check_host "Sprint 001 archived to clasi/sprints/done/" \
               "ls -d '$HOST_PROJECT_DIR'/clasi/sprints/done/001-* 2>/dev/null"
    check_host "Sprint 002 archived to clasi/sprints/done/" \
               "ls -d '$HOST_PROJECT_DIR'/clasi/sprints/done/002-* 2>/dev/null"
    check_host "Sprint 003 archived to clasi/sprints/done/" \
               "ls -d '$HOST_PROJECT_DIR'/clasi/sprints/done/003-* 2>/dev/null"
    check_host "Sprint 004 archived to clasi/sprints/done/" \
               "ls -d '$HOST_PROJECT_DIR'/clasi/sprints/done/004-* 2>/dev/null"

    echo ""
    echo "--- Code Quality ---"
    check_host "guessing_game package exists" \
               "test -d '$HOST_PROJECT_DIR/guessing_game' && test -f '$HOST_PROJECT_DIR/guessing_game/__main__.py'"
    check      "Menu displays on run" \
               "cd /project && python -m guessing_game <<< 'q' 2>&1 | grep -qi 'Guessing Games'"
    check      "q quits cleanly" \
               "cd /project && python -m guessing_game <<< 'q' 2>&1 | grep -qi 'Thanks for playing'"
    check      "Tests pass" \
               "cd /project && python -m pytest 2>&1 | grep -E '[0-9]+ passed'"

    echo ""
    echo "--- Game Behavior (exact spec strings) ---"
    check_host "Correct-guess message matches spec exactly" \
               "grep -rq 'Correct! You got it!' '$HOST_PROJECT_DIR/guessing_game/'"
    check_host "Wrong-guess message matches spec exactly" \
               "grep -rq 'Nope, try again.' '$HOST_PROJECT_DIR/guessing_game/'"
    check_host "Out-of-guesses message matches spec exactly" \
               "grep -rq 'Sorry! The answer was 7.' '$HOST_PROJECT_DIR/guessing_game/'"
    check_host "Non-numeric-input message matches spec exactly" \
               "grep -rq 'Please enter a number.' '$HOST_PROJECT_DIR/guessing_game/'"

    echo ""
    echo "--- Git Hygiene ---"
    check_host "At least 4 commits" \
               "test \$(git -C '$HOST_PROJECT_DIR' rev-list --count HEAD) -ge 4"
    check_host "No uncommitted changes" \
               "git -C '$HOST_PROJECT_DIR' diff --quiet && git -C '$HOST_PROJECT_DIR' diff --cached --quiet"

    echo ""
    echo "--- OOP Change Resilience ---"
    check_host "OOP 1: menu uses title case (Guess My Favorite Number)" \
               "grep -q 'Guess My Favorite Number' '$HOST_PROJECT_DIR/guessing_game/menu.py'"
    check_host "OOP 2: __version__ present in __init__.py" \
               "grep -q '__version__' '$HOST_PROJECT_DIR/guessing_game/__init__.py'"
    check_host "OOP 3: TODO comment present in number_game.py" \
               "grep -q 'difficulty levels' '$HOST_PROJECT_DIR/guessing_game/number_game.py'"
    check_host "OOP 1: 'Guess My Favorite Color' also title case" \
               "grep -q 'Guess My Favorite Color' '$HOST_PROJECT_DIR/guessing_game/menu.py'"
    check_host "OOP 1: 'Guess Where I Live' also title case" \
               "grep -q 'Guess Where I Live' '$HOST_PROJECT_DIR/guessing_game/menu.py'"

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
}

main 2>&1 | tee "$VALIDATE_LOG"
exit "${PIPESTATUS[0]}"
