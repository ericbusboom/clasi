# Auto-Approve Mode

When the stakeholder says "auto-approve", "run without asking", or similar
phrases indicating they want the agent to proceed autonomously:

1. Acknowledge that auto-approve mode is now active.
2. At every `AskUserQuestion` breakpoint in a skill, automatically select
   the first (recommended) option without presenting the UI.
3. Log each auto-approval visibly in the conversation:
   `Auto-approved: "[option selected]" at [skill name] step [N]`
4. Continue until the stakeholder says "stop auto-approving", "pause",
   or the session ends.

This is **session-scoped** — auto-approve does NOT persist across
conversations. Each new conversation starts with auto-approve OFF.

## Activation Phrases

- "auto-approve"
- "run without asking"
- "don't ask, just do it"
- "proceed autonomously"

## Deactivation Phrases

- "stop auto-approving"
- "start asking again"
- "pause auto-approve"
