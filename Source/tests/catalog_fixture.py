"""A test's declared catalogue, restored completely when its explicit scope ends."""
from contextlib import contextmanager
import os
from w2cplatform import catalog


@contextmanager
def isolated_catalog(*paths):
    """Load only the requested specs; tests may explicitly load additional fixtures.

This is an opt-in test context/decorator, never a runner hook or a store seed.
ContextDecorator preserves the wrapped function's metadata and signature.
"""
    previous_dir = os.environ.pop(catalog.SPEC_DIR, None)
    with catalog._lock:
        saved = catalog._loaded, catalog._files, catalog.version, catalog._derived
        catalog._loaded, catalog._files, catalog._derived = {}, {}, {}
        catalog.version += 1
    try:
        from w2cplatform.spec import SubsystemSpec
        for path in paths:
            SubsystemSpec.load(path)
        yield
    finally:
        with catalog._lock:
            catalog._loaded, catalog._files, catalog.version, catalog._derived = saved
        if previous_dir is None:
            os.environ.pop(catalog.SPEC_DIR, None)
        else:
            os.environ[catalog.SPEC_DIR] = previous_dir
