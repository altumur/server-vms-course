"""Судья части `refusals` (ADR-0125 № 4, доп. (1) п. 1): каталог отказов против приёмки и против двери.

Запуск (на CT 103): python tools/normgen/refusal_judge.py [--module-dir <каталог go.mod с refusals и door>] [--json итог]

Три вида проб (только stdlib и go 1.22; модуль по умолчанию — tools/normgen/out/p01-1/go):
- каталог: собранный пакет refusals (обвес tools/normgen/refusals/harness печатает refusals.All) против таблицы
  `forms/refusals.tsv`, прочитанной здесь заново: код, вид, поля, заголовки, лог;
- приёмка (независимый вход): каждое ожидание отказа `<4xx|5xx> {json}` сценариев `acceptance/1..3` находит строку
  каталога с тем же кодом и kind; поля ожидания — по правилу главы: 1.1 сравнивает тело целиком (поля = обязательные
  строки плюс часть необязательных), 1.2 и 1.3 — подмножеством (поля ⊆ поля строки);
- дверь: тело каждой строки http (обязательные поля; все поля) кодирует apidoor.Refuse + apidoor.Encode хотя бы у одной
  операции OpenAPI, строка с Retry-After — с заголовком (две генерации — № 2 и № 4 — согласны).
Отказы по шагам приёмки на заглушке двери — прогон раннера P/01.1 (судья части door), не здесь.
Итог: `refusals: P/N PASS|FAIL`; код 0 — все прошли, 1 — нет, 2 — ошибка запуска судьи.
"""
import argparse
import json
import re
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
TABLE = L.form("refusals.tsv")
ACCEPTANCE = L.path("acceptance")
WHOLE = {"1"}                 # главы, где тело сравнивается целиком (README приёмки 1.1); прочие — подмножеством


def read_table():
    lines = [x for x in TABLE.read_text(encoding="utf-8").splitlines() if not x.startswith("#")]
    cols = lines[0].split("\t")
    rows = []
    for x in lines[1:]:
        r = dict(zip(cols, x.split("\t")))
        fields = [] if r["fields"] == "-" else r["fields"].split(",")
        r["req"] = {f for f in fields if not f.endswith("?")}
        r["opt"] = {f[:-1] for f in fields if f.endswith("?")}
        r["code_n"] = int(r["code"]) if r["code"].isdigit() else (2 if r["code"] == "exit 2" else 1)
        rows.append(r)
    return rows


def harness(module_dir, work):
    hdir = Path(work) / "harness"
    hdir.mkdir()
    shutil.copy(HERE / "refusals/harness/main.go", hdir / "main.go")
    (hdir / "go.mod").write_text(f"module normgen/refusalharness\n\ngo 1.22\n\nrequire {L.go_module} v0.0.0\n\n"
                                 f"replace {L.go_module} => {Path(module_dir).resolve()}\n", encoding="utf-8")
    done = subprocess.run(["go", "run", "."], cwd=hdir, capture_output=True, text=True, timeout=300)
    if done.returncode:
        raise SystemExit(f"refusal_judge: the harness: {done.stderr.strip()}")
    return json.loads(done.stdout)


def expectations():
    """→ [(глава, сценарий, шаг, код, kind, поля)] — ожидания отказов приёмки."""
    out = []
    for ch in sorted(p.name for p in ACCEPTANCE.iterdir() if p.is_dir()):
        for line in (ACCEPTANCE / ch / "scenarios.tsv").read_text(encoding="utf-8").splitlines():
            cells = line.split("\t")
            if len(cells) != 4 or not (m := re.fullmatch(r"([45][0-9]{2}) (\{.*\})", cells[3])):
                continue
            try:
                body = json.loads(m[2])
            except ValueError:
                continue
            if isinstance(body, dict) and "kind" in body:
                out.append((ch, cells[0], cells[1], int(m[1]), body["kind"], set(body) - {"kind", "error"}))
    return out


PLAIN_HARNESS = '''// Harness of refusal_judge.py for a catalogue without an HTTP door: refusals.All as one JSON.
package main

import (
	"encoding/json"
	"os"

	"%s/refusals"
)

func main() { _ = json.NewEncoder(os.Stdout).Encode(refusals.All) }
'''
RUN_EXIT = re.compile(r"^exit (0|[1-9][0-9]*)(;|$)")


def plain(a):
    """Каталог урока без двери (P/02): закрытые колонки таблицы, прочитанной здесь заново, против пакета; каждое
    ожидание `exit N` шага RUN швов приёмки (N ≠ 0) находит строку с этим кодом или «exit !0» (независимый вход)."""
    lines = [x for x in TABLE.read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")]
    cols = lines[0].split("\t")
    rows = [dict(zip(cols, x.split("\t"))) for x in lines[1:]]
    with tempfile.TemporaryDirectory(prefix="refusal-judge-") as work:
        hdir = Path(work) / "harness"
        hdir.mkdir()
        (hdir / "main.go").write_text(PLAIN_HARNESS % L.go_module, encoding="utf-8")
        (hdir / "go.mod").write_text(f"module normgen/refusalharness\n\ngo 1.22\n\nrequire {L.go_module} v0.0.0\n\n"
                                     f"replace {L.go_module} => {Path(a.module_dir).resolve()}\n", encoding="utf-8")
        done = subprocess.run(["go", "run", "."], cwd=hdir, capture_output=True, text=True, timeout=300)
        if done.returncode:
            raise SystemExit(f"refusal_judge: the harness: {done.stderr.strip()}")
        got = json.loads(done.stdout)
    results = []

    def check(name, why):
        results.append({"name": name, "ok": why is None, "why": why})
        if why:
            print(f"FAIL {name}: {why}", flush=True)

    check("catalogue: the same names in order", None if [g["Name"] for g in got] == [r["name"] for r in rows]
          else "the names differ from the table")
    by = {g["Name"]: g for g in got}
    for r in rows:
        g = by.get(r["name"])
        if not g:
            continue
        code = r["code"]
        exit_, anyc, status = -1, code == "exit !0", 0
        if code.startswith("exit ") and code[5:].isdigit():
            exit_ = int(code[5:])
        elif code.isdigit():
            status = int(code)
        logs = [] if r["log"] == "-" else [x.strip() for x in re.findall(r"«[^«»]*»|[^,«»]+", r["log"]) if x.strip()]
        names = [x for x in logs if not x.startswith("«")]
        words = [x[1:-1] for x in logs if x.startswith("«")]
        want_word, want_any = ("" if r["word"] == "-" else r["word"]), []
        if L.key != "02-installer":                     # P/03+: word — ячейка источника; токены `…` — проекция
            toks = re.findall(r"`([^`]+)`", r["word"])
            plain_cell = re.sub(r"`[^`]+`|,|\s", "", r["word"]) == ""
            want_word, want_any = "", []
            if toks and plain_cell:
                want_word, want_any = (toks[0], []) if len(toks) == 1 else ("", toks)
        want_fields = [] if r["fields"] == "-" else [x.strip() for x in r["fields"].split(",")]
        want_headers = [] if r["headers"] == "-" else [[x.strip() for x in h.split(": ", 1)] for h in r["headers"].split(";")]
        diffs = [k for k, ok in (("chapter", g["Chapter"] == r["chapter"]), ("row", g["Row"] == int(r["row"])),
                                 ("surface", g["Surface"] == r["surface"]), ("exit", g["Exit"] == exit_),
                                 ("any", g["AnyNonZero"] == anyc), ("status", g["Status"] == status),
                                 ("word", g["Word"] == want_word), ("named", (g.get("Named") or []) == want_any),
                                 ("word_cell", L.key == "02-installer" or g.get("WordCell") == r["word"]),
                                 ("fields", (g.get("Fields") or []) == want_fields),
                                 ("headers", (g.get("Headers") or []) == want_headers),
                                 ("response", "response_schema" not in r or
                                  g.get("Response") == ("" if r["response_schema"] == "-" else r["response_schema"])),
                                 ("log", (g["Log"] or []) == names), ("words", (g["Words"] or []) == words),
                                 ("norm", g["Norm"] == r["norm"])) if not ok]
        check(f"catalogue {r['name']}", f"differs from the table in {diffs}" if diffs else None)
    codes = {g["Exit"] for g in got if g["Exit"] > 0}
    anyc = any(g["AnyNonZero"] for g in got)
    for seams in sorted(ACCEPTANCE.glob("*/seams.tsv")):
        for line in seams.read_text(encoding="utf-8").splitlines():
            cells = line.split("\t")
            if line.startswith("#") or len(cells) != 4 or not cells[2].startswith("RUN "):
                continue
            m = RUN_EXIT.match(cells[3])
            if not m or m[1] == "0":
                continue
            n = int(m[1])
            check(f"acceptance {seams.parent.name} {cells[0]} step {cells[1]}",
                  None if n in codes or anyc else f"exit {n}: no row of the catalogue with this code or «exit !0»")
    passed = sum(r["ok"] for r in results)
    verdict = "PASS" if passed == len(results) else "FAIL"
    print(f"refusals: {L.code} {passed}/{len(results)} {verdict}")
    if a.json:
        Path(a.json).write_text(json.dumps({"passed": passed, "total": len(results), "verdict": verdict,
                                            "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if verdict == "PASS" else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--module-dir", default=str(L.out / "go"))
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    if not shutil.which("go"):
        print("refusal_judge: go is not in PATH", file=sys.stderr)
        return 2
    head = next(x for x in TABLE.read_text(encoding="utf-8").splitlines() if x and not x.startswith("#"))
    if "word" in head.split("\t"):                         # каталог урока без двери (P/02)
        return plain(a)
    rows = read_table()
    with tempfile.TemporaryDirectory(prefix="refusal-judge-") as work:
        got = harness(a.module_dir, work)
    results = []

    def check(name, why):
        results.append({"name": name, "ok": why is None, "why": why})
        if why:
            print(f"FAIL {name}: {why}", flush=True)

    by = {g["Name"]: g for g in got}
    check("catalogue: the same names in order", None if [g["Name"] for g in got] == [r["name"] for r in rows]
          else f"{[g['Name'] for g in got]} vs the table")
    for r in rows:
        g = by.get(r["name"])
        if not g:
            continue
        fields = {f["Name"]: f["Optional"] for f in g["Fields"] or []}
        want = {**{f: False for f in r["req"]}, **{f: True for f in r["opt"]}}
        headers = [] if r["headers"] == "-" else [h.split(": ", 1) for h in r["headers"].split(";")]
        diffs = [k for k, ok in (("chapter", g["Chapter"] == r["chapter"]), ("row", g["Row"] == int(r["row"])),
                                 ("surface", g["Surface"] == r["surface"]), ("code", g["Code"] == r["code_n"]),
                                 ("kind", g["Kind"] == ("" if r["kind"] == "-" else r["kind"])),
                                 ("fields", fields == want), ("headers", (g["Headers"] or []) == headers),
                                 ("retry", g["RetryAfter"] == any(h[0] == "Retry-After" for h in headers)))
                 if not ok]
        check(f"catalogue {r['name']}", f"differs from the table in {diffs}" if diffs else None)
        if r["surface"] == "http":
            for p in g["probes"]:
                why = None
                if not p["ops"]:
                    why = f"apidoor.Refuse/Encode take the fields {p['fields'] or []} at no operation"
                elif g["RetryAfter"] and not p["retry"]:
                    why = "no operation declares Retry-After for it"
                check(f"door {r['name']} {sorted(p['fields'] or [])}", why)
    http = [r for r in rows if r["surface"] == "http"]
    for ch, sc, step, code, kind, fields in expectations():
        cands = [r for r in http if r["code_n"] == code and r["kind"] == kind]
        if ch in WHOLE:
            ok = any(r["req"] <= fields <= r["req"] | r["opt"] for r in cands)
        else:
            ok = any(fields <= r["req"] | r["opt"] for r in cands)
        check(f"acceptance {ch} {sc} step {step}", None if ok else
              f"{code} {kind} {sorted(fields)}: no row of the catalogue " +
              (f"(rows {[(r['name'], sorted(r['req']), sorted(r['opt'])) for r in cands]})" if cands else
               "with this code and kind"))
    passed = sum(r["ok"] for r in results)
    verdict = "PASS" if passed == len(results) else "FAIL"
    print(f"refusals: {passed}/{len(results)} {verdict}")
    if a.json:
        Path(a.json).write_text(json.dumps({"passed": passed, "total": len(results), "verdict": verdict,
                                            "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
