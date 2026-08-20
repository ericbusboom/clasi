#!/bin/bash
# CLASI E2E — Stop and clean up the test environment
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTAINER_NAME="clasi-e2e"
IMAGE_NAME="clasi-e2e"
CANONICAL_DIR="$SCRIPT_DIR/e2e-project"
CREDS_STAGE_DIR="$SCRIPT_DIR/.creds-stage"
WIPE=0
RUN_ID_OVERRIDE=""

usage() {
    echo "  Usage: ./stop.sh [--wipe] [--run-id <id>]" >&2
}

while [ $# -gt 0 ]; do
    case "$1" in
        --wipe)
            WIPE=1
            shift
            ;;
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

# --- Run-id resolution: explicit --run-id/positional wins; otherwise
# .e2e-runs/current. Same contract as run.sh/validate.sh. Fail loudly
# (returns 1 to its caller) rather than silently operating on the wrong or
# a nonexistent run directory — but unlike run.sh/validate.sh, a failure
# here must NOT abort this whole script: it only means the capture step
# below is skipped. Teardown (container + creds-stage removal) always
# proceeds regardless — see the ticket-002 note on `teardown()` below. ---
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

# --- Unconditional teardown: stop/remove the container and delete staged
# credentials. Registered on EXIT (below) so it always runs — even if the
# capture step fails, errors under `set -e`, or no run id ever resolves —
# matching start.sh's own cleanup() trap pattern. This is what makes
# stop.sh usable in exactly the case it's needed most: an aborted start.sh
# that never minted a run id (ticket 002). Every step here is defensive
# against docker itself erroring (daemon down, etc.) — `|| true` on the
# docker calls, so one failure can't skip the credential removal that
# follows it; that removal is a plain filesystem op with no docker
# dependency at all. Idempotent: safe to call more than once (each step
# checks state before acting), so calling it explicitly below — to keep
# the container/creds messages ahead of the final "Done" line, matching
# the known-good message order — is harmless; the EXIT trap re-running it
# at actual process exit just finds nothing left to do. ---
teardown() {
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Stopping container '$CONTAINER_NAME'..."
        docker stop "$CONTAINER_NAME" >/dev/null || true
    fi
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Removing container '$CONTAINER_NAME'..."
        docker rm "$CONTAINER_NAME" >/dev/null || true
    fi
    # --- Legacy sweep: remove the old named-volume artifact from prior
    # harness versions. Safe no-op once nothing uses it. ---
    docker volume rm clasi-data 2>/dev/null || true
    if [ -d "$CREDS_STAGE_DIR" ]; then
        echo "Removing staged credentials at $CREDS_STAGE_DIR..."
        rm -rf "$CREDS_STAGE_DIR"
    fi
}
trap teardown EXIT

HOST_PROJECT_DIR=""
if [ -e "$CANONICAL_DIR" ]; then
    HOST_PROJECT_DIR="$(cd -P "$CANONICAL_DIR" && pwd)"
fi

# --- Capture container logs and the subject's session directory into the
# run directory BEFORE teardown below removes the container — the
# container and its filesystem are gone once that runs, and this is the
# harness's only chance to preserve them (SUC-002). Best-effort only: if
# there's no container, nothing to capture (no-op). If a container exists
# but no run id resolves (or $CANONICAL_DIR itself doesn't exist), capture
# is skipped with a clear message — it does NOT abort the script, so
# teardown below still runs unconditionally either way. ---
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    if [ -z "$HOST_PROJECT_DIR" ]; then
        echo "WARNING: container '$CONTAINER_NAME' exists but $CANONICAL_DIR does not." >&2
        echo "  Cannot resolve a run directory to capture into — skipping capture." >&2
        echo "  Container/credential teardown still proceeds." >&2
    elif RUN_ID="$(resolve_run_id "$RUN_ID_OVERRIDE" "$HOST_PROJECT_DIR")"; then
        RUN_DIR="$HOST_PROJECT_DIR/.e2e-runs/$RUN_ID"
        mkdir -p "$RUN_DIR"

        echo "=== Capturing container logs and session directory into $RUN_DIR ==="
        if docker logs "$CONTAINER_NAME" > "$RUN_DIR/container.log" 2>&1; then
            echo "  Container log captured: $RUN_DIR/container.log"
        else
            echo "WARNING: 'docker logs $CONTAINER_NAME' failed; container.log may be incomplete." >&2
        fi

        rm -rf "$RUN_DIR/claude-projects"
        if docker cp "$CONTAINER_NAME:/home/agent/.claude/projects" "$RUN_DIR/claude-projects" >/dev/null 2>&1; then
            echo "  Session directory captured: $RUN_DIR/claude-projects"
        else
            echo "WARNING: 'docker cp' of ~/.claude/projects failed (no sessions captured yet? not fatal)." >&2
        fi
    else
        echo "WARNING: could not resolve a run id — no --run-id/positional given and" >&2
        echo "  $HOST_PROJECT_DIR/.e2e-runs/current does not exist or is empty." >&2
        echo "  Skipping capture: container.log and claude-projects will NOT be saved." >&2
        echo "  Pass --run-id <id> explicitly, or fix .e2e-runs/current, to capture next time." >&2
        echo "  Container/credential teardown still proceeds." >&2
    fi
fi

teardown

if [ "$WIPE" -eq 1 ]; then
    if [ -n "$HOST_PROJECT_DIR" ]; then
        echo "=== --wipe: wiping contents of $HOST_PROJECT_DIR ==="
        guarded_wipe "$HOST_PROJECT_DIR"
    else
        echo "--wipe requested but $CANONICAL_DIR does not exist; nothing to wipe."
    fi
fi

echo "Done. Image '$IMAGE_NAME' is kept for reuse."
echo "  To remove the image: docker rmi $IMAGE_NAME"
