"""Формы ADR-0125 п. 2 урока: `forms/daemon-flags.tsv` (флаги демона) и `forms/refusals.tsv` (каталог отказов Н4).

Флаги: форма (колонки, закрытый словарь `type`, `commands`, CEL `required` и `bad` над `f`, `cmd`, `default` байтов целым
и `default_text` той же величины) и согласие с таблицей прозы «Daemon flags» норм урока: тот же набор флагов в том же
порядке, токен типа и `default_text` в ячейках «Type», «Default», `required` ≠ `false` ⇔ «required» в строке,
`commands` ≠ `daemon` ⇔ команды названы в «Meaning».

Отказы: форма (колонки, имена, `surface`, `code`, `kind`) и согласие трёх мест (ADR-0125 доп. (1) п. 5): строки таблиц Н4
глав (число строк, код, вид, поля), `kind` и поля — в `*Fault` OpenAPI урока, код и вид каждой проверки `write-checks.tsv`
есть в каталоге, а строка с именем проверки — с тем же кодом и видом.
"""
import json
import os
import re
from pathlib import Path

import yaml

FLAG_COLUMNS = ["flag", "type", "default", "default_text", "required", "commands", "bad", "norm"]
REF_COLUMNS = ["chapter", "row", "name", "surface", "code", "kind", "fields", "headers", "log", "norm"]
REF_EXTRA = ["word", "response_schema", "cause", "outcome", "diagnostic", "caller"]   # response_schema — тело http без kind (P/05)   # ячейки Н4, когда форма — сама норма (ADR-0125 доп. (5))
SURFACES = ("http", "start", "cli", "call", "process", "peer")
TYPE = re.compile(r"(path|dir|file|addr|id|bool|string|number|duration|bytes:>0|int:[0-9]+\.\.[0-9]*|enum:[^|\s]+(?:\|[^|\s]+)+"
                  r"|list:id@addr(?:/addr)?)")
PROSE_TYPE = {"path": "path", "dir": "directory path", "file": "file path", "addr": "host:port", "id": "member id",
              "bool": "no value", "string": "string", "number": "number", "duration": "duration", "bytes": "bytes", "int": "integer", "list": "comma-separated list"}
COMMAND = re.compile(r"[a-z][a-z-]*")   # подкоманда урока; сверка — с прозой (ячейка смысла), ADR-0125 доп. (5)
UNITS = {"KiB": 1024, "MiB": 1024 ** 2, "GiB": 1024 ** 3}
FAULT_KIND = {"BadRequestFault": "badrequest", "BodyTooLargeFault": "toolarge", "ForbiddenFault": "forbidden"}
CELL = re.compile(r"(?<!\\)\|")
FLAG_NAME = re.compile(r"--?[a-z][a-z0-9-]*|\$[A-Z][A-Z0-9_]*|<[a-z][a-z0-9-]*>")   # флаг, переменная окружения, позиционный (ADR-0125 доп. (5))
TWO_HYPHENS = {"--from"}      # the name of the prose admin_ops; a rename is a change of the norms (ADR-0125 доп. (2) п. 1)


def flag_forms(root):
    return sorted(Path(root).glob("Platform/*/forms/daemon-flags.tsv"))


def refusal_forms(root):
    return sorted(Path(root).glob("Platform/*/forms/refusals.tsv"))


def read(path, columns, extra=()):
    """Колонки — `columns`, затем по порядку подмножество `extra` (колонки нормы в форме)."""
    lines = [line for line in Path(path).read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
    errors, rows = [], []
    head = lines[0].split("\t") if lines else []
    rest = head[len(columns):]
    if head[:len(columns)] != columns or rest != [c for c in extra if c in rest]:
        return [f"{path.name}: columns must be {columns}" + (f" then some of {list(extra)} in this order" if extra else "")], []
    columns = head
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
        if not (FLAG_NAME.fullmatch(r["flag"]) or r["flag"] in TWO_HYPHENS) or r["flag"] in seen:
            errors.append(f"{where}: the name is not -flag, --flag, $ENV or <arg>, or repeats")
        seen.add(r["flag"])
        if not TYPE.fullmatch(r["type"]):
            errors.append(f"{where}: type {r['type']!r} is not of the closed vocabulary")
        if not all(COMMAND.fullmatch(c) for c in r["commands"].split(",")):
            errors.append(f"{where}: commands {r['commands']!r} — not a list of lowercase command names")
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
        # форма — сама норма (ADR-0125 доп. (1) п. 5, доп. (5)): проза ссылается на неё, сверять не с чем
        if any(f"forms/{path.name}" in p.read_text(encoding="utf-8") for p in english_norms(path.parent.parent)):
            return errors, stats
        return errors + [f"{path.name}: no norms of the lesson hold the table «Daemon flags» or refer to forms/{path.name}"], stats
    text = norms[0].read_text(encoding="utf-8")
    start = next(i for i, line in enumerate(text.split("\n")) if line.startswith("**Daemon flags**"))
    prose = {}
    order = []
    for c in prose_table(text, start):
        for flag in re.findall(r"`(--?[a-z][a-z0-9-]*)`", c[0]):
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


def openapi_schemas(lesson):
    """Имя компонента → схема OpenAPI урока (все *.api.openapi.yaml)."""
    out = {}
    for api in (lesson / "spec").glob("*.api.openapi.yaml"):
        out.update((yaml.safe_load(api.read_text(encoding="utf-8")) or {}).get("components", {}).get("schemas", {}) or {})
    return out


def check_refusals(path):
    path = Path(path)
    lesson = path.parent.parent
    errors, rows = read(path, REF_COLUMNS, REF_EXTRA)
    stats = {"refusal_rows": len(rows)}
    names = set()
    for r in rows:
        where = f"{path.name}: {r['chapter']} row {r['row']} {r['name']}"
        if not re.fullmatch(r"[a-z][a-z0-9_]*", r["name"]) or r["name"] in names:
            errors.append(f"{where}: the name is not snake_case or repeats")
        names.add(r["name"])
        if r["surface"] not in SURFACES:
            errors.append(f"{where}: surface {r['surface']!r}")
        if not re.fullmatch(r"[1-5][0-9]{2}|exit [0-9]+|exit !0|-", r["code"]):
            errors.append(f"{where}: code {r['code']!r}")
        if r["surface"] == "http" and not re.fullmatch(r"[a-z]+", r["kind"]) and \
                not (r["kind"] == "-" and r.get("response_schema")):
            errors.append(f"{where}: an http refusal needs a kind or a response_schema")
        if r["surface"] != "http" and r["kind"] != "-":
            errors.append(f"{where}: kind of a {r['surface']} refusal is -")
    number = re.match(r"([0-9]{2})-", lesson.name)[1].lstrip("0") if re.match(r"[0-9]{2}-", lesson.name) else ""
    for chapter in sorted({r["chapter"] for r in rows}):
        if "." in chapter:
            norms = sorted((lesson / "spec").glob(f"{lesson.name[:2]}.{chapter.split('.')[1]}-*.norms.md"))
            mine_ok = chapter.startswith(number + ".")
        else:                                            # урок одной главой: нормы одним файлом NN-<имя>.norms.md
            norms = sorted((lesson / "spec").glob(f"{lesson.name[:2]}-*.norms.md"))
            mine_ok = chapter == number
        if not mine_ok or not norms:
            errors.append(f"{path.name}: chapter {chapter}: no norms file of the lesson")
            continue
        text = norms[0].read_text(encoding="utf-8")
        lines = text.split("\n")
        start = next((i for i, line in enumerate(lines) if line.startswith(("## Н4", "## N4"))), None)
        if start is None:
            errors.append(f"{path.name}: chapter {chapter}: {norms[0].name} has no Н4")
            continue
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        prose = prose_table("\n".join(lines[:end]), start)      # таблица только своего раздела Н4, не Н5
        mine = [r for r in rows if r["chapter"] == chapter]
        own = not prose                                  # форма — сама норма: код выхода и kind — её ячейки, не слова прозы
        if not prose:
            # Н4 — ссылка на форму (ADR-0125 доп. (1) п. 5, доп. (5)): ячейки нормы — колонки формы
            section = "\n".join(lines[start:end])
            if f"forms/{path.name}" not in section or "outcome" not in (rows[0] if rows else {}):
                errors.append(f"{path.name}: chapter {chapter}: Н4 of {norms[0].name} has no table and no reference to "
                              f"forms/{path.name} with the columns {REF_EXTRA}")
                continue
            first = {}                                      # строка Н4 может стать несколькими строками формы (один row)
            for r in mine:
                if r["row"].isdigit():
                    first.setdefault(int(r["row"]), r)
            prose = [["", first[n]["outcome"], " ".join(first[n].get(k, "") for k in ("word", "cause", "diagnostic", "caller"))]
                     for n in sorted(first)]
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
            if own:
                continue
            if re.fullmatch(r"[0-9]{3}", r["code"]) and r["code"] not in outcome:
                errors.append(f"{where}: code {r['code']} not in the prose cell «{outcome}»")
            if r["code"] == "exit 2" and "code 2" not in outcome and "does not start" not in outcome:
                errors.append(f"{where}: exit 2, the prose cell «{outcome}» says no code 2")
            m_exit = re.fullmatch(r"exit ([0-9]+)", r["code"])
            if m_exit and m_exit[1] != "2" and m_exit[1] not in outcome:
                errors.append(f"{where}: {r['code']}, the prose cell «{outcome}» does not name {m_exit[1]}")
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
    schemas = openapi_schemas(lesson)
    for r in rows:
        if r["surface"] != "http":
            continue
        where = f"{path.name}: {r['chapter']} row {r['row']} {r['name']}"
        if r["kind"] == "-":                             # тело без kind — по названной схеме OpenAPI (ADR-0125 доп. (5))
            name = r.get("response_schema", "")
            fields = [f.rstrip("?") for f in r["fields"].split(",")] if r["fields"] != "-" else []
            if name == "-":
                if fields:
                    errors.append(f"{where}: response_schema - (no body), but fields {r['fields']!r}")
                continue
            sch = schemas.get(name)
            if not isinstance(sch, dict):
                errors.append(f"{where}: response_schema {name!r} — no such component schema in the lesson OpenAPI")
                continue
            props = set((sch.get("properties") or {}))
            missing = [f for f in fields if f not in props]
            if missing:
                errors.append(f"{where}: fields {missing} not in the properties of {name}")
            must = [f for f in (sch.get("required") or []) if f not in [x for x in r["fields"].split(",") if not x.endswith("?")]]
            if must:
                errors.append(f"{where}: required properties {must} of {name} are not named in fields")
            continue
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


KIT_PARTS = {"writecheck", "door", "flags", "refusals", "vectors", "stagetests", "launch",   # ADR-0126 доп. (2) п. 1, доп. (7) п. 4; ADR-0083 доп. (95) п. 3
             "families", "admin", "core", "rollout-poll", "slot-capture",
             "slot-fate", "slot-release"}                                                # машины P/04 (ADR-0125 доп. (5))                                   # ADR-0125 доп. (5)
CH = r"[0-9]+(?:\.[0-9]+)?"          # глава NN.K или урок одной главой NN (P/04, ADR-0125 доп. (5))
GATE = re.compile(rf"tests:({CH}):([^:;\s]+)(:seams)?|accept:({CH}):([^:;\s]+)|vectors:([a-z0-9-]+)|build"
                  rf"|(verdicts|puts):({CH}):([^:;\s]+)")
CASE_TABLE = {"verdicts": "verdicts.tsv", "puts": "puts.tsv"}   # таблицы случаев приёмки (P/02), ADR-0125 доп. (5)


def acceptance_dir(lesson, chapter):
    """Каталог приёмки главы: `acceptance/K` для NN.K, `acceptance` для урока одной главой NN."""
    return lesson / "acceptance" / chapter.split(".")[1] if "." in chapter else lesson / "acceptance"


def stage_forms(root):
    return sorted(Path(root).glob("Platform/*/forms/stages.tsv"))


def check_stage_parts(path):
    """ADR-0126 доп. (4) п. 13: колонки `kit` (этап закрыт пакетом целиком) и `parts` (части, которыми этап пользуется) —
    `-` или перечень через запятую из KIT_PARTS; часть не названа дважды в одной строке; `n` идут по порядку с 1, `depends` —
    `-` или номера прежних этапов (ADR-0126 доп. (1)). Прочую сверку формы этапов ведёт `check_spec` («Архитектор»)."""
    path = Path(path)
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
    head = lines[0].split("\t") if lines else []
    errors = [f"{path.name}: no column {c}" for c in ("stage", "kit", "parts") if c not in head]
    if errors:
        return errors, {}
    lesson = path.parent.parent
    for i, line in enumerate(lines[1:], 1):
        r = dict(zip(head, line.split("\t")))
        if "n" in r and r["n"] != str(i):
            errors.append(f"{path.name}: {r['stage']}: n {r['n']!r} — expected {i}")
        if r.get("depends", "-") != "-" and not all(d.isdigit() and 0 < int(d) < i for d in r["depends"].split(",")):
            errors.append(f"{path.name}: {r['stage']}: depends {r['depends']!r} — not the n of former stages")
        for check in r.get("gate", "").split(";"):
            errors += gate_errors(lesson, r["stage"], check)
        for column in ("kit", "parts"):
            if r[column] == "-":
                continue
            names = r[column].split(",")
            if not set(names) <= KIT_PARTS or len(names) != len(set(names)):
                errors.append(f"{path.name}: {r['stage']}: {column} {r[column]!r} — not a list of {sorted(KIT_PARTS)}")
    return errors, {"stage_rows": len(lines) - 1}


ANCHOR = re.compile(r"^<!-- req: (\S+) -->$", re.M)
TOMBSTONE = re.compile(r"^<!-- removed: (\S+) by ADR-[0-9]{4} -->$", re.M)
REQ = re.compile(r"P/([0-9]{2})(?:\.([0-9]+))?-R([0-9]{3})")   # P/NN.K-RNNN или P/NN-RNNN урока одной главой


def req_lessons(root):
    """Lessons whose English norms carry requirement anchors (ADR-0122 доп. (1) п. 1)."""
    return sorted({p.parent.parent for p in Path(root).glob("Platform/*/spec/*.norms.md")
                   if ANCHOR.search(p.read_text(encoding="utf-8"))})


def check_req_anchors(lesson):
    """Якоря требований урока: номер `P/NN.K-RNNN` по грамматике и главе файла, уникален в уроке, не из надгробий
    `<!-- removed: … by ADR-NNNN -->`; русский перевод `ru/` якорей не несёт (их несёт только источник)."""
    lesson = Path(lesson)
    errors, seen, removed, count = [], {}, set(), 0
    for norms in sorted((lesson / "spec").glob("*.norms.md")):
        text = norms.read_text(encoding="utf-8")
        m = re.match(r"([0-9]{2})(?:\.([0-9]+))?-", norms.name)       # NN.K-<имя> — глава, NN-<имя> — урок одной главой
        removed |= set(TOMBSTONE.findall(text))
        for number in ANCHOR.findall(text):
            count += 1
            g = REQ.fullmatch(number)
            if not g:
                errors.append(f"{norms.name}: anchor {number} is not P/NN.K-RNNN")
            elif not m or (g[1], g[2]) != (m[1], m[2]):          # P/04-RNNN — только в 04-<имя>.norms.md
                errors.append(f"{norms.name}: anchor {number} is not of this chapter")
            if number in seen:
                errors.append(f"{norms.name}: anchor {number} repeats ({seen[number]})")
            seen.setdefault(number, norms.name)
    for number in sorted(removed & set(seen)):
        errors.append(f"{lesson.name}: anchor {number} reuses a removed number")
    for ru in sorted((lesson / "ru").rglob("*.md")) if (lesson / "ru").is_dir() else []:
        if ANCHOR.search(ru.read_text(encoding="utf-8")):
            errors.append(f"{ru.relative_to(lesson)}: a translation carries requirement anchors (only the source does)")
    return errors, {"req_anchors": count}


def gate_errors(lesson, stage, check):
    """ADR-0126 доп. (1) п. 8, доп. (7) пп. 2, 3: одна проверка списка `gate` — закрытый вид без пробелов; глава —
    каталог приёмки урока; сценарии — имена `scenarios.tsv` главы (`seams.tsv` — с `:seams`) или `*`; пакет векторов —
    `vectors/<пакет>` урока или проба формы `forms/<пакет>.probes.tsv`; `verdicts:`/`puts:` — случаи `verdicts.tsv`/`puts.tsv`
    главы (ADR-0125 доп. (5))."""
    m = GATE.fullmatch(check)
    if not m:
        return [f"stages.tsv: {stage}: gate {check!r} is not tests:<chapter>:<scenarios|*>[:seams], accept:…, "
                f"verdicts:<chapter>:<cases|*>, puts:<chapter>:<cases|*>, vectors:… or build"]
    if m[6]:
        if not ((lesson / "vectors" / m[6]).is_dir() or (lesson / "forms" / f"{m[6]}.probes.tsv").is_file()):
            return [f"stages.tsv: {stage}: no vector package {m[6]}"]
        return []
    if check == "build":
        return []
    if m[7]:                                             # verdicts:/puts: — случаи таблицы главы, первая колонка
        chapter, names = m[8], m[9]
        file = acceptance_dir(lesson, chapter) / CASE_TABLE[m[7]]
        if not file.is_file():
            return [f"stages.tsv: {stage}: no {file.relative_to(lesson)} for {m[7]}:{chapter}"]
        if names == "*":
            return []
        known = {ln.split("\t")[0] for ln in file.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")} - {"case"}
        missing = [n for n in names.split(",") if n not in known]
        return [f"stages.tsv: {stage}: cases {missing} are not in {file.relative_to(lesson)}"] if missing else []
    chapter, names, seams = (m[1], m[2], m[3]) if m[1] else (m[4], m[5], None)
    file = acceptance_dir(lesson, chapter) / ("seams.tsv" if seams else "scenarios.tsv")
    if not file.is_file():
        return [f"stages.tsv: {stage}: no {file.relative_to(lesson)} for {check.split(':')[0]}:{chapter}"]
    if names == "*":
        return []
    known = {ln.split("\t")[0] for ln in file.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")}
    missing = [n for n in names.split(",") if n not in known]
    return [f"stages.tsv: {stage}: scenarios {missing} are not in {file.relative_to(lesson)}"] if missing else []


DIRECTIVE = re.compile(r"@clock [+-](?:0|[1-9][0-9]*)(?:\.[0-9]{1,9})?|@reopen|@parallel [2-9]|@parallel [1-9][0-9]+")
OUTCOMES = re.compile(r"each \S.*|one \S.*; rest \S.*")


STAND_PATH = re.compile(r"\$(data|run|manifest)/[^\s\"]+")       # путь стенда: от {data}/{rundir}/{manifest}
FUNCTION = re.compile(r"[a-z][a-z0-9-]*")
RUN_PARTS = ("stdout ", "stdout-text ", "stderr ~")              # части ожидания RUN после exit, в этом порядке


def json_string(text):
    """Строка — ровно одна JSON-строка?"""
    try:
        return isinstance(json.loads(text), str)
    except ValueError:
        return False


def json_text(text):
    try:
        json.loads(text)
        return True
    except ValueError:
        return False


def run_words(text):
    """Слова RUN: через один пробел; слово — без пробела и кавычки, либо JSON-строка → список слов или None."""
    words, i, dec = [], 0, json.JSONDecoder()
    while i < len(text):
        if text[i] == '"':
            try:
                w, j = dec.raw_decode(text, i)
            except ValueError:
                return None
            if not isinstance(w, str):
                return None
        else:
            j = text.find(" ", i)
            j = len(text) if j < 0 else j
            w = text[i:j]
            if not w or '"' in w or "\t" in w:
                return None
        words.append(w)
        if j < len(text):
            if text[j] != " " or j + 1 == len(text):
                return None
            j += 1
        i = j
    return words


def process_step_errors(request, expect):
    """ADR-0125 доп. (5): шаг шва не по HTTP (грамматика генератора stagetests) → ошибки; None — шаг не этого вида."""
    if request.startswith("RUN "):
        words = run_words(request[4:])
        errs = [] if words and len(words) >= 1 else [f"RUN {request[4:]!r}: words are not plain or JSON strings with one space"]
        parts = expect.split("; ")
        if not re.fullmatch(r"exit [0-9]+", parts[0]):
            errs.append(f"RUN expects «exit N» first, got {expect!r}")
        last = -1
        for part in parts[1:]:
            k = next((n for n, pre in enumerate(RUN_PARTS) if part.startswith(pre)), None)
            if k is None or k <= last:
                errs.append(f"RUN expect part {part!r} is not stdout/stdout-text/stderr ~ in this order")
                continue
            last, body = k, part[len(RUN_PARTS[k]):]
            if not (json_text(body) if k == 0 else json_string(body)):
                errs.append(f"RUN expect part {part!r}: {'JSON' if k == 0 else 'a JSON string'} expected")
        return errs
    if request.startswith("CALL "):
        name, _, body = request[5:].partition(" ")
        errs = [] if FUNCTION.fullmatch(name) and json_text(body) else [f"CALL {request[5:]!r}: not <function> <JSON>"]
        if expect not in ("@absent", "@exit 2") and not json_text(expect):
            errs.append(f"CALL expects JSON, @absent or @exit 2, got {expect!r}")
        return errs
    if request.startswith("@file "):
        path, _, src = request[6:].partition(" ")
        errs = [] if STAND_PATH.fullmatch(path) and (re.fullmatch(r"inputs/[^\s\"]+", src) or json_string(src)) else \
            [f"@file {request[6:]!r}: not <$data|$run|$manifest/path> inputs/<file>|<JSON string>"]
        return errs + ([] if expect == "ok" else ["@file expects ok"])
    if request.startswith("@read "):
        errs = [] if STAND_PATH.fullmatch(request[6:]) else [f"@read {request[6:]!r}: not a stand path $data/, $run/, $manifest/"]
        if not (expect == "@absent" or json_text(expect) or (expect.startswith("text ") and json_string(expect[5:]))):
            errs.append(f"@read expects JSON, text <JSON string> or @absent, got {expect!r}")
        return errs
    return None


def seam_files(root):
    """Швы глав (acceptance/K/seams.tsv) и урока одной главой (acceptance/seams.tsv, P/04, P/05)."""
    root = Path(root)
    return sorted(set(root.glob("Platform/*/acceptance/*/seams.tsv")) | set(root.glob("Platform/*/acceptance/seams.tsv")))


def check_seams(path):
    """ADR-0126 доп. (7) п. 1: сценарии над швами процесса — колонки `scenarios.tsv`, шаги подряд с 1, директивы закрыты
    (`@clock ±N`, N — секунды без ведущих нулей, дробь до 9 знаков (как у генератора stagetests), `@reopen`, `@parallel K`, ожидание директивы — `ok`), шаг после `@parallel` ждёт `each …` или
    `one …; rest …`, прочие шаги — нет; имена сценариев не повторяют `scenarios.tsv` главы."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    head = [ln for ln in lines if ln.startswith("#")]
    errors, steps, last, parallel = [], 0, {}, False
    if not head or head[-1] != "# scenario\tstep\trequest\texpect":
        errors.append(f"{path.name}: the last header line must be the columns of scenarios.tsv")
    other = path.parent / "scenarios.tsv"
    known = {ln.split("\t")[0] for ln in other.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")} \
        if other.is_file() else set()
    for no, ln in enumerate(lines, 1):
        if not ln or ln.startswith("#"):
            continue
        cells = ln.split("\t")
        if len(cells) != 4:
            errors.append(f"{path.name}: line {no}: {len(cells)} cells, expected 4")
            continue
        name, step, request, expect = cells
        steps += 1
        if name in known:
            errors.append(f"{path.name}: line {no}: scenario {name} is also in scenarios.tsv")
        if step != str(last.get(name, 0) + 1):
            errors.append(f"{path.name}: line {no}: step {step} of {name}, expected {last.get(name, 0) + 1}")
        last[name] = int(step) if step.isdigit() else last.get(name, 0) + 1
        process = None
        if parallel and OUTCOMES.fullmatch(expect) and request.startswith(("RUN ", "CALL ")):
            subs = [expect[5:]] if expect.startswith("each ") else expect[4:].split("; rest ", 1)
            process = [e for sub in subs for e in process_step_errors(request, sub)]
        elif not parallel:
            process = process_step_errors(request, expect)
        if process is not None:
            errors += [f"{path.name}: line {no}: {e}" for e in process]
            if request.startswith("@file "):
                parallel = False
                continue
        if request.startswith("@") and not request.startswith(("@file ", "@read ")):
            if not DIRECTIVE.fullmatch(request):
                errors.append(f"{path.name}: line {no}: directive {request!r} is not @clock ±N (N — seconds, decimal fraction allowed), @reopen or @parallel K")
            if expect != "ok":
                errors.append(f"{path.name}: line {no}: a directive expects ok")
            if parallel:
                errors.append(f"{path.name}: line {no}: @parallel is followed by a directive")
            parallel = request.startswith("@parallel")
            continue
        if parallel != bool(OUTCOMES.fullmatch(expect)):
            errors.append(f"{path.name}: line {no}: " + ("the step after @parallel expects each … or one …; rest …" if parallel
                                                         else "each/one…rest only after @parallel"))
        parallel = False
    return errors, {"seam_steps": steps}



OPS_COLUMNS = ["command", "process", "prefix", "positionals", "norm"]


def operator_forms(root):
    return sorted(Path(root).glob("Platform/*/forms/operator-commands.tsv"))


def check_operator_commands(path):
    """ADR-0125 доп. (5): грамматика команд оператора урока (P/02) — форма-норма. command уникален и [a-z][a-z-]*;
    (process, prefix) уникальны; prefix — JSON-массив непустых слов; positionals — схема JSON Schema 2020-12 массива строк
    с целыми minItems ≤ maxItems ≥ 0; norm не пуст; каждая команда `commands` формы флагов урока (кроме daemon) — здесь.
    Семантику argv и ОС форма не доказывает."""
    import jsonschema
    path = Path(path)
    errors, rows = read(path, OPS_COLUMNS)
    seen, pairs = set(), set()
    for r in rows:
        where = f"{path.name}: {r['command']}"
        if not COMMAND.fullmatch(r["command"]) or r["command"] in seen:
            errors.append(f"{where}: command is not [a-z][a-z-]* or repeats")
        seen.add(r["command"])
        try:
            prefix = json.loads(r["prefix"])
        except ValueError:
            prefix = None
        if not (isinstance(prefix, list) and all(isinstance(w, str) and w and " " not in w for w in prefix)):
            errors.append(f"{where}: prefix is not a JSON array of non-empty words")
            prefix = []
        key = (r["process"], tuple(prefix))
        if not re.fullmatch(r"[a-z][a-z0-9._-]*", r["process"]) or key in pairs:
            errors.append(f"{where}: process {r['process']!r} with prefix repeats or is not a process name")
        pairs.add(key)
        try:
            schema = json.loads(r["positionals"])
            jsonschema.Draft202012Validator.check_schema(schema)
        except (ValueError, jsonschema.SchemaError) as exc:
            errors.append(f"{where}: positionals is not JSON Schema 2020-12: {str(exc)[:120]}")
            schema = None
        if isinstance(schema, dict):
            lo, hi = schema.get("minItems", 0), schema.get("maxItems")
            items = schema.get("items")
            if schema.get("type") != "array" or not (isinstance(items, dict) and items.get("type") == "string"):
                errors.append(f"{where}: positionals is not an array of strings")
            if not (type(lo) is int and lo >= 0 and (hi is None or (type(hi) is int and hi >= lo))):
                errors.append(f"{where}: minItems/maxItems are not integers 0 ≤ min ≤ max")
        if not r["norm"].strip():
            errors.append(f"{where}: no norm")
    flags = path.parent / "daemon-flags.tsv"
    if flags.is_file():
        _, frows = read(flags, FLAG_COLUMNS)
        used = {c for fr in frows for c in fr["commands"].split(",") if c != "daemon"}
        missing = sorted(used - seen)
        if missing:
            errors.append(f"{path.name}: commands of daemon-flags.tsv not declared here: {missing}")
    return errors, {"operator_commands": len(rows)}


DOOR_ROLE_COLUMNS = ["method", "path", "roles", "norm"]
ROLE = re.compile(r"\*|<sub>worker|[a-z][a-z0-9-]*")


def door_role_forms(root):
    return sorted(Path(root).glob("Platform/*/forms/door-roles.tsv"))


def check_door_roles(path):
    """ADR-0125 доп. (5): роли дверей урока (P/05) — method, path, roles, norm. Метод HTTP, путь — из OpenAPI урока, пара
    (method, path) — операция OpenAPI и не повторяется; roles — через запятую: имя роли, `<sub>worker` (воркер
    загруженного каталога) или `*` (любой аутентифицированный роль пакета); norm не пуст."""
    path = Path(path)
    lesson = path.parent.parent
    errors, rows = read(path, DOOR_ROLE_COLUMNS)
    ops = set()
    for api in (lesson / "spec").glob("*.api.openapi.yaml"):
        for p, item in ((yaml.safe_load(api.read_text(encoding="utf-8")) or {}).get("paths") or {}).items():
            for m in (item or {}):
                if m in ("get", "put", "post", "delete", "patch", "head"):
                    ops.add((m.upper(), p))
    seen = set()
    for r in rows:
        where = f"{path.name}: {r['method']} {r['path']}"
        key = (r["method"], r["path"])
        if key not in ops:
            errors.append(f"{where}: not an operation of the lesson OpenAPI")
        if key in seen:
            errors.append(f"{where}: repeats")
        seen.add(key)
        roles = r["roles"].split(",")
        if not roles or not all(ROLE.fullmatch(x) for x in roles) or len(roles) != len(set(roles)):
            errors.append(f"{where}: roles {r['roles']!r} — not a list of role names, <sub>worker or *")
        if not r["norm"].strip():
            errors.append(f"{where}: no norm")
    return errors, {"door_roles": len(rows)}


WIRE_COLUMNS = ["package", "table", "surface", "header", "inputs", "files", "expect", "compare", "markers", "native", "norm"]
WIRE_COMPARES = ("value", "subset", "raw", "set", "object-sets", "lines-value", "lines-subset")
ASSERT_COMPARES = ("value", "subset", "raw", "set", "object-sets")          # без test — без lines (wire.md «assert»)
ASSERT_TESTS = ("prefix", "absent", "no-leak")      # no-leak — решение «Архитектора» 2026-11-05 поверх wire.md
TURN_COMPARE = "turn"            # решение «Архитектора» 2026-11-06 (P/06 C4): только привязка common/turn, вне WIRE_COMPARES
TURN_BINDING = ("common/turn", "cases.tsv", "vectors")
TURN_MARKS = ("@new", "@same")   # свежесть держателя: новая попытка / текущая попытка; прочие ячейки — точно
NATIVE_WORDS = ("object", "array", "string", "number", "boolean", "null", "value", "bytes")
JSON_TYPES = ("object", "array", "string", "number", "boolean", "null")
FRAMES = ("json", "json-lf", "raw")
WIRE_VARIANT = re.compile(r"(?:[a-z][a-z0-9-]*)?")                          # пустой, read, write или иное имя
STAND_KEY = re.compile(r"stand:[a-z0-9][a-z0-9-]*")
WIRE_PACKAGE = re.compile(r"(common|[0-9]{2}-[a-z0-9-]+)/([a-z0-9][a-z0-9_.-]*)")
PLACE = re.compile(r"\{([^{}]*)\}")
OWNER_WORD = re.compile(r'owner\s*[!=]=\s*"([^"\\]*)"|"([^"\\]*)"\s*[!=]=\s*owner')
DECODES = {"column": ("cell", "json", "text"), "group": ("text", "json", "cell"), "groups": ("text", "json", "cell"),
           "suffix": ("text", "json", "cell"), "file": ("bytes", "text", "json")}
VALUE_KEYS = {"column": {"column", "decode"}, "literal": {"literal"}, "object": {"object"}, "array": {"array"},
              "file": {"file", "decode"}, "group": {"group"}, "groups": {"groups"}, "suffix": {"suffix", "decode"},
              "omit": {"omit"}, "map": {"map"}, "at": {"at", "decode"}}       # decode у at — необязательный, только json
ARG_JSON_KINDS = ("column", "literal", "object", "array")     # внутри arg_file json (wire.md «P/06 transport»: omit, at — нет)
ARG_JSON_DECODES = ("text", "json", "raw-json")
POINTER = re.compile(r"(/([^~/]|~[01])*)+")                   # непустой JSON Pointer RFC 6901 (не root "")


def pointer_get(doc, pointer):
    """Значение по JSON Pointer RFC 6901 → (найдено, значение); индекс массива — 0 или без ведущих нулей."""
    for tok in _pointer_tokens(pointer):
        if isinstance(doc, dict) and tok in doc:
            doc = doc[tok]
        elif isinstance(doc, list) and re.fullmatch(r"0|[1-9][0-9]*", tok) and int(tok) < len(doc):
            doc = doc[int(tok)]
        else:
            return False, None
    return True, doc


def decode_cell(text, decode):
    """Ячейка по decode column: text — строка, json — строгий JSON (ValueError), cell — JSON или исходная строка."""
    if decode == "text":
        return text
    if decode == "cell":
        try:
            return wire_json(text)
        except ValueError:
            return text
    return wire_json(text)


def wire_forms(root):
    return sorted(Path(root).glob("Platform/common/vectors/wire.tsv"))


def lf_lines(path):
    """Строки таблицы векторов строго по LF (`split("\\n")`, без одной завершающей пустой): U+2028, U+0085 и прочие
    разделители `str.splitlines()` — байты ячейки (опубликованный вектор JCS P/01)."""
    lines = Path(path).read_bytes().decode("utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def wire_json(text):
    """Строгий JSON ячейки провода: без BOM, повторов ключей, NaN и Infinity."""
    if text.startswith("\ufeff"):
        raise ValueError("BOM")

    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError(f"duplicate JSON key {key!r}")
            out[key] = value
        return out

    def constant(word):
        raise ValueError(f"not JSON: {word}")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def heading_anchors(path):
    """Якоря заголовков Markdown, как их строит GitHub (как `check_spec.anchors`)."""
    import unicodedata
    from markdown_it import MarkdownIt
    seen, out, level = {}, set(), None
    for tok in MarkdownIt("commonmark").parse(Path(path).read_text(encoding="utf-8")):
        if tok.type == "heading_open":
            level = tok.tag
        elif tok.type == "inline" and level is not None:
            words = "".join(c.content for c in (tok.children or []) if c.type in ("text", "code_inline"))
            base = "".join("-" if ch == " " else ch for ch in words.strip().lower()
                           if ch in "-_ " or unicodedata.category(ch)[0] in "LNM")
            n = seen.get(base, 0)
            seen[base] = n + 1
            out.add(base if n == 0 else f"{base}-{n}")
            level = None
    return out


def wire_cel_env():
    """CEL выбора строк провода: `row: map<string,string>`, `owner: string`, расширение strings (wire.md)."""
    from cel_expr_python import cel
    T = cel.Type
    cfg = cel.NewEnvConfigFromYaml("name: wire\nextensions:\n  - name: strings\n")
    # json(string) -> dyn (P/06): один строгий JSON-документ; отказ разбора — ошибка данных формы, не false
    parse = cel.FunctionDecl("json", [cel.Overload("json_string", T.DYN, [T.STRING], impl=wire_json)])
    return cel, cel.NewEnv(config=cfg, variables={"row": T.Map(T.STRING, T.STRING), "owner": T.STRING}, functions=[parse])


def vector_rows(path, names, positional):
    """Строки таблицы векторов по LF: пустые и `#` пропущены; с шапкой — первая прочая строка равна `names`. →
    (ошибки, [(номер физической строки, {имя: ячейка})])."""
    errors, rows, head = [], [], positional
    for no, line in enumerate(lf_lines(path), 1):
        if not line or line.startswith("#"):
            continue
        cells = line.split("\t")
        if not head:
            head = True
            if cells != names:
                errors.append(f"header {','.join(names)} differs from the table header {','.join(cells)}")
            continue
        if len(cells) != len(names):
            errors.append(f"{path.name} line {no}: {len(cells)} fields, the header has {len(names)}")
            continue
        rows.append((no, dict(zip(names, cells))))
    if not head:
        errors.append(f"{path.name} has no header line")
    return errors, rows


class _Errors:
    """Ошибки одной привязки: одно сообщение — один раз, со списком физических строк таблицы."""

    def __init__(self, where):
        self.where, self.lines = where, {}

    def add(self, message, line=None):
        lines = self.lines.setdefault(message, [])
        if line is not None and line not in lines:
            lines.append(line)

    def out(self):
        res = []
        for message, lines in self.lines.items():
            tail = ""
            if lines:
                tail = f" (line {', '.join(map(str, lines[:5]))}" + (f" and {len(lines) - 5} more" if len(lines) > 5 else "") + ")"
            res.append(f"{self.where}: {message}{tail}")
        return res


def _keys(obj, allowed, required, what, err):
    if not isinstance(obj, dict):
        err.add(f"{what} is not an object")
        return False
    extra, missing = sorted(set(obj) - set(allowed)), sorted(set(required) - set(obj))
    if extra or missing:
        err.add(f"{what}: keys {sorted(obj)} — unknown {extra}, missing {missing}")
        return False
    return True


def _pointer_tokens(p):
    return [t.replace("~1", "/").replace("~0", "~") for t in p.split("/")[1:]]


def _ignore_shape(items, err, what):
    """ignore (P/06): непустой массив JSON Pointer без root "", без повторов и перекрытий (один — префикс другого)."""
    if not isinstance(items, list) or not items or not all(isinstance(p, str) for p in items):
        err.add(f"{what}: ignore is not a nonempty array of JSON Pointers")
        return
    for p in items:
        if not re.fullmatch(r"(/([^~/]|~[01])*)+", p):
            err.add(f"{what}: ignore {p!r} is not a non-root JSON Pointer")
    if len(set(items)) != len(items):
        err.add(f"{what}: ignore repeats a pointer")
    toks = [_pointer_tokens(p) for p in set(items)]
    if any(a != b and b[:len(a)] == a for a in toks for b in toks):
        err.add(f"{what}: ignore pointers overlap (one is a prefix of another)")


def _value_shape(expr, cols, err, what, field=False, suffix=False, argfile=False, in_map=False):
    """ValueExpr: ровно один конструктор закрытого списка, ключи и decode; column — из header. `argfile` — внутри
    arg_file json (только column, literal, object, array; decode raw-json — только здесь), `in_map` — value у map
    (вычисляется по одной строке: без group, groups, map). → использует group?"""
    if not isinstance(expr, dict):
        err.add(f"{what}: a ValueExpr is not an object")
        return False
    kinds = [k for k in expr if k in VALUE_KEYS]
    if len(kinds) != 1 or not (set(expr) == VALUE_KEYS[kinds[0]] or (kinds[0] == "at" and set(expr) == {"at"})):
        err.add(f"{what}: not exactly one ValueExpr constructor of the closed list with its keys: {sorted(expr)}")
        return False
    kind, grouped = kinds[0], False
    if argfile and kind not in ARG_JSON_KINDS:
        err.add(f"{what}: {kind} is not a constructor of arg_file json (column, literal, object, array)")
        return False
    if in_map and kind in ("group", "groups", "map"):
        err.add(f"{what}: {kind} inside a map value, which is evaluated on one row")
        return False
    if argfile and kind == "column" and expr["decode"] not in ARG_JSON_DECODES:
        err.add(f"{what}: decode {expr['decode']!r} of a column in arg_file json is not one of {list(ARG_JSON_DECODES)}")
    elif kind == "column" and expr["decode"] == "raw-json":
        if not argfile:
            err.add(f"{what}: decode raw-json is allowed only inside arg_file json")
    elif kind == "at":
        if expr.get("decode", "json") != "json":
            err.add(f"{what}: the outer decode of at is only json")
        if _keys(expr["at"], {"value", "pointer"}, {"value", "pointer"}, f"{what}.at", err):
            v, p = expr["at"]["value"], expr["at"]["pointer"]
            if not (isinstance(p, str) and POINTER.fullmatch(p)):
                err.add(f"{what}.at: pointer {p!r} is not a nonempty RFC 6901 JSON Pointer starting with /")
            elif not (isinstance(v, dict) and [k for k in v if k in VALUE_KEYS] in (["column"], ["literal"])):
                err.add(f"{what}.at: value is only a column or literal ValueExpr (nested at and others are forbidden)")
            else:
                _value_shape(v, cols, err, f"{what}.at.value")
                if "literal" in v:
                    found, sel = pointer_get(v["literal"], p)
                    if not found:
                        err.add(f"{what}.at: pointer {p} is missing in the literal")
                    elif "decode" in expr:
                        try:
                            if not isinstance(sel, str):
                                raise ValueError("not a string")
                            wire_json(sel)
                        except ValueError as exc:
                            err.add(f"{what}.at: the selected value is not a strict JSON string ({str(exc)[:60]})")
    elif kind in DECODES and kind not in ("group", "groups") and expr["decode"] not in DECODES[kind]:
        err.add(f"{what}: decode {expr['decode']!r} of {kind} is not one of {list(DECODES[kind])}")
    if kind == "column" and expr["column"] not in cols:
        err.add(f"{what}: column {expr['column']!r} is not in header")
    elif kind == "object":
        if not isinstance(expr["object"], dict):
            err.add(f"{what}: object is not a map of fields")
        else:
            for name, sub in expr["object"].items():
                grouped |= _value_shape(sub, cols, err, f"{what}.{name}", field=True, suffix=suffix, argfile=argfile,
                                        in_map=in_map)
    elif kind == "array":
        if not isinstance(expr["array"], list):
            err.add(f"{what}: array is not a list")
        else:
            for i, sub in enumerate(expr["array"]):
                grouped |= _value_shape(sub, cols, err, f"{what}[{i}]", suffix=suffix, argfile=argfile, in_map=in_map)
    elif kind == "file":
        _file_shape(expr["file"], cols, err, f"{what}.file", path_column=True)
    elif kind in ("group", "groups"):
        grouped = True
        need = {"column", "decode"} | ({"by"} if kind == "groups" else set())
        if _keys(expr[kind], need, need, f"{what}.{kind}", err):
            for key in need - {"decode"}:
                if expr[kind][key] not in cols:
                    err.add(f"{what}.{kind}: {key} {expr[kind][key]!r} is not in header")
            if expr[kind]["decode"] not in DECODES[kind]:
                err.add(f"{what}: decode {expr[kind]['decode']!r} of {kind} is not one of {list(DECODES[kind])}")
    elif kind == "map":
        grouped = True
        if _keys(expr["map"], {"key", "value"}, {"key", "value"}, f"{what}.map", err):
            if expr["map"]["key"] not in cols:
                err.add(f"{what}.map: key {expr['map']['key']!r} is not in header")
            _value_shape(expr["map"]["value"], cols, err, f"{what}.map.value", suffix=suffix, in_map=True)
            if expr["map"]["value"] == {"omit": True}:
                err.add(f"{what}.map: omit is never a map value")
    elif kind == "suffix" and (expr["suffix"] is not True or not suffix):
        err.add(f"{what}: suffix is true only in a value of a prefix marker")
    elif kind == "omit" and (expr["omit"] is not True or not field):
        err.add(f"{what}: omit is true only as an object field")
    return grouped


def _file_shape(spec, cols, err, what, path_column=False):
    keys = {"base", "path", "path_column"} if path_column else {"base", "path", "when"}
    if not isinstance(spec, dict) or not set(spec) <= keys or "base" not in spec or \
            (path_column and len({"path", "path_column"} & set(spec)) != 1) or (not path_column and "path" not in spec):
        err.add(f"{what}: not {{base, path{'|path_column' if path_column else ', when?'}}}")
        return
    if spec["base"] not in ("package", "root"):
        err.add(f"{what}: base {spec['base']!r} is not package|root")
    if "path_column" in spec and spec["path_column"] not in cols:
        err.add(f"{what}: path_column {spec['path_column']!r} is not in header")
    if "path" in spec:
        p = spec["path"]
        if not isinstance(p, str) or not p or p.startswith("/") or PLACE.sub("", p).count("{") or PLACE.sub("", p).count("}"):
            err.add(f"{what}: path {p!r} is not a relative path with {{column}} substitutions")
        else:
            for name in PLACE.findall(p):
                if name not in cols:
                    err.add(f"{what}: substitution {{{name}}} is not a column of header")


def _assert_shape(items, cols, err, what, suffix=False):
    grouped = False
    if not isinstance(items, list):
        err.add(f"{what}: assert is not an array")
        return False
    for i, a in enumerate(items):
        w = f"{what}.assert[{i}]"
        if not _keys(a, {"pointer", "test", "value", "decode", "compare", "min_bytes", "whole", "ignore"}, {"pointer"}, w, err):
            continue
        if "ignore" in a:
            if a.get("test") is not None:
                err.add(f"{w}: ignore is only of an assertion without test")
            else:
                _ignore_shape(a["ignore"], err, w)
        if not isinstance(a["pointer"], str) or not re.fullmatch(r"(/([^~/]|~[01])*)*", a["pointer"]):
            err.add(f"{w}: pointer {a['pointer']!r} is not a JSON Pointer")
        test = a.get("test")
        if test is not None and test not in ASSERT_TESTS:
            err.add(f"{w}: test {test!r} is not {'|'.join(ASSERT_TESTS)}")
        if test == "no-leak":                              # только грамматика: утечку исполняет судья, не форма
            if set(a) - {"whole"} != {"pointer", "test", "value", "min_bytes"}:
                err.add(f"{w}: no-leak takes exactly pointer, value, min_bytes and optional whole")
            if "whole" in a and not isinstance(a["whole"], bool):
                err.add(f"{w}: whole is not boolean")
            if "min_bytes" in a and (type(a["min_bytes"]) is not int or a["min_bytes"] < 1):
                err.add(f"{w}: min_bytes is not an integer ≥ 1")
            v = a.get("value") if isinstance(a.get("value"), dict) else {}
            lits = [v["literal"]] if "literal" in v else \
                [x["literal"] for x in v["array"] if isinstance(x, dict) and "literal" in x] if isinstance(v.get("array"), list) else []
            if not all(isinstance(x, str) or ("literal" in v and isinstance(x, list) and all(isinstance(y, str) for y in x))
                       for x in lits):
                err.add(f"{w}: no-leak value is not a string or an array of strings")
        elif "min_bytes" in a or "whole" in a:
            err.add(f"{w}: min_bytes and whole are only of no-leak")
        if test == "absent" and set(a) != {"pointer", "test"}:
            err.add(f"{w}: absent takes only pointer")
        if test == "prefix" and ("value" not in a or "compare" in a):
            err.add(f"{w}: prefix requires value and no compare")
        if test is None and "value" not in a:
            err.add(f"{w}: a comparison without test requires value")
        if "compare" in a and a["compare"] not in ASSERT_COMPARES:
            err.add(f"{w}: compare {a['compare']!r} is not one of {list(ASSERT_COMPARES)}")
        if "decode" in a and a["decode"] != "json":
            err.add(f"{w}: decode {a['decode']!r} is not json")
        if "value" in a:
            grouped |= _value_shape(a["value"], cols, err, f"{w}.value", suffix=suffix)
    return grouped


def _native_shape(d, err, what, in_array):
    if not _keys(d, {"type", "frame", "schema", "variant", "when"}, {"type", "frame"} | ({"variant"} if in_array else set()),
                 what, err):
        return
    t = d["type"]
    if not (t in NATIVE_WORDS or (isinstance(t, list) and t and all(x in JSON_TYPES for x in t) and len(set(t)) == len(t))):
        err.add(f"{what}: type {t!r} is not a listed word or an array of JSON type words")
    if d["frame"] not in FRAMES:
        err.add(f"{what}: frame {d['frame']!r} is not json|json-lf|raw")
    if (t == "bytes") != (d["frame"] == "raw") or (t == "bytes" and "schema" in d):
        err.add(f"{what}: bytes requires frame raw without schema, raw is only for bytes")
    if "schema" in d:
        import jsonschema
        try:
            jsonschema.Draft202012Validator.check_schema(d["schema"])
        except jsonschema.SchemaError as exc:
            err.add(f"{what}: schema is not Draft 2020-12: {str(exc)[:100]}")


def short(text, n=100):
    """Длинная ячейка в сообщении — началом и длиной."""
    return repr(text) if len(text) <= n else repr(text[:n]) + f"… ({len(text)} chars)"


def lesson_dirs(root):
    """Каталоги уроков `Platform/lessons.tsv` (вторая колонка строк без `#`)."""
    return {ln.split("\t")[1] for ln in lf_lines(Path(root) / "Platform/lessons.tsv") if ln and not ln.startswith("#")}


CONSUMER_COLUMNS = ["package", "table", "lesson", "norm"]


def consumers(root):
    """`consumers.tsv` (wire.md «consumer set») → (ошибки, {(package, table): [lesson, …]}). package — полный путь
    `(common|NN-name)/name` без vectors/, NN-name — урок lessons.tsv; повтор (package, table, lesson), неизвестный
    урок, пакет или таблица — ошибка формы."""
    out, errors, seen = {}, [], set()
    path = Path(root) / "Platform/common/vectors/consumers.tsv"
    lessons = lesson_dirs(root)
    lines = [(no, ln) for no, ln in enumerate(lf_lines(path), 1) if ln and not ln.startswith("#")]
    if not lines or lines[0][1].split("\t") != CONSUMER_COLUMNS:
        return [f"{path.name}: columns must be {CONSUMER_COLUMNS}"], out
    for no, line in lines[1:]:
        c = line.split("\t")
        if len(c) != len(CONSUMER_COLUMNS):
            errors.append(f"{path.name}: row {no}: {len(c)} cells, expected {len(CONSUMER_COLUMNS)}")
            continue
        package, table, lesson = c[:3]
        m = WIRE_PACKAGE.fullmatch(package)
        if not m or (m[1] != "common" and m[1] not in lessons) or not (Path(root) / "Platform" / m[1] / "vectors" / m[2]).is_dir():
            errors.append(f"{path.name}: row {no}: package {package!r} is not an existing (common|NN-name)/name of lessons.tsv")
        elif "/" in table or not table.endswith(".tsv") or not (Path(root) / "Platform" / m[1] / "vectors" / m[2] / table).is_file():
            errors.append(f"{path.name}: row {no}: table {table!r} is not a TSV file of {package}")
        if lesson not in lessons:
            errors.append(f"{path.name}: row {no}: lesson {lesson!r} is not a directory of lessons.tsv")
        if (package, table, lesson) in seen:
            errors.append(f"{path.name}: row {no}: ({package}, {table}, {lesson}) repeats")
        seen.add((package, table, lesson))
        out.setdefault((package, table), []).append(lesson)
    return errors, out


def _decoded(text, decode, err, what, line):
    if decode in ("json", "raw-json"):
        try:
            wire_json(text)
        except ValueError as exc:
            err.add(f"{what}: the cell is not strict JSON ({str(exc)[:60]})", line)


def check_wire(path):
    """Форма провода векторов `Platform/common/vectors/wire.tsv` (wire.md; ADR-0125 доп. (1) п. 5, доп. (5)): 11 колонок
    литеральным TAB, тройка (package, table, surface) единственна, пакет и таблица существуют, header — шапка таблицы
    (или число позиционных полей), JSON-ячейки строгие по закрытым конструкторам, column — из header, when — CEL;
    затем по каждой строке таблицы и каждому потребителю: не больше одного входа варианта, у выбранного варианта ровно
    одно ожидание и один native (группы — после фильтра when, when согласны по группе), файлы есть, run identity
    единственна."""
    path = Path(path)
    root = path.parents[3]
    platform = root / "Platform"
    errors, stats = [], {"wire_bindings": 0, "wire_calls": 0, "wire_excluded": 0}
    try:
        lines = lf_lines(path)
    except (OSError, UnicodeError) as exc:
        return [f"{path.name}: unreadable: {exc}"], stats
    text = path.read_bytes()
    if text.startswith(b"\xef\xbb\xbf") or b"\r" in text:
        errors.append(f"{path.name}: BOM or CR — the form is UTF-8 with LF")
    body = [(no, ln) for no, ln in enumerate(lines, 1) if ln and not ln.startswith("#")]
    if not body or body[0][1].split("\t") != WIRE_COLUMNS:
        return errors + [f"{path.name}: columns must be {WIRE_COLUMNS}"], stats
    cel, env = wire_cel_env()
    cerr, owners_of = consumers(root)
    errors += cerr
    seen = set()
    for no, line in body[1:]:
        cells = line.split("\t")
        if len(cells) != len(WIRE_COLUMNS):
            errors.append(f"{path.name}: row {no}: {len(cells)} cells, expected {len(WIRE_COLUMNS)}")
            continue
        stats["wire_bindings"] += 1
        r = dict(zip(WIRE_COLUMNS, cells))
        err = _Errors(f"{path.name}: row {no} {r['package']} {r['table']} {r['surface']}")
        _check_binding(r, root, platform, env, cel, owners_of, seen, err, stats)
        errors += err.out()
    return errors, stats


def _check_binding(r, root, platform, env, cel, owners_of, seen, err, stats):
    triple = (r["package"], r["table"], r["surface"])
    if triple in seen:
        err.add("the triple (package, table, surface) repeats")
    seen.add(triple)
    surface = r["surface"]
    layout, stand = surface == "layout", surface.startswith("stand:")
    if not (surface in ("vectors", "layout") or STAND_KEY.fullmatch(surface)):
        err.add(f"surface {surface!r} is not vectors, stand:<key> or layout")
        return
    m = WIRE_PACKAGE.fullmatch(r["package"])
    pkg = platform / m[1] / "vectors" / m[2] if m else None
    if not m or not pkg.is_dir() or (m[1] != "common" and m[1] not in lesson_dirs(root)):
        err.add(f"package {r['package']!r} is not <lesson>/<name> of an existing Platform/<lesson>/vectors/<name>")
        return
    table = pkg / r["table"]
    if "/" in r["table"] or not r["table"].endswith(".tsv") or not table.is_file():
        err.add(f"table {r['table']!r} is not an existing TSV file of the package")
        return
    norm, _, anchor = r["norm"].partition("#")
    npath = platform / norm
    if not norm.endswith(".md") or not npath.is_file() or Path(norm).parts[0] == "ru" or \
            Path(norm).parts[1:2] in (("ru",), ("journal",)):          # ru/ и journal/ урока — не в выгрузке (ADR-0124)
        err.add(f"norm {r['norm']!r} is not an existing source .md path from Platform")
    elif "#" in r["norm"] and anchor not in heading_anchors(npath):
        err.add(f"norm anchor #{anchor} is not a heading of {norm}")
    names = r["header"].split(",")
    positional = names[0] == "-"
    cols = names[1:] if positional else names
    if not cols or not all(cols) or len(set(cols)) != len(cols) or "-" in cols:
        err.add(f"header {r['header']!r} is not a list of unique column names")
        return
    terr, rows = vector_rows(table, cols, positional)
    for e in terr:
        err.add(e)
    if terr:
        return
    parsed = {}
    for column in ("inputs", "files", "expect", "markers") + (() if layout else ("native",)):
        try:
            parsed[column] = wire_json(r[column])
        except ValueError as exc:
            err.add(f"{column} is not strict JSON: {str(exc)[:80]}")
    if layout:
        if parsed.get("inputs") != [] or parsed.get("expect") != [] or parsed.get("markers") != [] or \
                parsed.get("files") != {} or r["compare"] != "-" or r["native"] != "-":
            err.add("layout requires inputs, expect, markers [], files {}, compare and native -")
        return
    if len(parsed) != 5:
        return
    inputs, files, expect, markers, native = (parsed[c] for c in ("inputs", "files", "expect", "markers", "native"))
    whens = {}

    def when_of(obj, what):
        w = obj.get("when", "true")
        if not isinstance(w, str):
            err.add(f"{what}: when is not a CEL string")
            return None
        if w not in whens:
            try:
                prog = env.compile(w)
                if prog.return_type() not in (cel.Type.BOOL, cel.Type.DYN):    # dyn — через json(); значение судит ev
                    raise ValueError(f"type {prog.return_type()}, not bool")
                whens[w] = prog
            except Exception as exc:                       # noqa: BLE001 — the message names the cell
                err.add(f"{what}: when {short(w)} does not compile to a bool CEL: {str(exc).splitlines()[0][:160]}")
                whens[w] = None
        return w if whens[w] else None

    # inputs
    if not isinstance(inputs, list) or not inputs:
        err.add("inputs is not a nonempty array")
        return
    decls, variants = [], []
    for i, d in enumerate(inputs):
        what = f"inputs[{i}]"
        if not _keys(d, {"variant", "when", "case", "cells", "arg_file", "group_by"}, {"variant"}, what, err):
            continue
        ok = True
        if not isinstance(d["variant"], str) or not WIRE_VARIANT.fullmatch(d["variant"]):
            err.add(f"{what}: variant {d['variant']!r} is not a variant name")
            ok = False
        if ("cells" in d) == ("arg_file" in d) or ("cells" in d) == stand:
            err.add(f"{what}: exactly one of cells (vectors) or arg_file (stand:<key>)")
            ok = False
        if "cells" in d:
            if not isinstance(d["cells"], dict):                  # {} — функция без аргументов (P/06 fault)
                err.add(f"{what}: cells is not a map")
                ok = False
            else:
                for name, src in d["cells"].items():
                    if not (isinstance(src, dict) and len(src) == 1 and (
                            (isinstance(src.get("column"), str) and src["column"] in cols)
                            or isinstance(src.get("literal"), str))):
                        err.add(f"{what}: cell {name!r} is not {{column: <header>}} or {{literal: <string>}}")
                        ok = False
        if "arg_file" in d:
            a = d["arg_file"]
            if not (isinstance(a, dict) and (
                    (set(a) == {"column"} and a["column"] in cols) or (set(a) == {"literal"} and isinstance(a["literal"], str))
                    or (set(a) == {"path_column", "base"} and a["path_column"] in cols and a["base"] in ("package", "root"))
                    or set(a) == {"json"})):
                err.add(f"{what}: arg_file is not {{column}}, {{literal}}, {{path_column, base}} or {{json}} over header")
                ok = False
            elif "json" in a:
                n = len(err.lines)
                _value_shape(a["json"], cols, err, f"{what}.arg_file.json", argfile=True)
                if a["json"] == {"omit": True}:
                    err.add(f"{what}.arg_file.json: omit is never a root value")
                ok = ok and len(err.lines) == n
        if "case" in d:
            c = d["case"]
            if not (c in cols or c == {"line": True} or (isinstance(c, dict) and set(c) == {"literal"} and isinstance(c["literal"], str)
                                                          and c["literal"])):
                err.add(f"{what}: case {c!r} is not a header column, {{line: true}} or {{literal}}")
                ok = False
        if "group_by" in d and not (isinstance(d["group_by"], list) and all(g in cols for g in d["group_by"])
                                     and len(set(d["group_by"])) == len(d["group_by"])):
            err.add(f"{what}: group_by is not an array of header columns")
            ok = False
        w = when_of(d, what)
        if ok and w:
            decls.append((i, d, w))
        if isinstance(d.get("variant"), str) and d["variant"] not in variants:
            variants.append(d["variant"])
    # files
    if not isinstance(files, dict) or (stand and files):
        err.add("files is not a map" + (" ({} on a stand surface)" if stand else ""))
        files = {}
    filedecl = []
    for name, spec in files.items():
        what = f"files.{name}"
        if not name or "/" in name or name in (".", ".."):
            err.add(f"{what}: not a basename")
        _file_shape(spec, cols, err, what)
        if isinstance(spec, dict):
            filedecl.append((name, spec, when_of(spec, what)))
    # expect, markers, compare, native
    grouped_variants = set()
    if not isinstance(expect, list):
        err.add("expect is not an array")
        expect = []
    exps = []
    for i, e in enumerate(expect):
        what = f"expect[{i}]"
        if not _keys(e, {"variant", "when", "code", "value", "assert", "ignore"}, {"variant", "code", "value"}, what, err):
            continue
        if "ignore" in e:
            _ignore_shape(e["ignore"], err, what)
        if e["variant"] not in variants:
            err.add(f"{what}: variant {e['variant']!r} has no input declaration")
        if type(e["code"]) is not int or not 0 <= e["code"] <= 255:
            err.add(f"{what}: code is not an integer 0..255")
        g = _value_shape(e["value"], cols, err, f"{what}.value")
        if e["value"] == {"omit": True}:
            err.add(f"{what}: omit is never a root value")
        g |= _assert_shape(e.get("assert", []), cols, err, what)
        if g:
            grouped_variants.add(e["variant"])
        exps.append((e, when_of(e, what)))
    if not isinstance(markers, list):
        err.add("markers is not an array")
        markers = []
    marks = []
    for i, mk in enumerate(markers):
        what = f"markers[{i}]"
        if not _keys(mk, {"variant", "column", "match", "prefix", "code", "ignore_stdout", "value", "compare", "assert"},
                     {"variant", "column", "match"}, what, err):
            continue
        if mk["variant"] not in variants:
            err.add(f"{what}: variant {mk['variant']!r} has no input declaration")
        if mk["column"] not in cols:
            err.add(f"{what}: column {mk['column']!r} is not in header")
        if not isinstance(mk["match"], str) or not mk["match"]:
            err.add(f"{what}: match is not a nonempty string")
        for key in ("prefix", "ignore_stdout"):
            if key in mk and not isinstance(mk[key], bool):
                err.add(f"{what}: {key} is not boolean")
        if "code" in mk and (type(mk["code"]) is not int or not 0 <= mk["code"] <= 255):
            err.add(f"{what}: code is not an integer 0..255")
        if "compare" in mk and mk["compare"] not in WIRE_COMPARES:
            err.add(f"{what}: compare {mk['compare']!r} is not of the closed list")
        g = False
        if "value" in mk:
            g = _value_shape(mk["value"], cols, err, f"{what}.value", suffix=mk.get("prefix") is True)
            if mk["value"] == {"omit": True}:
                err.add(f"{what}: omit is never a root value")
        g |= _assert_shape(mk.get("assert", []), cols, err, what, suffix=mk.get("prefix") is True)
        if g:
            grouped_variants.add(mk["variant"])
        marks.append(mk)
    compare = r["compare"]
    if compare == TURN_COMPARE:
        compares = {v: TURN_COMPARE for v in variants}
        _turn_form(r, inputs, expect, markers, err)
    elif compare in WIRE_COMPARES:
        compares = {v: compare for v in variants}
    else:
        try:
            compares = wire_json(compare)
        except ValueError:
            compares = None
        if not (isinstance(compares, dict) and all(c in WIRE_COMPARES for c in compares.values())
                and set(compares) == set(variants)):
            err.add(f"compare {compare!r} is not one of {list(WIRE_COMPARES)} or a map of every variant to one")
            compares = {}
    natives = native if isinstance(native, list) else [native]
    nats = []
    for i, d in enumerate(natives):
        what = f"native[{i}]" if isinstance(native, list) else "native"
        _native_shape(d, err, what, isinstance(native, list))
        if isinstance(d, dict):
            if "variant" in d and d["variant"] not in variants:
                err.add(f"{what}: variant {d['variant']!r} has no input declaration")
            nats.append((d, when_of(d, what)))
    for v in grouped_variants:
        if any("group_by" not in d for _, d, _ in decls if d["variant"] == v):
            err.add(f"variant {v!r}: group, groups or map requires group_by on its input declarations")
    # потребители — явные строки consumers.tsv и урок-владелец пакета урока; у common неявного урока нет (wire.md)
    owner_set = ([] if r["package"].startswith("common/") else [r["package"].split("/")[0]])
    owner_set += [n for n in owners_of.get((r["package"], r["table"]), []) if n not in owner_set]
    if not owner_set:
        err.add("no consumer of the table in consumers.tsv")
        return
    for name in sorted({a or b for w in whens for a, b in OWNER_WORD.findall(w)}):
        if name not in owner_set:
            err.add(f"when names {name!r}, not a consumer of the table (consumers.tsv or the owner lesson)")
    if err.lines:                                          # строки судятся только по годной форме привязки
        return
    _check_rows(r, rows, cols, decls, filedecl, exps, marks, nats, compares, whens, owner_set, pkg, root, err, stats)


def _turn_form(r, inputs, expect, markers, err):
    """compare=turn (решение «Архитектора» 2026-11-06): только common/turn cases.tsv vectors; каждый вход выбран явным
    CEL-селектором when; ожидание — сама колонка JSON без ignore, assert и подмен значения; markers пусты."""
    if (r["package"], r["table"], r["surface"]) != TURN_BINDING:
        err.add(f"compare turn is only for the binding {' '.join(TURN_BINDING)}")
        return
    if markers != []:
        err.add("compare turn: markers must be []")
    for i, d in enumerate(inputs if isinstance(inputs, list) else []):
        if isinstance(d, dict) and not isinstance(d.get("when"), str):
            err.add(f"compare turn: inputs[{i}] needs an explicit CEL selector when over owner and kind")
    for i, e in enumerate(expect if isinstance(expect, list) else []):
        if not isinstance(e, dict):
            continue
        if "ignore" in e or "assert" in e:
            err.add(f"compare turn: expect[{i}] has no ignore or assert; every cell compares exactly")
        v = e.get("value")
        if not (isinstance(v, dict) and set(v) == {"column", "decode"} and v["decode"] == "json"):
            err.add(f"compare turn: expect[{i}].value is exactly {{column, decode json}}, no holder or value alias")


def _turn_marks(value, err, what, line):
    """Свежесть в ожидании compare=turn: строка на «@» — только значение holder, только @new или @same, @same — после
    @new того же случая; прочие значения сравниваются точно (литеральный holder подписанта — тоже)."""
    seen_new = False

    def walk(v, key):
        nonlocal seen_new
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, k)
        elif isinstance(v, list):
            for x in v:
                walk(x, None)
        elif isinstance(v, str) and v.startswith("@"):
            if key != "holder":
                err.add(f"{what}: freshness mark {v!r} outside holder (no alias)", line)
            elif v not in TURN_MARKS:
                err.add(f"{what}: unknown freshness mark {v!r}, not one of {list(TURN_MARKS)}", line)
            elif v == "@same" and not seen_new:
                err.add(f"{what}: @same before any @new of the case", line)
            seen_new = seen_new or v == "@new"
    walk(value, None)


def turn_match(expected, actual):
    """Сравнение compare=turn одного случая (решение «Архитектора» 2026-11-06): структура и все ячейки — точно, кроме
    значения holder с меткой. @new — настоящая метка попытки, не литерал «@…» и не равная ни одной прежней @new случая;
    @same — равна последней @new. Возвращает список расхождений (пустой — совпало)."""
    news, out = [], []

    def walk(e, a, at):
        if isinstance(e, dict):
            if not isinstance(a, dict) or set(a) != set(e):
                out.append(f"{at or '/'}: keys {sorted(a) if isinstance(a, dict) else type(a).__name__} != {sorted(e)}")
                return
            for k in e:
                sub = f"{at}/{k}"
                if k == "holder" and e[k] in TURN_MARKS:
                    if not isinstance(a[k], str) or not a[k] or a[k].startswith("@"):
                        out.append(f"{sub}: {a[k]!r} is not a real attempt label")
                    elif e[k] == "@new":
                        if a[k] in news:
                            out.append(f"{sub}: @new {a[k]!r} repeats an earlier @new of the case")
                        news.append(a[k])
                    elif not news or a[k] != news[-1]:
                        out.append(f"{sub}: @same {a[k]!r} is not the last @new {news[-1] if news else None!r}")
                else:
                    walk(e[k], a[k], sub)
        elif isinstance(e, list):
            if not isinstance(a, list) or len(a) != len(e):
                out.append(f"{at or '/'}: array length differs")
                return
            for i, (x, y) in enumerate(zip(e, a)):
                walk(x, y, f"{at}/{i}")
        elif type(e) is not type(a) and not (type(e) in (int, float) and type(a) in (int, float)) or e != a:
            out.append(f"{at or '/'}: {a!r} != {e!r}")
    walk(expected, actual, "")
    return out


def _check_rows(r, rows, cols, decls, filedecl, exps, marks, nats, compares, whens, owner_set, pkg, root, err, stats):
    """По каждой строке и потребителю: выбор, группы, ровно одно ожидание и native, файлы, run identity."""
    def ev(w, row, owner, line):
        if w is None:
            return None
        val = whens[w].eval(data={"row": row, "owner": owner}).value()
        if not isinstance(val, bool):
            err.add(f"when {short(w)} does not evaluate to a bool on the row (json() of a non-JSON cell is a data error): {str(val)[:80]}", line)
            return None
        return val

    def agree(values, what, line):
        vals = set(values)
        if len(vals) > 1:
            err.add(f"{what}: when differs across the rows of a group", line)
            return None
        return vals.pop() if vals else None

    def resolve(base, rel, what, line, decode=None):
        start = pkg if base == "package" else root
        full = Path(os.path.normpath(start / rel))
        if Path(rel).is_absolute() or not (full == root or root in full.parents):
            err.add(f"{what}: {rel!r} escapes the export", line)
            return
        if not full.is_file():
            err.add(f"{what}: {rel!r} is not an existing file", line)
            return
        try:
            data = full.read_bytes()
            if decode in ("text", "json"):
                data.decode("utf-8")
            if decode == "json":
                wire_json(data.decode("utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            err.add(f"{what}: {rel!r} is unreadable as {decode}: {str(exc)[:60]}", line)

    def constant(values, what, line):
        if len(set(values)) > 1:
            err.add(f"{what} is not constant across the group", line)
        return values[0]

    def subst(p, group):
        return [PLACE.sub(lambda m: row[m[1]], p) for _, row in group]

    def values(expr, group, what, line, suffix=None):
        """Чтение ValueExpr по строкам группы: decode json — строгий JSON, column — постоянна, file — есть."""
        if not isinstance(expr, dict):
            return
        if "column" in expr:
            cell = constant([row[expr["column"]] for _, row in group], f"{what} column {expr['column']}", line)
            _decoded(cell, expr["decode"], err, what, line)
        elif "object" in expr:
            for name, sub in expr["object"].items():
                values(sub, group, f"{what}.{name}", line, suffix)
        elif "array" in expr:
            for i, sub in enumerate(expr["array"]):
                values(sub, group, f"{what}[{i}]", line, suffix)
        elif "file" in expr:
            f = expr["file"]
            rel = constant(subst(f["path"], group) if "path" in f else [row[f["path_column"]] for _, row in group],
                           f"{what} file path", line)
            resolve(f["base"], rel, what, line, expr["decode"])
        elif "group" in expr or "groups" in expr:
            g = expr.get("group") or expr["groups"]
            for no, row in group:
                _decoded(row[g["column"]], g["decode"], err, what, no)
        elif "suffix" in expr and suffix is not None:
            _decoded(suffix, expr["decode"], err, what, line)
        elif "at" in expr and "column" in expr["at"]["value"]:     # указатель — по фактическим строкам таблицы
            src = expr["at"]["value"]
            cell = constant([row[src["column"]] for _, row in group], f"{what} at column {src['column']}", line)
            try:
                found, sel = pointer_get(decode_cell(cell, src["decode"]), expr["at"]["pointer"])
                if not found:
                    err.add(f"{what}: at pointer {expr['at']['pointer']} is missing in column {src['column']}", line)
                elif "decode" in expr:
                    if not isinstance(sel, str):
                        raise ValueError("the selected value is not a string")
                    wire_json(sel)
            except ValueError as exc:
                err.add(f"{what}: at over column {src['column']}: {str(exc)[:80]}", line)
        elif "map" in expr:                                # ключ — сырая ячейка строки, повтор — ошибка данных
            keys = [row[expr["map"]["key"]] for _, row in group]
            dup = sorted({k for k in keys if keys.count(k) > 1})
            if dup:
                err.add(f"{what}: map key {dup[0]!r} repeats in a group", line)
            for no, row in group:
                values(expr["map"]["value"], [(no, row)], f"{what}.map", no, suffix)

    identities = set()
    for owner in owner_set:
        calls = []                                         # (decl, [(no,row)…])
        chosen = {i: [] for i, _, _ in decls}
        for no, row in rows:
            taken = {}
            for i, d, w in decls:
                if ev(w, row, owner, no):
                    taken.setdefault(d["variant"], []).append(i)
                    chosen[i].append((no, row))
            for v, idx in taken.items():
                if len(idx) > 1:
                    err.add(f"owner {owner}: inputs {idx} of variant {v!r} select one row", no)
            if not taken:
                stats["wire_excluded"] += 1
        for i, d, w in decls:
            if "group_by" not in d:
                calls += [(d, [x]) for x in chosen[i]]
                continue
            groups = {}
            for no, row in chosen[i]:
                groups.setdefault(tuple(row[c] for c in d["group_by"]), []).append((no, row))
            for key in sorted(groups, key=lambda k: [x.encode("utf-8") for x in k]):
                calls.append((d, groups[key]))
        for d, group in calls:
            v, line = d["variant"], group[0][0]
            stats["wire_calls"] += 1
            c = d.get("case")
            if c is None:
                c = "case" if "case" in cols else "id" if "id" in cols else {"line": True}
            if c == {"line": True}:
                case = constant([f"line-{no}" for no, _ in group], "case line", line)
            elif isinstance(c, dict):
                case = c["literal"]
            else:
                case = constant([row[c] for _, row in group], f"case column {c}", line)
            ident = (owner, r["package"], r["table"], r["surface"], v, case)
            if ident in identities:
                err.add(f"owner {owner}: run identity variant {v!r} case {case!r} repeats", line)
            identities.add(ident)
            for name, src in (d.get("cells") or {}).items():
                if "column" in src:
                    constant([row[src["column"]] for _, row in group], f"cell {name}", line)
            a = d.get("arg_file") or {}
            if "column" in a:
                constant([row[a["column"]] for _, row in group], "arg_file column", line)
            if "path_column" in a:
                resolve(a["base"], constant([row[a["path_column"]] for _, row in group], "arg_file path", line),
                        "arg_file", line)
            if "json" in a:
                values(a["json"], group, "arg_file json", line)
            for name, spec, w in filedecl:
                if w is not None and agree([ev(w, row, owner, no) for no, row in group], f"files.{name}", line):
                    resolve(spec["base"], constant(subst(spec["path"], group), f"files.{name} path", line),
                            f"files.{name}", line)
            hit = [e for e, w in exps if e["variant"] == v and agree([ev(w, row, owner, no) for no, row in group],
                                                                      "expect", line)]
            if len(hit) != 1:
                err.add(f"owner {owner}: variant {v!r} has {len(hit)} expectations, not exactly one", line)
            nat = [nd for nd, w in nats if nd.get("variant", v) == v and agree(
                [ev(w, row, owner, no) for no, row in group], "native", line)]
            if len(nat) != 1:
                err.add(f"owner {owner}: variant {v!r} has {len(nat)} native descriptors, not exactly one", line)
            if r["package"] == "common/pool" and owner == "06-console" and len(hit) == 1 and \
                    (hit[0].get("ignore") != ["/fates"] or compares.get(v) != "value"):
                err.add('console pool: ignore is exactly ["/fates"] with compare value (wire.md «P/06 transport»)', line)
            if v not in compares:
                continue
            if compares[v] == TURN_COMPARE and len(hit) == 1:
                col = hit[0]["value"]["column"]
                for no, row in group:
                    try:
                        _turn_marks(wire_json(row[col]), err, f"compare turn column {col}", no)
                    except ValueError as exc:
                        err.add(f"compare turn column {col}: not strict JSON: {str(exc)[:80]}", no)
            found = []
            for no, row in group:
                first = next((k for k, mk in enumerate(marks) if mk["variant"] == v and (
                    row[mk["column"]].startswith(mk["match"]) if mk.get("prefix") else row[mk["column"]] == mk["match"])), None)
                found.append(first)
            first = found[0] if len(set(found)) == 1 else None
            if len(set(found)) > 1:
                err.add(f"owner {owner}: markers match differently across the rows of a group", line)
            if len(hit) != 1:
                continue
            mk = marks[first] if first is not None else {}
            suffix = group[0][1][mk["column"]][len(mk["match"]):] if mk.get("prefix") else None
            if mk.get("ignore_stdout"):
                continue
            values(mk.get("value", hit[0]["value"]), group, f"expect of variant {v!r}", line, suffix)
            for k, item in enumerate(mk.get("assert", hit[0].get("assert", []))):
                if isinstance(item, dict) and "value" in item:
                    values(item["value"], group, f"assert[{k}]", line, suffix)


ROUTE_METHODS = ("get", "put", "post", "delete", "patch", "head", "options")


def route_lessons(root):
    """Уроки, чей OpenAPI несёт расширения маршрутизации (x-route-priority, x-path-*), ADR-0125 доп. (5), P/05."""
    out = []
    for api in sorted(Path(root).glob("Platform/*/spec/*.api.openapi.yaml")):
        text = api.read_text(encoding="utf-8")
        if "x-route-priority" in text or "x-path-" in text or "x-query-lexeme" in text:
            out.append(api)
    return out


LEXEME_TYPE = {"number": "number", "integer": "integer", "uint64": "string"}   # parse → schema.type (P/05 x-query-lexeme)


def query_lexeme_errors(pw, p):
    """x-query-lexeme у параметра запроса (P/05, forms/README «Numeric query lexemes»): pattern — полный якорный regex,
    parse number|integer|uint64, strip — только "_" и только при number; schema.type согласован с parse."""
    q = p["x-query-lexeme"]
    if p.get("in") != "query":
        return [f"{pw}: x-query-lexeme only on query parameters"]
    if not isinstance(q, dict) or not {"pattern", "parse"} <= set(q) or set(q) - {"pattern", "parse", "strip"}:
        return [f"{pw}: x-query-lexeme takes pattern, parse and optional strip"]
    errs = []
    pat = q["pattern"]
    if not (isinstance(pat, str) and pat.startswith("^") and pat.endswith("$")):
        errs.append(f"{pw}: x-query-lexeme pattern is not an anchored ^…$ regex")
    else:
        try:
            re.compile(pat)
        except re.error as exc:
            errs.append(f"{pw}: x-query-lexeme pattern does not compile: {exc}")
    if q["parse"] not in LEXEME_TYPE:
        errs.append(f"{pw}: x-query-lexeme parse {q['parse']!r} is not number, integer or uint64")
    elif ((p.get("schema") or {}).get("type")) != LEXEME_TYPE[q["parse"]]:
        errs.append(f"{pw}: parse {q['parse']} needs schema.type {LEXEME_TYPE[q['parse']]}")
    if "strip" in q and (q["strip"] != "_" or q["parse"] != "number"):
        errs.append(f"{pw}: strip is only \"_\" and only with parse number")
    return errs


def check_openapi_routing(api):
    """x-route-priority у всех path item (уникальные целые ≥ 1, меньшее — раньше); x-path-capture segment|remainder только
    у параметров пути, remainder — последний параметр шаблона; x-path-decode percent-segment; x-path-error: МЕТОД операции
    этого пути → {status: 100..599 из ответов операции, response_schema: компонент схемы или -}."""
    api = Path(api)
    doc = yaml.safe_load(api.read_text(encoding="utf-8")) or {}
    schemas = (doc.get("components") or {}).get("schemas") or {}
    cparams = (doc.get("components") or {}).get("parameters") or {}
    errors, seen, n = [], {}, 0

    def resolve(p):
        if isinstance(p, dict) and "$ref" in p and str(p["$ref"]).startswith("#/components/parameters/"):
            return cparams.get(p["$ref"].rsplit("/", 1)[1]) or {}
        return p if isinstance(p, dict) else {}
    paths = doc.get("paths") or {}
    has = [p for p, item in paths.items() if isinstance(item, dict) and "x-route-priority" in item]
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        where = f"{api.name}: {path}"
        if has:
            pr = item.get("x-route-priority")
            if pr is None:
                errors.append(f"{where}: no x-route-priority (other paths of the file have it)")
            elif type(pr) is not int or pr < 1:
                errors.append(f"{where}: x-route-priority {pr!r} is not an integer ≥ 1")
            elif pr in seen:
                errors.append(f"{where}: x-route-priority {pr} repeats {seen[pr]}")
            else:
                seen[pr] = path
        names = re.findall(r"\{([^}]+)\}", path)
        ops = {m.upper(): op for m, op in item.items() if m in ROUTE_METHODS and isinstance(op, dict)}
        params = [resolve(p) for p in item.get("parameters") or []]
        for op in ops.values():
            params += [resolve(p) for p in op.get("parameters") or []]
        for p in params:
            if "x-query-lexeme" in p:
                n += 1
                errors += query_lexeme_errors(f"{where}: parameter {p.get('name')}", p)
            x = {k for k in p if k.startswith("x-path-")}
            if not x:
                continue
            n += 1
            pw = f"{where}: parameter {p.get('name')}"
            if p.get("in") != "path":
                errors.append(f"{pw}: x-path-* only on path parameters")
                continue
            if x - {"x-path-capture", "x-path-decode", "x-path-error"}:
                errors.append(f"{pw}: unknown {sorted(x - {'x-path-capture', 'x-path-decode', 'x-path-error'})}")
            cap = p.get("x-path-capture")
            if cap not in ("segment", "remainder"):
                errors.append(f"{pw}: x-path-capture {cap!r} is not segment or remainder")
            elif cap == "remainder" and not (names and names[-1] == p.get("name") and path.endswith("{" + p["name"] + "}")):
                errors.append(f"{pw}: remainder is only the last parameter, at the end of the template")
            if "x-path-decode" in p and p["x-path-decode"] != "percent-segment":
                errors.append(f"{pw}: x-path-decode {p['x-path-decode']!r} is not percent-segment")
            pe = p.get("x-path-error")
            if pe is None:
                continue
            if not isinstance(pe, dict) or not pe:
                errors.append(f"{pw}: x-path-error is not a map METHOD → {{status, response_schema}}")
                continue
            for meth, e in pe.items():
                ew = f"{pw}: x-path-error {meth}"
                if meth not in ops:
                    errors.append(f"{ew}: not an operation of this path")
                    continue
                if not isinstance(e, dict) or set(e) != {"status", "response_schema"}:
                    errors.append(f"{ew}: takes exactly status and response_schema")
                    continue
                st, rs = e["status"], e["response_schema"]
                if type(st) is not int or not 100 <= st <= 599:
                    errors.append(f"{ew}: status {st!r} is not an HTTP code")
                elif str(st) not in {str(k) for k in (ops[meth].get("responses") or {})}:
                    errors.append(f"{ew}: status {st} is not among the responses of the operation")
                if rs != "-" and rs not in schemas:
                    errors.append(f"{ew}: response_schema {rs!r} is not a component schema of the file")
    return errors, {"route_priorities": len(seen), "path_param_routes": n}


CONST_COLUMNS = ["name", "value", "unit", "norm", "meaning"]
CONST_UNITS = {"count", "s", "bytes"}


def runtime_constant_forms(root):
    return sorted(Path(root).glob("Platform/*/forms/runtime-constants.tsv"))


def check_runtime_constants(path):
    """ADR-0125 доп. (5), P/06: числовые константы урока — форма-норма. name уникален [A-Z][A-Z0-9_]*; value — положительное
    целое без ведущих нулей; unit count|s|bytes; norm — якорь требования этого урока, существующий в его нормах; meaning не пуст."""
    path = Path(path)
    lesson = path.parent.parent
    errors, rows = read(path, CONST_COLUMNS)
    anchors = set()
    for norms in (lesson / "spec").glob("*.norms.md"):
        anchors |= set(ANCHOR.findall(norms.read_text(encoding="utf-8")))
    number = lesson.name[:2]
    seen = set()
    for r in rows:
        where = f"{path.name}: {r['name']}"
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", r["name"]) or r["name"] in seen:
            errors.append(f"{where}: name is not [A-Z][A-Z0-9_]* or repeats")
        seen.add(r["name"])
        if not re.fullmatch(r"[1-9][0-9]*", r["value"]):
            errors.append(f"{where}: value {r['value']!r} is not a positive integer")
        if r["unit"] not in CONST_UNITS:
            errors.append(f"{where}: unit {r['unit']!r} not in {sorted(CONST_UNITS)}")
        g = REQ.fullmatch(r["norm"])
        if not g or g[1] != number:
            errors.append(f"{where}: norm {r['norm']!r} is not a requirement anchor of this lesson")
        elif r["norm"] not in anchors:
            errors.append(f"{where}: norm {r['norm']} has no anchor in the norms of the lesson")
        if not r["meaning"].strip():
            errors.append(f"{where}: no meaning")
    return errors, {"runtime_constants": len(rows)}


VDOOR_COLUMNS = ["method", "path", "row", "revision", "etag", "if_match", "absent_revision", "norm"]
VDOOR_REVISIONS = ("doc.rev", "revision", "rev")
VDOOR_IF_MATCH = ("optional", "ignored", "base-rev")
VDOOR_ROW = re.compile(r"[a-z][a-z0-9-]*(?:/(?:[a-z][a-z0-9-]*|<[a-z][a-z0-9-]*>))*")
VDOOR_BASE_REV_NORM = "P/08.0-R006"          # base-rev без P/08.0-R006 в norm — отказ (forms/README «Versioned doors»)


def versioned_door_forms(root):
    return sorted(Path(root).glob("Platform/*/forms/versioned-doors.tsv"))


def versioned_operations(lesson):
    """Операции OpenAPI урока → {(METHOD, path): (etag, if_match)}: заголовок ETag в каком-либо ответе (с `$ref` на
    components/responses) и параметр-заголовок If-Match у операции или её path item (с `$ref` на components/parameters)."""
    ops = {}
    for api in sorted((lesson / "spec").glob("*.api.openapi.yaml")):
        doc = yaml.safe_load(api.read_text(encoding="utf-8")) or {}
        comp = doc.get("components") or {}

        def ref(x, kind):
            if isinstance(x, dict) and str(x.get("$ref", "")).startswith(f"#/components/{kind}/"):
                return (comp.get(kind) or {}).get(x["$ref"].rsplit("/", 1)[1]) or {}
            return x if isinstance(x, dict) else {}
        for p, item in (doc.get("paths") or {}).items():
            if not isinstance(item, dict):
                continue
            for m, op in item.items():
                if m not in ROUTE_METHODS or not isinstance(op, dict):
                    continue
                etag = any("etag" in {str(h).lower() for h in (ref(r, "responses").get("headers") or {})}
                           for r in (op.get("responses") or {}).values())
                params = [ref(x, "parameters") for x in [*(item.get("parameters") or []), *(op.get("parameters") or [])]]
                if_match = any(x.get("in") == "header" and str(x.get("name", "")).lower() == "if-match" for x in params)
                ops[(m.upper(), p)] = (etag, if_match)
    return ops


def check_versioned_doors(path):
    """ADR-0125 доп. (5), P/08.0 Н1.9 (решение «Архитектора» 2026-11-05): версии дверей — форма-норма, грамматика закрытая.
    Колонки ровно VDOOR_COLUMNS (source нет); (method, path) — операция OpenAPI урока, не повторяется; каждая операция
    OpenAPI с ETag в ответе или If-Match в параметрах — строка формы; etag=true ⇔ ETag в ответе, if_match=ignored ⇔ нет
    If-Match. row — `-`, `writes[]` или шаблон семьи, где `<имя>` — захват пути операции или `<part>`; revision
    doc.rev|revision|rev; etag true|false; if_match optional|ignored|base-rev; absent_revision 0|-; norm — непустой список
    без повторов якорей требований урока, существующих в его нормах; base-rev — с P/08.0-R006."""
    path = Path(path)
    lesson = path.parent.parent
    head = next((ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")), "").split("\t")
    if "source" in head:
        return [f"{path.name}: no source column: the form is the norm (P/08.0 Н1.9 moved here)"], {"versioned_doors": 0}
    errors, rows = read(path, VDOOR_COLUMNS)
    ops = versioned_operations(lesson)
    anchors = set()
    for norms in (lesson / "spec").glob("*.norms.md"):
        anchors |= set(ANCHOR.findall(norms.read_text(encoding="utf-8")))
    number = lesson.name[:2]
    seen = set()
    for r in rows:
        where = f"{path.name}: {r['method']} {r['path']}"
        key = (r["method"], r["path"])
        if key in seen:
            errors.append(f"{where}: repeats")
        seen.add(key)
        if key not in ops:
            errors.append(f"{where}: not an operation of the lesson OpenAPI")
        row = r["row"]
        if row not in ("-", "writes[]"):
            captures = set(re.findall(r"\{([^{}]+)\}", r["path"])) | {"part"}
            if not VDOOR_ROW.fullmatch(row):
                errors.append(f"{where}: row {row!r} is not -, writes[] or a family row template")
            else:
                stray = sorted(set(re.findall(r"<([^<>]+)>", row)) - captures)
                if stray:
                    errors.append(f"{where}: row placeholders {stray} are not captures of the path nor <part>")
        if r["revision"] not in VDOOR_REVISIONS:
            errors.append(f"{where}: revision {r['revision']!r} not in {list(VDOOR_REVISIONS)}")
        if r["etag"] not in ("true", "false"):
            errors.append(f"{where}: etag {r['etag']!r} is not true or false")
        if r["if_match"] not in VDOOR_IF_MATCH:
            errors.append(f"{where}: if_match {r['if_match']!r} not in {list(VDOOR_IF_MATCH)}")
        if r["absent_revision"] not in ("0", "-"):
            errors.append(f"{where}: absent_revision {r['absent_revision']!r} is not 0 or -")
        if key in ops:
            etag, if_match = ops[key]
            if r["etag"] in ("true", "false") and (r["etag"] == "true") != etag:
                errors.append(f"{where}: etag {r['etag']}, but the OpenAPI response {'has' if etag else 'has no'} ETag")
            if r["if_match"] in VDOOR_IF_MATCH and (r["if_match"] != "ignored") != if_match:
                errors.append(f"{where}: if_match {r['if_match']}, but the OpenAPI operation "
                              f"{'reads' if if_match else 'does not declare'} If-Match")
        norm = r["norm"].split(",")
        if not r["norm"] or len(norm) != len(set(norm)):
            errors.append(f"{where}: norm {r['norm']!r} is not a non-empty list without repeats")
        for n in norm if r["norm"] else []:
            g = REQ.fullmatch(n)
            if not g or g[1] != number:
                errors.append(f"{where}: norm {n!r} is not a requirement anchor of this lesson")
            elif n not in anchors:
                errors.append(f"{where}: norm {n} has no anchor in the norms of the lesson")
        if r["if_match"] == "base-rev" and VDOOR_BASE_REV_NORM not in norm:
            errors.append(f"{where}: if_match base-rev needs {VDOOR_BASE_REV_NORM} in norm")
    for key in sorted(k for k, (etag, if_match) in ops.items() if (etag or if_match) and k not in seen):
        errors.append(f"{path.name}: {key[0]} {key[1]}: the OpenAPI operation declares ETag or If-Match, but has no row")
    return errors, {"versioned_doors": len(rows)}


FP_SAFE = 2 ** 53 - 1                       # все целые профиля и статуса — в точной области binary64
FP_COUNTS = ("n_unit", "n_claim", "n_folder", "n_empty", "n_delete", "n_guard")
FP_KEY_MAX, FP_VERSION_MAX, FP_ID_MAX, FP_TIMESTAMP = 1024, 20, 64, 313      # P02.3 N3, profile-form README
FP_ENCODER = "compact-json-utf8"
FP_H = "skeleton_entity_bytes-2*put_slots+timestamp_slots*(timestamp_upper_bytes-timestamp_dummy_bytes)"
FP_PROVENANCE = {                           # поле провенанса → раздел owned_context, который его доказывает
    "store_limits": ("owned-context:status", "status"),
    "catalogue": ("owned-context:confirmed-catalogue", "confirmed_catalogue"),
    "procedure_descriptors": ("owned-context:descriptors", "descriptors"),
    "complete_packet_roster": ("owned-context:descriptor-packet-roster", "descriptor_packet_roster"),
    "metadata_skeleton_proof": ("owned-context:metadata-proofs", "descriptors"),   # доказательства скелета — в дескрипторах
}
FP_OUTCOMES = ("ok", "refused:form")


def finite_profile_forms(root):
    return sorted(Path(root).glob("Platform/*/forms/finite-profile.cases.json"))


def _fp_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _fp_big(v, where, out):
    """Каждое целое (не bool) ≤ 2^53−1 и ≥ 0."""
    if isinstance(v, dict):
        for k, x in v.items():
            _fp_big(x, f"{where}/{k}", out)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            _fp_big(x, f"{where}/{i}", out)
    elif _fp_int(v) and not 0 <= v <= FP_SAFE:
        out.append(f"{where}: integer {v} outside 0..2^53-1")


def _fp_folder_row_max(root):
    path = Path(root) / "Platform/06-console/forms/runtime-constants.tsv"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            cells = line.split("\t")
            if cells[0] == "FOLDER_ROW_MAX" and len(cells) > 1 and cells[1].isdigit():
                return int(cells[1])
    return None


def _fp_descriptor_H(d):
    """H заново по метаданным дескриптора (profile-form README): скелет минус 2 на каждый put ({} вместо items), плюс
    каждая отметка времени до верхней оценки 313; поле H дескриптора не берётся."""
    return d["skeleton_entity_bytes"] - 2 * d["put_slots"] + d["timestamp_slots"] * (
        d["timestamp_upper_bytes"] - d["timestamp_dummy_bytes"])


def _fp_bound(H, c, V, F, lf):
    return H + (c["n_unit"] + c["n_claim"]) * (12 * V + 7) + c["n_folder"] * (6 * F + 19) + 2 * c["n_empty"] + lf


def _fp_context(ctx, F, err):
    """Независимый контекст: перечень пакетов без дублей, ровно один дескриптор на пакет, метаданные в пределах, H
    пересчитан. Возвращает {packet: (counts, H, descriptor)} годных дескрипторов."""
    if not isinstance(ctx, dict):
        err.append("owned_context is not an object")
        return {}
    roster = ctx.get("descriptor_packet_roster")
    if not (isinstance(roster, list) and roster and all(isinstance(p, str) and p for p in roster)):
        err.append("owned_context.descriptor_packet_roster is not a non-empty list of packet names")
        roster = []
    for p in sorted({p for p in roster if roster.count(p) > 1}):
        err.append(f"owned_context roster: packet {p!r} repeats")
    status = ctx.get("status")
    if not (isinstance(status, dict) and all(_fp_int(status.get(k)) and status[k] > 0 for k in ("max_value", "max_body"))):
        err.append("owned_context.status needs positive integers max_value and max_body")
    out = {}
    descs = ctx.get("descriptors") if isinstance(ctx.get("descriptors"), list) else []
    names = [d.get("packet") for d in descs if isinstance(d, dict)]
    for p in sorted({p for p in names if names.count(p) > 1}, key=str):
        err.append(f"owned_context descriptors: packet {p!r} has more than one descriptor")
    for p in roster:
        if p not in names:
            err.append(f"owned_context: roster packet {p!r} has no descriptor")
    for d in descs:
        p = d.get("packet") if isinstance(d, dict) else None
        where = f"owned_context descriptor {p!r}"
        if p not in roster:
            err.append(f"{where}: not in the packet roster")
            continue
        n = len(err)
        c = d.get("counts") if isinstance(d.get("counts"), dict) else {}
        if set(c) != set(FP_COUNTS) or not all(_fp_int(c[k]) and c[k] >= 0 for k in c):
            err.append(f"{where}: counts are not exactly {list(FP_COUNTS)} natural integers")
            continue
        nums = ("skeleton_entity_bytes", "put_slots", "key_utf8_bytes", "key_json_bytes", "version_digits",
                "id_hex_digits", "timestamp_slots", "timestamp_dummy_bytes", "timestamp_upper_bytes", "H")
        if not all(_fp_int(d.get(k)) and d[k] >= 0 for k in nums):
            err.append(f"{where}: metadata {list(nums)} are not natural integers")
            continue
        if not 1 <= d["key_utf8_bytes"] <= FP_KEY_MAX:
            err.append(f"{where}: key_utf8_bytes {d['key_utf8_bytes']} not in 1..{FP_KEY_MAX}")
        if d["key_json_bytes"] != 6 * d["key_utf8_bytes"] + 2:
            err.append(f"{where}: key_json_bytes {d['key_json_bytes']} != 6*key_utf8_bytes+2")
        if not 0 <= d["version_digits"] <= FP_VERSION_MAX:
            err.append(f"{where}: version_digits {d['version_digits']} > {FP_VERSION_MAX}")
        if not 1 <= d["id_hex_digits"] <= FP_ID_MAX:
            err.append(f"{where}: id_hex_digits {d['id_hex_digits']} not in 1..{FP_ID_MAX}")
        if d["timestamp_upper_bytes"] != FP_TIMESTAMP or not 1 <= d["timestamp_dummy_bytes"] <= FP_TIMESTAMP:
            err.append(f"{where}: timestamp_upper_bytes is not {FP_TIMESTAMP} or the dummy is outside 1..{FP_TIMESTAMP}")
        puts = c["n_unit"] + c["n_claim"] + c["n_folder"] + c["n_empty"]
        if d["put_slots"] != puts:
            err.append(f"{where}: put_slots {d['put_slots']} != n_unit+n_claim+n_folder+n_empty {puts}")
        keys = puts + c["n_delete"] + c["n_guard"]
        if d["skeleton_entity_bytes"] < keys * d["key_json_bytes"]:
            err.append(f"{where}: skeleton {d['skeleton_entity_bytes']} is below its {keys} full keys of "
                       f"{d['key_json_bytes']} bytes")
        if d.get("H_derivation") != FP_H:
            err.append(f"{where}: H_derivation is not {FP_H!r}")
        H = _fp_descriptor_H(d)
        if d["H"] != H:
            err.append(f"{where}: H {d['H']} != recomputed {H}")
        if len(err) == n:
            out[p] = (c, H, d)
    return out


def _fp_refusals(profile, status, ctx, descs, F, validator):
    """Решение судьи по случаю, без expect: список причин отказа (пусто — профиль проходит)."""
    why = [f"schema: {short(e.message, 120)}" for e in validator.iter_errors(profile)]
    _fp_big(profile, "profile", why)
    _fp_big(status, "store_status", why)
    if not (isinstance(status, dict) and all(_fp_int(status.get(k)) and status[k] > 0 for k in ("max_value", "max_body"))):
        why.append("store_status needs positive integers max_value and max_body")
    if why:
        return why
    B, V = status["max_body"], status["max_value"]
    if profile["body_bytes"] != B:
        why.append(f"body_bytes {profile['body_bytes']} != effective max_body {B}")
    if profile["row_weight_bytes"] != V:
        why.append(f"row_weight_bytes {profile['row_weight_bytes']} != effective max_value {V}")
    if F is None or profile["folder_weight_bytes"] != F:
        why.append(f"folder_weight_bytes {profile['folder_weight_bytes']} != FOLDER_ROW_MAX {F}")
    meta = profile["metadata"]
    for p, (_, _, d) in descs.items():
        for mk, dk in (("key_utf8_bytes", "key_utf8_bytes"), ("version_digits", "version_digits"),
                       ("id_hex_digits", "id_hex_digits"), ("timestamp_json_bytes", "timestamp_upper_bytes")):
            if meta[mk] != d[dk]:
                why.append(f"metadata.{mk} {meta[mk]} != descriptor {p} {dk} {d[dk]}")
    for field, (word, section) in FP_PROVENANCE.items():
        if profile["provenance"][field] != word or section not in ctx:
            why.append(f"provenance.{field} {profile['provenance'][field]!r} is not the proof {word!r}")
    roster = ctx.get("descriptor_packet_roster") or []
    names = [k["packet"] for k in profile["packets"]]
    for p in sorted({p for p in names if names.count(p) > 1}):
        why.append(f"packet {p!r} repeats")
    for p in roster:
        if p not in names:
            why.append(f"packet {p!r} of the roster is missing")
    lf = meta["trailing_lf"]
    for k in profile["packets"]:
        p = k["packet"]
        if p not in descs:
            why.append(f"packet {p!r} has no proved descriptor")
            continue
        c, H, _ = descs[p]
        if k["multiplicity_proof"] != f"owned-descriptor:{p}":
            why.append(f"packet {p}: multiplicity_proof {k['multiplicity_proof']!r} is not owned-descriptor:{p}")
        if k["H"] != H:
            why.append(f"packet {p}: H {k['H']} != recomputed {H}")
        for n in FP_COUNTS:
            if k[n] != c[n]:
                why.append(f"packet {p}: {n} {k[n]} != descriptor {c[n]}")
        bound = _fp_bound(H, c, V, F or 0, lf)
        if bound > B:
            why.append(f"packet {p}: bound {bound} > B {B}")
    return why


def check_finite_profile(path):
    """ADR-0127 P/06 C2, P02.3 N3 шаги 6a/3a, P06.8 (решение «Архитектора» 2026-11-06): судья полноты и границы
    конечного профиля удаления — то, что схема не доказывает. Контекст owned_context: перечень пакетов без дублей, по
    одному дескриптору, метаданные в пределах (ключ ≤ 1024, 6K+2, версия ≤ 20 цифр, id ≤ 64, отметка 313), H заново по
    скелету; expected_bounds и max_bound — по формуле. Каждый случай решается без expect: схема, целые ≤ 2^53−1,
    B и V — действующий статус случая, F — FOLDER_ROW_MAX, провенанс — разделы контекста, пакеты ровно перечень,
    H и кратности — пересчитанные, bound = H + (n_unit+n_claim)(12V+7) + n_folder(6F+19) + 2n_empty + LF ≤ B; решение
    равно expect. Покрытие: проходит случай с bound ровно B и отказывает случай с одной причиной bound = B+1."""
    import jsonschema
    path = Path(path)
    root = path.parents[3]
    errors = []
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [f"{path.name}: not JSON: {short(str(exc))}"], {"finite_profile_cases": 0}
    try:
        schema = json.loads((path.parent / d["schema"]).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
    except (KeyError, TypeError, OSError, ValueError, jsonschema.SchemaError) as exc:
        return [f"{path.name}: schema is not a readable JSON Schema 2020-12: {short(str(exc))}"], {"finite_profile_cases": 0}
    F = _fp_folder_row_max(root)
    if F is None:
        errors.append(f"{path.name}: FOLDER_ROW_MAX not found in Platform/06-console/forms/runtime-constants.tsv")
    ctx = d.get("owned_context")
    cerr = []
    descs = _fp_context(ctx, F, cerr)
    errors += [f"{path.name}: {m}" for m in cerr]
    ctx = ctx if isinstance(ctx, dict) else {}
    cases = d.get("cases") if isinstance(d.get("cases"), list) else []
    if not cases:
        errors.append(f"{path.name}: no cases")
    seen, exact, plus_one, lfs = set(), False, False, set()
    for i, case in enumerate(cases):
        if not (isinstance(case, dict) and set(case) == {"case", "profile", "store_status", "expect"}):
            errors.append(f"{path.name}: cases[{i}] is not exactly {{case, profile, store_status, expect}}")
            continue
        where = f"{path.name}: case {case['case']!r}"
        if case["case"] in seen:
            errors.append(f"{where}: repeats")
        seen.add(case["case"])
        if case["expect"] not in FP_OUTCOMES:
            errors.append(f"{where}: expect {case['expect']!r} not in {list(FP_OUTCOMES)}")
            continue
        why = _fp_refusals(case["profile"], case["store_status"], ctx, descs, F, validator)
        got = "refused:form" if why else "ok"
        if got != case["expect"]:
            errors.append(f"{where}: expect {case['expect']}, the judge gives {got}"
                          + (f": {'; '.join(why[:3])}" if why else ""))
            continue
        status = case["store_status"]
        top = None
        if not why or all(" bound " in w for w in why):
            p = case["profile"]
            lfs.add(p["metadata"]["trailing_lf"]) if not why else None
            top = max(_fp_bound(H, c, status["max_value"], F or 0, p["metadata"]["trailing_lf"])
                      for c, H, _ in descs.values()) if descs else None
        if top is not None and not why and top == status["max_body"]:
            exact = True
        if top is not None and why and top == status["max_body"] + 1:
            plus_one = True
    if cases and not exact:
        errors.append(f"{path.name}: no ok case whose largest bound is exactly B")
    if cases and not plus_one:
        errors.append(f"{path.name}: no refused case whose only reason is the largest bound B+1")
    exp = d.get("expected_bounds")
    if len(lfs) > 1:
        errors.append(f"{path.name}: ok cases disagree on trailing_lf {sorted(lfs)}")
    status = ctx.get("status") if isinstance(ctx.get("status"), dict) else {}
    if not isinstance(exp, dict) or set(exp) != set(ctx.get("descriptor_packet_roster") or []):
        errors.append(f"{path.name}: expected_bounds keys are not the packet roster")
    elif descs and lfs and _fp_int(status.get("max_value")) and F is not None:
        lf = next(iter(lfs))
        for p, (c, H, _) in descs.items():
            b = _fp_bound(H, c, status["max_value"], F, lf)
            if exp[p] != b:
                errors.append(f"{path.name}: expected_bounds {p} {exp[p]} != recomputed {b}")
        if d.get("max_bound") != max(exp.values(), key=lambda v: v if _fp_int(v) else -1):
            errors.append(f"{path.name}: max_bound {d.get('max_bound')} is not the largest expected bound")
    for k in ("owned_context", "expected_bounds", "max_bound"):     # случаи с целым вне области — свидетели отказа
        _fp_big(d.get(k), f"{path.name}: {k}", errors)
    return errors, {"finite_profile_cases": len(cases)}


def deletion_body_witness_forms(root):
    return sorted(Path(root).glob("Platform/*/forms/deletion-body-witnesses.json"))


def check_deletion_body_witnesses(path):
    """P06.8 N1.3 (решение «Архитектора» 2026-11-06): кодек-свидетели границы тела — entity_bytes = decoded_chunk;
    within_body_limit ⇔ entity_bytes ≤ limit; есть limit−1, limit (проходят) и limit+1 (отказ), и тот же JSON с LF
    на один байт длиннее своего без LF."""
    path = Path(path)
    errors = []
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [f"{path.name}: not JSON: {short(str(exc))}"], {"deletion_body_witnesses": 0}
    limit, ws = d.get("limit"), d.get("witnesses")
    if not (_fp_int(limit) and limit > 0 and isinstance(ws, dict) and ws):
        return [f"{path.name}: needs a positive integer limit and witnesses"], {"deletion_body_witnesses": 0}
    sizes = {}
    for name, w in ws.items():
        b = w.get("entity_bytes") if isinstance(w, dict) else None
        if not _fp_int(b):
            errors.append(f"{path.name}: {name}: entity_bytes is not an integer")
            continue
        sizes.setdefault(b, []).append(name)
        if w.get("decoded_chunk_entity_bytes") != b:
            errors.append(f"{path.name}: {name}: decoded_chunk_entity_bytes != entity_bytes {b}")
        if w.get("within_body_limit") is not (b <= limit):
            errors.append(f"{path.name}: {name}: within_body_limit {w.get('within_body_limit')} but {b} vs limit {limit}")
    for b in (limit - 1, limit, limit + 1):
        if b not in sizes:
            errors.append(f"{path.name}: no codec witness of {b} bytes (limit {limit} {b - limit:+d})")
    lfed = [w for w in ws.values() if isinstance(w, dict) and w.get("trailing_LF") is True]
    for w in lfed:
        twins = [x for x in ws.values() if isinstance(x, dict) and x.get("trailing_LF") is False
                 and x.get("ensure_ascii") == w.get("ensure_ascii") and x.get("put_weights") == w.get("put_weights")]
        if not any(x.get("entity_bytes") == w.get("entity_bytes", 0) - 1 for x in twins):
            errors.append(f"{path.name}: an LF witness of {w.get('entity_bytes')} bytes has no same JSON one byte shorter")
    return errors, {"deletion_body_witnesses": len(ws)}


RWB_COLUMNS = ["write", "key", "field", "source", "value", "guard_key", "guard_version", "norm"]
RWB_SOURCES = ("start", "input", "const")
RWB_TYPES = ("string", "boolean", "integer", "number", "object", "array", "dyn")
RWB_WRITE = re.compile(r"[a-z][a-z0-9-]*")
RWB_DECL = re.compile(r"#(start|input)(?:\s.*)?")                        # строка-объявление; прочие `#` — комментарий
RWB_DECL_LINE = re.compile(r"#(start|input) ((?:/(?:[^~/\s]|~[01])*)+) ([a-z]+)")
RWB_FIELD = re.compile(r"/(?:[^~/]|~[01])+")                            # ровно один токен — непосредственное свойство
RWB_SEG = r"\{[^{}/]*(?:/[^{}/]*)*\}|[A-Za-z0-9._-]+"
RWB_TEMPLATE = re.compile(rf"(?:{RWB_SEG})(?:/(?:{RWB_SEG}))*")
RWB_PLACE = re.compile(r"\{(start|input):((?:/(?:[^~/{}]|~[01])*)+)\}")
RWB_GUARD_VERSION = re.compile(r"(start|input):((?:/(?:[^~/]|~[01])*)+)")
RWB_JSON_TYPE = {bool: "boolean", int: "integer", float: "number", str: "string", dict: "object", list: "array",
                 type(None): "null"}


def row_write_binding_forms(root):
    return sorted(Path(root).glob("Platform/*/forms/row-write-bindings.tsv"))


def _rwb_template(text, decls):
    """Шаблон key/guard_key → (сегменты, ошибки): сегмент — буквальный или ("place", source, pointer) к объявленной string."""
    if not RWB_TEMPLATE.fullmatch(text):
        return None, [f"template {text!r} is not literal segments and whole-segment {{start:/p}}/{{input:/p}}"]
    segs, errors = [], []
    for seg in re.findall(RWB_SEG, text):
        if not seg.startswith("{"):
            segs.append(seg)
            continue
        m = RWB_PLACE.fullmatch(seg)
        if not m:
            errors.append(f"placeholder {seg} is not {{start:/pointer}} or {{input:/pointer}}")
        elif decls.get((m[1], m[2])) != "string":
            errors.append(f"placeholder {seg} does not read a declared #{m[1]} string")
        segs.append(("place", seg))
    return segs, errors


def _rwb_families(lesson):
    """Строки каталога данных платформы → [(сегменты ключа, путь схемы или None, ключ)]."""
    catalog = lesson.parent / "common/data/catalog.tsv"
    if not catalog.is_file():
        return []
    out = []
    for line in catalog.read_text(encoding="utf-8").splitlines():
        cols = line.split("\t")
        if line.startswith("#") or len(cols) < 8 or cols[0] == "key":
            continue
        schema = cols[7] if cols[7].endswith(".schema.json") else None
        out.append((cols[0].split("/"), lesson.parent / schema if schema else None, cols[0]))
    return out


def _rwb_match(segs, family):
    """Шаблон формы совпадает с ключом семьи: placeholder — только целый сегмент `<…>`, буквальный — равный буквальный
    или экземпляр сегмента семьи (`<…>` внутри сегмента — непустая часть без `/`)."""
    if len(segs) != len(family):
        return False
    for s, f in zip(segs, family):
        whole = re.fullmatch(r"<[^<>]+>", f) is not None
        if isinstance(s, tuple):
            if not whole:
                return False
        elif not re.fullmatch("".join(re.escape(p) if i % 2 == 0 else "[^/]+"
                                      for i, p in enumerate(re.split(r"(<[^<>]+>)", f))), s):
            return False
    return True


def _rwb_schema_type(schema, prop):
    """Тип свойства схемы (с локальным `$ref` на `#/$defs/…`) → множество типов JSON или None (любой)."""
    seen = 0
    while isinstance(prop, dict) and "type" not in prop and str(prop.get("$ref", "")).startswith("#/$defs/") and seen < 16:
        prop = (schema.get("$defs") or {}).get(prop["$ref"][len("#/$defs/"):]) or {}
        seen += 1
    t = prop.get("type") if isinstance(prop, dict) else None
    return None if t is None else set(t if isinstance(t, list) else [t])


def _rwb_compatible(declared, types):
    if declared == "dyn" or types is None:
        return True
    return declared in types or (declared == "integer" and "number" in types)


def check_row_write_bindings(path):
    """ADR-0127 доп. (1) п. 3, проект P03-GEN-01 (грамматика утверждена «Архитектором» 2026-11-06): конструкторы записи
    строки семьи — key/items/guard из снимка старта и аргумента, без выражений. Шапка ровно RWB_COLUMNS; объявления
    `#start /p тип`, `#input /p тип` (тип из RWB_TYPES, путь не повторяется). write — [a-z][a-z0-9-]*; (write, field)
    уникальны; key, guard_key, guard_version одинаковы в строках одного write. key — шаблон из буквальных сегментов и
    целосегментных {start:/p}/{input:/p} к объявленным string, совпадает с ключом ровно одной семьи каталога со схемой;
    field — JSON Pointer к непосредственному свойству items этой схемы, обязательные покрыты, чужие запрещены. source
    start|input|const: value — объявленный путь своего source (тип совместим с типом свойства, dyn — любой) или строгое
    JSON-значение. guard_key — шаблон или `-`; guard_version — start:/p или input:/p к объявленной string или `-`; обе
    `-` или обе заполнены. norm — непустой список без повторов существующих якорей требований урока."""
    path = Path(path)
    lesson = path.parent.parent
    errors, rows = read(path, RWB_COLUMNS)
    decls = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not RWB_DECL.fullmatch(line):
            continue
        m = RWB_DECL_LINE.fullmatch(line)
        if not m or m[3] not in RWB_TYPES:
            errors.append(f"{path.name}: declaration {line!r} is not #start|#input /pointer {'|'.join(RWB_TYPES)}")
            continue
        if (m[1], m[2]) in decls:
            errors.append(f"{path.name}: declaration #{m[1]} {m[2]} repeats")
        decls[(m[1], m[2])] = m[3]
    anchors = set()
    for norms in (lesson / "spec").glob("*.norms.md"):
        anchors |= set(ANCHOR.findall(norms.read_text(encoding="utf-8")))
    number = lesson.name[:2]
    families = _rwb_families(lesson)
    writes, seen = {}, set()
    for r in rows:
        where = f"{path.name}: {r['write']} {r['field']}"
        if not RWB_WRITE.fullmatch(r["write"]):
            errors.append(f"{where}: write {r['write']!r} is not [a-z][a-z0-9-]*")
        if (r["write"], r["field"]) in seen:
            errors.append(f"{where}: (write, field) repeats")
        seen.add((r["write"], r["field"]))
        writes.setdefault(r["write"], []).append(r)
        if not RWB_FIELD.fullmatch(r["field"]):
            errors.append(f"{where}: field {r['field']!r} is not a JSON Pointer to one direct property")
        if r["source"] not in RWB_SOURCES:
            errors.append(f"{where}: source {r['source']!r} not in {list(RWB_SOURCES)}")
        elif r["source"] == "const":
            try:
                wire_json(r["value"])
            except ValueError:
                errors.append(f"{where}: const value {short(r['value'])} is not one strict JSON value")
        elif not r["value"].startswith("/") or (r["source"], r["value"]) not in decls:
            errors.append(f"{where}: value {short(r['value'])} is not a declared #{r['source']} pointer")
        norm = r["norm"].split(",")
        if not r["norm"] or len(norm) != len(set(norm)):
            errors.append(f"{where}: norm {r['norm']!r} is not a non-empty list without repeats")
        for n in norm if r["norm"] else []:
            g = REQ.fullmatch(n)
            if not g or g[1] != number:
                errors.append(f"{where}: norm {n!r} is not a requirement anchor of this lesson")
            elif n not in anchors:
                errors.append(f"{where}: norm {n} has no anchor in the norms of the lesson")
    for write, group in writes.items():
        where = f"{path.name}: {write}"
        first = group[0]
        for column in ("key", "guard_key", "guard_version"):
            if any(r[column] != first[column] for r in group):
                errors.append(f"{where}: {column} differs between the rows of one write")
        segs, errs = _rwb_template(first["key"], decls)
        errors += [f"{where}: key: {e}" for e in errs]
        gk, gv = first["guard_key"], first["guard_version"]
        if (gk == "-") != (gv == "-"):
            errors.append(f"{where}: guard_key and guard_version are both - or both filled")
        if gk != "-":
            errors += [f"{where}: guard_key: {e}" for e in _rwb_template(gk, decls)[1]]
        if gv != "-":
            m = RWB_GUARD_VERSION.fullmatch(gv)
            if not m or decls.get((m[1], m[2])) != "string":
                errors.append(f"{where}: guard_version {gv!r} is not start:/p or input:/p to a declared string")
        if segs is None:
            continue
        found = [f for f in families if _rwb_match(segs, f[0])]
        if len(found) != 1:
            errors.append(f"{where}: key {first['key']!r} matches {len(found)} families of the catalog, not one"
                          + (f" ({', '.join(f[2] for f in found)})" if found else ""))
            continue
        schema_path, family = found[0][1], found[0][2]
        if schema_path is None or not schema_path.is_file():
            errors.append(f"{where}: family {family} has no schema of items")
            continue
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        props = schema.get("properties") or {}
        named = set()
        for r in group:
            if not RWB_FIELD.fullmatch(r["field"]):
                continue
            name = r["field"][1:].replace("~1", "/").replace("~0", "~")
            named.add(name)
            if name not in props:
                errors.append(f"{where}: field {r['field']} is not a property of {family} ({schema_path.name})")
                continue
            types = _rwb_schema_type(schema, props[name])
            if r["source"] == "const":
                try:
                    v = wire_json(r["value"])
                except ValueError:
                    continue
                jt = RWB_JSON_TYPE[type(v)]
                if types is not None and jt not in types and not (jt == "integer" and "number" in types):
                    errors.append(f"{where}: field {r['field']}: const {jt} against schema type {sorted(types)}")
            elif (r["source"], r["value"]) in decls:
                declared = decls[(r["source"], r["value"])]
                if not _rwb_compatible(declared, types):
                    errors.append(f"{where}: field {r['field']}: declared {declared} against schema type {sorted(types)}")
        missing = [p for p in schema.get("required") or [] if p not in named]
        if missing:
            errors.append(f"{where}: required properties of {family} not bound: {missing}")
    return errors, {"row_write_bindings": len(rows)}
