---
id: 005-003
title: "Predicate registry \u2014 @predicate decorator, lookup, and listing"
status: done
sprint: '005'
use-cases:
- SUC-002
- SUC-005
depends-on:
- 005-001
issues: []
---

## Description

Create `clasi/state_machine/registry.py` with the global predicate registry
and the `@predicate("name")` decorator. The registry is the single source of
truth for name → callable mappings; all engine lookups go through it.

## Acceptance Criteria

- [x] `@predicate("is_foo")` decorator registers the decorated function under
  the given name in the global registry.
- [x] `get_predicate(name: str) -> Callable` returns the function, or raises
  `UnknownPredicateError` if not found.
- [x] `list_predicates() -> list[str]` returns all registered names in
  sorted order.
- [x] Registering the same name twice raises `DuplicatePredicateError`
  (not a silent overwrite).
- [x] The decorator returns the original function unchanged (does not wrap it).
- [x] The registry is module-level state (a dict), initialized once at import.
  It is intentionally write-once: after all modules import, no new predicates
  are added at runtime.
- [x] A `clear_registry()` function exists for use in tests only (not exported
  from `__init__.py`).
- [x] Unit tests in `tests/unit/test_state_machine/test_registry.py` cover:
  register, lookup, list, duplicate error, unknown name error, and
  `clear_registry` in teardown.

## Implementation Plan

### Approach

Module-level `_REGISTRY: dict[str, Callable] = {}`. The decorator:

```python
def predicate(name: str):
    def decorator(fn):
        if name in _REGISTRY:
            raise DuplicatePredicateError(name)
        _REGISTRY[name] = fn
        return fn
    return decorator
```

`get_predicate` raises `UnknownPredicateError` on miss. `list_predicates`
returns `sorted(_REGISTRY.keys())`.

### Files to create

- `clasi/state_machine/registry.py`
- `tests/unit/test_state_machine/test_registry.py`

### Testing plan

Each test that registers predicates must call `clear_registry()` in teardown
(or use a pytest fixture). Test: register a function, look it up, call it.
Register same name twice → exception. Look up unknown name → exception.
`list_predicates()` returns sorted list.

### Documentation updates

Docstring on `@predicate` should explain the registration side effect and
warn that `clear_registry()` is test-only.
