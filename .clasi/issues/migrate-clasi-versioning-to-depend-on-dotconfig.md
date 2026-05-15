---
status: pending
---

# Migrate clasi internal versioning to depend on dotconfig.versioning as a library

## Context

In the OOP change of 2026-05-15, we retired the `clasi version` CLI and pointed all user-facing prose at `dotconfig version bump`. However, `clasi/versioning.py` (~500 lines) remains in the codebase because `close_sprint` imports six functions from it for its in-process bump-and-tag step.

The two modules — `clasi/versioning.py` and `dotconfig/versioning.py` (at `/Users/eric/proj/code-projects/dotconfig/src/dotconfig/versioning.py`) — are clearly forks of each other. They share `_classify_token`, `parse_format`, `format_has_auto`, `build_version`, `build_tag_regex`, `compute_next_version`, `update_pyproject_version`, `update_package_json_version`, `update_version_file`, `create_version_tag`, `_get_existing_tags`, `load_version_format`, and `load_version_sync` — same semantics, sometimes-different signatures.

The fork is now a maintenance hazard: any fix in one will silently diverge from the other.

## Goal

Make clasi depend on dotconfig as a library, and reimplement clasi's internal versioning needs on top of `dotconfig.versioning`. Retire `clasi/versioning.py` or shrink it to a thin clasi-specific shim.

## Constraints

- **`close_sprint` must keep working.** Three call sites in [clasi/tools/artifact_tools.py](clasi/tools/artifact_tools.py) (around lines 889-895, 1198-1213, 2006-2007) currently call `compute_next_version`, `detect_version_file`, `update_version_file`, `create_version_tag`, `load_version_trigger`, `should_version`. They feed into the close-sprint orchestration JSON return, which other tooling reads.
- **The MCP hot-reload list at [clasi/mcp_server.py:126](clasi/mcp_server.py) references `clasi.versioning`.** If the module is removed, drop the entry.
- **`tests/unit/test_versioning.py`** (~31 patches against `clasi.versioning.*`) needs to go with the module or be rewritten against `dotconfig.versioning`.

## Surface differences to reconcile

These functions exist in `clasi/versioning.py` and **not** in `dotconfig.versioning`:

- `load_version_trigger(project_root)` — reads `version_trigger` from `.clasi/config.yaml`. Values: `always`, `manual`, `sprint_close`, etc.
- `should_version(trigger, context)` — decides whether a given trigger + context combination should bump.
- `load_version_source(project_root)` — reads `version_source` path from settings.
- `detect_version_file(project_root) -> (Path, str) | None` — auto-discovers the canonical version file (pyproject.toml, package.json, etc.).
- `read_current_version(project_root)` — reads the current version from the detected source file.
- `sync_version(version, project_root)` — fan-out copy to all sync targets in settings.

Dotconfig has equivalents named differently and reading from `config/dotconfig.yaml` (different file, different format):

- `read_dotconfig_version(config_dir)` ↔ `read_current_version`
- `write_dotconfig_version(config_dir, version)` (none exact)
- `load_version_format(config_dir)` (shared name, but reads dotconfig.yaml)
- `seed_version_from_sources(project_root)` (no clasi equivalent)

**Key design question:** Which config file wins? Two options:

1. **dotconfig.yaml wins.** Clasi's `.clasi/config.yaml` versioning section becomes deprecated. Projects must use `config/dotconfig.yaml` for versioning settings. `should_version` / `load_version_trigger` either move to dotconfig (it grows triggers) or get retired (no one uses them?).

2. **clasi.yaml stays for clasi-specific triggers, dotconfig for the rest.** Clasi keeps `load_version_trigger` and `should_version` as a thin shim, but delegates `compute_next_version`, `update_version_file`, `create_version_tag`, etc. to `dotconfig.versioning`.

Option 2 is the lower-risk migration. Option 1 is cleaner long-term but requires changes to dotconfig.

## Approach (option 2, recommended)

1. **Add `dotconfig` as a runtime dependency** of clasi in `pyproject.toml`. Pin to a known-compatible version.
2. **Reduce `clasi/versioning.py` to ~50 lines** that re-export from `dotconfig.versioning` plus keep clasi-specific bits:
   ```python
   from dotconfig.versioning import (
       compute_next_version,
       create_version_tag,
       update_pyproject_version,
       update_package_json_version,
       update_version_file,
   )
   # clasi-specific:
   def load_version_trigger(project_root=None): ...
   def should_version(trigger, context): ...
   def detect_version_file(project_root): ...
   def read_current_version(project_root=None): ...
   def sync_version(version, project_root=None): ...
   def bump_version(major=0, tag=False): ...  # adapter
   ```
3. **Bridge config locations.** Either pass `config_dir=` explicitly when calling dotconfig functions, or extend dotconfig to fall back to `.clasi/config.yaml` when `config/dotconfig.yaml` is absent.
4. **Update tests.** `tests/unit/test_versioning.py` keeps testing the clasi-specific functions; the shared-function tests either go away or move to dotconfig's test suite.
5. **Update MCP hot-reload list** in `clasi/mcp_server.py:126` if the module shrinks significantly.

## Out of scope (for this issue)

- Removing `clasi.versioning` entirely. Even after the migration, `close_sprint`'s bridge logic needs a home.
- Changing `close_sprint`'s in-process bump semantics to a `subprocess.run(["dotconfig", "version", "bump"])` shellout. That's a different design decision; if pursued, it's its own issue.
- Retiring `docs/versioning.md`. It's currently flagged as a porting reference and can be retired or rewritten once this issue lands.

## Files to read for context

- [clasi/versioning.py](clasi/versioning.py) — current implementation, full 513 lines
- [/Users/eric/proj/code-projects/dotconfig/src/dotconfig/versioning.py](/Users/eric/proj/code-projects/dotconfig/src/dotconfig/versioning.py) — the library to depend on
- [clasi/tools/artifact_tools.py:36-43](clasi/tools/artifact_tools.py) — the imports that must keep working
- [clasi/tools/artifact_tools.py:889-895, 1198-1213, 2006-2007](clasi/tools/artifact_tools.py) — the three call sites
- [clasi/mcp_server.py:126](clasi/mcp_server.py) — hot-reload list
- [tests/unit/test_versioning.py](tests/unit/test_versioning.py) — test surface
- [docs/versioning.md](docs/versioning.md) — porting reference
- [pyproject.toml](pyproject.toml) — where the dependency goes

## Verification

- `close_sprint` succeeds end-to-end and produces the same JSON return shape it does today (version + tag fields populated).
- `dotconfig version bump` and `clasi`-internal bump (from close_sprint) produce the same version string for the same git state.
- Full test suite passes.
- `clasi/versioning.py` LOC reduced by >80% (most code now lives in dotconfig).
- No regression in the format scheme — `0.YYYYMMDD.R+` with the same revision-numbering semantics.
