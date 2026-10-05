"""A run of a suite leaves nothing in the temp dir (`tests/runroot.py`).

The suites made a temp dir per box, per cluster, per card and removed none: a machine's temp dir held some 400 000 of
them on 5 October, and the same litter had stopped the nightly runs on 3–4 October. Each runner now keeps its run's
temp dirs under one root of its own, removes it at exit and reaps the roots of runs that died. Proved here on a real
run of the runner, in a temp dir of the test's own standing for the system's."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import threading
import time

from tests import runroot

SOURCE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = "test_obsd"          # quick, a temp dir per test, and a child process (the daemon) with its own under TMPDIR


def _dead_pid() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def _base(name: str) -> str:
    """The child run's "system temp dir": under this run's root, short enough to be a root's base."""
    base = os.path.join(tempfile.gettempdir(), name)
    os.mkdir(base)
    assert runroot.root_for(99999, base).startswith(base + os.sep), "run this through a runner: its root is short"
    return base


class _Watch:
    """The directories any run root under `base` held while the child ran, looked at every 50 ms."""

    def __init__(self, base: str):
        self.base, self.seen, self.done = base, set(), threading.Event()
        self.t = threading.Thread(target=self._loop, daemon=True)
        self.t.start()

    def _loop(self):
        while not self.done.is_set():
            for root, dirs, _ in os.walk(self.base):
                if os.path.basename(root).startswith(runroot.PREFIX):
                    self.seen.update(dirs)
            time.sleep(0.05)

    def stop(self) -> set[str]:
        self.done.set()
        self.t.join(5)
        return self.seen


def _child(base: str, *modules: str) -> subprocess.Popen:
    env = dict(os.environ, TMPDIR=base, PYTHONUNBUFFERED="1")
    return subprocess.Popen([sys.executable, os.path.join("tests", "run.py"), *modules], cwd=SOURCE, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def test_a_root_too_long_for_a_socket_goes_under_tmp():
    """macOS's temp dir is 48 bytes long, and a unix socket's path is under 104: the root goes to /tmp then."""
    assert runroot.root_for(123, "/tmp") == "/tmp/w2c-tests-123"
    assert runroot.root_for(123, "/var/folders/rj/0mbpl0_d5jg43d1vmv_83cx00000gn/T") == "/tmp/w2c-tests-123"
    assert len(runroot.root_for(99999).encode()) <= runroot.ROOT_MAX


def test_a_process_the_tests_start_makes_its_temp_dirs_under_the_run_root():
    """obsd, a worker, a shell script: whatever a test starts inherits TMPDIR, and its temp dirs go with the run's."""
    here = subprocess.run([sys.executable, "-c", "import tempfile; print(tempfile.gettempdir())"], capture_output=True,
                          text=True, check=True).stdout.strip()
    sh = subprocess.run(["sh", "-c", 'mktemp -d "${TMPDIR:?}/sh.XXXXXX"'], capture_output=True, text=True, check=True).stdout.strip()
    assert here == tempfile.gettempdir() and os.path.basename(here).startswith(runroot.PREFIX), here
    assert os.path.dirname(sh) == here, sh


def test_a_selected_run_leaves_nothing_in_the_temp_dir_and_reaps_a_dead_runs_root():
    """A run of the runner: its temp dirs and its daemon's are under its root while it runs, and after it the temp dir
    holds what it held before, less the root of a run that died (SIGKILL: nothing removed it). A root whose process is
    alive, and directories that are no run's root, stay."""
    base = _base("b1")
    dead = os.path.join(base, f"{runroot.PREFIX}{_dead_pid()}")
    os.makedirs(os.path.join(dead, "vmsserver-abcd1234", "archive"))
    open(os.path.join(dead, "vmsserver-abcd1234", "archive", "x"), "w").close()
    keep = [f"{runroot.PREFIX}{os.getpid()}", f"{runroot.PREFIX}12x", "vmsserver-abcd1234"]   # alive; not a pid; a test's
    for k in keep:
        os.mkdir(os.path.join(base, k))
    watch = _Watch(base)
    p = _child(base, MODULE)
    out, _ = p.communicate(timeout=600)
    seen = watch.stop()
    assert p.returncode == 0 and "0 failed" in out, out[-2000:]
    root = out.splitlines()[0].removeprefix("temp: ")
    assert os.path.dirname(root) == base and os.path.basename(root).startswith(runroot.PREFIX), out[:200]
    assert any(d.startswith("obsd-") for d in seen), seen            # the daemon's dir was under the root
    assert sorted(os.listdir(base)) == sorted(keep), os.listdir(base)


def test_a_run_stopped_by_sigterm_removes_its_root_too():
    """SIGTERM's default ends a process without `atexit`: the runner turns it into an exit, its daemon is stopped and
    its root removed — a tool's timeout leaves nothing behind either."""
    base = _base("b2")
    p = _child(base, MODULE)
    lines = []
    for line in p.stdout:                                             # the first test passed: the daemon is up
        lines.append(line)
        if line.rstrip().endswith("... OK"):
            break
    assert p.poll() is None and os.listdir(base), "".join(lines)
    p.send_signal(signal.SIGTERM)
    out, _ = p.communicate(timeout=120)
    assert p.returncode == 128 + signal.SIGTERM, (p.returncode, "".join(lines) + out[-2000:])
    assert os.listdir(base) == [], os.listdir(base)
