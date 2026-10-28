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
# Дельты набора Б вне deltas.tsv, которые самопроверка узнаёт по строке:
# случаи Б с проверкой значения (setb_cases.VALUES) — значение по YAML 1.2.2 (обход D16, экранирование TAB);
VALUE_CASES = {"t27_escape_tab_ok", "t31_last_line_spaces_ok", "t33_flow_trailing_comma_ok"}
# тесты yaml-test-suite, которые эталон отказывает, а YAML 1.2.2 принимает, — по категориям п. 3 набора Б.
YTS_P3 = {"2EBW": "c5_key_question_mark", "FBC9": "c5_value_question_mark", "5NYZ": "c5_value_next_line_plain",
          "A984": "c5_value_next_line_plain", "P94K": "c5_value_next_line_plain",
          "UDR7": "t33_flow_trailing_comma_ok"}        # висячая запятая — 12-е отклонение п. 3 (решение 2026-10-28)


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
        if not (root / SPEC / "02.1-installer.form.yaml").is_file():
            raise SystemExit("dialect root %s is not a checkout of %s (git worktree add DIR %s)" % (root, TAG, TAG))
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
            return {"verdict": "crash", "class": None, "paths": [], "lines": [],
                    "why": ["%s: %s" % (type(exc).__name__, exc)]}

    @staticmethod
    def layer(r):
        if r["verdict"] != "refused":
            return None
        return "relations" if r.get("layer") == "relations" else LAYER.get(r.get("class"), r.get("class"))

    def load(self, data):
        r = self.judge(data)
        return r["verdict"], self.layer(r), r.get("paths", []), r.get("lines", [])

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


def backend(a):
    specs = Path(a.specs).resolve()
    if a.backend == "v7":
        return V7(specs)
    return Dialect(specs, Path(a.dialect_root).resolve())


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
        out = be.family(cells["family"], cells["kind"], cells["mode"], roles, cells["text"])
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
    """Строки, где исход эталона — не ожидание таблиц по решению набора Б: id дельт, случаи Б с иным ref, сужения yts."""
    setb = SCRIPTS / "v7/out/setb"
    out = {r["id"] for r in tsv(setb / "deltas.tsv")}
    for r in tsv(setb / "cases.tsv"):
        if r["ref"] != r["expect"]:
            out.add("case/" + r["id"].split(".")[0])
    out |= {"yts/" + r["id"] for r in tsv(setb / "yts-refusals.tsv")}
    out |= {"value/" + c for c in VALUE_CASES} | {"yts/" + i for i in YTS_P3}
    return out


def cmd_selftest(be, a):
    """Каждая строка корпуса P/02.1 и пакетов через бэкенд против ожидания таблицы; расхождение — с пометкой «дельта Б»
    (ожидаемо у dialect) или «НЕ дельта» (опровержение: стоп)."""
    specs = Path(a.specs).resolve()
    known = deltas() if be.name == "dialect" else set()
    report = {}

    def tally(name, rid, ok, ids):
        t = report.setdefault(name, {"rows": 0, "ok": 0, "delta": 0, "not_delta": []})
        t["rows"] += 1
        if ok:
            t["ok"] += 1
        elif any(i in known for i in ids):
            t["delta"] += 1
        else:
            t["not_delta"].append(rid)
    acc = specs / "Platform/02-installer/acceptance/1"
    verdicts = dict(ln.split("\t") for ln in (acc / "verdicts.tsv").read_text(encoding="utf-8").split("\n")
                    if ln and not ln.startswith("#"))
    classes = dict(ln.split("\t") for ln in (acc / "classes.tsv").read_text(encoding="utf-8").split("\n")
                   if ln and not ln.startswith("#"))
    for case, want in sorted(verdicts.items()):
        verdict, cls, _, _ = be.load((acc / "cases" / (case + ".subsystem.yaml")).read_bytes())
        tally("corpus-verdict", case, verdict == want, ["corpus/" + case, "case/" + case])
        if case in classes and verdict == "refused":
            tally("corpus-class", case, cls == classes[case], ["classes/" + case, "corpus/" + case, "case/" + case])
    vec = specs / "Platform/02-installer/vectors/canonical"
    for r in tsv(vec / "cases.tsv"):
        b, _ = be.canonical((specs / r["input"]).read_bytes())
        tally("canonical", r["case"], b == (vec / r["expect"]).read_bytes(),
              ["canonical/" + r["case"], "corpus/" + r["case"][len("corpus-"):], "case/" + r["case"][len("corpus-"):],
               "value/" + r["case"][len("corpus-"):]])
    fr = specs / "Platform/common/vectors/family-read"
    for t in sorted(fr.glob("[0-9][0-9].tsv")):
        for r in tsv(t):
            roles = json.loads(r["who"]) if r["mode"] == "reader" else []
            got = be.family(r["family"], r["kind"], r["mode"], roles, r["text"])
            ok = (got["verdict"] == r["verdict"] and sorted(got["paths"]) == sorted(json.loads(r["paths"]))
                  and got["outcome"] == json.loads(r["outcome"]))
            tally("family-read", r["case"], ok, ["family-read/%s|%s|%s|%s" % (r["family"], r["kind"], r["mode"],
                                                                                r["note"]),
                                                  "case/" + r["note"].split(".")[0]])
    ys = specs / "Platform/common/vectors/yaml-suite"
    if (ys / "expect.tsv").is_file():
        for r in tsv(ys / "expect.tsv"):
            got = be.layer1((ys / "inputs" / (r["id"] + ".yaml")).read_bytes())
            tally("yaml-suite", r["id"], got["layer1"] == r["layer1"], ["yts/" + r["id"]])
    for name, t in report.items():
        print("%-16s rows %5d  ok %5d  delta-Б %4d  NOT delta %4d %s" % (
            name, t["rows"], t["ok"], t["delta"], len(t["not_delta"]), " ".join(t["not_delta"][:8])))
    if a.json:
        Path(a.json).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 1 if any(t["not_delta"] for t in report.values()) else 0


# ---------------------------------------------------------------- каталог реализации для раннера

def cmd_materialize(a):
    """Каталог реализации для раннера: git-репозиторий с SPEC_VERSION, assembly.yaml, 02-installer/acceptance.yaml
    (профиль format 2) и обёрткой `02-installer/sut` вызова этого файла с бэкендом."""
    dest, specs = Path(a.dest).resolve(), Path(a.specs).resolve()
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit("%s is not empty" % dest)
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
    (mod / "acceptance.yaml").write_text(profile.replace("@BACKEND@", a.backend).replace("@SPEC_VERSION@", version),
                                         encoding="utf-8")
    (dest / "SPEC_VERSION").write_text(version + "\n", encoding="utf-8")
    (dest / "assembly.yaml").write_text("format: 1\nmodules:\n  02-installer: 02-installer/acceptance.yaml\n",
                                        encoding="utf-8")
    (dest / "README.md").write_text("SUT эталона (%s) для сверки раннера: %s\n" % (a.backend, HERE / "README.md"),
                                    encoding="utf-8")
    for args in (["init", "-q"], ["add", "SPEC_VERSION", "assembly.yaml", "README.md", "02-installer"],
                 ["-c", "user.name=sut", "-c", "user.email=sut@localhost", "commit", "-q", "-m", "SUT " + a.backend]):
        subprocess.run(["git", "-C", str(dest)] + args, check=True)
    print("implementation %s (backend %s, spec_version %s)" % (dest, a.backend, version))
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
