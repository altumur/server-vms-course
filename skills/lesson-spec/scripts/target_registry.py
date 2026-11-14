"""The acceptance target registry assembled from the common header and the rows of the lessons (ADR-0135 addendum (14)).

The registry is two tables: `targets.tsv` (M) and `targets.routing.tsv` (J). Their header — the first row outside `#` comments —
is the one of `Platform/common/acceptance/forms/`. Rows live in the common files (the former layout) or in
`Platform/NN-<process>/forms/targets.tsv` and `targets.routing.tsv` of their lesson, with the required common columns; routing may omit the optional execution column. During the transition
both layouts are accepted at once; one id in two places is an error.

Checked here, by data only:
- every source has the required common columns, cells as many as its columns, a nonempty `id`;
- an `id` of targets is unique across all sources, the same for routing;
- a row in a lesson's file has the `owner` of that lesson (its directory name);
- every target has exactly one routing row and the other way round, both in the same place (common, or the same lesson).

`stands(root)` reads the stand directories of the lessons from the column `acceptance` of the routing (OBSH.43): a lesson with
chapters keeps beside `acceptance/K/` only the stand directories `acceptance/<name>/` (a name that begins with a letter) that a
routing row names; check_spec judges both directions against the disk.

`assemble(root)` → (targets, routing, errors, stats): targets and routing are lists of (path, line, row) in source order
(common first, then lessons by directory), errors are (path, message).
"""
import json
import re
from pathlib import Path

COMMON = Path("Platform/common/acceptance/forms")
TARGETS, ROUTING = "targets.tsv", "targets.routing.tsv"
EXECUTION_SCHEMA = "targets.execution.schema.json"
OPTIONAL_ROUTING = {"execution": "{}"}
LESSON_DIR = re.compile(r"^\d\d-[a-z0-9-]+$")
# A stand directory of a lesson: `Platform/NN-<process>/acceptance/<name>`, <name> not a chapter number; the element of the
# column `acceptance` may name the directory itself or a path in it.
STAND = r"[a-z][a-z0-9-]*"
STAND_PATH = re.compile(r"^Platform/(\d\d-[a-z0-9-]+)/acceptance/(" + STAND + r")(?:/.*)?$")


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
        if not got or len(got) != len(set(got)):
            errors.append((path, "missing header or duplicate column name"))
            continue
        if name == ROUTING:
            missing = set(header) - set(OPTIONAL_ROUTING) - set(got)
            if missing:
                errors.append((path, f"the header differs from the common header: missing required columns {sorted(missing)}"))
                continue
        elif lesson is not None and got != header:
            errors.append((path, f"the header differs from the common header of {COMMON / name}: {got} != {header}"))
            continue
        for line, cells in body:
            if len(cells) != len(got):
                errors.append((path, f"line {line}: {len(cells)} cells, the header names {len(got)}"))
                continue
            supplied = dict(zip(got, cells))
            row = {key: supplied.get(key, OPTIONAL_ROUTING.get(key, "")) for key in header}
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
    routing_header, routing = _table(root, ROUTING, errors)
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
    execution_count = 0
    if routing_header and "execution" in routing_header:
        execution_count = _check_execution(root, targets, routing, errors)
    places = {place for *_, place in targets + routing}
    stats = {"registry_targets": len(t_ids), "registry_routing": len(r_ids),
             "registry_lessons_with_rows": len(places - {"common"}), "registry_execution_rows": execution_count}
    return ([(p, n, r) for p, n, r, _ in targets], [(p, n, r) for p, n, r, _ in routing], errors, stats)


def _json(cell):
    """Strict JSON: duplicate keys and non-finite extensions are data errors."""
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError(f"duplicate JSON key {key}")
            out[key] = value
        return out

    def constant(word):
        raise ValueError(f"non-finite JSON value {word}")

    return json.loads(cell, object_pairs_hook=pairs, parse_constant=constant)


def selected_scenarios(path, selector, exclude=()):
    """Read scenario identities/first requests only; never execute a step or read its expectation."""
    import source_cells
    text = path.read_text(encoding="utf-8")
    # Scenario tables allow a comment header and whitespace-only empty lines.
    text = "\n".join(raw if raw.strip() else "" for raw in text.split("\n"))
    header = ["scenario", "step", "request", "expect"]
    first_line = next((raw for raw in text.split("\n") if raw and not raw.startswith("#")), "")
    declared, decoded, problems = source_cells.table(text, columns=header,
                                                   positional=first_line.split("\t") != header)
    if problems:
        raise ValueError("; ".join(problems))
    if declared:
        rows = [(row["scenario"], row["request"]) for _, row in decoded]
    else:
        rows = []
        for number, raw in enumerate(text.split("\n"), 1):
            if not raw or raw.startswith("#"):
                continue
            cells = raw.split("\t")
            if cells == ["scenario", "step", "request", "expect"]:
                continue
            if len(cells) != 4:
                raise ValueError(f"line {number}: expected four scenario cells")
            rows.append((cells[0], cells[2]))
    first = {}
    previous = None
    for name, request in rows:
        if name != previous and name in first:
            raise ValueError(f"scenario {name} is not contiguous")
        first.setdefault(name, request)
        previous = name
    if selector == "all":
        selected = list(first)
    elif selector == "none":
        selected = []
    elif selector.startswith(("first-step:", "not-first-step:")):
        word, directive = selector.split(":", 1)
        if not directive or not directive.startswith("@") or any(c.isspace() for c in directive):
            raise ValueError("invalid first-step directive selector")
        selected = [name for name, request in first.items()
                    if (request == directive or request.startswith(directive + " ")) == (word == "first-step")]
    else:
        match = re.fullmatch(r"range:([0-9]+)-([0-9]+)", selector)
        if not match or int(match[1]) > int(match[2]):
            raise ValueError("invalid scenarios selector")
        lower, upper = int(match[1]), int(match[2])
        selected = [name for name in first if (number := re.match(r"[0-9]+", name))
                    and lower <= int(number[0]) <= upper]
    missing = set(exclude) - set(selected)
    if missing:
        raise ValueError(f"execution.exclude names unselected or absent scenarios: {sorted(missing)}")
    return [name for name in selected if name not in exclude]


def _check_execution(root, targets, routing, errors):
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
    schema_path = root / COMMON / EXECUTION_SCHEMA
    try:
        schema = _json(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
    except (OSError, ValueError, UnicodeError, SchemaError) as exc:
        errors.append((schema_path, f"invalid execution schema: {exc}"))
        return 0
    by_id = {row["id"]: row for _, _, row, _ in targets}
    count = 0
    for path, line, row, _ in routing:
        try:
            execution = _json(row["execution"])
            problems = list(validator.iter_errors(execution))
            if problems:
                raise ValueError("; ".join(f"execution/{'/'.join(map(str, e.path))}: {e.message}" for e in problems))
            if not execution:
                continue
            count += 1
            if row.get("engine") not in {"run", "l06", "l11", "store_group", "power_stand"}:
                raise ValueError("execution applies only to a scenario table, not this engine word")
            directories = _json(row.get("acceptance", "[]"))
            if not isinstance(directories, list) or not directories or not isinstance(directories[0], str):
                raise ValueError("execution requires a first acceptance directory")
            relative = Path(directories[0])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("execution requires a repository-relative acceptance directory")
            selected = selected_scenarios(root / relative / "scenarios.tsv", row.get("scenarios", ""),
                                          execution.get("exclude", []))
            positions = {name: number for number, name in enumerate(selected)}
            ids, boundaries = set(), set()
            last_position = -1
            for action in execution.get("between", []):
                if type(action["timeout_s"]) is not int:
                    raise ValueError("execution.between timeout_s must be a JSON integer token")
                aid = action["id"]
                boundary = (action["after"], action["before"])
                if aid in ids or boundary in boundaries:
                    raise ValueError("execution.between repeats an id or boundary")
                ids.add(aid)
                boundaries.add(boundary)
                after, before = boundary
                if after not in positions or before not in positions or positions[before] != positions[after] + 1:
                    raise ValueError(f"execution.between {aid}: after/before must be adjacent selected scenarios")
                if positions[after] < last_position:
                    raise ValueError("execution.between must follow the selected scenario order")
                last_position = positions[after]
                target = by_id.get(row["id"], {})
                commands = _json(target.get("stand_commands", "[]"))
                if not isinstance(commands, list) or action["command"] not in commands:
                    raise ValueError(f"execution.between {aid}: command is not declared in target stand_commands")
        except (OSError, ValueError, UnicodeError, KeyError) as exc:
            errors.append((path, f"line {line}: {exc}"))
    return count


def stands(root):
    """{(lesson, name): [(path, line, id)]} — the stand directories `Platform/<lesson>/acceptance/<name>` named in the column
    `acceptance` of any routing source (common or a lesson), in source order. Rows that do not parse are skipped: their form
    is judged by assemble() and by the checks of the routing."""
    out = {}
    for path, _lesson in sources(Path(root), ROUTING):
        try:
            header, body = read_table(path)
        except (OSError, UnicodeError):
            continue
        if not header or "acceptance" not in header or "id" not in header:
            continue
        for line, cells in body:
            if len(cells) != len(header):
                continue
            row = dict(zip(header, cells))
            try:
                dirs = json.loads(row["acceptance"])
            except ValueError:
                continue
            for value in dirs if isinstance(dirs, list) else []:
                match = STAND_PATH.match(value) if isinstance(value, str) else None
                if match:
                    out.setdefault(match.groups(), []).append((path, line, row["id"]))
    return out
