#!/usr/bin/env bash
# run_sprint.sh — Run Claude Code to plan and execute a sprint on the test project.
#
# Usage:
#   ./tests/e2e/run_sprint.sh [project-dir] [num-sprints]
#
# If no project directory is given, uses tests/e2e/project/.
# If no sprint count is given, defaults to 4 (matching the guessing-game spec).
#
# Each sprint is a separate claude invocation that plans and executes
# the next sprint, then closes it before moving on.
#
# Prerequisites:
#   - Project must already be initialized (run run_project_init.sh first)
#   - `claude` CLI available on PATH
#   - ANTHROPIC_API_KEY set (or Claude Code otherwise authenticated)
#   - CLASI MCP server must be configured in the project's .mcp.json

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="${1:-$SCRIPT_DIR/project}"
NUM_SPRINTS="${2:-4}"

# Clean and re-initialize the project directory
rm -rf "$PROJECT"
python "$SCRIPT_DIR/setup_project.py" "$PROJECT"

cd "$PROJECT"

for i in $(seq 1 "$NUM_SPRINTS"); do
  echo ""
  echo "=== E2E: Sprint $i of $NUM_SPRINTS ==="
  echo ""

  claude -p \
    --dangerously-skip-permissions \
    --output-format text \
    --max-budget-usd 10.00 \
    "Plan and execute the next sprint based on the project specification and any pending TODOs. Do not ask for confirmation — proceed directly through planning, ticketing, and execution. Close the sprints when all tickets are done and move on to the next sprints, until the project is completed."

  echo ""
  echo "=== E2E: Sprint $i complete ==="
done

echo ""
echo "=== E2E: All $NUM_SPRINTS sprints complete ==="
echo "Check $PROJECT/docs/clasi/sprints/ for sprint artifacts."
