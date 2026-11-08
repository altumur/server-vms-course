"""Private check_spec input binding for ADR-VMS-0002; never writes the Owner pin.

The view is an explicit VMS-only input, not a new full-course publication. Its
Platform and Platform history come from a commit; its VMS inputs remain current.
Callers retain the view/manifest as check evidence and decide its later release.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tarfile


PIN_FILE = Path("VMS/PLATFORM_PIN")
PINNED_HOMES = ("Platform", "decisions/history/platform", "decisions/journal/platform")
CURRENT_HOMES = ("VMS", "decisions-vms", "decisions/history/vms", "decisions/journal/vms",
                 "Source/vms", "tools/vms-boundary/source-vms.sha256")


class PinError(ValueError):
    """An explicit input/checking error, never permission to use live Platform."""


@dataclass(frozen=True)
class PlatformPin:
    commit: str
    source_sha256: str


def _repo(root):
    root = Path(root).resolve()
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                            capture_output=True, timeout=30)
    if result.returncode or Path(os.fsdecode(result.stdout).strip()).resolve() != root:
        raise PinError("VMS platform pin needs the complete local course Git root")
    return root


def _git(root, *args):
    root = _repo(root)
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=60)
    if result.returncode:
        raise PinError("cannot read local pinned course object: " + os.fsdecode(result.stderr).strip())
    return result.stdout


def checked_commit(root, value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise PinError("VMS platform pin must be a full lowercase course commit SHA")
    if _git(root, "cat-file", "-t", value).strip() != b"commit":
        raise PinError("VMS platform pin does not name a commit")
    if _git(root, "cat-file", "-t", value + ":Platform").strip() != b"tree":
        raise PinError("VMS platform pin has no Platform tree")
    return value


def _pin_bytes(root):
    path = Path(root).resolve() / PIN_FILE
    try:
        if path.resolve() != path.absolute() or not stat.S_ISREG(path.lstat().st_mode):
            raise PinError("VMS/PLATFORM_PIN must be a regular source file without symlinks")
        return path.read_bytes()
    except OSError as exc:
        raise PinError("cannot read required VMS/PLATFORM_PIN: " + str(exc)) from exc


def read_pin(root):
    data = _pin_bytes(root)
    if not re.fullmatch(rb"[0-9a-f]{40}\n?", data):
        raise PinError("VMS/PLATFORM_PIN must contain exactly one full course commit line")
    commit = checked_commit(root, data.rstrip(b"\n").decode("ascii"))
    return PlatformPin(commit, hashlib.sha256(data).hexdigest())


def verify_owner_pin(root, owner):
    if hashlib.sha256(_pin_bytes(root)).hexdigest() != owner.source_sha256:
        raise PinError("Owner VMS/PLATFORM_PIN changed during this check; no result is reusable")


def _selected_archive_member(name, homes, *, directory=False):
    """Git archive emits the selected homes' ancestor directories as well."""
    if name.is_absolute() or ".." in name.parts:
        return False
    return any(name == PurePosixPath(h) or PurePosixPath(h) in name.parents
               or directory and name in PurePosixPath(h).parents for h in homes)


def _extract_pinned(root, commit, output):
    homes = [name for name in PINNED_HOMES
             if _git(root, "ls-tree", commit, "--", name).strip()]
    _repo(root)  # Assert the exact root before the archive command as well.
    command = ["git", "-C", str(root), "archive", "--format=tar", commit, "--", *homes]
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        try:
            with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
                for member in archive:
                    name = PurePosixPath(member.name)
                    if not _selected_archive_member(name, homes, directory=member.isdir()):
                        raise PinError("pinned archive has an unsafe or unselected source path")
                    target = output.joinpath(*name.parts)
                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                    elif member.isfile():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.extractfile(member) as source, target.open("xb") as dest:
                            shutil.copyfileobj(source, dest)
                        target.chmod(member.mode & 0o777)
                    else:
                        raise PinError("pinned Platform source must contain regular files, not links/devices")
            error = process.stderr.read()
            if process.wait(timeout=60):
                raise PinError("cannot materialize pinned Platform: " + os.fsdecode(error).strip())
        finally:
            # Close only this helper's own archive process if extraction was refused.
            if process.poll() is None:
                process.stdout.close()
                process.wait(timeout=60)
    # Archive attributes must never silently omit or substitute pinned source
    # bytes. Compare the materialized inventory, modes and raw Git blob identity.
    expected = {}
    for entry in _git(root, "ls-tree", "-r", "-z", commit, "--", *homes).split(b"\0"):
        if not entry:
            continue
        metadata, raw_name = entry.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        if kind != b"blob" or mode not in (b"100644", b"100755"):
            raise PinError("pinned Platform input must be a regular Git source blob")
        expected[os.fsdecode(raw_name)] = (mode, oid)
    present = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
    if present != set(expected):
        raise PinError("pinned archive does not preserve the complete selected Git source inventory")
    for name, (mode, oid) in expected.items():
        path = output / name
        data = path.read_bytes()
        actual_oid = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest().encode()
        if actual_oid != oid:
            raise PinError("pinned archive altered raw source bytes: " + name)
        # Git archive applies tar.umask (often 0002); restore the Git tree mode.
        path.chmod(int(mode[-3:], 8))


def materialize_vms_view(root, owner, destination, *, candidate=None, live=False):
    """Return a fresh physical part-view; no source/pin mutation or automatic cleanup.

    A candidate is a separately labelled proposed commit, not a replacement of
    the mandatory Owner pin. The caller must label/report that run separately.
    """
    root, destination = _repo(root), Path(destination).absolute()
    if destination == root or root in destination.parents:
        raise PinError("a VMS part-view must be outside the course source root")
    if destination.parent.resolve() != destination.parent.absolute():
        raise PinError("VMS part-view parent must not contain symlinks")
    verify_owner_pin(root, owner)
    commit = checked_commit(root, candidate) if candidate is not None else owner.commit
    if destination.exists() or destination.is_symlink():
        raise PinError("VMS part-view destination must be fresh")
    destination.mkdir(parents=True)
    if candidate is not None and live:
        raise PinError("candidate and live Platform modes are distinct")
    if not live:
        _extract_pinned(root, commit, destination)
    names = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard",
                 "--", *CURRENT_HOMES, *(PINNED_HOMES if live else ())).split(b"\0")
    copied = []
    for raw in sorted(set(names) - {b""}):
        name = os.fsdecode(raw)
        source, target = root / name, destination / name
        if source.resolve() != source.absolute() or not source.is_file():
            raise PinError("current VMS input is missing or is not a regular source file: " + name)
        data = source.read_bytes()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(stat.S_IMODE(source.stat().st_mode))
        copied.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(),
                       "mode": stat.S_IMODE(source.stat().st_mode)})
    verify_owner_pin(root, owner)
    manifest = {"kind": "VMS_PART_INPUT_NOT_FULL_COURSE_PUBLICATION", "platform_commit": None if live else commit,
                "platform_mode": "live-working-source-diagnostic" if live else "candidate" if candidate else "owner-pin",
                "owner_platform_commit": owner.commit, "owner_pin_sha256": owner.source_sha256,
                "candidate": candidate is not None, "working_source_inputs": copied,
                "pinned_homes": [] if live else list(PINNED_HOMES), "source_root": str(root),
                "source_commit": _git(root, "rev-parse", "HEAD").decode().strip(),
                "view_files": [{"path": p.relative_to(destination).as_posix(),
                                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                                "mode": stat.S_IMODE(p.stat().st_mode)}
                               for p in sorted(destination.rglob("*")) if p.is_file()]}
    (destination / ".vms-platform-input.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
