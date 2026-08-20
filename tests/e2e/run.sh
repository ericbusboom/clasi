#!/bin/bash
# CLASI E2E — Drive one subject exchange, capturing it durably
#
# Wraps `docker exec clasi-e2e claude -p ...` so every subject exchange is
# captured into the current run's directory instead of living only in the
# tester's terminal (SUC-002 — a failed run today has no replayable
# record). Use this instead of raw `docker exec ... claude -p`; see
# AGENTS.md's "Launching subject sessions" section, which mandates it.
#
# Usage:
#   ./run.sh [--run-id <id>] --max-turns <N> <slug> "<prompt>"
#
# Writes .e2e-runs/<run-id>/<NN>-<slug>/{prompt.txt, output.jsonl,
# stderr.txt, exit-code, duration}. NN is a sequential 2-digit counter
# scoped to the run directory.
#
# Run-id resolution (the Run-ID Handoff Contract — see start.sh, which
# mints the id, and stop.sh/validate.sh, which resolve it the same way):
# --run-id, if given, wins; otherwise resolved from
# e2e-project/.e2e-runs/current. Unlike stop.sh/validate.sh, run.sh does
# NOT fall back to treating a bare positional as a run-id override — its
# two positionals are already <slug> and <prompt> — so pass --run-id
# explicitly if you need to target a run other than the current one.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTAINER_NAME="clasi-e2e"
CANONICAL_DIR="$SCRIPT_DIR/e2e-project"

RUN_ID_OVERRIDE=""
MAX_TURNS=""
POSITIONAL=()

usage() {
    echo "  Usage: ./run.sh [--run-id <id>] --max-turns <N> <slug> \"<prompt>\"" >&2
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
        --max-turns)
            if [ $# -lt 2 ]; then
                echo "ERROR: --max-turns requires a value." >&2
                usage
                exit 1
            fi
            MAX_TURNS="$2"
            shift 2
            ;;
        --*)
            echo "ERROR: Unknown flag '$1'." >&2
            usage
            exit 1
            ;;
        *)
            POSITIONAL+=("$1")
            shift
            ;;
    esac
done

if [ "${#POSITIONAL[@]}" -ne 2 ]; then
    echo "ERROR: expected exactly 2 positional arguments: <slug> <prompt> (got ${#POSITIONAL[@]})." >&2
    usage
    exit 1
fi
SLUG="${POSITIONAL[0]}"
PROMPT="${POSITIONAL[1]}"

case "$SLUG" in
    *[!A-Za-z0-9_-]*|"")
        echo "ERROR: <slug> must be non-empty and contain only letters, digits, '-', '_' (got '$SLUG')." >&2
        exit 1
        ;;
esac

case "$MAX_TURNS" in
    ''|*[!0-9]*)
        echo "ERROR: --max-turns <N> is required and must be a positive integer (got '$MAX_TURNS')." >&2
        usage
        exit 1
        ;;
esac

if [ ! -e "$CANONICAL_DIR" ]; then
    echo "ERROR: $CANONICAL_DIR does not exist; run ./start.sh first." >&2
    exit 1
fi
HOST_PROJECT_DIR="$(cd -P "$CANONICAL_DIR" && pwd)"

# --- Run-id resolution: explicit --run-id wins; otherwise
# .e2e-runs/current. Fail loudly rather than silently operating on the
# wrong or a nonexistent run directory. ---
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

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: container '$CONTAINER_NAME' is not running. Run ./start.sh first." >&2
    exit 1
fi

# --- Number this milestone within the run (NN, 2-digit, sequential).
# mkdir -p first: start.sh always creates RUN_DIR at mint time, but an
# explicit --run-id override isn't guaranteed to name an existing
# directory, and `find` on a missing dir would abort the script under
# `set -e`/pipefail rather than correctly reporting zero existing
# milestones. ---
mkdir -p "$RUN_DIR"
EXISTING_COUNT="$(find "$RUN_DIR" -mindepth 1 -maxdepth 1 -type d -name '[0-9][0-9]-*' 2>/dev/null | wc -l | tr -d ' ')"
NN="$(printf '%02d' "$((EXISTING_COUNT + 1))")"
MILESTONE_DIR="$RUN_DIR/${NN}-${SLUG}"
mkdir -p "$MILESTONE_DIR"

printf '%s' "$PROMPT" > "$MILESTONE_DIR/prompt.txt"

echo "=== run.sh: milestone $NN-$SLUG (run $RUN_ID, max-turns $MAX_TURNS) ==="

START_TS="$(date +%s)"
EXIT_CODE=0
docker exec "$CONTAINER_NAME" claude -p \
    --dangerously-skip-permissions --output-format stream-json --verbose \
    --max-turns "$MAX_TURNS" "$PROMPT" \
    > "$MILESTONE_DIR/output.jsonl" 2> "$MILESTONE_DIR/stderr.txt" || EXIT_CODE=$?
END_TS="$(date +%s)"
DURATION=$((END_TS - START_TS))

echo "$EXIT_CODE" > "$MILESTONE_DIR/exit-code"
echo "$DURATION" > "$MILESTONE_DIR/duration"

echo "  Output: $MILESTONE_DIR/output.jsonl"
echo "  Exit code: $EXIT_CODE  Duration: ${DURATION}s"

exit "$EXIT_CODE"
