---
status: done
sprint: '014'
tickets:
- 014-001
---

# clasr — cross-platform agent-config renderer (sub-tool of clasi)

Add a `clasr` CLI alongside `clasi` in the **same package**. `pip install clasi` installs both `clasi` and `clasr` entry points. They share a codebase; logical separation only. We may split into a separate package later, but not now.

`clasr` renders a source `asr/` directory into per-platform agent-config installs. CLASI itself becomes a `clasr` consumer.

## Packaging

- One `pyproject.toml`, two console_scripts:
  - `clasi = clasi.cli:main`  (existing)
  - `clasr = clasr.cli:main`  (new)
- Top-level packages: `clasi/` and `clasr/`. `clasi` may import from `clasr` (CLASI is a `clasr` consumer). `clasr` does **not** import from `clasi`.
- No second distribution. No second `pyproject.toml`. Single `pip install clasi` installs both CLIs.

## What `clasr` is

A generic transformer + installer. Input: a source directory called `asr/` (no leading dot — it lives inside another package's installed location, e.g. `curik/package_data/asr/`, not at a project's working dir). Output: rendered files for each requested platform (Claude Code, Codex, Copilot, more later), with symlinks where formats match and rendered files where they don't.

CLI shape:

```
clasr install --source <path-to-asr> --provider <name> --claude --copilot [--codex] [--copy]
clasr uninstall --provider <name> --claude
clasr --instructions
```

`--provider <name>` is the consumer's identifier (e.g. `clasi`, `curik`). It namespaces marker blocks and manifest files so multiple `clasr`-driven tools can coexist in the same repo (multi-tenant by design).

`clasr --instructions` prints agent-targeted help: how an agent (or human-with-agent) should structure an `asr/` source directory so `clasr` can install it. The text is **not inlined** in Python source — it lives as a Markdown file in the package (e.g. `clasr/instructions.md`) shipped via `package_data`/`importlib.resources`, and `cli.py` reads and prints it. Same pattern applies to `SCHEMA.md` and any other long-form docs the CLI surfaces.

## Source `asr/` layout

```
asr/
  AGENTS.md                    ← marker-block content for AGENTS.md / CLAUDE.md
  skills/<n>/SKILL.md          ← canonical, identical format across all targets
  agents/<n>.md                ← canonical agent body, frontmatter is a union
  rules/<n>.md                 ← canonical rule body, frontmatter is a union
  claude/                      ← Claude-only files (settings.json, settings.local.json,
                                 commands/, hooks, anything Claude-specific)
  codex/                       ← Codex-only files (config.toml fragments, etc.)
  copilot/                     ← Copilot-only files (.vscode/mcp.json fragment, etc.)
```

Per-platform subdirs under `asr/` hold platform-private content the consumer wants installed but that has no cross-platform equivalent. `clasr` copies these straight through to the corresponding platform target directory (e.g. `asr/claude/settings.json` → `.claude/settings.json`), recording each in the manifest.

`asr/` is the consumer's; `clasr` never edits it.

## AGENTS.md handling — marker block, NOT symlink

`asr/AGENTS.md` is **not** a file `clasr` symlinks or copies wholesale. It is the **content of a marker block** that `clasr` injects into the target's `AGENTS.md` and/or `CLAUDE.md`. Targets may already contain user content or content from other providers; `clasr` writes only between its own provider-named markers.

```
<!-- BEGIN clasr:clasi -->
... contents of asr/AGENTS.md ...
<!-- END clasr:clasi -->
```

A second consumer (e.g. `curik`) writes its own block:

```
<!-- BEGIN clasr:curik -->
... contents of curik's asr/AGENTS.md ...
<!-- END clasr:curik -->
```

`CLAUDE.md` is **not** a symlink to `AGENTS.md` in this design (sprint 013 had it as a symlink; this design supersedes that for clasr-managed installs). Instead, `clasr` writes the same marker block into both `AGENTS.md` and `CLAUDE.md`. This avoids the symlink-fragility issue on Windows and lets users keep platform-specific instructions in `CLAUDE.md` alongside the clasr block.

Uninstall strips the named block; if the file is empty after stripping, remove it.

## Frontmatter schema (agents/, rules/)

`asr/agents/*.md` and `asr/rules/*.md` carry **union** frontmatter — shared fields top-level, platform-specific fields nested under platform keys:

```yaml
---
name: code-review
description: Review a pull request
claude:
  tools: [Read, Grep, Bash]
copilot:
  applyTo: "**/*.ts"
codex:
  # absent or empty if no scoping
---
```

The renderer reads top-level + the active platform's nested block, merges, and writes target frontmatter. Body is verbatim.

Document this schema explicitly in `clasr/SCHEMA.md`. Resist organic growth.

## Render-vs-symlink decision

`clasr` decides per file:
- If output frontmatter == source frontmatter and the file is not in a per-platform `asr/<plat>/` subdir: **symlink** (or copy on `--copy` / Windows fallback).
- If frontmatter must be transformed: **render** a new file.
- If file lives under `asr/<platform>/`: **copy** straight through (no transform), record in that platform's manifest.

Skills (`SKILL.md`) almost always symlink. Agents and rules render. AGENTS.md is marker-block-managed.

## Manifest — per platform, lives inside the platform's directory

Each platform install writes its manifest **inside that platform's own directory**, because that's the directory whose contents the manifest describes, and these directories are multi-tenant (multiple providers can install into the same `.claude/`):

- `.claude/.clasr-manifest/<provider>.json`
- `.codex/.clasr-manifest/<provider>.json`
- `.github/.clasr-manifest/<provider>.json`

`<provider>` namespaces the manifest so `clasi` and `curik` (and future consumers) don't collide. `clasr uninstall --provider clasi --claude` reads only `.claude/.clasr-manifest/clasi.json` and removes only what that file lists.

Manifest schema:

```json
{
  "version": 1,
  "provider": "clasi",
  "platform": "claude",
  "source": "/abs/path/to/clasi/package_data/asr",
  "entries": [
    {"path": ".claude/skills/foo/SKILL.md", "kind": "symlink", "target": "<source>/skills/foo/SKILL.md"},
    {"path": ".claude/agents/code-review.md", "kind": "rendered", "from": "<source>/agents/code-review.md"},
    {"path": ".claude/settings.json", "kind": "copied", "from": "<source>/claude/settings.json"},
    {"path": "AGENTS.md", "kind": "marker-block", "block": "clasr:clasi"},
    {"path": "CLAUDE.md", "kind": "marker-block", "block": "clasr:clasi"}
  ]
}
```

`AGENTS.md` and `CLAUDE.md` entries appear in the Claude manifest (Claude is the platform that wrote them). If both `--claude` and `--codex` write to root `AGENTS.md`, each manifest records its own block; uninstalling one strips its block and leaves the other.

## Module layout

```
clasr/
  __init__.py
  cli.py                  ← argparse, install/uninstall, --provider, per-platform flags
  links.py                ← symlink-with-copy-fallback (lifted from clasi/platforms/_links.py)
  markers.py              ← named-marker-block writes (lifted from clasi/platforms/_markers.py)
  frontmatter.py          ← parse union frontmatter, project to per-platform output
  manifest.py             ← read/write per-platform per-provider manifests
  platforms/
    claude.py             ← writes .claude/, marker block in AGENTS.md + CLAUDE.md
    codex.py              ← writes .codex/, marker block in AGENTS.md (root + nested)
    copilot.py            ← writes .github/, .vscode/mcp.json, marker block in copilot-instructions.md
    detect.py             ← which platforms appear installed in target dir
  SCHEMA.md               ← the union-frontmatter spec
  README.md
tests/clasr/
  test_links.py
  test_markers.py
  test_frontmatter.py
  test_manifest.py
  test_platform_claude.py
  test_platform_codex.py
  test_platform_copilot.py
  test_three_platform_roundtrip.py
  test_multi_tenant.py    ← two providers installing into the same target
```

Modules drop the leading underscore (no longer "private to a single package" — they're internal to `clasr` but `clasi` imports them).

## Migration path for CLASI itself

Once `clasr` works, CLASI's `clasi/platforms/` becomes a thin wrapper:

1. CLASI ships its own `clasi/package_data/asr/` containing union-frontmatter source for CLASI's skills, agents, rules, and `claude/`/`codex/`/`copilot/` per-platform subdirs for settings.json etc.
2. `clasi init --claude --codex --copilot` calls `clasr install --provider clasi --source <clasi pkg asr> --claude --codex --copilot` (in-process, not a shell-out — they're in the same package).
3. `clasi/platforms/*.py` either delete entirely or shrink to nothing.

This validates the abstraction *before* curik or any other consumer is built.

## Multi-tenant scenarios

The design must handle: a user in a single repo runs both `clasi init` and `curik init`. Result:

- Two manifests in `.claude/.clasr-manifest/`: `clasi.json` and `curik.json`.
- Two marker blocks in `AGENTS.md`: `clasr:clasi` and `clasr:curik`.
- Skills from both providers coexist in `.claude/skills/` (different skill names; collision is the consumer's problem to solve via naming).
- `clasr uninstall --provider clasi --claude` removes only clasi's entries; curik's stay.

Test `test_multi_tenant.py` should cover install→install→uninstall sequences.

## Suggested implementation sequence

1. **Create `clasr/` package skeleton + entry point** in the existing `pyproject.toml`. Verify `pip install -e .` produces working `clasr --help`.
2. **Move `_links.py` and `_markers.py`** from `clasi/platforms/` into `clasr/links.py` and `clasr/markers.py`. Update `clasi/platforms/*.py` to import from `clasr`. Tests come along. Sprint 013 work stays green.
3. **Extend `markers.py`** to support named blocks (`<!-- BEGIN clasr:<provider> -->`) if not already present. Check what sprint 012 left behind for "named-section" support.
4. **Build `frontmatter.py`** — union-parse, per-platform projection. Heart of the renderer; unit-test heavily.
5. **Build `manifest.py`** — per-platform per-provider, atomic writes, schema validation.
6. **Build `clasr/cli.py`** — `install`/`uninstall` subcommands, `--provider`, `--source`, per-platform flags, `--copy`.
7. **Build Codex platform first** — AGENTS.md marker block, `.codex/` copies, simplest target.
8. **Build Claude platform** — `.claude/` symlinks for skills, renders for agents/rules, marker blocks in AGENTS.md + CLAUDE.md (both, no symlink), passthrough for `asr/claude/`.
9. **Build Copilot platform** — `.github/`, `.vscode/mcp.json` JSON-merge, `applyTo:` frontmatter render.
10. **Three-platform roundtrip test + multi-tenant test.**
11. **Migrate CLASI to be a clasr consumer.** Convert `clasi/templates/` and `clasi/platforms/_rules.py` content into `clasi/package_data/asr/` files with union frontmatter.

## Open questions

- **AGENTS.md vs CLAUDE.md symmetry.** Sprint 013 chose `CLAUDE.md → AGENTS.md` symlink. This design switches to "write the same marker block into both files." Confirm this is what stakeholder wants for clasr-managed installs (sprint 013 deliverables stay as-is for non-clasr code paths during transition).
- **Existing `clasi/platforms/_rules.py` Python constants.** Migrating to `asr/` files means moving rule bodies from Python source into Markdown files. Worth it (declarative + grep-able) but a non-trivial chunk of work. Could defer until after step 10 lands.
- **`asr/<platform>/` collision with target paths.** `asr/claude/settings.json` → `.claude/settings.json` is a one-to-one mapping. What about `asr/claude/commands/foo.md` → `.claude/commands/foo.md`? Suggest: per-platform subdirs are copied tree-recursive, with the platform subdir name stripped. Document in SCHEMA.md.
- **Multiple providers writing the same destination file.** Two providers both ship `asr/claude/settings.json` — last write wins, or error? Suggest: error with a clear message ("provider X and provider Y both want to write .claude/settings.json"). User resolves by removing one or by JSON-merging settings.json upstream.

## Out of scope (for the first cut)

- Cursor `.mdc` rendering — add later as another platform module once the engine is solid.
- Gemini CLI, Windsurf, Aider, Zed — drop-ins after the engine works.
- Splitting `clasr` into its own PyPI package — defer until dogfood story is proven *and* a second consumer (curik) is in flight.

## Origin

Stakeholder conversation 2026-05-01 evolving the sprint-013 cross-platform install design. Trajectory:

1. Start: sprint 013's "canonicalize on `.agents/`, symlink the rest, copy fallback" — works for skills, breaks on agent frontmatter divergence.
2. Sketch: wholesale `.claude/ → .agents/` symlink. Rejected (`.agents/` is a community namespace; mixing Claude-private settings into it pollutes the spec).
3. Sketch: `.asr/` as a canonical local dir with symlinks pointing in. Closer, but still has the frontmatter-union problem and mixes canonical with platform-private.
4. **Landing:** `asr/` as a per-package source dir + a generic renderer (`clasr`) that transforms it per platform. Source frontmatter is the union; targets are projections. Symlink is an optimization the renderer chooses; render is the default. Per-platform subdirs in `asr/` carry platform-private files. Manifests live in the platform directories they describe (multi-tenant). Marker blocks are named per provider. AGENTS.md and CLAUDE.md both get marker-block writes (no symlink).

Sprint 013 architecture: `docs/clasi/sprints/done/013-cross-platform-shared-install-canonicalize-symlink-and-add-copilot/architecture-update.md`.
