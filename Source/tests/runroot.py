"""One temp root per run of a suite: every temp directory a test makes goes under it, and it goes when the run does.

The tests make a directory per box, per cluster, per card, per volume (`tempfile.mkdtemp`) and remove none of them:
a run left thousands, the system's temp dir held some 400 000 of them on 5 October, and the same litter stopped the
nightly runs on 3–4 October. Removing each test's own would be a line in a hundred places, forgotten in the
hundred-and-first; so the runner owns the place instead (as the product's nightly does for its suites):

    enter()   called by a runner before anything is imported: makes `<base>/w2c-tests-<pid>` and points
              `tempfile.tempdir` at it — every `mkdtemp` in this process — and `TMPDIR` — every child the tests
              start: obsd, a worker, a shell script. First it reaps the roots of runs whose process is gone: a run
              killed by SIGKILL removed nothing, and the next run is the one that can
    at exit   the root is removed (`atexit`): after every test, on a failure, on an interrupt, on SIGTERM (the runner
              turns it into an exit). Daemons the tests started register their own stop with `atexit` later, so
              they stop first and nothing writes into the root while it goes

`<base>` is the system's temp dir when the root fits there, else `/tmp`: a unix socket's path is under 104 bytes, and
the deepest socket a suite makes is 58 bytes under the root (`test_units`' macOS box, its `reccontroller.sock`), so
the root is at most 45 bytes. macOS's own temp dir (`/var/folders/…/T`, 48 bytes) is too long for that."""
from __future__ import annotations

import atexit
import os
import re
import shutil
import signal
import sys
import tempfile
import time

PREFIX = "w2c-tests-"
ROOT_MAX = 45                                  # bytes: 104 for a socket's path, minus the deepest the suites make under it
_ROOT = re.compile(rf"^{PREFIX}(\d+)$")        # a pid and nothing else: never a test's own `mkdtemp` name

_entered: str | None = None


def root_for(pid: int, base: str | None = None) -> str:
    """Where the run of process `pid` keeps its temp dirs: under `base` (the system's temp dir) if that fits a socket."""
    root = os.path.join(base or tempfile.gettempdir(), f"{PREFIX}{pid}")
    return root if len(root.encode()) <= ROOT_MAX else os.path.join("/tmp", f"{PREFIX}{pid}")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:                    # another user's process: alive, and not ours to judge
        return True
    return True


def reap(base: str) -> list[str]:
    """Remove the run roots under `base` whose process is gone — ours only (the uid), named by a pid only. A root whose
    pid now belongs to another process waits for that one to end. Returns what it removed."""
    gone = []
    try:
        entries = list(os.scandir(base))
    except OSError:
        return gone
    for e in entries:
        m = _ROOT.match(e.name)
        if not m:
            continue
        try:
            if not e.is_dir(follow_symlinks=False) or e.stat(follow_symlinks=False).st_uid != os.getuid():
                continue
        except OSError:
            continue
        if not _alive(int(m.group(1))):
            shutil.rmtree(e.path, ignore_errors=True)
            gone.append(e.path)
    return gone


def leave(root: str | None = None) -> None:
    """Remove the run's root. A child that outlived its test may still write into it for a moment: try again then;
    what is left after that, the next run reaps — this process is gone by then."""
    root = root or _entered
    if not root:
        return
    for _ in range(20):
        shutil.rmtree(root, ignore_errors=True)
        if not os.path.lexists(root):
            return
        time.sleep(0.1)


def _exit_on_term(signum, frame):              # noqa: ARG001 — SIGTERM's default ends the process without `atexit`
    sys.exit(128 + signum)


def enter() -> str:
    """Make this process's run root, point the temp dir at it, reap the dead runs' roots, remove it at exit."""
    global _entered
    if _entered:
        return _entered
    root = root_for(os.getpid())
    reap(os.path.dirname(root))
    shutil.rmtree(root, ignore_errors=True)    # a dead run's that had our pid
    os.makedirs(root, mode=0o700)
    tempfile.tempdir = root
    os.environ["TMPDIR"] = root
    _entered = root
    atexit.register(leave, root)
    if signal.getsignal(signal.SIGTERM) is signal.SIG_DFL:
        signal.signal(signal.SIGTERM, _exit_on_term)
    return root
