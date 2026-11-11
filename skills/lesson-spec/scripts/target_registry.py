"""The acceptance target registry assembled from the common header and the rows of the lessons (ADR-0135 addendum (14)).

The registry is two tables: `targets.tsv` (M) and `targets.routing.tsv` (J). Their header — the first row outside `#` comments —
is the one of `Platform/common/acceptance/forms/`. Rows live in the common files (the former layout) or in
`Platform/NN-<process>/forms/targets.tsv` and `targets.routing.tsv` of their lesson, with the same header. During the transition
both layouts are accepted at once; one id in two places is an error.

Checked here, by data only:
- every source has the common header, cells as many as its columns, a nonempty `id`;
- an `id` of targets is unique across all sources, the same for routing;
- a row in a lesson's file has the `owner` of that lesson (its directory name);
- every target has exactly one routing row and the other way round, both in the same place (common, or the same lesson).

`assemble(root)` → (targets, routing, errors, stats): targets and routing are lists of (path, line, row) in source order
(common first, then lessons by directory), errors are (path, message).
"""
import re
from pathlib import Path

COMMON = Path("Platform/common/acceptance/forms")
TARGETS, ROUTING = "targets.tsv", "targets.routing.tsv"
LESSON_DIR = re.compile(r"^\d\d-[a-z0-9-]+$")


def read_table(path):
    """(header, [(line, cells)]) of a TSV form: `#` lines and empty lines are skipped, the first other line is the header."""
    header, rows = None, []
    for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if not line or line.startswith("#"):
            continue
        cells = line.split("\t")
        if header is None:
            header = cells
        else:
            rows.append((number, cells))
    return header, rows


def lesson_dirs(root):
    """The lesson directories of Platform/ (NN-<process>), sorted."""
    base = root / "Platform"
    return sorted(p for p in base.iterdir() if p.is_dir() and LESSON_DIR.match(p.name)) if base.is_dir() else []


def sources(root, name):
    """[(path, lesson or None)] of the files holding rows of a registry table: common first, then lessons."""
    out = []
    common = root / COMMON / name
    if common.is_file():
        out.append((common, None))
    for lesson in lesson_dirs(root):
        path = lesson / "forms" / name
        if path.is_file():
            out.append((path, lesson.name))
    return out


def _table(root, name, errors):
    """(header, [(path, line, row, place)]) of one registry table assembled from its sources."""
    common = root / COMMON / name
    if not common.is_file():
        errors.append((common, "the common registry file is missing: it holds the header of the table"))
        return None, []
    header, _ = read_table(common)
    if not header or "id" not in header:
        errors.append((common, "the common registry file has no header with the column id"))
        return None, []
    rows = []
    for path, lesson in sources(root, name):
        got, body = read_table(path)
        if lesson is not None and got != header:
            errors.append((path, f"the header differs from the common header of {COMMON / name}: {got} != {header}"))
            continue
        for line, cells in body:
            if len(cells) != len(header):
                errors.append((path, f"line {line}: {len(cells)} cells, the header names {len(header)}"))
                continue
            row = dict(zip(header, cells))
            if not row.get("id"):
                errors.append((path, f"line {line}: empty id"))
                continue
            if lesson is not None and "owner" in row and row["owner"] != lesson:
                errors.append((path, f"line {line}: target {row['id']} has owner {row['owner']}, the rows of a lesson's "
                                     f"registry belong to {lesson}"))
            rows.append((path, line, row, lesson or "common"))
    return header, rows


def _unique(rows, name, errors):
    """{id: (path, line, place)} of the first occurrence; a repeated id is an error at its later place."""
    seen = {}
    for path, line, row, place in rows:
        if row["id"] in seen:
            first = seen[row["id"]]
            errors.append((path, f"line {line}: target id {row['id']} of {name} is already at {first[0]}:{first[1]}"))
            continue
        seen[row["id"]] = (path, line, place)
    return seen


def assemble(root):
    root = Path(root)
    errors = []
    _, targets = _table(root, TARGETS, errors)
    _, routing = _table(root, ROUTING, errors)
    t_ids = _unique(targets, TARGETS, errors)
    r_ids = _unique(routing, ROUTING, errors)
    for tid, (path, line, place) in t_ids.items():
        if tid not in r_ids:
            errors.append((path, f"line {line}: target {tid} has no row in {ROUTING}"))
        elif r_ids[tid][2] != place:
            errors.append((r_ids[tid][0], f"line {r_ids[tid][1]}: the routing row of {tid} is in {r_ids[tid][2]}, "
                                          f"its target row in {place}: both belong to one place"))
    for rid, (path, line, _) in r_ids.items():
        if rid not in t_ids:
            errors.append((path, f"line {line}: routing row {rid} has no target in {TARGETS}"))
    places = {place for *_, place in targets + routing}
    stats = {"registry_targets": len(t_ids), "registry_routing": len(r_ids),
             "registry_lessons_with_rows": len(places - {"common"})}
    return ([(p, n, r) for p, n, r, _ in targets], [(p, n, r) for p, n, r, _ in routing], errors, stats)
