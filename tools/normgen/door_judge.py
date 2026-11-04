"""Мера судьи двери (ADR-0125 доп. (1) п. 1): отчёт раннера P/01.1 на заглушке ядра — только шаги, не зависящие от ядра.

Запуск: python3 tools/normgen/door_judge.py <каталог отчёта раннера (out/report)> [--scenarios <scenarios.tsv>] [--json итог]

Заглушка (tools/normgen/kit/build_stub.py) держит дверь, а не смысл Н3: cas, guard, память id и время допуска — не её.
Шаг зависит от ядра, если запрос или ожидание называет `cas`, `guard`, `"id"`, `not_after`, `not_before`, `again`
или отказ `conflict`, `guard`, `expired`, `early`; и всякий шаг после такого в том же сценарии (состояние хранилища
могло разойтись). Остальные шаги — мера двери: формы ответов, коды отказов разбора, маршруты и методы.
Вторая мера — по тексту самого шага (без хвоста): шаги после шага ядра, сами его не называющие, тоже считаются;
их провал может быть следом ядра — список провалов идёт с текстом раннера. Итог по сценариям: сценарий без шагов ядра — целиком мера; с ними — его шаги до первого шага ядра.
Пробы P/01.1/extra (полный ключ, отпечаток id, личность) и сырые пробы HTTP (рамка — ручная часть, доп. (1) п. 2)
показываются, в меру не идут.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SCENARIOS = ROOT / "Platform/01-store/acceptance/1/scenarios.tsv"
CORE = re.compile(r'"(cas|guard|guards|id|not_after|not_before|again)"\s*:|"kind":\s*"(conflict|guard|expired|early)"')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("report", help="out/report of the runner (P-01.1-door.json, P-01.1-extra.json)")
    ap.add_argument("--scenarios", default=str(SCENARIOS))
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    lines = Path(a.scenarios).read_text(encoding="utf-8").split("\n")
    door = json.loads((Path(a.report) / "P-01.1-door.json").read_text(encoding="utf-8"))
    out, total, passed, core_n, fails = {}, 0, 0, 0, []
    own_total, own_fails = [0, 0], []          # мера по тексту самого шага, без хвоста сценария
    for name, sc in door["scenarios"].items():
        tainted, mine = False, []
        for st in sc["steps"]:
            text = lines[st["line"] - 1] if st.get("line") else ""
            cells = text.split("\t")
            own = bool(CORE.search("\t".join(cells[2:4]) if len(cells) >= 4 else text))
            if not own:
                own_total[0] += 1
                own_total[1] += bool(st["ok"])
                if not st["ok"]:
                    own_fails.append(f"{name} step {st['step']}: {'; '.join(map(str, st.get('why') or []))[:300]}")
            tainted = tainted or own
            if tainted:
                core_n += 1
                continue
            mine.append(st)
            total += 1
            passed += bool(st["ok"])
            if not st["ok"]:
                fails.append(f"{name} step {st['step']}: {'; '.join(map(str, st.get('why') or []))[:300]}")
        out[name] = {"steps": len(sc["steps"]), "door_steps": len(mine), "door_passed": sum(s["ok"] for s in mine),
                     "whole": len(mine) == len(sc["steps"])}
    extra = {}
    path = Path(a.report) / "P-01.1-extra.json"
    if path.is_file():
        e = json.loads(path.read_text(encoding="utf-8"))
        extra = {k: f"{v.get('ok')}/{v.get('total')}" for k, v in (e.get("probes") or {}).items()}
    raw = door.get("raw_http") or []
    extra["raw_http (frame)"] = f"{sum(bool(p.get('ok')) for p in raw)}/{len(raw)}"
    green = [n for n, s in out.items() if s["door_steps"] and s["door_steps"] == s["door_passed"]]
    for f in fails:
        print("FAIL", f)
    for f in own_fails:
        print("FAIL (own text)", f)
    print(f"door (own text of the step, the tail after a core step counted too): {own_total[1]}/{own_total[0]}")
    print(f"door: {passed}/{total} steps independent of the core PASS ({core_n} core steps not counted); "
          f"scenarios green on their door steps {len(green)}/{sum(1 for s in out.values() if s['door_steps'])}"
          f"; whole door-only scenarios {sum(s['whole'] for s in out.values())}; extra probes and raw HTTP, not counted {extra}")
    if a.json:
        Path(a.json).write_text(json.dumps({"passed": passed, "total": total, "core_steps": core_n,
                                            "scenarios": out, "fails": fails, "extra": extra,
                                            "own": {"passed": own_total[1], "total": own_total[0], "fails": own_fails}},
                                           ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
