#!/usr/bin/env python3
"""ADR-0121 (8): Cyrillic letters in Platform and code shipped by normgen.

Read-only by default. --shrink only lowers the explicit per-file debt; --ready
adds a clean directory to the readiness declarations in that same registry.
No product imports, network access, or execution of source files.
"""

import argparse
import os
import re
import stat
import subprocess
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath

DEBT = Path(__file__).resolve().parents[1] / "cyrillic-debt.tsv"
SCOPES = ("Platform", "tools/normgen")
LOCALIZATION = "Platform/06-console/data/localization.tsv"
HEADER = "kind\tpath\tletters"
# Unicode 17.0.0, Script=Cyrillic AND General_Category=L* (449 letters).
# https://www.unicode.org/Public/17.0.0/ucd/Scripts.txt
# SHA256 9f5e50d3abaee7d6ce09480f325c706f485ae3240912527e651954d2d6b035bf
# Pinned ranges also cover letters unknown to Python 3.12's Unicode database.
LETTER_RANGES = ((0x0400, 0x0481), (0x048A, 0x052F), (0x1C80, 0x1C8A),
                 (0x1D2B, 0x1D2B), (0x1D78, 0x1D78), (0xA640, 0xA66E),
                 (0xA67F, 0xA69D), (0x1E030, 0x1E06D))
LETTERS = re.compile("[" + "".join(chr(low) + "-" + chr(high) for low, high in LETTER_RANGES) + "]")


def scoped(name):
    return any(name == scope or name.startswith(scope + "/") for scope in SCOPES)


def mirror(name):
    # Module, common and lesson mirrors (ADR-0124); not a normgen escape hatch.
    parts = PurePosixPath(name).parts
    return (len(parts) >= 3 and parts[:2] == ("Platform", "ru") or
            len(parts) >= 4 and parts[0] == "Platform" and parts[2] == "ru" and
            (parts[1] == "common" or re.fullmatch(r"[0-9]{2}-[^/]+", parts[1]) is not None))


def safe_name(name):
    parts = name.split("/")
    return bool(name) and not any(p in {"", ".", ".."} for p in parts) and "\\" not in name and scoped(name)


def load_debt(path):
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
        if not safe_name(name) or mirror(name + "/_") or name in seen:
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


def source_files(root):
    """Tracked source in a checkout; disk source in a Git-free export/fixture."""
    if not root.is_dir():
        raise OSError(f"source root is not a directory: {root}")
    probe = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                           capture_output=True)
    if probe.returncode == 0 and Path(os.fsdecode(probe.stdout).strip()).resolve() == root:
        result = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", *SCOPES], capture_output=True)
        if result.returncode:
            raise OSError("git ls-files failed")
        return sorted({os.fsdecode(p) for p in result.stdout.split(b"\0") if p})
    if (root / ".git").exists():
        raise OSError("cannot determine Git root")
    names = []
    for scope in SCOPES:
        base = root / scope
        if base.is_symlink():
            raise OSError(f"symlink scope: {scope}")
        if not base.exists():
            continue
        if not base.is_dir():
            raise OSError(f"scope is not a directory: {scope}")

        def raise_walk_error(exc):
            raise exc

        for directory, dirs, files in os.walk(base, followlinks=False, onerror=raise_walk_error):
            for name in dirs[:]:
                path = Path(directory) / name
                if name in {".git", "__pycache__"}:
                    dirs.remove(name)
                elif path.is_symlink():
                    raise OSError(f"symlink directory: {path.relative_to(root)}")
            names.extend((Path(directory) / name).relative_to(root).as_posix() for name in files)
    return sorted(names)


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


def scan(root):
    counts, errors, stats = {}, [], Counter(cyrillic_scanned_files=0, cyrillic_non_utf8=0)
    try:
        names = source_files(root)
    except OSError as exc:
        return counts, [f"Cyrillic inventory: {exc}"], stats
    for name in names:
        if mirror(name):
            continue
        path = root / name
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


def check(root, debt_path=DEBT, *, shrink=False, declare_ready=()):
    root, debt_path = Path(root).resolve(), Path(debt_path)
    debt, ready, errors = load_debt(debt_path)
    counts, scan_errors, stats = scan(root)
    errors.extend(scan_errors)
    for unit in sorted(ready | set(declare_ready)):
        if not safe_name(unit) or mirror(unit + "/_") or not (root / unit).is_dir() or (root / unit).resolve() != root / unit:
            errors.append(f"{unit}: ready unit must be an existing source directory in scope")
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
    parser.add_argument("--shrink", action="store_true", help="only lower/remove existing debt")
    parser.add_argument("--ready", action="append", default=[], metavar="DIRECTORY", help="declare a clean unit ready (also shrinks)")
    args = parser.parse_args()
    errors, stats = check(args.root, args.debt, shrink=args.shrink, declare_ready=args.ready)
    for error in errors:
        print("ERROR", error)
    print("COUNTS", " ".join(f"{key}={value}" for key, value in sorted(stats.items())))
    print("FAIL" if errors else "PASS", "Cyrillic letters only; translation semantics remain separate")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
