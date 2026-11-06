"""Source TSV transport (ADR-0121): LF rows, one cell-json decode, byte proofs.

This layer does not interpret wire declarations, CEL or the JSON inside a cell.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re


class TSVError(ValueError):
    """The source table or its byte-preservation proof is malformed."""


@dataclass
class Table:
    raw: bytes
    columns: tuple
    declared: tuple
    rows: list
    sources: tuple = ()

    @property
    def text(self):
        return self.raw.decode("utf-8")

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()


_DECLARATION = re.compile(r"# cell-json: ([A-Za-z_][A-Za-z0-9_]*(?:,[A-Za-z_][A-Za-z0-9_]*)*)\Z")
_PROOF = Path("Platform/common/data/cell-json-sha256.tsv")
_CONTRACT = Path("Platform/common/contracts/source-cells.md")
_PROOF_COLUMNS = ("table", "line", "column", "before_sha256", "decoded_sha256")


def _names(names, where):
    if isinstance(names, (str, bytes)) or not names or any(not isinstance(n, str) or not n for n in names):
        raise TSVError(f"{where}: nonempty column names required")
    if len(names) != len(set(names)):
        raise TSVError(f"{where}: duplicate column")
    return tuple(names)


def _cell(text, where):
    if not text.isascii():
        raise TSVError(f"{where}: cell-json must be an ASCII JSON string")
    try:
        value = json.loads(text)
    except ValueError as exc:
        raise TSVError(f"{where}: invalid cell-json: {exc}") from None
    if not isinstance(value, str):
        raise TSVError(f"{where}: cell-json must be a JSON string")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise TSVError(f"{where}: unpaired surrogate in cell-json") from None
    return value


def parse(raw, *, names=None, positional=False, where="table"):
    """Parse raw source bytes/text, with no filesystem or domain interpretation.

    `names` is the existing form's column list; `positional=True` means there is
    no physical header. In particular, a comment header is never a data row.
    """
    if not isinstance(raw, (str, bytes)):
        raise TSVError(f"{where}: expected raw source text/bytes, not decoded rows")
    try:
        data = raw.encode("utf-8") if isinstance(raw, str) else raw
        text = data.decode("utf-8")
    except UnicodeError:
        raise TSVError(f"{where}: source is not scalar UTF-8") from None
    expected = _names(names, where) if names is not None else None
    if positional and expected is None:
        raise TSVError(f"{where}: positional input requires column names")
    columns = expected if positional else None
    declared, seen_declaration, started, rows = (), False, False, []
    # splitlines() also splits VT and U+2028, which are ordinary source data.
    for no, line in enumerate(text.split("\n"), 1):
        loc = f"{where}:{no}"
        if line.lstrip(" \t").startswith("# cell-json"):
            match = _DECLARATION.fullmatch(line)
            if match is None:
                raise TSVError(f"{loc}: invalid cell-json declaration")
            if seen_declaration or started:
                raise TSVError(f"{loc}: duplicate or late cell-json declaration")
            declared = _names(match[1].split(","), loc)
            seen_declaration = True
            continue
        if line == "" or line.startswith("#"):
            continue
        cells = line.split("\t")
        if columns is None:
            columns = _names(cells, loc)
            if expected is not None and columns != expected:
                raise TSVError(f"{loc}: header {list(columns)}, expected {list(expected)}")
            started = True
            continue
        started = True
        if len(cells) != len(columns):
            raise TSVError(f"{loc}: {len(cells)} cells, expected {len(columns)}")
        if set(declared) - set(columns):
            raise TSVError(f"{loc}: unknown cell-json column {sorted(set(declared) - set(columns))}")
        row = dict(zip(columns, cells))
        for name in declared:
            row[name] = _cell(row[name], f"{loc} column {name}")
        rows.append((no, row))
    if columns is None:
        raise TSVError(f"{where}: no header")
    if set(declared) - set(columns):
        raise TSVError(f"{where}: unknown cell-json column {sorted(set(declared) - set(columns))}")
    return Table(data, columns, tuple(declared), rows)


def _proofs(root):
    path = Path(root) / _PROOF
    if not path.is_file():
        return {}, path
    proofs = {}
    for no, row in parse(path.read_bytes(), names=_PROOF_COLUMNS, where=str(path)).rows:
        key = (row["table"], row["line"], row["column"])
        if key in proofs:
            raise TSVError(f"{path}:{no}: duplicate cell proof {key}")
        if not re.fullmatch(r"[1-9][0-9]*", row["line"]):
            raise TSVError(f"{path}:{no}: invalid proof line")
        if not re.fullmatch(r"[0-9a-f]{64}", row["before_sha256"]) or row["before_sha256"] != row["decoded_sha256"]:
            raise TSVError(f"{path}:{no}: invalid or different before/decoded SHA256")
        proofs[key] = row["decoded_sha256"]
    return proofs, path


def read(path, *, names=None, positional=False, root=None):
    """Read a source file; a marked file requires its exact rooted byte proof."""
    path = Path(path)
    table = parse(path.read_bytes(), names=names, positional=positional, where=str(path))
    inputs = [path]
    if root is None:
        if table.declared:
            raise TSVError(f"{path}: source root required for cell-json byte proofs")
    else:
        root = Path(root)
        try:
            rel = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            if table.declared:
                raise TSVError(f"{path}: marked table is outside source root {root}") from None
            table.sources = tuple(inputs)
            return table
        proofs, proof_path = _proofs(root)
        if proof_path.is_file():
            inputs.append(proof_path)
        actual = {(rel, str(no), name): hashlib.sha256(row[name].encode("utf-8")).hexdigest()
                  for no, row in table.rows for name in table.declared}
        expected = {k: v for k, v in proofs.items() if k[0] == rel}
        if actual != expected:
            raise TSVError(f"{path}: missing, extra or mismatched cell-json byte proof")
        if table.declared or expected:
            if (root / _CONTRACT).is_file():
                inputs.append(root / _CONTRACT)
    table.sources = tuple(inputs)
    return table


def source_files(path, *, root):
    """Provenance inputs; callers separately validate header/positional rows."""
    path, root = Path(path), Path(root)
    if not path.resolve().is_relative_to(root.resolve()):
        return [path]
    marked = any(line.lstrip(" \t").startswith("# cell-json")
                 for line in path.read_bytes().decode("utf-8").split("\n"))
    return [path] + ([root / _PROOF] if (root / _PROOF).is_file() else []) + \
        ([root / _CONTRACT] if marked and (root / _CONTRACT).is_file() else [])
