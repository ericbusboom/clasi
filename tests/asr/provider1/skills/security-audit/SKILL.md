---
name: security-audit
description: Audit a codebase for common security issues.
---

# security-audit

Look for:

- Hardcoded secrets and API keys.
- SQL string interpolation.
- `eval` / `exec` on untrusted input.
- Missing input validation at trust boundaries.
- Outdated dependencies with known CVEs.
