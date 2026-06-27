"""Advisory platform detection for CLASI.

Inspects observable signals to recommend which platform(s) are configured
for a target project. Never reads environment variable values, never writes
files, never runs subprocesses beyond shutil.which, and never makes
irreversible decisions.

Public interface::

    detect_platforms(target: Path) -> PlatformSignals

``PlatformSignals`` is a dataclass with::

    claude_score:  int          # sum of all Claude signal weights
    codex_score:   int          # sum of all Codex signal weights
    copilot_score: int          # sum of all Copilot signal weights
    recommendation: str        # "claude", "codex", "copilot", or "both"

Recommendation logic:
- claude_score > 0 and codex_score == 0 and copilot_score == 0  → "claude"
- codex_score > 0  and claude_score == 0 and copilot_score == 0 → "codex"
- copilot_score > 0 and claude_score == 0 and codex_score == 0  → "copilot"
- any two or more > 0                                            → "both"
- all == 0                                                       → "claude"  (backward-compat default)

Signal weights:
- Project-level file present: +2
- Installed command:           +1
- User config directory:       +1
- Env var name present:        +1
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class PlatformSignals:
    """Result of advisory platform detection."""

    claude_score: int
    codex_score: int
    copilot_score: int
    recommendation: str  # "claude" | "codex" | "copilot" | "both"


# ---------------------------------------------------------------------------
# Internal signal helpers
# ---------------------------------------------------------------------------

# Project-level file/directory indicators (weight +2 each)
_CLAUDE_PROJECT_FILES = [
    ".claude",
    "CLAUDE.md",
]

_CODEX_PROJECT_FILES = [
    ".codex",
    ".agents/skills",
    "AGENTS.md",
]

# CLI command names (weight +1 each)
_CLAUDE_COMMANDS = ["claude"]
_CODEX_COMMANDS = ["codex"]
_COPILOT_COMMANDS = ["code", "gh"]

# User config directories under ~ (weight +1 each)
_CLAUDE_USER_DIRS = [".claude"]
_CODEX_USER_DIRS = [".codex"]
_COPILOT_USER_DIRS = [".config/github-copilot"]

# Environment variable name prefixes/exact names (weight +1 per matching name)
# Values are NEVER read — only names are checked.
_CLAUDE_ENV_EXACT = {"ANTHROPIC_API_KEY"}
_CLAUDE_ENV_PREFIX = "CLAUDE_"

_CODEX_ENV_EXACT = {"OPENAI_API_KEY"}
_CODEX_ENV_PREFIX = "CODEX_"

_COPILOT_ENV_EXACT: set[str] = set()
_COPILOT_ENV_PREFIX = "GITHUB_COPILOT_"

# Copilot project-level indicators (weight +2 each)
_COPILOT_PROJECT_FILES = [
    ".github/copilot-instructions.md",
    ".github/agents",
    ".github/instructions",
]


def _project_file_score(target: Path, indicators: list[str]) -> int:
    """Return 2 × count of present project-level indicators under *target*."""
    score = 0
    for rel in indicators:
        if (target / rel).exists():
            score += 2
    return score


def _command_score(commands: list[str]) -> int:
    """Return 1 × count of installed commands found via shutil.which."""
    score = 0
    for cmd in commands:
        if shutil.which(cmd) is not None:
            score += 1
    return score


def _user_dir_score(dirs: list[str]) -> int:
    """Return 1 × count of user config directories that exist under ~."""
    home = Path.home()
    score = 0
    for d in dirs:
        if (home / d).exists():
            score += 1
    return score


def _env_score(exact: set[str], prefix: str) -> int:
    """Return 1 × count of matching env var *names* present.

    Values are never accessed.
    """
    score = 0
    for name in os.environ:
        if name in exact or name.startswith(prefix):
            score += 1
    return score


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_platforms(target: Path) -> PlatformSignals:
    """Inspect advisory signals and return a platform recommendation.

    Parameters
    ----------
    target:
        Root directory of the project to inspect.

    Returns
    -------
    PlatformSignals
        Advisory scores and recommendation. No files are written and no
        environment variable values are read.
    """
    claude_score = (
        _project_file_score(target, _CLAUDE_PROJECT_FILES)
        + _command_score(_CLAUDE_COMMANDS)
        + _user_dir_score(_CLAUDE_USER_DIRS)
        + _env_score(_CLAUDE_ENV_EXACT, _CLAUDE_ENV_PREFIX)
    )

    codex_score = (
        _project_file_score(target, _CODEX_PROJECT_FILES)
        + _command_score(_CODEX_COMMANDS)
        + _user_dir_score(_CODEX_USER_DIRS)
        + _env_score(_CODEX_ENV_EXACT, _CODEX_ENV_PREFIX)
    )

    copilot_score = (
        _project_file_score(target, _COPILOT_PROJECT_FILES)
        + _command_score(_COPILOT_COMMANDS)
        + _user_dir_score(_COPILOT_USER_DIRS)
        + _env_score(_COPILOT_ENV_EXACT, _COPILOT_ENV_PREFIX)
    )

    active = sum(1 for s in (claude_score, codex_score, copilot_score) if s > 0)

    if active == 0:
        recommendation = "claude"  # safe default
    elif active > 1:
        recommendation = "both"
    elif claude_score > 0:
        recommendation = "claude"
    elif codex_score > 0:
        recommendation = "codex"
    else:
        recommendation = "copilot"

    return PlatformSignals(
        claude_score=claude_score,
        codex_score=codex_score,
        copilot_score=copilot_score,
        recommendation=recommendation,
    )
