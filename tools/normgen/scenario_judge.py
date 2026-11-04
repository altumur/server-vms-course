"""Внешний судья тестов этапов (ADR-0125 доп. (3) п. 4, доп. (4) п. 6): шаги проекции против шагов раннера на том же коде.

Запуск: python3 tools/normgen/scenario_judge.py --inventory <internal/stagetests/inventory.tsv>
            --go-test <вывод go test -json ./internal/stagetests> --runner <out/report раннера> [--stage http] [--json итог]

- опись — по id шага `<глава>/<файл>/<сценарий>/<шаг>` (шаги seams.tsv раннер не исполняет — не судятся): переведённые шаги — подтесты `Test<Этап>_<Сценарий>/<шаг>`;
- раннер — отчёт цели P/01.1/door (`P-01.1-door.json`: сценарий → шаги ok);
- шаг совпал, когда исход подтеста (pass | fail) равен исходу шага у раннера; расхождение — дефект генератора (или
  адаптера, если он обходит рамку: такие шаги сверяются отдельно, доп. (4) п. 6); подтест, которого нет в выводе,
  — красный (опись неизменна, доп. (4) п. 5).
Адаптеры-свидетели (кладутся в копию реализации вместо internal/coreadapter/open.go пакета): stagetests/witnesscgo
(свидетель c-go P/01, ADR-0125 доп. (4) п. 6), stagetests/witness16 (16-я попытка MiniMax).
Ожидаемый набор шагов — не из поступивших отчётов, а из сценариев и проекции (gen_stagetests.build по форме дерева
--root): опись должна совпасть с ним строка в строку; раннер должен дать исход каждому шагу scenarios.tsv выбранных
сценариев; прогон go test — завершиться событием пакета. Нет исхода у шага (missing), skip, незавершённый прогон,
отсутствующий или обрезанный отчёт — отрицательный исход, никогда не совпадение (ревью Codex Б1).
Итог: `stagetests <этап>: совпало N/M (зелёных у раннера R, у тестов T)`; код 0 — все совпали, 1 — нет.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen_stagetests  # noqa: E402

CHAPTER_REPORT = {"1.1": "P-01.1-door.json"}
OUTCOMES = ("pass", "fail")


def read_go_test(path):
    """→ ({подтест: pass|fail|skip}, ошибка прогона | None). Прогон годен, когда пакет закончился событием pass|fail."""
    tests, done, bad = {}, None, 0
    p = Path(path)
    if not p.is_file():
        return tests, f"no go test output {path}"
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            bad += 1
            continue
        act, test = e.get("Action"), e.get("Test") or ""
        if act in ("pass", "fail", "skip") and test:
            tests[test] = act
        elif act in ("pass", "fail", "skip") and not test:
            done = act
    if done is None:
        return tests, "go test did not finish (no package event: build failure, crash or a cut output)"
    if done == "skip":
        return tests, "go test skipped the package (no test files)"
    return tests, None


def read_runner(report, wanted):
    """→ ({шаг: pass|fail}, [ошибки]) по отчётам глав из wanted (главы, чьи шаги ждутся)."""
    runner, errs = {}, []
    for chapter in sorted(wanted):
        name = CHAPTER_REPORT.get(chapter)
        if name is None:
            errs.append(f"chapter {chapter}: no runner report is known to the judge")
            continue
        path = Path(report) / name
        if not path.is_file():
            errs.append(f"no runner report {path}")
            continue
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
            for sc, b in body["scenarios"].items():
                for st in b.get("steps", []):
                    runner[f"{chapter}/{sc}/{st['step']}"] = "pass" if st["ok"] is True else "fail"
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            errs.append(f"runner report {path} unreadable: {e!r}")
    return runner, errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--go-test", required=True)
    ap.add_argument("--runner", required=True)
    ap.add_argument("--root", default=str(gen_stagetests.ROOT), help="the course tree whose form gave the inventory")
    ap.add_argument("--stage", action="append", default=[])
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    errs = []
    inv_path = Path(a.inventory)
    rows = []
    if inv_path.is_file():
        rows = [tuple(line.split("\t")) for line in inv_path.read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#")][1:]
    else:
        errs.append(f"no inventory {a.inventory}")
    _, expected = gen_stagetests.build(a.root)
    if a.stage:
        unknown = set(a.stage) - {r[1] for r in expected}
        if unknown:
            errs.append(f"stages without a projection in the form: {sorted(unknown)}")
    if rows != [tuple(r) for r in expected]:
        have, want = set(rows), {tuple(r) for r in expected}
        errs.append(f"inventory differs from the projection of the form: {len(want - have)} rows absent, "
                    f"{len(have - want)} rows extra")
    tests, go_err = read_go_test(a.go_test)
    if go_err:
        errs.append(go_err)
    sel = [r for r in expected if r[3] == "translated" and (not a.stage or r[1] in a.stage)]
    judged = [r for r in sel if r[0].split("/")[1] == "scenarios.tsv"]
    runner, r_errs = read_runner(a.runner, {r[0].split("/")[0] for r in judged})
    errs += r_errs
    out, by_stage, seams = [], {}, len(sel) - len(judged)
    for step_id, stage, test, *_ in judged:
        chapter, _, sc, step = step_id.split("/")
        sub = f"{test}/{step}"
        got, want = tests.get(sub, "missing"), runner.get(f"{chapter}/{sc}/{step}", "missing")
        ok = got == want and got in OUTCOMES      # missing/skip с обеих сторон — не совпадение
        s = by_stage.setdefault(stage, {"match": 0, "total": 0, "runner_green": 0, "tests_green": 0, "absent": 0})
        s["total"] += 1
        s["match"] += ok
        s["runner_green"] += want == "pass"
        s["tests_green"] += got == "pass"
        s["absent"] += got not in OUTCOMES or want not in OUTCOMES
        out.append({"step": step_id, "stage": stage, "test": sub, "tests": got, "runner": want, "ok": ok})
        if not ok:
            print(f"DIFF {stage} {step_id}: tests {got}, runner {want}")
    if not out:
        errs.append("nothing to judge: no translated scenarios.tsv step in the selection")
    for e in errs:
        print("ERROR", e)
    if seams:
        print(f"seams.tsv steps not judged by the runner: {seams}")
    for stage, s in by_stage.items():
        print(f"stagetests {stage}: matched {s['match']}/{s['total']} (green: runner {s['runner_green']}, "
              f"tests {s['tests_green']}; without an outcome {s['absent']})")
    if a.json:
        Path(a.json).write_text(json.dumps({"stages": by_stage, "steps": out, "errors": errs}, ensure_ascii=False,
                                           indent=1), encoding="utf-8")
    return 0 if not errs and all(r["ok"] for r in out) else 1


if __name__ == "__main__":
    sys.exit(main())
