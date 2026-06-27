#!/bin/bash
# CLASI E2E — Connect to the running Claude Code tmux session
set -euo pipefail

CONTAINER_NAME="clasi-e2e"
TMUX_SESSION="claude"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: Container '$CONTAINER_NAME' is not running."
    echo "  Run ./start.sh first."
    exit 1
fi

if ! docker exec "$CONTAINER_NAME" tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    echo "ERROR: tmux session '$TMUX_SESSION' not found in container."
    echo "  The container may have crashed. Check: docker logs $CONTAINER_NAME"
    exit 1
fi

echo "Connecting to Claude Code in container '$CONTAINER_NAME'..."
echo "  Use Ctrl+B then D to detach (Claude keeps running)."
echo "  Use Ctrl+C to cancel Claude's current operation."
echo "  Type /exit or Ctrl+D to exit Claude and stop the container."
echo ""

exec docker exec -it "$CONTAINER_NAME" tmux attach -t "$TMUX_SESSION"