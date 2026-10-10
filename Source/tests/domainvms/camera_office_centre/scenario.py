#!/usr/bin/env python3
"""The traces of `_notes-ru/camera-office-centre/` — «Камера, офис, центр: первая установка домена в запросах».

    python scenario.py                     every scene, printed
    python scenario.py 03 f2               the scenes whose names start so
    python scenario.py --write [scene…]    …written to `_notes-ru/camera-office-centre/traces/<scene>.txt`

Run from anywhere, in the course's venv (python3.12 with pyyaml, cryptography), with `OBSD_BIN` naming the obsd the
recorders format their volumes with. Each scene is its own run from zero, in a process of its own: the stand is built,
the scenes before it are played with nothing recorded, and then the scene itself is recorded and printed — the way
`three-cameras` took its parts. A failure scene starts from the end of the happy path.

The stand and how it is wired: `stand.py`; what is recorded and how it is printed: `tracing.py`. The scenes are below,
in the order of the notes (the plan's §4.3 and §4.5).
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
COURSE = os.path.dirname(SOURCE)
TRACES = os.path.join(COURSE, "_notes-ru", "camera-office-centre", "traces")
if SOURCE not in sys.path:
    sys.path.insert(0, SOURCE)
os.environ.setdefault("STORE_VOLATILE", "1")
os.environ.setdefault("WATERMARK_DEFAULT", "off")


def _scenes():
    from tests.domainvms.camera_office_centre import scenes
    return scenes.SCENES


def run_one(name: str, brief: bool = False) -> str:
    """One scene, from zero: the stand, the scenes before it unrecorded, then this one recorded."""
    from tests.domainvms.camera_office_centre.stand import Site
    site = Site()
    from tests.domainvms.camera_office_centre import scenes
    order = scenes.before(name)
    with site.log.muted():
        for prior in order:
            scenes.SCENES[prior](site)
    mark = site.log.mark()
    scenes.SCENES[name](site)
    return site.log.render(since=mark) + "\f" + site.log.render(since=mark, brief=True)


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "--one":
        whole = run_one(argv[1])
        sys.stdout.write(whole if "--brief" not in argv else whole.split("\f", 1)[1])
        sys.stdout.flush()
        os._exit(0)                                   # daemon threads of the stand's doors: nothing to wait for
    write = "--write" in argv
    wanted = [a for a in argv if a != "--write"]
    names = [n for n in _scenes() if not wanted or any(n.startswith(w) for w in wanted)]
    if not names:
        print(f"no such scene: {' '.join(wanted)}", file=sys.stderr)
        return 2
    failed = 0
    for name in names:
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "--one", name], capture_output=True, text=True,
                           env={**os.environ, "PYTHONHASHSEED": "0"})
        if p.returncode != 0 or not p.stdout:
            print(f"=== {name}: FAILED\n{p.stderr[-4000:]}", file=sys.stderr)
            failed += 1
            continue
        whole, brief = p.stdout.split("\f", 1)
        if write:
            os.makedirs(TRACES, exist_ok=True)
            for suffix, text in (("", whole), (".brief", brief)):
                with open(os.path.join(TRACES, f"{name}{suffix}.txt"), "w", encoding="utf-8") as f:
                    f.write(text)
            print(f"{name}: {whole.count(chr(10))} lines, brief {brief.count(chr(10))}")
        else:
            print(f"==================== {name} ====================")
            print(whole)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
