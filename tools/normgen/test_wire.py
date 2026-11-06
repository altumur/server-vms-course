"""Judge for the vector wire form reader (wire.py), without Go.

Run: /opt/check-env/lesson-spec/bin/python tools/normgen/test_wire.py [-v]   (requires cel_expr_python)
Read the form from the course root, or WIRE_ROOT (an export with Platform/, including its canonical fixture data)
if it is not yet in main; otherwise skip the tests.

1. Parse the form and expand lesson 02 without errors; journal is an excluded layout.
2. Each generated P/02 frame follows the expanded form (input, fixtures, case, variant). Cross-check shared
   P/01/P/02 packages with the independent common_vectors reader (expectation, input, fixtures; family-read uses
   subset verdicts, a set of paths, value comparison for writer outcomes and sets for reader outcomes).
3. Reject form mutants with WireError: duplicate JSON key, foreign constructor, unknown comparison, two inputs
   of the same variant on a row, json decoding of a string domain, a norm anchor without a heading, a stand fixture,
   no-leak without integer min_bytes ≥ 1, nonboolean whole or whole outside no-leak, an owner outside consumers.tsv,
   when disagreeing within a group, and a duplicate run.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("NORMGEN_LESSON", "02-installer")

import wire  # noqa: E402


def form_root():
    if (ROOT / wire.FORM).is_file():
        return ROOT
    w = os.environ.get("WIRE_ROOT")
    if w and (Path(w) / wire.FORM).is_file():
        return Path(w)
    return None


def need():
    try:
        import cel_expr_python  # noqa: F401
    except ImportError:
        raise unittest.SkipTest("no cel_expr_python: /opt/check-env/lesson-spec/bin/python")
    root = form_root()
    if root is None:
        raise unittest.SkipTest(f"no {wire.FORM} in the course and no WIRE_ROOT")
    return root


class Form(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = need()
        cls.cel = wire.Cel()

    def test_parse_and_expand(self):
        bs = wire.parse(self.root)
        self.assertTrue(bs)
        runs, excl = wire.expand(self.root, "02-installer", self.cel)
        self.assertTrue(runs)
        self.assertIn(("common/journal", "modes.tsv"), {(x.binding.package, x.binding.table) for x in excl})
        ids = [r.identity for r in runs]
        self.assertEqual(len(ids), len(set(ids)))

    def test_generated_runs_follow_the_form(self):
        import test_gen_vectors
        g = test_gen_vectors.gv()
        files, _ = g.build(self.root)
        runs, _ = wire.expand(self.root, "02-installer", self.cel)
        for r in runs:
            if r.binding.surface != "vectors":
                continue
            stem = f"line-{r.lines[0]}" + (f"-{r.variant}" if r.variant else "")
            path = f"vectors/{r.binding.package}/{r.binding.table[:-4]}/{stem}.json"
            frame = json.loads(files[path])
            self.assertEqual((frame["package"], frame["table"], frame["case"], frame["variant"]),
                             (r.binding.package, r.binding.table, r.case, r.variant))
            self.assertEqual(frame["cells"], r.cells)
            import base64
            self.assertEqual({k: base64.b64decode(v) for k, v in frame["files"].items()}, r.files)

    def test_same_as_common_vectors(self):
        import common_vectors as C
        for owner in ("01-store", "02-installer"):
            runs, _ = wire.expand(self.root, owner, self.cel)
            by = {}
            for r in runs:
                by.setdefault((r.binding.package[len("common/"):], r.binding.table), {})[r.lines[0]] = r
            for name, table in C.composition(owner, self.root, known_only=True):
                rel, _, rows = C.read(self.root, name, table)
                fx = {f: d for f, (_, d) in C.fixtures(self.root, name).items()}
                got = by.get((name, table))
                self.assertIsNotNone(got, f"{owner} {name}: no form row")
                self.assertEqual(sorted(got), [no for no, _ in rows], f"{owner} {name}")
                for no, row in rows:
                    w, where = got[no], f"{owner} {name} {table}:{no}"
                    want = C.expected(name, row, where)
                    self.assertEqual(w.cells, {c: row[c] for c in C.DECLS[name]["inputs"]}, where)
                    self.assertEqual(w.files, fx, where)
                    if name != "family-read":
                        self.assertEqual(w.value, want, where)
                        continue
                    a = {x.pointer: (x.compare, x.value) for x in w.asserts}
                    self.assertEqual((w.compare, w.value), ("subset", {"verdict": want["verdict"]}), where)
                    self.assertEqual((a["/paths"][0], sorted(a["/paths"][1])), ("set", want["paths"]), where)
                    c, v = a["/outcome"]
                    reader = row["mode"] == "reader"
                    self.assertEqual(c, "object-sets" if reader else "value", where)
                    self.assertEqual({x: sorted(y) for x, y in v.items()} if reader else v, want["outcome"], where)


class Mutants(unittest.TestCase):
    """Each single-cell form mutation must fail parsing or expansion."""

    @classmethod
    def setUpClass(cls):
        cls.src = need()
        cls.cel = wire.Cel()
        cls.tmp = Path(tempfile.mkdtemp(prefix="judge-wire-"))
        shutil.copytree(cls.src / "Platform", cls.tmp / "Platform")
        cls.text = (cls.tmp / wire.FORM).read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def tearDown(self):
        (self.tmp / wire.FORM).write_text(self.text, encoding="utf-8")

    def edit(self, package, table, surface, column, fn):
        lines = self.text.split("\n")
        for i, line in enumerate(lines):
            cells = line.split("\t")
            if cells[:3] == [package, table, surface]:
                k = wire.COLUMNS.index(column)
                cells[k] = fn(cells[k])
                lines[i] = "\t".join(cells)
                (self.tmp / wire.FORM).write_text("\n".join(lines), encoding="utf-8")
                return
        self.skipTest(f"no row {package} {table} {surface} in this form")

    def jedit(self, package, table, surface, column, fn):
        def f(cell):
            v = json.loads(cell)
            fn(v)
            return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        self.edit(package, table, surface, column, f)

    def refused(self, owner="02-installer"):
        with self.assertRaises(wire.WireError):
            wire.expand(self.tmp, owner, self.cel)

    def test_unchanged_is_accepted(self):
        wire.expand(self.tmp, "02-installer", self.cel)

    def test_duplicate_json_key(self):
        self.edit("common/loopback", "cases.tsv", "vectors", "native", lambda c: c[:-1] + ',"frame":"json"}')
        self.refused()

    def test_foreign_constructor(self):
        self.jedit("common/loopback", "cases.tsv", "vectors", "expect",
                   lambda v: v[0].__setitem__("value", {"eval": "expect"}))
        self.refused()

    def test_unknown_compare(self):
        self.edit("common/loopback", "cases.tsv", "vectors", "compare", lambda c: "bytes")
        self.refused()

    def test_two_inputs_of_a_variant(self):
        self.jedit("common/loopback", "cases.tsv", "vectors", "inputs", lambda v: v.append(dict(v[0])))
        self.refused()

    def test_json_on_a_string_domain(self):
        # backup-key: 64 hex is a string (decode text); decoding that cell as json must fail.
        self.jedit("common/domain-backup-key", "cases.tsv", "vectors", "expect",
                   lambda v: v[0]["value"].__setitem__("decode", "json"))
        self.refused()

    def test_missing_anchor(self):
        self.edit("common/journal", "modes.tsv", "layout", "norm", lambda c: c.split("#")[0] + "#no-such-heading")
        self.refused()

    def test_stand_files(self):
        self.edit("02-installer/exec", "cases.tsv", "stand:exec", "files",
                  lambda c: '{"x":{"base":"package","path":"cases.tsv"}}')
        self.refused()

    def test_owner_not_a_consumer(self):
        self.jedit("common/sealing", "ring.tsv", "vectors", "inputs",
                   lambda v: v[1].__setitem__("when", v[1]["when"].replace("02-installer", "09-nowhere")))
        self.refused()

    def test_when_differs_in_a_group(self):
        self.jedit("02-installer/platform-lists", "cases.tsv", "vectors", "expect",
                   lambda v: v[0].__setitem__("when", 'row["word"].startsWith("a")'))
        self.refused()

    def test_duplicate_run(self):
        self.jedit("common/yaml-suite", "expect.tsv", "vectors", "inputs",
                   lambda v: v[0].__setitem__("case", "suite"))
        self.refused()

    def test_no_leak_needs_min_bytes(self):
        def add(v, mb):
            v[0]["assert"] = [dict({"pointer": "", "test": "no-leak", "value": {"column": "raw", "decode": "text"}},
                                   **({} if mb is None else {"min_bytes": mb}))]
        for mb in (None, 0, True, "4"):
            with self.subTest(min_bytes=mb):
                self.jedit("common/log-mask", "cases.tsv", "vectors", "expect", lambda v: add(v, mb))
                self.refused()
                self.tearDown()
        self.jedit("common/log-mask", "cases.tsv", "vectors", "expect", lambda v: add(v, 4))
        runs, _ = wire.expand(self.tmp, "02-installer", self.cel)
        r = next(r for r in runs if r.binding.package == "common/log-mask")
        self.assertEqual(r.asserts[0][1:], ("no-leak", None, [r.cells["raw"]], 4, False, None, None))

    def test_json_decode_is_preserved_in_assertion(self):
        self.jedit("common/sealing", "reseal.tsv", "vectors", "expect",
                   lambda v: v[0].__setitem__("assert", [{"pointer": "/row", "decode": "json", "compare": "value",
                                                        "value": {"literal": {"n": 1}}}]))
        runs, _ = wire.expand(self.tmp, "02-installer", self.cel)
        assertion = next(r for r in runs if r.binding.key == ("common/sealing", "reseal.tsv", "vectors")).asserts[0]
        self.assertEqual((assertion.pointer, assertion.decode, assertion.value), ("/row", "json", {"n": 1}))

    def test_whole_only_with_no_leak(self):
        def add(v, extra):
            v[0]["assert"] = [dict({"pointer": "", "value": {"column": "raw", "decode": "text"}}, **extra)]
        bad = ({"test": "no-leak", "min_bytes": 4, "whole": 1}, {"test": "prefix", "whole": True},
               {"whole": False}, {"min_bytes": 4})
        for extra in bad:
            with self.subTest(extra=extra):
                self.jedit("common/log-mask", "cases.tsv", "vectors", "expect", lambda v: add(v, extra))
                self.refused()
                self.tearDown()
        self.jedit("common/log-mask", "cases.tsv", "vectors", "expect",
                   lambda v: add(v, {"test": "no-leak", "min_bytes": 4, "whole": True}))
        runs, _ = wire.expand(self.tmp, "02-installer", self.cel)
        r = next(r for r in runs if r.binding.package == "common/log-mask")
        self.assertIs(r.asserts[0].whole, True)


    def test_escape_the_export(self):
        self.jedit("common/log-mask", "cases.tsv", "vectors", "files",
                   lambda v: v["fields.yaml"].__setitem__("path", "../../../../../etc/passwd"))
        self.refused()


class Leaks(unittest.TestCase):
    def test_fragment_and_whole(self):
        self.assertEqual(wire.leaks("x=abcd", ["zzabcdzz"], 4), ["zzabcdzz"])         # fragment ≥ 4 bytes
        self.assertEqual(wire.leaks("x=abc", ["zzabcdzz"], 4), [])
        self.assertEqual(wire.leaks("x=abcd", ["zzabcdzz"], 4, whole=True), [])         # the whole secret is absent
        self.assertEqual(wire.leaks("x=zzabcdzz!", ["zzabcdzz"], 4, whole=True), ["zzabcdzz"])
        self.assertEqual(wire.leaks("x=ab", ["ab"], 4, whole=True), [])                 # shorter secrets are not judged
        self.assertEqual(wire.leaks("\u043f\u0430\u0440\u043e\u043b\u044c", ["\u0430\u0440\u043e\u043b"], 8), ["\u0430\u0440\u043e\u043b"])  # UTF-8 bytes


if __name__ == "__main__":
    unittest.main()
