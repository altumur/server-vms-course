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
import re
from pathlib import Path

import yaml

FLAG_COLUMNS = ["flag", "type", "default", "default_text", "required", "commands", "bad", "norm"]
REF_COLUMNS = ["chapter", "row", "name", "surface", "code", "kind", "fields", "headers", "log", "norm"]
REF_EXTRA = ["word", "cause", "outcome", "diagnostic", "caller"]   # ячейки Н4, когда форма — сама норма (ADR-0125 доп. (5))
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


KIT_PARTS = {"writecheck", "door", "flags", "refusals", "vectors", "stagetests", "launch",   # ADR-0126 доп. (2) п. 1, доп. (7) п. 4; ADR-0083 доп. (95) п. 3
             "families", "admin", "core", "rollout-poll"}                                   # ADR-0125 доп. (5)
GATE = re.compile(r"tests:([0-9]+\.[0-9]+):([^:;\s]+)(:seams)?|accept:([0-9]+\.[0-9]+):([^:;\s]+)|vectors:([a-z0-9-]+)|build"
                  r"|(verdicts|puts):([0-9]+\.[0-9]+):([^:;\s]+)")
CASE_TABLE = {"verdicts": "verdicts.tsv", "puts": "puts.tsv"}   # таблицы случаев приёмки (P/02), ADR-0125 доп. (5)


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
REQ = re.compile(r"P/([0-9]{2})\.([0-9]+)-R([0-9]{3})")


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
        m = re.match(r"([0-9]{2})\.([0-9]+)-", norms.name)
        removed |= set(TOMBSTONE.findall(text))
        for number in ANCHOR.findall(text):
            count += 1
            g = REQ.fullmatch(number)
            if not g:
                errors.append(f"{norms.name}: anchor {number} is not P/NN.K-RNNN")
            elif not m or (g[1], g[2]) != (m[1], m[2]):
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
        file = lesson / "acceptance" / chapter.split(".")[1] / CASE_TABLE[m[7]]
        if not file.is_file():
            return [f"stages.tsv: {stage}: no {file.relative_to(lesson)} for {m[7]}:{chapter}"]
        if names == "*":
            return []
        known = {ln.split("\t")[0] for ln in file.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")} - {"case"}
        missing = [n for n in names.split(",") if n not in known]
        return [f"stages.tsv: {stage}: cases {missing} are not in {file.relative_to(lesson)}"] if missing else []
    chapter, names, seams = (m[1], m[2], m[3]) if m[1] else (m[4], m[5], None)
    file = lesson / "acceptance" / chapter.split(".")[1] / ("seams.tsv" if seams else "scenarios.tsv")
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
    return sorted(Path(root).glob("Platform/*/acceptance/*/seams.tsv"))


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
