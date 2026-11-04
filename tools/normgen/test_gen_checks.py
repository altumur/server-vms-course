"""Проверка генератора tools/normgen/gen_checks.py по оракулу skills/lesson-spec/scripts/check_tables.py.

Запуск: /Users/murat/w2c/venv-spec-domain/bin/python tools/normgen/test_gen_checks.py [-v]
(нужен cel_expr_python оракула и go 1.22 в PATH; сети не нужно).

- сгенерированные модули в tools/normgen/out/p01-1 совпадают со свежей генерацией;
- на всех входах probes.tsv цепочка (n, исход каждого шага) и первый отказ (n, check, code, kind, fault) Go и Python
  совпадают с оракулом;
- то же на MUTANTS мутациях входов probes (удалить поле, сменить тип, пустые и длинные строки, большие числа, null,
  лишние поля, перестановка элементов списков, одиночные суррогаты, сокет);
- выражения вне подмножества — отказ генератора с номером строки.
Память: входы идут потоком по одному (оракул, модуль Python, один долгоживущий процесс Go построчно), CEL
оракула компилируется один раз на строку таблицы (check_tables.Runner); тело мутанта — не больше MAX_BODY;
max RSS процесса теста — не больше 1 ГБ (проверяется).
"""
import copy
import importlib.util
import json
import math
import os
import random
import resource
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "skills/lesson-spec/scripts"))

import check_tables  # noqa: E402 — оракул
import gen_checks  # noqa: E402

TABLE = ROOT / "Platform/01-store/data/write-checks.tsv"
PROBES = ROOT / "Platform/01-store/data/write-checks.probes.tsv"
OUT = HERE / "out/p01-1"
MUTANTS = int(os.environ.get("NORMGEN_MUTANTS", "12000"))
SEED = int(os.environ.get("NORMGEN_SEED", "20261104"))
SEM_INPUTS = int(os.environ.get("NORMGEN_SEM_INPUTS", "4000"))
MAX_BODY = 16 * 1024            # байт JSON тела мутанта: длинные строки есть (>1024 байт ключа), роста нет
MAX_RSS = 1 << 30               # процесс теста держит не больше 1 ГБ


# ---------------------------------------------------------------- входы

def load_probes():
    lims, allows, probes = {}, [], []
    lines = PROBES.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if m := re.fullmatch(r"#lim ([A-Z][A-Z0-9_]*) ([0-9]+)", line):
            lims[m[1]] = int(m[2])
        elif m := re.fullmatch(r"#allow (\S+) (\S+) ?(\S*)", line):
            allows.append((m[1], m[2], m[3]))
    for line in [x for x in lines if not x.startswith("#")][1:]:
        n, case, sock, text = line.split("\t")
        if case != "nopair":
            probes.append((f"probe n {n} {case}", sock, text))
    return lims, allows, probes


def dump(v):
    """JSON без потери вида числа: double всегда с . или e, ±inf — ±1e400 (так их читает обвязка Go)."""
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if type(v) is int:
        return str(v)
    if type(v) is float:
        if math.isinf(v):
            return "1e400" if v > 0 else "-1e400"
        assert v == v, "NaN is not JSON"
        return repr(v)
    if type(v) is str:
        return json.dumps(v)
    if type(v) is list:
        return "[" + ",".join(dump(x) for x in v) + "]"
    return "{" + ",".join(json.dumps(k) + ":" + dump(x) for k, x in v.items()) + "}"


def canon(v):
    """Значение Python (оракул, модуль Python) → сравнимый вид с видом числа."""
    if v is None:
        return ("null",)
    if type(v) is bool:
        return ("bool", v)
    if type(v) is int:
        return ("int", v)
    if type(v) is float:
        return ("double", v)
    if type(v) is str:
        return ("string", v)
    if type(v) is list:
        return ("list", tuple(canon(x) for x in v))
    if type(v) is dict:
        return ("map", tuple(sorted((k, canon(x)) for k, x in v.items())))
    raise TypeError(type(v))


def canon_go(v):
    """Значение с метками обвязки Go → тот же вид, что canon."""
    if type(v) is dict:
        if "$int" in v:
            return ("int", int(v["$int"]))
        if "$double" in v:
            return ("double", float(v["$double"]))
        return ("map", tuple(sorted((k, canon_go(x)) for k, x in v["$map"].items())))
    if type(v) is list:
        return ("list", tuple(canon_go(x) for x in v))
    return canon(v)


def norm_refusal(r, go=False):
    if r is None:
        return None
    fault = None
    if r["fault"] is not None:
        fault = canon_go({"$map": r["fault"]["$map"]}) if go else canon(r["fault"])
    return (r["n"], r["check"], r["code"], r["kind"], fault, bool(r["fault_error"]))


# ---------------------------------------------------------------- три исполнителя

class Oracle:
    def __init__(self, lims, allows, path=TABLE, form=True):
        table = check_tables.Table(path)
        if form:                                   # синтетическая таблица семантики формы (пределы-литералы) не держит
            assert not table.errors, table.errors
        table.errors = []
        self.runner = check_tables.Runner(table, lims, allows)
        assert not table.errors, table.errors

    def run(self, sock, body, lone):
        chain = self.runner.run(sock, body, lone)
        steps, hit = [], None
        for step in chain:
            row, status, value = step[:3]
            st = "error" if status != "ok" else ("true" if value is True else "false")
            steps.append((int(row["n"]), st))
            if st == "true" and hit is None:
                fault, fault_error = None, False
                if row["fault"]:
                    fs, fv = self.runner.eval(row, "fault", step[3])
                    if fs == "ok" and isinstance(fv, dict):
                        fault = canon(fv)
                    else:
                        fault_error = True
                hit = (int(row["n"]), row["check"], int(row["code"]), row["kind"], fault, fault_error)
        return steps, hit


def load_python(path):
    spec = importlib.util.spec_from_file_location("normgen_checks_p01_1", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PyRunner:
    def __init__(self, path, lims, allows):
        self.mod, self.lims = load_python(path), lims

        def allowed(sock, op, key):
            return any(s == sock and o in ("*", op) and key.startswith(prefix) for s, o, prefix in allows)

        self.fns = {"allowed": allowed}

    def run(self, sock, body, lone):
        hit = self.mod.check(copy.deepcopy(body), sock, lone, self.lims, self.fns)
        steps, chain_hit = self.mod.chain(copy.deepcopy(body), sock, lone, self.lims, self.fns)
        return [tuple(s) for s in steps], norm_refusal(hit), norm_refusal(chain_hit)


def build_go(out, workdir):
    """Собирает обвязку против сгенерированного модуля в out; → путь к исполняемому файлу."""
    hdir = Path(workdir) / "harness"
    hdir.mkdir()
    shutil.copy(HERE / "harness/main.go", hdir / "main.go")
    (hdir / "go.mod").write_text("module normgen/harness\n\ngo 1.22\n\nrequire normgen/p01-1 v0.0.0\n\n"
                                 f"replace normgen/p01-1 => {Path(out).resolve() / 'go'}\n", encoding="utf-8")
    exe = Path(workdir) / "harness.bin"
    env = dict(os.environ, GOPROXY="off", GOFLAGS="-mod=mod", GOWORK="off", GOTOOLCHAIN="local")
    done = subprocess.run(["go", "build", "-o", str(exe), "."], cwd=hdir, env=env, capture_output=True, text=True)
    if done.returncode:
        raise AssertionError(f"go build failed:\n{done.stderr}")
    vet = subprocess.run(["go", "vet", "./..."], cwd=Path(out) / "go", env=env, capture_output=True, text=True)
    if vet.returncode:
        raise AssertionError(f"go vet failed:\n{vet.stderr}")
    return exe


class GoProc:
    """Один долгоживущий процесс обвязки: вход — строка JSON, ответ читается сразу (ничего не копится)."""

    def __init__(self, exe, lims, allows):
        self.head = json.dumps({"lim": lims, "allow": allows})[1:-1]
        self.proc = subprocess.Popen([str(exe)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def run(self, sock, body, lone):
        line = "{" + self.head + ', "sock": ' + json.dumps(sock) + ', "lone": ' + json.dumps(lone) \
            + ', "body": ' + dump(body) + "}\n"
        self.proc.stdin.write(line)
        self.proc.stdin.flush()
        answer = self.proc.stdout.readline()
        if not answer:
            raise AssertionError(f"harness died (code {self.proc.poll()})")
        r = json.loads(answer)
        return [tuple(x) for x in r["chain"]], norm_refusal(r["check"], True), norm_refusal(r["chain_hit"], True)

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=30)
        self.proc.stdout.close()


# ---------------------------------------------------------------- мутации

FIELDS = ["op", "key", "items", "cas", "guard", "id", "not_after", "not_before", "writes", "guards", "index",
          "extra", "value", "f", "\ud800", "�"]
STRINGS = ["put", "delete", "batch", "floor", "get", "", "acc/a", "acc/b", "acc/g", "zzz/a", "zzz/g", "/a", "a/../b",
           "..", "acc/" + "x" * 1030, "x" * 1025, "x" * 1024, "0", "01", "7", "123", "12345678901234567890",
           "123456789012345678901", "\ud800", "a\ud800", "\udfff", "�", "é", "0\n", "ab\n", "ab", "X", "f" * 64,
           "f" * 65, "v", "vvvvvvvvv", "véé", "😀", "acc/😀"]
NUMBERS = [0, 1, -1, 5, 7, 2 ** 63 - 1, 2 ** 63, -2 ** 63, -2 ** 63 - 1, 2 ** 64, 10 ** 30, 0.0, -0.0, 0.5, 1.5,
           -0.5, 1e308, float("inf"), float("-inf"), 2.0 ** 63, 1e-300]
SOCKS = ["writer", "admin", "console", "domain", "reader", ""]


def rand_value(rng, depth=0):
    r = rng.random()
    if r < 0.12:
        return None
    if r < 0.2:
        return rng.random() < 0.5
    if r < 0.4:
        return rng.choice(NUMBERS)
    if r < 0.7 or depth > 2:
        return rng.choice(STRINGS)
    if r < 0.85:
        return [rand_value(rng, depth + 1) for _ in range(rng.randrange(4))]
    choices = [{"key": rng.choice(STRINGS), "index": rng.choice(["", "1", "01", 5])},
               {"op": rng.choice(["put", "delete", "get"]), "key": rng.choice(STRINGS),
                "items": {"f": rng.choice(["v", "vvvvvvvvv", 1])}},
               {"f": rng.choice(STRINGS)}, {}]
    if rng.random() < 0.5:
        return rng.choice(choices)
    return {rng.choice(FIELDS): rand_value(rng, depth + 1) for _ in range(rng.randrange(4))}


def nodes(value, path=()):
    yield path, value
    if type(value) is list:
        for k, x in enumerate(value):
            yield from nodes(x, path + (k,))
    elif type(value) is dict:
        for k, x in value.items():
            yield from nodes(x, path + (k,))


def put(root, path, new):
    if not path:
        return new
    parent = root
    for p in path[:-1]:
        parent = parent[p]
    parent[path[-1]] = new
    return root


def mutate_once(rng, body):
    path, node = rng.choice(list(nodes(body)))
    r = rng.random()
    if type(node) is dict and node and r < 0.25:
        del node[rng.choice(list(node))]
        return body
    if type(node) is dict and r < 0.4:
        node[rng.choice(FIELDS)] = rand_value(rng)
        return body
    if type(node) is list and node and r < 0.45:
        how = rng.randrange(5)
        if how == 0:
            rng.shuffle(node)
        elif how == 1:
            node.reverse()
        elif how == 2:
            node.append(copy.deepcopy(rng.choice(node)))
        elif how == 3:
            node.pop(rng.randrange(len(node)))
        else:
            node.insert(rng.randrange(len(node) + 1), rand_value(rng))
        return body
    if type(node) is str and r < 0.6:
        how = rng.randrange(7)
        new = {0: "", 1: (node or "x") * (1100 // max(len(node), 1) + 1), 2: "/" + node, 3: node + "/..", 4: node + "\n", 5: node + "\ud800",
               6: node.upper()}[how]
        return put(body, path, new)
    if type(node) in (int, float) and type(node) is not bool and r < 0.6:
        return put(body, path, rng.choice(NUMBERS))
    if rng.random() < 0.5:
        return put(body, path, rng.choice(STRINGS + NUMBERS + [None, True, False, [], {}]))
    return put(body, path, rand_value(rng))


def mutants(probes, count, seed):
    """Поток мутантов (генератор, ничего не копит); тело больше MAX_BODY байт JSON — мутация заново от входа."""
    rng = random.Random(seed)
    bases = [(sock, json.loads(text)) for _, sock, text in probes]
    k = 0
    while k < count:
        sock, body = rng.choice(bases)
        body = copy.deepcopy(body)
        for _ in range(rng.choice([1, 1, 2, 2, 3, 4])):
            body = mutate_once(rng, body)
        text = json.dumps(body)
        if len(text) > MAX_BODY:
            continue
        if rng.random() < 0.15:
            sock = rng.choice(SOCKS)
        yield f"mutant {k}", sock, text
        k += 1


# ---------------------------------------------------------------- тесты

class Trio(unittest.TestCase):
    """Оракул, модуль Python и обвязка Go над одной таблицей; compare сверяет цепочку и первый отказ."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="normgen-")
        cls.lims, allows, cls.probes = load_probes()
        cls.allows = [list(a) for a in allows]
        table = cls.table_path()
        cls.out = Path(cls.tmp.name) / "p01-1"
        gen_checks.generate(table, cls.out)
        cls.oracle = Oracle(cls.lims, allows, table, form=table == TABLE)
        cls.py = PyRunner(cls.out / "python/checks.py", cls.lims, allows)
        cls.go = GoProc(build_go(cls.out, cls.tmp.name), cls.lims, cls.allows)

    @classmethod
    def table_path(cls):
        return TABLE

    @classmethod
    def tearDownClass(cls):
        cls.go.close()
        cls.tmp.cleanup()

    def compare(self, decoded, label):
        """decoded: поток (имя, sock, body, lone) — по одному входу, ничего не копится;
        → ({n первого отказа: число входов}, {n: исходы}); расхождение — провал."""
        stats = {"python": 0, "go": 0}
        mismatches, hits, statuses = [], {}, {}
        total = 0
        for name, sock, body, lone in decoded:
            total += 1
            go_result = self.go.run(sock, body, lone)
            want_steps, want_hit = self.oracle.run(sock, body, lone)
            hits[want_hit[0] if want_hit else 0] = hits.get(want_hit[0] if want_hit else 0, 0) + 1
            for n, st in want_steps:
                statuses.setdefault(n, set()).add(st)
            for lang, (steps, hit, chain_hit) in (("python", self.py.run(sock, body, lone)), ("go", go_result)):
                if steps == want_steps and hit == want_hit and chain_hit == want_hit:
                    stats[lang] += 1
                elif len(mismatches) < 6:
                    diff = [(a, b) for a, b in zip(want_steps, steps) if a != b][:4]
                    mismatches.append(f"{lang} {name} sock={sock} body={dump(body)[:300]} lone={lone}\n"
                                      f"  oracle hit {want_hit}\n  {lang:6} hit {hit} / {chain_hit}\n"
                                      f"  steps (oracle, {lang}) differ: {diff}")
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
        print(f"\n{label}: python {stats['python']}/{total}, go {stats['go']}/{total}; first refusal by n: "
              + ", ".join(f"{n}:{c}" for n, c in sorted(hits.items())) + f"; max RSS {rss >> 20} MiB", file=sys.stderr)
        self.assertEqual(mismatches, [], "\n".join(mismatches))
        self.assertLess(rss, MAX_RSS, "the test process holds more than 1 GiB")
        return hits, statuses


def decode_all(inputs):
    for name, sock, text in inputs:
        body, lone = check_tables.decode(text)
        yield name, sock, body, lone


class GenChecks(Trio):
    def test_out_up_to_date(self):
        """tools/normgen/out/p01-1 — ровно то, что строит генератор сейчас."""
        def files(root):
            return sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts)

        fresh, kept = files(self.out), files(OUT)
        self.assertEqual(fresh, kept)
        for rel in fresh:
            self.assertEqual((self.out / rel).read_bytes(), (OUT / rel).read_bytes(),
                             f"{rel} is stale: run tools/normgen/gen_checks.py")

    def test_probes(self):
        """Все входы probes.tsv: Go и Python = оракул."""
        self.compare(decode_all(self.probes), "probes")

    def test_mutants(self):
        """MUTANTS мутаций входов probes: Go и Python = оракул; каждая строка таблицы — первый отказ хоть раз."""
        self.assertGreaterEqual(MUTANTS, 10000)
        hits, _ = self.compare(decode_all(mutants(self.probes, MUTANTS, SEED)), f"mutants (seed {SEED})")
        missing = [row["n"] for row in gen_checks.Table(TABLE.read_text(encoding="utf-8")).rows
                   if row["n"] not in hits]
        self.assertEqual(missing, [], "rows never hit first by mutants")


# Выражения всего подмножества, не только ветви, достижимые в таблице (её охранные порядки прячут, например,
# «ошибка || true», size() строки, int против double у 2^63, when не bool). Каждое — строка op * синтетической таблицы.
SEMANTICS = [
    "body.a || true", "true || body.a", "body.a || false", "false || body.a", "body.a && false", "false && body.a",
    "body.a && true", "!body.a", "(body.a || body.b) && (body.b || body.a)", "!(body.a in body.b) || body.c",
    "body.a == body.b", "body.a != body.b", "body.a < body.b", "body.a <= body.b", "body.a > body.b",
    "body.a >= body.b", "body.a in body.b", "body.a in [\"put\", 1, 1.5, null, [1], {\"k\": 1}]",
    "body.a == [1, \"x\"]", "body.a == {\"k\": 1}", "[body.a, body.b] == [body.b, body.a]",
    "{\"k\": body.a}.k == body.b", "body.a == 9223372036854775807", "body.a < 9.3e18", "body.a == 0.0",
    "body.a > lim.BATCH_WRITES", "has(body.a.k)", "has(body.a) && has(body.b)", "body.a.k == 1",
    "body.a[body.b] == 1", "body.a[0] == body.b", "body.a[0][0] == 1", "size(body.a) > 2",
    "size(body.a) == size(body.b)", "string(body.a) == \"1\"", "string(body.a) == body.b",
    "string(body.a).startsWith(\"1\")", "body.a + body.b == body.c", "(body.a + \"x\").startsWith(\"ac\")",
    "body.a ? body.b : body.c", "size(body.a) == 0 ? body.b : body.c", "(body.a ? true : false) == body.b",
    "type(body.a) == type(body.b)", "type(body.a) == map || type(body.a) == list",
    "type(body.a) == int || type(body.a) == double || type(body.a) == null_type || type(body.a) == bool",
    "type(body.a) == string && type(type(body.a)) == type", "body.a.matches(\"^[0-9a-f]{1,3}$\")",
    "body.a.matches(\"^(|0|[1-9][0-9]{0,19})$\")", "body.a.matches(\"c.\")", "body.a.startsWith(body.b)",
    "body.a.exists(x, x == body.b)", "body.a.exists(x, x)", "body.a.exists(x, x.k)",
    "body.a.exists(i, x, i == 1 || x == 1)", "body.a.exists(i, x, body.a.exists(j, y, i < j && x == y))",
    "body.a.exists(k, v, k == \"k\" && v == body.b)", "body.a.exists(x, x == 1) || body.b.exists(x, x == 1)",
    "body.a.exists(x, body.b.exists(x, x == 1))", "key_ok(body.a)", "weight(body.a) > 3", "finite(body.a)",
    "allowed(sock, body.a, body.b)", "body.a", "lone.exists(p, p.startsWith(\"/a\"))",
    "\"/a\" in lone || sock == \"admin\"", "size(lone) > 0 && lone[0] == \"/a\"",
]
SEM_VALUES = [None, True, False, 0, 1, -1, 2, 1.0, 1.5, -0.0, 2 ** 63 - 1, 2.0 ** 63, 9.2e18, float("inf"),
              "", "1", "1.5", "1e+20", "x", "ac", "acc/a", "c\n", "0\n", "007", "abc", "ABC", "é😀", "\ud800", "/a",
              "a/../b", "x" * 1100, [], [1], [1.0], [1, "x"], [1, 2, 1], [[1]], ["k"], [{"k": 1}, {"k": 1.0}],
              [True, 2], [2, True], [False, "x"], {}, {"k": 1}, {"k": 1.0}, {"k": "v"}, {"k": True},
              {"k": "vvvv", "j": "w"}, {"k": [1]}, {"k": 1, "j": 1}]


def semantics_inputs(count, seed):
    rng = random.Random(seed)
    for k in range(count):
        body = {}
        for name in ("a", "b", "c"):
            if rng.random() < 0.9:
                body[name] = rng.choice(SEM_VALUES) if rng.random() < 0.75 else rand_value(rng)
        text = json.dumps(body)
        decoded, lone = check_tables.decode(text)
        lone = sorted(set(lone + rng.sample(["/a", "/a/b", "/b", "/ab"], rng.randrange(3))))
        yield f"semantics {k}", rng.choice(SOCKS), decoded, lone


class SubsetSemantics(Trio):
    """Синтетическая таблица из SEMANTICS (шапка — таблицы P/01.1): Go и Python = оракул на случайных телах."""

    @classmethod
    def table_path(cls):
        head = [line for line in TABLE.read_text(encoding="utf-8").splitlines() if line.startswith("#")]
        rows = ["\t".join(gen_checks.COLUMNS)]
        rows += [f"{k}\t*\t\t\tsem_{chr(97 + k // 26)}{chr(97 + k % 26)}\t{expr}\t400\tbadrequest\t\tsemantics"
                 for k, expr in enumerate(SEMANTICS, 1)]
        path = Path(cls.tmp.name) / "semantics-checks.tsv"
        path.write_text("\n".join(head + rows) + "\n", encoding="utf-8")
        return path

    def test_semantics(self):
        _, statuses = self.compare(semantics_inputs(SEM_INPUTS, SEED), f"subset semantics ({len(SEMANTICS)} rows)")
        # Постоянны по построению: true || x, x || true — true; false && x, x && false — false.
        constant = {SEMANTICS.index(e) + 1 for e in ("body.a || true", "true || body.a", "body.a && false",
                                                    "false && body.a")}
        flat = [n for n in range(1, len(SEMANTICS) + 1) if len(statuses.get(n, ())) < 2 and n not in constant]
        self.assertEqual(flat, [], "rows with a single outcome over all inputs: the inputs do not exercise them")


class OutOfSubset(unittest.TestCase):
    """Выражение вне подмножества — отказ генератора с номером строки."""
    CASES = [
        ("when", "body.items.all(f, true)", "method all"),
        ("when", "int(body.key) > 0", "function int"),
        ("when", "size(body.key) - 1 > 0", "operator -"),
        ("when", "size(body.key) * 2 > 0", "operator *"),
        ("when", "size(body.key) % 2 == 0", "operator %"),
        ("when", "-size(body.key) < 0", "unary -"),
        ("when", "body.key.endsWith(\"a\")", "method endsWith"),
        ("when", "body.key.size() > 0", "method size"),
        ("when", "body.key.matches(sock)", "string literal pattern"),
        ("when", "body.key.matches(\"\\\\d+\")", "regex escape"),
        ("when", "body.key.matches(\"(?i)a\")", "group flags"),
        ("when", "undeclared(body.key)", "function undeclared"),
        ("when", "q == 1", "identifier q"),
        ("when", "size(body.key) > lim.NOPE", "lim.NOPE"),
        ("when", "body.x == 1u", "uint literal"),
        ("when", "body.x == b\"a\"", "string prefix"),
        ("when", "has(body)", "has() takes"),
        ("when", "body.writes.map(w, w.key) == []", "method map"),
        ("when", "body.writes.exists_one(w, true)", "method exists_one"),
        ("when", "body.writes.exists(1, true)", "exists() takes"),
        ("when", "body.key == \"a\\x41\"", "escape \\x"),
        ("when", "body.key == 99999999999999999999", "int64 range"),
        ("when", "body.key in [1, 2", "expected"),
        ("when", "body.key == 'a' ;", "unexpected character"),
        ("when", "key_ok(body.key, 1)", "takes 1 arguments"),
        ("fault", "{\"a\": 1, \"a\": 2}", "duplicate map key"),
        ("fault", "{1: body.key}", "string literals"),
        ("fault", "[body.key]", "map literal"),
    ]

    def test_refusals(self):
        text = TABLE.read_text(encoding="utf-8")
        lines = text.splitlines()
        k = next(i for i, line in enumerate(lines) if line.startswith("5\t"))
        for column, expr, fragment in self.CASES:
            with self.subTest(expr=expr):
                cells = lines[k].split("\t")
                cells[gen_checks.COLUMNS.index(column)] = expr
                bad = "\n".join(lines[:k] + ["\t".join(cells)] + lines[k + 1:]) + "\n"
                with self.assertRaises(gen_checks.GenError) as caught:
                    gen_checks.build(gen_checks.Table(bad, "bad.tsv"))
                self.assertIn("n 5", str(caught.exception))
                self.assertIn(fragment, str(caught.exception))

    def test_table_builds(self):
        go_src, py_src = gen_checks.build(gen_checks.Table(TABLE.read_text(encoding="utf-8"), TABLE.name))
        self.assertIn("func Check(in Input) *Refusal", go_src)
        self.assertIn("def check(body, sock, lone, lim, fns=None):", py_src)


if __name__ == "__main__":
    unittest.main()
