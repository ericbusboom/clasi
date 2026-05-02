# General-engineering provider

A first provider that ships generic engineering guidance — code
review, security audit, no-secrets and Python style. Its block
coexists with other providers' blocks in the same project via clasr's
named marker blocks.

The agent should:

- Run linters before committing.
- Prefer small focused commits over large ones.
- Read `SKILL.md` files under `skills/` for repeatable workflows.
