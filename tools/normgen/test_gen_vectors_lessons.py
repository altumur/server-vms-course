"""Тесты части vectors P/03, P/04 (gen_vectors.py по черновику провода wire_p03p04.py; ADR-0125 доп. (5) п. 5).

Запуск: python3 tools/normgen/test_gen_vectors_lessons.py [-v]   (go 1.22)

1. out свежий; состав = consumers.tsv урока (каждая пара — объявление, пакет P/01 через common_vectors или excluded
   с причиной); выбор строк — в описи excluded с причиной.
2. Заглушки — всё красное без паники (кроме family-read — его читает часть families).
3. Подставной адаптер — нативные ответы, выписанные судьёй из таблиц по правилу сравнения README («@absent» опущен,
   «@new»/«@same» — метки, у отказа secret-in — текст без пароля): всё зелёное.
4. Мутанты по правилам — красные: subset (нет ключа), events (поле события), row (лишнее слово), secret (текст с
   паролем), turn (пустая метка вместо новой), vbt-write (лишний ключ), fields (поле из списка), setarrays (повтор),
   raw (байт), stand (код); поле вне списка fields — зелёное (правило не шире README).
"""
import copy
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LESSONS = {"03-worker": "p03", "04-controller": "p04"}
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")


def gv(lesson_key):
    sys.path.insert(0, str(HERE))
    os.environ["NORMGEN_LESSON"] = lesson_key
    import lesson
    lesson.CURRENT = lesson.get(lesson_key)
    import gen_vectors
    return importlib.reload(gen_vectors)


def native(compare, value, state):
    """Ответ, удовлетворяющий правилу, — из ожидания."""
    def drop_absent(v):
        if isinstance(v, dict):
            return {k: drop_absent(x) for k, x in v.items() if x != "@absent"}
        if isinstance(v, list):
            return [drop_absent(x) for x in v]
        return v
    if compare in ("subset", "events"):
        return drop_absent(value)
    if compare == "row":
        out = {"result": value["result"]}
        for k in ("word", "field"):
            if k in value and value[k] != "@absent":
                out[k] = value[k]
        if value["result"] == "ok":
            out["row"] = {k: v for k, v in (value.get("row") or {}).items() if v != "@absent"}
        return out
    if compare == "secret":
        return {"fault": value["fault"], "text": "refused"} if value["fault"] else {"fault": ""}
    if compare == "turn":
        out, current = [], None
        for act in value:
            if isinstance(act, dict) and isinstance(act.get("write"), dict) and act["write"].get("holder") in ("@new", "@same"):
                if act["write"]["holder"] == "@new" or current is None:
                    state["n"] += 1
                    current = f"mark-{state['n']}"
                act = dict(act, write=dict(act["write"], holder=current))
            out.append(act)
        return out
    if compare == "vbt-write":
        if "rowjson" in value:
            return {"status": "ok", "row": json.dumps(value["rowjson"], ensure_ascii=False)}
        return value
    return value


def fake_go(g, mut=None):
    """Подставной адаптер урока: по функции пакета — карта входа в ответ; mut(decl, no, variant, answer) → answer."""
    decls, _ = g.plan(ROOT)
    by_fn = {}
    for d in decls:
        by_fn.setdefault(d["fn"], []).append(d)
    out = ["package vectoradapter", "", "import (", '\t"encoding/json"', '\t"sort"', '\t"strings"', ")", "",
           "func val(s string) any {", "\tvar v any", "\t_ = json.Unmarshal([]byte(s), &v)", "\treturn v", "}", "",
           "func key(table, variant string, cells map[string]string) string {", "\tks := []string{}",
           "\tfor k := range cells {", '\t\tks = append(ks, k+"="+cells[k])', "\t}", "\tsort.Strings(ks)",
           '\treturn table + "|" + variant + "|" + strings.Join(ks, "\\x00")', "}", ""]
    state = {"n": 0}
    for fn, ds in by_fn.items():
        entries = []
        for d in ds:
            pdir, path, rows = g.read_table(ROOT, d)
            if "select" in d:
                rows = [(no, r) for no, r in rows if d["select"](r) is True]
            for no, r, variant, fcells, (code, value, raw), fcompare in g.frames_of(d, rows, pdir):
                compare = fcompare or d["compare"]
                ans = {"code": code, "value": native(compare, value, state) if code == 0 else None, "raw": raw}
                if mut:
                    ans = mut(d, no, variant, compare, ans)
                if d["surface"] == "vectors":
                    cells = fcells if fcells is not None else {c: r[c] for c in d["inputs"]}
                    k = d["table"] + "|" + variant + "|" + "\x00".join(sorted(f"{a}={b}" for a, b in cells.items()))
                else:
                    data = d["input"](r) if callable(d["input"]) else r[d["input"]].encode("utf-8")
                    k = data.decode("utf-8")
                entries.append((k, ans))
        table = ",\n".join(f"\t{g.gstr(k)}: {{Code: {a['code']}, Value: val({g.gstr(json.dumps(a['value'], ensure_ascii=False))})"
                           + (f", Raw: []byte({g.go_bytes(a['raw'])})" if a["raw"] is not None else "") + "}"
                           for k, a in entries)
        out.append(f"var answers{fn} = map[string]Answer{{\n{table},\n}}\n")
        d = ds[0]
        if d["args"] == "cells":
            out.append(f"func {fn}(table string, cells map[string]string, files map[string][]byte) Answer {{\n"
                       f'\treturn answers{fn}[key(table, "", cells)]\n}}\n')
        elif d["args"] == "cells+variant":
            out.append(f"func {fn}(table, variant string, cells map[string]string, files map[string][]byte) Answer {{\n"
                       f"\treturn answers{fn}[key(table, variant, cells)]\n}}\n")
        else:
            out.append(f"func {fn}(input []byte) Answer {{\n\treturn answers{fn}[string(input)]\n}}\n")
    return "\n".join(out), list(by_fn)


def results(mod):
    done = subprocess.run(["go", "test", "-count=1", "-json", "./vectortests/"], cwd=mod, capture_output=True, text=True,
                          env=GOENV)
    res, panics = {}, 0
    for line in done.stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("Action") == "output" and "panic:" in e.get("Output", ""):
            panics += 1
        if e.get("Test") and e["Action"] in ("pass", "fail"):
            res[e["Test"]] = e["Action"]
    res = {t: a for t, a in res.items() if not t.startswith("TestCommon")}   # пакеты P/01 — их судит судья P/01, P/02
    return res, panics, done


class VectorsLessons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        cls.tmp = Path(tempfile.mkdtemp(prefix="vectors-lessons-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def module(self, lesson_key, name, fake=None):
        slug = LESSONS[lesson_key]
        mod = self.tmp / f"{slug}-{name}"
        shutil.copytree(HERE / "out" / slug / "go", mod)
        if fake is not None:
            text, fns = fake
            for fn in fns:
                (mod / "vectoradapter" / f"{fn.lower()}.go").unlink()
            (mod / "vectoradapter/fake.go").write_text(text, encoding="utf-8")
        return mod

    def test_fresh_and_composition(self):
        for lesson_key, slug in LESSONS.items():
            with self.subTest(lesson=lesson_key):
                g = gv(lesson_key)
                files, inv = g.build(ROOT)
                for rel, data in files.items():
                    kept = HERE / "out" / slug / rel
                    self.assertTrue(kept.is_file(), f"{kept} is missing")
                    self.assertEqual(kept.read_bytes(), data, f"{kept} is stale: run gen_vectors.py --lesson {lesson_key}")
                decls, known = g.plan(ROOT)
                declared = {(d["package"], d["table"]) for d in decls} | {(f"common/{n}", t) for n, t in known}
                skipped = set(g.SKIP) | set(g.SKIP_LESSON.get(lesson_key, {}))
                self.assertEqual(g.lesson_consumers(ROOT) - declared - skipped, set())

    def test_stubs_red(self):
        for lesson_key in LESSONS:
            with self.subTest(lesson=lesson_key):
                res, panics, done = results(self.module(lesson_key, "stubs"))
                self.assertEqual(panics, 0, done.stdout[-1500:])
                red = [t for t, a in res.items() if a == "fail" and "FamilyRead" not in t]
                green = [t for t, a in res.items() if a == "pass" and "FamilyRead" not in t]
                self.assertTrue(red)
                self.assertEqual(green, [])

    def test_fake_green(self):
        for lesson_key in LESSONS:
            with self.subTest(lesson=lesson_key):
                g = gv(lesson_key)
                res, panics, done = results(self.module(lesson_key, "fake", fake_go(g)))
                fails = [t for t, a in res.items() if a == "fail"]
                self.assertEqual(fails, [], done.stdout[-3000:])
                self.assertGreater(len(res), 500)

    def mutant(self, lesson_key, name, mut):
        g = gv(lesson_key)
        res, panics, done = results(self.module(lesson_key, f"mut-{name}", fake_go(g, mut)))
        return [t for t, a in res.items() if a == "fail"]

    def test_mutants(self):
        def first(pkg, table, change, compare=None, variant=None):
            hit = {"done": False}

            def mut(d, no, v, cmp, ans):
                if hit["done"] or d["package"] != pkg or d["table"] != table or ans["code"] != 0:
                    return ans
                if (compare and cmp != compare) or (variant is not None and v != variant):
                    return ans
                new = change(copy.deepcopy(ans))
                if new is None:
                    return ans
                hit["done"] = True
                return new
            return mut

        def set_value(f):
            def change(a):
                v = f(a["value"])
                return None if v is None else dict(a, value=v)
            return change

        cases = {
            ("03-worker", "subset-missing"): first("common/domain-token", "cases.tsv",
                                                   set_value(lambda v: {k: x for k, x in v.items() if k != "result"})),
            ("03-worker", "events-field"): first("common/events-merge", "cases.tsv",
                                                 set_value(lambda v: dict(v, events=[dict(e, id="mutant") for e in v["events"]])
                                                           if v.get("events") and "id" in v["events"][0] else None)),
            ("03-worker", "row-extra-word"): first("common/row-check", "cases.tsv",
                                                   set_value(lambda v: dict(v, word="mutant") if v["result"] == "ok" and
                                                             False else (dict(v, result="refused") if v["result"] == "ok" else None))),
            ("03-worker", "secret-leak"): first("common/secret-in", "cases.tsv",
                                                lambda a: None),  # заменяется ниже — нужен скрытый кусок
            ("03-worker", "vbt-extra"): first("common/values-by-type", "cases.tsv",
                                              set_value(lambda v: dict(v, extra=1) if v.get("status") == "ok" else None),
                                              variant="write"),
            ("03-worker", "setarrays-repeat"): first("common/labels", "cases.tsv",
                                                     set_value(lambda v: v + [v[0]] if isinstance(v, list) and v else None)),
            ("03-worker", "raw-byte"): first("03-worker/creates-key", "cases.tsv",
                                             lambda a: dict(a, raw=a["raw"] + b"x")),
            ("03-worker", "stand-code"): first("common/said-id", "said.tsv", lambda a: dict(a, code=2)),
            ("04-controller", "turn-old-mark"): first("common/turn", "cases.tsv", lambda a: None),
            ("04-controller", "fields-listed"): first("common/slot", "cases.tsv",
                                                      set_value(lambda v: dict(v, state="mutant"))),
        }
        g3 = gv("03-worker")

        def leak(d, no, v, cmp, ans):                      # текст отказа повторяет пароль строки
            if leak.done or d["package"] != "common/secret-in" or cmp != "secret":
                return ans
            pdir, path, rows = g3.read_table(ROOT, d)
            r = dict(rows)[no]
            hidden = g3.WIRE["03-worker"] and __import__("wire_p03p04").secret_hidden(r["raw"], r["masked"])
            if not r["fault"] or not hidden:
                return ans
            leak.done = True
            return dict(ans, value={"fault": r["fault"], "text": "bad " + hidden[0]})
        leak.done = False
        cases[("03-worker", "secret-leak")] = leak

        def old_mark(d, no, v, cmp, ans):                  # «@new» — пустая метка вместо новой
            if old_mark.done or d["package"] != "common/turn":
                return ans
            pdir, path, rows = gv("04-controller").read_table(ROOT, d)
            exp = json.loads(dict(rows)[no]["expect"])
            news = [i for i, a in enumerate(exp) if isinstance(a, dict) and isinstance(a.get("write"), dict)
                    and a["write"].get("holder") == "@new"]
            if not news:
                return ans
            acts = copy.deepcopy(ans["value"])
            acts[news[0]]["write"]["holder"] = ""
            old_mark.done = True
            return dict(ans, value=acts)
        old_mark.done = False
        cases[("04-controller", "turn-old-mark")] = old_mark

        for (lesson_key, name), mut in cases.items():
            with self.subTest(mutant=name):
                fails = self.mutant(lesson_key, name, mut)
                self.assertTrue(getattr(mut, "done", True), f"{name}: the mutant does not apply")
                self.assertEqual(len(fails), 1, f"{name}: red {fails}")

        # поле вне списка fields:state (takeable у slot P/04) — правило не шире README: зелёное
        unlisted = first("common/slot", "cases.tsv", set_value(lambda v: dict(v, takeable="mutant") if "takeable" in v else None))
        self.assertEqual(self.mutant("04-controller", "fields-unlisted", unlisted), [])


if __name__ == "__main__":
    unittest.main()
