#!/bin/bash
# CLASI E2E — Start the test environment
# Builds the Docker image and launches a container with Claude Code in tmux,
# bind-mounted to a fresh, host-visible project directory. Uses OpenRouter
# as the API backend (ANTHROPIC_BASE_URL redirect).
#
# Order of responsibilities: flags -> prereq checks -> wheel build ->
# docker build -> probe/choose project dir -> container down -> wipe
# (unless --resume) -> env file -> docker run -> readiness wait.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE_NAME="clasi-e2e"
CONTAINER_NAME="clasi-e2e"
ENV_FILE=""
RESUME=0

CANONICAL_DIR="$SCRIPT_DIR/e2e-project"
FALLBACK_DIR="$HOME/.clasi/e2e-project"

E2E_MODEL="${E2E_MODEL:-anthropic/claude-opus-4.8}"
E2E_SMALL_MODEL="${E2E_SMALL_MODEL:-}"
CLASI_SOURCE="${CLASI_SOURCE:-}"

# --- Flags ---
for arg in "$@"; do
    case "$arg" in
        --resume)
            RESUME=1
            ;;
        *)
            echo "ERROR: Unknown argument '$arg'." >&2
            echo "  Usage: ./start.sh [--resume]" >&2
            exit 1
            ;;
    esac
done

cleanup() {
    if [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
        rm -f "$ENV_FILE"
    fi
}
trap cleanup EXIT

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

if [ -z "$CLASI_SOURCE" ] && ! command -v uv &>/dev/null; then
    echo "ERROR: uv is not installed or not in PATH."
    echo "  uv is required to build the local clasi wheel (default path)."
    echo "  Either install uv, or pin a released version instead:"
    echo "    CLASI_SOURCE=<tag> ./start.sh"
    exit 1
fi

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

# --- Bind-mount probe: verify host-side visibility, never trust the docker
# exit code alone (the exact OrbStack failure mode that broke
# start-container.py: docker reports success, but /project is VM-local and
# invisible on the host). ---
probe_bind() {
    local dir="$1" token="probe-$$-$RANDOM"
    mkdir -p "$dir"
    docker run --rm -v "$dir:/probe" --entrypoint sh "$IMAGE_NAME" \
        -c "echo $token > /probe/.bind-probe" >/dev/null 2>&1 || return 1
    grep -qs "$token" "$dir/.bind-probe" || return 1
    rm -f "$dir/.bind-probe"
}

# --- Local-wheel build (default path) ---
if [ -z "$CLASI_SOURCE" ]; then
    echo "=== Building local clasi wheel... ==="
    rm -f "$SCRIPT_DIR"/clasi-*.whl
    (cd "$REPO_ROOT" && uv build --wheel --out-dir "$SCRIPT_DIR")
    CLASI_SOURCE="local"
    echo ""
fi

# --- Build image ---
echo "=== Building Docker image '$IMAGE_NAME' (CLASI_SOURCE=$CLASI_SOURCE)... ==="
docker build --build-arg "CLASI_SOURCE=$CLASI_SOURCE" -t "$IMAGE_NAME" "$SCRIPT_DIR"
echo ""

if [ "$CLASI_SOURCE" = "local" ]; then
    rm -f "$SCRIPT_DIR"/clasi-*.whl
fi

# --- Probe/choose project dir ---
echo "=== Probing bind-mount host-visibility... ==="
PROJECT_DIR=""
if probe_bind "$CANONICAL_DIR"; then
    PROJECT_DIR="$CANONICAL_DIR"
    echo "  Bind mount OK at $CANONICAL_DIR"
else
    echo "  Canonical dir did not materialize a host-visible bind; falling back to $FALLBACK_DIR"
    mkdir -p "$FALLBACK_DIR"
    if ! probe_bind "$FALLBACK_DIR"; then
        echo "ERROR: bind-mount probe failed for both $CANONICAL_DIR and $FALLBACK_DIR." >&2
        echo "  Docker cannot reliably bind-mount host directories in this environment." >&2
        exit 1
    fi
    PROJECT_DIR="$FALLBACK_DIR"

    # Reconcile tests/e2e/e2e-project as a symlink to the fallback dir.
    if [ -L "$CANONICAL_DIR" ]; then
        rm -f "$CANONICAL_DIR"
    elif [ -e "$CANONICAL_DIR" ]; then
        if [ -d "$CANONICAL_DIR" ] && [ -z "$(find "$CANONICAL_DIR" -mindepth 1 -maxdepth 1)" ]; then
            rmdir "$CANONICAL_DIR"
        else
            echo "ERROR: $CANONICAL_DIR exists and is non-empty; refusing to replace it with a symlink to $FALLBACK_DIR." >&2
            echo "  Move or remove it manually, then re-run." >&2
            exit 1
        fi
    fi
    ln -s "$FALLBACK_DIR" "$CANONICAL_DIR"
    echo "  Symlinked $CANONICAL_DIR -> $FALLBACK_DIR"
fi

# Always resolve to a physical path before passing to docker -v.
HOST_PROJECT_DIR="$(cd -P "$PROJECT_DIR" && pwd)"

# --- Stop and remove any existing container ---
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Removing existing container '$CONTAINER_NAME'..."
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1
fi

# --- Wipe (unless resuming) ---
if [ "$RESUME" -eq 1 ]; then
    echo "=== --resume: skipping wipe of $HOST_PROJECT_DIR ==="
else
    echo "=== Wiping contents of $HOST_PROJECT_DIR ==="
    guarded_wipe "$HOST_PROJECT_DIR"
fi

# --- Write env file (safe for keys with special characters) ---
ENV_FILE="$(mktemp)"
{
    echo "ANTHROPIC_API_KEY=${OPENROUTER_API_KEY}"
    echo "ANTHROPIC_BASE_URL=https://openrouter.ai/api/v1"
    echo "ANTHROPIC_MODEL=${E2E_MODEL}"
    if [ -n "$E2E_SMALL_MODEL" ]; then
        echo "ANTHROPIC_SMALL_FAST_MODEL=${E2E_SMALL_MODEL}"
    fi
    echo "E2E_RESUME=${RESUME}"
} > "$ENV_FILE"

# --- Run ---
echo "=== Starting container '$CONTAINER_NAME'... ==="
docker run -d \
    --name "$CONTAINER_NAME" \
    --env-file "$ENV_FILE" \
    -v "${HOST_PROJECT_DIR}:/project" \
    "$IMAGE_NAME"

# Clean up env file now (trap also covers early-exit paths).
rm -f "$ENV_FILE"
ENV_FILE=""

# --- Wait for Claude to be ready ---
echo "Waiting for Claude Code to start..."
for i in $(seq 1 30); do
    if docker exec "$CONTAINER_NAME" tmux has-session -t claude 2>/dev/null; then
        echo ""
        echo "============================================"
        echo "  Ready! Drive sprints via print mode:"
        echo "    docker exec clasi-e2e claude -p '...'"
        echo "  Project dir: $HOST_PROJECT_DIR"
        echo "  Model: $E2E_MODEL"
        echo "============================================"
        exit 0
    fi
    sleep 1
done

echo "ERROR: Claude Code did not start within 30 seconds."
echo "Check logs: docker logs $CONTAINER_NAME"
exit 1
