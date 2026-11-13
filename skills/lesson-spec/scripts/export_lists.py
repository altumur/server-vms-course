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

The roster (OBSH.58): every file of Platform/ — the lessons, common and the other files, the Russian mirrors among
them — is classified in both assembled filters, and the filters name no other path. The roster is the one the export
pair operator classifies (P02.52, `b7_export_pair._source` and `_classification`, «filter does not cover exact full J
roster»): every entry under Platform/ of the source tree and the source marker `Platform/COURSE_COMMIT` that the
operator adds before classifying. The source tree is
- in a git tree (a `.git` at the root): git's index — the operator reads the committed tree of C, what is not added is
  not in the export;
- in a tree without `.git` (a full source archive, `git archive` of C, as the pair preparation checks it): the files
  on disk under Platform/ — the archive is the committed tree.
So:
- a file of the roster without a record in M or in J is an error with its path and the filter (for a lesson with its
  list the list check above reports it);
- a record of the common filter that names no file of the roster (nor the marker) is an error;
- the marker as a file of the tree, and an entry under Platform/ that is not a regular file (a link, a submodule),
  are errors: the operator refuses both.
No ledger of exceptions and no partial mode: a root without Platform/ has nothing to cover; any other root is judged as
a whole source, whatever lessons the run names.

A file of a lesson that has not moved yet (no forms/export.json) and that no record names is counted in the stats
(`export_unlisted`); the roster check makes it an error of the common filters (ADR-0135 addendum (14)
item 4: such a lesson keeps its records in the common filters until it brings its list).

The third input Q (qualification, ADR-0130 addendum (20) item 1): the procedures of checking the production obligations
of M — the files `Platform/<lesson>/qualification/**` (translations `Platform/<lesson>/ru/qualification/**`; likewise
`Platform/common/qualification/**`). The qualifier reads Q, the model that writes the candidate does not. Checked here:
- Q is outside M: no Q file and no translation of one is model_and_judge in the assembled M (a Q file of a lesson with
  its list is judge_only there); a translation of Q is exclude in J, as any Russian mirror;
- the filter of Q `Platform/common/qualification-input-filter.json`, where it is (data without Q have none and are
  judged as before): exactly the fields version (1) and files; each record {path, disposition, basis} with disposition
  include (an inventory of the input file by file: what it does not name is outside Q), sorted by path as UTF-8 bytes,
  each path once; a path is an existing file under Platform/ (no mask), not a Russian mirror (Q is English only), not a
  filter of the export; every Q file of the tree is named; the filter itself is not model_and_judge in M;
- Q files without the filter are an error: a procedure that no filter names is lost to the qualifier.

`assemble(root)` → ({"model": [records], "judge": [records]}, errors, stats); errors are (path, message).
`qualification_files(root)` → the repository paths of the Q files of the tree (sources and translations).
`platform_roster(root)` → ({path: mode} of the entries under Platform/ of the source tree, its kind), or (None, why)
when git's index of a git tree cannot be read.
"""
import json
import os
import re
import stat
import subprocess
from pathlib import Path

COMMON = {"model": Path("Platform/common/export-model-filter.json"),
          "judge": Path("Platform/common/acceptance/judge-input-filter.json")}
QUALIFICATION = Path("Platform/common/qualification-input-filter.json")   # the filter of the third input Q
Q_DIR = "qualification"
LIST = Path("forms/export.json")
DISPOSITIONS = {"model": {"model_and_judge", "judge_only"}, "judge": {"include", "exclude"},
                "qualification": {"include"}}
RECORD_KEYS = {"path", "disposition", "basis"}
RULES = {  # item 3: the forms of the registry and of the list in every lesson
    "forms/targets.tsv": {"model": "model_and_judge", "judge": "include"},
    "forms/targets.routing.tsv": {"model": "judge_only", "judge": "include"},
    "forms/export.json": {"model": "judge_only", "judge": "exclude"},
}
LESSON_DIR = re.compile(r"^\d\d-[a-z0-9-]+$")
MARKER = "Platform/COURSE_COMMIT"   # the source marker the export pair operator adds to the roster (b7_export_pair.MARKER)
REGULAR = {"100644", "100755"}      # the only entries the operator takes


def lesson_dirs(root):
    platform = root / "Platform"
    return sorted(p.name for p in platform.iterdir() if p.is_dir() and LESSON_DIR.match(p.name)) if platform.is_dir() else []


def q_kind(path):
    """"source" for a Q file `Platform/<dir>/qualification/…`, "translation" for `Platform/<dir>/ru/qualification/…`,
    None for any other repository path (<dir> — a lesson directory or common)."""
    parts = str(path).split("/")
    if len(parts) < 4 or parts[0] != "Platform" or not (LESSON_DIR.match(parts[1]) or parts[1] == "common"):
        return None
    if parts[2] == Q_DIR:
        return "source"
    if parts[2] == "ru" and len(parts) > 4 and parts[3] == Q_DIR:
        return "translation"
    return None


def qualification_files(root):
    """The repository paths of the Q files of the tree, sources and translations."""
    root = Path(root)
    out = set()
    for home in [*lesson_dirs(root), "common"]:
        if (root / "Platform" / home).is_dir():
            out |= {p for p in lesson_files(root, home) if q_kind(p)}
    return out


def lesson_files(root, lesson):
    """The files of a lesson directory as repository paths: git's tracked files when the root is a git tree, else the walk."""
    rel = f"Platform/{lesson}"
    if (root / ".git").exists():
        done = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", rel], capture_output=True)
        if done.returncode == 0:
            return {p for p in done.stdout.decode("utf-8").split("\0") if p}
    return {p.relative_to(root).as_posix() for p in (root / rel).rglob("*") if p.is_file()}


def platform_roster(root):
    """The roster of the export operator without its marker: ({path: mode} of the entries under Platform/, source).
    A git tree gives git's index (source "git index"); a tree without .git gives the files on disk (source "files"),
    with the modes of git: 100755 executable, 100644 other regular files, 120000 a link (a link to a directory is not
    entered). (None, why) when the index of a git tree cannot be read."""
    root = Path(root)
    if (root / ".git").exists():
        done = subprocess.run(["git", "-C", str(root), "ls-files", "-s", "-z", "--", "Platform"], capture_output=True)
        if done.returncode != 0:
            return None, done.stderr.decode("utf-8", "replace").strip() or f"git ls-files exit {done.returncode}"
        roster = {}
        for raw in done.stdout.decode("utf-8").split("\0"):
            if raw:
                meta, path = raw.split("\t", 1)
                roster[path] = meta.split()[0]
        return roster, "git index"
    roster = {}
    for top, dirs, files in os.walk(root / "Platform"):
        for name in [*dirs, *files]:
            path = Path(top) / name
            if name in dirs and not path.is_symlink():
                continue
            mode = path.lstat().st_mode
            kind = ("120000" if stat.S_ISLNK(mode) else
                    ("100755" if mode & 0o111 else "100644") if stat.S_ISREG(mode) else "other")
            roster[path.relative_to(root).as_posix()] = kind
    return roster, "files"


def roster_coverage(root, by, seen, moved, errors, stats):
    """Every file of the roster has a record in M and in J, and the common filters name no other path (OBSH.58)."""
    roster, source = platform_roster(root)
    if roster is None:
        errors.append((root / ".git", f"git's index is unreadable ({source}) — the roster of Platform/ is not known"))
        return
    stats["export_roster_files"] = len(roster)
    if MARKER in roster:
        errors.append((root / MARKER, f"{MARKER} is a file of the tree ({source}) — the export operator adds the "
                                      "source marker itself and refuses a tree that already has it"))
    for p, mode in sorted(roster.items()):
        if mode not in REGULAR:
            errors.append((root / p, f"{p} is an entry of mode {mode} ({source}) — the export operator takes only "
                                     "regular files (100644, 100755)"))
    expected = set(roster) | {MARKER}

    def listed(p):  # a file of a lesson with its list: the list check reports it missing
        parts = p.split("/")
        return len(parts) > 2 and parts[1] in moved

    for side, rel in COMMON.items():
        named = set(by[side])
        for p in sorted(expected - named):
            if not listed(p):
                errors.append((root / rel, f"{side}: the file {p} of Platform has no record in {rel.as_posix()} — the "
                                           "export operator refuses a filter that does not cover the exact roster"))
        for p in sorted(named - expected):
            if seen[side][p] == root / rel:  # a lesson list reports a record outside its lesson itself
                errors.append((root / seen[side][p], f"{side}: {p} has a record and is no file of Platform ({source}) "
                                                     "— the export operator refuses a filter wider than the roster"))


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
    model_paths = set(by["model"])
    if (root / "Platform").is_dir():
        roster_coverage(root, by, seen, moved, errors, stats)   # M and J both equal the roster

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
    qualification(root, by, seen, errors, stats)
    return assembled, errors, stats


def qualification(root, by, seen, errors, stats):
    """The input Q: Q outside M, the translations of Q outside the exports, the form and the composition of its filter."""
    q_files = qualification_files(root)
    sources = sorted(p for p in q_files if q_kind(p) == "source")
    stats["qualification_files"] = len(sources)
    for p in sorted(set(by["model"]) | q_files):
        kind = q_kind(p)
        if kind is None:
            continue
        if by["model"].get(p) == "model_and_judge":
            errors.append((root / seen["model"][p], f"model: {p} is model_and_judge — a file of the input Q "
                                                    "(qualification) is outside M, the model that writes the candidate "
                                                    "does not read it: judge_only"))
        if kind == "translation" and by["judge"].get(p, "exclude") != "exclude":
            errors.append((root / seen["judge"][p], f"judge: {p} is {by['judge'][p]} — a Russian mirror of Q is "
                                                    "outside the exports: exclude"))
    path, rel = root / QUALIFICATION, QUALIFICATION.as_posix()
    if by["model"].get(rel) == "model_and_judge":
        errors.append((root / seen["model"][rel], f"model: {rel} is model_and_judge — the filter of Q is outside M: "
                                                  "judge_only"))
    if not path.is_file():
        if sources:
            errors.append((path, f"the filter of the input Q is missing, and the tree has Q files ({', '.join(sources)}): "
                                 "a procedure that no filter names is lost to the qualifier"))
        return
    data = _load(path, errors)
    if data is None:
        return
    if not isinstance(data, dict) or set(data) != {"version", "files"} or data.get("version") != 1:
        errors.append((path, "the filter of Q is an object with exactly version (1) and files"))
        return
    named = [r["path"] for r in _records(path, data["files"], "qualification", errors)]
    stats["qualification_records"] = len(named)
    filters = {rel, *(c.as_posix() for c in COMMON.values())}
    for p in sorted({p for p in named if named.count(p) > 1}):
        errors.append((path, f"files: {p} is named more than once"))
    for p in sorted(set(named)):
        if not p.startswith("Platform/") or any(c in p for c in "*?[") or not (root / p).is_file():
            errors.append((path, f"files: {p} is not a file of the tree under Platform/ (a record names one existing "
                                 "file, no mask)"))
        elif q_kind(p) == "translation" or "/ru/" in p:
            errors.append((path, f"files: {p} is a Russian mirror — the input Q is English only"))
        elif p in filters:
            errors.append((path, f"files: {p} is a filter of the export, not an input of the qualifier"))
    for p in sources:
        if p not in named:
            errors.append((path, f"files: the Q file {p} has no record — every qualification file is in the input Q"))
