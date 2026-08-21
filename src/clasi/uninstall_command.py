"""Implementation of the `clasi uninstall` command.

Removes CLASI-managed platform integration files from a target repository.
Claude is the only installable platform as of sprint 032 (Codex and Copilot
were archived — see the ``archive/codex-copilot-adapters`` branch); the
--codex/--copilot flags are still accepted for backward compatibility but
raise a clear error instead of silently no-op'ing.

In interactive mode (no flag, TTY), prompts the user to confirm removing
Claude platform integration.

In non-interactive mode (no flag), exits with a clear error requiring an
explicit flag.

Public interface::

    run_uninstall(target: str, claude: bool) -> None
"""

import sys
from pathlib import Path

import click


def _prompt_uninstall(target: Path) -> str:
    """Prompt the user to confirm removing Claude platform integration.

    Claude is the only installable platform as of sprint 032 (Codex and
    Copilot were archived — see the ``archive/codex-copilot-adapters``
    branch), so this no longer inspects multi-platform detect_platforms()
    signals or offers a multi-platform menu; it presents a single
    confirmation.
    """
    del target  # kept for call-site/API compatibility; no longer consulted

    click.echo("Uninstall CLASI platform integration:")
    click.echo("  [1] Claude")

    while True:
        choice = click.prompt("Choice", type=str, default="1").strip()
        if choice == "1":
            return "claude"
        click.echo("Invalid choice. Enter 1.")


def run_uninstall(
    target: str,
    claude: bool = False,
    codex: bool = False,
    copilot: bool = False,
    copy: bool = False,
) -> None:
    """Remove CLASI platform integration files from *target*.

    Parameters
    ----------
    target:
        Path to the target project directory.
    claude:
        If True, run the Claude platform uninstaller.
    codex:
        Accepted for backward compatibility only. If True (or *copilot*
        is True), raises a ``click.ClickException`` with a clear
        archived-support message instead of removing anything or
        silently no-op'ing.
    copilot:
        See *codex*.
    copy:
        If True, alias operations use file-copy removal semantics.
        In practice ``_links.unlink_alias`` handles both symlinks and
        regular files identically, so this flag is surfaced for parity
        with ``clasi init --copy`` and passed through to the uninstallers.

    Raises
    ------
    click.ClickException
        If *codex* or *copilot* is True.
    """
    if codex or copilot:
        raise click.ClickException(
            "Codex/Copilot support has been archived; see the "
            "archive/codex-copilot-adapters branch. Re-run `clasi uninstall` "
            "without --codex/--copilot to manage Claude support only."
        )

    target_path = Path(target).resolve()
    interactive = sys.stdin.isatty() and sys.stdout.isatty()

    if not claude:
        if interactive:
            choice = _prompt_uninstall(target_path)
            claude = choice == "claude"
        else:
            click.echo("Error: specify --claude.", err=True)
            raise SystemExit(1)

    if claude:
        from clasi.platforms.claude import uninstall as claude_uninstall
        claude_uninstall(target_path, copy=copy)
