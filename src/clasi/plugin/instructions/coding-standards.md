---
name: coding-standards
description: Language-agnostic principles for error handling, dependencies, and naming
---

# Coding Standards

These principles apply to all code regardless of language. For
language-specific conventions, see `instructions/languages/`.

## Error Handling

- **Fail fast**: Raise exceptions at the point of failure rather than
  returning error codes or None.
- **Be specific**: Use the most precise error type available — not a
  generic catch-all.
- **Only catch what you handle**: Do not catch exceptions just to log and
  re-raise. Only catch when you can actually recover or add meaningful
  context.
- **Validate at boundaries**: Validate inputs at public function boundaries
  (user input, file I/O, external APIs). Internal functions can trust their
  callers.
- **No silent failures**: Never swallow errors without logging or
  re-raising.

## Dependency Management

- Declare all dependencies in the project manifest (`pyproject.toml`,
  `package.json`, etc.).
- Pin to minimum compatible versions, not exact versions.
- Minimize dependencies. Prefer the standard library when it's adequate.
- Never add a dependency for something trivially implementable.

## Naming

- Names should be descriptive. Avoid single-letter variables except in
  short comprehensions and lambdas.
- Avoid catch-all module names (`utils.py`, `helpers.py`, `misc.py`).
  Name modules after what they contain.
- Follow the language's idiomatic casing conventions (see language
  instructions).
