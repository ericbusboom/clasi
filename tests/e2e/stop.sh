#!/bin/bash
# CLASI E2E — Stop and clean up the test environment
set -euo pipefail

CONTAINER_NAME="clasi-e2e"
IMAGE_NAME="clasi-e2e"

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Stopping container '$CONTAINER_NAME'..."
    docker stop "$CONTAINER_NAME" >/dev/null
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Removing container '$CONTAINER_NAME'..."
    docker rm "$CONTAINER_NAME" >/dev/null
fi

echo "Done. Image '$IMAGE_NAME' is kept for reuse."
echo "  To remove the image: docker rmi $IMAGE_NAME"