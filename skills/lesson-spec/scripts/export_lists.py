"""The export filters M and J assembled from the common filters and the lists of the lessons (ADR-0135 addendum (14)).

Rule: Platform/common/acceptance/README.md, «Target registry and export lists assembled from the lessons», items 2–4.
The common filters `Platform/common/export-model-filter.json` (M) and `Platform/common/acceptance/judge-input-filter.json` (J)
keep their own records; a lesson that has moved keeps the records of its files in `Platform/NN-<process>/forms/export.json`:
`{"version": 1, "model": [...], "judge": [...]}`. The assembled filter is the common records and the lesson records.

Checked here, by data only:
- the form of a lesson list: exactly the fields version (1), model, judge; each array of records {path, disposition, basis},
  sorted by path as UTF-8 bytes; dispositions of M are model_and_judge or judge_only, of J include or exclude;
- a lesson list names every file of its lesson directory once in model and once in judge, and no other file;
- a path has one record in each assembled filter (not in the common filter and a lesson list at once), and the assembled M
  and J name the same paths (the transition keeps the composition: what M names, J names, and the other way round);
- the common rules of item 3: in every lesson `forms/targets.tsv` is model_and_judge in M and include in J,
  `forms/targets.routing.tsv` is judge_only in M (never given to the model) and include in J, `forms/export.json` is
  judge_only in M and exclude in J.

A file of a lesson that has not moved yet (no forms/export.json) and that no record names is counted in the stats
(`export_unlisted`), not an error: its lesson brings its list when it moves (ADR-0135 addendum (14) item 4).

`assemble(root)` → ({"model": [records], "judge": [records]}, errors, stats); errors are (path, message).
"""
import json
import re
import subprocess
from pathlib import Path

COMMON = {"model": Path("Platform/common/export-model-filter.json"),
          "judge": Path("Platform/common/acceptance/judge-input-filter.json")}
LIST = Path("forms/export.json")
DISPOSITIONS = {"model": {"model_and_judge", "judge_only"}, "judge": {"include", "exclude"}}
RECORD_KEYS = {"path", "disposition", "basis"}
RULES = {  # item 3: the forms of the registry and of the list in every lesson
    "forms/targets.tsv": {"model": "model_and_judge", "judge": "include"},
    "forms/targets.routing.tsv": {"model": "judge_only", "judge": "include"},
    "forms/export.json": {"model": "judge_only", "judge": "exclude"},
}
LESSON_DIR = re.compile(r"^\d\d-[a-z0-9-]+$")


def lesson_dirs(root):
    platform = root / "Platform"
    return sorted(p.name for p in platform.iterdir() if p.is_dir() and LESSON_DIR.match(p.name)) if platform.is_dir() else []


def lesson_files(root, lesson):
    """The files of a lesson directory as repository paths: git's tracked files when the root is a git tree, else the walk."""
    rel = f"Platform/{lesson}"
    if (root / ".git").exists():
        done = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", rel], capture_output=True)
        if done.returncode == 0:
            return {p for p in done.stdout.decode("utf-8").split("\0") if p}
    return {p.relative_to(root).as_posix() for p in (root / rel).rglob("*") if p.is_file()}


def _records(path, records, side, errors):
    out = []
    if not isinstance(records, list):
        errors.append((path, f"{side} is not an array of records"))
        return out
    keys = []
    for index, record in enumerate(records):
        where = f"{side}[{index}]"
        if not isinstance(record, dict) or set(record) != RECORD_KEYS:
            errors.append((path, f"{where}: a record has exactly the fields path, disposition, basis"))
            continue
        if not all(isinstance(record[k], str) and record[k] for k in RECORD_KEYS):
            errors.append((path, f"{where}: path, disposition and basis are nonempty strings"))
            continue
        if record["disposition"] not in DISPOSITIONS[side]:
            errors.append((path, f"{where} {record['path']}: disposition {record['disposition']} is not one of "
                                 f"{', '.join(sorted(DISPOSITIONS[side]))}"))
        keys.append(record["path"].encode("utf-8"))
        out.append(record)
    if keys != sorted(keys):
        errors.append((path, f"{side} is not sorted by path as UTF-8 bytes"))
    return out


def _load(path, errors):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        errors.append((path, f"unreadable JSON: {type(exc).__name__}"))
        return None


def assemble(root):
    root = Path(root)
    errors, stats = [], {"export_lessons_with_lists": 0, "export_unlisted": 0}
    assembled = {"model": [], "judge": []}
    seen = {"model": {}, "judge": {}}  # path -> source path of its record

    def take(side, source, records):
        for record in records:
            other = seen[side].get(record["path"])
            if other is not None:
                errors.append((source, f"{side}: {record['path']} has a record here and in {other}"))
                continue
            seen[side][record["path"]] = source
            assembled[side].append(record)

    for side, rel in COMMON.items():
        data = _load(root / rel, errors) if (root / rel).is_file() else None
        if data is None:
            if not (root / rel).is_file():
                errors.append((root / rel, "the common filter is missing"))
            continue
        take(side, root / rel, _records(root / rel, data.get("files") if isinstance(data, dict) else None, side, errors))

    lessons = lesson_dirs(root)
    moved = set()
    for lesson in lessons:
        path = root / "Platform" / lesson / LIST
        if not path.is_file():
            continue
        data = _load(path, errors)
        if data is None:
            continue
        if not isinstance(data, dict) or set(data) != {"version", "model", "judge"} or data.get("version") != 1:
            errors.append((path, "a lesson list is an object with exactly version (1), model and judge"))
            continue
        moved.add(lesson)
        stats["export_lessons_with_lists"] += 1
        files = lesson_files(root, lesson)
        for side in ("model", "judge"):
            records = _records(path, data[side], side, errors)
            named = [r["path"] for r in records]
            for p in sorted(set(named) - files):
                errors.append((path, f"{side}: {p} is not a file of the lesson directory Platform/{lesson}/"))
            for p in sorted(files - set(named)):
                errors.append((path, f"{side}: the file {p} of the lesson has no record"))
            for p in sorted({p for p in named if named.count(p) > 1}):
                errors.append((path, f"{side}: {p} is named more than once"))
            take(side, path, records)

    by = {side: {r["path"]: r["disposition"] for r in assembled[side]} for side in assembled}
    model_paths, judge_paths = set(by["model"]), set(by["judge"])
    for p in sorted(model_paths - judge_paths):
        errors.append((root / COMMON["judge"], f"{p} has a record in M and none in J"))
    for p in sorted(judge_paths - model_paths):
        errors.append((root / COMMON["model"], f"{p} has a record in J and none in M"))

    for lesson in lessons:
        for rel, want in RULES.items():
            p = f"Platform/{lesson}/{rel}"
            if not (root / p).is_file():
                continue
            for side, disposition in want.items():
                have = by[side].get(p)
                if have is None:
                    continue  # a moved lesson reported it above; an unmoved one is counted in export_unlisted below
                if have != disposition:
                    leak = " — the routing of the judge would reach the model" if rel.endswith("routing.tsv") and side == "model" else ""
                    errors.append((root / seen[side][p], f"{side}: {p} is {have}, the rule gives {disposition}{leak}"))
        if lesson not in moved:
            stats["export_unlisted"] += len([p for p in lesson_files(root, lesson) if p not in model_paths])

    stats["export_model_records"] = len(assembled["model"])
    stats["export_judge_records"] = len(assembled["judge"])
    return assembled, errors, stats
