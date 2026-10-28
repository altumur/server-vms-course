"""SUT эталона для сверки раннера до реализаций (PLAN-TRANSITION п. 3.4): протокол реализаций — команды стенда P/02.1–2.2
и единая команда пакетов векторов; бэкенды `v7` (стек В7 навыка) и `dialect` (код навыка по метке
`dialect-reference-dc94d0fd1`, из worktree метки). Протокол и запуск — README.md рядом.

    python sut.py --backend v7|dialect --specs SPECS [--dialect-root DIR] COMMAND …
"""
import argparse
import base64
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1]                                  # skills/lesson-spec/scripts этого курса
TAG = "dialect-reference-dc94d0fd1"
SPEC = Path("Platform/02-installer/spec")
PACKAGES = {"02-installer/canonical", "common/family-read", "common/yaml-suite"}
# Класс диалекта → слой (ADR-0092 п. 6; как набор А, seta.LAYER): отказ связей — `relations`.
LAYER = {"text": "text", "name": "form", "key": "form", "value": "form", "reference": "form"}


# ---------------------------------------------------------------- бэкенды

class V7:
    """Стек В7 навыка на стандартных файлах выгрузки SPECS."""
    name = "v7"

    def __init__(self, specs):
        sys.path.insert(0, str(SCRIPTS))
        from v7 import project, spec, stack, textv7
        self.specs, self.project, self.spec, self.stack, self.textv7 = specs, project, spec, stack, textv7
        base = specs / SPEC / "02.1-installer"
        textv7.use_scalars(Path(str(base) + ".scalars.tsv"))
        self.manifest = stack.Manifest(json.loads(Path(str(base) + ".schema.json").read_text(encoding="utf-8")),
                                       json.loads(Path(str(base) + ".relations.json").read_text(encoding="utf-8")))
        self.catalog = {(r["key"], r["kind"]): r for r in spec.read_catalog(specs)}
        self.fams = {}

    def load(self, data):
        """→ (verdict, класс, пути, строки)."""
        r = self.manifest.judge(data)
        return r["verdict"], r["layer"], r["paths"], []

    def canonical(self, data):
        r = self.manifest.judge(data)
        if r["verdict"] != "ok":
            return None, r
        return self.stack.jcs(self.project.canonical(self.manifest.sch, r["tree"])).encode("utf-8"), r

    def family(self, key, kind, mode, roles, text):
        row = self.catalog[(key, kind)]
        k = (key, kind)
        if k not in self.fams:
            _, _, doc, _, outcomes = self.spec.load_family(self.specs, row)
            self.fams[k] = (self.stack.Family(doc, kind), outcomes)
        fam, outcomes = self.fams[k]
        value = text
        if kind == "row":
            try:
                value = json.loads(text)
            except ValueError:
                value = text
        elif kind == "file":
            value = text.encode("utf-8")
        v = fam.judge(value, mode)
        outcome = ({r: [o.path for o in self.spec.outcomes_for(outcomes, v["paths"], r)] for r in roles}
                   if mode == "reader" else [])
        return {"verdict": v["verdict"], "paths": v["paths"], "outcome": outcome}

    def layer1(self, data):
        from v7 import thin_rules
        try:
            self.textv7.load_text_map(data)
            return {"layer1": "ok", "rule": "-"}
        except self.textv7.TextRefused as exc:
            return {"layer1": "refused", "rule": thin_rules.rule_of(exc)}


class Dialect:
    """Код навыка по метке (form_source, textlayer) на файлах диалекта метки; входы — из SPECS."""
    name = "dialect"

    def __init__(self, specs, root):
        head = git(root, "rev-parse", "HEAD")
        tag = git(SCRIPTS, "rev-parse", TAG + "^{commit}")
        if head is None or head != tag:
            raise SystemExit("dialect root %s is not at %s (%s): git worktree add DIR %s" % (root, TAG, tag, TAG))
        sys.path.insert(0, str(root / "skills/lesson-spec/scripts"))
        from form_source import Loader
        from form_source import families as fam
        from form_source import canonical as can
        self.specs, self.root, self.fam, self.can = specs, root, fam, can
        base = root / SPEC / "02.1-installer"
        self.loader = Loader(*(Path(str(base) + s) for s in (".form.yaml", ".references.tsv", ".scalars.tsv")))
        self.catalog = {(r["key"], r["kind"]): r for r in fam.read_catalog(root)}
        self.common = fam.load_common(root / fam.COMMON)
        self.fams = {}

    def judge(self, data):
        try:
            return self.loader.judge(data)
        except Exception as exc:                            # noqa: BLE001 — авария эталона (D9, набор Б t26)
            return {"verdict": "crash", "class": None, "exc": type(exc).__name__, "paths": [], "lines": [],
                    "why": ["%s: %s" % (type(exc).__name__, exc)]}

    @staticmethod
    def layer(r):
        if r["verdict"] != "refused":
            return None
        return "relations" if r.get("layer") == "relations" else LAYER.get(r.get("class"), r.get("class"))

    def load(self, data):
        r = self.judge(data)
        return r["verdict"], self.layer(r), r.get("paths", []), r.get("lines", [])

    def raw(self, data):
        """Исход эталона словами строки дельты: `ok`, `refused:<класс диалекта>`, `crash`."""
        r = self.judge(data)
        if r["verdict"] == "crash":
            return "crash:%s" % r["exc"]
        return r["verdict"] if r["verdict"] != "refused" else "refused:%s" % r.get("class")

    def canonical(self, data):
        r = self.judge(data)
        if r["verdict"] != "ok":
            return None, r
        return self.can.canonical_bytes(self.loader, data), r

    def family(self, key, kind, mode, roles, text):
        k = (key, kind)
        if k not in self.fams:
            f = self.fam.load_family(self.root, self.catalog[k], self.common)
            self.fams[k] = (f, {m: self.fam.Judge(f.form, m) for m in ("writer", "reader")})
        f, judges = self.fams[k]
        value = text
        if kind == "row":
            try:
                value = json.loads(text)
            except ValueError:
                value = text
        elif kind == "file":
            value = text.encode("utf-8")
        try:
            r = judges[mode].judge(value, kind)
        except Exception as exc:                            # noqa: BLE001 — авария эталона (дефект эталона, набор Б)
            return {"verdict": "crash", "paths": [], "outcome": [], "why": "%s: %s" % (type(exc).__name__, exc)}
        outs = [o.path for o in self.fam.outcomes_for(f.outcomes, r["paths"])] if mode == "reader" else []
        # у диалекта исходы без читателя: тот же набор строк у каждой роли (заготовка столбца reader — копии)
        return {"verdict": r["verdict"], "paths": r["paths"], "outcome": {x: outs for x in roles} if mode == "reader"
                else []}

    def layer1(self, data):
        from form_source.source import textlayer
        try:
            textlayer.load_text(data)
            return {"layer1": "ok", "rule": "-"}
        except textlayer.TextRefused:
            return {"layer1": "refused", "rule": "dialect"}
        except Exception as exc:                            # noqa: BLE001 — авария эталона (D9: OverflowError)
            return {"layer1": "crash", "rule": "%s" % type(exc).__name__}


def git(where, *args):
    try:
        return subprocess.run(["git", "-C", str(where), *args], capture_output=True, check=True,
                              text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def pins():
    """Код SUT: [(путь от корня курса, sha256)] — sut.py, стек v7/*.py, дельты Б (М-7)."""
    import hashlib
    course = SCRIPTS.parents[2]
    files = [Path(__file__).resolve(), *sorted((SCRIPTS / "v7").glob("*.py")), SCRIPTS / "v7/out/setb/deltas.tsv",
             SCRIPTS / "v7/out/setb/cases.tsv"]
    return [(f.relative_to(course).as_posix(), hashlib.sha256(f.read_bytes()).hexdigest()) for f in files]


class Keys:
    """Ключ строки family-read по шаблону каталога выгрузки (V7-FAMILY-KEY-PLACEHOLDER-01) — до бэкенда, у обоих одним
    правилом стека В7 (у диалекта проверки ключа не было): не по шаблону — отказ строки целиком `[""]`, значение не
    судится, исход у читателя — строки пустого пути его роли."""

    def __init__(self, specs):
        sys.path.insert(0, str(SCRIPTS))                    # v7 навыка этого курса — до кода метки у бэкенда dialect
        from v7 import spec
        self.spec, self.specs, self.templates, self.outcomes = spec, specs, None, {}

    def refused(self, family, kind, key, mode, roles):
        if self.templates is None:
            catalog = self.spec.read_catalog(self.specs)
            self.templates, errors = self.spec.key_templates(self.specs, catalog)
            if errors:
                raise ValueError("family-read keys: " + "; ".join(errors))
            self.rows = {(r["key"], r["kind"]): r for r in catalog}
        if self.templates[(family, kind)].matches(key):
            return None
        k = (family, kind)
        if k not in self.outcomes:
            self.outcomes[k] = self.spec.load_family(self.specs, self.rows[k])[4]
        whole = self.spec.KEY_REFUSED
        return {"verdict": "refused", "paths": list(whole), "outcome": (
            {r: [o.path for o in self.spec.outcomes_for(self.outcomes[k], whole, r)] for r in roles}
            if mode == "reader" else [])}


def backend(a):
    specs = Path(a.specs).resolve()
    keys = Keys(specs)
    be = V7(specs) if a.backend == "v7" else Dialect(specs, Path(a.dialect_root).resolve())
    be.keys = keys
    return be


def read_family(be, family, key, kind, mode, roles, text):
    """Исход строки family-read: ключ — Keys, затем значение — бэкенд."""
    return be.keys.refused(family, kind, key, mode, roles) or be.family(family, kind, mode, roles, text)


# ---------------------------------------------------------------- стенд P/02.1, P/02.2

def refusal_text(be, name, cls, paths, lines):
    """Текст отказа: называет файл, класс `refused:<класс>`, пути JSON-массивами, строки `line N`."""
    where = " ".join(json.dumps(p, ensure_ascii=False) for p in paths)
    return "refused:%s: %s: at %s%s\n" % (cls, name, where or "[]", "".join(" line %d" % n for n in lines))


def cmd_load(be, a):
    p = Path(a.file)
    try:
        verdict, cls, paths, lines = be.load(p.read_bytes())
    except Exception as exc:                                # noqa: BLE001
        sys.stderr.write("crash: %s: %s\n" % (type(exc).__name__, exc))
        return 1
    if verdict == "ok":
        sys.stdout.write("ok: %s\n" % p.name)
        return 0
    if verdict == "crash":
        sys.stderr.write("crash: %s\n" % p.name)
        return 1
    sys.stderr.write(refusal_text(be, p.name, cls, paths, lines))
    return 2


def cmd_load_adapter(be, a):
    for line in sys.stdin:
        p = Path(line.rstrip("\n"))
        try:
            verdict, cls, paths, lines = be.load(p.read_bytes())
            out = {"verdict": verdict, "text": "" if verdict == "ok" else "crash: %s" % p.name if verdict == "crash"
                   else refusal_text(be, p.name, cls, paths, lines)}
        except Exception as exc:                            # noqa: BLE001
            out = {"verdict": "crash", "text": "%s: %s" % (type(exc).__name__, exc)}
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


def cmd_canonical(be, a):
    p = Path(a.input)
    b, r = be.canonical(p.read_bytes())
    if b is None:
        cls = be.layer(r) if be.name == "dialect" else r.get("layer")
        sys.stderr.write(refusal_text(be, p.name, cls, r.get("paths", []), []))
        return 1 if r["verdict"] == "crash" else 2
    sys.stdout.buffer.write(b)
    return 0


# ---------------------------------------------------------------- пакеты векторов (рамка раннера)

def native(package, request, be, specs):
    """→ (код, stdout, stderr) пакета; ожидание строки (колонки verdict, paths, outcome, expect, layer1) не читается."""
    cells, files = request["cells"], request["files"]

    def input_bytes(name, rel):
        if name in files:
            return base64.b64decode(files[name])
        return (specs / rel).read_bytes()
    if package == "02-installer/canonical":
        rel = cells["input"]
        b, r = be.canonical(input_bytes("input", rel))
        if b is None:
            cls = be.layer(r) if be.name == "dialect" else r.get("layer")
            return 1 if r["verdict"] == "crash" else 2, b"", refusal_text(be, Path(rel).name, cls, r.get("paths", []),
                                                                          []).encode("utf-8")
        return 0, b, b""
    if package == "common/family-read":
        roles = json.loads(cells["who"]) if cells["mode"] == "reader" else []
        out = read_family(be, cells["family"], cells["key"], cells["kind"], cells["mode"], roles, cells["text"])
        return 0, json.dumps(out, ensure_ascii=False, sort_keys=True).encode("utf-8"), b""
    if package == "common/yaml-suite":
        data = input_bytes("in.yaml", "Platform/common/vectors/yaml-suite/inputs/%s.yaml" % cells["id"])
        return 0, json.dumps(be.layer1(data), sort_keys=True).encode("utf-8"), b""
    raise ValueError("package %s is not served (%s)" % (package, ", ".join(sorted(PACKAGES))))


def cmd_vectors(be, a):
    request = json.loads(Path(a.input).read_bytes().decode("utf-8"))
    if request.get("format") != 1:
        raise SystemExit("request format must be 1")
    try:
        code, out, err = native(request["package"], request, be, Path(a.specs).resolve())
    except Exception as exc:                                # noqa: BLE001 — авария пакета — native-код 1
        code, out, err = 1, b"", ("%s: %s\n" % (type(exc).__name__, exc)).encode("utf-8")
    sys.stdout.write(json.dumps({"exit_code": code, "stdout_b64": base64.b64encode(out).decode("ascii"),
                                 "stderr_b64": base64.b64encode(err).decode("ascii")}) + "\n")
    return 0


# ---------------------------------------------------------------- самопроверка: таблицы против бэкенда

def tsv(path):
    lines = [ln for ln in Path(path).read_text(encoding="utf-8").split("\n") if ln and not ln.startswith("#")]
    head = lines[0].split("\t")
    return [dict(zip(head, ln.split("\t"))) for ln in lines[1:]]


def deltas():
    """Набор Б одним списком: id → «было» (ответ эталона по решению Б). Источник — `v7/out/setb/deltas.tsv` (дельты
    набора А, yaml-suite, значения) и `cases.tsv` (случаи Б: `case/<id>` → `ref`) — без второго списка здесь (повторное
    ревью Claude М-6)."""
    setb = SCRIPTS / "v7/out/setb"
    out = {r["id"]: r["old"] for r in tsv(setb / "deltas.tsv")}
    for r in tsv(setb / "cases.tsv"):
        if r["ref"] != r["expect"]:
            out["case/" + r["id"]] = r["ref"]
    return out


def dialect_matches(be, known, ids, answer):
    """Строка-дельта засчитана, только если эталон дал «было» дельты (М-5): answer(id, было) — сверка по виду строки."""
    for i in ids:
        if i in known:
            return answer(i, known[i])
    return None                                          # строки в Б нет: расхождение — не дельта


def p1_states(want, got):
    """D19 (DEFECTS.tsv): вид эталона отличается от ожидания только `snapshot` без `state.<имя>` — П1 метки без
    состояний (ADR-0091 п. 3; V7-P022-SNAPSHOT-STATE-01)."""
    try:
        w, g = json.loads(want), json.loads(got)
    except (TypeError, ValueError):
        return False
    if not (isinstance(w, dict) and isinstance(g, dict)) or set(w) != set(g) or "snapshot" not in w:
        return False
    st = (w.get("unit") or {}).get("state") or {}
    states = ["state." + k for k in st if k != "cursor"] if isinstance(st, dict) else []
    n = len(g["snapshot"]) if isinstance(g["snapshot"], list) else -1      # порядок автора в JCS вида не виден
    return bool(states and n >= 0 and w["snapshot"][:n] == g["snapshot"] and sorted(w["snapshot"][n:]) == sorted(states)
                and all(w[k] == g[k] for k in w if k != "snapshot"))


# Известные дефекты эталона по метке (DEFECTS.tsv, library — эталон): id → сверка (ожидание, ответ эталона) по виду
# строки. Не дельты Б: правка нормы после метки, у эталона П1 старый.
REFERENCE_DEFECTS = {"D19": ("canonical", p1_states)}


def reference_defects():
    ids = {r["id"] for r in tsv(SCRIPTS / "v7/DEFECTS.tsv")}
    missing = sorted(set(REFERENCE_DEFECTS) - ids)
    if missing:
        raise SystemExit("v7/DEFECTS.tsv has no row %s" % ", ".join(missing))
    return REFERENCE_DEFECTS


def reference_defect(be, package, want, got):
    """id известного дефекта эталона, если строка `dialect` расходится ровно им; иначе None."""
    if be.name != "dialect":
        return None
    for i, (pkg, same) in reference_defects().items():
        if pkg == package and same(want, got):
            return i
    return None


def cmd_selftest(be, a):
    """Каждая строка корпуса P/02.1 и пакетов через бэкенд против ожидания таблицы. У `dialect` расхождение засчитано
    дельтой Б, только если строка есть в наборе Б и эталон дал её «было»; иначе — «НЕ дельта» (стоп, разбор)."""
    import ast
    specs = Path(a.specs).resolve()
    known = deltas() if be.name == "dialect" else {}
    report = {}

    def tally(name, rid, ok, verdict=None):
        t = report.setdefault(name, {"rows": 0, "ok": 0, "delta": 0, "defect": 0, "not_delta": []})
        t["rows"] += 1
        if ok:
            t["ok"] += 1
        elif isinstance(verdict, str):                   # известный дефект эталона (DEFECTS.tsv), не дельта Б
            t["defect"] += 1
        elif verdict:
            t["delta"] += 1
        else:
            t["not_delta"].append(rid)
    acc = specs / "Platform/02-installer/acceptance/1"
    verdicts = dict(ln.split("\t") for ln in (acc / "verdicts.tsv").read_text(encoding="utf-8").split("\n")
                    if ln and not ln.startswith("#"))
    classes = dict(ln.split("\t") for ln in (acc / "classes.tsv").read_text(encoding="utf-8").split("\n")
                   if ln and not ln.startswith("#"))
    for case, want in sorted(verdicts.items()):
        data = (acc / "cases" / (case + ".subsystem.yaml")).read_bytes()
        verdict, cls, _, _ = be.load(data)
        raw = be.raw(data) if be.name == "dialect" else None
        mapped = raw if verdict == "crash" else verdict if verdict != "refused" else "refused:%s" % cls

        def same(i, old):
            return old == (mapped if i.startswith("case/") else raw)
        tally("corpus-verdict", case, verdict == want,
              verdict != want and dialect_matches(be, known, ["corpus/" + case, "case/" + case], same))
        if case in classes and verdict == "refused":
            def same_class(i, old):
                if i.startswith("classes/"):
                    return old == raw.split(":", 1)[-1] or old.endswith("эталон: %s)" % raw.split(":", 1)[-1])
                return same(i, old)
            tally("corpus-class", case, cls == classes[case], cls != classes[case] and dialect_matches(
                be, known, ["classes/" + case, "corpus/" + case, "case/" + case], same_class))
    vec = specs / "Platform/02-installer/vectors/canonical"
    for r in tsv(vec / "cases.tsv"):
        data = (specs / r["input"]).read_bytes()
        b, _ = be.canonical(data)
        want = (vec / r["expect"]).read_bytes()
        c = r["case"][len("corpus-"):]

        def same_canonical(i, old):
            if i.startswith("canonical/"):
                return (b is None) == old.startswith("нет вектора")
            if i.startswith("case/"):
                return (b is None) == old.startswith("refused")
            if i.startswith("value/"):                   # значение на пути — «было» эталона (или его отказ)
                if old.startswith("refused"):
                    return b is None
                return b is not None and json.dumps(_at(json.loads(b), _value_path(c)), ensure_ascii=False) == old
            return False
        tally("canonical", r["case"], b == want, b != want and (dialect_matches(
            be, known, ["canonical/" + r["case"], "value/" + c, "case/" + c], same_canonical)
            or reference_defect(be, "canonical", want, b)))
    fr = specs / "Platform/common/vectors/family-read"
    for t in sorted(fr.glob("[0-9][0-9].tsv")):
        for r in tsv(t):
            roles = json.loads(r["who"]) if r["mode"] == "reader" else []
            got = read_family(be, r["family"], r["key"], r["kind"], r["mode"], roles, r["text"])
            ok = (got["verdict"] == r["verdict"] and sorted(got["paths"]) == sorted(json.loads(r["paths"]))
                  and got["outcome"] == json.loads(r["outcome"]))
            outs = next(iter(got["outcome"].values()), []) if isinstance(got["outcome"], dict) else got["outcome"]

            def same_family(i, old):
                m = re.fullmatch(r"(\w+) (\[.*?\]) (\[.*\])", old)
                if not m:
                    return False
                parse = ast.literal_eval if i.startswith("family-read/") else json.loads
                return (m.group(1) == got["verdict"] and sorted(parse(m.group(2))) == sorted(got["paths"])
                        and parse(m.group(3)) == outs)
            tally("family-read", r["case"], ok, not ok and dialect_matches(
                be, known, ["family-read/%s|%s|%s|%s" % (r["family"], r["kind"], r["mode"], r["note"]),
                            "case/" + r["note"]], same_family))
    ys = specs / "Platform/common/vectors/yaml-suite"
    if (ys / "expect.tsv").is_file():
        for r in tsv(ys / "expect.tsv"):
            got = be.layer1((ys / "inputs" / (r["id"] + ".yaml")).read_bytes())
            word = got["layer1"] if got["layer1"] != "crash" else "crash:%s" % got["rule"]
            tally("yaml-suite", r["id"], got["layer1"] == r["layer1"], got["layer1"] != r["layer1"] and dialect_matches(
                be, known, ["yaml-suite/" + r["id"]], lambda i, old: old == word))
    for name, t in report.items():
        print("%-16s rows %5d  ok %5d  delta-Б %4d  defect %3d  NOT delta %4d %s" % (
            name, t["rows"], t["ok"], t["delta"], t["defect"], len(t["not_delta"]), " ".join(t["not_delta"][:8])))
    if a.json:
        Path(a.json).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 1 if any(t["not_delta"] for t in report.values()) else 0


def _value_path(case):
    """Путь значения случая Б (строка `value/<случай>` deltas.tsv: «…путь a/b)»)."""
    for r in tsv(SCRIPTS / "v7/out/setb/deltas.tsv"):
        if r["id"] == "value/" + case:
            m = re.search(r"путь ([^)]+)\)", r["basis"])
            return m.group(1).split("/") if m else []
    return []


def _at(tree, path):
    for s in path:
        tree = tree.get(s) if isinstance(tree, dict) else None
    return tree


# ---------------------------------------------------------------- каталог реализации для раннера

def cmd_materialize(a):
    """Каталог реализации для раннера: git-репозиторий с SPEC_VERSION, assembly.yaml, 02-installer/acceptance.yaml
    (профиль format 2) и обёрткой `02-installer/sut` вызова этого файла с бэкендом."""
    dest, specs = Path(a.dest).resolve(), Path(a.specs).resolve()
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit("%s is not empty" % dest)
    course = git(SCRIPTS, "rev-parse", "HEAD")
    if course is None or git(SCRIPTS, "status", "--porcelain", "--", str(SCRIPTS)):
        raise SystemExit("the skill has uncommitted changes under %s: commit first, the SUT pins its code" % SCRIPTS)
    dialect = ""
    if a.backend == "dialect":
        head = git(Path(a.dialect_root).resolve(), "rev-parse", "HEAD")
        if head != git(SCRIPTS, "rev-parse", TAG + "^{commit}"):
            raise SystemExit("dialect root is not at %s" % TAG)
        dialect = head
    try:
        version = subprocess.run(["git", "-C", str(specs), "rev-parse", "HEAD"], capture_output=True, check=True,
                                 text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit("%s is not a git checkout of the export (spec_version = its HEAD)" % specs)
    mod = dest / "02-installer"
    mod.mkdir(parents=True)
    dial = " --dialect-root %s" % Path(a.dialect_root).resolve() if a.backend == "dialect" else ""
    (mod / "sut").write_text("#!/bin/sh\nexec %s -B %s --backend %s --specs %s%s \"$@\"\n"
                             % (a.python, Path(__file__).resolve(), a.backend, specs, dial), encoding="utf-8")
    (mod / "sut").chmod(0o755)
    profile = (HERE / "acceptance.yaml.in").read_text(encoding="utf-8")
    (mod / "acceptance.yaml").write_text(profile.replace("@BACKEND@", a.backend).replace("@SPEC_VERSION@", version)
                                         .replace("@COURSE@", course).replace("@DIALECT@", dialect or "-"),
                                         encoding="utf-8")
    (dest / "SUT-PIN.tsv").write_text(
        "course\t%s\nbackend\t%s\nspec_version\t%s\ndialect\t%s\n" % (course, a.backend, version, dialect or "-")
        + "".join("sha256\t%s\t%s\n" % (path, h) for path, h in pins()), encoding="utf-8")
    (dest / "SPEC_VERSION").write_text(version + "\n", encoding="utf-8")
    (dest / "assembly.yaml").write_text("format: 1\nmodules:\n  02-installer: 02-installer/acceptance.yaml\n",
                                        encoding="utf-8")
    (dest / "README.md").write_text("SUT эталона (%s) для сверки раннера: %s\n" % (a.backend, HERE / "README.md"),
                                    encoding="utf-8")
    for args in (["init", "-q"], ["add", "SPEC_VERSION", "assembly.yaml", "README.md", "SUT-PIN.tsv", "02-installer"],
                 ["-c", "user.name=sut", "-c", "user.email=sut@localhost", "commit", "-q", "-m", "SUT " + a.backend]):
        subprocess.run(["git", "-C", str(dest)] + args, check=True)
    print("implementation %s (backend %s, spec_version %s, course %s)" % (dest, a.backend, version, course))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=("v7", "dialect"), required=True)
    ap.add_argument("--specs", required=True, help="корень выгрузки (cammeta-specs) или дерева курса")
    ap.add_argument("--dialect-root", default=str(SCRIPTS.parents[2].parent / "wt-dialect-reference"),
                    help="worktree метки %s (бэкенд dialect)" % TAG)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("load").add_argument("file")
    sub.add_parser("load-adapter")
    sub.add_parser("canonical").add_argument("input")
    sub.add_parser("vectors").add_argument("input")
    s = sub.add_parser("selftest")
    s.add_argument("--json")
    m = sub.add_parser("materialize")
    m.add_argument("dest")
    m.add_argument("--python", default=sys.executable)
    a = ap.parse_args(argv)
    if a.cmd == "materialize":
        return cmd_materialize(a)
    be = backend(a)
    return {"load": cmd_load, "load-adapter": cmd_load_adapter, "canonical": cmd_canonical, "vectors": cmd_vectors,
            "selftest": cmd_selftest}[a.cmd](be, a)


if __name__ == "__main__":
    sys.exit(main())
