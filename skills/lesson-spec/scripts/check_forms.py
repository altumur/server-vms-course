"""Формы ADR-0125 п. 2 урока: `forms/daemon-flags.tsv` (флаги демона) и `forms/refusals.tsv` (каталог отказов Н4).

Флаги: форма (колонки, закрытый словарь `type`, `commands`, CEL `required` и `bad` над `f`, `cmd`, `default` байтов целым
и `default_text` той же величины) и согласие с таблицей прозы «Daemon flags» норм урока: тот же набор флагов в том же
порядке, токен типа и `default_text` в ячейках «Type», «Default», `required` ≠ `false` ⇔ «required» в строке,
`commands` ≠ `daemon` ⇔ команды названы в «Meaning».

Отказы: форма (колонки, имена, `surface`, `code`, `kind`) и согласие трёх мест (ADR-0125 доп. (1) п. 5): строки таблиц Н4
глав (число строк, код, вид, поля), `kind` и поля — в `*Fault` OpenAPI урока, код и вид каждой проверки `write-checks.tsv`
есть в каталоге, а строка с именем проверки — с тем же кодом и видом.
"""
import re
from pathlib import Path

import yaml

FLAG_COLUMNS = ["flag", "type", "default", "default_text", "required", "commands", "bad", "norm"]
REF_COLUMNS = ["chapter", "row", "name", "surface", "code", "kind", "fields", "headers", "log", "norm"]
TYPE = re.compile(r"(path|dir|file|addr|id|bool|duration|bytes:>0|int:[0-9]+\.\.[0-9]*|enum:[^|\s]+(?:\|[^|\s]+)+"
                  r"|list:id@addr(?:/addr)?)")
PROSE_TYPE = {"path": "path", "dir": "directory path", "file": "file path", "addr": "host:port", "id": "member id",
              "bool": "no value", "duration": "duration", "bytes": "bytes", "int": "integer", "list": "comma-separated list"}
COMMANDS = {"daemon", "status", "join", "leave", "admit", "backup", "restore", "import", "recover", "rights"}
UNITS = {"KiB": 1024, "MiB": 1024 ** 2, "GiB": 1024 ** 3}
FAULT_KIND = {"BadRequestFault": "badrequest", "BodyTooLargeFault": "toolarge", "ForbiddenFault": "forbidden"}
CELL = re.compile(r"(?<!\\)\|")


def flag_forms(root):
    return sorted(Path(root).glob("Platform/*/forms/daemon-flags.tsv"))


def refusal_forms(root):
    return sorted(Path(root).glob("Platform/*/forms/refusals.tsv"))


def read(path, columns):
    lines = [line for line in Path(path).read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
    errors, rows = [], []
    if not lines or lines[0].split("\t") != columns:
        return [f"{path.name}: columns must be {columns}"], []
    for no, line in enumerate(lines[1:], 2):
        cells = line.split("\t")
        if len(cells) != len(columns):
            errors.append(f"{path.name}: row {no}: {len(cells)} cells, expected {len(columns)}")
            continue
        rows.append(dict(zip(columns, cells)))
    return errors, rows


def cells(row):
    return [c.strip() for c in CELL.split(row.strip().strip("|"))]


def prose_table(text, start):
    """The first Markdown table after the line index `start` → rows of cells (without the header and the rule)."""
    lines = text.split("\n")[start:]
    out, inside = [], False
    for line in lines:
        if line.startswith("|"):
            inside = True
            if not re.match(r"\|\s*-", line):
                out.append(cells(line))
        elif inside:
            break
    return out[1:]


def english_norms(lesson):
    return sorted(p for p in (lesson / "spec").glob("*.norms.md"))


def cel_env():
    """CEL of the flag form: `f`, `cmd`; `loopback(string) -> bool` — only declared here (the host of the address is
    127.0.0.0/8, ::1 or localhost; the implementation is in normgen runtime/prims; ADR-0125 доп. (2) п. 4)."""
    from cel_expr_python import cel
    T = cel.Type
    cfg = cel.NewEnvConfigFromYaml("name: forms\nextensions:\n  - name: strings\n")
    loopback = cel.FunctionDecl("loopback", [cel.Overload("loopback_string", T.BOOL, [T.STRING])])   # declaration only
    return cel.NewEnv(config=cfg, variables={"f": T.Map(T.STRING, T.DYN), "cmd": T.STRING}, functions=[loopback])


def size(text):
    m = re.fullmatch(r"([0-9]+)(KiB|MiB|GiB)?", text)
    return None if not m else int(m[1]) * UNITS.get(m[2] or "", 1)


def check_flags(path):
    path = Path(path)
    errors, rows = read(path, FLAG_COLUMNS)
    stats = {"daemon_flags": len(rows)}
    env = cel_env()
    seen = set()
    for r in rows:
        where = f"{path.name}: {r['flag']}"
        if not re.fullmatch(r"-[a-z][a-z-]*", r["flag"]) or r["flag"] in seen:
            errors.append(f"{where}: the flag is not -name or repeats")
        seen.add(r["flag"])
        if not TYPE.fullmatch(r["type"]):
            errors.append(f"{where}: type {r['type']!r} is not of the closed vocabulary")
        if not set(r["commands"].split(",")) <= COMMANDS:
            errors.append(f"{where}: commands {r['commands']!r} outside {sorted(COMMANDS)}")
        for column in ("required", "bad"):
            if r[column]:
                try:
                    env.compile(r[column])
                except Exception as exc:                       # noqa: BLE001 — the message names the cell
                    errors.append(f"{where}: {column} does not compile: {exc}")
        if r["type"] == "bytes:>0" and r["default"] != "-" and size(r["default"]) != size(r["default_text"]):
            errors.append(f"{where}: default {r['default']} and default_text {r['default_text']} differ")
    norms = [p for p in english_norms(path.parent.parent) if "**Daemon flags**" in p.read_text(encoding="utf-8")]
    if not norms:
        return errors + [f"{path.name}: no norms of the lesson hold the table «Daemon flags»"], stats
    text = norms[0].read_text(encoding="utf-8")
    start = next(i for i, line in enumerate(text.split("\n")) if line.startswith("**Daemon flags**"))
    prose = {}
    order = []
    for c in prose_table(text, start):
        for flag in re.findall(r"`(-[a-z][a-z-]*)`", c[0]):
            prose[flag] = c
            order.append(flag)
    if order != [r["flag"] for r in rows]:
        errors.append(f"{path.name}: flags differ from the prose table of {norms[0].name}: "
                      f"only form {[r['flag'] for r in rows if r['flag'] not in prose]}, "
                      f"only prose {[f for f in order if f not in seen]}, or the order")
    for r in rows:
        c = prose.get(r["flag"])
        if not c or len(c) < 4:
            continue
        where = f"{path.name}: {r['flag']}"
        kind = r["type"].split(":")[0]
        if kind == "enum":
            missing = [v for v in r["type"][5:].split("|") if f"`{v}`" not in c[1]]
            if missing:
                errors.append(f"{where}: enum values {missing} not in the prose type cell")
        elif PROSE_TYPE[kind] not in c[1]:
            errors.append(f"{where}: type {r['type']} — the prose type cell has no «{PROSE_TYPE[kind]}»")
        if r["default"] == "-":
            if not c[2].startswith("none"):
                errors.append(f"{where}: no default, the prose default cell does not start with «none»")
        elif r["default_text"] not in c[2]:
            errors.append(f"{where}: default_text {r['default_text']!r} not in the prose default cell")
        required = "required" in (c[2] + " " + c[3])
        if required != (r["required"] != "false"):
            errors.append(f"{where}: required {r['required']!r}, the prose {'says' if required else 'does not say'} «required»")
        cmds = [x for x in r["commands"].split(",") if x != "daemon"]
        missing = [x for x in cmds if f"`{x}`" not in c[3]]
        if missing:
            errors.append(f"{where}: commands {missing} not named in the prose meaning cell")
        if not cmds and re.search(r"only for `", c[3]):
            errors.append(f"{where}: the prose says «only for …», commands is daemon")
    return errors, stats


def fault_kinds(lesson):
    """kind const → properties of the OpenAPI schemas of the lesson that carry it."""
    out = {}
    for api in (lesson / "spec").glob("*.api.openapi.yaml"):
        schemas = (yaml.safe_load(api.read_text(encoding="utf-8")) or {}).get("components", {}).get("schemas", {})
        for schema in schemas.values():
            props = (schema or {}).get("properties", {}) if isinstance(schema, dict) else {}
            const = (props.get("kind") or {}).get("const") if isinstance(props.get("kind"), dict) else None
            if const:
                out.setdefault(const, set()).update(props)
    return out


def check_refusals(path):
    path = Path(path)
    lesson = path.parent.parent
    errors, rows = read(path, REF_COLUMNS)
    stats = {"refusal_rows": len(rows)}
    names = set()
    for r in rows:
        where = f"{path.name}: {r['chapter']} row {r['row']} {r['name']}"
        if not re.fullmatch(r"[a-z][a-z0-9_]*", r["name"]) or r["name"] in names:
            errors.append(f"{where}: the name is not snake_case or repeats")
        names.add(r["name"])
        if r["surface"] not in ("http", "start", "cli"):
            errors.append(f"{where}: surface {r['surface']!r}")
        if not re.fullmatch(r"[1-5][0-9]{2}|exit 2|exit !0|-", r["code"]):
            errors.append(f"{where}: code {r['code']!r}")
        if r["surface"] == "http" and not re.fullmatch(r"[a-z]+", r["kind"]):
            errors.append(f"{where}: an http refusal needs a kind")
        if r["surface"] != "http" and r["kind"] != "-":
            errors.append(f"{where}: kind of a {r['surface']} refusal is -")
    number = re.match(r"([0-9]{2})-", lesson.name)[1].lstrip("0") if re.match(r"[0-9]{2}-", lesson.name) else ""
    for chapter in sorted({r["chapter"] for r in rows}):
        k = chapter.split(".")[1]
        norms = sorted((lesson / "spec").glob(f"{lesson.name[:2]}.{k}-*.norms.md"))
        if not chapter.startswith(number + ".") or not norms:
            errors.append(f"{path.name}: chapter {chapter}: no norms file of the lesson")
            continue
        text = norms[0].read_text(encoding="utf-8")
        lines = text.split("\n")
        start = next((i for i, line in enumerate(lines) if line.startswith("## Н4")), None)
        if start is None:
            errors.append(f"{path.name}: chapter {chapter}: {norms[0].name} has no Н4")
            continue
        prose = prose_table(text, start)
        mine = [r for r in rows if r["chapter"] == chapter]
        numbers = sorted({int(r["row"]) for r in mine})
        if numbers != list(range(1, len(prose) + 1)):
            errors.append(f"{path.name}: chapter {chapter}: rows {numbers[:3]}…{numbers[-3:]} do not cover the {len(prose)} "
                          f"rows of Н4 of {norms[0].name}")
        for r in mine:
            n = int(r["row"])
            if not 1 <= n <= len(prose):
                continue
            c = prose[n - 1] + ["", "", ""]
            where = f"{path.name}: {chapter} row {n} {r['name']}"
            outcome, words = c[1], c[2]
            if re.fullmatch(r"[0-9]{3}", r["code"]) and r["code"] not in outcome:
                errors.append(f"{where}: code {r['code']} not in the prose cell «{outcome}»")
            if r["code"] == "exit 2" and "code 2" not in outcome and "does not start" not in outcome:
                errors.append(f"{where}: exit 2, the prose cell «{outcome}» says no code 2")
            if r["code"] == "exit !0" and "≠ 0" not in outcome and "refusal" not in outcome:
                errors.append(f"{where}: exit !0, the prose cell «{outcome}» says no refusal")
            if r["kind"] != "-":
                said = re.findall(r"[A-Za-z]+Fault", outcome + " " + words)
                if r["kind"] not in re.findall(r"[a-z]+", outcome + " " + words) and r["kind"] not in [FAULT_KIND.get(s) for s in said]:
                    errors.append(f"{where}: kind {r['kind']} not in the prose row")
            if r["fields"] != "-" and "chapter" not in words:
                missing = [f.rstrip("?") for f in r["fields"].split(",") if f"`{f.rstrip('?')}`" not in words]
                if missing:
                    errors.append(f"{where}: fields {missing} not in the prose cell")
    kinds = fault_kinds(lesson)
    for r in rows:
        if r["surface"] != "http":
            continue
        where = f"{path.name}: {r['chapter']} row {r['row']} {r['name']}"
        if r["kind"] not in kinds:
            errors.append(f"{where}: kind {r['kind']} — no OpenAPI schema of the lesson carries it")
        elif r["fields"] != "-":
            missing = [f.rstrip("?") for f in r["fields"].split(",") if f.rstrip("?") not in kinds[r["kind"]]]
            if missing:
                errors.append(f"{where}: fields {missing} not in the OpenAPI schemas of kind {r['kind']}")
    catalogue = {(r["code"], r["kind"]) for r in rows}
    by_name = {r["name"]: r for r in rows}
    for table in sorted((lesson / "forms").glob("*-checks.tsv")):
        lines = [line.split("\t") for line in table.read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
        head = lines[0] if lines else []
        if not {"check", "code", "kind"} <= set(head):
            continue
        for line in lines[1:]:
            w = dict(zip(head, line))
            if (w["code"], w["kind"]) not in catalogue:
                errors.append(f"{path.name}: {table.name} check {w['check']}: {w['code']} {w['kind']} is not in the catalogue")
            r = by_name.get(w["check"])
            if r and (r["code"], r["kind"]) != (w["code"], w["kind"]):
                errors.append(f"{path.name}: {r['name']}: {r['code']} {r['kind']}, {table.name} says {w['code']} {w['kind']}")
    stats["refusal_chapters"] = len({r["chapter"] for r in rows})
    return errors, stats
