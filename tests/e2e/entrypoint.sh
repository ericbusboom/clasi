#!/bin/bash
# CLASI E2E Container Entrypoint
# Initializes the project and launches Claude Code in a tmux session.
set -euo pipefail

PROJECT_DIR="/project"
SPEC_SRC="/spec/guessing-game-spec.md"
SPEC_DST="$PROJECT_DIR/docs/guessing-game-spec.md"
TMUX_SESSION="claude"

# --- Harness-owned top-level entries in $PROJECT_DIR ------------------------
# These are created by the harness itself (this script and start.sh) before
# the fresh-vs-existing check below runs, and must NOT be mistaken for
# genuine prior project state left by 'clasi init' or the subject agent.
# This is the ONE place this list lives — the emptiness check below reads
# it rather than hardcoding names, so a future harness file only needs to
# be added here to stay invisible to the guard. Deliberately an explicit
# allowlist, not "ignore all dotfiles": genuine project state such as
# .clasi/, .claude/, .agents/, and .git/ must still trip the guard below.
HARNESS_OWNED_ENTRIES=(".e2e-coverage" ".e2e-runs" ".gitignore")

echo "=== CLASI E2E Environment ==="
echo ""

cd "$PROJECT_DIR"

# --- Coverage output dir + gitignore (ticket 032/007) ----------------------
# COVERAGE_PROCESS_START/COVERAGE_FILE (set container-wide in the
# Dockerfile) write parallel-mode `.coverage.*` files into
# /project/.e2e-coverage/ for every `clasi` CLI call and the long-lived
# `clasi mcp` server. This must happen BEFORE step [1] below: `clasi init`
# is itself a coverage-measured CLI invocation, so its own .coverage.*
# file can already exist by the time step [2]'s "Initial commit: CLASI
# init" runs. Gitignoring first — unlike .e2e-runs/, which is appended to
# .gitignore from the HOST side by start.sh, safely after that first
# commit already happened — keeps these out of the SUBJECT's own git
# history from the very first commit, since that ordering trick isn't
# available here (this script IS the thing making that first commit).
mkdir -p "$PROJECT_DIR/.e2e-coverage"
if [ ! -f "$PROJECT_DIR/.gitignore" ] || ! grep -qxF '.e2e-coverage/' "$PROJECT_DIR/.gitignore"; then
    echo '.e2e-coverage/' >> "$PROJECT_DIR/.gitignore"
fi

# --- Determine fresh vs resume ---
RESUMING=0
if [ "${E2E_RESUME:-0}" = "1" ] && [ -d "$PROJECT_DIR/.clasi" ] && [ -d "$PROJECT_DIR/.git" ]; then
    RESUMING=1
fi

if [ "$RESUMING" -eq 1 ]; then
    echo "[1/5] Resuming existing project (E2E_RESUME=1, .clasi + .git present)..."
else
    # Fail loudly rather than silently re-initializing over stale state.
    # Ignore harness-owned entries (HARNESS_OWNED_ENTRIES above) — those
    # are created by the harness itself, not evidence of a prior run.
    FIND_IGNORE_HARNESS=()
    for owned in "${HARNESS_OWNED_ENTRIES[@]}"; do
        FIND_IGNORE_HARNESS+=(! -name "$owned")
    done
    if [ -n "$(find "$PROJECT_DIR" -mindepth 1 -maxdepth 1 "${FIND_IGNORE_HARNESS[@]}" 2>/dev/null)" ]; then
        echo "ERROR: $PROJECT_DIR is non-empty and E2E_RESUME is not set." >&2
        echo "  Refusing to run 'clasi init' over existing state." >&2
        echo "  Use ./start.sh --resume to continue a prior run, or ./start.sh" >&2
        echo "  (fresh, which wipes the project dir) to start over." >&2
        exit 1
    fi

    echo "[1/5] Initializing CLASI project..."
    clasi init --claude --yes
fi

# --- Init git ---
if [ "$RESUMING" -eq 1 ]; then
    echo "[2/5] Skipping git init (resuming)."
else
    echo "[2/5] Initializing git..."
    git init -b master
    git add .
    git commit -m "Initial commit: CLASI init" --quiet
fi

# --- Copy spec ---
if [ "$RESUMING" -eq 1 ] && [ -f "$SPEC_DST" ]; then
    echo "[3/5] Spec already present (resuming) — skipping copy."
else
    echo "[3/5] Copying guessing-game spec..."
    if [ -f "$SPEC_SRC" ]; then
        mkdir -p "$(dirname "$SPEC_DST")"
        cp "$SPEC_SRC" "$SPEC_DST"
        git add docs/
        git commit -m "Add guessing-game spec" --quiet
        echo "  Spec copied to $SPEC_DST"
    else
        echo "  WARNING: Spec not found at $SPEC_SRC — skipping"
    fi
fi

# --- Remove any stale tmux socket (in case of unclean shutdown) ---
rm -f /tmp/tmux-0/default 2>/dev/null || true

# --- Pre-configure Claude Code auth and trust ---
echo "[4/5] Pre-configuring Claude Code..."
mkdir -p "$HOME/.claude"
cat > "$HOME/.claude.json" << 'CLAUDE_EOF'
{
  "projects": {
    "/project": {
      "hasTrustDialogAccepted": true
    }
  }
}
CLAUDE_EOF
echo "  Trust pre-accepted for /project"

# --- Launch Claude Code in tmux (keep-alive only — actual work uses print mode) ---
echo "[5/5] Launching Claude Code in tmux session '$TMUX_SESSION'..."
echo ""

# Start a detached tmux session with Claude Code (dangerous mode — we're in a throwaway container)
tmux new-session -d -s "$TMUX_SESSION" -x 140 -y 40 \
    bash -c "cd $PROJECT_DIR && exec claude --dangerously-skip-permissions" 2>/dev/null || true

# Handle the permissions bypass dialog if tmux started
sleep 3
tmux send-keys -t "$TMUX_SESSION" Down 2>/dev/null || true
sleep 0.3
tmux send-keys -t "$TMUX_SESSION" Enter 2>/dev/null || true
sleep 2

echo "============================================"
if [ "$RESUMING" -eq 1 ]; then
    echo "  Resuming. Container ready. Claude Code in tmux (optional)."
else
    echo "  Container ready. Claude Code in tmux (optional)."
fi
echo "  Drive sprints via print mode:"
echo "    docker exec clasi-e2e claude -p '...'"
echo "============================================"
echo ""

# Keep container alive indefinitely (print mode commands run via docker exec)
while true; do sleep 60; done
