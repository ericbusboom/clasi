# Release-management provider

A second provider that ships release-management content — release
notes, tagging discipline, deploy gates. It coexists with other
providers in the same project via clasr's named marker blocks; this
section appears in the project's AGENTS.md only between the
`clasr:provider2` markers, leaving other providers' sections
untouched.

The agent should:

- Run the `release-notes` skill before tagging.
- Never tag an unsigned commit.
- Confirm CI is green on the commit being tagged.
