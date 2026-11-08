#!/usr/bin/env python3
"""Перенос форм P/04 slot-fate.tsv и slot-release.tsv в Quint.

Читает блобы пина (git show), сверяет sha256 и пишет p04_forms.qnt рядом с собой.
Запуск: gen_forms.py [--check] (--check: сверить с уже записанным файлом).
"""
import hashlib, re, subprocess, sys, pathlib

PIN = "959af8d62e7c35ab527fde6e86979b1279ead2ba"
HERE = pathlib.Path(__file__).resolve().parent
REPO = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE, check=True, capture_output=True, text=True).stdout.strip()

FATE = "Platform/04-controller/forms/slot-fate.tsv"
REL = "Platform/04-controller/forms/slot-release.tsv"


def blob(path):
    r = subprocess.run(["git", "show", f"{PIN}:{path}"], cwd=REPO, check=True, capture_output=True)
    return r.stdout


def expr(s):
    """Перевод условий форм в Quint: только идентификаторы/литералы/операторы из форм."""
    t = s.strip()
    t = re.sub(r"!([a-z_]+)", lambda m: f"not({m.group(1)})", t)
    t = t.replace("&&", " and ").replace("||", " or ")
    return t


def version_expr(s):
    s = s.strip()
    if s == '""':
        return "NOVER"
    if s == "version":
        return "version"
    if s == "release_version":
        return "release_version"
    m = re.fullmatch(r"(.+?) \? version : \"\"", s)
    if m:
        return f"if ({expr(m.group(1))}) version else NOVER"
    raise SystemExit(f"unsupported version expression: {s}")


def result(a):
    m = re.fullmatch(r'result\("([a-z_]+)", (.+)\)', a.strip())
    if not m:
        raise SystemExit(f"bad action: {a}")
    return m.group(1), version_expr(m.group(2))


def parse(path):
    data = blob(path).decode()
    rows = []
    for line in data.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if parts[0] == "n":
            header = parts
            continue
        rows.append(dict(zip(header, parts)))
    return data, rows


def main():
    fate_data, fate_rows = parse(FATE)
    rel_data, rel_rows = parse(REL)
    lines = []
    w = lines.append
    w("// СГЕНЕРИРОВАНО gen_forms.py из формы P/04 на пине; не редактировать.")
    w(f"// slot-fate.tsv sha256 {hashlib.sha256(fate_data.encode()).hexdigest()}  ({len(fate_rows)} строк)")
    w(f"// slot-release.tsv sha256 {hashlib.sha256(rel_data.encode()).hexdigest()}  ({len(rel_rows)} строк)")
    w("module p04_forms {")
    w("  pure val SLOT_TERM: int = 45     // slot-fate.tsv: #const SLOT_TERM; Platform/common/contracts/slot.md:45")
    w("  pure val LOST_AFTER: int = 45    // slot-fate.tsv: #const LOST_AFTER; observation.md Freshness")
    w("  pure val NOVER: int = -1         // пустая версия: нет разрешения")
    w("")
    w("  // Результат: (судьба, версия разрешения или NOVER, номер строки формы)")
    w("  pure def slotFate(age: int, slot_readable: bool, worker_fresh: bool, resource: str, presence: str, assigned: bool, server_known: bool, gen_readable: bool, version: int, HUNG_MOVE_AFTER: int): (str, int, int) =")
    body = "(\"judge\", NOVER, 0)"  # no match; formal rows end with "true"
    for r in reversed(fate_rows):
        cond = expr(r["condition"])
        n = int(r["n"])
        if r["action"] == "-":
            then = f'("{r["next"]}", NOVER, {n})'
        else:
            f, v = result(r["action"])
            then = f'("{f}", {v}, {n})'
        body = f"if ({cond}) {then}\n    else {body}"
    w("    " + body)
    w("")
    w("  // Шаг машины release: (состояние, судьба-исход, версия-разрешение, номер строки); нет совпадения — ожидание без действия.")
    w("  pure def slotReleaseStep(state: str, fate: str, gen_readable: bool, age: int, HUNG_MOVE_AFTER: int, version: int, release_version: int, reply: str): (str, str, int, int) =")
    # по состоянию, строки формы в порядке
    states = {}
    for r in rel_rows:
        states.setdefault(r["state"], []).append(r)
    defs = []
    def state_body(st):
        b = f'("{st}", "", NOVER, 0)'
        for r in reversed(states[st]):
            cond = expr(r["condition"])
            n = int(r["n"])
            if r["action"] == "-":
                then = f'("{r["next"]}", "", NOVER, {n})'
            else:
                f, v = result(r["action"])
                then = f'("{r["next"]}", "{f}", {v}, {n})'
            b = f"if ({cond}) {then}\n    else {b}"
        return b
    final = '("' + "done" + '", "", NOVER, 0)'
    for st in reversed(list(states)):
        final = f'if (state == "{st}") ({state_body(st)})\n    else {final}'
    w("    " + final)
    w("}")
    text = "\n".join(lines) + "\n"
    out = HERE / "p04_forms.qnt"
    if "--check" in sys.argv:
        current = out.read_text()
        print("forms-check:", "OK" if current == text else "MISMATCH")
        sys.exit(0 if current == text else 1)
    out.write_text(text)
    print("written", out, "rows", len(fate_rows), len(rel_rows))


if __name__ == "__main__":
    main()
