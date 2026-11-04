"""Внешний судья тестов этапов (ADR-0125 доп. (3) п. 4, доп. (4) п. 6): шаги проекции против шагов раннера на том же коде.

Запуск: python3 tools/normgen/scenario_judge.py --inventory <internal/stagetests/inventory.tsv>
            --go-test <вывод go test -json ./internal/stagetests> --runner <out/report раннера> [--stage http] [--json итог]

- опись — по id шага `<глава>/<сценарий>/<шаг>`: переведённые шаги — подтесты `Test<Этап>_<Сценарий>/<шаг>`;
- раннер — отчёт цели P/01.1/door (`P-01.1-door.json`: сценарий → шаги ok);
- шаг совпал, когда исход подтеста (pass | fail) равен исходу шага у раннера; расхождение — дефект генератора (или
  адаптера, если он обходит рамку: такие шаги сверяются отдельно, доп. (4) п. 6); подтест, которого нет в выводе,
  — красный (опись неизменна, доп. (4) п. 5).
Адаптеры-свидетели (кладутся в копию реализации вместо internal/coreadapter/open.go пакета): stagetests/witnesscgo
(свидетель c-go P/01, ADR-0125 доп. (4) п. 6), stagetests/witness16 (16-я попытка MiniMax).
Итог: `stagetests <этап>: совпало N/M (зелёных у раннера R, у тестов T)`; код 0 — все совпали, 1 — нет.
"""
import argparse
import json
import sys
from pathlib import Path

CHAPTER_REPORT = {"1.1": "P-01.1-door.json"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--go-test", required=True)
    ap.add_argument("--runner", required=True)
    ap.add_argument("--stage", action="append", default=[])
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    rows = [line.split("\t") for line in Path(a.inventory).read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")][1:]
    tests = {}
    for line in Path(a.go_test).read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("Action") in ("pass", "fail", "skip") and "/" in (e.get("Test") or ""):
            tests[e["Test"]] = e["Action"]
    runner = {}
    for chapter, name in CHAPTER_REPORT.items():
        path = Path(a.runner) / name
        if path.is_file():
            for sc, body in json.loads(path.read_text(encoding="utf-8"))["scenarios"].items():
                for st in body.get("steps", []):
                    runner[f"{chapter}/{sc}/{st['step']}"] = "pass" if st["ok"] else "fail"
    out, by_stage = [], {}
    for step_id, stage, test, status, _ in rows:
        if status != "translated" or (a.stage and stage not in a.stage):
            continue
        sub = f"{test}/{step_id.rsplit('/', 1)[1]}"
        got, want = tests.get(sub, "missing"), runner.get(step_id, "missing")
        ok = got == want
        s = by_stage.setdefault(stage, {"match": 0, "total": 0, "runner_green": 0, "tests_green": 0})
        s["total"] += 1
        s["match"] += ok
        s["runner_green"] += want == "pass"
        s["tests_green"] += got == "pass"
        out.append({"step": step_id, "stage": stage, "test": sub, "tests": got, "runner": want, "ok": ok})
        if not ok:
            print(f"DIFF {stage} {step_id}: tests {got}, runner {want}")
    for stage, s in by_stage.items():
        print(f"stagetests {stage}: matched {s['match']}/{s['total']} (green: runner {s['runner_green']}, "
              f"tests {s['tests_green']})")
    if a.json:
        Path(a.json).write_text(json.dumps({"stages": by_stage, "steps": out}, ensure_ascii=False, indent=1),
                                encoding="utf-8")
    return 0 if out and all(r["ok"] for r in out) else 1


if __name__ == "__main__":
    sys.exit(main())
