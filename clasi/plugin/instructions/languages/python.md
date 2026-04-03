---
name: python
description: Python-specific conventions for naming, imports, logging, style, type hints, testing, and idioms
---

# Python Language Instructions

These conventions supplement `instructions/coding-standards.md` with
Python-specific guidance.

## Virtual Environments and `uv`

Use `uv` as the package manager and virtual environment tool.

```bash
# Create a new project
uv init my-project
cd my-project

# Add dependencies
uv add requests pydantic

# Add dev dependencies
uv add --dev pytest pytest-cov ruff

# Run commands in the venv
uv run pytest
uv run python -m mypackage

# Sync after pulling changes
uv sync
```

- Always use `uv run` to execute commands — never activate the venv
  manually or use `pip install` directly.
- Lock files (`uv.lock`) should be committed to version control.
- Use `uv add` and `uv remove` to manage dependencies — never edit
  `pyproject.toml` dependency lists by hand.

## `pyproject.toml` Configuration

All project metadata belongs in `pyproject.toml`. Do not use `setup.py`,
`setup.cfg`, or `requirements.txt`.

```toml
[project]
name = "my-package"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "requests>=2.28",
    "pydantic>=2.0",
]

[project.scripts]
my-cli = "my_package.cli:main"

[dependency-groups]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.4",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"

[tool.ruff]
line-length = 88
target-version = "py311"
```

- Pin to minimum compatible versions (`>=`), not exact versions (`==`).
- Use `[dependency-groups]` for dev tools, not extras.
- Keep `[tool.*]` configuration in `pyproject.toml` rather than separate
  config files.

## Naming Conventions

- **Modules**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions and variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_leading_underscore`

## Import Ordering

Follow PEP 8 import ordering with blank lines between groups:

```python
# 1. Standard library
import os
import sys
from pathlib import Path

# 2. Third-party packages
import requests
from pydantic import BaseModel

# 3. Local/project imports
from .link_agents import get_repo_root
```

- Use absolute imports for top-level modules.
- Use relative imports within a package only when referring to siblings.
- Never use wildcard imports (`from module import *`).
- Sort imports alphabetically within each group.

## Logging

- Use the standard library `logging` module, not `print()` for operational
  messages.
- Get a logger per module: `logger = logging.getLogger(__name__)`
- Use appropriate levels:
  - `DEBUG` — Detailed diagnostic info (variable values, flow tracing)
  - `INFO` — Normal operation milestones (started, completed, loaded N items)
  - `WARNING` — Something unexpected but recoverable
  - `ERROR` — Something failed but the program continues
  - `CRITICAL` — Program cannot continue
- Keep `print()` only for user-facing CLI output.

## Code Style

- Follow PEP 8.
- Maximum line length: 88 characters (Black/Ruff default).
- Prefer f-strings over `.format()` or `%` formatting.
- Prefer `pathlib.Path` over `os.path`.
- Prefer list/dict/set comprehensions over `map()`/`filter()` for simple
  transformations.
- Keep functions short — if a function exceeds 30 lines, consider splitting.
- One return type per function. Avoid functions that sometimes return a value
  and sometimes return None unless the signature explicitly says so.

## Type Hints

Add type hints to all public function signatures. Use modern syntax.

```python
from __future__ import annotations

from pathlib import Path


def load_items(path: Path, limit: int | None = None) -> list[dict[str, str]]:
    """Load items from a JSON file."""
    ...


def find_by_name(items: list[dict[str, str]], name: str) -> dict[str, str] | None:
    """Find an item by name, or None if not found."""
    ...
```

- Use `from __future__ import annotations` for `X | Y` union syntax.
- Use `Path` not `str` for file system paths.
- Use `list[X]`, `dict[K, V]`, `set[X]` — not `List`, `Dict`, `Set` from
  `typing`.
- Internal helper functions benefit from type hints but do not require them.

## pytest Patterns and Fixtures

### Test file layout

```
tests/
├── unit/                    # One module in isolation
│   ├── test_module_a.py
│   └── test_module_b.py
├── system/                  # Multiple modules together
│   └── test_feature_x.py
├── dev/                     # Throwaway dev scripts
└── conftest.py              # Shared fixtures
```

- One test file per source module. Name it `test_<module>.py`.
- Place in `tests/unit/` or `tests/system/` — never directly in `tests/`.
- Group related tests into classes: `class TestFeatureName:`.
- Test function names describe the behavior: `test_raises_on_missing_file`.

### Fixtures

```python
@pytest.fixture
def sample_config(tmp_path):
    """Create a sample config file for testing."""
    config = tmp_path / "config.json"
    config.write_text('{"key": "value"}')
    return config


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    """Set up a temporary working directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
```

- Use `tmp_path` for file system operations — never write to the real file
  system in tests.
- Use `monkeypatch.chdir` when code depends on `Path.cwd()`.
- Keep fixtures minimal — create only what the test needs.
- Prefer function-scoped fixtures (the default) over session or module scope.

### Assertions

```python
# Good — specific assertions
assert result["status"] == "done"
assert len(items) == 3
assert "error" in str(exc.value)

# Good — pytest.raises for exceptions
with pytest.raises(ValueError, match="not found"):
    load_config(Path("missing.json"))

# Bad — bare assert with no message context
assert result  # What was expected?
```

### Parametrize for variants

```python
@pytest.mark.parametrize("input_val,expected", [
    ("hello world", "hello-world"),
    ("Hello World!", "hello-world"),
    ("  spaces  ", "spaces"),
])
def test_slugify(input_val, expected):
    assert slugify(input_val) == expected
```

## Python Idioms

### Prefer pathlib over os.path

```python
# Good
from pathlib import Path
config = Path("config") / "settings.json"
content = config.read_text(encoding="utf-8")

# Bad
import os
config = os.path.join("config", "settings.json")
with open(config) as f:
    content = f.read()
```

### Use context managers for resources

```python
# Good
with open(path, encoding="utf-8") as f:
    data = json.load(f)

# Or even better for simple reads
data = json.loads(path.read_text(encoding="utf-8"))
```

### Prefer comprehensions for simple transforms

```python
# Good
names = [item["name"] for item in items if item["active"]]

# Avoid for complex logic — use a loop instead
results = []
for item in items:
    if item["active"] and validate(item):
        result = transform(item)
        results.append(result)
```

### Guard clauses over deep nesting

```python
# Good — early returns
def process(item):
    if not item:
        return None
    if item["status"] == "skip":
        return None
    return do_work(item)

# Bad — deep nesting
def process(item):
    if item:
        if item["status"] != "skip":
            return do_work(item)
    return None
```

### String formatting

```python
# Good — f-strings
message = f"Found {count} items in {path}"

# Acceptable — when building from parts
parts = [f"{k}={v}" for k, v in params.items()]
query = "&".join(parts)

# Bad — old-style formatting
message = "Found %d items in %s" % (count, path)
message = "Found {} items in {}".format(count, path)
```
