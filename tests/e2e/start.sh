#!/bin/bash
# CLASI E2E — Start the test environment
# Builds the Docker image and launches a container with Claude Code in tmux.
# Uses OpenRouter as the API backend (ANTHROPIC_BASE_URL redirect).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE_NAME="clasi-e2e"
CONTAINER_NAME="clasi-e2e"
VOLUME_NAME="clasi-data"
ENV_FILE="/tmp/clasi-e2e-env"

# --- Prerequisites ---
if [ -z "${OPENROUTER_API_KEY:-}" ]; then
    echo "ERROR: OPENROUTER_API_KEY is not set."
    echo "  export OPENROUTER_API_KEY=sk-or-..."
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

# --- Write env file (safe for keys with special characters) ---
cat > "$ENV_FILE" << EOF
ANTHROPIC_API_KEY=${OPENROUTER_API_KEY}
ANTHROPIC_BASE_URL=https://openrouter.ai/api/v1
EOF

# --- Run ---
echo "=== Starting container '$CONTAINER_NAME'... ==="
# Named volume for persistent project data (OrbStack can't bind-mount from /Volumes/Proj)
docker volume create "$VOLUME_NAME" >/dev/null 2>&1 || true

docker run -d \
    --name "$CONTAINER_NAME" \
    --env-file "$ENV_FILE" \
    -v "${VOLUME_NAME}:/project" \
    "$IMAGE_NAME"

# Clean up env file
rm -f "$ENV_FILE"

# --- Wait for Claude to be ready ---
echo "Waiting for Claude Code to start..."
for i in $(seq 1 30); do
    if docker exec "$CONTAINER_NAME" tmux has-session -t claude 2>/dev/null; then
        echo ""
        echo "============================================"
        echo "  Ready! Drive sprints via print mode:"
        echo "    docker exec clasi-e2e claude -p --model anthropic/claude-sonnet-4 '...'"
        echo "  Volume: $VOLUME_NAME"
        echo "============================================"
        exit 0
    fi
    sleep 1
done

echo "ERROR: Claude Code did not start within 30 seconds."
echo "Check logs: docker logs $CONTAINER_NAME"
exit 1