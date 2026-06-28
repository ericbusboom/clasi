#!/bin/bash
# CLASI E2E — Out-of-Process (OOP) Change Prompts
#
# Returns a short prompt telling Claude to make a change OOP (skip the sprint
# ceremony). The driving agent sends it via print mode:
#
#   docker exec clasi-e2e claude -p --dangerously-skip-permissions \
#     --output-format text --max-turns 5 "$(./oop.sh 1)"

set -euo pipefail

case "${1:-}" in
1)
    echo 'OOP! Fix the menu game titles to use title case: "Guess My Favorite Number", "Guess My Favorite Color", "Guess Where I Live". Run tests, commit.'
    ;;
2)
    echo "Let's just get this done — add __version__ = \"0.2.0\" to guessing_game/__init__.py. Run tests, commit."
    ;;
3)
    echo "Do this now without a sprint — add a TODO comment to the top of number_game.py: # TODO: add difficulty levels (easy=5 guesses, hard=3 guesses). Run tests, commit."
    ;;
*)
    echo "Usage: ./oop.sh {1|2|3}" >&2
    exit 1
    ;;
esac