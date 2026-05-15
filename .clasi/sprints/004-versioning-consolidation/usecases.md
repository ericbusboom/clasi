---
status: approved
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 004 Use Cases

## SUC-001: Add dotconfig as a runtime dependency
Parent: internal infrastructure

- **Actor**: Developer / package installer
- **Preconditions**: `clasi` is installed in a Python environment. `dotconfig` is not yet a declared runtime dependency.
- **Main Flow**:
  1. `pyproject.toml` declares `dotconfig>=0.20260507.2` in `[project.dependencies]`.
  2. Running `pip install clasi` or `uv sync` pulls in dotconfig automatically.
  3. `import dotconfig.versioning` succeeds in the same environment as `import clasi`.
- **Postconditions**: `dotconfig` is importable anywhere `clasi` is installed. The import is verified by the MCP server preflight check.
- **Acceptance Criteria**:
  - [ ] `pyproject.toml` lists `dotconfig>=0.20260507.2` in runtime dependencies.
  - [ ] `import dotconfig.versioning` succeeds in the clasi environment.
  - [ ] Existing tests still pass.

---

## SUC-002: `clasi/versioning.py` delegates shared logic to dotconfig
Parent: internal infrastructure

- **Actor**: `close_sprint` orchestration (via `artifact_tools.py`)
- **Preconditions**: dotconfig is installed (SUC-001 complete). `clasi/versioning.py` exists with ~500 lines of duplicated logic.
- **Main Flow**:
  1. `artifact_tools.py` calls `compute_next_version()`, `detect_version_file()`, `update_version_file()`, `create_version_tag()`, `load_version_trigger()`, `should_version()` from `clasi.versioning`.
  2. `clasi.versioning` re-exports `compute_next_version`, `update_version_file`, `create_version_tag`, `update_pyproject_version`, `update_package_json_version` directly from `dotconfig.versioning`.
  3. Clasi-specific helpers (`load_version_trigger`, `should_version`, `detect_version_file`, `read_current_version`, `sync_version`) remain in `clasi/versioning.py` as thin adapters over the dotconfig API or standalone (when no dotconfig equivalent exists).
  4. All call sites in `artifact_tools.py` continue to import from `clasi.versioning` unchanged.
- **Postconditions**: `clasi/versioning.py` shrinks to ~50 lines. Shared computation lives in dotconfig. No call site changes in `artifact_tools.py`.
- **Acceptance Criteria**:
  - [ ] `clasi/versioning.py` is reduced to under 100 lines.
  - [ ] All six functions imported in `artifact_tools.py` (lines 36-42) still import cleanly from `clasi.versioning`.
  - [ ] `close_sprint` produces the same JSON shape (`version`, `tag` fields) as before.
  - [ ] `dotconfig version bump` and clasi-internal close_sprint produce the same version string for the same git state.

---

## SUC-003: `.agents/.clasi-version` file removed; dotconfig is sole version authority
Parent: internal infrastructure

- **Actor**: Platform installer (`clasi codex install` / `clasi claude install`)
- **Preconditions**: Some client repos may have a stale `.agents/.clasi-version` file from an old installer.
- **Main Flow**:
  1. The installer no longer writes `.agents/.clasi-version`.
  2. Any existing `.agents/.clasi-version` file in a target repo is deleted opportunistically on the next installer run (already handled by `_markers.py` stale-cleanup logic).
  3. Documentation or prose that references `.agents/.clasi-version` is updated or removed.
- **Postconditions**: No new `.agents/.clasi-version` files are created. Version information is read from the canonical source (dotconfig / pyproject.toml).
- **Acceptance Criteria**:
  - [ ] No code path creates `.agents/.clasi-version`.
  - [ ] `_markers.py` stale-cleanup still removes `.agents/.clasi-version` if found.
  - [ ] Any docs referencing `.agents/.clasi-version` are corrected.

---

## SUC-004: Test suite covers the shim, not the deleted shared logic
Parent: internal infrastructure

- **Actor**: CI / developer running `pytest`
- **Preconditions**: `clasi/versioning.py` has been shrunk to a thin shim (SUC-002 complete).
- **Main Flow**:
  1. Tests that cover logic now in dotconfig are deleted or moved to dotconfig's test suite.
  2. Tests that cover clasi-specific functions (`load_version_trigger`, `should_version`, `detect_version_file`, `read_current_version`, `sync_version`) are retained and updated for any signature changes.
  3. `pytest` runs the full test suite; coverage threshold is met or adjusted.
- **Postconditions**: No test patches `clasi.versioning.*` for logic that now lives in dotconfig. Clasi-specific behavior is tested.
- **Acceptance Criteria**:
  - [ ] `tests/unit/test_versioning.py` no longer patches `clasi.versioning.compute_next_version`, `build_version`, `parse_format`, etc. (those tests belong to dotconfig).
  - [ ] Tests for `load_version_trigger` and `should_version` pass.
  - [ ] Full test suite passes with coverage at or above threshold.

---

## SUC-005: MCP hot-reload list reflects shim
Parent: internal infrastructure

- **Actor**: MCP server startup
- **Preconditions**: `clasi/versioning.py` has been shrunk (SUC-002 complete).
- **Main Flow**:
  1. `clasi/mcp_server.py` preflight check lists `clasi.versioning` if the module still exists.
  2. If the module is retained as a shim, the entry stays. If the module is removed entirely, the entry is dropped.
- **Postconditions**: MCP server startup completes without preflight errors. Hot-reload watches the correct set of modules.
- **Acceptance Criteria**:
  - [ ] MCP server starts without preflight import errors.
  - [ ] If `clasi.versioning` is retained as a shim, its entry in `mcp_server.py:126` is unchanged.
  - [ ] If `clasi.versioning` is removed, the entry is dropped and no import error occurs.
