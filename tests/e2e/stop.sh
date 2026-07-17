#!/bin/bash
# CLASI E2E — Stop and clean up the test environment
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTAINER_NAME="clasi-e2e"
IMAGE_NAME="clasi-e2e"
CANONICAL_DIR="$SCRIPT_DIR/e2e-project"
WIPE=0

for arg in "$@"; do
    case "$arg" in
        --wipe)
            WIPE=1
            ;;
        *)
            echo "ERROR: Unknown argument '$arg'." >&2
            echo "  Usage: ./stop.sh [--wipe]" >&2
            exit 1
            ;;
    esac
done

# --- Guarded wipe: refuse anything that isn't clearly the e2e project dir ---
guarded_wipe() {
    local dir="$1"
    case "$dir" in
        */e2e-project) ;;
        *)
            echo "ERROR: refusing to wipe '$dir' — path does not end in /e2e-project." >&2
            return 1
            ;;
    esac
    if [ "$dir" = "/" ] || [ "$dir" = "$HOME" ]; then
        echo "ERROR: refusing to wipe '$dir' — looks like / or \$HOME." >&2
        return 1
    fi
    # Portable mount-point check (no `mountpoint` binary on macOS): a
    # directory is a mount point iff df reports its own path as the mount
    # point of the filesystem it lives on.
    if [ "$(df -P "$dir" 2>/dev/null | tail -1 | awk '{print $NF}')" = "$dir" ]; then
        echo "ERROR: refusing to wipe '$dir' — it is a mount point." >&2
        return 1
    fi
    find "$dir" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
}

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Stopping container '$CONTAINER_NAME'..."
    docker stop "$CONTAINER_NAME" >/dev/null
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Removing container '$CONTAINER_NAME'..."
    docker rm "$CONTAINER_NAME" >/dev/null
fi

# --- Legacy sweep: remove the old named-volume artifact from prior harness
# versions. Safe no-op once nothing uses it. ---
docker volume rm clasi-data 2>/dev/null || true

if [ "$WIPE" -eq 1 ]; then
    if [ -e "$CANONICAL_DIR" ]; then
        HOST_PROJECT_DIR="$(cd -P "$CANONICAL_DIR" && pwd)"
        echo "=== --wipe: wiping contents of $HOST_PROJECT_DIR ==="
        guarded_wipe "$HOST_PROJECT_DIR"
    else
        echo "--wipe requested but $CANONICAL_DIR does not exist; nothing to wipe."
    fi
fi

echo "Done. Image '$IMAGE_NAME' is kept for reuse."
echo "  To remove the image: docker rmi $IMAGE_NAME"
