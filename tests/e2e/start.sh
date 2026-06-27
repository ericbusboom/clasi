#!/bin/bash
# CLASI E2E — Start the test environment
# Builds the Docker image and launches a container with Claude Code in tmux.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE_NAME="clasi-e2e"
CONTAINER_NAME="clasi-e2e"

# --- Prerequisites ---
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "ERROR: ANTHROPIC_API_KEY is not set."
    echo "  export ANTHROPIC_API_KEY=sk-ant-..."
    exit 1
fi

if ! command -v docker &>/dev/null; then
    echo "ERROR: docker is not installed or not in PATH."
    exit 1
fi

# --- Stop and remove any existing container ---
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Removing existing container '$CONTAINER_NAME'..."
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1
fi

# --- Build ---
echo "=== Building Docker image '$IMAGE_NAME'... ==="
docker build -t "$IMAGE_NAME" "$SCRIPT_DIR"
echo ""

# --- Run ---
echo "=== Starting container '$CONTAINER_NAME'... ==="
docker run -d \
    --name "$CONTAINER_NAME" \
    -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
    "$IMAGE_NAME"

# --- Wait for Claude to be ready ---
echo "Waiting for Claude Code to start..."
for i in $(seq 1 30); do
    if docker exec "$CONTAINER_NAME" tmux has-session -t claude 2>/dev/null; then
        echo ""
        echo "============================================"
        echo "  Ready! Connect with:"
        echo "    ./connect.sh"
        echo "============================================"
        exit 0
    fi
    sleep 1
done

echo "ERROR: Claude Code did not start within 30 seconds."
echo "Check logs: docker logs $CONTAINER_NAME"
exit 1