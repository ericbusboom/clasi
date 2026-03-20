# Guessing Game CLI — Project Specification

## Overview

A Python CLI application with three simple guessing games. The user
selects a game from a menu, plays it (3 guesses max), then returns to
the menu.

## Technology

- Python 3.10+
- No external dependencies (stdlib only)
- Single entry point: `python -m guessing_game`
- Text-based interface (print/input)

## Features

### Main Menu

When the program starts, display:

```
=== Guessing Games ===
1. Guess my favorite number
2. Guess my favorite color
3. Guess where I live
q. Quit

Choose a game:
```

The user enters 1, 2, 3, or q. Invalid input shows "Invalid choice"
and re-displays the menu.

### Game 1: Guess My Favorite Number

The secret number is 7 (hardcoded).

```
=== Guess My Favorite Number ===
You have 3 guesses.

Guess 1: _
```

- If correct: "Correct! You got it!" → return to menu
- If wrong: "Nope, try again." → next guess
- After 3 wrong: "Sorry! The answer was 7." → return to menu
- Non-numeric input: "Please enter a number." (doesn't count as a guess)

### Game 2: Guess My Favorite Color

The secret color is "blue" (hardcoded, case-insensitive).

```
=== Guess My Favorite Color ===
You have 3 guesses.

Guess 1: _
```

- If correct (case-insensitive): "Correct! You got it!" → return to menu
- If wrong: "Nope, try again." → next guess
- After 3 wrong: "Sorry! The answer was blue." → return to menu

### Game 3: Guess Where I Live

The secret city is "Paris" (hardcoded, case-insensitive).

```
=== Guess Where I Live ===
You have 3 guesses.

Guess 1: _
```

- If correct (case-insensitive): "Correct! You got it!" → return to menu
- If wrong: "Nope, try again." → next guess
- After 3 wrong: "Sorry! The answer was Paris." → return to menu

### Quit

Entering "q" at the menu prints "Thanks for playing!" and exits.

## Sprint Plan

This project should be implemented in 4 sprints:

1. **Sprint 001: Project structure and menu** — Create the package
   structure (`guessing_game/`), the `__main__.py` entry point, and
   the main menu loop. Menu displays choices and handles input but
   games print "Coming soon!" and return to menu.

2. **Sprint 002: Number guessing game** — Implement game 1 (guess the
   number). Add tests.

3. **Sprint 003: Color guessing game** — Implement game 2 (guess the
   color). Add tests.

4. **Sprint 004: City guessing game** — Implement game 3 (guess the
   city). Add tests.

## Acceptance Criteria

- [ ] `python -m guessing_game` starts the menu
- [ ] Each game allows exactly 3 guesses
- [ ] Correct guess shows success and returns to menu
- [ ] 3 wrong guesses shows the answer and returns to menu
- [ ] "q" at menu quits gracefully
- [ ] Each game has unit tests
- [ ] All tests pass
