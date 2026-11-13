"""Independently judge OpenAPI generation (ADR-0125 generator 2, addendum 1, item 1). Run test_gen_door.py with PyYAML, jsonschema and Go 1.22, without network. Compare yamlsub with PyYAML and reject unsupported YAML; require fresh output, build/vet/gofmt and full paths/methods/query/body/status/schema/header coverage. Test routes, foreign targets and decoding/normalization/absolute forms; compare schema checks to Draft 2020-12 jsonschema with lexical integer rules. Every declared response must round-trip AnswerOf/Encode with schema and field ordering; undeclared code/schema/header must refuse. Check Refuse, query parsing via latin1 parse_qsl, acceptance1.1 response uniqueness and behavior-changing OpenAPI mutants. Peak test/child RSS stays within1GB."""
import lesson as output_lesson
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
from types import SimpleNamespace
from urllib.parse import parse_qsl

import jsonschema
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import gen_door  # noqa: E402
import yamlsub  # noqa: E402
import tsv_input  # noqa: E402 — source cells before the existing HTTP/schema checks

SPEC = gen_door.DEFAULT_SPEC
OUT = output_lesson.output_root() / 'p01-1'
SCEN = ROOT / "Platform/01-store/acceptance/1/scenarios.tsv"
GOENV = dict(os.environ, GOPROXY="off", GOFLAGS="-mod=mod", GOWORK="off", GOTOOLCHAIN="local")
SEED = int(os.environ.get("NORMGEN_SEED", "20261104"))
SAMPLES = int(os.environ.get("NORMGEN_DOOR_SAMPLES", "120"))
MAX_RSS = 1 << 30
# ADR-0125 addendum 1, item 3: write-checks.tsv judges write-command bodies; the door omits those schemas.
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
    """Build doorprobe against the <out>/go module, retaining the p01-1 output directory name."""
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


# ---------------------------------------------------------------- independent OpenAPI read (PyYAML)

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
                    headers = r.get("headers", {})
                    if type(headers) is not dict:
                        raise ValueError("response headers must be a mapping")
                    header_schemas, required_headers = {}, set()
                    for key, header in headers.items():
                        if (type(key) is not str or type(header) is not dict or
                                type(header.get("schema")) is not dict or
                                type(header.get("required", False)) is not bool):
                            raise ValueError("malformed source header declaration")
                        header_schemas[key] = copy.deepcopy(header["schema"])
                        if header.get("required", False):
                            required_headers.add(key)
                    declared[int(code)] = {"media": media, "schemas": self.expand(names),
                                           "headers": sorted(headers), "header_schemas": header_schemas,
                                           "required_headers": sorted(required_headers)}
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

    def header_validator(self, op, code, name):
        schema = self.op(op)["declared"][code]["header_schemas"][name]
        return self.validator(schema)

    def resolve(self, node):
        while isinstance(node, dict) and "$ref" in node:
            node = self.schemas[node["$ref"].split("/")[-1]]
        return node


def source_required_probe_headers(response):
    """Supply declared required constants to the private observer; expected wire values stay Source-owned."""
    from test_gen_machine import CheckingError
    options, headers = {}, []
    fields = {"Retry-After": "retry", "Allow": "allow", "Content-Length": "content_length",
              "Transfer-Encoding": "transfer_encoding"}
    for name in response["required_headers"]:
        schema = response["header_schemas"][name]
        if name not in fields or "const" not in schema:
            raise CheckingError("no declared private-observer input for required Source header " + name)
        value = schema["const"]
        if name == "Retry-After":
            if type(value) is not int:
                raise CheckingError("required Retry-After is not an integer constant")
            options[fields[name]] = True
        else:
            if type(value) is not str:
                raise CheckingError("required Source header is not a string constant")
            options[fields[name]] = True if name == "Allow" else value
        headers.append([name, str(value)])
    return options, headers


# ---------------------------------------------------------------- schema-shaped values

STRINGS = ["", "a", "1", "0", "01", "42", "18446744073709551615", "123456789012345678901", "/x", "a/../b", "..foo",
           "a/..", "x/./y", "acc/k", "door", "admin", "configstore", "configstore-door", "Leader", "Door", "Follower",
           "Candidate", "Shutdown", "acc", "a-b_c.d", "-a", "A" * 128, "A" * 129, "é", '\u043a\u043b\u044e\u0447', "a\u0000b", "a b",
           "badkey", "badrequest", "forbidden", "conflict", "expired", "early", "guard", "toolarge", "unavailable",
           "ambiguous", "refused", "put", "floor", "ab", "0a", "x" * 65, "f" * 64, "10.0.0.1:7000", "@"]
NUMBERS = [0, 1, -1, 60, 61, 60.5, 61.5, 1.5, 1.0, 20.0, 2 ** 53, 9007194959773696, 9007194959773697, 2 ** 63 - 1,
           2 ** 63, 2 ** 64 - 1, 2 ** 64, 1048576]
POOL = [None, True, False] + NUMBERS + STRINGS + [[], ["a"], ["a", "b"], [1], {}, {"a": "b"}, {"a": 1}]
KEYS = ["a", "b", "acc/x", "é", "s1", "zz"]


def shaped(d, node, rnd, depth=0):
    """Generate schema-shaped candidates, both potentially valid and invalid; only the oracle decides validity."""
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
    """Check raw object name order: declared object fields follow a properties subsequence; pure additionalProperties maps use UTF-8 byte order."""
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


# ---------------------------------------------------------------- tests

class DoorBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
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
        """Compare yamlsub with PyYAML for every course OpenAPI, including P/10 mapping-value anchors/aliases."""
        files = subprocess.run(["git", "ls-files", "*.openapi.yaml"], cwd=ROOT, capture_output=True,
                               text=True).stdout.split()
        self.assertGreater(len(files), 5)
        same = 0
        for f in files:
            text = (ROOT / f).read_text(encoding="utf-8")
            self.assertEqual(yamlsub.load(text, f), yaml.safe_load(text), f)
            same += 1
        self.assertGreater(same, 5)

    def test_yaml_refusals(self):
        self.assertEqual(yamlsub.load("a: &x 1\nb: *x\nc: &y\n  d: 2\ne: *y\n"),
                         yaml.safe_load("a: &x 1\nb: *x\nc: &y\n  d: 2\ne: *y\n"))
        for text in ("a: *x\n", "a: &x 1\nb: &x 2\n", "- &x 1\n- *x\n", "a: !!str 1\n", "--- \na: 1\n", "a: 1\na: 2\n", "? a\n: 1\n", "a: |2\n  x\n"):
            with self.assertRaises(yamlsub.YamlError, msg=text):
                yamlsub.load(text)


class CoverageProjectionControls(unittest.TestCase):
    """Synthetic private frames exercise the unchanged independent Source coverage check."""

    def setUp(self):
        self.source = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
        self.doc = Doc(copy.deepcopy(self.source))
        self.table = []
        for op in self.doc.ops:
            self.table.append(dict(op=op["op"], method=op["method"], path=op["path"],
                query=[p["name"] for p in op["params"]],
                body=[n for n in op["body"] or [] if n not in EXCLUDED],
                writecheck=[n for n in op["body"] or [] if n in EXCLUDED], body_required=op["body_required"],
                declared={str(code): {"schemas": list(r["schemas"]), "headers": list(r["headers"])}
                          for code, r in op["declared"].items()}))
        self.head = next(i for i, op in enumerate(self.doc.ops) if op["path"] == "/v1/copy" and op["method"] == "HEAD")
        self.get = next(i for i, op in enumerate(self.doc.ops) if op["path"] == "/v1/copy" and op["method"] == "GET")

    def check_coverage(self, table):
        target = Generated("test_coverage")
        target.d = self.doc
        known = (set(self.doc.schemas) - EXCLUDED) | set(self.doc.inline)
        def probe(**request):
            if request["cmd"] == "table":
                return {"ops": table}
            if request["cmd"] == "check":
                return {"known": request["schema"] in known}
            raise RuntimeError("CheckingError: unexpected synthetic probe request")
        target.probe = probe
        target.test_coverage()

    def test_canonical_empty_array_and_body_bearing_head_source_neighbour(self):
        self.check_coverage(self.table)
        changed = copy.deepcopy(self.source)
        response = changed["paths"]["/v1/copy"]["get"]["responses"]["400"]
        if "$ref" in response:
            response = changed["components"]["responses"][response["$ref"].split("/")[-1]]
        changed["paths"]["/v1/copy"]["head"]["responses"]["400"]["content"] = copy.deepcopy(response["content"])
        changed["paths"]["/v1/copy"]["head"]["responses"]["404"] = copy.deepcopy(
            changed["paths"]["/v1/copy"]["get"]["responses"]["404"])
        head = next(op for op in Doc(changed).ops if op["path"] == "/v1/copy" and op["method"] == "HEAD")
        self.assertTrue(head["declared"][400]["schemas"])
        self.assertIsNotNone(head["declared"][400]["media"])
        self.assertEqual(self.doc.ops[self.head]["declared"][400]["schemas"], [])

    def test_null_wrong_type_or_invented_schema_is_not_empty_source_absence(self):
        self.check_coverage(self.table)
        for value in (None, {}, "", 0, ["UnexpectedBody"]):
            actual = copy.deepcopy(self.table)
            actual[self.head]["declared"]["400"]["schemas"] = value
            with self.subTest(value=value), self.assertRaises(AssertionError):
                self.check_coverage(actual)

    def test_missing_or_extra_status_and_missing_schema_member_are_not_hidden(self):
        self.check_coverage(self.table)
        missing = copy.deepcopy(self.table)
        del missing[self.head]["declared"]["400"]
        extra = copy.deepcopy(self.table)
        extra[self.head]["declared"]["299"] = {"schemas": [], "headers": []}
        for value in (missing, extra):
            with self.assertRaises(AssertionError):
                self.check_coverage(value)
        malformed = copy.deepcopy(self.table)
        del malformed[self.head]["declared"]["400"]["schemas"]
        with self.assertRaises(KeyError):  # Incomplete service frame; not a semantic mutant kill.
            self.check_coverage(malformed)

    def test_body_bearing_source_schema_cannot_be_removed_or_null(self):
        self.check_coverage(self.table)
        self.assertTrue(self.table[self.get]["declared"]["200"]["schemas"])
        for value in ([], None):
            actual = copy.deepcopy(self.table)
            actual[self.get]["declared"]["200"]["schemas"] = value
            with self.subTest(value=value), self.assertRaises(AssertionError):
                self.check_coverage(actual)

    def test_bodyless_and_body_bearing_header_omissions_or_additions_are_red(self):
        self.check_coverage(self.table)
        for index, code in ((self.head, "405"), (self.get, "405"), (self.get, "200")):
            self.assertTrue(self.table[index]["declared"][code]["headers"])
            for value in (None, [], ["Unexpected-Header"]):
                actual = copy.deepcopy(self.table)
                actual[index]["declared"][code]["headers"] = value
                with self.subTest(index=index, code=code, value=value), self.assertRaises(AssertionError):
                    self.check_coverage(actual)
        unexpected = copy.deepcopy(self.table)
        unexpected[self.head]["declared"]["400"]["headers"] = ["Unexpected-Header"]
        with self.assertRaises(AssertionError):
            self.check_coverage(unexpected)


class Generated(DoorBase):
    def test_out_up_to_date(self):
        """Require exact fresh apidoor output with the current OpenAPI SHA header."""
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        for name in ("door.go", "runtime.go"):
            self.assertEqual((self.out / "go/apidoor" / name).read_bytes(), (OUT / "go/apidoor" / name).read_bytes(),
                             f"{name} is stale: run tools/normgen/gen_door.py")
        self.assertEqual((self.out / "go/go.mod").read_bytes(), (OUT / "go/go.mod").read_bytes())
        import hashlib
        self.assertIn(hashlib.sha256(self.text.encode()).hexdigest(), (OUT / "go/apidoor/door.go").read_text()[:400])

    def test_build_vet_fmt(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        go(["build", "./..."], OUT / "go")
        go(["vet", "./..."], OUT / "go")
        fmt = subprocess.run(["gofmt", "-l", "apidoor"], cwd=OUT / "go", capture_output=True, text=True).stdout
        self.assertEqual(fmt, "")

    def test_coverage(self):
        """Compare door operations, query, bodies, statuses, schemas and headers with independently parsed OpenAPI."""
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

    def test_no_content_table_and_body_header_boundaries(self):
        """Private table arrays preserve Source absence, body shape and declared headers."""
        actual = {row["op"]: row for row in self.probe(cmd="table")["ops"]}
        no_content = [(op, code, response) for op in self.d.ops for code, response in op["declared"].items()
                      if response["media"] is None]
        self.assertTrue(no_content, "actual Source must exercise a no-content declaration")
        for op, code, response in no_content:
            with self.subTest(op=op["op"], code=code):
                declaration = actual[op["op"]]["declared"][str(code)]
                self.assertIs(type(declaration["schemas"]), list)
                self.assertEqual(declaration["schemas"], [])
                self.assertEqual(sorted(declaration["headers"] or []), response["headers"])
                options, headers = source_required_probe_headers(response)
                nil = self.probe(cmd="answer", op=op["op"], code=code, no_body=True, **options)
                self.assertEqual(nil["resp"], {"code": code, "header": headers or None, "body": ""})
                body = self.probe(cmd="answer", op=op["op"], code=code, json="{}", **options)
                self.assertTrue("answer_error" in body or "encode_error" in body, body)
                if "Allow" in response["required_headers"]:
                    absent = self.probe(cmd="answer", op=op["op"], code=code, no_body=True,
                                        **dict(options, allow=False))
                    self.assertIn("encode_error", absent)
                elif "Allow" not in response["headers"]:
                    extra = self.probe(cmd="answer", op=op["op"], code=code, no_body=True,
                                       **dict(options, allow=True))
                    self.assertIn("encode_error", extra)
        stream = next(op for op in self.d.ops if op["path"] == "/v1/copy" and op["method"] == "GET")
        response = stream["declared"][200]
        self.assertTrue(actual[stream["op"]]["declared"]["200"]["schemas"])
        self.assertIsNotNone(response["media"])
        value = "first\nsecond é\n"
        options, _ = source_required_probe_headers(response)
        accepted = self.probe(cmd="answer", op=stream["op"], code=200, json=json.dumps(value), **options)
        self.assertEqual(base64.b64decode(accepted["resp"]["body"]), value.encode("utf-8"))

    def test_routes(self):
        """Test every method/path: foreign paths return404 with its schema; unsupported methods return405 when declared."""
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
        _, required = source_required_probe_headers(declared)
        if not declared["schemas"]:
            self.assertIsNone(declared["media"], where)
            self.assertEqual(resp["header"], required or None, where)
            self.assertEqual(base64.b64decode(resp["body"]), b"", where)
            return
        self.assertEqual(resp["header"], [["Content-Type", declared["media"]], *required], where)
        body = json.loads(base64.b64decode(resp["body"]))
        self.assertEqual(sum(self.valid(n, body) for n in declared["schemas"]), 1, where)

    def test_schema_checks(self):
        """Compare chk* to jsonschema on schema-shaped values and mutants."""
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
        """Every declared operation/status/schema must encode a value-equivalent, valid body in property order."""
        seen = 0
        for o in self.d.ops:
            for code, r in o["declared"].items():
                options, required = source_required_probe_headers(r)
                if not r["schemas"]:
                    self.assertIsNone(r["media"], f"{o['op']} {code}: bodyless Source response")
                    got = self.probe(cmd="answer", op=o["op"], code=code, no_body=True, **options)
                    self.assertIn("resp", got, f"{o['op']} {code}: {got}")
                    self.assertEqual(got["resp"], {"code": code, "header": required or None, "body": ""})
                    seen += 1
                for name in r["schemas"]:
                    vals = self.samples(name)
                    self.assertTrue(vals, f"no valid sample of {name}")
                    for value in vals:
                        hits = sum(self.valid(n, value) for n in r["schemas"])
                        text = json.dumps(value, ensure_ascii=False)
                        got = self.probe(cmd="answer", op=o["op"], code=code, json=text, **options)
                        where = f"{o['op']} {code} {name}: {text[:200]}"
                        if hits == 1 and "not representable" in got.get("answer_error", ""):
                            # Reject integers outside int64 or values inexact in binary64 number fields instead of truncating silently.
                            self.assertFalse(representable(value, exact_float=True), where)
                            continue
                        if hits != 1:
                            self.assertIn("answer_error", got, where)
                            continue
                        self.assertIn("resp", got, where)
                        resp = got["resp"]
                        raw = base64.b64decode(resp["body"])
                        self.assertEqual(resp["header"], [["Content-Type", r["media"]], *required], where)
                        if r["media"] == "application/json":
                            self.assertEqual(json.loads(raw), value, where)
                            self.assertTrue(ordered_ok(self.d, self.d.node(name),
                                                       json.loads(raw, object_pairs_hook=pairs_hook)), where)
                        else:
                            self.assertEqual(raw.decode("utf-8"), value, where)
                        retry = self.probe(cmd="answer", op=o["op"], code=code, json=text, **dict(options, retry=True))
                        if "Retry-After" in r["headers"]:
                            self.assertEqual(retry["resp"]["header"][-1], ["Retry-After", "1"], where)
                        else:
                            self.assertIn("encode_error", retry, where)
                        seen += 1
        self.assertGreater(seen, 100)

    def test_undeclared(self):
        """Encode must reject statuses and schemas not declared for the operation."""
        for o in self.d.ops:
            for other in self.d.ops:
                for code, r in other["declared"].items():
                    for name in r["schemas"]:
                        vals = self.samples(name, 2, small=True)
                        if not vals or sum(self.valid(n, vals[0]) for n in r["schemas"]) != 1:
                            continue
                        mine = o["declared"].get(code)
                        options, _ = source_required_probe_headers(mine) if mine else ({}, [])
                        got = self.probe(cmd="answer", op=o["op"], code=code, json=json.dumps(vals[0]),
                                         via_op=other["op"], via_code=code, **options)
                        if mine and name in mine["schemas"]:
                            self.assertIn("resp", got, f"{o['op']} {code} {name}")
                        else:
                            self.assertIn("encode_error", got, f"{o['op']} {code} {name}")

    def test_refuse(self):
        """Refuse selects the refusal schema matching kind+fields, otherwise refuses."""
        n = 0
        for o in self.d.ops:
            for code, r in o["declared"].items():
                if code < 400:
                    continue
                options, _ = source_required_probe_headers(r)
                for name in r["schemas"]:
                    for value in self.samples(name, 5, small=True):
                        fields = {k: v for k, v in value.items() if k not in ("kind", "error")}
                        got = self.probe(cmd="refuse", op=o["op"], code=code, kind=value["kind"], msg="m",
                                         fields=fields, **options)
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
        """Query parsing equals latin1 parse_qsl plus the parameter schema; check presence, repetition, UTF-8 then schema."""
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
        """Every acceptance1.1 response must be declared and match exactly one operation schema."""
        steps = 0
        columns = ("scenario", "step", "request", "expect")
        for _, row in tsv_input.read(SCEN, names=columns, positional=True, root=ROOT).rows:
            cells = [row[name] for name in columns]
            if not re.match(r"[A-Z]+ /", cells[2]) or not re.match(r"[0-9]{3}( |$)", cells[3]):
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
        """Decode request bodies like jsonschema and retain their input fields in the constructed value."""
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
    """Use integers within int64 and, with exact_float, exact binary64; these fit unconstrained Go integer/number fields."""
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
    """Smoke-test door kits and build_stub: build, manifest and a few daemon requests. This is not acceptance, which runs through the server runner."""

    @classmethod
    def setUpClass(cls):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
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
        for parts in (("door",), ("vectors", "door", "families")):
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
    """OpenAPI mutants must change generated output and door behavior."""

    @classmethod
    def setUpClass(cls):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
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
        """Mutations without probes must still change output."""
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

    def test_ref_alias(self):
        """Named ref aliases, with or without annotations, get their own chk<Name>; generated code builds and validation matches the target (Codex C3)."""
        def change(d):
            sch = d["components"]["schemas"]
            sch["AliasKey"] = {"$ref": "#/components/schemas/Key"}
            sch["AliasKey2"] = {"description": "an alias", "$ref": "#/components/schemas/AliasKey"}
        p = self.mutant(12, change)
        for name in ("AliasKey", "AliasKey2", "Key"):
            self.assertIsNone(p(cmd="check", schema=name, json='"acc/x"')["violation"], name)
            self.assertIsNotNone(p(cmd="check", schema=name, json='""')["violation"], name)
            self.assertIsNotNone(p(cmd="check", schema=name, json="7")["violation"], name)

    def test_ref_alias_of_object_refused(self):
        """Object/union aliases are unsupported: refuse generation rather than emitting invalid Go."""
        for k, target in enumerate(("Written", "Row")):
            doc = copy.deepcopy(self.doc)
            doc["components"]["schemas"]["Alias"] = {"$ref": f"#/components/schemas/{target}"}
            with self.assertRaises(gen_door.GenError, msg=target):
                gen_door.emit(doc, "mutant", "0" * 64, Path(self.tmp.name) / f"ra{k}" / "p01-1")

    def test_subset_refusals(self):
        """Unsupported constraints must refuse, never disappear silently."""
        cases = [
            lambda d: d["components"]["schemas"]["Version"].update(format="uint64"),
            lambda d: d["paths"].update({"/v1/x/{id}": d["paths"]["/v1/get"]}),
            lambda d: d["paths"]["/v1/get"]["get"]["parameters"][0].update({"in": "header"}),
            lambda d: d["paths"]["/v1/get"]["get"]["responses"].update({"default": {"description": "x"}}),
            lambda d: d["paths"]["/v1/get"]["get"]["parameters"][0].update(schema={"type": "integer"}),
            lambda d: d["components"]["schemas"]["Key"].update(pattern=r"^\w+$"),
            lambda d: d["paths"]["/v1/get"]["get"]["responses"].pop("404"),
            lambda d: d["paths"]["/v1/status"]["get"]["responses"]["503"]["headers"]["Retry-After"].update(schema={"type": "object"}),
            lambda d: d["components"]["schemas"].pop("Cmd"),
        ]
        for k, change in enumerate(cases):
            doc = copy.deepcopy(self.doc)
            change(doc)
            with self.assertRaises(gen_door.GenError, msg=f"case {k}"):
                gen_door.emit(doc, "mutant", "0" * 64, Path(self.tmp.name) / f"r{k}" / "p01-1")


Z21_COPY_OBSERVER = r'''package apidoor
import (
    "encoding/base64"
    "encoding/json"
    "os"
    "sort"
    "testing"
)
type z21Probe struct { ID, Kind, Method, Header string; Code int; Value any; Body any; NilBody, Allow, Retry bool; CL, TE *string }
type z21Row struct { ID string `json:"id"`; OK bool `json:"ok"`; Code int `json:"code"`; Body string `json:"body"`; Headers [][2]string `json:"headers"`; Error string `json:"error"` }
type z21Meta struct { Media string `json:"media"`; Schemas, Headers, Required []string }
func z21Op(method string) Op { for _,o:=range Operations {if o.Path=="/v1/copy" && o.Method==method{return o.Op}};return 0 }
func TestZ21CopyObserver(t *testing.T) {
    raw,err:=os.ReadFile("z21_input.json");if err!=nil{t.Fatal(err)}
    var probes []z21Probe
    if err=json.Unmarshal(raw,&probes);err!=nil{t.Fatal(err)}
    meta:=map[string]map[int]z21Meta{}
    for _,method:=range []string{"GET","HEAD"} {
        values:=map[int]z21Meta{}
        for code,s:=range responses[z21Op(method)] {
            schemas:=append([]string{},s.schemas...);headers:=append([]string{},s.headers...);required:=append([]string{},s.required...)
            sort.Strings(headers);sort.Strings(required)
            values[code]=z21Meta{s.media,schemas,headers,required}
        }
        meta[method]=values
    }
    rows:=make([]z21Row,0,len(probes))
    for _,p:=range probes {
        row:=z21Row{ID:p.ID,Headers:[][2]string{}}
        op:=z21Op(p.Method)
        if p.Kind=="header" {
            check:=responses[op][p.Code].headerChecks[p.Header]
            row.OK=check==nil || check(p.Value,"")==nil
        } else {
            var a Answer
            var err error
            if p.NilBody {a=Answer{Code:p.Code}} else {a,err=AnswerOf(op,p.Code,p.Body)}
            if err==nil {
                a.Allow=p.Allow;if p.Retry {seconds:=int64(1);a.RetryAfter=&seconds};a.ContentLength=p.CL;a.TransferEncoding=p.TE
                var response *Response
                response,err=Encode(op,a)
                if err==nil {row.OK=true;row.Code=response.Code;row.Body=base64.StdEncoding.EncodeToString(response.Body);row.Headers=append([][2]string{},response.Header...)}
            }
            if err!=nil {row.Error=err.Error()}
        }
        rows=append(rows,row)
    }
    frame:=struct{Version,Declared,Completed int; Meta map[string]map[int]z21Meta; Rows []z21Row}{1,len(probes),len(rows),meta,rows}
    f,err:=os.OpenFile("z21_observed.json",os.O_CREATE|os.O_EXCL|os.O_WRONLY,0600);if err!=nil{t.Fatal(err)}
    if err=json.NewEncoder(f).Encode(frame);err!=nil{t.Fatal(err)}
    if err=f.Close();err!=nil{t.Fatal(err)}
}
'''


def read_copy_door_frame(raw, ids):
    """Validate the whole private observation before any Source comparison."""
    from test_gen_machine import CheckingError
    if type(ids) is not list or not ids or any(type(i) is not str or not i for i in ids) or len(set(ids)) != len(ids):
        raise CheckingError("missing or ambiguous expected copy observation identities")
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise CheckingError("duplicate copy observation member")
            value[key] = item
        return value
    def bad_number(value):
        raise CheckingError("non-JSON observation number")
    try:
        raw.decode("utf-8", "strict").encode("utf-8", "strict")
        frame = json.loads(raw, object_pairs_hook=unique, parse_constant=bad_number)
        # Reject escaped lone surrogates in every parsed string, too.
        json.dumps(frame, ensure_ascii=False).encode("utf-8", "strict")
    except (ValueError, UnicodeError, TypeError, RecursionError) as exc:
        raise CheckingError("invalid copy observation JSON/UTF-8") from exc
    if (type(frame) is not dict or set(frame) != {"Version", "Declared", "Completed", "Meta", "Rows"} or
            type(frame["Version"]) is not int or frame["Version"] != 1 or
            any(type(frame[k]) is not int or frame[k] != len(ids) for k in ("Declared", "Completed")) or
            type(frame["Rows"]) is not list or len(frame["Rows"]) != len(ids) or
            type(frame["Meta"]) is not dict or set(frame["Meta"]) != {"GET", "HEAD"}):
        raise CheckingError("copy observation envelope is incomplete or has wrong identity")
    for expected, row in zip(ids, frame["Rows"]):
        if (type(row) is not dict or set(row) != {"id", "ok", "code", "body", "headers", "error"} or
                type(row["id"]) is not str or row["id"] != expected or type(row["ok"]) is not bool or
                type(row["code"]) is not int or row["code"] < 0 or type(row["body"]) is not str or
                type(row["error"]) is not str or type(row["headers"]) is not list or
                any(type(pair) is not list or len(pair) != 2 or any(type(x) is not str for x in pair)
                    for pair in row["headers"]) or len({p[0] for p in row["headers"]}) != len(row["headers"])):
            raise CheckingError("copy observation row has wrong shape/order/identity")
        try:
            base64.b64decode(row["body"], validate=True)
        except (ValueError, TypeError) as exc:
            raise CheckingError("copy observation body is not base64") from exc
    for values in frame["Meta"].values():
        if type(values) is not dict or not values:
            raise CheckingError("missing operation metadata")
        for code, value in values.items():
            if (not re.fullmatch(r"[1-5][0-9][0-9]", code) or type(value) is not dict or
                    set(value) != {"media", "Schemas", "Headers", "Required"} or type(value["media"]) is not str or
                    any(type(value[k]) is not list or any(type(x) is not str for x in value[k]) or
                        len(set(value[k])) != len(value[k]) for k in ("Schemas", "Headers", "Required"))):
                raise CheckingError("malformed operation metadata")
    return frame


def run_copy_door_observer(module, probes):
    from test_gen_machine import CheckingError, complete_go_tests
    pkg = module / "apidoor"
    try:
        (pkg / "z21_copy_test.go").write_text(Z21_COPY_OBSERVER, encoding="utf-8")
        (pkg / "z21_input.json").write_text(json.dumps(probes, ensure_ascii=True), encoding="utf-8")
        done = subprocess.run(["go", "test", "-count=1", "-json", "-run", "^TestZ21CopyObserver$", "./apidoor"],
                              cwd=module, env=GOENV, capture_output=True, timeout=120)
        observed = SimpleNamespace(returncode=done.returncode, stdout=done.stdout.decode("utf-8", "strict"),
                                   stderr=done.stderr.decode("utf-8", "strict"))
        if complete_go_tests(observed, ["TestZ21CopyObserver"], "normgen/p01-1/apidoor"):
            raise CheckingError("private observer failed before obtaining observations")
        return read_copy_door_frame((pkg / "z21_observed.json").read_bytes(), [p["ID"] for p in probes])
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise CheckingError("copy observer cannot produce a complete report") from exc


class Z21ProbeHeaderControls(unittest.TestCase):
    """Synthetic private-observer input projection; no producer or Source execution."""
    def test_optional_headers_keep_old_empty_arguments_and_required_constants_are_source_owned(self):
        response = {"required_headers": [], "header_schemas": {"Retry-After": {"const": 1}}}
        self.assertEqual(source_required_probe_headers(response), ({}, []))
        response = {"required_headers": ["Allow"], "header_schemas": {"Allow": {"type": "string", "const": "GET"}}}
        self.assertEqual(source_required_probe_headers(response), ({"allow": True}, [["Allow", "GET"]]))
        changed = copy.deepcopy(response)
        changed["header_schemas"]["Allow"]["const"] = "SOURCE-WITNESS"
        self.assertEqual(source_required_probe_headers(changed)[1], [["Allow", "SOURCE-WITNESS"]])

    def test_unknown_nonconstant_and_wrongly_typed_required_headers_are_checking_errors(self):
        from test_gen_machine import CheckingError
        for name, schema in (("Unknown", {"const": "x"}), ("Allow", {"type": "string"}),
                             ("Allow", {"const": True}), ("Retry-After", {"const": True})):
            with self.subTest(name=name, schema=schema), self.assertRaises(CheckingError):
                source_required_probe_headers({"required_headers": [name], "header_schemas": {name: schema}})


class Z21PrivateDoorprobe(unittest.TestCase):
    """Private recorder/library checks; no backend, HTTP server or generated implementation claim."""
    source_root = ROOT
    code_root = ROOT

    @classmethod
    def setUpClass(cls):
        from test_gen_core import z21_ready_p01
        from test_gen_machine import CheckingError
        cls.output = output_lesson.output_root()
        cls.output_receipt = os.environ.get(output_lesson.OUTPUT_RECEIPT_ENV)
        cls.ready = z21_ready_p01(cls.output, cls.source_root, cls.code_root,
                                 expected_manifest_sha256=cls.output_receipt)
        cls.doc = Doc(yaml.safe_load((cls.source_root / "Platform/01-store/spec/01-store.api.openapi.yaml").read_text()))
        cls.tmp = tempfile.TemporaryDirectory(prefix="z21-private-doorprobe-")
        cls.addClassCleanup(cls.tmp.cleanup)
        try:
            cls.probe = Probe(build_probe(cls.ready["p01-1"], cls.tmp.name))
        except (AssertionError, OSError, subprocess.SubprocessError) as exc:
            raise CheckingError("private doorprobe compile/start failed") from exc

    @classmethod
    def tearDownClass(cls):
        from test_gen_core import z21_ready_p01
        from test_gen_machine import CheckingError
        cls.probe.close()
        if cls.probe.proc.returncode != 0:
            raise CheckingError("private doorprobe did not finish normally")
        z21_ready_p01(cls.output, cls.source_root, cls.code_root, expected_manifest_sha256=cls.output_receipt)

    def test_complete_source_table_and_every_dispatch_method(self):
        actual = self.probe(cmd="table")["ops"]
        self.assertEqual([(o["op"], o["method"], o["path"]) for o in actual],
                         [(o["op"], o["method"], o["path"]) for o in self.doc.ops])
        for got, source in zip(actual, self.doc.ops):
            self.assertEqual(got["declared"], {str(c): {"schemas": r["schemas"] or None, "headers": r["headers"] or None}
                                             for c, r in source["declared"].items()})
            query = []
            for p in source["params"]:
                self.assertTrue(self.doc.validator(p["schema"]).is_valid("a"), "normal input does not satisfy Source")
                query.append(p["name"] + "=a")
            got = self.probe(cmd="dispatch", op=source["op"], query="&".join(query))
            self.assertEqual(got["method"], source["op"])
            self.assertIsNone(got["error"])
            self.assertEqual(got["query"], {p["name"]: base64.b64encode(b"a").decode() for p in source["params"]} or None)

    def test_copy_raw_string_header_schemas_required_allow_and_bodyless_head(self):
        source = {o["method"]: o for o in self.doc.ops if o["path"] == "/v1/copy"}
        self.assertEqual(set(source), {"GET", "HEAD"})
        get, head = source["GET"], source["HEAD"]
        raw = "one\né\n"
        for field, header, value in (("content_length", "Content-Length", str(len(raw.encode()))),
                                     ("transfer_encoding", "Transfer-Encoding", "CHUNKED")):
            self.assertTrue(self.doc.header_validator(get["op"], 200, header).is_valid(value))
            got = self.probe(cmd="answer", op=get["op"], code=200, json=json.dumps(raw), **{field: value})
            self.assertEqual(got["resp"], {"code": 200, "header": [["Content-Type", get["declared"][200]["media"]], [header, value]],
                                           "body": base64.b64encode(raw.encode()).decode()})
        for field, header, value in (("content_length", "Content-Length", "-1"),
                                     ("transfer_encoding", "Transfer-Encoding", "gzip")):
            self.assertFalse(self.doc.header_validator(get["op"], 200, header).is_valid(value))
            self.assertIn("encode_error", self.probe(cmd="answer", op=get["op"], code=200, json=json.dumps(raw), **{field: value}))
        fault_name = get["declared"][405]["schemas"][0]
        fault = {"kind": self.doc.node(fault_name)["properties"]["kind"]["const"], "error": "witness"}
        self.assertTrue(self.doc.validator(fault_name).is_valid(fault))
        options, required = source_required_probe_headers(get["declared"][405])
        got = self.probe(cmd="answer", op=get["op"], code=405, json=json.dumps(fault), **options)
        self.assertEqual(got["resp"]["header"], [["Content-Type", get["declared"][405]["media"]], *required])
        self.assertEqual(json.loads(base64.b64decode(got["resp"]["body"])), fault)
        self.assertIn("encode_error", self.probe(cmd="answer", op=get["op"], code=405, json=json.dumps(fault)))
        got = self.probe(cmd="refuse", op=get["op"], code=405, kind=fault["kind"], msg=fault["error"], **options)
        self.assertEqual(json.loads(base64.b64decode(got["resp"]["body"])), fault)
        self.assertEqual(got["resp"]["header"], [["Content-Type", get["declared"][405]["media"]], *required])
        for code, response in head["declared"].items():
            self.assertEqual(response["schemas"], [])
            options, required = source_required_probe_headers(response)
            got = self.probe(cmd="answer", op=head["op"], code=code, no_body=True, **options)
            self.assertEqual(got, {"resp": {"code": code, "header": required or None, "body": ""}, "schema": ""})
        self.assertIn("answer_error", self.probe(cmd="answer", op=head["op"], code=400, json=json.dumps(fault)))
        self.assertIn("encode_error", self.probe(cmd="answer", op=get["op"], code=200, no_body=True))


class Z21CopySource(unittest.TestCase):
    """Independent source projection. These Python controls execute no generated implementation."""

    source_root = ROOT

    def setUp(self):
        path = self.source_root / "Platform/01-store/spec/01-store.api.openapi.yaml"
        self.source = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.doc = Doc(self.source)

    def response(self, method, code):
        value = self.source["paths"]["/v1/copy"][method]["responses"][str(code)]
        if "$ref" in value:
            value = self.source["components"]["responses"][value["$ref"].split("/")[-1]]
        return value

    def copy_op(self, method):
        return next(op for op in self.doc.ops if op["path"] == "/v1/copy" and op["method"] == method.upper())

    def test_full_actual_header_projection_including_requiredness(self):
        self.assertEqual({m for m in self.source["paths"]["/v1/copy"]}, {"get", "head"})
        for method in ("get", "head"):
            op = self.copy_op(method)
            self.assertEqual(set(op["declared"]), {int(c) for c in self.source["paths"]["/v1/copy"][method]["responses"]})
            for code, actual in op["declared"].items():
                header = self.response(method, code).get("headers", {})
                with self.subTest(method=method, code=code):
                    self.assertEqual(actual["headers"], sorted(header))
                    self.assertEqual(actual["header_schemas"], {n: h["schema"] for n, h in header.items()})
                    self.assertEqual(actual["required_headers"], sorted(n for n, h in header.items() if h.get("required", False)))
        self.assertEqual(self.copy_op("get")["declared"][200]["required_headers"], [])

    def test_copy_stream_and_unsupported_head_keep_their_source_shapes(self):
        get = self.copy_op("get")["declared"][200]
        raw = self.response("get", 200)["content"]
        self.assertEqual(get["media"], next(iter(raw)))
        self.assertEqual(raw[get["media"]]["schema"]["type"], "string")
        self.assertEqual(len(get["schemas"]), 1)
        schema = self.doc.node(get["schemas"][0])
        self.assertEqual(schema, raw[get["media"]]["schema"])
        # The API scalar is opaque UTF-8/LF data, not one decoded JSON object or a copy-format proof.
        self.assertTrue(self.doc.validator(schema).is_valid('first\nsecond é\n'))
        self.assertFalse(self.doc.validator(schema).is_valid({"first": "second"}))
        for code, response in self.copy_op("head")["declared"].items():
            with self.subTest(head=code):
                self.assertNotIn("content", self.response("head", code))
                self.assertIsNone(response["media"])
                self.assertEqual(response["schemas"], [])
        self.assertNotIn(200, self.copy_op("head")["declared"])

    def test_typed_header_neighbours_use_actual_schema(self):
        op = self.copy_op("get")["op"]
        # These are typed schema values. HTTP field framing/CRLF rejection is a separate transport proof.
        cases = [(200, "Content-Length", ["0", "001", "123"], ["", "-1", "1.0", "1e3", "a", 1, True]),
                 (200, "Transfer-Encoding", ["chunked", "CHUNKED", "cHuNkEd"],
                  ["gzip", "chunked,gzip", "chunked ", 1, True]),
                 (405, "Allow", ["GET"], ["get", "HEAD", "GET, HEAD", 1, True]),
                 (503, "Retry-After", [1], [0, 2, 1.0, True, "1"])]
        for code, header, good, bad in cases:
            validator = self.doc.header_validator(op, code, header)
            for value in good:
                with self.subTest(code=code, header=header, good=value):
                    self.assertTrue(validator.is_valid(value))
            for value in bad:
                with self.subTest(code=code, header=header, bad=value):
                    self.assertFalse(validator.is_valid(value))

    def test_malformed_header_declarations_are_source_errors(self):
        for headers in (None, [], False, 0, "", {1: {"schema": {"type": "string"}}},
                        {"X": {"schema": None}}, {"X": {"schema": []}},
                        {"X": {"schema": {"type": "string"}, "required": 1}}):
            changed = copy.deepcopy(self.source)
            changed["paths"]["/v1/copy"]["get"]["responses"]["200"]["headers"] = headers
            with self.subTest(headers=headers), self.assertRaises(ValueError):
                Doc(changed)

    def test_shared_404_is_required_except_for_fully_bodyless_head(self):
        # Establish the physical source neighbour before rejecting owned copies.
        def build(doc, label):
            return gen_door.build_go(gen_door.Spec(doc, label), label, "0" * 64)
        build(copy.deepcopy(self.source), "actual source")
        missing = copy.deepcopy(self.source)
        del missing["paths"]["/v1/status"]["get"]["responses"]["404"]
        self.assertIn("405", missing["paths"]["/v1/status"]["get"]["responses"])
        with self.assertRaisesRegex(gen_door.GenError, "404"):
            build(missing, "non-HEAD without shared 404")
        body = copy.deepcopy(self.source)
        body["paths"]["/v1/copy"]["head"]["responses"]["400"]["content"] = {
            "application/json": {"schema": {"$ref": "#/components/schemas/BadRequestFault"}}}
        with self.assertRaisesRegex(gen_door.GenError, "404"):
            build(body, "body-bearing HEAD without shared 404")


class Z21CopyCompiled(unittest.TestCase):
    """Selected component readback; no HTTP server, source admission or storage-provider claim."""
    source_root = ROOT
    code_root = ROOT

    @classmethod
    def setUpClass(cls):
        from test_gen_core import z21_ready_p01
        cls.output = output_lesson.output_root()
        cls.output_receipt = os.environ.get(output_lesson.OUTPUT_RECEIPT_ENV)
        cls.ready = z21_ready_p01(cls.output, cls.source_root, cls.code_root,
                                 expected_manifest_sha256=cls.output_receipt)
        cls.doc = Doc(yaml.safe_load((cls.source_root / "Platform/01-store/spec/01-store.api.openapi.yaml").read_text()))
        cls.tmp = tempfile.TemporaryDirectory(prefix="z21-copy-door-")

    @classmethod
    def tearDownClass(cls):
        from test_gen_core import z21_ready_p01
        cls.tmp.cleanup()
        z21_ready_p01(cls.output, cls.source_root, cls.code_root, expected_manifest_sha256=cls.output_receipt)

    def module(self, name):
        target = Path(self.tmp.name) / name
        target.mkdir()
        shutil.copy(self.ready["p01-1"] / "go/go.mod", target / "go.mod")
        shutil.copytree(self.ready["p01-1"] / "go/apidoor", target / "apidoor")
        return target

    def probes(self):
        probes, expected = [], []
        def add(kind="encode", method="GET", code=200, ok=True, body=None, headers=None, **kw):
            identity = f"copy-{len(probes) + 1:03d}"
            probes.append(dict(ID=identity, Kind=kind, Method=method, Code=code, **kw))
            expected.append(dict(id=identity, ok=ok, code=code if kind == "encode" else 0, body=body, headers=headers))
        op = next(o for o in self.doc.ops if o["path"] == "/v1/copy" and o["method"] == "GET")["op"]
        for header, values in (("Content-Length", ["0", "001", "123", "", "-1", "1.2", 1, True]),
                               ("Transfer-Encoding", ["chunked", "CHUNKED", "cHuNkEd", "gzip", "chunked,gzip", 1, True])):
            validator = self.doc.header_validator(op, 200, header)
            for value in values:
                add(kind="header", Header=header, Value=value, ok=validator.is_valid(value))
        raw = "first\nsecond é\n"
        media = self.doc.op(op)["declared"][200]["media"]
        add(Body=raw, body=raw.encode(), headers={"Content-Type": media})
        add(Body={"first": "second"}, ok=False)
        for field, header, values in (("CL", "Content-Length", ["0", "001", "", "-1"]),
                                       ("TE", "Transfer-Encoding", ["CHUNKED", "chunked", "gzip"])):
            validator = self.doc.header_validator(op, 200, header)
            for value in values:
                add(Body=raw, **{field: value}, ok=validator.is_valid(value), body=raw.encode(),
                    headers={"Content-Type": media, header: value})
        fault = {"kind": "badrequest", "error": ""}
        for method in ("GET", "HEAD"):
            source_op = next(o for o in self.doc.ops if o["path"] == "/v1/copy" and o["method"] == method)
            required = source_op["declared"][405]["required_headers"]
            for allow in (False, True):
                add(method=method, code=405, Body=fault, NilBody=method == "HEAD", Allow=allow,
                    ok=allow or "Allow" not in required,
                    body=b"" if method == "HEAD" else json.dumps(fault, separators=(",", ":")).encode(),
                    headers=({} if method == "HEAD" else {"Content-Type": "application/json"}) |
                            ({"Allow": "GET"} if allow else {}))
        add(method="HEAD", code=400, NilBody=True, body=b"", headers={})
        add(method="HEAD", code=400, Body=fault, ok=False)
        for retry in (False, True):
            value = {"kind": "unavailable", "error": ""}
            add(code=503, Body=value, Retry=retry, body=json.dumps(value, separators=(",", ":")).encode(),
                headers={"Content-Type": "application/json"} | ({"Retry-After": "1"} if retry else {}))
        return probes, expected

    def differences(self, frame, expected):
        differences = []
        for method in ("GET", "HEAD"):
            op = next(o for o in self.doc.ops if o["path"] == "/v1/copy" and o["method"] == method)
            want = {str(code): {"media": r["media"] or "", "Schemas": r["schemas"], "Headers": r["headers"],
                                "Required": r["required_headers"]} for code, r in op["declared"].items()}
            if frame["Meta"][method] != want:
                differences.append("source-metadata-" + method)
        for actual, want in zip(frame["Rows"], expected):
            if actual["ok"] != want["ok"]:
                differences.append(want["id"] + "-acceptance")
            elif actual["ok"] and (actual["code"] != want["code"] or actual["error"]):
                differences.append(want["id"] + "-status-or-error")
            elif actual["ok"] and want["body"] is not None and (
                    base64.b64decode(actual["body"], validate=True) != want["body"] or
                    dict(actual["headers"]) != want["headers"]):
                differences.append(want["id"] + "-wire-bytes-or-headers")
        return differences

    def test_actual_response_metadata_headers_raw_stream_and_bodyless_head(self):
        probes, expected = self.probes()
        self.assertEqual(self.differences(run_copy_door_observer(self.module("normal"), probes), expected), [])

    def test_compiled_valid_mutants_require_complete_source_disagreements(self):
        probes, expected = self.probes()
        self.assertEqual(self.differences(run_copy_door_observer(self.module("mutant-baseline"), probes), expected), [])
        mutations = {
            "length-check-removed": ('"Content-Length": chkCopyGet200HeaderContentLength', '"Content-Length": nil'),
            "encoding-check-removed": ('"Transfer-Encoding": chkCopyGet200HeaderTransferEncoding', '"Transfer-Encoding": nil'),
            "allow-not-required": ('required: []string{"Allow"}', 'required: []string{}'),
            "copy-stream-json-quoted": ('func (x CopyGet200) appendJSON(b []byte) []byte { return append(b, x...) }',
                                         'func (x CopyGet200) appendJSON(b []byte) []byte { return appendString(b, string(x)) }'),
            "successful-status-replaced": ('return &Response{Code: a.Code, Header: header, Body: body}, nil',
                                             'return &Response{Code: 299, Header: header, Body: body}, nil'),
        }
        for name, (before, after) in mutations.items():
            with self.subTest(mutant=name):
                module = self.module(name)
                path = module / "apidoor/door.go"
                text = path.read_text()
                self.assertGreater(text.count(before), 0, "missing mutation anchor")
                path.write_text(text.replace(before, after), encoding="utf-8")
                self.assertTrue(self.differences(run_copy_door_observer(module, probes), expected), "surviving mutant " + name)

    def test_observer_compile_error_is_not_a_semantic_mismatch(self):
        from test_gen_machine import CheckingError
        module = self.module("compile-error")
        path = module / "apidoor/door.go"
        path.write_text(path.read_text() + "\nnot valid Go\n")
        with self.assertRaises(CheckingError):
            run_copy_door_observer(module, self.probes()[0])


class Z21CopyFrameControls(unittest.TestCase):
    def test_partial_extra_duplicate_type_and_utf8_are_checking_errors(self):
        from test_gen_machine import CheckingError
        normal = {"Version": 1, "Declared": 1, "Completed": 1,
                  "Meta": {m: {"400": {"media": "", "Schemas": [], "Headers": [], "Required": []}} for m in ("GET", "HEAD")},
                  "Rows": [{"id": "one", "ok": True, "code": 0, "body": "", "headers": [], "error": ""}]}
        encoded = json.dumps(normal).encode()
        self.assertEqual(read_copy_door_frame(encoded, ["one"]), normal)
        changes = [lambda f: f.update(Version=True), lambda f: f.update(Completed=0),
                   lambda f: f.update(Rows=[]), lambda f: f["Rows"].append(copy.deepcopy(f["Rows"][0])),
                   lambda f: f["Rows"][0].update(id="foreign"), lambda f: f["Rows"][0].update(ok=1),
                   lambda f: f["Rows"][0].update(body="???"), lambda f: f["Rows"][0].update(headers=[["x", "a"], ["x", "b"]]),
                   lambda f: f["Meta"]["GET"]["400"].update(Required=False)]
        for mutate in changes:
            changed = copy.deepcopy(normal); mutate(changed)
            with self.subTest(mutate=repr(changed)), self.assertRaises(CheckingError):
                read_copy_door_frame(json.dumps(changed).encode(), ["one"])
        for raw in (encoded + b"{}", b'{"Version":1,"Version":1}', b'"\xff"', b'{"x":NaN}', b'{"x":"\\ud800"}',
                    b"[" * 2000 + b"]" * 2000):
            with self.subTest(raw=raw), self.assertRaises(CheckingError):
                read_copy_door_frame(raw, ["one"])
        for ids in ([], ["one", "one"], [True], "one"):
            with self.subTest(ids=ids), self.assertRaises(CheckingError):
                read_copy_door_frame(encoded, ids)

    def test_missing_observer_destination_is_a_checking_error_before_execution(self):
        from test_gen_machine import CheckingError
        with tempfile.TemporaryDirectory(prefix="z21-observer-path-") as tmp:
            with self.assertRaises(CheckingError):
                run_copy_door_observer(Path(tmp) / "absent", [{"ID": "one"}])


if __name__ == "__main__":
    unittest.main()
