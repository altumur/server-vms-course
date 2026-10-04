"""python3 -m w2cplatform controller <sub> | resource — the platform's own processes, for whatever subsystems the
directory `SPEC_DIR` holds specs of (`host.py`; the boundary's step 5). Nothing here names a subsystem: the controller
of `<sub>` is the platform's controller run from `<sub>.subsystem.yaml`, the resource is the platform's resource.

    SPEC_DIR=/app/specs python3 -m w2cplatform controller <sub>
    SPEC_DIR=/app/specs python3 -m w2cplatform resource
"""
from __future__ import annotations

import logging
import os
import signal
import sys

from .host import main, stop

if __name__ == "__main__":
    # Only when run: a module imported (the tests) must not take the process's signals (the review's fifth pass).
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(name)s %(levelname)s %(message)s")
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    sys.exit(main(sys.argv[1:]))
