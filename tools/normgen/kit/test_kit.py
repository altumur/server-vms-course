"""Проверка пакета Б P/01 (ADR-0083 доп. (86) п. 2): собранный build_kit.py пакет против оракула check_tables.

Запуск: /Users/murat/w2c/venv-spec-domain/bin/python tools/normgen/kit/test_kit.py [-v]
(нужны cel_expr_python оракула и go 1.22 в PATH; сети не нужно).

- build_kit.py собирает пакет в пустой каталог; go build, go vet, gofmt — в пустом модуле; манифест сходится с файлами;
- все входы write-checks.probes.tsv (кроме nopair) сырыми байтами → writecheck даёт тот же первый отказ, тело и lone,
  что оракул (check_tables.decode и таблица на cel-expr-python);
- NORMGEN_KIT_MUTANTS мутаций входов (мутатор tools/normgen/test_gen_checks.py), текст — строгим JSON со случайными
  пробелами и UTF-8 то сырым, то экранированным — тоже как оракул;
- векторы JSON урока (Platform/01-store/vectors/jcs/canonical_json.tsv, колонка raw) разбираются, как у оракула;
- отрицательные случаи Н2.1: повтор имени (и вложенный), BOM, NaN, Infinity, не UTF-8, глубина 128 и 129, синтаксис
  RFC 8259; одиночный суррогат в key, items, guard.key, writes, guards и в лишнем поле; числа на границе int64 и binary64;
- память: max RSS теста и дочерних процессов — не больше 1 ГБ (входы идут потоком, обвязка Go — один процесс).
"""
import base64
import json
import math
import os
import random
import resource
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
NORMGEN = HERE.parent
ROOT = NORMGEN.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(NORMGEN))
sys.path.insert(0, str(ROOT / "skills/lesson-spec/scripts"))

import build_kit  # noqa: E402
import check_tables  # noqa: E402 — оракул
import test_gen_checks as tg  # noqa: E402 — входы проб, мутатор, оракул на таблице

MODULE = "example.com/w2c/store"
JCS = ROOT / "Platform/01-store/vectors/jcs/canonical_json.tsv"
MUTANTS = int(os.environ.get("NORMGEN_KIT_MUTANTS", "3000"))
SEED = int(os.environ.get("NORMGEN_SEED", "20261104"))
MAX_RSS = 1 << 30
GOENV = dict(os.environ, GOPROXY="off", GOFLAGS="-mod=mod", GOWORK="off", GOTOOLCHAIN="local")


def canon(v):
    """Значение Python → сравнимый вид: вид числа и знак нуля различаются."""
    if v is None or type(v) is bool or type(v) is str:
        return (type(v).__name__, v)
    if type(v) is int:
        return ("int", v)
    if type(v) is float:
        return ("double", v, math.copysign(1.0, v))
    if type(v) is list:
        return ("list", tuple(canon(x) for x in v))
    return ("map", tuple(sorted((k, canon(x)) for k, x in v.items())))


def untag(v):
    """Значение обвязки с метками → значение Python."""
    if type(v) is dict:
        if "$int" in v:
            return int(v["$int"])
        if "$double" in v:
            return float(v["$double"])
        return {k: untag(x) for k, x in v["$map"].items()}
    if type(v) is list:
        return [untag(x) for x in v]
    return v


def has_surrogate(s):
    return any(0xD800 <= ord(c) <= 0xDFFF for c in s)


def strict_text(v, rng):
    """Значение Python → строгий JSON: ±inf — ±1e400, строки то экранированы, то сырым UTF-8, пробелы случайны."""
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
        return repr(v)
    if type(v) is str:
        return json.dumps(v, ensure_ascii=has_surrogate(v) or rng.random() < 0.5)
    comma = rng.choice([",", ", ", ",\n\t", " ,\r\n"])
    colon = rng.choice([":", ": ", " :\t"])
    if type(v) is list:
        return "[" + comma.join(strict_text(x, rng) for x in v) + "]"
    return "{" + comma.join(json.dumps(k) + colon + strict_text(x, rng) for k, x in v.items()) + "}"


class KitProc:
    """Один долгоживущий процесс обвязки kitprobe: вход — строка JSON, ответ читается сразу (ничего не копится)."""

    def __init__(self, exe, lims, allows):
        self.head = json.dumps({"lim": lims, "allow": allows})[1:-1]
        self.proc = subprocess.Popen([str(exe)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def run(self, sock, raw):
        line = "{" + self.head + ', "sock": ' + json.dumps(sock) + ', "body": "' \
            + base64.b64encode(raw).decode("ascii") + '"}\n'
        self.proc.stdin.write(line)
        self.proc.stdin.flush()
        answer = self.proc.stdout.readline()
        if not answer:
            raise AssertionError(f"kitprobe died (code {self.proc.poll()})")
        return json.loads(answer)

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=30)
        self.proc.stdout.close()


def go(args, cwd):
    done = subprocess.run(["go", *args], cwd=cwd, env=GOENV, capture_output=True, text=True)
    if done.returncode:
        raise AssertionError(f"go {' '.join(args)} failed:\n{done.stdout}{done.stderr}")
    return done.stdout


class Kit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="normgen-kit-")
        cls.dst = Path(cls.tmp.name) / "work"
        cls.manifest = build_kit.build(cls.dst, MODULE)
        cls.store = cls.dst / "01-store"
        (cls.store / "go.mod").write_text(f"module {MODULE}\n\ngo 1.22\n", encoding="utf-8")
        go(["build", "./..."], cls.store)
        go(["vet", "./..."], cls.store)
        cls.gofmt = subprocess.run(["gofmt", "-l", "internal"], cwd=cls.store, capture_output=True, text=True).stdout
        probe = cls.store / "cmd/kitprobe"
        probe.mkdir(parents=True)
        src = (HERE / "harness/main.go").read_text(encoding="utf-8")
        (probe / "main.go").write_text(src.replace('"kitmodule/internal/', f'"{MODULE}/internal/'), encoding="utf-8")
        exe = Path(cls.tmp.name) / "kitprobe.bin"
        go(["build", "-o", str(exe), "./cmd/kitprobe"], cls.store)
        cls.lims, allows, cls.probes = tg.load_probes()
        cls.allows = [list(a) for a in allows]
        cls.oracle = tg.Oracle(cls.lims, allows)
        cls.kit = KitProc(exe, cls.lims, cls.allows)

    @classmethod
    def tearDownClass(cls):
        cls.kit.close()
        cls.tmp.cleanup()
        own = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        kids = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        scale = 1 if sys.platform == "darwin" else 1024
        print(f"\nmax RSS: test {own * scale >> 20} MiB, children {kids * scale >> 20} MiB", file=sys.stderr)
        if max(own, kids) * scale >= MAX_RSS:
            raise AssertionError("a process holds more than 1 GiB")

    # ------------------------------------------------------------ помощники

    def oracle_hit(self, sock, text):
        body, lone = check_tables.decode(text)
        _, hit = self.oracle.run(sock, body, lone)
        return body, lone, hit

    def got(self, sock, raw):
        r = self.kit.run(sock, raw)
        ref = r["refusal"]
        hit = None
        if ref is not None:
            fault = None
            if ref["fault"] is not None:
                fault = tg.canon_go({"$map": ref["fault"]["$map"]})
            hit = (ref["n"], ref["check"], ref["code"], ref["kind"], fault, ref["reason"].startswith("fault:"))
        return r, hit

    def same_as_oracle(self, sock, text, raw=None):
        """Сырые байты (по умолчанию UTF-8 текста) → тот же отказ, тело и lone, что у оракула; → ответ обвязки."""
        raw = text.encode("utf-8") if raw is None else raw
        body, lone, want = self.oracle_hit(sock, text)
        r, hit = self.got(sock, raw)
        where = f"sock={sock} body={text[:300]!r}"
        self.assertEqual(hit, want, where)
        self.assertEqual(canon(untag(r["value"])), canon(body), where)
        self.assertEqual(r["lone"], lone, where)
        return r

    def refused(self, raw, reason=None, sock="writer"):
        r, hit = self.got(sock, raw)
        self.assertIsNotNone(hit, raw[:200])
        self.assertEqual(hit[:4], (0, "json", 400, "badrequest"), raw[:200])
        self.assertIsNone(r["value"], raw[:200])
        if reason:
            self.assertEqual(r["refusal"]["reason"], reason, raw[:200])

    def outcome(self, raw, n, kind=None, lone=None, sock="writer"):
        r, hit = self.got(sock, raw)
        where = raw[:200]
        if n == 0:
            self.assertIsNone(hit, where)
        else:
            self.assertIsNotNone(hit, where)
            self.assertEqual(hit[0], n, where)
            if kind:
                self.assertEqual(hit[3], kind, where)
        if lone is not None:
            self.assertEqual(r["lone"], lone, where)
        return r

    # ------------------------------------------------------------ сборка

    def test_build(self):
        """Пакет собран в пустом модуле (go build, go vet — в setUpClass), gofmt чист, манифест сходится с файлами."""
        self.assertEqual(self.gofmt, "", f"gofmt -l: {self.gofmt}")
        m = json.loads((self.dst / "kit.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["module"], MODULE)
        self.assertEqual(m["table"]["sha256"], build_kit.sha256(build_kit.TABLE.read_bytes()))
        paths = sorted(f["path"] for f in m["files"])
        on_disk = sorted(str(p.relative_to(self.dst)) for p in (self.store / "internal").rglob("*") if p.is_file())
        self.assertEqual(paths, on_disk)
        for f in m["files"]:
            data = (self.dst / f["path"]).read_bytes()
            self.assertEqual(f["sha256"], build_kit.sha256(data), f["path"])
            self.assertEqual(f["lines"], build_kit.lines(data), f["path"])
            self.assertIn(f["origin"], ("generated", "handwritten"))
            self.assertNotIn(b"kitmodule", data, f["path"])
        self.assertEqual(m["doc"]["sha256"], build_kit.sha256((self.dst / "KIT.md").read_bytes()))
        self.assertEqual(sum(m["lines"].values()), sum(f["lines"] for f in m["files"]))
        self.assertEqual(sum(m["lines_by_component"].values()), sum(f["lines"] for f in m["files"]))
        self.assertEqual(sorted(m["lines_by_component"]), ["kit", "normgen"])
        self.assertIn(f"{MODULE}/internal/writecheck", (self.dst / "KIT.md").read_text(encoding="utf-8"))

    def test_limits_match_table(self):
        """writecheck.Limits — ровно имена #lim таблицы."""
        table = check_tables.Table(tg.TABLE)
        src = (HERE / "go/writecheck/writecheck.go").read_text(encoding="utf-8")
        line = next(x for x in src.splitlines() if x.startswith("var Limits = []string{"))
        names = json.loads("[" + line.split("{", 1)[1].rsplit("}", 1)[0] + "]")
        self.assertEqual(sorted(names), sorted(table.lims))

    def test_build_refuses_bad_module(self):
        with tempfile.TemporaryDirectory() as d:
            for bad in ("", "a//b", "a/", "a b", "/a"):
                with self.assertRaises(build_kit.KitError):
                    build_kit.build(d, bad)

    # ------------------------------------------------------------ пробы, мутанты, векторы

    def test_probes(self):
        """Все входы probes.tsv, кроме nopair, сырыми байтами: как оракул."""
        for name, sock, text in self.probes:
            with self.subTest(name):
                self.same_as_oracle(sock, text)
        print(f"\nprobes: {len(self.probes)}", file=sys.stderr)

    def test_mutants(self):
        """Мутанты входов probes строгим JSON: как оракул; хоть раз — каждая строка таблицы первым отказом."""
        rng = random.Random(SEED)
        seen, total = set(), 0
        for name, sock, text in tg.mutants(self.probes, MUTANTS, SEED):
            strict = strict_text(json.loads(text), rng)
            r = self.same_as_oracle(sock, strict)
            seen.add(r["refusal"]["n"] if r["refusal"] else 0)
            total += 1
        print(f"\nmutants: {total}, first refusals by n: {sorted(seen)}", file=sys.stderr)
        self.assertEqual(total, MUTANTS)

    def test_jcs_vectors(self):
        """Векторы JSON урока (jcs, колонка raw): разбираются, тело как у оракула."""
        count = 0
        for line in JCS.read_text(encoding="utf-8").split("\n"):        # не splitlines: в ячейке есть U+2028 и т. п.
            if not line or line.startswith("#"):
                continue
            raw = line.split("\t")[0]
            r = self.same_as_oracle("writer", raw)
            self.assertFalse(r["refusal"] and r["refusal"]["n"] == 0, raw)
            count += 1
        self.assertGreater(count, 10)
        print(f"\njcs vectors: {count}", file=sys.stderr)

    # ------------------------------------------------------------ Н2.1: отказы разбора

    PUT = b'{"op":"put","key":"acc/a","items":{}'

    def test_repeated_names(self):
        self.refused(b'{"op":"put","op":"put","key":"acc/a","items":{}}', "duplicate_name")
        self.refused(b'{"op":"put","key":"acc/a","items":{"n":"1","n":"2"}}', "duplicate_name")
        self.refused(self.PUT + b',"x":[1,{"a":1,"b":{"c":1,"d":[{"e":0,"e":0}]}}]}', "duplicate_name")
        self.refused(self.PUT + b',"a":1,"\\u0061":2}', "duplicate_name")
        self.refused(self.PUT + b',"\\ud800":1,"\\ud800":2}', "duplicate_name")
        self.refused(self.PUT + b',"\xc3\xa9":1,"\\u00e9":2}', "duplicate_name")
        # Разные имена RFC 8259, совпавшие после U+FFFD, — не повтор (как оракул); "a" и "A" — разные.
        self.same_as_oracle("writer", '{"op":"put","key":"acc/a","items":{},"\\ud800":1,"\\udbff":2,"\ufffd":3}')
        self.same_as_oracle("writer", '{"op":"put","key":"acc/a","items":{},"a":1,"A":2}')
        # Одно имя в разных объектах — не повтор.
        self.same_as_oracle("writer", '{"op":"put","key":"acc/a","items":{"key":"v"},"x":{"key":1}}')

    def test_bom_nan_infinity(self):
        self.refused(b"\xef\xbb\xbf" + self.PUT + b"}", "bom")
        self.refused(b" \xef\xbb\xbf" + self.PUT + b"}")
        self.refused(self.PUT + b',"x":NaN}', "nan_or_infinity")
        self.refused(self.PUT + b',"x":Infinity}', "nan_or_infinity")
        self.refused(self.PUT + b',"x":-Infinity}', "nan_or_infinity")
        self.refused(self.PUT + b',"x":[1,NaN]}', "nan_or_infinity")
        self.refused(b'{"op":"put","key":"acc/a","items":{},"not_after":Infinity}', "nan_or_infinity")
        # BOM внутри строки — обычный символ U+FEFF.
        self.same_as_oracle("writer", '{"op":"put","key":"acc/a","items":{"f":"\ufeff"}}')

    def test_not_utf8(self):
        for bad in (b"\xff", b"\xc0\xaf", b"\xed\xa0\x80", b"\xed\xbf\xbf", b"\xf4\x90\x80\x80", b"\xe2\x82",
                    b"\x80", b"\xf8\x88\x80\x80\x80"):
            with self.subTest(bad=bad):
                self.refused(self.PUT + b',"x":"a' + bad + b'"}', "utf8")
                self.refused(self.PUT + b',"' + bad + b'":1}', "utf8")
                self.refused(b'{"op":"put","key":"acc/' + bad + b'","items":{}}', "utf8")
        self.refused(self.PUT + b"}\xe2\x82", "utf8")
        # U+FFFF и U+10FFFF — UTF-8 и JSON (не символы, но RFC 8259 их допускает).
        self.same_as_oracle("writer", '{"op":"put","key":"acc/a","items":{"f":"\uffff\U0010ffff"}}')

    def test_depth(self):
        def arrays(k):
            return b"[" * k + b"]" * k

        def objects(k):
            return b'{"a":' * (k - 1) + b"{}" + b"}" * (k - 1)

        # Корень — 1: лишнее поле с 127 вложенными массивами — глубина 128.
        self.outcome(self.PUT + b',"x":' + arrays(127) + b"}", 0)
        self.outcome(self.PUT + b',"x":' + objects(127) + b"}", 0)
        self.outcome(self.PUT + b',"x":[' + objects(126) + b"]}", 0)
        self.refused(self.PUT + b',"x":' + arrays(128) + b"}", "depth")
        self.refused(self.PUT + b',"x":' + objects(128) + b"}", "depth")
        self.refused(self.PUT + b',"x":[' + objects(127) + b"]}", "depth")
        self.outcome(arrays(128), 1, "badrequest")
        self.refused(arrays(129), "depth")
        self.outcome(objects(128), 2, "badrequest")
        self.refused(objects(129), "depth")
        # Скаляры глубины не прибавляют; глубина 128 — как оракул.
        text = '{"op":"put","key":"acc/a","items":{},"x":' + "[" * 127 + '"s",1,null' + "]" * 127 + "}"
        self.same_as_oracle("writer", text)
        # Глубину мерят и в items: 128-й уровень — отказ строки items, 129-й — разбора.
        self.outcome(b'{"op":"put","key":"acc/a","items":{"f":' + arrays(126) + b"}}", 6, "badrequest")
        self.refused(b'{"op":"put","key":"acc/a","items":{"f":' + arrays(127) + b"}}", "depth")

    def test_syntax(self):
        cases = [b"", b" ", b"\n\t\r ", b"{", b"}", b"[", b'{"a":1,}', b"[1,]", b"[,1]", b'{,"a":1}', b'{"a" 1}',
                 b'{"a":1 "b":2}', b"[1 2]", b"{'a':1}", b'{"a":01}', b'{"a":-01}', b'{"a":+1}', b'{"a":.5}',
                 b'{"a":1.}', b'{"a":1e}', b'{"a":1e+}', b'{"a":-}', b'{"a":0x1}', b'{"a":1_000}', b'{"a":tru}',
                 b'{"a":nul}', b'{"a":True}', b'{"a":None}', b'{"a":undefined}', b'{"a":"\x01"}', b'{"a":"\t"}',
                 b'{"a":"\n"}', b'{"a":"\x1f"}', b'{"a":"\\x41"}', b'{"a":"\\u12"}', b'{"a":"\\u12g4"}',
                 b'{"a":"\\U0041"}', b'{"a":"\\a"}', b'{"a":"\\', b'{"a":"abc', b'{"a":1}/**/', b'/*c*/{}',
                 b'{"a":1} {}', b'{"a":1}x', b"{}\x00", b"\x0b{}", b"{\xc2\xa0}", b'{"a"\xc2\xa0:1}',
                 b'{"a":[1,2}', b'{"a":{"b":1]}', b'{a:1}', b'{"a":1,"b"}', b'{"a":"\\ud800\\u"}', b'"\\']
        for raw in cases:
            with self.subTest(raw=raw):
                self.refused(raw)
        # Пробелы RFC 8259 — пробел, TAB, LF, CR — где угодно между лексемами.
        self.same_as_oracle("writer", ' \t\r\n{ "op" : "put" ,\n"key"\t:\r"acc/a", "items" : { } } \n')
        self.same_as_oracle("writer", '{"op":"put","key":"acc/a","items":{"f":"\\"\\\\\\/\\b\\f\\n\\r\\t\\u00e9"}}')
        self.same_as_oracle("writer", '{"op":"put","key":"acc/a","items":{"\\u00E9":"\\uABCD"}}')
        # U+0000 — символ строки (Н2.1: %00 ключа допустим). Оракул здесь не судья: cel-expr-python обрезает строку
        # на U+0000 (size("a\\u0000b") == 1), поэтому — прямо: вес 1 + 11 байт > ROW_CEILING 8, ключ с NUL проходит Н1.
        r = self.outcome(b'{"op":"put","key":"acc/a","items":{"f":"\\"\\\\\\/\\b\\f\\n\\r\\t\\u00e9\\u0000"}}', 13,
                         "toolarge")
        self.assertEqual(untag(r["refusal"]["fault"]), {"limit": 8, "key": "acc/a", "size": 12})
        self.assertEqual(untag(r["value"])["items"]["f"], "\"\\/\b\f\n\r\té\u0000")
        r = self.outcome(b'{"op":"put","key":"acc/\\u0000","items":{"\\u0000":"\\u0000"}}', 0, lone=[])
        self.assertEqual(untag(r["value"])["key"], "acc/\x00")
        # Два ключа пакета, различные только после U+0000, — разные (строка 26 не отказывает).
        self.outcome(b'{"op":"batch","writes":[{"op":"delete","key":"acc/\\u0000a"},{"op":"delete","key":"acc/\\u0000b"}]}',
                     0)
        # Корень не объект — не ошибка разбора: отказ строки 1 таблицы.
        for root in (b'"s"', b"1", b"null", b"true", b"[]", b"-0.5e-3"):
            self.outcome(root, 1, "badrequest")

    # ------------------------------------------------------------ Н2.1: одиночный суррогат

    def test_lone_surrogate(self):
        cases = [
            ('{"op":"put","key":"acc/\\ud800","items":{}}', 5, ["/key"]),
            ('{"op":"delete","key":"\\udfffacc/a"}', 5, ["/key"]),
            ('{"op":"put","key":"acc/a","items":{"\\ud800":"x"}}', 6, ["/items"]),
            ('{"op":"put","key":"acc/a","items":{"k":"\\ud800"}}', 6, ["/items/k"]),
            ('{"op":"put","key":"acc/a","items":{"\\udc00":"\\udc00"}}', 6, ["/items", "/items/\ufffd"]),
            ('{"op":"put","key":"acc/a","items":{},"x":"\\udc00"}', 0, ["/x"]),
            ('{"op":"put","key":"acc/a","items":{},"\\udc00":1}', 0, [""]),
            ('{"op":"put","key":"acc/a","items":{},"a/b~c":"\\ud800"}', 0, ["/a~1b~0c"]),
            ('{"op":"put","key":"acc/a","items":{},"x":[1,{"\\ud800":["\\udbff"]}]}', 0,
             ["/x/1", "/x/1/\ufffd/0"]),
            ('{"op":"put","key":"acc/a","items":{},"guard":{"key":"acc/\\ud800","index":""}}', 9, ["/guard/key"]),
            ('{"op":"batch","writes":[{"op":"put","key":"acc/\\ud800","items":{}}]}', 20, ["/writes/0/key"]),
            ('{"op":"batch","writes":[{"op":"delete","key":"acc/b"},{"op":"put","key":"acc/a","items":{"k":"\\ud800"}}]}',
             21, ["/writes/1/items/k"]),
            ('{"op":"batch","writes":[{"op":"put","key":"acc/a","items":{}}],"guards":[{"key":"acc/\\udc00","index":""}]}',
             25, ["/guards/0/key"]),
            # Пара — один символ, не одиночный; обратный порядок и разорванная пара — два одиночных.
            ('{"op":"put","key":"acc/\\ud83d\\ude00","items":{}}', 0, []),
            ('{"op":"put","key":"acc/\\uD83D\\uDE00","items":{"\\ud83d\\ude00":"\\ud83d\\ude00"}}', 0, []),
            ('{"op":"put","key":"acc/a","items":{},"x":"\\udbff\\udfff\\ud800\\udc00"}', 0, []),
            ('{"op":"put","key":"acc/a","items":{},"x":"\\ude00\\ud83d"}', 0, ["/x"]),
            ('{"op":"put","key":"acc/a","items":{},"x":"\\ud800\\u0041\\ud800\\ud800\\udc00"}', 0, ["/x"]),
            ('{"op":"put","key":"acc/a","items":{},"x":"\\ud800x","y":"\\ud800"}', 0, ["/x", "/y"]),
        ]
        for text, n, lone in cases:
            with self.subTest(text=text):
                r = self.same_as_oracle("writer", text)
                self.assertEqual(r["refusal"]["n"] if r["refusal"] else 0, n)
                self.assertEqual(r["lone"], lone)
        r = self.outcome(b'{"op":"put","key":"acc/a","items":{},"x":"\\ud800\\u0041\\ud800\\ud800\\udc00"}', 0)
        self.assertEqual(untag(r["value"])["x"], "\ufffdA\ufffd\U00010000")

    # ------------------------------------------------------------ числа

    def number(self, literal, field="not_after"):
        raw = b'{"op":"put","key":"acc/a","items":{},"' + field.encode() + b'":' + literal + b"}"
        r = self.kit.run("writer", raw)
        return r, r["value"][("$map")][field] if r["value"] else None

    def test_numbers(self):
        cases = [  # литерал, вид, значение, отказ строки not_after (11) или 0
            (b"0", "$int", "0", 0), (b"-0", "$int", "0", 0), (b"7", "$int", "7", 0),
            (b"9223372036854775807", "$int", "9223372036854775807", 0),
            (b"9223372036854775808", "$double", "9223372036854775808", 0),
            (b"-9223372036854775808", "$int", "-9223372036854775808", 11),
            (b"-9223372036854775809", "$double", "-9223372036854775808", 11),
            (b"18446744073709551616", "$double", "18446744073709551616", 0),
            (b"1" + b"0" * 400, "$double", "+Inf", 11), (b"-" + b"9" * 400, "$double", "-Inf", 11),
            (b"1e400", "$double", "+Inf", 11), (b"-1e400", "$double", "-Inf", 11),
            (b"1E99999999999999999999", "$double", "+Inf", 11), (b"1e-400", "$double", "0", 0),
            (b"-1e-400", "$double", "-0", 0), (b"1.0", "$double", "1", 0), (b"0.0", "$double", "0", 0),
            (b"-0.0", "$double", "-0", 0), (b"1E2", "$double", "100", 0), (b"1e+2", "$double", "100", 0),
            (b"1.5", "$double", "1.5", 0), (b"-1.5", "$double", "-1.5", 11),
            (b"1.7976931348623157e308", "$double", "1.7976931348623157e+308", 0),
            (b"1.7976931348623159e308", "$double", "+Inf", 11),
            (b"4102444800.123456789012345678901234567890", "$double", "4102444800.123456789012345678901234567890", 0),
            (b"0." + b"0" * 5000 + b"1", "$double", "0", 0),
        ]
        for literal, kind, value, n in cases:
            with self.subTest(literal=literal[:40]):
                r, v = self.number(literal)
                self.assertEqual(list(v), [kind])
                self.assertEqual(float(v[kind]), float(value))
                self.assertEqual(math.copysign(1, float(v[kind])), math.copysign(1, float(value)))
                self.assertEqual(r["refusal"]["n"] if r["refusal"] else 0, n)
                if len(literal) < 1000 and b"1E99" not in literal:
                    text = ('{"op":"put","key":"acc/a","items":{},"not_after":' + literal.decode() + "}")
                    if not (literal.lstrip(b"-").isdigit() and len(literal) > 300):   # float(10**400) у оракула — OverflowError
                        self.same_as_oracle("writer", text)

    def test_long_extra_fields(self):
        """Числа и строки лишних полей не читаются при любой длине (Н2.1): принято, без ошибок."""
        self.outcome(self.PUT + b',"n":' + b"1" * 300000 + b',"m":-' + b"7" * 200000 + b".5e-99999999"
                     + b',"s":"' + "é".encode() * 200000 + b'"}', 0)
        self.outcome(self.PUT + b',"x":[' + b",".join([b"1.5", b'"s"', b"null", b"{}"] * 50000) + b"]}", 0)


class Fresh(unittest.TestCase):
    """Свежесть № 1 и № 2 (ревью Codex С2): сборка сверяет копируемый выход со свежей генерацией, не с шапкой."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="normgen-fresh-"))
        self.patches = []

    def tearDown(self):
        for obj, name, old in reversed(self.patches):
            setattr(obj, name, old)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def patch(self, obj, name, new):
        self.patches.append((obj, name, getattr(obj, name)))
        setattr(obj, name, new)

    def refuses(self, parts=("door",)):
        with self.assertRaises(build_kit.KitError) as ctx:
            build_kit.build(self.tmp / "dst", MODULE, list(parts))
        self.assertIn("fresh run", str(ctx.exception))

    def test_green(self):
        m = build_kit.build(self.tmp / "dst", MODULE, ["door"])
        for part in ("writecheck", "door"):
            prov = m["provenance"][part]
            self.assertTrue(prov["generator"]["sha256"] and prov["judge"]["sha256"] and prov["output"], part)
            self.assertIsNone(prov["judged"])

    def test_out_edited_header_kept(self):
        """Подмена в out при прежней шапке (проба ревью: отказы отключены)."""
        copy = self.tmp / "normgen"
        shutil.copytree(NORMGEN / "out", copy / "out")
        f = copy / "out/p01-1/go/checks/checks.go"
        text = f.read_text(encoding="utf-8")
        self.assertIn("hit == nil && isTrue(v)", text)
        f.write_text(text.replace("hit == nil && isTrue(v)", "false"), encoding="utf-8")
        self.patch(build_kit, "NORMGEN", copy)
        self.refuses(())

    def test_environment_only(self):
        """Изменилась только ручная среда (runtime.go checks, doorrt) — форма и генератор прежние."""
        import gen_checks
        import gen_door
        env = self.tmp / "env"
        shutil.copytree(NORMGEN / "runtime", env / "runtime")
        shutil.copytree(NORMGEN / "prims", env / "prims")
        rt = env / "runtime/go/runtime.go"
        rt.write_text(rt.read_text(encoding="utf-8") + "\nvar envChanged = 1\n", encoding="utf-8")
        self.patch(gen_checks, "HERE", env)
        self.refuses(())
        setattr(gen_checks, "HERE", NORMGEN)
        door_rt = env / "doorrt.go"
        door_rt.write_text(gen_door.RUNTIME.read_text(encoding="utf-8") + "\nvar envChanged = 1\n", encoding="utf-8")
        self.patch(gen_door, "RUNTIME", door_rt)
        self.patch(gen_door, "HERE", env)
        self.refuses()

    def test_generator_only(self):
        """Изменилась только логика генератора."""
        import gen_checks
        import gen_door
        old = gen_checks.go_module
        self.patch(gen_checks, "go_module", lambda *a: old(*a) + "\nvar genChanged = 1\n")
        self.refuses(())
        setattr(gen_checks, "go_module", old)
        old_door = gen_door.build_go
        self.patch(gen_door, "build_go", lambda *a: (old_door(*a)[0] + "\nvar genChanged = 1\n", old_door(*a)[1]))
        self.refuses()


if __name__ == "__main__":
    unittest.main()
