"""Where the product's checkout is, for the tests that hold the course to it (`test_spec_parity.py`,
`test_secret_in_table.py`): `W2C_PRODUCT_DIR`, else `vmssubsystem` beside the course's checkout — beside the main
checkout when this one is a git worktree of it. None when there is none: those tests are skipped, the course builds alone.

WHAT IS READ IS THE PRODUCT'S COMMITTED `main` (`W2C_PRODUCT_REF` names another), never its working tree: a file the
product's author is halfway through editing is no file of the product's, and the course's suite failed on it.
`product_file` / `product_files` answer None and [] when the checkout, git or the ref is not there — the tests skip."""
from __future__ import annotations

import os
import subprocess

SOURCE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COURSE = os.path.dirname(SOURCE)
REF = os.environ.get("W2C_PRODUCT_REF", "main")


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


def _git(*args: str) -> bytes | None:
    root = product_dir()
    if root is None:
        return None
    try:
        got = subprocess.run(["git", "-C", root, *args], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return got.stdout if got.returncode == 0 else None


def product_file(path: str) -> bytes | None:
    """The bytes of `path` (relative to the product's root) as its `main` holds them; None when it holds none."""
    return _git("show", f"{REF}:{path}")


def product_files(directory: str, suffix: str = "") -> list[str]:
    """The paths of the files directly in `directory` on the product's `main` that end in `suffix`, sorted."""
    got = _git("ls-tree", "--name-only", REF, directory.rstrip("/") + "/")
    if got is None:
        return []
    return sorted(p for p in got.decode().split("\n") if p and p.endswith(suffix))
