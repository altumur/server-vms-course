"""Судья части `families` (ADR-0125 № 5, доп. (1) п. 1): чтение семей сгенерированным пакетом против векторов семей.

Запуск (на CT 103): python tools/normgen/family_judge.py [--module-dir <каталог go.mod с families>] [--lesson NN-<имя>]
                    [--runs 3] [--json итог]

Вход — таблица `Platform/common/vectors/family-read/<урок>.tsv` (case family key kind mode who text verdict paths outcome
note; формат — README пакета): каждая строка идёт в обвес tools/normgen/families/harness (пакет families: Judge по ключу,
OutcomesFor по ролям who), сравниваются вердикт, множество путей и исход у каждой роли — строго, как у раннера.
Векторы — эталон диалекта с дельтами набора «Б»; их согласие со стеком В7 проверяет check_spec (family-read), не здесь.
Проход повторяется --runs раз: порядок обхода map в Go случаен (README пакета, D18).
--v7 — второй вход: свои экземпляры судьи (лишний ключ, нестроковые значения, целое и время на границах, ключ не по
шаблону, текст не JSON) поверх базовой строки векторов, ожидание — стек В7 курса (skills/lesson-spec/scripts/v7:
stack.Family, spec.outcomes_for, шаблон ключа), а не генератор; нужен Python с jsonschema (/opt/check-env/lesson-spec).
Итог: `families: P/<урок> N/M PASS|FAIL`; код 0 — все совпали, 1 — нет, 2 — ошибка запуска судьи.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import lesson  # noqa: E402 — урок (ADR-0125 доп. (5) п. 2)
L = lesson.CURRENT
VECTORS = ROOT / "Platform/common/vectors/family-read"
HEADER = ["case", "family", "key", "kind", "mode", "who", "text", "verdict", "paths", "outcome", "note"]


def rows(lesson):
    path = VECTORS / f"{lesson}.tsv"
    lines = [x for x in path.read_text(encoding="utf-8").split("\n") if x]
    if lines[0].split("\t") != HEADER:
        raise SystemExit(f"family_judge: {path}: header is not {HEADER}")
    out = []
    for x in lines[1:]:
        r = dict(zip(HEADER, x.split("\t")))
        r["who"] = json.loads(r["who"])
        r["paths"] = json.loads(r["paths"])
        r["outcome"] = json.loads(r["outcome"])
        out.append(r)
    return out


def harness(module_dir, cases):
    work = Path(tempfile.mkdtemp(prefix="family-judge-"))
    try:
        shutil.copy(HERE / "families/harness/main.go", work / "main.go")
        (work / "go.mod").write_text(f"module normgen/familyharness\n\ngo 1.22\n\nrequire {L.go_module} v0.0.0\n\n"
                                     f"replace {L.go_module} => {Path(module_dir).resolve()}\n", encoding="utf-8")
        build = subprocess.run(["go", "build", "-o", "harness", "."], cwd=work, capture_output=True, text=True,
                               timeout=300)
        if build.returncode:
            raise SystemExit(f"family_judge: the harness does not build: {build.stderr.strip()}")
        stdin = "".join(json.dumps({"family": c["family"], "key": c["key"], "mode": c["mode"], "who": c["who"],
                                    "text": c["text"]}, ensure_ascii=False) + "\n" for c in cases)
        done = subprocess.run([str(work / "harness")], input=stdin, capture_output=True, text=True, timeout=300)
        if done.returncode:
            raise SystemExit(f"family_judge: the harness: {done.stderr.strip()}")
        return [json.loads(x) for x in done.stdout.splitlines()]
    finally:
        shutil.rmtree(work, ignore_errors=True)


def compare(case, got):
    if "error" in got:
        return got["error"]
    if got["verdict"] != case["verdict"] or sorted(got["paths"]) != sorted(case["paths"]) \
            or got["outcome"] != case["outcome"]:
        return (f"expected {case['verdict']} {case['paths']} {json.dumps(case['outcome'], ensure_ascii=False)}, "
                f"got {got['verdict']} {got['paths']} {json.dumps(got['outcome'], ensure_ascii=False)}")
    return None


V7_SCRIPTS = ROOT / "skills/lesson-spec/scripts"


def v7_cases(lesson, base_rows):
    """Свои экземпляры поверх базовой строки каждой семьи; ожидание — стек В7 (Python)."""
    sys.path.insert(0, str(V7_SCRIPTS))
    from v7 import spec, stack                       # noqa: E402 — стек В7 курса
    catalog = spec.read_catalog(ROOT)
    templates, _ = spec.key_templates(ROOT, catalog)
    out = []
    for row in catalog:
        if not (spec.is_v7_family(row) and row["owner"][2:4] == lesson):
            continue
        _, _, doc, _, outcomes = spec.load_family(ROOT, row)
        fam, tmpl = stack.Family(doc, row["kind"]), templates[(row["key"], row["kind"])]
        bases = {r["mode"]: r for r in base_rows if r["family"] == row["key"] and r["note"] == "base"}
        if set(bases) != {"writer", "reader"}:
            raise SystemExit(f"family_judge: {row['key']}: no base rows of both modes in the vectors")
        items = json.loads(bases["writer"]["text"])
        key = bases["writer"]["key"]
        texts = ['"x"', "[]", "{}", "x", json.dumps(dict(items, zz_extra="1")), json.dumps(dict(items, zz_extra=1))]
        for k in items:
            for raw in ("1", "0", "true", "null", '"0"', '"9007199254740991"', '"0.5"', '"1.000"', '"1.123456"',
                        '"-0"', '"01"', '"1e3"', '"1E400"', '"' + "9" * 400 + '"'):
                texts.append("{" + ",".join(json.dumps(x) + ":" + (raw if x == k else json.dumps(v))
                                            for x, v in items.items()) + "}")
        keys = [key, key + "/x", key.rsplit("/", 1)[0] + "/." if "/" in key else key + ".", key.upper()]
        for text in texts:
            for k in keys:
                for mode in ("writer", "reader"):
                    who = bases[mode]["who"]
                    v = spec.judge_family(fam, tmpl, k, row["kind"], text, mode)
                    outcome = ({r: [o.path for o in spec.outcomes_for(outcomes, v["paths"], r)] for r in who}
                               if mode == "reader" else [])
                    out.append({"case": f"v7-{len(out) + 1:04d}", "family": row["key"], "key": k, "kind": row["kind"],
                                "mode": mode, "who": who, "text": text, "verdict": v["verdict"], "paths": v["paths"],
                                "outcome": outcome, "note": f"v7 {k} {text}"})
    return out


def judge(module_dir, lesson=L.nn, runs=3, v7=False):
    cases = rows(lesson)
    if v7:
        cases += v7_cases(lesson, cases)
    bad = {}
    for _ in range(runs):
        answers = harness(module_dir, cases)
        if len(answers) != len(cases):
            raise SystemExit(f"family_judge: {len(answers)} answers to {len(cases)} cases")
        for c, a in zip(cases, answers):
            why = compare(c, a)
            if why and c["case"] not in bad:
                bad[c["case"]] = f"{c['note']}: {why}"
    return {"lesson": lesson, "cases": len(cases), "pass": len(cases) - len(bad), "runs": runs,
            "failures": [{"case": k, "why": v} for k, v in sorted(bad.items())]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--module-dir", default=str(L.out / "go"))
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--v7", action="store_true", help="also own instances judged by the V7 stack of the course")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    try:
        res = judge(a.module_dir, L.nn, a.runs, a.v7)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2
    for f in res["failures"]:
        print(f"FAIL {f['case']}: {f['why']}")
    ok = not res["failures"]
    print(f"families: P/{L.nn} {res['pass']}/{res['cases']} {'PASS' if ok else 'FAIL'} (runs {res['runs']})")
    if a.json:
        Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
