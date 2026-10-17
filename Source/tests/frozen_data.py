"""Specification inputs for the frozen Python tests, with unrelated fixtures kept current."""
from functools import lru_cache
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
import subprocess
import tempfile

FROZEN_TESTDATA_REF = "a0bd9e53"  # старый Python заморожен, ADR-0080 доп. 16
_ROOT = Path(__file__).resolve().parents[2]
_PREFIX = "Source/tests/testdata"


def _frozen(relative):
    path = PurePosixPath(relative)
    return path.parts[0] == "acceptance" or (len(path.parts) == 1 and
        (path.suffix == ".tsv" or fnmatchcase(path.name, "testsub*.subsystem.yaml")))


@lru_cache(maxsize=1)
def _snapshot():
    temporary = tempfile.TemporaryDirectory(prefix="frozen-testdata-")
    target = Path(temporary.name) / "testdata"
    target.mkdir()
    (target / "acceptance").mkdir()
    for entry in (_ROOT / _PREFIX).iterdir():
        if not _frozen(entry.name):
            (target / entry.name).symlink_to(entry.resolve(), target_is_directory=entry.is_dir())
    files = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", "-z", FROZEN_TESTDATA_REF, "--", _PREFIX],
        cwd=_ROOT, encoding="utf-8")
    for name in filter(None, files.split("\0")):
        relative = PurePosixPath(name).relative_to(_PREFIX)
        if _frozen(str(relative)) and relative.parts[0] != "acceptance":
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(subprocess.check_output(
                ["git", "show", f"{FROZEN_TESTDATA_REF}:{name}"], cwd=_ROOT))
    return temporary


def frozen_testdata(relative=""):
    relative = PurePosixPath(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("not a testdata path")
    destination = Path(_snapshot().name) / "testdata" / relative
    if relative.parts and relative.parts[0] == "acceptance" and not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(subprocess.check_output(
            ["git", "show", f"{FROZEN_TESTDATA_REF}:{_PREFIX}/{relative}"], cwd=_ROOT))
    return destination
