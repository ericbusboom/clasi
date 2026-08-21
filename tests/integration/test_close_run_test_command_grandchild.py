"""Real-process regression test (032/006): a timed-out test command must
not leave a grandchild process running.

``close.py``'s ``_run_test_command`` runs the sprint's configured test
command. The command is commonly a wrapper -- ``uv run pytest``, ``npm
test``, ``poetry run pytest`` -- whose real work happens in a grandchild
process, not the direct child ``_run_test_command`` spawns. A timeout
that kills only the direct child leaves that grandchild running. Observed
live at close of sprint 031: an abandoned ``uv run pytest`` was still
consuming CPU 32 minutes after its ``close_sprint`` call had been aborted
client-side, and had to be killed by hand.

The unit tests in ``tests/unit/test_close_run_test_command.py`` mock
``subprocess.Popen`` and assert ``os.killpg`` is called with the right
arguments -- they prove the code takes the right *actions*, not that a
real grandchild process actually dies. This test spawns real processes
(via ``sh -c``) to close that gap: a direct child that backgrounds a
long-running grandchild before itself blocking past the timeout, then
asserts the grandchild's pid is no longer alive afterward.

Design note -- why this runs _run_test_command in a background thread
with a bounded join, not just a plain call: the grandchild inherits the
direct child's stdout/stderr pipe (the same way a real `pytest` process
run via `uv run` would). If the process GROUP is properly killed, every
process holding that pipe open is dead, so `Popen.communicate()`'s
post-kill drain hits EOF almost immediately. But if only the direct
child is killed (the historical `subprocess.run` defect), the surviving
grandchild keeps the pipe open for its own remaining lifetime --
`communicate()`, and therefore `_run_test_command` itself, blocks for
that whole time. A plain call would still eventually return once the
grandchild finished on its own 60s sleep, and the assertions below would
then find it already dead -- an accidental pass that took a full minute
and proved nothing. Bounding the wait via a thread join turns "still
blocked because a grandchild kept the pipe open" into a fast, explicit
failure instead.

Marked ``slow`` (real timing, real process spawn/kill -- not a unit-level
mock) so it's excluded from the default ``-m 'not slow'`` addopts and
must be run explicitly, e.g.:

    uv run pytest tests/integration/test_close_run_test_command_grandchild.py -v -m slow
"""

from __future__ import annotations

import os
import subprocess
import threading
import time

import pytest

from clasi.close import _run_test_command


@pytest.mark.slow
def test_timed_out_command_kills_grandchild_process(tmp_path):
    """A grandchild spawned by the direct child must not survive a
    _run_test_command timeout -- the whole process group is killed, not
    just the direct child (the defect subprocess.run's own timeout
    handling has)."""
    pid_file = tmp_path / "grandchild.pid"

    # The direct child (`sh`) backgrounds a long sleep -- the grandchild,
    # standing in for the real `pytest` process a wrapper like `uv run`
    # would fork -- writes its own pid to a file essentially immediately,
    # then the direct child itself blocks well past the timeout below so
    # the TimeoutExpired path is actually exercised. (If the direct child
    # exited quickly on its own, _run_test_command would never time out
    # and the kill path -- the thing under test -- would never run.)
    cmd = [
        "sh",
        "-c",
        f"sleep 60 & echo $! > {pid_file}; sleep 60",
    ]

    outcome: dict = {}

    def _call():
        try:
            _run_test_command(cmd, timeout=1)
        except BaseException as exc:  # capture across the thread boundary
            outcome["exc"] = exc

    thread = threading.Thread(target=_call, daemon=True)
    thread.start()
    # See module docstring: 10s is generous slack over the 1s timeout for
    # a correctly-group-killed process, but far short of the grandchild's
    # own 60s sleep -- enough to tell "killed promptly" apart from "still
    # blocked on a surviving grandchild" without waiting out the full 60s.
    thread.join(timeout=10)
    assert not thread.is_alive(), (
        "_run_test_command did not return within 10s of its 1s timeout -- "
        "it is still blocked (most likely in Popen.communicate()'s "
        "post-kill drain, waiting on a grandchild that still holds the "
        "output pipe open because it was never actually killed)"
    )
    assert isinstance(outcome.get("exc"), subprocess.TimeoutExpired), (
        f"expected subprocess.TimeoutExpired, got: {outcome.get('exc')!r}"
    )

    # The pid-file write happens at the very start of the child's
    # execution (well before the 1-second timeout), but poll briefly
    # rather than assume it landed before we look.
    deadline = time.monotonic() + 5
    grandchild_pid = None
    while time.monotonic() < deadline:
        if pid_file.exists():
            content = pid_file.read_text().strip()
            if content:
                grandchild_pid = int(content)
                break
        time.sleep(0.05)
    assert grandchild_pid is not None, (
        "grandchild never reported its pid -- test setup is broken, "
        "not exercising the kill path at all"
    )

    # os.killpg's SIGKILL is not necessarily instantaneous from the
    # caller's perspective (signal delivery + kernel reaping); poll
    # briefly for the grandchild to actually disappear rather than
    # checking exactly once. By this point the thread has already
    # returned, so this window just accounts for reaping latency, not
    # the kill itself.
    alive = True
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.kill(grandchild_pid, 0)
        except ProcessLookupError:
            alive = False
            break
        except PermissionError:
            # Exists but we can't signal it -- still alive for our purposes.
            pass
        time.sleep(0.05)

    assert not alive, (
        f"grandchild pid {grandchild_pid} survived _run_test_command's "
        "timeout -- process-group kill did not reach it (this is exactly "
        "the sprint-031 defect: an abandoned `uv run pytest` still "
        "running 32 minutes after its close_sprint call was aborted)"
    )
