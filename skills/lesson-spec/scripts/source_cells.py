"""Validate source-only TSV cell-json columns (ADR-0121 (6), Architect 2026-11-06).

The value is decoded once before a consumer interprets its columns. This module
checks the source form; it never translates a decoded payload or runtime word.
"""
import json
import re
import hashlib
from pathlib import Path

PREFIX = "# cell-json:"
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
DECLARATION = re.compile(r"# cell-json: ([A-Za-z_][A-Za-z0-9_]*(?:,[A-Za-z_][A-Za-z0-9_]*)*)\Z")


def decode(cell):
    if not cell.isascii():
        raise ValueError("cell-json requires an ASCII JSON string with Unicode escapes")
    try:
        value = json.loads(cell)
    except ValueError as exc:
        raise ValueError(f"cell-json is not one strict JSON string: {exc}") from None
    if not isinstance(value, str):
        raise ValueError("cell-json must decode to a string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("cell-json has an unpaired surrogate") from None
    return value


def table(text, columns=None, positional=False):
    """Return (declared columns, [(physical line, decoded row)], errors).

    Headerless tables obtain their column names from the existing wire form.
    Physical line numbers and all undeclared source cells stay unchanged.
    """
    lines = text.split("\n")
    declarations = [(n, line) for n, line in enumerate(lines, 1)
                    if re.match(r"^\s*#\s*cell-json\b", line)]
    if not declarations:
        return (), [], []
    errors = []
    if len(declarations) != 1:
        errors.append("cell-json must have exactly one declaration")
    number, declaration = declarations[0]
    match = DECLARATION.fullmatch(declaration)
    if not match:
        return (), [], errors + [f"line {number}: expected {PREFIX} <columns>"]
    names = match[1].split(",")
    if len(names) != len(set(names)):
        errors.append(f"line {number}: duplicate cell-json column")
    data = [(n, line.split("\t")) for n, line in enumerate(lines, 1) if line and not line.startswith("#")]
    if not data:
        return tuple(names), [], errors + ["cell-json table has no header or data"]
    if number >= data[0][0]:
        errors.append(f"line {number}: cell-json must precede the table")
    if not positional:
        _, header = data.pop(0)
        if columns is not None and list(columns) != header:
            errors.append("cell-json table header differs from the wire form")
        columns = header
    elif columns is None:
        return tuple(names), [], errors + ["cell-json positional table needs the wire column names"]
    if len(columns) != len(set(columns)):
        errors.append("cell-json table has duplicate header columns")
    missing = set(names) - set(columns)
    if missing:
        errors.append(f"cell-json declares unknown columns: {', '.join(sorted(missing))}")
    rows = []
    for line, cells in data:
        if len(cells) != len(columns):
            errors.append(f"line {line}: cell-json table has {len(cells)} cells, expected {len(columns)}")
            continue
        row = dict(zip(columns, cells))
        for name in names:
            if name not in row:
                continue
            try:
                row[name] = decode(row[name])
            except ValueError as exc:
                errors.append(f"line {line}, column {name}: {exc}")
        rows.append((line, row))
    return tuple(names), rows, errors


POSITIONAL_SOURCES = {
    "Platform/06-console/acceptance/8/seams.tsv": (["scenario", "step", "request", "expect"], True),
}


def _source_scopes(source_scopes):
    if source_scopes is not None and (not source_scopes or any(s not in {"Platform", "VMS"} for s in source_scopes)):
        raise ValueError("cell-json source scopes must be nonempty module homes")
    return ("Platform", "VMS") if source_scopes is None else tuple(source_scopes)


def wire_headers(root, *, source_scopes=None):
    """Existing wire bindings and the scenario form name positional columns."""
    modules = _source_scopes(source_scopes)
    base = Path(root) / "Platform/common/vectors"
    canonical, cases = base / "wire.tsv", base / "wire.cases.tsv"
    present = lambda path: path.exists() or path.is_symlink()
    wires = ([canonical] + ([cases] if present(cases) else [])) if any(
        present(path) for path in (canonical, cases)) else []
    columns = ["package", "table", "surface", "header", "inputs", "files",
               "expect", "compare", "markers", "native", "norm"]
    result, seen = {}, set()
    for wire in wires:
        try:
            raw = wire.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise ValueError(f"{wire.name}: unreadable wire form: {exc}") from None
        if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
            raise ValueError(f"{wire.name}: BOM or CR — the form is UTF-8 with LF")
        lines = [(no, line.split("\t")) for no, line in enumerate(text.split("\n"), 1)
                 if line and not line.startswith("#")]
        if not lines or lines[0][1] != columns:
            raise ValueError(f"{wire.name}: columns must be {columns}")
        for no, values in lines[1:]:
            if len(values) != len(columns):
                raise ValueError(f"{wire.name}:{no}: wrong wire row width")
            row = dict(zip(columns, values))
            triple = row["package"], row["table"], row["surface"]
            if triple in seen:
                raise ValueError(f"{wire.name}:{no}: the triple (package, table, surface) repeats")
            seen.add(triple)
            package = row["package"].split("/")
            path = Path("Platform") / package[0] / "vectors" / Path(*package[1:]) / row["table"]
            form = row["header"].split(",")
            value = (form[1:] if form[0] == "-" else form, form[0] == "-")
            if path in result and result[path] != value:
                raise ValueError(f"{path}: conflicting wire column declarations")
            result[path] = value
    # The existing acceptance form already fixes these columns. It permits its
    # traditional comment header and an ordinary header; neither is a data row.
    for module in modules:
        for path in (Path(root) / module).glob("*/acceptance/**/scenarios.tsv"):
            columns = ["scenario", "step", "request", "expect"]
            first = next((line.split("\t") for line in path.read_bytes().decode("utf-8").split("\n")
                          if line and not line.startswith("#")), [])
            result[path.relative_to(root)] = (columns, first != columns)
    # Exactly-named positional sources outside the wire and scenario forms
    # (Architect 2026-11-06, P/06 source binding); no glob over other seams.
    for path, value in POSITIONAL_SOURCES.items():
        result[Path(path)] = value
    return result


def errors(root, paths, *, source_scopes=None):
    """Validate declarations and a complete bijection with the byte proof table."""
    root = Path(root)
    modules = _source_scopes(source_scopes)
    selected = lambda name: source_scopes is None or name.split("/", 1)[0] in modules
    found = []
    actual = {}
    try:
        forms = wire_headers(root, source_scopes=source_scopes)
    except ValueError as exc:
        return [(root / "Platform/common/vectors/wire.tsv", str(exc))]
    for path in paths:
        if not selected(path.relative_to(root).as_posix()):
            raise ValueError("cell-json input outside explicit module scopes")
        text = path.read_bytes().decode("utf-8", errors="surrogateescape")
        columns, positional = forms.get(path.relative_to(root), (None, False))
        names, rows, problems = table(text, columns, positional)
        found.extend((path, problem) for problem in problems)
        if problems:
            continue
        for line, row in rows:
            for name in names:
                actual[(path.relative_to(root).as_posix(), str(line), name)] = hashlib.sha256(row[name].encode()).hexdigest()
    manifest = root / "Platform/common/data/cell-json-sha256.tsv"
    if not manifest.is_file():
        return found + ([(manifest, "missing cell-json byte-preservation proof")] if actual else [])
    lines = [(n, line.split("\t")) for n, line in enumerate(manifest.read_bytes().decode("utf-8").split("\n"), 1)
             if line and not line.startswith("#")]
    header = ["table", "line", "column", "before_sha256", "decoded_sha256"]
    if not lines or lines[0][1] != header:
        return found + [(manifest, "invalid cell-json SHA256 proof header")]
    covered = set()
    for number, cells in lines[1:]:
        if len(cells) != len(header):
            found.append((manifest, f"line {number}: invalid cell-json proof width"))
            continue
        key = tuple(cells[:3])
        if source_scopes is not None and (not cells[0] or "\\" in cells[0]
                or any(part in {"", ".", ".."} for part in cells[0].split("/"))):
            found.append((manifest, f"line {number}: unsafe cell-json proof table path"))
            continue
        if source_scopes is not None and (not re.fullmatch(r"[1-9][0-9]*", cells[1]) or not NAME.fullmatch(cells[2])):
            found.append((manifest, f"line {number}: invalid cell-json proof cell identity"))
            continue
        if key in covered:
            found.append((manifest, f"line {number}: duplicate cell-json proof cell"))
        covered.add(key)
        before, decoded = cells[3:]
        if (not re.fullmatch(r"[0-9a-f]{64}", before) or before != decoded
                or selected(cells[0]) and actual.get(key) != decoded):
            found.append((manifest, f"line {number}: cell-json before/decoded SHA256 mismatch or undeclared cell"))
    for key in sorted(actual.keys() - covered):
        found.append((manifest, f"missing cell-json byte proof for {key}"))
    return found
