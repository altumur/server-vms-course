"""Select normgen lesson paths, Go modules, kit directories and chapter norms from Platform/lessons.tsv (ADR-0125 addendum 5, item 2). select() removes --lesson NN-name or --lesson=NN-name from argv; otherwise use NORMGEN_LESSON, then01-store. One process selects one lesson, read at generator/build_kit import. P/01 retains out/p01-1, normgen/p01-1, p01store/01-store for byte compatibility; others use out/pNN, normgen/pNN, pNN<name>/NN-name."""
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LESSONS = ROOT / "Platform/lessons.tsv"
DEFAULT = "01-store"
ENV = "NORMGEN_LESSON"
KEY = re.compile(r"(0[1-9]|[1-9][0-9])-[a-z][a-z0-9-]*")


class LessonError(Exception):
    pass


class Lesson:
    def __init__(self, nn, key, process):
        self.nn, self.key, self.process = nn, key, process
        self.name = key.split("-", 1)[1]                       # store, installer, domain-console
        self.code = f"P/{nn}"
        self.rel = f"Platform/{key}"
        self.dir = ROOT / self.rel
        self.slug = "p01-1" if key == DEFAULT else f"p{nn}"
        self.out = HERE / "out" / self.slug
        self.go_module = f"normgen/{self.slug}"
        self.kit_dir = key                                     # <dst>/<kit_dir>/internal
        self.module = f"p{nn}{self.name.replace('-', '')}/{key}"   # p01store/01-store

    def __repr__(self):
        return f"Lesson({self.key})"

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
