#!/bin/bash
# CLASI E2E — Start the test environment
# Builds the Docker image and launches a container with Claude Code in tmux,
# bind-mounted to a fresh, host-visible project directory. Auth backend is
# selectable via E2E_AUTH:
#   - subscription (default): bind-mounts a throwaway copy of the host's
#     Claude Code OAuth credentials so claude -p authenticates as the
#     logged-in subscription instead of an API key.
#   - openrouter: API key over OpenRouter (ANTHROPIC_BASE_URL redirect).
#     Currently a dead path — the CLI rejects every model through the
#     redirect, see
#     clasi/issues/later/claude-cli-rejects-models-through-openrouter-redirect-in-e2e.md.
#     Kept available behind the explicit --auth flag for whoever revisits
#     that issue, but no longer the silent default. See --auth flag below.
#
# Order of responsibilities: flags -> prereq checks -> wheel build ->
# docker build -> probe/choose project dir -> container down -> wipe
# (unless --resume) -> env/credentials staging -> docker run -> readiness wait.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE_NAME="clasi-e2e"
CONTAINER_NAME="clasi-e2e"
ENV_FILE=""
# Stable (not mktemp -d) so the mounted file survives after start.sh exits —
# the container keeps running detached and needs the bind source to persist.
# Cleaned up by stop.sh, not by this script's exit trap.
CREDS_STAGE_DIR="$SCRIPT_DIR/.creds-stage"
RESUME=0

CANONICAL_DIR="$SCRIPT_DIR/e2e-project"
FALLBACK_DIR="$HOME/.clasi/e2e-project"

E2E_SMALL_MODEL="${E2E_SMALL_MODEL:-}"
CLASI_SOURCE="${CLASI_SOURCE:-}"
E2E_AUTH="${E2E_AUTH:-subscription}"
# Model ID format differs by backend: OpenRouter wants a provider-prefixed
# string ("anthropic/claude-opus-4.8"); direct subscription auth wants the
# bare Anthropic model ID ("claude-opus-4-8") — a prefixed string against
# api.anthropic.com fails with "model may not exist or you may not have
# access to it". Pick the default AFTER E2E_AUTH is resolved (see below);
# E2E_MODEL, if the caller sets it explicitly, always wins over either
# default.

# --- Flags ---
for arg in "$@"; do
    case "$arg" in
        --resume)
            RESUME=1
            ;;
        --auth=*)
            E2E_AUTH="${arg#--auth=}"
            ;;
        *)
            echo "ERROR: Unknown argument '$arg'." >&2
            echo "  Usage: ./start.sh [--resume] [--auth=openrouter|subscription]" >&2
            exit 1
            ;;
    esac
done

case "$E2E_AUTH" in
    openrouter|subscription) ;;
    *)
        echo "ERROR: --auth must be 'openrouter' or 'subscription' (got '$E2E_AUTH')." >&2
        exit 1
        ;;
esac

if [ "$E2E_AUTH" = "openrouter" ]; then
    echo "WARNING: --auth=openrouter is a known-dead path — the CLI rejects" >&2
    echo "  every model through the OpenRouter base-URL redirect. See" >&2
    echo "  clasi/issues/later/claude-cli-rejects-models-through-openrouter-redirect-in-e2e.md" >&2
    echo "  Proceeding anyway since it was explicitly requested." >&2
    E2E_MODEL="${E2E_MODEL:-anthropic/claude-opus-4.8}"
else
    E2E_MODEL="${E2E_MODEL:-claude-opus-4-8}"
fi

cleanup() {
    if [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
        rm -f "$ENV_FILE"
    fi
}
trap cleanup EXIT

# --- Prerequisites ---
# Credential source resolution for --auth=subscription (checked here, at
# prereq time, so we fail fast rather than mid-run):
#   1. macOS Keychain entry "Claude Code-credentials" — this is what
#      Claude Code on macOS actually keeps refreshed; the on-disk
#      ~/.claude/.credentials.json fallback file is NOT updated by the
#      macOS client and can sit expired for weeks while Keychain-backed
#      sessions work fine. Confirmed live: a copy of the stale on-disk
#      file authenticated but then failed with "Not logged in" (expired
#      access token, no refresh attempted by headless `claude -p`);
#      swapping in the Keychain copy fixed it immediately.
#   2. ~/.claude/.credentials.json — used when Keychain is unavailable
#      (non-macOS hosts, where this file IS kept current).
# CREDS_SOURCE_CMD is a shell command that prints the credentials JSON to
# stdout; staged into CREDS_STAGE_DIR further down, once, right before
# docker run (as close to container start as practical, since a Keychain
# access token can itself expire between resolution here and use).
CREDS_SOURCE_CMD=""
if [ "$E2E_AUTH" = "subscription" ]; then
    if command -v security &>/dev/null && \
       security find-generic-password -s "Claude Code-credentials" -w >/dev/null 2>&1; then
        CREDS_SOURCE_CMD='security find-generic-password -s "Claude Code-credentials" -w'
    elif [ -f "$HOME/.claude/.credentials.json" ]; then
        CREDS_SOURCE_CMD="cat \"$HOME/.claude/.credentials.json\""
    else
        echo "ERROR: --auth=subscription found no usable Claude Code credentials." >&2
        echo "  Checked macOS Keychain (\"Claude Code-credentials\") and" >&2
        echo "  $HOME/.claude/.credentials.json. Log in with 'claude' interactively" >&2
        echo "  on this host first." >&2
        exit 1
    fi
fi

if [ "$E2E_AUTH" = "openrouter" ] && [ -z "${OPENROUTER_API_KEY:-}" ]; then
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
    if [ "$E2E_AUTH" = "openrouter" ]; then
        echo "ANTHROPIC_API_KEY=${OPENROUTER_API_KEY}"
        echo "ANTHROPIC_BASE_URL=https://openrouter.ai/api/v1"
    fi
    echo "ANTHROPIC_MODEL=${E2E_MODEL}"
    if [ -n "$E2E_SMALL_MODEL" ]; then
        echo "ANTHROPIC_SMALL_FAST_MODEL=${E2E_SMALL_MODEL}"
    fi
    echo "E2E_RESUME=${RESUME}"
    echo "E2E_AUTH=${E2E_AUTH}"
} > "$ENV_FILE"

# --- Stage a throwaway credentials copy for subscription auth ---
# Never bind-mount the host's live ~/.claude directly: the container must
# not be able to write back into the real credential store. We resolve
# CREDS_SOURCE_CMD (Keychain or the on-disk fallback file, decided above)
# into a scratch dir under $SCRIPT_DIR (gitignored), mount that read-only.
# This dir must outlive start.sh (the container runs detached) — stop.sh
# removes it, not this script. Staged as late as practical (right before
# docker run) since a Keychain-sourced access token can itself expire
# between an earlier resolution and actual use.
DOCKER_RUN_MOUNTS=(-v "${HOST_PROJECT_DIR}:/project")
if [ "$E2E_AUTH" = "subscription" ]; then
    rm -rf "$CREDS_STAGE_DIR"
    mkdir -p "$CREDS_STAGE_DIR"
    eval "$CREDS_SOURCE_CMD" > "$CREDS_STAGE_DIR/.credentials.json"
    chmod 700 "$CREDS_STAGE_DIR"
    chmod 600 "$CREDS_STAGE_DIR/.credentials.json"
    DOCKER_RUN_MOUNTS+=(-v "${CREDS_STAGE_DIR}/.credentials.json:/home/agent/.claude/.credentials.json:ro")
    echo "=== Staged read-only copy of subscription credentials ==="
    echo "  (kept at $CREDS_STAGE_DIR for the container's lifetime; ./stop.sh removes it)"
fi

# --- Run ---
echo "=== Starting container '$CONTAINER_NAME'... ==="
docker run -d \
    --name "$CONTAINER_NAME" \
    --env-file "$ENV_FILE" \
    "${DOCKER_RUN_MOUNTS[@]}" \
    "$IMAGE_NAME"

# Clean up env file now (trap also covers early-exit paths).
rm -f "$ENV_FILE"
ENV_FILE=""

# --- Wait for Claude to be ready ---
echo "Waiting for Claude Code to start..."
TMUX_READY=0
for i in $(seq 1 30); do
    if docker exec "$CONTAINER_NAME" tmux has-session -t claude 2>/dev/null; then
        TMUX_READY=1
        break
    fi
    sleep 1
done

if [ "$TMUX_READY" -ne 1 ]; then
    echo "ERROR: Claude Code did not start within 30 seconds." >&2
    echo "Check logs: docker logs $CONTAINER_NAME" >&2
    exit 1
fi

# --- Preflight: prove the auth path and clasi install actually work,
# before handing the tester a session that looks ready but silently can't
# do anything (the openrouter model-gate rejection is exactly this failure
# mode). Aborts loudly on any failure — see module 1 in sprint.md. Output
# from both probes lands in a minimal per-run directory under
# .e2e-runs/; ticket 002 owns the full run-id/version/digest scheme and
# may extend or supersede this directory. ---
echo "=== Running preflight probe... ==="
RUN_ID="$(date +%Y%m%d-%H%M%S)-$$"
RUN_DIR="$HOST_PROJECT_DIR/.e2e-runs/$RUN_ID"
mkdir -p "$RUN_DIR"
PREFLIGHT_LOG="$RUN_DIR/preflight.txt"

CLAUDE_PREFLIGHT_OUTPUT=""
if ! CLAUDE_PREFLIGHT_OUTPUT="$(docker exec "$CONTAINER_NAME" claude -p --max-turns 1 "Reply READY" 2>&1)"; then
    {
        echo "=== claude -p --max-turns 1 \"Reply READY\" (FAILED, non-zero exit) ==="
        echo "$CLAUDE_PREFLIGHT_OUTPUT"
    } >> "$PREFLIGHT_LOG"
    echo "ERROR: preflight probe 'claude -p --max-turns 1 \"Reply READY\"' failed (non-zero exit)." >&2
    echo "  Auth: $E2E_AUTH, model: $E2E_MODEL. Output logged to $PREFLIGHT_LOG:" >&2
    echo "$CLAUDE_PREFLIGHT_OUTPUT" >&2
    exit 1
fi
{
    echo "=== claude -p --max-turns 1 \"Reply READY\" ==="
    echo "$CLAUDE_PREFLIGHT_OUTPUT"
} >> "$PREFLIGHT_LOG"

if ! printf '%s' "$CLAUDE_PREFLIGHT_OUTPUT" | grep -qi "ready"; then
    echo "ERROR: preflight probe 'claude -p' exited 0 but its output doesn't" >&2
    echo "  look like a completed 'READY' reply. Auth: $E2E_AUTH, model: $E2E_MODEL." >&2
    echo "  Output logged to $PREFLIGHT_LOG:" >&2
    echo "$CLAUDE_PREFLIGHT_OUTPUT" >&2
    exit 1
fi

CLASI_PREFLIGHT_OUTPUT=""
if ! CLASI_PREFLIGHT_OUTPUT="$(docker exec "$CONTAINER_NAME" clasi --version 2>&1)"; then
    {
        echo "=== clasi --version (FAILED, non-zero exit) ==="
        echo "$CLASI_PREFLIGHT_OUTPUT"
    } >> "$PREFLIGHT_LOG"
    echo "ERROR: preflight probe 'clasi --version' failed (non-zero exit)." >&2
    echo "  Output logged to $PREFLIGHT_LOG:" >&2
    echo "$CLASI_PREFLIGHT_OUTPUT" >&2
    exit 1
fi
{
    echo "=== clasi --version ==="
    echo "$CLASI_PREFLIGHT_OUTPUT"
} >> "$PREFLIGHT_LOG"

echo "  Preflight OK. Output: $PREFLIGHT_LOG"

echo ""
echo "============================================"
echo "  Ready! Drive sprints via print mode:"
echo "    docker exec clasi-e2e claude -p '...'"
echo "  Project dir: $HOST_PROJECT_DIR"
echo "  Model: $E2E_MODEL"
echo "  Auth: $E2E_AUTH"
echo "  Run dir: $RUN_DIR"
echo "============================================"
exit 0
