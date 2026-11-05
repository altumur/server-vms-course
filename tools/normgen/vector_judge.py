"""Судья gate `vectors:<пакет>` (ADR-0126 доп. (1) п. 1, доп. (3) п. 2): команда векторов реализации на входах,
которые построил tools/normgen/gen_tests.py (ADR-0125 № 6). Только stdlib.

Запуск:
  python tools/normgen/vector_judge.py --package jcs --cmd './bin/store vectors {input}' [--cwd <каталог профиля>]
      [--cases <каталог>] [--specs <корень выгрузки>] [--timeout 20] [--json <итог.json>]

- `--package` — аргумент gate (`jcs`, `rights-evaluator`) или полное имя пакета (`01-store/jcs`); входы — в
  `tools/normgen/out/p01-1/vectors/<пакет>/` (`cases.tsv` и `line-<N>.json`), либо в `--cases`.
- `--cmd` — шаблон команды профиля с `{input}` (как запись `vectors` профиля приёмки); исполняется `sh -c` в `--cwd`.
  Каждый вход копируется в свой новый каталог (команда может класть временные файлы рядом с `{input}`).
- Провод — единый провод команды векторов: stdout — один объект `{exit_code, stdout_b64, stderr_b64}`, внешний код 0.
  Нативный исход сверяется с `cases.tsv`: код и stdout как одно значение JSON по значению (тип строго: 1 ≠ 1.0 ≠ true,
  повтор имени и NaN — не JSON).
- `--specs` — сверить sha256 таблиц-источников (`# source … sha256 …` в cases.tsv) с выгрузкой: входы не устарели.
Итог: строка `vectors <пакет>: P/N PASS|FAIL`; код 0 — все строки прошли, 1 — нет, 2 — ошибка запуска судьи.
"""
import argparse
import base64
import binascii
import hashlib
import json
import math
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lesson  # noqa: E402 — урок (ADR-0125 доп. (5) п. 2)
L = lesson.CURRENT
CASES_ROOT = L.out / "vectors"
ALIASES = {"jcs": "01-store/jcs", "rights-evaluator": "01-store/rights-evaluator", "write-checks": "01-store/write-checks"}
ENVELOPE = {"exit_code", "stdout_b64", "stderr_b64"}


class NotJSON(Exception):
    pass


def strict_loads(text):
    def pairs(items):
        keys = [k for k, _ in items]
        if len(keys) != len(set(keys)):
            raise NotJSON("repeated name")
        return dict(items)

    def const(name):
        raise NotJSON(f"{name} is not JSON")

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=const)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise NotJSON(str(exc)) from None


def same(a, b):
    """Равенство значений JSON с учётом вида: bool, int, float, str, list, dict различаются."""
    if type(a) is not type(b):
        return False
    if isinstance(a, float):
        return a == b and math.copysign(1.0, a) == math.copysign(1.0, b)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return a == b


def b64(text, field):
    if not isinstance(text, str):
        raise NotJSON(f"{field} is not a string")
    try:
        data = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        raise NotJSON(f"{field} is not base64") from None
    if base64.b64encode(data).decode("ascii") != text:
        raise NotJSON(f"{field} is not canonical base64")
    return data


def read_cases(cases_dir):
    text = (cases_dir / "cases.tsv").read_text(encoding="utf-8")
    sources, rows, header = [], [], None
    for line in text.split("\n"):
        if line.startswith("# source "):
            parts = line.split()
            sources.append((parts[2], parts[4]))
            continue
        if not line or line.startswith("#"):
            continue
        cells = line.split("\t")
        if header is None:
            if cells != ["case", "input", "exit", "stdout"]:
                raise ValueError(f"{cases_dir}/cases.tsv: header must be case, input, exit, stdout")
            header = cells
            continue
        case, name, code, out = cells
        rows.append({"case": case, "input": cases_dir / name, "exit": int(code), "stdout": strict_loads(out)})
    return sources, rows


def judge_one(row, cmd, cwd, timeout, work):
    """→ None (прошла) или причина."""
    d = Path(tempfile.mkdtemp(prefix=row["case"] + "-", dir=work))
    path = d / "input.json"
    shutil.copyfile(row["input"], path)
    line = cmd.replace("{input}", shlex.quote(str(path)))
    try:
        done = subprocess.run(["sh", "-c", line], cwd=cwd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"timeout {timeout}s"
    if done.returncode != 0:
        tail = done.stderr.decode("utf-8", "replace").strip()[-400:]
        return f"outer exit {done.returncode}: {tail}"
    try:
        env = strict_loads(done.stdout.decode("utf-8"))
        if not isinstance(env, dict) or set(env) != ENVELOPE:
            raise NotJSON(f"envelope must have exactly {sorted(ENVELOPE)}")
        code = env["exit_code"]
        if type(code) is not int or not 0 <= code <= 255:
            raise NotJSON("exit_code is not an integer 0…255")
        out = b64(env["stdout_b64"], "stdout_b64")
        err = b64(env["stderr_b64"], "stderr_b64")
    except (NotJSON, UnicodeDecodeError) as exc:
        return f"answer out of the wire: {exc}: {done.stdout[:300]!r}"
    if code != row["exit"]:
        return f"native exit {code}, want {row['exit']}; stderr {err[-300:]!r}"
    if row["exit"] != 0:
        return None
    try:
        value = strict_loads(out.decode("utf-8"))
    except (NotJSON, UnicodeDecodeError) as exc:
        return f"native stdout is not one JSON value ({exc}): {out[:300]!r}"
    if not same(value, row["stdout"]):
        return (f"native stdout {json.dumps(value, ensure_ascii=False)[:300]}, "
                f"want {json.dumps(row['stdout'], ensure_ascii=False)[:300]}")
    return None


def judge(package, cmd, cwd=".", cases=None, specs=None, timeout=20.0):
    """→ (итог {package, passed, total, failed: [{case, reason}]}, ошибка запуска или None)."""
    package = ALIASES.get(package, package)
    cases_dir = Path(cases) if cases else CASES_ROOT / package
    if not (cases_dir / "cases.tsv").is_file():
        return None, f"no cases.tsv in {cases_dir}"
    sources, rows = read_cases(cases_dir)
    if specs:
        for rel, digest in sources:
            got = hashlib.sha256((Path(specs) / rel).read_bytes()).hexdigest() if (Path(specs) / rel).is_file() else None
            if got != digest:
                return None, f"{rel} in {specs}: sha256 {got}, cases are built from {digest} — run tools/normgen/gen_tests.py"
    failed = []
    with tempfile.TemporaryDirectory(prefix="vector-judge-") as work:
        for row in rows:
            reason = judge_one(row, cmd, cwd, timeout, work)
            if reason:
                failed.append({"case": row["case"], "reason": reason})
    return {"package": package, "passed": len(rows) - len(failed), "total": len(rows), "failed": failed}, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--package", required=True)
    ap.add_argument("--cmd", required=True, help="command template with {input}")
    ap.add_argument("--cwd", default=".")
    ap.add_argument("--cases")
    ap.add_argument("--specs")
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    if "{input}" not in args.cmd:
        print("vector_judge: --cmd has no {input}", file=sys.stderr)
        return 2
    result, error = judge(args.package, args.cmd, args.cwd, args.cases, args.specs, args.timeout)
    if error:
        print(f"vector_judge: {error}", file=sys.stderr)
        return 2
    for f in result["failed"]:
        print(f"FAIL {result['package']} {f['case']}: {f['reason']}")
    ok = not result["failed"] and result["total"] > 0
    print(f"vectors {result['package']}: {result['passed']}/{result['total']} {'PASS' if ok else 'FAIL'}")
    if args.json:
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
