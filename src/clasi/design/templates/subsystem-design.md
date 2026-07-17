<!--
SUBSYSTEM DESIGN DOCUMENT TEMPLATE

Place one copy of this file in each subsystem's subdirectory (e.g. DESIGN.md).
The root design document owns system-wide context, the subsystem map, and the
global conventions every subsystem is allowed to assume. Do NOT repeat that
material here — reference it.

Prompts in HTML comments are instructions for whoever (human or agent) fills
the section in. Delete each comment once its section is written. Keep prose
tight; the code carries the mechanism, this document carries what the code
cannot say about itself.

No frontmatter is required or written for this file. The doc's location
under its subsystem's own source directory is its identity — there is
nothing to backlink.
-->

# <Subsystem Name>

<!--
STATUS/OWNERSHIP HEADER — one line, keep it current.
Owner, last-reviewed date, and stability (stable | in-flux | deprecated).
An undated design doc that has silently gone stale is worse than no doc.
-->
**Owner:** <name> · **Last reviewed:** <YYYY-MM-DD> · **Status:** <stable | in-flux | deprecated>

---

## 1. Purpose

<!--
One paragraph. Answer three things:
- What this subsystem is.
- Why it is a subsystem — i.e. what seam in the design justifies drawing a
  boundary here rather than folding this into a neighbor. If you can't name the
  seam, the boundary may be wrong.
- What problem it owns that nothing else owns.
Do not describe HOW it works yet. This is the "why does this directory exist"
paragraph.
-->

## 2. Orientation

<!--
The page-length abstract. Target: a reader finishes this and either (a) has
enough context for their task and stops, or (b) knows exactly which later
section they need.
Describe how it works at the altitude needed to read the rest of the document —
the main pieces, the flow between them, the shape of the thing. No struct-level
or line-level detail; that belongs in Design.
Test before you move on: if section 4 (Design) just restates this at greater
length, one of the two sections is wrong. This is the map; Design is the terrain.
-->

## 3. Constraints and Invariants

<!--
The highest-value section. Write only what a competent reader CANNOT derive by
reading the code. The code already tells them what it does; it does not tell
them:
- Invariants that must always hold (and are not locally obvious).
- Things this subsystem deliberately does NOT do, and must not be "helpfully"
  extended to do.
- Traps: obvious-looking simplifications or edits that are actually wrong.
- Ordering, timing, or resource constraints imposed from outside.
Pair each item with the CONSEQUENCE of violating it — that is what stops a
well-intentioned edit from destroying it.

Format as a list. Each entry: the rule, then why / what breaks if ignored.

AGENT NOTE: treat every item here as a hard boundary on generated or modified
code. Do not relax, "improve past," or refactor away anything in this section
without explicit human sign-off. If a requested change conflicts with an
invariant here, stop and surface the conflict rather than resolving it silently.
-->

- **<Constraint>:** <what must hold> — <what breaks if it doesn't>
- **<Deliberate non-goal>:** <what this does not do> — <why extending it here is wrong>

## 4. Design

<!--
The real content. How it actually works.
Cover, as applicable:
- Key data structures and who owns them (memory ownership / lifetime).
- Control flow and the timing/lifecycle model for THIS subsystem (init, tick,
  teardown; interrupt vs. main-loop context; reentrancy).
- Concurrency: what runs where, what the locking / disable-interrupt discipline
  is, what state is shared.
- The decisions that shaped it AND their rationale. Rationale outranks mechanism
  here: the mechanism is in the code, the reason it is that way is not. When you
  chose A over an obvious B, say why B was rejected.
Prefer explaining the non-obvious over cataloguing the obvious.
-->

## 5. Interfaces

<!--
Keep this tight. Two halves:

Exposes — what this subsystem offers to others. The public surface: functions,
messages, shared state, events. For each, the contract (pre/postconditions,
timing, error behavior) that a caller must honor. Describe your OWN outputs in
full detail — this is the authoritative source for them.

Consumes — what this subsystem depends on from others. Describe these by
REFERENCE, not in detail: name the interface and why you use it, and point to
the owning subsystem's doc / the root subsystem map for specifics. Do not
re-document another subsystem's behavior here; that description will rot the
moment they change it.
-->

### Exposes
- **<interface>:** <contract — pre/post, timing, errors>

### Consumes
- **<interface> (from <subsystem>):** <why used> — see <link to that subsystem's doc / root map>

## 6. Open Questions / Known Limitations

<!--
The honest section. What is known-wrong, deferred, or uncertain but not yet
fixed. If it lives only in someone's head it will be rediscovered painfully;
put it here.
- Known bugs or shortcuts taken deliberately.
- Decisions made under uncertainty that may need revisiting.
- Questions the design does not yet answer.
Delete the section only if it is genuinely empty — an empty one is fine, a
missing one implies false confidence.
-->
