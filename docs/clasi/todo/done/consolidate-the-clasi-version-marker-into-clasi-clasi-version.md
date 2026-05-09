---
status: done
sprint: '015'
tickets:
- 015-020
---

# Consolidate the CLASI version marker into `.clasi/clasi-version`

## Context

When CLASI is installed into a target project, each platform installer (Claude, Codex, Copilot) currently drops a `.clasi-version` stamp file into *every* directory it owns:

- `<target>/.claude/.clasi-version`
- `<target>/.codex/.clasi-version`
- `<target>/.agents/.clasi-version`
- `<target>/.github/.clasi-version`

This produces 2–3 duplicate version files per install (Claude+Codex both stamp `.agents/`, so it's double-written), and the leading-dot filename inside an already-hidden directory is awkward to inspect.

The user wants a **single, consolidated marker** at `<target>/.clasi/clasi-version` — one file per installed project, no leading dot on the filename, and decoupled from any individual platform's directory.

This change applies only to *target* projects where CLASI gets installed; the layout of this source repo (`docs/`, `docs/clasi/`, `docs/design/`, `docs/versioning.md`) is **not** changing.

## Scope

In scope:
- Change `write_version_stamp` to write a single file at `<target>/.clasi/clasi-version`.
- Update each platform installer's call site so the stamp is written exactly once per `clasi install`, regardless of which platforms are selected.
- Update the docstring/echo language to reflect the new path.

Out of scope:
- Reading the marker (no code reads it; it's a write-only artifact).
- Uninstall cleanup of the marker (none exists today, and adding one isn't requested — note this in Verification so the user can confirm).
- Any moves under `docs/` in this source repo.

## Files to modify

- [clasi/platforms/_markers.py](clasi/platforms/_markers.py) — rewrite `write_version_stamp`.
- [clasi/platforms/claude.py:454-457](clasi/platforms/claude.py#L454-L457) — collapse two stamp calls into one.
- [clasi/platforms/codex.py:457-460](clasi/platforms/codex.py#L457-L460) — collapse two stamp calls into one.
- [clasi/platforms/copilot.py:458-461](clasi/platforms/copilot.py#L458-L461) — collapse two stamp calls into one.

## Implementation

### 1. `clasi/platforms/_markers.py`

Replace `write_version_stamp(target, subdir)` with a no-argument-beyond-target version:

```python
def write_version_stamp(target: Path) -> None:
    """Write the installed clasi version to <target>/.clasi/clasi-version.

    A single-line file (version + newline) so a reader can tell which
    clasi release populated this project. Called by every platform
    installer; the resulting file is shared, not platform-specific,
    so multiple invocations during a single `clasi install` simply
    overwrite with the same value.
    """
    dest = target / ".clasi" / "clasi-version"
    dest.parent.mkdir(parents=True, exist_ok=True)
    version = _current_version()
    dest.write_text(f"{version}\n", encoding="utf-8")
    click.echo(f"  Wrote: .clasi/clasi-version ({version})")
```

The signature change is acceptable because all four call sites are updated in this same change and the function is private to this package (`_markers` is underscore-prefixed; no external callers found via grep).

### 2. Platform installers

In each of `claude.py`, `codex.py`, `copilot.py`, replace the existing two-call block:

```python
from clasi.platforms._markers import write_version_stamp
click.echo("Version stamps:")
write_version_stamp(target, ".claude")     # or .codex / .github
write_version_stamp(target, ".agents")
click.echo()
```

with a single call:

```python
from clasi.platforms._markers import write_version_stamp
click.echo("Version stamp:")
write_version_stamp(target)
click.echo()
```

Re-stamping on a second platform install is harmless (same content). No coordination needed between platforms.

## Verification

Run the existing test suite — no test currently exercises `write_version_stamp` (verified via `grep -rn "write_version_stamp\|clasi-version" tests/`), so all tests should still pass:

```
uv run pytest
```

End-to-end check using a throwaway target directory:

```
mkdir -p /tmp/clasi-marker-check
cd /tmp/clasi-marker-check
clasi install --platform claude
ls -la .clasi/                  # expect: clasi-version
cat .clasi/clasi-version        # expect: <version>\n
ls .claude/.clasi-version 2>&1  # expect: not found
ls .agents/.clasi-version 2>&1  # expect: not found
```

Then re-run `clasi install --platform codex` in the same dir and confirm `.clasi/clasi-version` still has a single line with the same version (no duplication, no append).

## Notes for the user (worth confirming before merge)

- **Stale markers from prior installs.** Existing target projects will keep their old `.claude/.clasi-version`, `.codex/.clasi-version`, `.agents/.clasi-version`, `.github/.clasi-version` files until the next `clasi uninstall` (which doesn't currently remove them either). If you'd like, the implementation can opportunistically delete those old paths inside `write_version_stamp`. Not included by default — flag if you want it added.
- **Uninstall.** None of the three `uninstall()` paths currently delete the version stamp. That's pre-existing behavior; this change preserves it. Say the word if uninstall should now `rm .clasi/clasi-version` (and remove `.clasi/` if empty).
