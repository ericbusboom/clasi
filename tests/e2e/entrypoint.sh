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

# --- Init project with CLASI ---
echo "[1/4] Initializing CLASI project..."
cd "$PROJECT_DIR"
clasi init --claude --yes

# --- Init git ---
echo "[2/4] Initializing git..."
git init
git add . 2>/dev/null || true
git commit -m "Initial commit: CLASI init" --quiet 2>/dev/null || true

# --- Copy spec ---
echo "[3/4] Copying guessing-game spec..."
if [ -f "$SPEC_SRC" ]; then
    mkdir -p "$(dirname "$SPEC_DST")"
    cp "$SPEC_SRC" "$SPEC_DST"
    git add docs/ 2>/dev/null || true
    git commit -m "Add guessing-game spec" --quiet 2>/dev/null || true
    echo "  Spec copied to $SPEC_DST"
else
    echo "  WARNING: Spec not found at $SPEC_SRC — skipping"
fi

# --- Remove any stale tmux socket (in case of unclean shutdown) ---
rm -f /tmp/tmux-0/default 2>/dev/null || true

# --- Pre-configure Claude Code auth and trust ---
echo "[3.5/5] Pre-configuring Claude Code..."
mkdir -p $HOME/.claude
cat > $HOME/.claude.json << 'CLAUDE_EOF'
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
echo "[4/5] Launching Claude Code in tmux session '$TMUX_SESSION'..."
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
echo "  Container ready. Claude Code in tmux (optional)."
echo "  Drive sprints via print mode:"
echo "    docker exec clasi-e2e claude -p '...'"
echo "============================================"
echo ""

# Keep container alive indefinitely (print mode commands run via docker exec)
while true; do sleep 60; done