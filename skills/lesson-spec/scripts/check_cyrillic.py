#!/usr/bin/env python3
"""ADR-0121 (8): Cyrillic letters in the course's published source and exports.

Read-only by default. --shrink only lowers the explicit per-file debt; --ready
adds a clean directory to the readiness declarations in that same registry.
No product imports, network access, or execution of source files.
"""

import argparse
import hashlib
import os
import re
import stat
import subprocess
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath

DEBT = Path(__file__).resolve().parents[1] / "cyrillic-debt.tsv"
# Course-side canonical source and generator homes; an export is checked in full.
# ADR-0083 (115): Source holds immutable witnesses, not canonical inputs.
SCOPES = ("Platform", "VMS", "tools/normgen")
# ADR-VMS-0003 Decision2б: exact public upstream/literal carriers selected by
# Sourcec8eafc05626112db4c2003b416f762055deaef65, source-owned inbox
# decisions/inbox/2026-11-08-запрос-vms-v11-english-cb728a4.md.
# Each SHA binds the whole raw file, not a Cyrillic budget or a path pattern.
EXACT_SOURCE_FILES = {
    'VMS/11-backend/README.md': '2d77a4666410b1121226bdfd49e00c843bb15424d4d03800b62b438671fffd81',
    'VMS/11-backend/acceptance/4/README.md': 'e5bfada38fd0b2db93b925c1398466c45bad46355137ac89c7363a5367154ee6',
    'VMS/11-backend/acceptance/4/scenarios.tsv': 'c7f7c12b7c7d7f376fbf929731432f259220333cbbef234ec7028e1009a1cbfe',
    'VMS/11-backend/acceptance/8/README.md': '954504f48ef6d17b6446819701be91c60f4288da21a84e1d77ca8c1fbd724217',
    'VMS/11-backend/acceptance/8/scenarios.tsv': '14c16a8807b4ccd682c35bd4a0fc460e7088df7a04f0fa1e7085adf6ee6fa2bd',
    'VMS/11-backend/backend.shell.html': '90e9cd59cb70207a785e23da943fb0785c9f80d382afecfae4d94a0bce9a05ff',
    'VMS/11-backend/consolem.openapi.json': '200d203d4197776892e66a32126998bc8cf0b79a9986ef7ac144c6af230f7124',
    'VMS/11-backend/data/mapping.tsv': '5cee4b13d073232991149f67d8b5457ee48fefcfd74a3a2b8394044bc693ac39',
    'VMS/11-backend/data/profile-tests.tsv': 'f5265ab14f0166e9875667c2f652a02bcac1e52c16270b96082e6d5088081842',
    'VMS/11-backend/harness/export/system.md': 'ea03b6af2ec417198fd82e7ac9780e1c8e7c7fa175b90ddb9f4ec72da1322c31',
    'VMS/11-backend/harness/route/system.md': '79619d6b8e234e14621905b9bf37882788f8ae2482286775bb044eba960d8e8e',
    'VMS/11-backend/harness/rules/words.json': 'b8346d50e7d96ec9d60d7d210e433dddc3c96eb71b29ce31f13ec777f4f69531',
    'VMS/11-backend/harness/words.json': '839e11c287f09537587a9426a8311306bbc8f00da09491ca0c5a51143b5af5bd',
    'VMS/11-backend/spec/11.11-backend.norms.md': '0ad89d2862e4461231aed5019d7d1bb24cb702e2ce4f7674aa89749558032b31',
    'VMS/11-backend/spec/11.13-backend.norms.md': '1b2ff6fa33b54cdd2523c7f28f424f6a292aab48e45de1d2d16509737c0226e3',
    'VMS/11-backend/spec/11.14-backend.norms.md': '89741b3e8ab7808750892a91d505d164f31ae46f9a04d27d3d0726485d79fdaf',
    'VMS/11-backend/spec/11.15-backend.norms.md': 'b3a775e38a14f3c6dcd5c57819ef463b35ed1ff0762ecabe683e4cfa6f76ce60',
    'VMS/11-backend/spec/11.2-backend.norms.md': 'a547c01f0689df032a0f5a6e08be517dda40f08742bb03a415813becc00573ad',
    'VMS/11-backend/spec/11.3-backend.norms.md': '06dc4d60dc6a75ee3c9ec766cf42307b5a85684ec3f5e75a7f0c6350af9c1853',
    'VMS/11-backend/spec/11.4-backend.norms.md': 'a1082d07605891af5f6ed86eff0edd99455e0c474b21c6dfd59b94947dc6cd53',
    'VMS/11-backend/spec/11.6-backend.norms.md': 'c7312623acd199b743387731ca17601e3a491b7a086b25037ca744177c4232b9',
    'VMS/11-backend/spec/11.7-backend.norms.md': '23e9ccc6b3bfb70ab839d9f16d9b7d4a19ee1911e41be0f5c56c7d53e51f4807',
    'VMS/11-backend/spec/11.8-backend.norms.md': '8d99bcb4bab50805b69e16b09d09893f3d4c3bf414d34a6e32daa33aa9713513',
    'VMS/11-backend/vectors/plan-check/README.md': 'ea5d2eb3ffea9cc7f58e6d604a56f1f9cb5aa68264f236e07567a6e57ca9253b',
    'VMS/11-backend/vectors/plan-check/cases.json': '08f03de9e08482e1393cba4a9fd81a17cc8015d23edaf43c691ab368c728ae27',
    'VMS/11-backend/vectors/plan-check/text.json': 'cb4479e0518477b195511e17b20f4185c7ba1570302539c8fc18efc48e4468d3',
    'VMS/11-backend/vectors/plan-check/vms.console.json': '9ab2960f009d45939b1d96deaa951d2a79299c79246dab6ea331dae84cd482a7',
    'VMS/11-backend/vectors/rules-neutral/README.md': 'a898f5384a9c5f33910c83e258e0e143020db5cacdf94f0e227c0465314cbd18',
    'VMS/11-backend/vectors/rules-neutral/cases.json': 'f3c44c701ba5f02b08da7e9e1518ad30939085aec008a53a06e8a02835f3c308',
    'VMS/11-backend/vectors/rules-words/README.md': '7cf0e4223a58a9c97ed73a53067ec5912fc0edf7ce687ffda60ab080a8d39629',
    'VMS/11-backend/vectors/rules-words/cases.json': '486a14c79f40fc5f77526d53ca9c452ef8c25356fa3a8fc360a6c835bfe880a2',
}
EXPORT_MARKERS = ("Platform/COURSE_COMMIT", "VMS/COURSE_COMMIT")
LOCALIZATION = "Platform/07-console-module/data/localization.tsv"
HEADER = "kind\tpath\tletters"
# Unicode 17.0.0, Script=Cyrillic AND General_Category=L* (449 letters).
# https://www.unicode.org/Public/17.0.0/ucd/Scripts.txt
# SHA256 9f5e50d3abaee7d6ce09480f325c706f485ae3240912527e651954d2d6b035bf
# Pinned ranges also cover letters unknown to Python 3.12's Unicode database.
LETTER_RANGES = ((0x0400, 0x0481), (0x048A, 0x052F), (0x1C80, 0x1C8A),
                 (0x1D2B, 0x1D2B), (0x1D78, 0x1D78), (0xA640, 0xA66E),
                 (0xA67F, 0xA69D), (0x1E030, 0x1E06D))
LETTERS = re.compile("[" + "".join(chr(low) + "-" + chr(high) for low, high in LETTER_RANGES) + "]")


def scoped(name, *, export=False):
    return export or any(name == scope or name.startswith(scope + "/") for scope in SCOPES)


def mirror(name):
    # Module, common and lesson mirrors (ADR-0124); not a normgen escape hatch.
    parts = PurePosixPath(name).parts
    return (len(parts) >= 3 and parts[0] in {"Platform", "VMS"} and parts[1] == "ru" or
            len(parts) >= 4 and parts[0] in {"Platform", "VMS"} and parts[2] == "ru" and
            (parts[1] == "common" or re.fullmatch(r"[0-9]{2}-[^/]+", parts[1]) is not None))


def safe_name(name, *, export=False):
    parts = name.split("/")
    return bool(name) and not any(p in {"", ".", ".."} for p in parts) and "\\" not in name and scoped(name, export=export)


def load_debt(path, *, export=False):
    debt, ready, errors = {}, set(), []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return debt, ready, [f"{path}: cannot read Cyrillic debt: {exc}"]
    records = [(line, text) for line, text in enumerate(lines, 1) if text and not text.startswith("#")]
    if not records or records[0][1] != HEADER:
        return debt, ready, [f"{path}: expected {HEADER!r}"]
    seen = set()
    for line, text in records[1:]:
        cells = text.split("\t")
        if len(cells) != 3:
            errors.append(f"{path}:{line}: expected kind, path, letters")
            continue
        kind, name, count = cells
        if not safe_name(name, export=export) or mirror(name + "/_") or name in EXACT_SOURCE_FILES or name in seen:
            errors.append(f"{path}:{line}: unsafe, excluded or duplicate path {name!r}")
            continue
        seen.add(name)
        try:
            number = int(count) if count.isascii() and count.isdecimal() else 0
        except ValueError:
            number = 0
        if kind == "debt" and number > 0:
            debt[name] = number
        elif kind == "ready" and count == "-":
            ready.add(name)
        else:
            errors.append(f"{path}:{line}: expected debt with positive integer, or ready with -")
    for name in debt:
        if any(name == unit or name.startswith(unit + "/") for unit in ready):
            errors.append(f"{path}: debt {name} is under a ready unit")
    return debt, ready, errors


def export_mode(root, explicit=None):
    if explicit is not None:
        return explicit
    markers = (*EXPORT_MARKERS, "COURSE_COMMIT")
    if any((root / name).exists() or (root / name).is_symlink() for name in markers):
        return True
    # A deleted tracked marker must not narrow the check back to course scope.
    try:
        result = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", *markers],
                                capture_output=True)
        return result.returncode == 0 and bool(result.stdout)
    except OSError:
        return False                       # source_files reports a missing Git tool


def export_marker_errors(root):
    """Two operator pins, exact full Git hash + LF; no root alias or symlinks."""
    errors, values = [], []
    legacy = root / "COURSE_COMMIT"
    if legacy.exists() or legacy.is_symlink():
        errors.append("COURSE_COMMIT: root marker is forbidden; use both nested markers")
    for name in EXPORT_MARKERS:
        path = root / name
        try:
            if path.resolve() != path.absolute() or not stat.S_ISREG(path.stat().st_mode):
                raise OSError("marker must be a regular file without symlinks")
            data = path.read_bytes()
        except OSError as exc:
            errors.append(f"{name}: cannot read export marker: {exc}")
            continue
        if re.fullmatch(rb"[0-9a-f]{40}\n", data) is None:
            errors.append(f"{name}: expected full 40 lowercase hex course commit followed by one LF")
        else:
            values.append(data)
    if len(values) == 2 and values[0] != values[1]:
        errors.append("Platform/COURSE_COMMIT and VMS/COURSE_COMMIT differ")
    return errors


def source_files(root, *, export=False):
    """Tracked checkout source; all disk files in every export, including Git."""
    if not root.is_dir():
        raise OSError(f"source root is not a directory: {root}")
    if not export:
        probe = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                               capture_output=True)
        if probe.returncode == 0 and Path(os.fsdecode(probe.stdout).strip()).resolve() == root:
            result = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", *SCOPES], capture_output=True)
            if result.returncode:
                raise OSError("git ls-files failed")
            return sorted({name for p in result.stdout.split(b"\0") if p
                           and scoped(name := os.fsdecode(p), export=export)})
        if (root / ".git").exists():
            raise OSError("cannot determine Git root")
    names = []
    for scope in ((".",) if export else SCOPES):
        base = root / scope
        if base.is_symlink():
            raise OSError(f"symlink scope: {scope}")
        if not base.exists():
            continue
        if base.is_file():
            names.append(scope)
            continue
        if not base.is_dir():
            raise OSError(f"scope is not a regular file or directory: {scope}")

        def raise_walk_error(exc):
            raise exc

        for directory, dirs, files in os.walk(base, followlinks=False, onerror=raise_walk_error):
            for name in dirs[:]:
                path = Path(directory) / name
                relative = path.relative_to(root).as_posix()
                metadata = relative == ".git" if export else name in {".git", "__pycache__"}
                if (metadata or
                        mirror(relative + "/_")):
                    dirs.remove(name)
                elif path.is_symlink():
                    raise OSError(f"symlink directory: {path.relative_to(root)}")
            names.extend((Path(directory) / name).relative_to(root).as_posix() for name in files
                         if not (export and Path(directory) == root and name == ".git"))
    return sorted(name for name in names if scoped(name, export=export))


def exact_source_file_error(root, name, data=None):
    """Identity of one explicitly named public carrier; no text or locale allowance."""
    path = Path(root) / name
    try:
        if path.resolve() != path.absolute() or not stat.S_ISREG(path.stat().st_mode):
            raise OSError("exact source carrier must be a regular file without symlinks")
        if data is None:
            data = path.read_bytes()
    except OSError as exc:
        return f"{name}: cannot read exact source carrier: {exc}"
    if hashlib.sha256(data).hexdigest() != EXACT_SOURCE_FILES[name]:
        return f"{name}: exact source carrier SHA256 mismatch; no byte changes allowed"
    return None


def localization_text(text):
    """Remove only data cells under the unambiguous ru header; retain comments."""
    output, errors, columns = [], [], None
    for number, line in enumerate(text.split("\n"), 1):
        if not line:
            output.append(line)
            continue
        comment = line.startswith("#")
        candidate = line[1:].lstrip(" ") if comment else line
        cells = candidate.split("\t")
        if columns is None:
            if comment and not {"key", "en", "ru"}.issubset(cells):
                output.append(line)
                continue
            if len(set(cells)) != len(cells) or "" in cells or not {"key", "en", "ru"}.issubset(cells):
                errors.append(f"line {number}: ambiguous localization header (requires key, en, ru)")
            else:
                columns = cells
            output.append(line)
        elif comment:
            output.append(line)
        elif len(cells) != len(columns):
            errors.append(f"line {number}: localization row width differs from header")
            output.append(line)
        else:
            cells[columns.index("ru")] = ""
            output.append("\t".join(cells))
    if columns is None:
        errors.append("missing localization header (requires key, en, ru)")
    return "\n".join(output), errors


def _source_selection(source_scopes):
    if source_scopes is None:
        return lambda name: True
    if not source_scopes or any(scope not in SCOPES for scope in source_scopes):
        raise ValueError("explicit source scopes must be nonempty canonical source homes")
    return lambda name: any(name == scope or name.startswith(scope + "/") for scope in source_scopes)


def scan(root, *, export=None, source_scopes=None):
    export = export_mode(root, export)
    selected = _source_selection(source_scopes)
    counts, errors, stats = {}, [], Counter(cyrillic_scanned_files=0, cyrillic_non_utf8=0, cyrillic_export=int(export))
    try:
        names = source_files(root, export=export)
    except OSError as exc:
        return counts, [f"Cyrillic inventory: {exc}"], stats
    # A deleted exact carrier must fail even in a Git-free projected view.
    if (root / "VMS/11-backend").is_dir():
        names = sorted(set(names) | set(EXACT_SOURCE_FILES))
    for name in names:
        if not selected(name) or mirror(name):
            continue
        path = root / name
        if name in EXACT_SOURCE_FILES:
            problem = exact_source_file_error(root, name)
            if problem:
                errors.append(problem)
            stats["cyrillic_exact_source_files"] += 1
            continue
        try:
            # Never follow a tracked symlink (or a replaced parent) outside source.
            if path.resolve() != path.absolute():
                raise OSError("source symlink is not allowed")
            if not path.exists():                 # deleted tracked file: old debt becomes stale
                continue
            if not stat.S_ISREG(path.stat().st_mode):
                raise OSError("source is not a regular file")
            data = path.read_bytes()
        except OSError as exc:
            errors.append(f"{name}: cannot read Cyrillic source: {exc}")
            continue
        text = data.decode("utf-8", errors="surrogateescape")
        stats["cyrillic_scanned_files"] += 1
        stats["cyrillic_non_utf8"] += any(0xDC80 <= ord(c) <= 0xDCFF for c in text)
        if name == LOCALIZATION:
            text, problems = localization_text(text)
            errors.extend(f"{name}: {problem}" for problem in problems)
        count = len(LETTERS.findall(text))
        if count:
            counts[name] = count
    return counts, errors, stats


def check(root, debt_path=DEBT, *, shrink=False, declare_ready=(), export=None, source_scopes=None):
    if source_scopes is not None and (shrink or declare_ready):
        raise ValueError("scoped Cyrillic checks are read-only; debt writes require the whole source")
    selected = _source_selection(source_scopes)
    root, debt_path = Path(root).resolve(), Path(debt_path)
    export = export_mode(root, export)
    debt, ready, errors = load_debt(debt_path, export=export)
    if export:
        errors.extend(export_marker_errors(root))
    debt = {name: count for name, count in debt.items() if selected(name)}
    ready = {unit for unit in ready if selected(unit)}
    counts, scan_errors, stats = scan(root, export=export, source_scopes=source_scopes)
    errors.extend(scan_errors)
    for unit in sorted(ready | set(declare_ready)):
        if not safe_name(unit, export=export) or mirror(unit + "/_") or not (root / unit).is_dir() or (root / unit).resolve() != root / unit:
            errors.append(f"{unit}: ready unit must be an existing source directory in scope")
        elif any(name == unit or name.startswith(unit + "/") for name in EXACT_SOURCE_FILES):
            errors.append(f"{unit}: ready unit includes exact source carriers; their identity is not English readiness")
        elif any(name == unit or name.startswith(unit + "/") for name in counts):
            errors.append(f"{unit}: ready unit still has Cyrillic letters")
    for name, count in sorted(counts.items()):
        if count > debt.get(name, 0):
            errors.append(f"{name}: Cyrillic letters {count}, debt {debt.get(name, 0)}: new/increased debt")
    if not shrink and not declare_ready:
        for name, count in sorted(debt.items()):
            if counts.get(name, 0) < count:
                errors.append(f"{name}: Cyrillic letters {counts.get(name, 0)}, debt {count}: shrink debt explicitly")
    elif not errors:
        # No create/reset mode: a missing registry or any new debt forbids writing.
        ready.update(declare_ready)
        contents = "# ADR-0121 (8): per-file Cyrillic letter debt; only shrink or declare a clean unit ready.\n" + HEADER + "\n"
        contents += "".join(f"ready\t{name}\t-\n" for name in sorted(ready))
        contents += "".join(f"debt\t{name}\t{count}\n" for name, count in sorted(counts.items()))
        if contents != debt_path.read_text(encoding="utf-8"):
            descriptor, temporary = tempfile.mkstemp(prefix=debt_path.name + ".", dir=debt_path.parent)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                    stream.write(contents)
                os.chmod(temporary, debt_path.stat().st_mode & 0o777)
                os.replace(temporary, debt_path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        debt = counts
    stats.update(cyrillic_debt_files=len(debt), cyrillic_debt_letters=sum(debt.values()), cyrillic_ready=len(ready))
    return errors, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--debt", type=Path, default=DEBT)
    parser.add_argument("--export", action="store_true", default=None,
                        help="check every export file (auto with nested COURSE_COMMIT), with exact named carrier identities and human mirrors; require both equal pins")
    parser.add_argument("--shrink", action="store_true", help="only lower/remove existing debt")
    parser.add_argument("--ready", action="append", default=[], metavar="DIRECTORY", help="declare a clean unit ready (also shrinks)")
    args = parser.parse_args()
    errors, stats = check(args.root, args.debt, shrink=args.shrink, declare_ready=args.ready, export=args.export)
    for error in errors:
        print("ERROR", error)
    print("COUNTS", " ".join(f"{key}={value}" for key, value in sorted(stats.items())))
    print("FAIL" if errors else "PASS", "Cyrillic letters only; translation semantics remain separate")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
