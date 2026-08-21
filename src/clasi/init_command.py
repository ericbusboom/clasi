"""Implementation of the `clasi init` command.

Installs the CLASI SE process into a target repository. Supports two modes:

- **Project-local mode** (default): Copies skills, agents, and hook config
  from the bundled plugin/ directory into the project's .claude/ directory.
  Skills are unnamespaced (/plan-sprint, /se, /issue).

- **Plugin mode** (--plugin): Registers the CLASI plugin with Claude Code.
  Skills are namespaced (/clasi:plan-sprint, /clasi:se, /clasi:issue).

Both modes also configure MCP server, permissions, TODO directories,
and path-scoped rules.

Claude Code is the only platform in master as of sprint 032 (Codex and
Copilot were archived — see the ``archive/codex-copilot-adapters``
branch). With no --claude flag (interactive or not), installs Claude
support. --codex/--copilot are still accepted for backward compatibility
but raise a clear error instead of installing anything or silently
no-op'ing.

Also writes `protected_paths:` to .clasi/config.yaml (ticket 031-004):
auto-detects `src/` and `tests/` at the project root, or — when nothing is
detected and the session is interactive — prompts for directories to
protect. A non-interactive call (or an interactive decline) that detects
nothing leaves the key unwritten, preserving role-guard's pre-existing
block-by-default fallback for tier 0/1 writes.
"""

import json
import sys
from pathlib import Path

import click
import yaml

# The plugin directory is bundled inside the clasi package.
_PLUGIN_DIR = Path(__file__).parent / "plugin"

# Re-export RULES for backward compatibility with existing tests that import
# RULES from clasi.init_command.
from clasi.platforms.claude import RULES  # noqa: E402,F401
from clasi.project import ARTIFACT_PATH_DEFAULTS  # noqa: E402


def _detect_mcp_command(target: Path) -> dict:
    """Return the MCP server command written into MCP config files.

    Always uses the bare `clasi mcp` command. After `pip install clasi`
    (or any other install method that places `clasi` on PATH), this is
    the right invocation for both end users and CI. The previous
    `uv run clasi mcp` form was only useful when CLASI was being
    developed locally and broke for any project that didn't have uv or
    didn't have a [project] table in pyproject.toml. Projects that
    actually want `uv run` can edit their MCP config by hand.

    The *target* parameter is retained for API compatibility but is not
    consulted.
    """
    del target
    return {"command": "clasi", "args": ["mcp"]}


# Convention-based directory names `clasi init` checks for at the project
# root when writing `protected_paths:` (ticket 031-004). Deliberately kept
# to the two names the ticket's own plan cites (src/, tests/) — the
# cheapest, most common convention across Python/JS/TS/Rust layouts — not
# an exhaustive per-ecosystem list. A project using other conventions
# (Go's cmd/pkg, Java/Maven's src/main+src/test, a bare top-level package
# with no src/ wrapper, ...) will not be auto-detected; see
# _detect_protected_paths' docstring for what happens then.
_PROTECTED_DIR_CANDIDATES = ("src", "tests")


def _detect_protected_paths(target: Path) -> list[str]:
    """Return convention-based source/test directory names found under *target*.

    Checks only for ``src/`` and ``tests/`` directly under the project
    root. Returns the subset that actually exists as a directory (in
    ``_PROTECTED_DIR_CANDIDATES`` order), so a project with only one of
    the two (e.g. ``src/`` but no top-level ``tests/``) still gets a
    partial, non-empty result rather than being treated as undetectable.

    Returns ``[]`` when neither convention matches — the "cannot detect
    anything" case. This is expected and unremarkable for a project that
    doesn't follow the src/tests convention (a Go project using cmd/pkg,
    a Java/Maven layout, a bare top-level package, ...); the caller
    (:func:`run_init`) must NOT write an empty ``protected_paths:`` in
    that case; leaving the key absent keeps role-guard's pre-existing
    block-by-default fallback in effect, which is the safe default for a
    layout this heuristic doesn't recognize.
    """
    return [name for name in _PROTECTED_DIR_CANDIDATES if (target / name).is_dir()]


def _prompt_protected_paths() -> list[str]:
    """Interactively ask which directories to protect from agent writes.

    Only called when running interactively (TTY attached) AND
    :func:`_detect_protected_paths` found nothing to auto-detect. A blank
    response means the stakeholder declines — returns ``[]``, and the
    caller must not write ``protected_paths:`` (matching the
    non-interactive behavior for the same "nothing detected" case:
    role-guard's block-by-default fallback stays in effect).
    """
    click.echo(
        "Could not auto-detect source/test directories (looked for src/, tests/)."
    )
    raw = click.prompt(
        "Directories to protect from agent writes (comma-separated, e.g. "
        "'src,tests'; blank to skip and keep the default block-by-default policy)",
        default="",
        show_default=False,
    )
    return [p.strip().strip("/") for p in raw.split(",") if p.strip()]


def _update_mcp_json(mcp_json_path: Path, target: Path) -> bool:
    """Merge MCP server config into .mcp.json.

    If a `clasi` entry already exists in `mcpServers` — in ANY form, not
    just the exact default this function would otherwise write — it is
    left untouched. Only a missing entry is written, using the default
    from :func:`_detect_mcp_command`. This is deliberately more general
    than detecting "is this the clasi repo itself": any project that has
    hand-edited its `clasi` entry (e.g. to `uv run clasi mcp` for a local
    editable install) keeps that edit across every `clasi init`/`clasi
    migrate` re-run, instead of having it silently reverted to the bare
    consumer default (ticket 032/004; see also
    `clasi-init-reverts-this-repos-own-mcp-config-to-the-consumer-default.md`).

    Returns True if the file was written/updated, False if unchanged.
    """
    rel = str(mcp_json_path.name)
    mcp_config = _detect_mcp_command(target)

    if mcp_json_path.exists():
        try:
            data = json.loads(mcp_json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            data = {}
    else:
        data = {}

    mcp_servers = data.setdefault("mcpServers", {})

    if "clasi" in mcp_servers:
        click.echo(f"  Unchanged: {rel} (existing clasi server entry preserved)")
        return False

    mcp_servers["clasi"] = mcp_config
    mcp_json_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    click.echo(f"  Updated: {rel}")
    return True


def run_init(
    target: str,
    plugin_mode: bool = False,
    claude: bool = False,
    codex: bool = False,
    copilot: bool = False,
    copy: bool = False,
    migrate: bool = False,
    process: str = "se",
    yes: bool = False,
) -> None:
    """Initialize a repository for the CLASI SE process.

    In project-local mode (default), copies skills, agents, and hooks
    from the plugin/ directory into .claude/. In plugin mode, registers
    the CLASI plugin with Claude Code.

    Claude is the only installable platform as of sprint 032 (Codex and
    Copilot were archived — never dogfooded, reachable only via these
    explicit flags; see the ``archive/codex-copilot-adapters`` branch).
    When *claude* is not True (interactive or not), the function defaults
    to installing Claude support.

    Args:
        target: Path to the target project root (string; resolved internally).
        plugin_mode: If True, run in plugin mode instead of project-local mode.
        claude: If True, run the Claude platform installer.
        codex: Accepted for backward compatibility only. If True (or
            *copilot* is True), ``run_init`` raises a ``click.ClickException``
            with a clear archived-support message instead of installing
            anything or silently no-op'ing.
        copilot: See *codex*.
        copy: If True, use file copy instead of symlink for alias operations.
        migrate: If True, convert legacy direct-copy installs to symlinks.
        process: SE process variant to activate; one of ``"se"`` or ``"solo"``.
            Written to ``.clasi/config.yaml`` as the ``process:`` key.
        yes: If True, relocate legacy files without prompting (unattended opt-in).

    Raises:
        click.ClickException: if *codex* or *copilot* is True.
    """
    if codex or copilot:
        raise click.ClickException(
            "Codex/Copilot support has been archived; see the "
            "archive/codex-copilot-adapters branch. Re-run `clasi init` "
            "without --codex/--copilot to install Claude support only."
        )

    from clasi.platforms.claude import install as claude_install

    # Track whether the user explicitly specified a platform.  --migrate is
    # platform-scoped: it only runs when an explicit platform flag is given.
    explicit_platform = claude
    effective_migrate = migrate and explicit_platform

    # Claude is the only platform in master; default to it whenever no
    # explicit flag is given (interactive or not — there is nothing left to
    # choose among, so no interactive prompt is shown).
    if not claude:
        claude = True

    target_path = Path(target).resolve()
    mode_label = "plugin" if plugin_mode else "project-local"
    click.echo(f"Initializing CLASI in {target_path} ({mode_label} mode)")
    click.echo()

    # Detect MCP command once; shared scaffolding and platform installers use it.
    mcp_config = _detect_mcp_command(target_path)

    if plugin_mode:
        # Plugin mode: just tell the user how to install
        click.echo("Plugin mode: install the CLASI plugin with Claude Code:")
        click.echo(f"  claude --plugin-dir {_PLUGIN_DIR}")
        click.echo("  Or: /plugin install clasi (from marketplace)")
        click.echo()
    else:
        if claude:
            # Project-local mode: delegate all Claude-specific steps to the platform module.
            claude_install(target_path, mcp_config, copy=copy, migrate=effective_migrate)

    # Configure MCP server in .mcp.json at project root (shared setup).
    click.echo("MCP server configuration:")
    _update_mcp_json(target_path / ".mcp.json", target_path)
    click.echo()

    # Create directory structure from ARTIFACT_PATH_DEFAULTS (shared setup).
    click.echo("CLASI directories:")
    clasi_dir = target_path / ".clasi"
    clasi_dir.mkdir(parents=True, exist_ok=True)

    for key, rel in ARTIFACT_PATH_DEFAULTS.items():
        if key == "db":
            continue  # db is a file; created by StateDB on first use
        dir_path = target_path / rel
        dir_path.mkdir(parents=True, exist_ok=True)
        if key == "logs":
            gitignore = dir_path / ".gitignore"
            gitignore.write_text("# Ignore all log files\n*\n!.gitignore\n", encoding="utf-8")
            click.echo(f"  Created: {rel}/ (with .gitignore)")
        else:
            gk = dir_path / ".gitkeep"
            if not gk.exists() and not any(dir_path.iterdir()):
                gk.touch()
            click.echo(f"  Created: {rel}/")

    # Write (or update) .clasi/config.yaml with the chosen process and paths.
    config_path = clasi_dir / "config.yaml"
    config_data: dict = {}
    if config_path.exists():
        try:
            existing = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                config_data = existing
        except yaml.YAMLError:
            pass  # overwrite a corrupt config
    config_data["process"] = process
    config_data.setdefault("paths", dict(ARTIFACT_PATH_DEFAULTS))
    # Write the design-doc opt-in explicitly so the key is visible in a fresh
    # config rather than absent. "disabled" is the safe default (identical
    # behavior to unset for the sprint lifecycle); setdefault preserves an
    # existing "enabled"/"disabled" choice on re-init.
    config_data.setdefault("design_docs", "disabled")
    # Detect (or ask for) the project's source/test directories so
    # role-guard has a real, project-specific protected_paths list instead
    # of falling back to block-by-default for tier 0/1 (ticket 031-004).
    # Only attempted when the key is absent — matches the setdefault
    # pattern above: an already-configured (or previously declined, see
    # below) project is never re-detected or re-prompted on a later
    # `clasi init` re-run.
    if "protected_paths" not in config_data:
        detected = _detect_protected_paths(target_path)
        if not detected and sys.stdin.isatty() and sys.stdout.isatty():
            detected = _prompt_protected_paths()
        if detected:
            config_data["protected_paths"] = detected
            click.echo(f"  Written: protected_paths: {detected}")
        # else: nothing detected and either non-interactive or the
        # stakeholder declined — leave protected_paths unwritten so
        # role-guard's pre-existing block-by-default fallback stays in
        # effect (no regression for a layout this heuristic can't read).
    config_path.write_text(yaml.safe_dump(config_data, default_flow_style=False), encoding="utf-8")
    click.echo(f"  Written: .clasi/config.yaml (process: {process})")

    click.echo()
    click.echo("Done! The CLASI SE process is now configured.")

    # ── Detect and optionally relocate legacy artifacts ────────────────────
    from clasi.migrate_command import detect_moves, execute_moves
    from clasi.project import Project

    project = Project(target_path)
    moves = detect_moves(project)

    if moves:
        if yes:
            click.echo()
            click.echo("Relocating legacy artifacts (--yes flag set):")
            execute_moves(project, moves)
        elif sys.stdin.isatty() and sys.stdout.isatty():
            click.echo()
            click.echo("Your files are not in the right spot. Proposed moves:")
            for m in moves:
                click.echo(f"  {m.src} → {m.dst}")
            if click.confirm("Move them?", default=False):
                execute_moves(project, moves)
            else:
                click.echo(
                    "Hint: run `clasi migrate` to relocate files when ready.",
                )
        else:
            click.echo(
                "WARNING: Files found at legacy locations. "
                "Run `clasi migrate` to relocate.",
                err=True,
            )
