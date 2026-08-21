"""Regression tests for close.py's test-runner subprocess: stdin closed
(031/008) and the whole process group killed on timeout (032/006).

``_run_test_command`` (``clasi.close``) used to be a single
``subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
stdin=subprocess.DEVNULL)`` call. 031/008 added the ``stdin=DEVNULL`` --
without it, the "tests" step inherited the *calling* process's stdin,
which through the MCP server is the JSON-RPC pipe from the client and
never delivers input; a test suite reading stdin blocked forever instead
of failing (measured: a suite that finished in about 12 minutes from a
shell was still running after 32+ minutes through the MCP server).

032/006 replaced ``subprocess.run`` with ``Popen`` +
``start_new_session=True`` + ``communicate(timeout=...)``, because
``subprocess.run``'s own timeout handling kills only the *direct* child
it spawned -- the configured test command is commonly a wrapper (``uv
run pytest``, ``npm test``, ``poetry run pytest``) whose real work
happens in a grandchild in the same process group. Observed live at
close of sprint 031: an abandoned ``uv run pytest`` was still consuming
CPU 32 minutes after its ``close_sprint`` call had been aborted
client-side. On ``TimeoutExpired`` the whole process group is now killed
via ``os.killpg(os.getpgid(pid), SIGKILL)``, not just the direct child.

All tests here mock ``clasi.close.subprocess.Popen`` (and, where
relevant, ``clasi.close.os.killpg``/``os.getpgid``) rather than
reproducing real process behavior -- proving the fix mechanically via
call assertions. The real-process, real-grandchild-survival proof lives
in ``tests/integration/test_close_run_test_command_grandchild.py``
(marked ``slow`` -- it actually spawns processes and waits on timing).
"""

from __future__ import annotations

import signal
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from clasi.close import _run_test_command


def _mock_proc(
    returncode: int = 0, stdout: str = "", stderr: str = "", pid: int = 4242
) -> MagicMock:
    """Build a Popen-shaped mock matching exactly what _run_test_command
    reads off its Popen instance: .communicate(...) and .returncode."""
    proc = MagicMock()
    proc.communicate.return_value = (stdout, stderr)
    proc.returncode = returncode
    proc.pid = pid
    return proc


class TestRunTestCommandClosesStdin:
    def test_stdin_is_devnull(self):
        with patch("clasi.close.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _mock_proc(0)
            _run_test_command(["uv", "run", "pytest"], timeout=900)

        mock_popen.assert_called_once()
        call_args, call_kwargs = mock_popen.call_args
        assert call_args == (["uv", "run", "pytest"],)
        assert call_kwargs["stdin"] is subprocess.DEVNULL

    def test_text_mode_and_pipes_are_used(self):
        """Popen is configured for text-mode captured output, matching what
        subprocess.run(capture_output=True, text=True) used to provide."""
        with patch("clasi.close.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _mock_proc(0)
            _run_test_command(["uv", "run", "pytest"], timeout=123)

        _, call_kwargs = mock_popen.call_args
        assert call_kwargs["stdout"] is subprocess.PIPE
        assert call_kwargs["stderr"] is subprocess.PIPE
        assert call_kwargs["text"] is True

    def test_starts_new_session_for_process_group_kill(self):
        """032/006: the child must lead its own process group (POSIX
        setsid via start_new_session=True) so a timeout can killpg() the
        whole group, not just this direct child."""
        with patch("clasi.close.subprocess.Popen") as mock_popen, \
                patch("clasi.close._HAS_PROCESS_GROUPS", True):
            mock_popen.return_value = _mock_proc(0)
            _run_test_command(["uv", "run", "pytest"], timeout=123)

        _, call_kwargs = mock_popen.call_args
        assert call_kwargs["start_new_session"] is True

    def test_timeout_passed_to_communicate(self):
        with patch("clasi.close.subprocess.Popen") as mock_popen:
            proc = _mock_proc(0)
            mock_popen.return_value = proc
            _run_test_command(["uv", "run", "pytest"], timeout=123)

        proc.communicate.assert_called_once_with(timeout=123)

    def test_result_matches_completed_process_shape(self):
        with patch("clasi.close.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _mock_proc(0, stdout="ok\n", stderr="")
            result = _run_test_command(["uv", "run", "pytest"], timeout=900)

        assert result.returncode == 0
        assert result.stdout == "ok\n"
        assert result.stderr == ""

    def test_file_not_found_propagates(self):
        with patch("clasi.close.subprocess.Popen", side_effect=FileNotFoundError()):
            with pytest.raises(FileNotFoundError):
                _run_test_command(["not-a-real-executable"], timeout=900)


class TestRunTestCommandKillsProcessGroupOnTimeout:
    """032/006: on TimeoutExpired, the whole process group is killed, not
    just the direct child -- see close.py's _run_test_command docstring
    for why (031/008's abandoned uv run pytest, still running 32 minutes
    after its close_sprint call was aborted)."""

    def test_timeout_expired_propagates(self):
        with patch("clasi.close.subprocess.Popen") as mock_popen, \
                patch("clasi.close.os.killpg"), \
                patch("clasi.close.os.getpgid", return_value=99), \
                patch("clasi.close._HAS_PROCESS_GROUPS", True):
            proc = _mock_proc(0, pid=4242)
            proc.communicate.side_effect = [
                subprocess.TimeoutExpired(cmd=["uv", "run", "pytest"], timeout=1),
                ("", ""),  # post-kill drain call
            ]
            mock_popen.return_value = proc

            with pytest.raises(subprocess.TimeoutExpired):
                _run_test_command(["uv", "run", "pytest"], timeout=1)

    def test_process_group_is_killed_on_timeout(self):
        """The fix's actual mechanism: os.killpg(getpgid(pid), SIGKILL)."""
        with patch("clasi.close.subprocess.Popen") as mock_popen, \
                patch("clasi.close.os.killpg") as mock_killpg, \
                patch("clasi.close.os.getpgid", return_value=99) as mock_getpgid, \
                patch("clasi.close._HAS_PROCESS_GROUPS", True):
            proc = _mock_proc(0, pid=4242)
            proc.communicate.side_effect = [
                subprocess.TimeoutExpired(cmd=["uv", "run", "pytest"], timeout=1),
                ("", ""),
            ]
            mock_popen.return_value = proc

            with pytest.raises(subprocess.TimeoutExpired):
                _run_test_command(["uv", "run", "pytest"], timeout=1)

        mock_getpgid.assert_called_once_with(4242)
        mock_killpg.assert_called_once_with(99, signal.SIGKILL)
        # communicate() called twice: once with the timeout that expired,
        # once (no timeout) afterward to drain/reap the killed group.
        assert proc.communicate.call_count == 2

    def test_process_already_gone_does_not_raise(self):
        """A race where the process exits between TimeoutExpired and the
        killpg call (ProcessLookupError) must not mask the timeout."""
        with patch("clasi.close.subprocess.Popen") as mock_popen, \
                patch("clasi.close.os.killpg", side_effect=ProcessLookupError()), \
                patch("clasi.close.os.getpgid", return_value=99), \
                patch("clasi.close._HAS_PROCESS_GROUPS", True):
            proc = _mock_proc(0, pid=4242)
            proc.communicate.side_effect = [
                subprocess.TimeoutExpired(cmd=["uv", "run", "pytest"], timeout=1),
                ("", ""),
            ]
            mock_popen.return_value = proc

            with pytest.raises(subprocess.TimeoutExpired):
                _run_test_command(["uv", "run", "pytest"], timeout=1)

    def test_windows_fallback_kills_direct_child_only(self):
        """When process groups aren't available (Windows: no os.killpg/
        os.getpgid), the timeout path falls back to proc.kill() instead
        of crashing with AttributeError -- see _run_test_command's
        docstring, "Windows" section: this is a documented gap, not full
        Windows support."""
        with patch("clasi.close.subprocess.Popen") as mock_popen, \
                patch("clasi.close._HAS_PROCESS_GROUPS", False):
            proc = _mock_proc(0, pid=4242)
            proc.communicate.side_effect = [
                subprocess.TimeoutExpired(cmd=["pytest"], timeout=1),
                ("", ""),
            ]
            mock_popen.return_value = proc

            with pytest.raises(subprocess.TimeoutExpired):
                _run_test_command(["pytest"], timeout=1)

        proc.kill.assert_called_once()

    def test_windows_fallback_does_not_pass_start_new_session(self):
        with patch("clasi.close.subprocess.Popen") as mock_popen, \
                patch("clasi.close._HAS_PROCESS_GROUPS", False):
            mock_popen.return_value = _mock_proc(0)
            _run_test_command(["pytest"], timeout=123)

        _, call_kwargs = mock_popen.call_args
        assert "start_new_session" not in call_kwargs
