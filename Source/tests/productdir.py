"""Where the product's checkout is, for the tests that hold the course to it (`test_spec_parity.py`,
`test_secret_in_table.py`): `W2C_PRODUCT_DIR`, else `vmssubsystem` beside the course's checkout — beside the main
checkout when this one is a git worktree of it. None when there is none: those tests are skipped, the course builds alone."""
from __future__ import annotations

import os

SOURCE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COURSE = os.path.dirname(SOURCE)


def _main_checkout(root: str) -> str:
    """The checkout `root` is a worktree of (its `.git` is a file naming `<main>/.git/worktrees/<name>`), else `root`."""
    git = os.path.join(root, ".git")
    if os.path.isfile(git):
        with open(git) as f:
            line = f.read().strip()
        if line.startswith("gitdir:") and "/.git/worktrees/" in line:
            return line[len("gitdir:"):].strip().split("/.git/worktrees/")[0]
    return root


def product_dir() -> str | None:
    given = os.environ.get("W2C_PRODUCT_DIR")
    if given:
        return given if os.path.isdir(given) else None
    for root in dict.fromkeys((COURSE, _main_checkout(COURSE))):
        cand = os.path.join(os.path.dirname(root), "vmssubsystem")
        if os.path.isdir(cand):
            return cand
    return None
