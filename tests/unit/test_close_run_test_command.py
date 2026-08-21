"""Regression test for close.py's test-runner subprocess (031/008 follow-up).

A real defect found empirically while closing sprint 031: the "tests"
step's subprocess call had no ``stdin=`` argument, so it inherited the
*calling* process's stdin. Through the MCP server that inherited stdin is
the JSON-RPC pipe from the client -- it never delivers input, so any test
that reads stdin (directly or via a fixture/runner default) blocked
forever, taking the whole sprint close down with it. Measured: the same
suite that finished in about 12 minutes from a shell (stdin redirected
from ``/dev/null``) was still running after 32+ minutes when invoked
through the MCP server, long after the client had already given up.

``_run_test_command`` (``clasi.close``) is the fix: the exact same
``subprocess.run`` call the "tests" step always made, with
``stdin=subprocess.DEVNULL`` added. Asserted here on the call arguments
made to a mocked ``subprocess.run`` rather than trying to reproduce an
actual multi-minute hang -- proving the fix mechanically rather than
reenacting the incident.
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from clasi.close import _run_test_command


class TestRunTestCommandClosesStdin:
    def test_stdin_is_devnull(self):
        with patch("clasi.close.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            _run_test_command(["uv", "run", "pytest"], timeout=900)

        mock_run.assert_called_once()
        call_args, call_kwargs = mock_run.call_args
        assert call_args == (["uv", "run", "pytest"],)
        assert call_kwargs["stdin"] is subprocess.DEVNULL

    def test_capture_output_text_and_timeout_are_unchanged(self):
        """The stdin fix must not disturb the call's pre-existing shape
        -- capture_output/text/timeout are exactly what the "tests" step
        relied on before this ticket."""
        with patch("clasi.close.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            _run_test_command(["uv", "run", "pytest"], timeout=123)

        _, call_kwargs = mock_run.call_args
        assert call_kwargs["capture_output"] is True
        assert call_kwargs["text"] is True
        assert call_kwargs["timeout"] == 123

    def test_result_is_returned_unchanged(self):
        with patch("clasi.close.subprocess.run") as mock_run:
            expected = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="ok\n", stderr=""
            )
            mock_run.return_value = expected
            result = _run_test_command(["uv", "run", "pytest"], timeout=900)

        assert result is expected

    def test_timeout_expired_propagates(self):
        with patch("clasi.close.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["uv", "run", "pytest"], timeout=1
            )
            try:
                _run_test_command(["uv", "run", "pytest"], timeout=1)
            except subprocess.TimeoutExpired:
                pass
            else:
                raise AssertionError("expected TimeoutExpired to propagate")

    def test_file_not_found_propagates(self):
        with patch("clasi.close.subprocess.run", side_effect=FileNotFoundError()):
            try:
                _run_test_command(["not-a-real-executable"], timeout=900)
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("expected FileNotFoundError to propagate")
