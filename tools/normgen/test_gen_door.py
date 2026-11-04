"""Сверка генератора № 2 ADR-0125 (tools/normgen/gen_door.py) с OpenAPI урока — свой судья (ADR-0125 доп. (1) п. 1).

Запуск: /Users/murat/w2c/venv-spec-domain/bin/python tools/normgen/test_gen_door.py [-v]
(нужны PyYAML и jsonschema — независимые загрузчик и валидатор, — и go 1.22 в PATH; сети не нужно).

- загрузчик yamlsub = PyYAML на OpenAPI курса; конструкции вне подмножества — отказ;
- out/p01-1/go/apidoor — ровно свежая генерация; go build, go vet, gofmt чисты;
- покрытие: пути, методы, параметры query, тела запросов, коды и схемы ответов, заголовки — как в OpenAPI (читает PyYAML);
- маршруты: каждый метод на каждом пути и чужие пути (декодирование, нормализация, абсолютная форма) — код и схема
  отказа по OpenAPI;
- проверки схем = jsonschema (Draft 2020-12; integer — запись без дробной части) на случайных значениях и мутантах;
- ответы: каждое объявленное (операция, код, схема) — AnswerOf и Encode дают тело, равное значению и по схеме; поля —
  в порядке properties, имена отображений — в порядке байтов; необъявленный код, схема, заголовок — отказ Encode;
- Refuse — отказ по kind и полям в свою схему;
- query: разбор = urllib.parse.parse_qsl (latin-1 — байты) и схема параметра;
- сценарии приёмки 1.1: каждый ожидаемый ответ `<код> <JSON>` объявлен у операции и отвечает ровно одной её схеме
  (ADR-0125 п. 1: «Сценарии приёмки 1.1 против сгенерированных форм ответов»);
- мутации OpenAPI меняют выход и поведение двери.
max RSS процесса теста и детей — не больше 1 ГБ (проверяется).
"""
import base64
import copy
import json
import os
import random
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qsl

import jsonschema
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import gen_door  # noqa: E402
import yamlsub  # noqa: E402

SPEC = gen_door.DEFAULT_SPEC
OUT = HERE / "out/p01-1"
SCEN = ROOT / "Platform/01-store/acceptance/1/scenarios.tsv"
GOENV = dict(os.environ, GOPROXY="off", GOFLAGS="-mod=mod", GOWORK="off", GOTOOLCHAIN="local")
SEED = int(os.environ.get("NORMGEN_SEED", "20261104"))
SAMPLES = int(os.environ.get("NORMGEN_DOOR_SAMPLES", "120"))
MAX_RSS = 1 << 30
# ADR-0125 доп. (1) п. 3: тело команды записи судит write-checks.tsv — этих схем у двери нет.
EXCLUDED = {"Cmd", "BatchCmd", "BatchWrite", "BatchGuard"}
METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "TRACE", "CONNECT", "get", "Post"]

TYPES = jsonschema.Draft202012Validator.TYPE_CHECKER.redefine(
    "integer", lambda checker, x: isinstance(x, int) and not isinstance(x, bool))
Validator = jsonschema.validators.extend(jsonschema.Draft202012Validator, type_checker=TYPES)


def go(args, cwd):
    done = subprocess.run(["go", *args], cwd=cwd, env=GOENV, capture_output=True, text=True)
    if done.returncode:
        raise AssertionError(f"go {' '.join(args)} failed:\n{done.stdout}{done.stderr}")
    return done.stdout


def build_probe(out, workdir):
    """Обвязка doorprobe над модулем <out>/go (имя каталога out — p01-1)."""
    hdir = Path(workdir) / "doorprobe"
    hdir.mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "harness/doorprobe/main.go", hdir / "main.go")
    (hdir / "go.mod").write_text("module normgen/doorprobe\n\ngo 1.22\n\nrequire normgen/p01-1 v0.0.0\n\n"
                                 f"replace normgen/p01-1 => {Path(out) / 'go'}\n", encoding="utf-8")
    exe = Path(workdir) / "doorprobe.bin"
    go(["build", "-o", str(exe), "."], hdir)
    return exe


class Probe:
    def __init__(self, exe):
        self.proc = subprocess.Popen([str(exe)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def __call__(self, **req):
        self.proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise AssertionError(f"doorprobe died (code {self.proc.poll()})")
        return json.loads(line)

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=30)
        self.proc.stdout.close()


# ---------------------------------------------------------------- независимое чтение OpenAPI (PyYAML)

def op_name(path, method, n_methods):
    last = [p for p in path.split("/") if p][-1]
    return "".join(x[:1].upper() + x[1:] for x in re.split(r"[^A-Za-z0-9]+", last) if x) + \
        (method.capitalize() if n_methods > 1 else "")


class Doc:
    def __init__(self, doc):
        self.doc = doc
        self.schemas = doc["components"]["schemas"]
        self.inline = {}
        self.ops = []
        for path, item in doc["paths"].items():
            methods = [m for m in item if m in ("get", "put", "post", "delete", "patch", "head", "options", "trace")]
            for m in methods:
                o = item[m]
                name = op_name(path, m, len(methods))
                declared = {}
                for code, r in o["responses"].items():
                    if "$ref" in r:
                        r = doc["components"]["responses"][r["$ref"].split("/")[-1]]
                    content = r.get("content") or {}
                    media, names = None, []
                    for media, c in content.items():
                        s = c["schema"]
                        if "$ref" in s:
                            names = [s["$ref"].split("/")[-1]]
                        elif "oneOf" in s and all("$ref" in x for x in s["oneOf"]):
                            names = [x["$ref"].split("/")[-1] for x in s["oneOf"]]
                        else:
                            names = [f"{name}{code}"]
                            self.inline[names[0]] = s
                    declared[int(code)] = {"media": media, "schemas": self.expand(names),
                                           "headers": sorted(r.get("headers") or {})}
                params = [p for p in o.get("parameters") or []]
                body = None
                if "requestBody" in o:
                    s = o["requestBody"]["content"]["application/json"]["schema"]
                    body = [x["$ref"].split("/")[-1] for x in s["oneOf"]] if "oneOf" in s else [s["$ref"].split("/")[-1]]
                self.ops.append({"op": name, "method": m.upper(), "path": path, "params": params, "body": body,
                                 "body_required": bool((o.get("requestBody") or {}).get("required")),
                                 "declared": declared})

    def expand(self, names):
        out = []
        for n in names:
            s = self.schemas.get(n)
            if s and set(s) - {"description"} == {"oneOf"} and all(set(x) == {"$ref"} for x in s["oneOf"]):
                out.extend(self.expand([x["$ref"].split("/")[-1] for x in s["oneOf"]]))
            else:
                out.append(n)
        return out

    def op(self, name):
        return next(o for o in self.ops if o["op"] == name)

    def node(self, name):
        return self.inline[name] if name in self.inline else self.schemas[name]

    def validator(self, name_or_node):
        if isinstance(name_or_node, str):
            if name_or_node in self.inline:
                root = dict(self.inline[name_or_node], components=self.doc["components"])
            else:
                root = {"components": self.doc["components"], "$ref": f"#/components/schemas/{name_or_node}"}
        else:
            root = dict(name_or_node, components=self.doc["components"])
        return Validator(root)

    def resolve(self, node):
        while isinstance(node, dict) and "$ref" in node:
            node = self.schemas[node["$ref"].split("/")[-1]]
        return node


# ---------------------------------------------------------------- значения по схеме

STRINGS = ["", "a", "1", "0", "01", "42", "18446744073709551615", "123456789012345678901", "/x", "a/../b", "..foo",
           "a/..", "x/./y", "acc/k", "door", "admin", "configstore", "configstore-door", "Leader", "Door", "Follower",
           "Candidate", "Shutdown", "acc", "a-b_c.d", "-a", "A" * 128, "A" * 129, "é", "ключ", "a\u0000b", "a b",
           "badkey", "badrequest", "forbidden", "conflict", "expired", "early", "guard", "toolarge", "unavailable",
           "ambiguous", "refused", "put", "floor", "ab", "0a", "x" * 65, "f" * 64, "10.0.0.1:7000", "@"]
NUMBERS = [0, 1, -1, 60, 61, 60.5, 61.5, 1.5, 1.0, 20.0, 2 ** 53, 9007194959773696, 9007194959773697, 2 ** 63 - 1,
           2 ** 63, 2 ** 64 - 1, 2 ** 64, 1048576]
POOL = [None, True, False] + NUMBERS + STRINGS + [[], ["a"], ["a", "b"], [1], {}, {"a": "b"}, {"a": 1}]
KEYS = ["a", "b", "acc/x", "é", "s1", "zz"]


def shaped(d, node, rnd, depth=0):
    """Значение «по форме» узла схемы: часть подходит, часть нет — решает оракул."""
    node = d.resolve(node)
    if depth > 6 or not isinstance(node, dict):
        return rnd.choice(POOL)
    if "const" in node and rnd.random() < 0.85:
        return copy.deepcopy(node["const"])
    if "enum" in node and rnd.random() < 0.85:
        return copy.deepcopy(rnd.choice(node["enum"]))
    for key in ("oneOf", "anyOf"):
        if key in node and rnd.random() < 0.8:
            branch = rnd.choice(node[key])
            merged = dict({k: v for k, v in node.items() if k not in (key, "unevaluatedProperties")}, **d.resolve(branch))
            if "properties" in node and "properties" in d.resolve(branch):
                merged["properties"] = dict(node["properties"], **d.resolve(branch)["properties"])
                merged["required"] = list(node.get("required", [])) + list(d.resolve(branch).get("required", []))
            return shaped(d, merged, rnd, depth + 1)
    if "allOf" in node and rnd.random() < 0.3:
        for sub in node["allOf"]:
            if "then" in sub and "if" in sub:
                ifp = sub["if"].get("properties", {})
                base = shaped(d, {k: v for k, v in node.items() if k != "allOf"}, rnd, depth + 1)
                if isinstance(base, dict):
                    for p, s in ifp.items():
                        if "const" in s:
                            base[p] = s["const"]
                    for p, s in (sub["then"].get("properties") or {}).items():
                        if "const" in s and rnd.random() < 0.9:
                            base[p] = s["const"]
                return base
    t = node.get("type")
    if isinstance(t, list):
        t = rnd.choice(t)
    if t is None and "properties" in node:
        t = "object"
    if t == "object":
        out = {}
        props = node.get("properties") or {}
        req = node.get("required") or []
        for p, sub in props.items():
            if p in req or rnd.random() < 0.5:
                out[p] = shaped(d, sub, rnd, depth + 1)
        add = node.get("additionalProperties")
        if isinstance(add, dict):
            names = node.get("propertyNames")
            for _ in range(rnd.randint(0, 3)):
                k = shaped(d, names, rnd, depth + 1) if names and rnd.random() < 0.7 else rnd.choice(KEYS)
                if isinstance(k, str):
                    out[k] = shaped(d, add, rnd, depth + 1)
        return out
    if t == "array":
        return [shaped(d, node.get("items", {}), rnd, depth + 1) for _ in range(rnd.randint(0, 3))]
    if t == "string":
        return rnd.choice(STRINGS)
    if t == "integer":
        return rnd.choice([n for n in NUMBERS if isinstance(n, int)])
    if t == "number":
        return rnd.choice(NUMBERS)
    if t == "boolean":
        return rnd.choice([True, False])
    if t == "null":
        return None
    return rnd.choice(POOL)


def mutants(value, rnd):
    if isinstance(value, dict):
        for k in list(value):
            m = dict(value)
            del m[k]
            yield m
            m = dict(value)
            m[k] = rnd.choice(POOL)
            yield m
        m = dict(value)
        m["zz"] = 1
        yield m
    elif isinstance(value, list) and value:
        yield value[1:]
        yield value + [rnd.choice(POOL)]
    yield rnd.choice(POOL)


def ordered_ok(d, node, raw):
    """Порядок имён в записанном JSON (raw — разбор с object_pairs_hook=list): объект схемы — подпоследовательность
    properties, отображение (additionalProperties без properties) — по байтам UTF-8."""
    node = d.resolve(node)
    if isinstance(raw, list) and raw and isinstance(raw[0], tuple) or raw == [] and isinstance(node, dict) and \
            node.get("type") == "object":
        names = [k for k, _ in raw]
        branches = [d.resolve(b) for b in node.get("oneOf", [])] or [node]
        ok_any = False
        for b in branches:
            props = list((b.get("properties") or {}))
            if props:
                pos = [props.index(n) for n in names if n in props]
                ok = pos == sorted(pos) and all(ordered_ok(d, b["properties"][n], v) for n, v in raw if n in props)
            else:
                ok = names == sorted(names, key=lambda s: s.encode("utf-8"))
                add = b.get("additionalProperties")
                if isinstance(add, dict):
                    ok = ok and all(ordered_ok(d, add, v) for _, v in raw)
            ok_any = ok_any or ok
        return ok_any
    if isinstance(raw, list):
        items = node.get("items", {}) if isinstance(node, dict) else {}
        return all(ordered_ok(d, items, v) for v in raw)
    return True


def pairs_hook(pairs):
    return list(pairs)


# ---------------------------------------------------------------- тесты

class DoorBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SPEC.read_text(encoding="utf-8")
        cls.d = Doc(yaml.safe_load(cls.text))
        cls.tmp = tempfile.TemporaryDirectory(prefix="normgen-door-")
        cls.out = Path(cls.tmp.name) / "p01-1"
        gen_door.generate(SPEC, cls.out)
        cls.probe = Probe(build_probe(cls.out, cls.tmp.name))
        cls.rnd = random.Random(SEED)

    @classmethod
    def tearDownClass(cls):
        cls.probe.close()
        cls.tmp.cleanup()
        own = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        kids = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        scale = 1 if sys.platform == "darwin" else 1024
        print(f"\nmax RSS: test {own * scale >> 20} MiB, children {kids * scale >> 20} MiB", file=sys.stderr)
        if max(own, kids) * scale >= MAX_RSS:
            raise AssertionError("a process holds more than 1 GiB")

    def valid(self, name, value):
        return self.d.validator(name).is_valid(value)


class Loader(unittest.TestCase):
    def test_yaml_matches_pyyaml(self):
        """yamlsub = PyYAML на всех OpenAPI курса; якорь — отказ (вне подмножества)."""
        files = subprocess.run(["git", "ls-files", "*.openapi.yaml"], cwd=ROOT, capture_output=True,
                               text=True).stdout.split()
        self.assertGreater(len(files), 5)
        same = 0
        for f in files:
            text = (ROOT / f).read_text(encoding="utf-8")
            if any(getattr(e, "anchor", None) or isinstance(e, yaml.AliasEvent) for e in yaml.parse(text)):
                with self.assertRaises(yamlsub.YamlError, msg=f):
                    yamlsub.load(text, f)
                continue
            self.assertEqual(yamlsub.load(text, f), yaml.safe_load(text), f)
            same += 1
        self.assertGreater(same, 5)

    def test_yaml_refusals(self):
        for text in ("a: &x 1\nb: *x\n", "a: !!str 1\n", "--- \na: 1\n", "a: 1\na: 2\n", "? a\n: 1\n", "a: |2\n  x\n"):
            with self.assertRaises(yamlsub.YamlError, msg=text):
                yamlsub.load(text)


class Generated(DoorBase):
    def test_out_up_to_date(self):
        """tools/normgen/out/p01-1/go/apidoor — ровно свежая генерация; шапка несёт sha256 OpenAPI."""
        for name in ("door.go", "runtime.go"):
            self.assertEqual((self.out / "go/apidoor" / name).read_bytes(), (OUT / "go/apidoor" / name).read_bytes(),
                             f"{name} is stale: run tools/normgen/gen_door.py")
        self.assertEqual((self.out / "go/go.mod").read_bytes(), (OUT / "go/go.mod").read_bytes())
        import hashlib
        self.assertIn(hashlib.sha256(self.text.encode()).hexdigest(), (OUT / "go/apidoor/door.go").read_text()[:400])

    def test_build_vet_fmt(self):
        go(["build", "./..."], OUT / "go")
        go(["vet", "./..."], OUT / "go")
        fmt = subprocess.run(["gofmt", "-l", "apidoor"], cwd=OUT / "go", capture_output=True, text=True).stdout
        self.assertEqual(fmt, "")

    def test_coverage(self):
        """Операции, query, тела, коды, схемы и заголовки двери — как в OpenAPI (PyYAML)."""
        got = self.probe(cmd="table")["ops"]
        self.assertEqual([(o["method"], o["path"], o["op"]) for o in got],
                         [(o["method"], o["path"], o["op"]) for o in self.d.ops])
        for g, o in zip(got, self.d.ops):
            self.assertEqual(g["query"], [p["name"] for p in o["params"]], o["op"])
            self.assertEqual(g["body"], [n for n in o["body"] or [] if n not in EXCLUDED], o["op"])
            self.assertEqual(g["writecheck"], [n for n in o["body"] or [] if n in EXCLUDED], o["op"])
            self.assertEqual(g["body_required"], o["body_required"], o["op"])
            want = {str(c): {"schemas": r["schemas"], "headers": r["headers"]} for c, r in o["declared"].items()}
            self.assertEqual({c: {"schemas": v["schemas"], "headers": sorted(v["headers"] or [])} for c, v in g["declared"].items()},
                             want, o["op"])
        names = [n for n in self.d.schemas if n not in EXCLUDED] + list(self.d.inline)
        for n in names:
            self.assertTrue(self.probe(cmd="check", schema=n, json="null")["known"], n)
        for n in EXCLUDED:
            self.assertFalse(self.probe(cmd="check", schema=n, json="null")["known"], n)

    def test_routes(self):
        """Каждый метод на каждом пути; чужие пути — 404 со схемой 404; метод не своего пути — 405, если объявлен."""
        paths = {}
        for o in self.d.ops:
            paths.setdefault(o["path"], []).append(o)
        for path, ops in paths.items():
            wrong = 405 if all(405 in o["declared"] for o in ops) else 404
            for method in METHODS:
                for target in (path, path + "?a=b", path + "?"):
                    r = self.probe(cmd="route", method=method, target=target)
                    mine = [o for o in ops if o["method"] == method]
                    where = f"{method} {target}"
                    if mine:
                        self.assertEqual(r["op"], mine[0]["op"], where)
                        self.assertEqual(r["query"], target.partition("?")[2], where)
                        self.assertIsNone(r["resp"], where)
                    else:
                        self.refusal(r, wrong, ops[0]["declared"][wrong], where)
        nf = self.d.ops[0]["declared"][404]
        for target in ("/", "", "/v1", "/v1/", "/v1/get/", "//v1/get", "/v1/%67et", "/V1/GET", "/v1/getx",
                       "http://localhost/v1/get?key=a", "/metrics/", "/v1/get;x", "/v1/write/", "*", "/v1/./get"):
            for method in ("GET", "POST", "HEAD"):
                self.refusal(self.probe(cmd="route", method=method, target=target), 404, nf, f"{method} {target}")

    def refusal(self, r, code, declared, where):
        self.assertEqual(r["op"], "", where)
        resp = r["resp"]
        self.assertEqual(resp["code"], code, where)
        self.assertEqual(resp["header"], [["Content-Type", declared["media"]]], where)
        body = json.loads(base64.b64decode(resp["body"]))
        self.assertEqual(sum(self.valid(n, body) for n in declared["schemas"]), 1, where)

    def test_schema_checks(self):
        """chk* = jsonschema на значениях по форме схем и их мутантах."""
        mismatches, total, valid = [], 0, 0
        for name in [n for n in self.d.schemas if n not in EXCLUDED] + list(self.d.inline):
            v = self.d.validator(name)
            for _ in range(SAMPLES):
                base = shaped(self.d, self.d.node(name), self.rnd)
                for value in [base, *mutants(base, self.rnd)]:
                    text = json.dumps(value, ensure_ascii=False)
                    want = v.is_valid(value)
                    got = self.probe(cmd="check", schema=name, json=text)
                    total += 1
                    valid += want
                    if (got["violation"] is None) != want:
                        mismatches.append(f"{name}: {text[:200]} oracle={want} door={got['violation']}")
        self.assertEqual(mismatches[:20], [], f"{len(mismatches)} of {total}")
        self.assertGreater(valid, total // 10, "too few valid samples: the test does not reach the success branch")
        print(f"\nschema checks: {total} values, {valid} valid", file=sys.stderr)

    def samples(self, name, n=40, small=False):
        out = []
        for _ in range(n * 30):
            x = shaped(self.d, self.d.node(name), self.rnd)
            if self.valid(name, x) and x not in out and (not small or representable(x, exact_float=True)):
                out.append(x)
                if len(out) >= n:
                    break
        return out

    def test_answers(self):
        """Каждое объявленное (операция, код, схема): AnswerOf и Encode; тело = значение, по схеме, в порядке полей."""
        seen = 0
        for o in self.d.ops:
            for code, r in o["declared"].items():
                for name in r["schemas"]:
                    vals = self.samples(name)
                    self.assertTrue(vals, f"no valid sample of {name}")
                    for value in vals:
                        hits = sum(self.valid(n, value) for n in r["schemas"])
                        text = json.dumps(value, ensure_ascii=False)
                        got = self.probe(cmd="answer", op=o["op"], code=code, json=text)
                        where = f"{o['op']} {code} {name}: {text[:200]}"
                        if hits == 1 and "not representable" in got.get("answer_error", ""):
                            # целое вне int64 или не точное в binary64 (поле number): дверь не обрезает молча
                            self.assertFalse(representable(value, exact_float=True), where)
                            continue
                        if hits != 1:
                            self.assertIn("answer_error", got, where)
                            continue
                        self.assertIn("resp", got, where)
                        resp = got["resp"]
                        raw = base64.b64decode(resp["body"])
                        self.assertEqual(resp["header"], [["Content-Type", r["media"]]], where)
                        if r["media"] == "application/json":
                            self.assertEqual(json.loads(raw), value, where)
                            self.assertTrue(ordered_ok(self.d, self.d.node(name),
                                                       json.loads(raw, object_pairs_hook=pairs_hook)), where)
                        else:
                            self.assertEqual(raw.decode("utf-8"), value, where)
                        retry = self.probe(cmd="answer", op=o["op"], code=code, json=text, retry=True)
                        if "Retry-After" in r["headers"]:
                            self.assertEqual(retry["resp"]["header"][-1], ["Retry-After", "1"], where)
                        else:
                            self.assertIn("encode_error", retry, where)
                        seen += 1
        self.assertGreater(seen, 100)

    def test_undeclared(self):
        """Encode отвергает код и схему, не объявленные у операции."""
        for o in self.d.ops:
            for other in self.d.ops:
                for code, r in other["declared"].items():
                    for name in r["schemas"]:
                        vals = self.samples(name, 2, small=True)
                        if not vals or sum(self.valid(n, vals[0]) for n in r["schemas"]) != 1:
                            continue
                        got = self.probe(cmd="answer", op=o["op"], code=code, json=json.dumps(vals[0]),
                                         via_op=other["op"], via_code=code)
                        mine = o["declared"].get(code)
                        if mine and name in mine["schemas"]:
                            self.assertIn("resp", got, f"{o['op']} {code} {name}")
                        else:
                            self.assertIn("encode_error", got, f"{o['op']} {code} {name}")

    def test_refuse(self):
        """Refuse(kind, поля) — в ту схему отказа, которой отвечает объект; иначе отказ."""
        n = 0
        for o in self.d.ops:
            for code, r in o["declared"].items():
                if code < 400:
                    continue
                for name in r["schemas"]:
                    for value in self.samples(name, 5, small=True):
                        fields = {k: v for k, v in value.items() if k not in ("kind", "error")}
                        got = self.probe(cmd="refuse", op=o["op"], code=code, kind=value["kind"], msg="m",
                                         fields=fields)
                        full = dict(fields, kind=value["kind"], error="m")
                        hits = [s for s in r["schemas"] if self.valid(s, full)]
                        if len(hits) == 1:
                            self.assertEqual(got.get("schema"), hits[0], f"{o['op']} {code} {value}")
                            self.assertEqual(json.loads(base64.b64decode(got["resp"]["body"])), full)
                            n += 1
                        else:
                            self.assertIn("answer_error", got)
        self.assertGreater(n, 30)

    def test_query(self):
        """Разбор query = parse_qsl (latin-1 — байты) + схема параметра; порядок: есть ли, повтор, UTF-8, схема."""
        fixed = ["key=a", "", "key", "key=", "key=a&key=b", "key=a&&", "&&key=a", "key=a+b", "key=a%2Bb", "key=%zz",
                 "key=%", "key=%2", "key=%00", "key=%FF", "key=%C3%A9", "key=/x", "key=a/../b", "key=..foo", "x=1&key=a",
                 "key=a=b", "KEY=a", "key=a&x", "key=%2Fx", "key=%2e%2e/a", "key=%FF&key=%FF", "key&key", "k%65y=a",
                 "prefix=a", "prefix=a&prefix=b", "prefix=%FF", "prefix=", "prefix", "prefix=a+b", "prefix=%2B",
                 "key=" + "a" * 1025, "key=%E2%82", "key=%ED%A0%80"]
        alphabet = ["k", "e", "y", "=", "&", "%", "2", "B", "F", "f", "+", "a", "/", ".", "p", "r", "x", "C", "3", "0"]
        cases = fixed + ["".join(self.rnd.choice(alphabet) for _ in range(self.rnd.randint(0, 14)))
                         for _ in range(400)] + \
            ["key=" + "".join(self.rnd.choice(alphabet) for _ in range(self.rnd.randint(0, 10))) for _ in range(300)]
        n = 0
        for o in self.d.ops:
            if not o["params"]:
                continue
            for raw in cases:
                got = self.probe(cmd="dispatch", op=o["op"], query=raw)
                want = self.query_oracle(o, raw)
                where = f"{o['op']} ?{raw}"
                if isinstance(want, tuple):
                    self.assertEqual(got["method"], "QueryRefused", where)
                    e = got["error"]
                    self.assertEqual((e["param"], e["reason"], e["schema"]), want[:3], where)
                    if want[3]:
                        self.assertEqual(e["rule"], want[3], where)
                else:
                    self.assertEqual(got["method"], o["op"], where)
                    self.assertEqual(got["query"], want, where)
                n += 1
        self.assertGreater(n, 1000)

    def query_oracle(self, o, raw):
        pairs = [(k.encode("latin-1"), v.encode("latin-1"))
                 for k, v in parse_qsl(raw, keep_blank_values=True, encoding="latin-1")]
        out = {}
        for p in o["params"]:
            schema_name = p["schema"]["$ref"].split("/")[-1] if "$ref" in p["schema"] else ""
            vals = [v for k, v in pairs if k == p["name"].encode()]
            if not vals:
                if p.get("required"):
                    return (p["name"], 1, "", "")
                out[p["name"]] = None
                continue
            if len(vals) > 1:
                return (p["name"], 2, "", "")
            b = vals[0]
            try:
                s = b.decode("utf-8")
            except UnicodeDecodeError:
                if string_bound(self.d, p["schema"]):
                    return (p["name"], 3, schema_name, "utf8")
                out[p["name"]] = base64.b64encode(b).decode()
                continue
            if not self.d.validator(p["schema"]).is_valid(s):
                return (p["name"], 3, schema_name, "")
            out[p["name"]] = base64.b64encode(b).decode()
        return out

    def test_acceptance_forms(self):
        """Сценарии приёмки 1.1: ожидаемый ответ объявлен у операции и отвечает ровно одной её схеме."""
        steps = 0
        for line in SCEN.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or not line.strip():
                continue
            cells = line.split("\t")
            if len(cells) < 4 or not re.match(r"[A-Z]+ /", cells[2]) or not re.match(r"[0-9]{3}( |$)", cells[3]):
                continue
            method, target = cells[2].split(" ")[:2]
            code_s, _, body = cells[3].partition(" ")
            code = int(code_s)
            where = f"{cells[0]} {cells[1]}: {cells[2][:80]} → {cells[3][:120]}"
            value = None
            if body.strip():
                value = json.loads(re.sub(r'"\$[A-Za-z0-9_]+"', '"1"', body))
                if isinstance(value, dict) and "kind" in value and "error" not in value:
                    value["error"] = "x"
            r = self.probe(cmd="route", method=method, target=target)
            if r["op"] == "":
                self.assertEqual(r["resp"]["code"], code, where)
                if value is not None:
                    self.assertEqual(json.loads(base64.b64decode(r["resp"]["body"]))["kind"], value["kind"], where)
                steps += 1
                continue
            o = self.d.op(r["op"])
            self.assertIn(code, o["declared"], where)
            if value is not None:
                schemas = o["declared"][code]["schemas"]
                hits = [n for n in schemas if self.valid(n, value)]
                self.assertEqual(len(hits), 1, f"{where}: oracle {hits}")
                got = self.probe(cmd="answer", op=r["op"], code=code, json=json.dumps(value, ensure_ascii=False))
                self.assertEqual(got.get("schema"), hits[0], f"{where}: {got}")
            steps += 1
        self.assertGreater(steps, 300)
        print(f"\nacceptance 1.1: {steps} steps against the door forms", file=sys.stderr)

    def test_decode_bodies(self):
        """Decode<схема> тел запросов = jsonschema; собранное значение несёт поля входа."""
        for name in ("FloorCmd", "Join", "Leave"):
            for _ in range(SAMPLES):
                base = shaped(self.d, self.d.node(name), self.rnd)
                for value in [base, *mutants(base, self.rnd)]:
                    got = self.probe(cmd="decode", schema=name, json=json.dumps(value, ensure_ascii=False))
                    want = self.valid(name, value)
                    self.assertEqual(got["violation"] is None, want, f"{name} {value}")
                    if want:
                        props = self.d.resolve(self.d.node(name))["properties"]
                        for k in value:
                            if "const" not in props[k]:
                                self.assertIn(re.sub(r"(^|_)([a-z])", lambda m: m[2].upper(), k), got["value"])


def representable(value, exact_float=False):
    """Целые значения в пределах int64 (и, с exact_float, точные в binary64) — то, что держат типы Go двери у integer
    без предела в схеме и у number."""
    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return -2 ** 63 <= value < 2 ** 63 and (not exact_float or int(float(value)) == value)
    if isinstance(value, dict):
        return all(representable(v, exact_float) for v in value.values())
    if isinstance(value, list):
        return all(representable(v, exact_float) for v in value)
    return True


def string_bound(d, node, seen=None):
    seen = set() if seen is None else seen
    if isinstance(node, dict):
        if "$ref" in node:
            n = node["$ref"].split("/")[-1]
            if n not in seen:
                seen.add(n)
                if string_bound(d, d.schemas[n], seen):
                    return True
        if {"minLength", "maxLength", "pattern"} & set(node):
            return True
        return any(string_bound(d, v, seen) for k, v in node.items() if k != "description")
    if isinstance(node, list):
        return any(string_bound(d, v, seen) for v in node)
    return False


class Kit(unittest.TestCase):
    """Часть door пакета Б (build_kit --parts) и стенд заглушки (build_stub): сборка, манифест, дымовая проба демона.
    Это не прогон приёмки (он — раннером на сервере): несколько запросов, что демон собран и отвечает дверью."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(HERE / "kit"))
        import build_kit
        import build_stub
        cls.build_kit, cls.build_stub = build_kit, build_stub
        cls.tmp = tempfile.TemporaryDirectory(prefix="nd-")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_parts(self):
        bk = self.build_kit
        for parts in (("door",), ("vectors", "door")):
            dst = Path(self.tmp.name) / "-".join(parts)
            m = bk.build(dst, "kittest", parts)
            store = dst / "01-store"
            (store / "go.mod").write_text("module kittest\n\ngo 1.22\n", encoding="utf-8")
            go(["build", "./..."], store)
            go(["vet", "./..."], store)
            self.assertEqual(m["parts"], ["writecheck", *sorted(parts)])
            door = [f for f in m["files"] if f["component"] == "door"]
            self.assertEqual(sorted((f["path"], f["origin"]) for f in door),
                             [("01-store/internal/apidoor/door.go", "generated"),
                              ("01-store/internal/apidoor/runtime.go", "handwritten")])
            self.assertEqual(m["openapi"]["sha256"], bk.sha256(SPEC.read_bytes()))
            self.assertIn("kittest/internal/apidoor", (dst / "KIT.md").read_text(encoding="utf-8"))
            self.assertEqual(sorted(m["lines_by_component"]), sorted({"kit", "normgen", *parts}))
        with self.assertRaises(bk.KitError):
            bk.build(Path(self.tmp.name) / "bad", "kittest", ("doors",))
        m = bk.build(Path(self.tmp.name) / "default", "kittest")
        self.assertEqual(m["parts"], ["writecheck"])
        self.assertNotIn("door", m["lines_by_component"])
        self.assertNotIn("openapi", m)

    def test_stub_daemon(self):
        import socket
        import time
        dst = Path(self.tmp.name) / "stub"
        self.build_stub.build(dst, "0" * 40, go_build=True)
        run = Path(tempfile.mkdtemp(prefix="nd", dir="/tmp"))
        self.addCleanup(shutil.rmtree, run, True)
        rights = run / "rights.json"
        rights.write_text('{"roles": {"acc": {"group": "acc", "read": ["acc/*"], "write": ["acc/*"], '
                          '"delete": ["acc/*"]}}}', encoding="utf-8")
        proc = subprocess.Popen([str(dst / "01-store/bin/stubstore"), "-dir", str(run / "data"), "-admin",
                                 str(run / "admin.sock"), "-rights", str(rights), "-max-body", "200", "-max-value", "64"],
                                stderr=subprocess.PIPE)
        self.addCleanup(lambda: (proc.terminate(), proc.wait(10), proc.stderr.close()))
        for _ in range(200):
            if (run / "acc.sock").exists() or proc.poll() is not None:
                break
            time.sleep(0.05)
        if proc.poll() is not None:
            raise AssertionError(f"stubstore exited {proc.returncode}: {proc.stderr.read().decode()}")

        def http(sock, method, target, body=b""):
            s = socket.socket(socket.AF_UNIX)
            s.connect(str(run / sock))
            s.sendall(f"{method} {target} HTTP/1.1\r\nHost: x\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n"
                      .encode() + body)
            data = b""
            while chunk := s.recv(65536):
                data += chunk
            s.close()
            head, _, payload = data.partition(b"\r\n\r\n")
            return int(head.split()[1]), json.loads(payload) if payload else None

        d = Doc(yaml.safe_load(SPEC.read_text(encoding="utf-8")))
        self.assertEqual(http("acc.sock", "GET", "/v1/get?key=acc/x"), (200, {"items": None, "index": ""}))
        code, w = http("acc.sock", "POST", "/v1/write", b'{"op":"put","key":"acc/x","items":{"n":"1"}}')
        self.assertEqual(code, 200)
        self.assertEqual(http("acc.sock", "GET", "/v1/get?key=acc/x"), (200, {"items": {"n": "1"}, "index": w["index"]}))
        self.assertEqual(http("acc.sock", "GET", "/v1/list?prefix=acc/"), (200, {"keys": {"acc/x": w["index"]}}))
        for target, want in (("/v1/get?key=a&key=b", "badrequest"), ("/v1/get?key=%FF", "badkey"),
                             ("/v1/get?key", "badkey"), ("/v1/get", "badrequest")):
            code, body = http("acc.sock", "GET", target)
            self.assertEqual((code, body["kind"]), (400, want), target)
        self.assertEqual(http("acc.sock", "PATCH", "/v1/get?key=acc/x")[0], 404)
        self.assertEqual(http("acc.sock", "GET", "/v1/%67et?key=acc/x")[0], 404)
        self.assertEqual(http("admin.sock", "GET", "/v1/join")[0], 405)
        self.assertEqual(http("acc.sock", "POST", "/v1/write", b'{"op":"floor","floor":1,"id":"ab"}')[1]["kind"],
                         "forbidden")
        code, body = http("acc.sock", "POST", "/v1/write", b'{"op":"put","key":"acc/y","items":{"n":"' + b"x" * 80 + b'"}}')
        self.assertEqual((code, body["kind"], body["limit"], body["key"]), (413, "toolarge", 64, "acc/y"))
        code, body = http("acc.sock", "POST", "/v1/write", b"{" + b" " * 300 + b"}")
        self.assertEqual((code, body["kind"], body["limit"]), (413, "toolarge", 200))
        code, body = http("admin.sock", "GET", "/v1/status")
        self.assertEqual(code, 200)
        self.assertTrue(d.validator("Status").is_valid(body), body)
        self.assertEqual(http("admin.sock", "POST", "/v1/join", b'{"id":"s2","raft":"a:1","api":"b:2"}'),
                         (409, {"kind": "refused", "error": "stub has no group"}))
        self.assertEqual(http("admin.sock", "POST", "/v1/join", b'{"id":"s2","raft":"","api":"b:2"}')[1]["kind"],
                         "badrequest")
        self.assertEqual(http("acc.sock", "GET", "/v1/rights")[1]["kind"], "forbidden")
        code, body = http("admin.sock", "GET", "/v1/rights")
        self.assertEqual((code, sorted(body["roles"])), (200, ["acc"]))


class Mutations(unittest.TestCase):
    """Мутации OpenAPI: выход меняется, и дверь ведёт себя по мутанту."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="normgen-door-mut-")
        _, cls.doc = gen_door.load(SPEC)
        cls.base = (OUT / "go/apidoor/door.go").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def mutant(self, k, change, probe=True):
        doc = copy.deepcopy(self.doc)
        change(doc)
        out = Path(self.tmp.name) / f"m{k}" / "p01-1"
        gen_door.emit(doc, "mutant", "0" * 64, out)
        text = (out / "go/apidoor/door.go").read_text(encoding="utf-8")
        self.assertNotEqual(text.split("\n", 3)[3], self.base.split("\n", 3)[3], f"mutant {k}: the output did not change")
        if not probe:
            return None
        p = Probe(build_probe(out, Path(self.tmp.name) / f"m{k}"))
        self.addCleanup(p.close)
        return p

    def test_remove_path(self):
        p = self.mutant(1, lambda d: d["paths"].pop("/metrics"))
        self.assertEqual(p(cmd="route", method="GET", target="/metrics")["resp"]["code"], 404)
        self.assertNotIn("Metrics", [o["op"] for o in p(cmd="table")["ops"]])

    def test_add_405(self):
        p = self.mutant(2, lambda d: d["paths"]["/v1/get"]["get"]["responses"].update(
            {"405": {"$ref": "#/components/responses/NoRoute"}}))
        self.assertEqual(p(cmd="route", method="PATCH", target="/v1/get")["resp"]["code"], 405)
        self.assertEqual(p(cmd="route", method="PATCH", target="/v1/list")["resp"]["code"], 404)

    def test_pattern(self):
        p = self.mutant(3, lambda d: d["components"]["schemas"]["Version"].update(pattern="^(?:[1-9][0-9]*)$"))
        self.assertIsNotNone(p(cmd="check", schema="Version", json='"0"')["violation"])
        self.assertIsNone(p(cmd="check", schema="Version", json='"7"')["violation"])

    def test_required_field(self):
        def change(d):
            w = d["components"]["schemas"]["Written"]
            w["properties"]["zz"] = {"type": "string"}
            w["required"] = w["required"] + ["zz"]
        p = self.mutant(4, change)
        self.assertIn("answer_error", p(cmd="answer", op="Write", code=200, json='{"index": "1"}'))
        got = p(cmd="answer", op="Write", code=200, json='{"index": "1", "zz": "q"}')
        self.assertEqual(json.loads(base64.b64decode(got["resp"]["body"])), {"index": "1", "zz": "q"})

    def test_remove_code(self):
        p = self.mutant(5, lambda d: d["paths"]["/v1/write"]["post"]["responses"].pop("412"))
        got = p(cmd="answer", op="Write", code=412, json='{"kind": "guard", "error": "", "key": "a", "index": ""}',
                via_op="Write", via_code=409)
        self.assertTrue("answer_error" in got or "encode_error" in got)

    def test_param_optional(self):
        p = self.mutant(6, lambda d: d["paths"]["/v1/get"]["get"]["parameters"][0].update(required=False))
        self.assertEqual(p(cmd="dispatch", op="Get", query="")["method"], "Get")

    def test_header_removed(self):
        p = self.mutant(7, lambda d: d["paths"]["/v1/status"]["get"]["responses"]["503"].pop("headers"))
        got = p(cmd="answer", op="Status", code=503, json='{"kind": "unavailable", "error": ""}', retry=True)
        self.assertIn("encode_error", got)

    def test_text_only(self):
        """Мутации без пробы: выход меняется."""
        def rename(d):
            s = d["components"]["schemas"]["Status"]
            s["properties"]["tls2"] = s["properties"].pop("tls")
            s["required"] = [x if x != "tls" else "tls2" for x in s["required"]]
        self.mutant(8, rename, probe=False)
        self.mutant(9, lambda d: d["components"]["schemas"]["Listing"].pop("additionalProperties"), probe=False)
        self.mutant(10, lambda d: d["components"]["schemas"]["FloorCmd"]["properties"]["floor"].update(maximum=10),
                    probe=False)
        self.mutant(11, lambda d: d["paths"]["/v1/list"]["get"]["parameters"][0]["schema"].update(minLength=1),
                    probe=False)

    def test_subset_refusals(self):
        """Вне подмножества — отказ генератора, а не молчаливая потеря ограничения."""
        cases = [
            lambda d: d["components"]["schemas"]["Version"].update(format="uint64"),
            lambda d: d["paths"].update({"/v1/x/{id}": d["paths"]["/v1/get"]}),
            lambda d: d["paths"]["/v1/get"]["get"]["parameters"][0].update({"in": "header"}),
            lambda d: d["paths"]["/v1/get"]["get"]["responses"].update({"default": {"description": "x"}}),
            lambda d: d["paths"]["/v1/get"]["get"]["parameters"][0].update(schema={"type": "integer"}),
            lambda d: d["components"]["schemas"]["Key"].update(pattern=r"^\w+$"),
            lambda d: d["paths"]["/v1/get"]["get"]["responses"].pop("404"),
            lambda d: d["paths"]["/v1/status"]["get"]["responses"]["503"]["headers"]["Retry-After"]["schema"].pop("const"),
            lambda d: d["components"]["schemas"].pop("Cmd"),
        ]
        for k, change in enumerate(cases):
            doc = copy.deepcopy(self.doc)
            change(doc)
            with self.assertRaises(gen_door.GenError, msg=f"case {k}"):
                gen_door.emit(doc, "mutant", "0" * 64, Path(self.tmp.name) / f"r{k}" / "p01-1")


if __name__ == "__main__":
    unittest.main()
