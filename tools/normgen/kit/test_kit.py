"""Check the P/01 kit against the check_tables oracle (ADR-0083 addendum 86, item 2).

Run kit/test_kit.py with cel_expr_python and Go 1.22 on PATH, without network. Build into an empty directory/module, check go build/vet/gofmt and file/manifest agreement. Stream every non-nopair write-checks probe as raw bytes and compare first refusal, body and lone paths with check_tables.decode/CEL. NORMGEN_KIT_MUTANTS adds randomized strict JSON, whitespace and raw/escaped UTF-8; every expected result comes from the oracle. Parse lesson JCS raw vectors identically.

Negative N2.1 cases include duplicate names, nested duplicates, BOM, NaN, Infinity, invalid UTF-8, depth 128/129 and RFC 8259 syntax; lone surrogates in keys, items, guard.key, writes, guards and extra fields; int64/binary64 boundaries. Peak RSS for the streaming test and child processes must remain within1GB; one Go harness process handles the stream."""
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
import check_tables  # noqa: E402 -- oracle
import test_gen_checks as tg  # noqa: E402 -- probe inputs, mutator and table oracle

MODULE = "example.com/w2c/store"
JCS = ROOT / "Platform/01-store/vectors/jcs/canonical_json.tsv"
MUTANTS = int(os.environ.get("NORMGEN_KIT_MUTANTS", "3000"))
SEED = int(os.environ.get("NORMGEN_SEED", "20261104"))
MAX_RSS = 1 << 30
GOENV = dict(os.environ, GOPROXY="off", GOFLAGS="-mod=mod", GOWORK="off", GOTOOLCHAIN="local")


def canon(v):
    """Normalize Python values while preserving number kind and the sign of zero."""
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
    """Decode tagged harness values to Python values."""
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
    """Serialize strict JSON with randomized whitespace/raw-or-escaped UTF-8; represent positive/negative infinity by +/-1e400."""
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
    """Use one persistent kitprobe harness process: send one JSON line and read its response immediately without accumulation."""

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

    # ------------------------------------------------------------ helpers

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
        """Send raw bytes (UTF-8 text by default), compare refusal/body/lone with the oracle, and return the harness response."""
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

    # ------------------------------------------------------------ build

    def test_build(self):
        """Build/vet in an empty module during setUpClass; require clean gofmt and matching manifest/files."""
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
        """writecheck.Limits must contain exactly the table's #lim names."""
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

    # ------------------------------------------------------------ probes, mutants, vectors

    def test_probes(self):
        """All non-nopair probes run as raw bytes against the oracle."""
        for name, sock, text in self.probes:
            with self.subTest(name):
                self.same_as_oracle(sock, text)
        print(f"\nprobes: {len(self.probes)}", file=sys.stderr)

    def test_mutants(self):
        """Strict-JSON probe mutants match the oracle and cover every table row as first refusal."""
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
        """Parse lesson JCS raw vectors and compare bodies with the oracle."""
        count = 0
        for line in JCS.read_text(encoding="utf-8").split("\n"):        # Do not use splitlines: cells may contain U+2028 and similar characters.
            if not line or line.startswith("#"):
                continue
            raw = line.split("\t")[0]
            r = self.same_as_oracle("writer", raw)
            self.assertFalse(r["refusal"] and r["refusal"]["n"] == 0, raw)
            count += 1
        self.assertGreater(count, 10)
        print(f"\njcs vectors: {count}", file=sys.stderr)

    # ------------------------------------------------------------ N2.1 parse refusals

    PUT = b'{"op":"put","key":"acc/a","items":{}'

    def test_repeated_names(self):
        self.refused(b'{"op":"put","op":"put","key":"acc/a","items":{}}', "duplicate_name")
        self.refused(b'{"op":"put","key":"acc/a","items":{"n":"1","n":"2"}}', "duplicate_name")
        self.refused(self.PUT + b',"x":[1,{"a":1,"b":{"c":1,"d":[{"e":0,"e":0}]}}]}', "duplicate_name")
        self.refused(self.PUT + b',"a":1,"\\u0061":2}', "duplicate_name")
        self.refused(self.PUT + b',"\\ud800":1,"\\ud800":2}', "duplicate_name")
        self.refused(self.PUT + b',"\xc3\xa9":1,"\\u00e9":2}', "duplicate_name")
        # Distinct RFC 8259 names that collide after U+FFFD are not duplicates, matching the oracle; a and A differ.
        self.same_as_oracle("writer", '{"op":"put","key":"acc/a","items":{},"\\ud800":1,"\\udbff":2,"\ufffd":3}')
        self.same_as_oracle("writer", '{"op":"put","key":"acc/a","items":{},"a":1,"A":2}')
        # The same name in different objects is not a duplicate.
        self.same_as_oracle("writer", '{"op":"put","key":"acc/a","items":{"key":"v"},"x":{"key":1}}')

    def test_bom_nan_infinity(self):
        self.refused(b"\xef\xbb\xbf" + self.PUT + b"}", "bom")
        self.refused(b" \xef\xbb\xbf" + self.PUT + b"}")
        self.refused(self.PUT + b',"x":NaN}', "nan_or_infinity")
        self.refused(self.PUT + b',"x":Infinity}', "nan_or_infinity")
        self.refused(self.PUT + b',"x":-Infinity}', "nan_or_infinity")
        self.refused(self.PUT + b',"x":[1,NaN]}', "nan_or_infinity")
        self.refused(b'{"op":"put","key":"acc/a","items":{},"not_after":Infinity}', "nan_or_infinity")
        # A BOM inside a string is ordinary U+FEFF data.
        self.same_as_oracle("writer", '{"op":"put","key":"acc/a","items":{"f":"\ufeff"}}')

    def test_not_utf8(self):
        for bad in (b"\xff", b"\xc0\xaf", b"\xed\xa0\x80", b"\xed\xbf\xbf", b"\xf4\x90\x80\x80", b"\xe2\x82",
                    b"\x80", b"\xf8\x88\x80\x80\x80"):
            with self.subTest(bad=bad):
                self.refused(self.PUT + b',"x":"a' + bad + b'"}', "utf8")
                self.refused(self.PUT + b',"' + bad + b'":1}', "utf8")
                self.refused(b'{"op":"put","key":"acc/' + bad + b'","items":{}}', "utf8")
        self.refused(self.PUT + b"}\xe2\x82", "utf8")
        # U+FFFF/U+10FFFF are valid UTF-8/JSON noncharacters permitted by RFC 8259.
        self.same_as_oracle("writer", '{"op":"put","key":"acc/a","items":{"f":"\uffff\U0010ffff"}}')

    def test_depth(self):
        def arrays(k):
            return b"[" * k + b"]" * k

        def objects(k):
            return b'{"a":' * (k - 1) + b"{}" + b"}" * (k - 1)

        # Root depth is1: an extra field with127 nested arrays reaches depth 128.
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
        # Scalars do not increase depth; depth 128 matches the oracle.
        text = '{"op":"put","key":"acc/a","items":{},"x":' + "[" * 127 + '"s",1,null' + "]" * 127 + "}"
        self.same_as_oracle("writer", text)
        # Measure items depth too: level 128 refuses items, level 129 refuses parsing.
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
        # RFC 8259 whitespace (space, TAB, LF, CR) is allowed between tokens.
        self.same_as_oracle("writer", ' \t\r\n{ "op" : "put" ,\n"key"\t:\r"acc/a", "items" : { } } \n')
        self.same_as_oracle("writer", '{"op":"put","key":"acc/a","items":{"f":"\\"\\\\\\/\\b\\f\\n\\r\\t\\u00e9"}}')
        self.same_as_oracle("writer", '{"op":"put","key":"acc/a","items":{"\\u00E9":"\\uABCD"}}')
        # U+0000 is string data (N2.1 allows %00 in keys). Do not use the CEL oracle for this case: cel-expr-python
        # truncates at NUL, yielding size(a\u0000b)=1. Assert directly:1+11 bytes exceeds ROW_CEILING8; N1 allows NUL keys.
        r = self.outcome(b'{"op":"put","key":"acc/a","items":{"f":"\\"\\\\\\/\\b\\f\\n\\r\\t\\u00e9\\u0000"}}', 13,
                         "toolarge")
        self.assertEqual(untag(r["refusal"]["fault"]), {"limit": 8, "key": "acc/a", "size": 12})
        self.assertEqual(untag(r["value"])["items"]["f"], "\"\\/\b\f\n\r\té\u0000")
        r = self.outcome(b'{"op":"put","key":"acc/\\u0000","items":{"\\u0000":"\\u0000"}}', 0, lone=[])
        self.assertEqual(untag(r["value"])["key"], "acc/\x00")
        # Keys differing only after U+0000 remain distinct; row 26 must not refuse.
        self.outcome(b'{"op":"batch","writes":[{"op":"delete","key":"acc/\\u0000a"},{"op":"delete","key":"acc/\\u0000b"}]}',
                     0)
        # A non-object root parses successfully and is refused by table row 1.
        for root in (b'"s"', b"1", b"null", b"true", b"[]", b"-0.5e-3"):
            self.outcome(root, 1, "badrequest")

    # ------------------------------------------------------------ N2.1 lone surrogates

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
            # A valid pair is one character; reversed or separated pairs contain two lone surrogates.
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

    # ------------------------------------------------------------ numbers

    def number(self, literal, field="not_after"):
        raw = b'{"op":"put","key":"acc/a","items":{},"' + field.encode() + b'":' + literal + b"}"
        r = self.kit.run("writer", raw)
        return r, r["value"][("$map")][field] if r["value"] else None

    def test_numbers(self):
        cases = [  # Literal, kind, value and not_after row 11 refusal, or0.
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
                    if not (literal.lstrip(b"-").isdigit() and len(literal) > 300):   # float(10**400) raises OverflowError in the oracle.
                        self.same_as_oracle("writer", text)

    def test_long_extra_fields(self):
        """Numbers/strings in extra fields are ignored at any length (N2.1): accepted without errors."""
        self.outcome(self.PUT + b',"n":' + b"1" * 300000 + b',"m":-' + b"7" * 200000 + b".5e-99999999"
                     + b',"s":"' + "é".encode() * 200000 + b'"}', 0)
        self.outcome(self.PUT + b',"x":[' + b",".join([b"1.5", b'"s"', b"null", b"{}"] * 50000) + b"]}", 0)


class Fresh(unittest.TestCase):
    """Creation identity catches changed output, runtime and generator inputs without regeneration."""
    def setUp(self):
        import lesson
        self.tmp = Path(tempfile.mkdtemp(prefix="normgen-fresh-"))
        self.patches = []
        self.lesson = lesson
        self.real_ready = lesson.ready_outputs
        self.ready = self.real_ready(profiles=lesson.PROFILES)
        self.receipt = os.environ[lesson.OUTPUT_RECEIPT_ENV]
        self.original_output = lesson.output_root()

    def tearDown(self):
        for obj, name, old in reversed(self.patches):
            setattr(obj, name, old)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def patch(self, obj, name, new):
        self.patches.append((obj, name, getattr(obj, name)))
        setattr(obj, name, new)

    def consumes_copy(self, output=None, code=None):
        from functools import partial
        self.patch(self.lesson, "ready_outputs", partial(self.real_ready,
                   output_root=output or self.original_output, source_root=ROOT, code_root=code or ROOT,
                   expected_manifest_sha256=self.receipt))

    def code_copy(self):
        root = self.tmp / "code"
        def excluded(directory, names):
            return [name for name in names if name == '__pycache__' or name.endswith('.pyc')
                    or (Path(directory) == NORMGEN and name == 'out')]
        shutil.copytree(NORMGEN, root / 'tools/normgen', ignore=excluded)
        # Prove the copied inputs match before applying any mutation.
        self.real_ready(output_root=self.original_output, source_root=ROOT, code_root=root,
                        profiles=self.lesson.PROFILES, expected_manifest_sha256=self.receipt)
        return root

    def refuses(self, parts=("door",)):
        with self.assertRaises(build_kit.KitError) as ctx:
            build_kit.build(self.tmp / "dst", MODULE, list(parts))
        self.assertRegex(str(ctx.exception), "prepared output|creation receipt")
        self.assertFalse((self.tmp / 'dst').exists(), 'integrity must fail before destination copy')

    def test_green(self):
        m = build_kit.build(self.tmp / "dst", MODULE, ["door"])
        for part in ("writecheck", "door"):
            prov = m["provenance"][part]
            self.assertTrue(prov["generator"]["sha256"] and prov["judge"]["sha256"] and prov["output"], part)
            self.assertIsNone(prov["judged"])

    def test_out_edited_header_kept(self):
        """The supplied output is a copy; the unchanged original/receipt is retained."""
        output = self.tmp / "output"
        shutil.copytree(self.original_output, output)
        f = output / "p01-1/go/checks/checks.go"
        text = f.read_text()
        before_count = text.count("hit == nil && isTrue(v)")
        self.assertGreater(before_count, 0)
        changed = text.replace("hit == nil && isTrue(v)", "false")
        self.assertNotEqual(changed, text)
        self.assertEqual(changed.count("hit == nil && isTrue(v)"), 0)
        f.write_text(changed)
        before = f.read_bytes()
        self.consumes_copy(output=output)
        self.refuses(())
        self.assertEqual(f.read_bytes(), before, 'consumer must not heal output')
        self.real_ready(output_root=self.original_output, source_root=ROOT, code_root=ROOT,
                        profiles=self.lesson.PROFILES, expected_manifest_sha256=self.receipt)

    def test_environment_only(self):
        """Physical runtime changes invalidate the recorded inputs; no renderer is called."""
        root = self.code_copy()
        self.consumes_copy(code=root)
        for relative in ('runtime/go/runtime.go', 'doorrt/go/runtime.go'):
            path = root / 'tools/normgen' / relative
            original = path.read_bytes()
            path.write_bytes(original + b'\nvar envChanged = 1\n')
            self.refuses(())
            self.assertEqual(path.read_bytes(), original + b'\nvar envChanged = 1\n')
            path.write_bytes(original)

    def test_generator_only(self):
        """Changed generator implementations cannot authorize regeneration at consumption."""
        root = self.code_copy()
        self.consumes_copy(code=root)
        for relative, function in (('gen_checks.py', 'go_module'), ('gen_door.py', 'build_go')):
            path = root / 'tools/normgen' / relative
            original = path.read_bytes()
            mutation = ('\ndef ' + function + '(*args, **kwargs):\n    raise RuntimeError("owned generator mutant")\n').encode()
            path.write_bytes(original + mutation)
            self.refuses(())
            self.assertEqual(path.read_bytes(), original + mutation)
            path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
