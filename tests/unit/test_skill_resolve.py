"""Unit tests for clasi.skill_resolve — the pure Load from: resolver.

``resolve_skill_body`` was moved out of ``clasi.tools.process_tools``
(which imports ``clasi.mcp_server`` at module level, and that module in
turn does ``from mcp.server.fastmcp import FastMCP``) into this
standalone, dependency-free module. This is so ``clasi init`` — which
only needs the pure ``Load from:`` resolution logic, not the MCP server
— never has to import FastMCP at all.

See ``clasi/issues/mcp-2-breaks-every-fresh-install.md`` for the crash
this decoupling fixes: an unbounded ``mcp>=1.0`` dependency resolves to
``mcp==2.0.0`` on a fresh install, which deleted
``mcp.server.fastmcp`` entirely, and ``clasi init`` was pulling in that
whole import chain merely to call this one pure helper.

Covers:
- resolve_skill_body: passthrough when no Load from: directive present
- resolve_skill_body: resolves Load from: directive, replaces body
- resolve_skill_body: preserves YAML frontmatter
- resolve_skill_body: raises FileNotFoundError for missing reference
- _PACKAGE_ROOT resolves to the same src/ directory the old
  tools/process_tools.py location did (round-tripped against a real
  bundled skill's Load from: directive)
- clasi.skill_resolve imports nothing from clasi.mcp_server /
  mcp.server.fastmcp (static AST check + a subprocess sys.modules check)
- clasi init's own install path completes even when mcp.server.fastmcp
  is blocked from importing (the actual reported failure mode)
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from clasi.skill_resolve import resolve_skill_body, _PACKAGE_ROOT

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILL_RESOLVE_SRC = _REPO_ROOT / "src" / "clasi" / "skill_resolve.py"


# ---------------------------------------------------------------------------
# resolve_skill_body — behavioral unit tests
# ---------------------------------------------------------------------------


class TestResolveSkillBodyPassthrough:
    def test_returns_raw_when_no_directive(self, tmp_path: Path) -> None:
        raw = "---\nname: foo\n---\n\n# Foo\n\nSome content.\n"
        assert resolve_skill_body(raw) == raw

    def test_no_frontmatter_no_directive_passthrough(self) -> None:
        raw = "# Just markdown, no directive.\n"
        assert resolve_skill_body(raw) == raw

    def test_comment_not_treated_as_directive(self) -> None:
        raw = "---\nname: bar\n---\n\n<!-- Load from: `something.md` -->\n# Bar\n"
        assert resolve_skill_body(raw) == raw


class TestResolveSkillBodyResolution:
    def test_replaces_body_with_referenced_file(self, tmp_path: Path) -> None:
        instruction_file = tmp_path / "my-instruction.md"
        instruction_file.write_text("# Full Prose\n\nDetailed instructions here.\n")

        raw = (
            "---\nname: my-skill\ndescription: A skill\n---\n\n"
            "Brief description.\n\n## Instructions\n\nLoad from: `my-instruction.md`\n"
        )
        result = resolve_skill_body(raw, base_path=tmp_path)

        assert "# Full Prose" in result
        assert "Detailed instructions here." in result

    def test_preserves_frontmatter(self, tmp_path: Path) -> None:
        instruction_file = tmp_path / "body.md"
        instruction_file.write_text("# Body Content\n")

        raw = "---\nname: my-skill\ndescription: My description\n---\n\nLoad from: `body.md`\n"
        result = resolve_skill_body(raw, base_path=tmp_path)

        assert result.startswith("---\nname: my-skill\ndescription: My description\n---\n")
        assert "# Body Content" in result

    def test_stub_body_not_in_result(self, tmp_path: Path) -> None:
        instruction_file = tmp_path / "full.md"
        instruction_file.write_text("# Full Instructions\n")

        raw = "---\nname: x\n---\n\nBrief stub text.\n\nLoad from: `full.md`\n"
        result = resolve_skill_body(raw, base_path=tmp_path)

        assert "Brief stub text." not in result
        assert "# Full Instructions" in result

    def test_raises_file_not_found_for_missing_ref(self, tmp_path: Path) -> None:
        raw = "---\nname: y\n---\n\nLoad from: `nonexistent.md`\n"
        with pytest.raises(FileNotFoundError, match="nonexistent.md"):
            resolve_skill_body(raw, base_path=tmp_path)

    def test_no_frontmatter_still_resolves(self, tmp_path: Path) -> None:
        instruction_file = tmp_path / "no-fm.md"
        instruction_file.write_text("# No FM\nContent.\n")

        raw = "Load from: `no-fm.md`\n"
        result = resolve_skill_body(raw, base_path=tmp_path)

        assert "# No FM" in result


# ---------------------------------------------------------------------------
# _PACKAGE_ROOT — must resolve to the same src/ directory the old
# tools/process_tools.py location did (one fewer .parent since
# skill_resolve.py sits one directory level shallower).
# ---------------------------------------------------------------------------


class TestPackageRootRoundTrip:
    def test_package_root_is_the_src_directory(self) -> None:
        # src/ is the parent of the clasi package, and contains
        # clasi/schemas/... — the root Load from: paths are relative to.
        assert _PACKAGE_ROOT.name == "src"
        assert (_PACKAGE_ROOT / "clasi").is_dir()
        assert (_PACKAGE_ROOT / "clasi" / "schemas").is_dir()

    def test_real_bundled_skill_load_from_resolves(self) -> None:
        """Round-trip a real bundled skill's Load from: directive using the
        default base_path (None -> _PACKAGE_ROOT), exactly as
        get_skill_definition and the platform installers call it."""
        skill_md = (
            _PACKAGE_ROOT / "clasi" / "plugin" / "skills" / "plan-sprint" / "SKILL.md"
        )
        assert skill_md.exists(), f"fixture skill missing: {skill_md}"
        raw = skill_md.read_text(encoding="utf-8")
        assert "Load from:" in raw

        instruction_path = (
            _PACKAGE_ROOT
            / "clasi"
            / "schemas"
            / "se-process"
            / "instructions"
            / "sprint-plan.md"
        )
        assert instruction_path.exists()
        expected = instruction_path.read_text(encoding="utf-8")

        result = resolve_skill_body(raw)

        assert "Load from:" not in result
        assert expected in result
        assert "name: plan-sprint" in result


# ---------------------------------------------------------------------------
# clasi.skill_resolve must never import clasi.mcp_server / mcp.server.fastmcp
# ---------------------------------------------------------------------------


class TestNoMcpServerImport:
    def test_static_source_has_no_mcp_import(self) -> None:
        """AST-check the module source: it must not import anything from
        the mcp package or clasi.mcp_server."""
        assert _SKILL_RESOLVE_SRC.exists()
        tree = ast.parse(_SKILL_RESOLVE_SRC.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("mcp"), (
                        f"skill_resolve.py imports {alias.name!r} — "
                        "must stay free of the mcp package"
                    )
                    assert "mcp_server" not in alias.name
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith("mcp"), (
                    f"skill_resolve.py imports from {module!r} — "
                    "must stay free of the mcp package"
                )
                assert "mcp_server" not in module

    def test_importing_skill_resolve_does_not_load_mcp_server(self) -> None:
        """Import clasi.skill_resolve alone, in a fresh subprocess, and
        assert neither clasi.mcp_server nor mcp.server.fastmcp end up in
        sys.modules as a side effect."""
        script = dedent(
            """
            import sys
            import clasi.skill_resolve
            assert "clasi.mcp_server" not in sys.modules, sys.modules.get("clasi.mcp_server")
            assert "mcp.server.fastmcp" not in sys.modules
            print("OK")
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "OK" in result.stdout


# ---------------------------------------------------------------------------
# clasi init's install path must complete even when mcp.server.fastmcp is
# unimportable — the actual reported failure mode (mcp 2.0.0 deleted
# mcp.server.fastmcp entirely). This is the acceptance-criterion test: it
# proves the CLI import chain, not just this module in isolation.
# ---------------------------------------------------------------------------


class TestInitSurvivesBlockedFastMCP:
    def test_clasi_init_completes_with_fastmcp_blocked(self, tmp_path: Path) -> None:
        target = tmp_path / "target_repo"
        target.mkdir()
        script = dedent(
            f"""
            import sys

            # Simulate mcp>=2.0, which deleted mcp.server.fastmcp entirely:
            # setting a sys.modules entry to None makes any subsequent
            # `import mcp.server.fastmcp` (or `from mcp.server.fastmcp
            # import ...`) raise ImportError immediately, exactly like the
            # real crash captured in
            # clasi/issues/mcp-2-breaks-every-fresh-install.md.
            sys.modules["mcp.server.fastmcp"] = None

            from clasi.init_command import run_init

            run_init({str(target)!r})

            assert "clasi.mcp_server" not in sys.modules, (
                "clasi init pulled in clasi.mcp_server — it must not need "
                "FastMCP at all"
            )
            print("OK")
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "OK" in result.stdout

        skill = target / ".claude" / "skills" / "se" / "SKILL.md"
        assert skill.exists(), "clasi init did not complete: SKILL.md missing"
