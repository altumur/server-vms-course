"""Select normgen lesson paths, Go modules, kit directories and chapter norms from Platform/lessons.tsv (ADR-0125 addendum 5, item 2). select() removes --lesson NN-name or --lesson=NN-name from argv; otherwise use NORMGEN_LESSON, then01-store. One process selects one lesson, read at generator/build_kit import. P/01 retains out/p01-1, normgen/p01-1, p01store/01-store for byte compatibility; others use out/pNN, normgen/pNN, pNN<name>/NN-name."""
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LESSONS = ROOT / "Platform/lessons.tsv"
DEFAULT = "01-store"
ENV = "NORMGEN_LESSON"
KEY = re.compile(r"(0[1-9]|[1-9][0-9])-[a-z][a-z0-9-]*")
OUTPUT_ENV = "NORMGEN_OUT"
PROFILES = ("p01-1", "p02", "p03", "p04", "p05", "p06", "p08", "p09", "p10")
OUTPUT_MANIFEST = "normgen-output.manifest.json"
_temporary_output = None
_output_path = None


class LessonError(Exception):
    pass


def output_root():
    """One external root per process; children inherit it, only its creator cleans it."""
    global _temporary_output, _output_path
    if _output_path is None:
        given = os.environ.get(OUTPUT_ENV)
        if given:
            if not Path(given).is_absolute():
                raise LessonError(f"{OUTPUT_ENV} must be an absolute external directory")
            _output_path = Path(given).resolve()
        else:
            _temporary_output = tempfile.TemporaryDirectory(prefix="normgen-output-")
            _output_path = Path(_temporary_output.name)
            os.environ[OUTPUT_ENV] = str(_output_path)
        if _output_path.is_relative_to(HERE):
            raise LessonError(f"{OUTPUT_ENV} must be outside tools/normgen; repository out is not an input")
    return _output_path


def owns_output_root():
    return _temporary_output is not None


def _profiles(values):
    if type(values) not in (list, tuple) or not values or any(type(p) is not str for p in values):
        raise LessonError("output profiles must be a nonempty list without duplicates")
    if len(values) != len(set(values)):
        raise LessonError("output profiles must be a nonempty list without duplicates")
    if any(type(p) is not str or p not in PROFILES for p in values):
        raise LessonError(f"output profiles must be selected from {PROFILES}; P07 has no profile")
    return tuple(values)


def _relative(value):
    if (type(value) is not str or not value or "\\" in value or
            PurePosixPath(value).is_absolute() or str(PurePosixPath(value)) != value or
            any(p in (".", "..") for p in value.split("/")) or
            any(ord(c) < 32 for c in value)):
        raise LessonError(f"not a relative output/input path: {value!r}")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise LessonError("non-scalar path in output manifest") from None
    return value


def _scan(root, scopes, *, code=False, manifest=False):
    """Record physical files/directories, never follow symlinks or inspect Git-out."""
    root = Path(root).resolve()
    records = []
    for scope in scopes:
        start = root / scope if scope else root
        if not start.is_dir() or start.is_symlink():
            raise LessonError(f"missing regular input/output directory: {start}")
        pending = [start] if scope else list(start.iterdir())
        while pending:
            p = pending.pop()
            rel = p.relative_to(root).as_posix()
            if manifest and rel == OUTPUT_MANIFEST:
                continue
            if code and (rel == "tools/normgen/out" or rel.startswith("tools/normgen/out/") or
                         "__pycache__" in p.parts or p.suffix == ".pyc"):
                continue
            mode = p.lstat().st_mode
            if stat.S_ISDIR(mode):
                records.append({"path": rel, "type": "directory", "mode": stat.S_IMODE(mode),
                                "bytes": 0, "sha256": None})
                pending.extend(p.iterdir())
            elif stat.S_ISREG(mode):
                data = p.read_bytes()
                records.append({"path": rel, "type": "file", "mode": stat.S_IMODE(mode),
                                "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            else:
                raise LessonError(f"non-regular input/output path: {p}")
    if not any(r["type"] == "file" for r in records):
        raise LessonError(f"empty input/output file roster: {root}")
    return sorted(records, key=lambda r: r["path"])


def output_inputs(source_root=ROOT, code_root=ROOT, *, kind="current"):
    """Exact source/code/runtime byte identities; historical donors are explicit."""
    source_scopes = ["Platform"]
    if kind == "historical" and (Path(source_root) / "Source/tests/testdata").is_dir():
        source_scopes.append("Source/tests/testdata")
    return {"source": _scan(source_root, source_scopes),
            "code": _scan(code_root, ["tools/normgen"], code=True)}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise LessonError(f"duplicate output manifest key: {key}")
        result[key] = value
    return result


def _records(value):
    if not isinstance(value, list) or not value:
        raise LessonError("empty output/input manifest roster")
    seen = set()
    for row in value:
        if type(row) is not dict or set(row) != {"path", "type", "mode", "bytes", "sha256"}:
            raise LessonError("malformed output/input file record")
        path = _relative(row["path"])
        if path in seen:
            raise LessonError(f"duplicate output/input path: {path}")
        seen.add(path)
        if (row["type"] not in ("file", "directory") or type(row["mode"]) is not int or
                not 0 <= row["mode"] <= 0o7777 or type(row["bytes"]) is not int or row["bytes"] < 0):
            raise LessonError(f"malformed mode/type/size: {path}")
        if row["type"] == "directory":
            if row["bytes"] != 0 or row["sha256"] is not None:
                raise LessonError(f"malformed directory record: {path}")
        elif type(row["sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise LessonError(f"malformed SHA256: {path}")
    return sorted(value, key=lambda r: r["path"])


def output_manifest(output_root=None):
    """Read metadata only. This function never prepares or repairs a set."""
    root = Path(output_root or globals()["output_root"]()).resolve()
    path = root / OUTPUT_MANIFEST
    if not path.is_file() or path.is_symlink():
        raise LessonError(f"prepared output manifest is missing: {path}; create a new set explicitly")
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise LessonError("prepared output manifest mode changed")
    try:
        def nonfinite(value):
            raise LessonError(f"non-finite output metadata: {value}")
        value = json.loads(path.read_bytes(), object_pairs_hook=_unique, parse_constant=nonfinite)
    except (ValueError, UnicodeError) as exc:
        raise LessonError(f"invalid output manifest: {exc}") from None
    if type(value) is not dict or set(value) != {"version", "context", "profiles", "parts", "inputs", "files"}:
        raise LessonError("malformed prepared output manifest")
    if type(value["version"]) is not int or value["version"] != 1:
        raise LessonError("unknown prepared output manifest version")
    declared = _profiles(value["profiles"])
    context = value["context"]
    if type(context) is not dict or not {"kind"} <= set(context) <= {"kind", "course_commit", "export_commit", "source_pin"}:
        raise LessonError("malformed output context")
    if context["kind"] not in ("current", "component", "historical", "export"):
        raise LessonError("unknown output context")
    if context["kind"] == "current" and set(declared) != set(PROFILES):
        raise LessonError("current full output requires all nine profiles")
    for key in set(context) - {"kind"}:
        if context[key] is not None and (type(context[key]) is not str or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", context[key])):
            raise LessonError(f"invalid pinned output context: {key}")
    if type(value["parts"]) is not dict or set(value["parts"]) != set(declared):
        raise LessonError("output parts do not cover the declared profiles")
    for parts in value["parts"].values():
        if (type(parts) is not list or not parts or any(type(p) is not str or not re.fullmatch(r"[a-z][a-z0-9-]*", p) for p in parts)
                or len(parts) != len(set(parts))):
            raise LessonError("empty/duplicate/malformed output parts")
    if type(value["inputs"]) is not dict or set(value["inputs"]) != {"source", "code"}:
        raise LessonError("missing source/code identities")
    for group in ("source", "code"):
        _records(value["inputs"][group])
    records = _records(value["files"])
    if any(r["path"].split("/", 1)[0] not in declared for r in records):
        raise LessonError("output path outside the declared profile roster")
    for slug in declared:
        files = [r for r in records if r["path"].startswith(slug + "/") and r["type"] == "file"]
        if len(files) < 2 or not any(r["path"] == slug + "/go/go.mod" and r["bytes"] for r in files):
            raise LessonError(f"empty/incomplete output profile: {slug}")
    return value


def record_outputs(output_root, *, source_root=ROOT, code_root=ROOT, profiles=PROFILES,
                   parts, context, inputs):
    """Seal one newly created set; preparation is the caller's separate phase."""
    root = Path(output_root).resolve()
    if (root / OUTPUT_MANIFEST).exists():
        raise LessonError("output set already exists; prepare a new root")
    if inputs != output_inputs(source_root, code_root, kind=context["kind"]):
        raise LessonError("inputs changed during preparation; no ready set was published")
    payload = {"version": 1, "context": context, "profiles": list(_profiles(profiles)),
               "parts": parts, "inputs": inputs, "files": _scan(root, [""], manifest=True)}
    target = root / OUTPUT_MANIFEST
    target.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    target.chmod(0o600)
    try:
        return ready_outputs(output_root=root, source_root=source_root, code_root=code_root, profiles=profiles)
    except Exception:
        target.unlink()
        raise


def ready_outputs(output_root=None, source_root=ROOT, code_root=ROOT, profiles=PROFILES):
    """Validate, then return slug→absolute Path. No writes, render or regeneration."""
    given = Path(output_root or globals()["output_root"]())
    if given.is_symlink() or not given.is_absolute():
        raise LessonError("output root must be an absolute regular directory")
    root = given.resolve()
    if root.is_relative_to(Path(code_root).resolve() / "tools/normgen"):
        raise LessonError("repository out cannot be consumed as a ready set")
    expected = _profiles(profiles)
    value = output_manifest(root)
    if set(value["profiles"]) != set(expected):
        raise LessonError("missing/extra prepared profiles for the requested context")
    if value["inputs"] != output_inputs(source_root, code_root, kind=value["context"]["kind"]):
        raise LessonError("prepared output inputs/code/runtime changed; prepare a new set explicitly")
    if _records(value["files"]) != _scan(root, [""], manifest=True):
        raise LessonError("prepared output is missing/extra/changed (mode/type/size/SHA); no regeneration performed")
    return {slug: root / slug for slug in expected}


class Lesson:
    def __init__(self, nn, key, process):
        self.nn, self.key, self.process = nn, key, process
        self.name = key.split("-", 1)[1]                       # store, installer, domain-console
        self.code = f"P/{nn}"
        self.rel = f"Platform/{key}"
        self.dir = ROOT / self.rel
        self.slug = "p01-1" if key == DEFAULT else f"p{nn}"
        self.out = output_root() / self.slug
        self.go_module = f"normgen/{self.slug}"
        self.kit_dir = key                                     # <dst>/<kit_dir>/internal
        self.module = f"p{nn}{self.name.replace('-', '')}/{key}"   # p01store/01-store

    def __repr__(self):
        return f"Lesson({self.key})"

    def output_source(self, path, out=None):
        """Stable provenance label for generated bytes, never a current Git input."""
        return (PurePosixPath("tools/normgen/out") / self.slug /
                Path(path).relative_to(Path(out) if out is not None else self.out).as_posix()).as_posix()

    def path(self, *parts):
        return self.dir.joinpath(*parts)

    def spec(self, name):
        return self.dir / "spec" / name

    def norms(self, chapter=None):
        """Resolve chapter norms as spec/NN.K-name.norms.md, or NN-name.norms.md for a single-file lesson."""
        if chapter is None:
            return self.spec(f"{self.key}.norms.md")
        return self.spec(f"{self.nn}.{chapter}-{self.name}.norms.md")

    def chapters(self):
        """Return numeric chapter names sorted by number, or [] for single-file lessons."""
        pat = re.compile(re.escape(self.nn) + r"\.(\d+)-" + re.escape(self.name) + r"\.norms\.md")
        found = [m[1] for p in (self.dir / "spec").glob("*.norms.md") if (m := pat.fullmatch(p.name))]
        return sorted(found, key=int)

    @property
    def openapi(self):
        return self.spec(f"{self.key}.api.openapi.yaml")

    def form(self, name):
        return self.dir / "forms" / name


def lessons():
    out = {}
    for line in LESSONS.read_text(encoding="utf-8").split("\n"):
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 4:
            raise LessonError(f"{LESSONS}: line {line!r}: want number, directory, title, process")
        out[cols[1]] = Lesson(cols[0], cols[1], cols[3])
    return out


def get(key):
    if not KEY.fullmatch(key or ""):
        raise LessonError(f"--lesson {key!r}: want NN-<name> (a directory of Platform/lessons.tsv)")
    known = lessons()
    if key not in known:
        raise LessonError(f"--lesson {key!r}: not in {LESSONS.relative_to(ROOT)} ({', '.join(known)})")
    return known[key]


def select(argv=None):
    """Select a lesson from --lesson (removed from argv), then NORMGEN_LESSON, then01-store."""
    argv = sys.argv if argv is None else argv
    key = None
    for i, a in enumerate(list(argv)):
        if a == "--lesson" and i + 1 < len(argv):
            key = argv[i + 1]
            del argv[i:i + 2]
            break
        if a.startswith("--lesson="):
            key = a.split("=", 1)[1]
            del argv[i]
            break
    key = key or os.environ.get(ENV) or DEFAULT
    os.environ[ENV] = key                                      # Export-build child processes inherit the same lesson.
    return get(key)


try:
    CURRENT = select()
except LessonError as exc:
    print(f"normgen: {exc}", file=sys.stderr)
    raise SystemExit(2)


def require(lesson, what, supported=(DEFAULT,)):
    """Restrict this generator to supported lessons; reject with the lesson name rather than silently using P/01."""
    if lesson.key not in supported:
        raise LessonError(f"{what}: no declaration for lesson {lesson.key} (declared: {', '.join(supported)})")
