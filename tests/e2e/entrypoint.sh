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
git add .
git commit -m "Initial commit: CLASI init" --quiet

# --- Copy spec ---
echo "[3/4] Copying guessing-game spec..."
if [ -f "$SPEC_SRC" ]; then
    mkdir -p "$(dirname "$SPEC_DST")"
    cp "$SPEC_SRC" "$SPEC_DST"
    git add docs/
    git commit -m "Add guessing-game spec" --quiet
    echo "  Spec copied to $SPEC_DST"
else
    echo "  WARNING: Spec not found at $SPEC_SRC — skipping"
fi

# --- Remove any stale tmux socket (in case of unclean shutdown) ---
rm -f /tmp/tmux-0/default 2>/dev/null || true

# --- Launch Claude Code in tmux ---
echo "[4/4] Launching Claude Code in tmux session '$TMUX_SESSION'..."
echo ""

# Start a detached tmux session with Claude Code
tmux new-session -d -s "$TMUX_SESSION" -x 140 -y 40 \
    bash -c "cd $PROJECT_DIR && exec claude"

# Give Claude a moment to start
sleep 2

echo "============================================"
echo "  Claude Code is running in tmux."
echo ""
echo "  From the host, connect with:"
echo "    ./connect.sh"
echo ""
echo "  Or directly:"
echo "    docker exec -it clasi-e2e tmux attach -t $TMUX_SESSION"
echo "============================================"
echo ""

# Keep container alive — just tail the tmux session status
while tmux has-session -t "$TMUX_SESSION" 2>/dev/null; do
    sleep 5
done

echo "tmux session ended. Container shutting down."