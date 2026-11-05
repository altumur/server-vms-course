"""Судья части 3а двери урока (gen_door_lesson.py; P/06): маршруты по OpenAPI — своя модель судьи против Go Route.

Запуск: python3 tools/normgen/test_gen_door_lesson.py [-v]   (go 1.22)

1. out свежий; каждая операция OpenAPI (путь, метод) — ровно одна Op с её методом, путём, параметрами, кодами ответов.
2. Пробы: на каждую операцию — путь из образцов значений параметров (класс каталога — имя подставного каталога,
   прочие — первое значение из словаря судьи, проходящее схему параметра), короткий и с префиксом /{sub}, если у пути
   сервер {origin}/{sub}; отрицательные: неизвестный первый сегмент, неизвестное имя каталога, чужой метод (405 только
   при 405 у всех операций пути), испорченное %XX, значение вне схемы. Ожидание — своя модель судьи (литерал >
   параметр класса > свободный; каталог; схема), исполнение — Go Route на подставном каталоге.
3. Мутанты таблиц routes.go: потерян префиксный вариант, all405, шаблон параметра, ранг класса — пробы красные.
"""
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LESSONS = {"06-console": "p06", "08-domain": "p08", "09-agent": "p09", "10-domain-console": "p10"}
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")
CATALOG = {"sub": {"testsub", "testsub2"}, "rows": {"units", "cams"}, "table": {"tallies"}, "pass": {"probe"}}
SAMPLES = ["c1", "0123456789abcdef", "0001", "srv-a", "t1", "a", "member-1", "index.js", "x"]

sys.path.insert(0, str(HERE))
import yamlsub  # noqa: E402


class Model:
    """Своя модель маршрутов судьи: OpenAPI → шаблоны и проверки параметров."""

    def __init__(self, lesson):
        self.spec = ROOT / "Platform" / lesson / "spec" / f"{lesson}.api.openapi.yaml"
        self.files = {}
        self.doc = self.load(self.spec)
        self.paths = []
        for path, item in self.doc["paths"].items():
            ms = [m.upper() for m in METHODS if m in item]
            if not ms:
                continue
            segs = [] if path == "/" else path[1:].split("/")
            checks = {}
            ops = {}
            for m in METHODS:
                if m not in item:
                    continue
                op = item[m]
                prms = [self.deref(p, self.spec) for p in item.get("parameters", []) + op.get("parameters", [])]
                for p, pbase in prms:                     # схема параметра — от файла, где параметр объявлен
                    if p["in"] == "path":
                        checks[p["name"]] = self.schema(p["schema"], pbase)
                codes = [str(c) for c in op["responses"]]
                ops[m.upper()] = codes
            urls = [s["url"] for s in item.get("servers") or []]
            pre = "{origin}/{sub}" in urls
            self.paths.append({"path": path, "segs": segs, "checks": checks, "ops": ops, "prefixed": pre,
                               "all405": all("405" in c for c in ops.values())})

    def load(self, p):
        p = Path(p).resolve()
        if p not in self.files:
            self.files[p] = yamlsub.load(p.read_text(encoding="utf-8"), p.name)
        return self.files[p]

    def deref(self, node, base):
        while isinstance(node, dict) and "$ref" in node:
            f, _, ptr = node["$ref"].partition("#")
            base = (Path(base).parent / f).resolve() if f else base
            node = self.load(base)
            for part in ptr.strip("/").split("/"):
                node = node[part]
        return node, base

    def schema(self, node, base):
        node, base = self.deref(node, base)
        return {"min": node.get("minLength", 0), "max": node.get("maxLength"), "pattern": node.get("pattern"),
                "enum": node.get("enum"), "not": node.get("not")}

    @staticmethod
    def ok(c, v):
        if v == "" or len(v) < c["min"] or (c["max"] is not None and len(v) > c["max"]):
            return False
        if c["pattern"] and not re.search(c["pattern"], v):
            return False
        if c["enum"] is not None and v not in [str(e) for e in c["enum"]]:
            return False
        neg = c["not"]
        if neg:
            for it in neg.get("anyOf", [neg]):
                if "enum" in it and v in [str(e) for e in it["enum"]]:
                    return False
                if "pattern" in it and re.search(it["pattern"], v):
                    return False
        return True

    def templates(self):
        for p in self.paths:
            yield p, p["segs"], False
            if p["prefixed"]:
                yield p, ["{sub}"] + p["segs"], True

    @staticmethod
    def rank(seg):
        m = re.fullmatch(r"\{(.+)\}", seg)
        if not m:
            return 2
        return 1 if m[1] in CATALOG else 0

    def route(self, method, path):
        """→ ("op", path, method, params, prefixed) | ("err", code)."""
        if not path.startswith("/"):
            return ("err", 404)
        raw = [] if path == "/" else path[1:].split("/")
        segs = []
        for s in raw:
            if re.search(r"%(?![0-9A-Fa-f]{2})", s):
                return ("err", 404)                    # испорченное %XX
            b = re.sub(rb"%([0-9A-Fa-f]{2})", lambda m: bytes([int(m[1], 16)]), s.encode("utf-8"))
            segs.append(b.decode("utf-8", "surrogateescape"))
        hits = []
        for p, tsegs, pre in self.templates():
            if len(tsegs) != len(segs):
                continue
            params, good = {}, True
            for t, v in zip(tsegs, segs):
                m = re.fullmatch(r"\{(.+)\}", t)
                if not m:
                    good = t == v
                elif m[1] == "sub" and pre and t == tsegs[0] and "sub" not in p["checks"]:
                    good = v != ""
                    params["sub"] = v
                else:
                    good = self.ok(p["checks"][m[1]], v)
                    params[m[1]] = v
                if not good:
                    break
            if not good:
                continue
            sub = params.get("sub", "")
            for name, v in params.items():
                if name in ("rows", "table", "pass") and v not in CATALOG[name]:
                    good = False
                if name == "sub" and v not in CATALOG["sub"]:
                    good = False
            if good:
                hits.append((p, tsegs, pre, params))
        if not hits:
            return ("err", 404)

        def key(h):
            return [self.rank(s) for s in h[1]]
        top = max(key(h) for h in hits)
        best = [h for h in hits if key(h) == top]
        if len({h[0]["path"] for h in best}) > 1:
            return ("err", 0)
        p, _, pre, params = best[0]
        m = method.upper()
        if m in p["ops"]:
            return ("op", p["path"], m, params, pre)
        return ("err", 405 if p["all405"] else 404)

    def sample(self, p, name):
        if name in CATALOG:
            return sorted(CATALOG[name])[0]
        c = p["checks"][name]
        if c["enum"]:
            return str(c["enum"][0])
        for s in SAMPLES:
            if self.ok(c, s):
                return s
        return None


DRIVER = r'''package main

import (
	"bufio"
	"encoding/json"
	"os"

	"%s/apidoor"
)

type cat struct{}

func in(xs []string, v string) bool {
	for _, x := range xs {
		if x == v {
			return true
		}
	}
	return false
}

func (cat) Sub(n string) bool           { return in([]string{"testsub", "testsub2"}, n) }
func (cat) Rows(sub, n string) bool     { return in([]string{"units", "cams"}, n) }
func (cat) Table(sub, n string) bool    { return in([]string{"tallies"}, n) }
func (cat) Pass(sub, n string) bool     { return in([]string{"probe"}, n) }

func main() {
	sc := bufio.NewScanner(os.Stdin)
	enc := json.NewEncoder(os.Stdout)
	for sc.Scan() {
		var c struct{ Method, Path string }
		_ = json.Unmarshal(sc.Bytes(), &c)
		m, err := apidoor.Route(c.Method, c.Path, cat{})
		if err != nil {
			enc.Encode(map[string]any{"err": err.Code})
			continue
		}
		info := apidoor.Ops[m.Op]
		enc.Encode(map[string]any{"path": info.Path, "method": info.Method, "params": m.Params, "prefixed": m.Prefixed})
	}
}
'''


def run(mod, probes):
    d = Path(mod) / "cmd/judgeroutes"
    d.mkdir(parents=True, exist_ok=True)
    module = (Path(mod) / "go.mod").read_text().split("\n")[0].split()[1]
    (d / "main.go").write_text(DRIVER % module)
    done = subprocess.run(["go", "run", "./cmd/judgeroutes"], cwd=mod, capture_output=True, text=True, env=GOENV,
                          input="".join(json.dumps({"Method": m, "Path": p}) + "\n" for m, p in probes))
    if done.returncode:
        raise AssertionError(done.stderr[-2000:])
    return [json.loads(x) for x in done.stdout.split("\n") if x]


def probes(model, rnd):
    out = []
    for p in model.paths:
        for pre in (False, True) if p["prefixed"] else (False,):
            vals = []
            good = True
            for s in p["segs"]:
                m = re.fullmatch(r"\{(.+)\}", s)
                if not m:
                    vals.append(s)
                    continue
                v = model.sample(p, m[1])
                if v is None:
                    good = False
                    break
                vals.append(v)
            if not good:
                continue
            path = "/" + "/".join((["testsub"] if pre else []) + vals)
            for meth in p["ops"]:
                out.append((meth, path))
            out.append(("TRACE", path))                       # чужой метод
            bad = path.replace("/" + vals[0], "/zz-unknown", 1) if vals else "/zz-unknown"
            out.append(("GET", bad))
    for p in model.paths:                             # границы схемы свободного параметра: minLength и на 1 короче
        for k, seg in enumerate(p["segs"]):
            m = re.fullmatch(r"\{(.+)\}", seg)
            if not m or m[1] in CATALOG:
                continue
            c = p["checks"][m[1]]
            base = []
            for j, s2 in enumerate(p["segs"]):
                mm = re.fullmatch(r"\{(.+)\}", s2)
                base.append(s2 if not mm else model.sample(p, mm[1]))
            if None in base:
                continue
            for n in (c["min"], c["min"] - 1):
                if n < 1:
                    continue
                vals = list(base)
                vals[k] = "a" * n
                out.append((next(iter(p["ops"])), "/" + "/".join(vals)))
    out += [("GET", "/%zz"), ("GET", "nope"), ("GET", "/testsub/zz/zz/zz/zz/zz"), ("GET", "/zzsub/units")]
    for _ in range(300):
        segs = [rnd.choice(["testsub", "units", "tallies", "probe", "folders", "domain", "at", "c1", "zz", "",
                            "manifest", "where", "servers", "api", "metrics", "%41"]) for _ in range(rnd.randint(0, 5))]
        out.append((rnd.choice(["GET", "PUT", "POST", "DELETE", "PATCH"]), "/" + "/".join(segs)))
    return out


def expected(model, probe):
    r = model.route(*probe)
    if r[0] == "err":
        return {"err": r[1]}
    return {"path": r[1], "method": r[2], "params": r[3], "prefixed": r[4]}


class DoorLessonBase:
    LESSON = SLUG = None

    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        cls.tmp = Path(tempfile.mkdtemp(prefix="door-lesson-"))
        out = cls.tmp / "fresh"
        done = subprocess.run([sys.executable, str(HERE / "gen_door_lesson.py"), "--lesson", cls.LESSON, str(out)],
                              capture_output=True, text=True)
        if done.returncode:
            raise AssertionError(done.stderr)
        cls.fresh = out / "go"
        cls.model = Model(cls.LESSON)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_fresh(self):
        for name in ("routes.go", "routes_rt.go"):
            kept = HERE / "out" / self.SLUG / "go/apidoor" / name
            self.assertEqual(kept.read_bytes(), (self.fresh / "apidoor" / name).read_bytes(), f"{kept} is stale")

    def test_ops(self):
        text = (self.fresh / "apidoor/routes.go").read_text()
        n = sum(len(p["ops"]) for p in self.model.paths)
        self.assertEqual(len(re.findall(r"^\tOp\w+(?:\s+Op = iota \+ 1)?\s+// [A-Z]+ /", text, re.M)), n)
        for p in self.model.paths:
            for m in p["ops"]:
                self.assertIn(f'"{p["path"]} {m}": ', text)

    def test_probes(self):
        rnd = random.Random(6)
        pr = probes(self.model, rnd)
        got = run(self.fresh, pr)
        bad = [(p, expected(self.model, p), g) for p, g in zip(pr, got) if expected(self.model, p) != g]
        self.assertEqual(bad[:3], [], f"{len(bad)} of {len(pr)} probes disagree")
        hit_ops = {(g["path"], g["method"], g["prefixed"]) for g in got if "path" in g}
        want = {(p["path"], m, pre) for p in self.model.paths for m in p["ops"]
                for pre in ((False, True) if p["prefixed"] else (False,))}
        missed = want - hit_ops
        # пробы, затенённые более конкретным шаблоном или без образца, — допустимы, но не больше 10 %
        self.assertLessEqual(len(missed), len(want) // 10, f"probes reach too few operations: {sorted(missed)[:10]}")
        codes = {g.get("err") for g in got}
        self.assertIn(404, codes)
        if any(p["all405"] for p in self.model.paths):
            self.assertIn(405, codes)

    def test_mutants(self):
        rnd = random.Random(7)
        pr = probes(self.model, rnd)
        src = (self.fresh / "apidoor/routes.go").read_text()
        rt = (self.fresh / "apidoor/routes_rt.go").read_text()
        m405 = re.search(r'^\t("[^"]+":\s+)true,$', src[src.index("var all405"):], re.M)
        muts = {
            "prefix-lost": ("routes.go", re.sub(r"(\{path: \"[^\"]+\", segs: \[\]segment\{\{param: \"sub\"\}[^\n]*prefixed: )true",
                                                r"\1false", src, count=1)),
            "all405": ("routes.go", src.replace(f"\t{m405[1]}true,", f"\t{m405[1]}false,", 1) if m405 else src),
            "pattern": ("routes.go", re.sub(r'("(?!sub"|rows"|table"|pass")\w+": paramCheck\{minLen: )1(, maxLen: -1, rx: nil)',
                                            r"\g<1>3\2", src, count=1)),
            "rank": ("routes_rt.go", rt.replace('case s.param == "sub" || s.param == "rows"', 'case s.param == "sub" || s.param == "zz"', 1)),
        }
        prefixed = any(p["prefixed"] for p in self.model.paths)
        shapes = {}
        for p, tsegs, pre in self.model.templates():
            shapes.setdefault(tuple("{}" if re.fullmatch(r"\{.+\}", sg) else sg for sg in tsegs), []).append(tsegs)

        def rows_vs_free(group):                       # ранг rows решает: {rows} и свободный параметр на одной позиции
            for i in range(len(group[0])):
                names = {sg for sg in (t[i] for t in group)}
                if "{rows}" in names and any(re.fullmatch(r"\{(.+)\}", n) and n[1:-1] not in CATALOG for n in names):
                    return True
            return False
        classes = any(len(v) > 1 and rows_vs_free(v) for v in shapes.values())
        for name, (f, text) in muts.items():
            if (name == "prefix-lost" and not prefixed) or (name == "rank" and not classes) \
                    or (name == "all405" and m405 is None):
                continue                                   # на уроке без префикса и классов каталога — неприменим
            base = src if f == "routes.go" else rt
            if name == "pattern" and text == base:
                continue                                   # у урока нет свободного параметра с minLength 1 без шаблона
            with self.subTest(mutant=name):
                self.assertNotEqual(text, base, f"{name}: the mutant does not apply")
                mod = self.tmp / f"mut-{name}"
                shutil.copytree(self.fresh, mod)
                (mod / "apidoor" / f).write_text(text)
                try:
                    got = run(mod, pr)
                except AssertionError:
                    continue
                bad = [p for p, g in zip(pr, got) if expected(self.model, p) != g]
                self.assertTrue(bad, f"{name} survives")


for _lesson, _slug in LESSONS.items():
    _name = "DoorLesson_" + _slug
    globals()[_name] = type(_name, (DoorLessonBase, unittest.TestCase), {"LESSON": _lesson, "SLUG": _slug})


if __name__ == "__main__":
    unittest.main()
