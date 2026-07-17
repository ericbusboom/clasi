#!/bin/bash
# CLASI E2E Container Entrypoint
# Initializes the project and launches Claude Code in a tmux session.
set -euo pipefail

PROJECT_DIR="/project"
SPEC_SRC="/spec/guessing-game-spec.md"
SPEC_DST="$PROJECT_DIR/docs/guessing-game-spec.md"
TMUX_SESSION="claude"

echo "=== CLASI E2E Environment ==="
echo ""

cd "$PROJECT_DIR"

# --- Determine fresh vs resume ---
RESUMING=0
if [ "${E2E_RESUME:-0}" = "1" ] && [ -d "$PROJECT_DIR/.clasi" ] && [ -d "$PROJECT_DIR/.git" ]; then
    RESUMING=1
fi

if [ "$RESUMING" -eq 1 ]; then
    echo "[1/5] Resuming existing project (E2E_RESUME=1, .clasi + .git present)..."
else
    # Fail loudly rather than silently re-initializing over stale state.
    if [ -n "$(find "$PROJECT_DIR" -mindepth 1 -maxdepth 1 2>/dev/null)" ]; then
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
