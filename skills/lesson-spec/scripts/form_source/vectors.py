"""Глава 2.2 «Канонический вид» в раскладке курса: векторы `canonical` (P/02.2-07), их генератор, проба мутаций,
приёмка `puts.tsv` с колонкой вида и проверка главы для check_spec.

Векторы — `Platform/02-installer/vectors/canonical/`: `README.md`, `cases.tsv` (`case<TAB>input<TAB>expect<TAB>note`),
`expect/<case>.json` — байты `spec` (JCS, UTF-8, без перевода строки в конце), необязательный `inputs/` — входы строк-
примеров. `input` — путь файла спеки от корня раскладки (`/`, без `..`), принятого загрузчиком главы 2.1; `expect` — ровно
`expect/<case>.json`. Строки `corpus-<случай>` (каждый `ok` случай корпуса 2.1) и `course-<имя>` (каждая спека курса)
и все ожидания строит generate(); прочие строки — примеры автора, их порядок и входы генератор сохраняет.
"""
import json
import re
from pathlib import Path

from .canonical import BEGIN, END, STEPS, build_view_section, canonical, jcs, schema_text, steps_of, tree_of, \
    unique_names, view_schema
from .judge import Loader
from .source import SourceError, all_nodes

LESSON = Path("Platform/02-installer")
SOURCE = LESSON / "spec/02.1-installer"
NORMS = LESSON / "spec/02.2-installer.norms.md"
SCHEMA_FILE = LESSON / "spec/02.2-installer.canonical.schema.json"     # необязателен: если есть — построенный
CORPUS = LESSON / "acceptance/1"
ACCEPTANCE = LESSON / "acceptance/2"
VECTORS = LESSON / "vectors/canonical"
COURSE_SPECS = (Path("Source/vms"), Path("Source/tests/testdata"))
HEADER = ["case", "input", "expect", "note"]
CASE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
GENERATED = ("corpus-", "course-")
VECTOR_ENTRIES = {"README.md", "cases.tsv", "expect", "inputs"}
COMMENT = ("# Векторы canonical главы P/02.2 (P/02.2-07): байты спеки → байты `spec` канонического вида (без обёртки, Р13).\n"
           "# Строка: case<TAB>input<TAB>expect<TAB>note; input — путь спеки от корня раскладки, expect — expect/<case>.json.\n"
           "# Строки corpus-*, course-* и все ожидания строит построитель (form_source/build_canonical.py vectors); правила — README.\n")
PUTS_DIRECTIVES = {"@view-delete", "@view-spoil"}
PUTS_FILE = re.compile(r"[a-z0-9][a-z0-9_-]*")
EXPECT = re.compile(r"(0|2) ([1-9][0-9]*|-)")


def loader(root):
    base = Path(root) / SOURCE
    return Loader(*(Path(str(base) + s) for s in (".form.yaml", ".references.tsv", ".scalars.tsv")))


def present(root):
    """Есть ли у главы 2.2 хоть один файл (нормы, векторы, приёмка): без них проверка пропускается."""
    return any((Path(root) / p).exists() for p in (NORMS, VECTORS, ACCEPTANCE))


def _tsv(text, width):
    """[(номер строки, поля)] без комментариев, пустых строк и заголовка; ширина не та — ValueError."""
    out = []
    for no, line in enumerate(text.split("\n"), 1):
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) != width:
            raise ValueError("line %d: expected %d TSV columns, got %d" % (no, width, len(cols)))
        out.append((no, cols))
    return out


def accepted_inputs(root):
    """[(case, путь от корня)]: ok-случаи корпуса 2.1 по verdicts.tsv и спеки курса — по имени, без повторов."""
    root = Path(root)
    out = []
    verdicts = root / CORPUS / "verdicts.tsv"
    if verdicts.exists():
        for _, (case, verdict) in _tsv(verdicts.read_text(encoding="utf-8"), 2):
            if verdict == "ok":
                out.append(("corpus-" + case, (CORPUS / "cases" / (case + ".subsystem.yaml")).as_posix()))
    for d in COURSE_SPECS:
        for p in sorted((root / d).glob("*.subsystem.yaml")):
            out.append(("course-" + p.name[:-len(".subsystem.yaml")], (d / p.name).as_posix()))
    return sorted(out)


def read_cases(path):
    """cases.tsv → (строки комментария до заголовка, [(номер, case, input, expect, note)]); ошибка формы — ValueError."""
    text = Path(path).read_text(encoding="utf-8")
    if text.startswith("﻿") or "\r" in text:
        raise ValueError("BOM or CR")
    lead = []
    for line in text.split("\n"):
        if line.startswith("#"):
            lead.append(line)
        else:
            break
    rows, header = [], False
    for no, cols in _tsv(text, 4):
        if cols == HEADER and not header and not rows:
            header = True
            continue
        rows.append((no, *cols))
    if not header:
        raise ValueError("the first row is the header %s" % "<TAB>".join(HEADER))
    return lead, rows


def input_path(root, value):
    """Путь входа от корня или None, если он не по форме (абсолютный, `..`, `\\`, не `.subsystem.yaml`)."""
    parts = value.split("/")
    if not value or value.startswith("/") or "\\" in value or any(p in ("", ".", "..") for p in parts) \
            or not value.endswith(".subsystem.yaml"):
        return None
    return Path(root) / value


def expected_bytes(ld, data, skip=()):
    if ld.judge(data)["verdict"] != "ok":
        return None
    return jcs(canonical(ld.form, tree_of(data), skip)).encode("utf-8")


def generate(root):
    """Переписать cases.tsv и expect/ главы 2.2 по всем входам: строки автора — как были, corpus-*/course-* — заново.
    Повтор на тех же входах даёт те же байты. Вход автора, который загрузчик не принимает, — SourceError, ничего не
    записано. Возвращает число строк."""
    root = Path(root)
    ld = loader(root)
    vec = root / VECTORS
    lead, rows = [], []
    if (vec / "cases.tsv").exists():
        try:
            lead, rows = read_cases(vec / "cases.tsv")
        except ValueError as exc:
            raise SourceError("%s: %s" % (VECTORS / "cases.tsv", exc))
    author = [(case, inp, note) for _, case, inp, _, note in rows if not case.startswith(GENERATED)]
    notes = {case: note for _, case, _, _, note in rows if case.startswith(GENERATED)}
    gen = [(case, inp, notes.get(case) or ("принятый случай корпуса 2.1" if case.startswith("corpus-") else "спека курса"))
           for case, inp in accepted_inputs(root)]
    out, seen = [], set()
    for case, inp, note in author + gen:
        if not CASE.fullmatch(case) or case in seen:
            raise SourceError("cases.tsv: case %r is not unique or not [A-Za-z0-9][A-Za-z0-9_.-]*" % case)
        seen.add(case)
        p = input_path(root, inp)
        if p is None or not p.is_file():
            raise SourceError("cases.tsv: case %s: input %r is not a spec file under the root" % (case, inp))
        b = expected_bytes(ld, p.read_bytes())
        if b is None:
            raise SourceError("cases.tsv: case %s: the loader of 2.1 refuses %s" % (case, inp))
        out.append((case, inp, note, b))
    (vec / "expect").mkdir(parents=True, exist_ok=True)
    text = ("\n".join(lead) + "\n" if lead else COMMENT) + "\t".join(HEADER) + "\n"
    text += "".join("%s\t%s\texpect/%s.json\t%s\n" % (case, inp, case, note) for case, inp, note, _ in out)
    (vec / "cases.tsv").write_text(text, encoding="utf-8")
    keep = {case + ".json" for case, *_ in out}
    for p in (vec / "expect").iterdir():
        if p.name not in keep and p.is_file():
            p.unlink()
    for case, _, _, b in out:
        p = vec / "expect" / (case + ".json")
        if not p.exists() or p.read_bytes() != b:
            p.write_bytes(b)
    return len(out)


# ---------------------------------------------------------------- проба мутаций (ADR-0089 Confirmation)

def mutants(form):
    """[(имя, сделать, вернуть)]: снять каждый default и каждый ordered в источнике, пропустить каждый шаг урока 2."""
    out = []
    for n in all_nodes(form):
        if "default" in n.notes:
            def do(n=n):
                n.mutant = n.notes.pop("default")

            def undo(n=n):
                n.notes["default"] = n.mutant
            out.append(("default %s" % n.where, do, undo))
        if n.ordered:
            def do(n=n):
                n.ordered = False

            def undo(n=n):
                n.ordered = True
            out.append(("ordered %s" % n.where, do, undo))
    for s in STEPS:
        out.append(("step %s" % s.name, s.name, None))
    return out


def probe(form, trees, built):
    """Имена мутантов, на которых все векторы дают прежние байты (мутант выжил: векторы правило не держат)."""
    alive = []
    for name, do, undo in mutants(form):
        if undo is None:
            skip, do = (do,), None
        else:
            skip = ()
            do()
        try:
            if all(jcs(canonical(form, t, skip)).encode("utf-8") == b for t, b in zip(trees, built)):
                alive.append(name)
        finally:
            if undo is not None:
                undo()
    return alive


# ---------------------------------------------------------------- проверка главы 2.2

class Chapter:
    """Проверка главы 2.2 для check_spec: errors — [(путь от корня, сообщение)], stats — счёты COUNTS."""

    def __init__(self, root, strict=False):
        self.root, self.strict = Path(root), strict
        self.errors, self.stats = [], {}
        self.validator = self.schema = None
        self.vectors = {}                                    # case → ожидаемые байты (для puts.tsv)

    def error(self, path, message):
        self.errors.append((Path(path), message))

    def run(self):
        if not present(self.root):
            self.stats["canonical"] = "absent"
            return self
        self.stats["canonical"] = "present"
        try:
            self.ld = loader(self.root)
        except SourceError as exc:
            self.error(SOURCE.with_suffix(".form.yaml"), "canonical: form source: %s" % exc)
            return self
        missing = [s.name for s in STEPS if s not in steps_of(self.ld.form)]
        if missing:
            self.error(Path(str(SOURCE) + ".form.yaml"), "canonical: steps %s have no place in the form" % ", ".join(missing))
        self.views()
        self.section()
        self.schema_file()
        self.cases()
        if (self.root / ACCEPTANCE / "puts.tsv").exists():
            self.stats["canonical_puts"] = self.puts(ACCEPTANCE)
        return self

    def views(self):
        """Вид каждого принятого входа (корпус 2.1, спеки курса) проходит построенную схему (ADR-0089 Confirmation)."""
        try:
            import jsonschema
        except ImportError as exc:
            self.error(NORMS, "canonical: the schema check needs jsonschema, missing: %s" % exc)
            return
        try:
            self.schema = view_schema(self.ld.form)
            jsonschema.Draft202012Validator.check_schema(self.schema)
        except (SourceError, jsonschema.SchemaError) as exc:
            self.error(Path(str(SOURCE) + ".form.yaml"), "canonical: built schema: %s" % str(exc).split("\n")[0])
            return
        self.validator = jsonschema.Draft202012Validator(self.schema)
        n = 0
        for case, inp in accepted_inputs(self.root):
            p = self.root / inp
            try:
                b = expected_bytes(self.ld, p.read_bytes())
            except OSError:
                continue
            if b is None:
                continue                                         # отказ — дело проверки корпуса и спек курса
            self.view(Path(inp), b)
            n += 1
        self.stats["canonical_views"] = n

    def view(self, where, b):
        """Вид проходит построенную схему и не повторяет `name` в списке `ordered`."""
        if getattr(self, "validator", None) is None:
            return
        v = json.loads(b)
        bad = sorted(self.validator.iter_errors(v), key=lambda e: list(map(str, e.absolute_path)))
        if bad:
            e = bad[0]
            self.error(where, "canonical: the view does not pass the built schema at /%s: %s"
                       % ("/".join(map(str, e.absolute_path)), e.message[:200]))
        for at in unique_names(self.schema, v):
            self.error(where, "canonical: the view repeats a name in the ordered list at %s" % at)

    def section(self):
        path = self.root / NORMS
        if not path.exists():
            return
        lines = path.read_text(encoding="utf-8").split("\n")
        begins = [i for i, x in enumerate(lines) if x == BEGIN]
        ends = [i for i, x in enumerate(lines) if x == END]
        if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
            self.error(NORMS, "canonical: the norms hold the built section once, between %s and %s (P/02.2-05)" % (BEGIN, END))
            return
        said = "\n".join(lines[begins[0] + 1:ends[0]]) + "\n"
        built = build_view_section(self.ld.form)
        if said != built:
            old, new = said.splitlines(), built.splitlines()
            at = next((i for i, (a, b) in enumerate(zip(old, new)) if a != b), min(len(old), len(new)))
            self.error(NORMS, "canonical: the section differs from the built one at its line %d (rebuild: python "
                              "skills/lesson-spec/scripts/form_source/build_canonical.py section %s)" % (at + 1, NORMS))

    def schema_file(self):
        path = self.root / SCHEMA_FILE
        if path.exists() and path.read_text(encoding="utf-8") != schema_text(self.ld.form):
            self.error(SCHEMA_FILE, "canonical: the schema differs from the built one (rebuild: python "
                                    "skills/lesson-spec/scripts/form_source/build_canonical.py schema %s)" % SCHEMA_FILE)

    def cases(self):
        vec = self.root / VECTORS
        self.stats["canonical_vectors"] = 0
        if not vec.exists():
            return
        rebuild = "rebuild: python skills/lesson-spec/scripts/form_source/build_canonical.py vectors"
        for p in sorted(vec.iterdir()):
            if p.name not in VECTOR_ENTRIES and p.name != ".DS_Store":
                self.error(VECTORS / p.name, "canonical: unsupported entry of the vectors (README.md, cases.tsv, expect/, inputs/)")
        if not (vec / "README.md").is_file():
            self.error(VECTORS, "canonical: the vectors need README.md (the format, P/02.2-07)")
        try:
            _, rows = read_cases(vec / "cases.tsv")
        except (OSError, UnicodeError, ValueError) as exc:
            self.error(VECTORS / "cases.tsv", "canonical: %s" % exc)
            return
        seen, inputs, trees, built = set(), set(), [], []
        accepted = {inp for _, inp in accepted_inputs(self.root)}
        for no, case, inp, expect, _ in rows:
            where = VECTORS / "cases.tsv"
            if not CASE.fullmatch(case) or case in seen:
                self.error(where, "line %d: case %r is not unique or not [A-Za-z0-9][A-Za-z0-9_.-]*" % (no, case))
                continue
            seen.add(case)
            if expect != "expect/%s.json" % case:
                self.error(where, "line %d: expect must be expect/%s.json" % (no, case))
            p = input_path(self.root, inp)
            if p is None or not p.is_file():
                self.error(where, "line %d: input %r is not a spec file under the root (a path from the root, "
                                  "without ..)" % (no, inp))
                continue
            inputs.add(inp)
            data = p.read_bytes()
            b = expected_bytes(self.ld, data)
            if b is None:
                self.error(where, "line %d: the loader of 2.1 refuses the input %s: a vector needs an accepted spec" % (no, inp))
                continue
            self.vectors[case] = b
            if inp not in accepted:
                self.view(Path(inp), b)                         # строка-пример: её вид — та же схема
            trees.append(tree_of(data))
            built.append(b)
            e = vec / "expect" / (case + ".json")
            if not e.is_file():
                self.error(VECTORS / "expect" / e.name, "canonical: missing (%s)" % rebuild)
            elif e.read_bytes() != b:
                self.error(VECTORS / "expect" / e.name, "canonical: differs from the built view (%s)" % rebuild)
        for case, inp in accepted_inputs(self.root):
            if inp not in inputs:
                self.error(VECTORS / "cases.tsv", "canonical: no vector for the accepted input %s (%s)" % (inp, rebuild))
        if (vec / "expect").is_dir():
            for p in sorted((vec / "expect").iterdir()):
                if p.name != ".DS_Store" and p.name[:-len(".json")] not in seen:
                    self.error(VECTORS / "expect" / p.name, "canonical: no row of cases.tsv names it")
        if (vec / "inputs").is_dir():
            for p in sorted((vec / "inputs").rglob("*")):
                if p.is_file() and p.name != ".DS_Store" and p.relative_to(self.root).as_posix() not in inputs:
                    self.error(p.relative_to(self.root), "canonical: no row of cases.tsv takes this input")
        self.stats["canonical_vectors"] = len(built)
        if not built:
            return
        alive = probe(self.ld.form, trees, built)
        total = len(mutants(self.ld.form))
        self.stats["canonical_mutants"] = total
        self.stats["canonical_mutants_killed"] = total - len(alive)
        if self.strict:
            for name in alive:
                self.error(VECTORS / "cases.tsv", "canonical: mutant «%s» changes no vector — add an example row "
                                                  "(ADR-0089 Confirmation)" % name)

    # ---- приёмка: puts.tsv (3 колонки — глава 2.3; 4 — глава 2.2 с колонкой вида)
    def puts(self, acceptance):
        """Форма puts.tsv и puts/ каталога приёмки; возвращает число случаев (ошибки — в errors)."""
        acceptance = Path(acceptance)
        rel = acceptance.relative_to(self.root) if acceptance.is_absolute() else acceptance
        table = self.root / rel / "puts.tsv"
        try:
            text = table.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self.error(rel / "puts.tsv", str(exc))
            return 0
        rows = [(no, line.split("\t")) for no, line in enumerate(text.split("\n"), 1) if line and not line.startswith("#")]
        if not rows or rows[0][1] not in (["case", "puts", "expect"], ["case", "puts", "expect", "canonical"]):
            self.error(rel / "puts.tsv", "the first row is the header case<TAB>puts<TAB>expect[<TAB>canonical]")
            return 0
        width, view = len(rows[0][1]), len(rows[0][1]) == 4
        files = {p.name[:-len(".subsystem.yaml")] for p in (self.root / rel / "puts").glob("*.subsystem.yaml")}
        others = [p.name for p in (self.root / rel / "puts").iterdir()] if (self.root / rel / "puts").is_dir() else []
        for name in others:
            if not name.endswith(".subsystem.yaml") and name != ".DS_Store":
                self.error(rel / "puts" / name, "puts/ holds only <имя>.subsystem.yaml")
        used, seen, n = set(), set(), 0
        for no, cols in rows[1:]:
            where = rel / "puts.tsv"
            if len(cols) != width:
                self.error(where, "line %d: expected %d TSV columns, got %d" % (no, width, len(cols)))
                continue
            case, puts, expect = cols[:3]
            if not re.fullmatch(r"[a-z0-9_]+", case) or case in seen:
                self.error(where, "line %d: case %r is not unique or not [a-z0-9_]+" % (no, case))
            seen.add(case)
            tokens = puts.split(" ")
            names = [t for t in tokens if not t.startswith("@")]
            bad = [t for t in tokens if (t not in PUTS_DIRECTIVES if t.startswith("@") else not PUTS_FILE.fullmatch(t))]
            if bad or not names or tokens[0].startswith("@") or tokens[-1].startswith("@"):
                self.error(where, "line %d: puts — file names through one space (directives %s between them%s)"
                           % (no, ", ".join(sorted(PUTS_DIRECTIVES)), "" if view else ": only with the canonical column"))
                continue
            if not view and len(names) != len(tokens):
                self.error(where, "line %d: directives %s need the canonical column" % (no, ", ".join(sorted(PUTS_DIRECTIVES))))
            for t in names:
                used.add(t)
                if t not in files:
                    self.error(where, "line %d: no file puts/%s.subsystem.yaml" % (no, t))
            m = EXPECT.fullmatch(expect)
            if not m:
                self.error(where, "line %d: expect is `<code 0|2> <rev|->`" % no)
                continue
            n += 1
            if not view:
                continue
            want = cols[3]
            if want == "-":
                if m.group(1) == "0":
                    self.error(where, "line %d: after a successful install the view exists: canonical names its vector" % no)
                continue
            if want not in self.vectors:
                self.error(where, "line %d: canonical %r is not a case of %s/cases.tsv" % (no, want, VECTORS))
                continue
            pool = names[-1:] if m.group(1) == "0" else names
            got = []
            for t in pool:
                p = self.root / rel / "puts" / (t + ".subsystem.yaml")
                if p.is_file():
                    got.append(expected_bytes(self.ld, p.read_bytes()))
            if self.vectors[want] not in got:
                self.error(where, "line %d: the vector %s is not the view of %s" %
                           (no, want, "the last file" if m.group(1) == "0" else "any file of the case"))
        for t in sorted(files - used):
            self.error(rel / "puts" / (t + ".subsystem.yaml"), "no row of puts.tsv installs it")
        return n
