---
date: 2026-02-11
sprint: 001
category: ignored-instruction
---

## What Happened

The stakeholder scolded the agent twice, and the agent failed to detect
either scolding:

1. **First scolding**: "why am I not getting the UI that I'm supposed to
   get?" — The agent treated this as a regular question and responded with
   an explanation and a follow-up question. No self-reflect triggered.

2. **Second scolding**: "obviously I want you to follow the process. If I
   didn't want you to follow the process, I gotta change the process." —
   The agent acknowledged the correction ("fair point") and adjusted
   behavior, but still did not trigger the self-reflect skill.

The stakeholder had to explicitly ask "Was I scolding you? Cause I think
that was a scolding" before the agent recognized the pattern and ran
self-reflect.

## What Should Have Happened

On the first message ("why am I not getting the UI..."), the agent should
have:

1. Recognized the process critique pattern from `scold-detection.md`:
   "why did you do X?" maps directly to "why am I not getting X?"
2. Acknowledged the correction immediately.
3. Run the self-reflect skill to produce a reflection document.
4. Then continued with the corrected approach.

## Root Cause

**Ignored instruction.** The scold-detection rules are clear and the
stakeholder's messages matched the documented patterns:

- "why am I not getting the UI that I'm supposed to get?" matches
  **process critique**: "why did you do X?", "that's not how it works"
- "obviously I want you to follow the process" matches **direct
  correction** and **frustration** signals.

The agent prioritized answering the question over checking whether the
message was a scolding. The scold-detection check should happen *before*
formulating a response, not after. It's a pre-processing step, not an
afterthought.

## Proposed Fix

Behavioral change: when processing any stakeholder message, check it
against the scold-detection signals *first*, before composing a response.
If a scolding is detected, the self-reflect skill takes priority over
answering the question. The reflection itself will capture the correction,
and the corrected approach follows from there.

This is ordering discipline, not a process gap — the rules exist and are
clear.
