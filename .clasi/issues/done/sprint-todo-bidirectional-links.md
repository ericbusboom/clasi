---
status: done
---

# Bidirectional links between sprints and the TODOs they implement

During the early (roadmap) phase of sprint planning — before the detail
phase — establish bidirectional references between each sprint and the
TODOs it implements:

- The `sprint.md` frontmatter should include a list of TODO references
  (the TODOs this sprint will implement).
- Each referenced TODO file's frontmatter should include a back-reference
  to the sprint that is implementing it.

This makes traceability explicit in both directions: from a sprint you
can see which TODOs justify it, and from a TODO you can see which sprint
will deliver it. Links should be created during the roadmap phase so the
relationships are in place before the detail phase begins.
