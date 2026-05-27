"""Unit tests for finalize_sprint MCP tool alias (ticket 007-002).

Verifies that finalize_sprint is an exact alias for close_sprint:
- identical Python signature (param names, types, defaults, order)
- body delegates to close_sprint with correct arguments
- registered in the MCP server tool registry
"""

import inspect
from unittest.mock import patch

import clasi.tools.artifact_tools  # noqa: F401 — trigger tool registration
from clasi.tools.artifact_tools import close_sprint, finalize_sprint
from clasi.mcp_server import server


class TestFinalizeSprintSignature:
    """The signature of finalize_sprint must be byte-for-byte identical to close_sprint."""

    def test_parameter_names_match(self):
        cs_params = inspect.signature(close_sprint).parameters
        fs_params = inspect.signature(finalize_sprint).parameters
        assert list(cs_params.keys()) == list(fs_params.keys())

    def test_parameter_defaults_match(self):
        cs_params = inspect.signature(close_sprint).parameters
        fs_params = inspect.signature(finalize_sprint).parameters
        for name in cs_params:
            assert cs_params[name].default == fs_params[name].default, (
                f"Default mismatch for param '{name}': "
                f"close_sprint={cs_params[name].default!r}, "
                f"finalize_sprint={fs_params[name].default!r}"
            )

    def test_parameter_annotations_match(self):
        cs_params = inspect.signature(close_sprint).parameters
        fs_params = inspect.signature(finalize_sprint).parameters
        for name in cs_params:
            assert cs_params[name].annotation == fs_params[name].annotation, (
                f"Annotation mismatch for param '{name}': "
                f"close_sprint={cs_params[name].annotation!r}, "
                f"finalize_sprint={fs_params[name].annotation!r}"
            )

    def test_parameter_kinds_match(self):
        cs_params = inspect.signature(close_sprint).parameters
        fs_params = inspect.signature(finalize_sprint).parameters
        for name in cs_params:
            assert cs_params[name].kind == fs_params[name].kind, (
                f"Kind mismatch for param '{name}'"
            )

    def test_return_annotation_matches(self):
        cs_sig = inspect.signature(close_sprint)
        fs_sig = inspect.signature(finalize_sprint)
        assert cs_sig.return_annotation == fs_sig.return_annotation

    def test_full_signature_equality(self):
        """Combined test: inspect.signature equality across all attributes."""
        cs_params = inspect.signature(close_sprint).parameters
        fs_params = inspect.signature(finalize_sprint).parameters
        assert list(cs_params.keys()) == list(fs_params.keys())
        for name in cs_params:
            assert cs_params[name].default == fs_params[name].default
            assert cs_params[name].annotation == fs_params[name].annotation


class TestFinalizeSprintDelegation:
    """finalize_sprint must delegate all calls to close_sprint."""

    def test_delegates_to_close_sprint_with_defaults(self):
        with patch(
            "clasi.tools.artifact_tools.close_sprint", return_value='{"ok": true}'
        ) as mock_close:
            result = finalize_sprint("007")
        mock_close.assert_called_once_with(
            "007", None, "master", True, True, None
        )
        assert result == '{"ok": true}'

    def test_delegates_to_close_sprint_with_all_args(self):
        with patch(
            "clasi.tools.artifact_tools.close_sprint", return_value='{"ok": true}'
        ) as mock_close:
            result = finalize_sprint(
                sprint_id="007",
                branch_name="sprint/007-my-sprint",
                main_branch="main",
                push_tags=False,
                delete_branch=False,
                test_command="make test",
            )
        mock_close.assert_called_once_with(
            "007", "sprint/007-my-sprint", "main", False, False, "make test"
        )
        assert result == '{"ok": true}'

    def test_returns_close_sprint_result(self):
        sentinel = '{"status": "closed"}'
        with patch(
            "clasi.tools.artifact_tools.close_sprint", return_value=sentinel
        ):
            result = finalize_sprint("007")
        assert result == sentinel


class TestFinalizeSprintRegistration:
    """finalize_sprint must be registered as an MCP tool."""

    def _registered_tool_names(self) -> set[str]:
        return set(server._tool_manager._tools.keys())

    def test_finalize_sprint_is_registered(self):
        assert "finalize_sprint" in self._registered_tool_names()

    def test_close_sprint_still_registered(self):
        """close_sprint must remain registered (unchanged)."""
        assert "close_sprint" in self._registered_tool_names()
