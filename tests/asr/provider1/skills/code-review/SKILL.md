---
name: code-review
description: Review a pull request for correctness, style, and tests.
---

# code-review

Walk the diff. For each changed file:

1. Check the public API for breaking changes.
2. Check tests cover the new behavior.
3. Flag dead code, unused imports, and TODOs.
4. Confirm commit message references the ticket or issue.
