#!/bin/bash
# CLASI E2E — Combine + report the real-app coverage collected during a run
# (ticket 032/007; SUC-006).
#
# Every `clasi` CLI invocation and `clasi mcp` server session inside the
# container writes a parallel-mode `.coverage.<host>.<pid>.<rand>` file into
# the bind-mounted project's `.e2e-coverage/` directory (see Dockerfile's
# COVERAGE_PROCESS_START/COVERAGE_FILE env and entrypoint.sh's directory
# setup). This script combines those raw files into one dataset and renders
# it — text, JSON, LCOV, and HTML — into this run's own directory. Like
# validate.sh, it only reads the bind-mounted project directly, so it works
# whether or not the container is still running.
#
# Usage:
#   ./coverage.sh [--run-id <id>]
#
# Run-id resolution: same contract as run.sh/validate.sh/stop.sh/report.sh
# (the Run-ID Handoff Contract) — explicit --run-id/positional wins;
# otherwise resolved from e2e-project/.e2e-runs/current. Fails loudly if
# neither resolves, rather than silently reporting on the wrong run.
#
# Uses tests/e2e/.coveragerc (NOT the repo root pyproject.toml's own
# [tool.coverage.run]) for both combine and report — see .coveragerc's own
# header for why: pyproject.toml's omit list deliberately excludes
# cli.py/hook_handlers.py/mcp_server.py for the unit gate, and coverage.py
# has no CLI override that clears a config file's own omit list at report
# time (verified empirically while building this harness). Reusing
# pyproject.toml here would silently re-hide exactly the three files this
# report exists to show. pyproject.toml's own [tool.coverage.paths] is
# still added (ticket 032/007's acceptance criteria ask for it there
# specifically) but this script does not depend on it.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CANONICAL_DIR="$SCRIPT_DIR/e2e-project"
COVERAGERC="$SCRIPT_DIR/.coveragerc"

RUN_ID_OVERRIDE=""

usage() {
    echo "  Usage: ./coverage.sh [--run-id <id>]" >&2
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

if [ ! -f "$COVERAGERC" ]; then
    echo "ERROR: $COVERAGERC not found." >&2
    exit 1
fi

if [ ! -e "$CANONICAL_DIR" ]; then
    echo "ERROR: $CANONICAL_DIR does not exist; run ./start.sh first." >&2
    exit 1
fi
HOST_PROJECT_DIR="$(cd -P "$CANONICAL_DIR" && pwd)"

# --- Run-id resolution: explicit --run-id/positional wins; otherwise
# .e2e-runs/current. Same contract as run.sh/validate.sh/stop.sh/report.sh.
# Fail loudly rather than silently operating on the wrong or a nonexistent
# run directory. (Reused verbatim from the other scripts — no shared lib
# file exists in this directory, so each script carries its own copy, per
# existing convention.) ---
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

RAW_COVERAGE_DIR="$HOST_PROJECT_DIR/.e2e-coverage"
OUT_DIR="$RUN_DIR/coverage"
mkdir -p "$OUT_DIR"

if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv is not installed or not in PATH (needed to run this repo's own 'coverage' tool from its .venv)." >&2
    exit 1
fi

echo "=== coverage.sh: run $RUN_ID ==="
echo "  Raw data dir: $RAW_COVERAGE_DIR"

RAW_FILES=()
if [ -d "$RAW_COVERAGE_DIR" ]; then
    while IFS= read -r f; do
        [ -n "$f" ] && RAW_FILES+=("$f")
    done < <(find "$RAW_COVERAGE_DIR" -maxdepth 1 -type f -name '.coverage.*' 2>/dev/null | sort)
fi

echo "  Raw .coverage.* files found: ${#RAW_FILES[@]}"
if [ "${#RAW_FILES[@]}" -eq 0 ]; then
    echo "ERROR: no .coverage.* files found under $RAW_COVERAGE_DIR." >&2
    echo "  Nothing to combine. Either no clasi CLI call / clasi mcp session has" >&2
    echo "  happened in this run yet, or COVERAGE_PROCESS_START/COVERAGE_FILE" >&2
    echo "  (Dockerfile ENV) aren't reaching the container's processes — check" >&2
    echo "  'docker exec clasi-e2e env | grep COVERAGE' if this is unexpected." >&2
    exit 1
fi
for f in "${RAW_FILES[@]}"; do
    echo "    - $(basename "$f")"
done

COMBINED_DATA_FILE="$OUT_DIR/.coverage"
rm -f "$OUT_DIR"/.coverage*

echo ""
echo "=== Combining ==="
(
    cd "$REPO_ROOT"
    COVERAGE_FILE="$COMBINED_DATA_FILE" uv run coverage combine \
        --rcfile="$COVERAGERC" --keep "$RAW_COVERAGE_DIR"
)

echo ""
echo "=== Text report ==="
REPORT_TXT="$OUT_DIR/report.txt"
(
    cd "$REPO_ROOT"
    COVERAGE_FILE="$COMBINED_DATA_FILE" uv run coverage report \
        --rcfile="$COVERAGERC" | tee "$REPORT_TXT"
)

echo ""
echo "=== Machine-readable output ==="
(
    cd "$REPO_ROOT"
    COVERAGE_FILE="$COMBINED_DATA_FILE" uv run coverage json \
        --rcfile="$COVERAGERC" -o "$OUT_DIR/coverage.json" >/dev/null
    echo "  JSON: $OUT_DIR/coverage.json"
    COVERAGE_FILE="$COMBINED_DATA_FILE" uv run coverage lcov \
        --rcfile="$COVERAGERC" -o "$OUT_DIR/coverage.lcov" >/dev/null
    echo "  LCOV: $OUT_DIR/coverage.lcov"
    COVERAGE_FILE="$COMBINED_DATA_FILE" uv run coverage html \
        --rcfile="$COVERAGERC" -d "$OUT_DIR/html" >/dev/null
    echo "  HTML: $OUT_DIR/html/index.html"
)

echo ""
echo "=== Entry-point check (cli.py / hook_handlers.py / mcp_server.py) ==="
if grep -qE 'clasi/(cli|hook_handlers|mcp_server)\.py' "$REPORT_TXT"; then
    echo "  Present in the report (not omitted, as intended — see .coveragerc):"
    grep -E 'clasi/(cli|hook_handlers|mcp_server)\.py' "$REPORT_TXT" | sed 's/^/    /'
else
    echo "  WARNING: none of cli.py/hook_handlers.py/mcp_server.py appear in the" >&2
    echo "  combined report. Either no CLI/MCP-server invocation happened in this" >&2
    echo "  run, or something upstream of this script didn't measure them." >&2
fi

echo ""
echo "Done. $OUT_DIR/report.txt (+ coverage.json, coverage.lcov, html/index.html)"
