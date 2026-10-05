#!/usr/bin/env python3
"""Run the millisecond suite without pytest (the appliance image has none):
    python3 tests/run.py [test_module … | console]   # from Source/; no names: every module, and the console's
Discovers test_* functions in tests/test_*.py, runs coroutines with
asyncio.run, prints one line per test like Lesson 21 does.

The console's own tests are JavaScript in jsdom (`tests/console/`: the platform's console module, its page, the VMS's
page): each `*.test.js` is one test here, run by `node` when there is one and `tests/console/node_modules/jsdom` beside
it (`npm install` there, once). Without them they are skipped — said with the reason and counted in the last line, so
that a green run never means the console's tests did not run."""
from __future__ import annotations

import asyncio
import importlib
import inspect
import os
import signal
import sys
import traceback

# The file store is durable unless told otherwise: every write is flushed to the medium, some fifteen
# milliseconds each on a laptop (`w2cplatform/variables.py`). A suite makes thousands; it says it is a test.
# The one test of the barriers asks for a durable store by name.
os.environ.setdefault("STORE_VOLATILE", "1")
os.environ.setdefault("WATERMARK_DEFAULT", "off")     # a suite runs on a disk as full as it happens to be: no cutting fixtures for that

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# THE RUN'S TEMP ROOT (`tests/runroot.py`): made before any test module is imported, so that every `mkdtemp` of the run
# — and every child's, through TMPDIR — lands under it; removed at exit, a dead run's reaped by the next.
from tests import runroot  # noqa: E402
RUN_ROOT = runroot.enter()

import w2cplatform  # noqa: E402,F401

try:
    import pydantic  # noqa: F401
except ImportError:
    import types
    class _BaseModel:
        def __init__(self, **kw): self.__dict__.update(kw)
    _pyd = types.ModuleType("pydantic"); _pyd.BaseModel = _BaseModel
    sys.modules["pydantic"] = _pyd

try:
    import pytest  # noqa: F401
except ImportError:
    import contextlib
    import types

    class _Skip:
        def __init__(self, cond, reason=""):
            self.name, self.args, self.kwargs = "skipif", (cond,), {"reason": reason}

    @contextlib.contextmanager
    def _raises(exc):
        try:
            yield
        except exc:
            return
        raise AssertionError(f"{exc.__name__} not raised")

    shim = types.ModuleType("pytest")
    shim.mark = types.SimpleNamespace(skipif=_Skip)
    shim.raises = _raises
    sys.modules["pytest"] = shim


class _Monkeypatch:
    def __init__(self): self._undo = []
    def setattr(self, obj, name, value):
        self._undo.append((obj, name, getattr(obj, name))); setattr(obj, name, value)
    def undo(self):
        for obj, name, old in reversed(self._undo): setattr(obj, name, old)


# THE RUNNER'S OWN SIGNALS (the review's sixth pass). Code under test that installs a handler for SIGTERM or SIGINT —
# at import, as `vms/__main__` did until the fifth pass, or inside a test — takes them from the RUN: a signal sent to
# stop it (a `kill`, a terminal's interrupt, a tool's timeout) is swallowed, the run goes on, and whatever the
# handler set fails some later test that passes alone (`test_pass_failures.py` says what that looked like). So the
# handlers are compared after every import and every test: a change fails that module or test by name, and is undone.
def _signals_taken(ours: dict) -> list[str]:
    taken = [s.name for s, h in ours.items() if signal.getsignal(s) is not h]
    for s, h in ours.items():
        if h is not None and signal.getsignal(s) is not h:
            signal.signal(s, h)
    return taken


# THE CONSOLE'S TESTS (the boundary's step 3): `node` on each `tests/console/*.test.js`, which prints its checks and
# `FAILED: …` naming those that did not hold. A test that crashes, hangs past two minutes or prints FAILED fails.
CONSOLE = "console"


def console_tests(here: str) -> tuple[int, int, str]:
    """(passed, failed, why they were not run — "" when they were)."""
    import shutil
    import subprocess
    d = os.path.join(here, CONSOLE)
    node = shutil.which("node")
    if node is None:
        return 0, 0, "no node on PATH"
    if not os.path.isdir(os.path.join(d, "node_modules", "jsdom")):
        return 0, 0, "no jsdom: run npm install in tests/console"
    passed = failed = 0
    for f in sorted(x for x in os.listdir(d) if x.endswith(".test.js")):
        try:
            got = subprocess.run([node, f], cwd=d, capture_output=True, text=True, timeout=120)
            out, ok = got.stdout + got.stderr, got.returncode == 0
        except subprocess.TimeoutExpired:
            out, ok = "did not finish in 120 s", False
        bad = [line for line in out.splitlines() if line.startswith("FAILED")]
        if ok and not bad:
            print(f"{CONSOLE}/{f} ... OK"); passed += 1
        else:
            print(f"{CONSOLE}/{f} ... FAIL"); print("\n".join((bad or out.splitlines())[-6:])); failed += 1
    return passed, failed, ""


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    files = sorted(f for f in os.listdir(here) if f.startswith("test_") and f.endswith(".py"))
    want = set(sys.argv[1:])                                 # `run.py test_a test_b`: those modules only
    if want - {f[:-3] for f in files} - {CONSOLE}:
        print(f"no such module here: {', '.join(sorted(want - {f[:-3] for f in files} - {CONSOLE}))}"); return 2
    files = [f for f in files if not want or f[:-3] in want]
    print(f"temp: {RUN_ROOT}")
    passed = failed = skipped = 0
    ours = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
    for f in files:
        try:
            mod = importlib.import_module(f"tests.{f[:-3]}")
        except Exception:                                  # noqa: BLE001 — a module that does not import fails, and the rest still run
            print(f"{f} ... FAIL (does not import)"); traceback.print_exc(); failed += 1
            continue
        took = _signals_taken(ours)
        if took:
            print(f"{f} ... FAIL (importing it took the runner's {', '.join(took)}: a signal sent to the run would be swallowed)")
            failed += 1
        mark = getattr(mod, "pytestmark", None)
        if mark is not None and getattr(mark, "name", "") == "skipif" and mark.args and mark.args[0]:
            print(f"{f}: skipped ({mark.kwargs.get('reason', '')})"); skipped += 1; continue
        for name, fn in inspect.getmembers(mod, inspect.isfunction):
            if not name.startswith("test_") or fn.__module__ != mod.__name__:
                continue
            mp = _Monkeypatch()
            kwargs = {"monkeypatch": mp} if "monkeypatch" in inspect.signature(fn).parameters else {}
            try:
                res = fn(**kwargs)
                if inspect.iscoroutine(res):
                    asyncio.run(res)
                took = _signals_taken(ours)
                if took:
                    raise AssertionError(f"it left its own handler for {', '.join(took)}: a signal sent to the run would be swallowed")
                print(f"{f}::{name} ... OK"); passed += 1
            except Exception:                              # noqa: BLE001
                print(f"{f}::{name} ... FAIL"); traceback.print_exc(); failed += 1
            finally:
                mp.undo()
                _signals_taken(ours)
    why = ""
    if not want or CONSOLE in want:
        p, f, why = console_tests(here)
        passed, failed = passed + p, failed + f
        if why:
            print(f"{CONSOLE}: skipped ({why})"); skipped += 1
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped" + (f"; skipped: {CONSOLE} ({why})" if why else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
