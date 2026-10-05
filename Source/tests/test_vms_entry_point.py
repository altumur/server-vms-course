"""The VMS's entry point and the test run's signals. Moved from `test_pass_failures.py` (the boundary's step 5): the
platform's half — the controller loop's helper runs its pass whatever signal came before — is there, on testsub."""


def test_importing_the_entry_point_takes_none_of_the_runners_signals():
    """The other half, and the one the fix had no test for: `vms.__main__` imported — as this module imports it, and
    six others — installs no handler. One installed at import swallows a SIGTERM or SIGINT sent to the test run,
    which then goes on with `stop` set. The handlers this process has now are not the entry point's, and the lines
    that install them are under `if __name__ == "__main__"`."""
    import inspect
    import signal
    import vms.__main__ as m
    for s in (signal.SIGTERM, signal.SIGINT):
        assert getattr(signal.getsignal(s), "__module__", None) != m.__name__, f"importing vms.__main__ took {s.name}"
    src = inspect.getsource(m)
    assert "signal.signal(" not in src.split('if __name__ == "__main__":')[0], "a handler installed at import"
    assert "signal.signal(" in src.split('if __name__ == "__main__":')[1]          # …and the process still stops on SIGTERM
