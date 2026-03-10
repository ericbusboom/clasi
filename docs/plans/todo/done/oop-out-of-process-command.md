---
status: pending
---

# /oop — out-of-process command

Add a `/oop` slash command that means "out of process." When invoked, the
agent skips all SE process ceremony (no sprint, no tickets, no gates) and
just fixes the thing right now.

This is for quick, targeted changes where the full process would be
overkill — typos, small bug fixes, config tweaks, one-line changes.
The agent should act like a normal coding assistant: read the code,
make the change, run the tests, done.
