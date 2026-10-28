"""Пакет перехода на В7 — данные (PLAN-TRANSITION п. 2): применить к дереву курса то, что «Спецификация» переносит
байтами, кроме текстов норм. Для её ветки и для пробы `check_spec` в режиме В7 на копии дерева.

    python -m v7.transition --root ДЕРЕВО [--lessons 01,02,03,04,05,06]      (из skills/lesson-spec/scripts)
    python -m v7.transition --root ДЕРЕВО --keys          (дерево В7: столбец key пакета family-read, шаг 6)
    python -m v7.transition --root ДЕРЕВО --add-row BASE TEXT NOTE   (дерево В7: строки family-read по образцу, исход — стек)

По порядку (дерево — с диалектом; повтор на уже переведённом дереве — отказ):
1. стандартные файлы на места (`v7.build --place`): схемы, связи, таблицы слоёв, схема вида, `common.schema.json`;
   у строк связей, следующих из других, — `x-implied-by` (IMPLIED);
2. каталог: колонка `schema` — `….schema.json` того же базового имени; одна схема на семью: семьи `events` (7 семей
   на `events.form.yaml`) — по своему файлу EVENTS (схема, слои, исходы — копии; решение «Архитектора» 2026-10-28);
3. файлы диалекта снимаются: `*.form.yaml` (формы семей, `common.form.yaml`, форма манифеста), `references.tsv`,
   `common/DIALECT.md` (всё — за меткой `dialect-reference-dc94d0fd1`);
4. корпус P/02.1 по `v7/out/setb/deltas.tsv` и `cases.tsv`: файлы без `worker:` дополняются (п. 7), `verdicts.tsv` и
   `classes.tsv` — по дельтам, новые случаи Б без пометки `dup` (кроме `p3_*`: это входы корпуса после п. 7);
5. векторы `canonical` заново (`v7.vectors`);
6. пакет `Platform/common/vectors/family-read/`: README и таблица на урок-владельца из уроков `--lessons` (набор А,
   `v7/out/seta/family-read.jsonl`, у строк `1e400` — исход по Б; случаи семей Б `a*`); столбец `key` — пример по
   шаблону каталога (таблица плейсхолдеров `Platform/common/data/README.md`), строки `key: …` — ключ не по шаблону;
   на дереве В7 — только это, на месте: `--keys` (V7-FAMILY-KEY-PLACEHOLDER-01);
7. разделы норм между маркерами (`v7.sections`): «Форма» P/02.1, «Семьи данных» глав-владельцев, «Форма канонического
   вида» P/02.2;
9. пакет `Platform/common/vectors/yaml-suite/`: README, `LICENSE` (MIT), `inputs/<id>.yaml` и `expect.tsv` — исход
   слоя 1 по каждому тесту yaml-test-suite закреплённой версии (`--yts`, по умолчанию v7.yts.SUITE; набор сверяется
   с закреплённым — число файлов, тестов и sha256 содержимого — до первой правки дерева, иначе отказ с ненулевым кодом);
8. `outcomes.tsv` — столбец `reader` (решение владельца 2026-10-28): строка пустого пути — на каждого читателя семьи
   (`readers` каталога, у `*` — роли уроков, чей абзац «Данные» читает ключ, ∪ участники `cas` и `guard`), строки
   полей — `*`. Это заготовка: проза исхода скопирована каждому читателю — делить её по читателям и называть пробелы
   «Спецификации» руками (PLAN-TRANSITION п. 2.7).
Тексты норм (Н1.1, Н3–Н5, LAYERS.md вместо DIALECT.md, ссылки на файлы диалекта) — правка «Спецификации», не здесь.
"""
import argparse
import ast
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from v7 import spec  # noqa: E402

CORPUS = Path("Platform/02-installer/acceptance/1")
FAMILY_READ = Path("Platform/common/vectors/family-read")
SETB = HERE / "out" / "setb"
SETA = HERE / "out" / "seta"
WORKER = b"worker: {exec: /usr/lib/probe/worker}\n"
P7_SKIP = {"empty_document", "a91_worker_missing"}
HEADER = spec.FR_HEADER
# Семьи событий (P/05) — один файл схемы и исходов на семью: ключ каталога → базовое имя (решение «Архитектора»
# 2026-10-28).
EVENTS = {
    "<корень событий>/<sub>/<unit>/e<эпоха>/<YYYYMMDDTHHMMSSZ>.events.jsonl": "events-unit",
    "<корень событий>/<sub>.alarms/<unit>/e<эпоха>/<YYYYMMDDTHHMMSSZ>.events.jsonl": "events-unit-alarms",
    "<корень событий>/audit/<роль>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl": "events-audit",
    "<корень событий>/audit.alarms/<роль>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl": "events-audit-alarms",
    "<корень событий>/console/<экземпляр>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl": "events-console",
    "<корень событий>/console.alarms/<экземпляр>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl": "events-console-alarms",
    "<корень событий>/.mirror/<server>/<дерево>/<unit>/e<эпоха>/<YYYYMMDDTHHMMSSZ>.events.jsonl": "events-mirror",
}


def tsv(path):
    return [ln.split("\t") for ln in Path(path).read_text(encoding="utf-8").split("\n") if ln and not ln.startswith("#")]


def write_tsv(path, lead, header, rows):
    """header None — таблица без строки заголовка (заголовок — в комментарии шапки, как у verdicts.tsv корпуса)."""
    text = "".join(x + "\n" for x in lead) + ("\t".join(header) + "\n" if header else "")
    text += "".join("\t".join(r) + "\n" for r in rows)
    Path(path).write_text(text, encoding="utf-8")


def lead_of(path):
    out = []
    for ln in Path(path).read_text(encoding="utf-8").split("\n"):
        if not ln.startswith("#"):
            break
        out.append(ln)
    return out


# ---------------------------------------------------------------- 1–3: стандартные файлы, каталог, диалект

def standard_files(root):
    from v7 import build
    build.build(root, None, place=True)


# Строки связей, которые следуют из других (решение «Архитектора» 2026-10-28, PLAN-TRANSITION п. 2.3.6): номер →
# номера; check_spec держит их групповой мутацией.
IMPLIED = {18: [16, 17]}


def implied(root):
    p = root / "Platform/02-installer/spec/02.1-installer.relations.json"
    rel = json.loads(p.read_text(encoding="utf-8"))
    for r in rel["rows"]:
        if r["no"] in IMPLIED:
            r["x-implied-by"] = IMPLIED[r["no"]]
    p.write_text(json.dumps(rel, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def catalog(root):
    p = root / spec.CATALOG
    lines = p.read_text(encoding="utf-8").split("\n")
    header = None
    for i, ln in enumerate(lines):
        if not ln or ln.startswith("#"):
            continue
        cols = ln.split("\t")
        if header is None:
            header = cols
            continue
        k = header.index("schema")
        if cols[k].endswith(".form.yaml"):
            base = cols[k][:-len(".form.yaml")]
            name = EVENTS.get(cols[0])
            if name is not None:
                d = root / "Platform" / base.rsplit("/", 1)[0]
                old = base.rsplit("/", 1)[1]
                for suffix in (".schema.json", ".layers.tsv", ".outcomes.tsv"):
                    (d / (name + suffix)).write_bytes((d / (old + suffix)).read_bytes())
                base = base.rsplit("/", 1)[0] + "/" + name
            cols[k] = base + ".schema.json"
            lines[i] = "\t".join(cols)
    p.write_text("\n".join(lines), encoding="utf-8")
    for d in sorted((root / "Platform").glob("*/data")):
        for suffix in (".schema.json", ".layers.tsv", ".outcomes.tsv"):
            if (d / ("events" + suffix)).exists() and (d / "events-unit.schema.json").exists():
                (d / ("events" + suffix)).unlink()


def drop_dialect(root):
    gone = sorted((root / "Platform").glob("*/data/*.form.yaml")) + [
        root / "Platform/common/data/common.form.yaml", root / "Platform/02-installer/spec/02.1-installer.form.yaml",
        root / "Platform/02-installer/spec/02.1-installer.references.tsv",
        root / "Platform/common/DIALECT.md"]            # за меткой dialect-reference-dc94d0fd1 (решение 2026-10-28)
    for p in gone:
        if p.exists():
            p.unlink()
    return len(gone)


# ---------------------------------------------------------------- 4: корпус P/02.1

def corpus(root):
    cases = root / CORPUS / "cases"
    n7 = 0
    for p in sorted(cases.glob("*.subsystem.yaml")):
        case = p.name[:-len(".subsystem.yaml")]
        data = p.read_bytes()
        if case in P7_SKIP or re.search(rb"(?m)^worker\s*:", data):
            continue
        p.write_bytes(data + (b"" if data.endswith(b"\n") or not data else b"\n") + WORKER)
        n7 += 1
    verdicts = {r[0]: r[1] for r in tsv(root / CORPUS / "verdicts.tsv")}
    classes = {r[0]: r[1] for r in tsv(root / CORPUS / "classes.tsv")}
    for r in tsv(SETB / "deltas.tsv"):
        rid, new = r[0], r[2]
        if rid.startswith("corpus/"):
            case = rid[len("corpus/"):]
            verdicts[case] = "ok" if new == "ok" else "refused"
            if new != "ok":
                classes[case] = new.split(":", 1)[1]
        elif rid.startswith("classes/"):
            case = rid[len("classes/"):]
            if new.startswith("строка снимается"):
                classes.pop(case, None)
            else:
                classes[case] = new.split(" ")[0]
    added = []
    for r in tsv(SETB / "cases.tsv"):
        cid, where, expect, dup = r[0], r[1], r[2], r[7]
        if where != "corpus" or dup or cid.startswith("p3_") or cid == "id":
            continue
        (cases / (cid + ".subsystem.yaml")).write_bytes((SETB / "cases" / (cid + ".subsystem.yaml")).read_bytes())
        verdicts[cid] = "ok" if expect == "ok" else "refused"
        if expect != "ok":
            classes[cid] = expect.split(":", 1)[1]
        added.append(cid)
    note = "# Набор Б ADR-0092 (пакет перехода на В7): случаи t*, f*, r* — v7/out/setb/cases.tsv"
    edit(root / CORPUS / "verdicts.tsv", verdicts, note)
    edit(root / CORPUS / "classes.tsv", classes, note)
    diag = root / CORPUS / "diagnostics.tsv"           # подсказка (п. 5): строки только у отказанных случаев
    edit(diag, {r[0]: "\t".join(r[1:]) for r in tsv(diag) if verdicts.get(r[0]) == "refused"}, None)
    added = len(added)
    return n7, added


def edit(path, values, note):
    """Таблица case<TAB>…: строки — на своих местах (значение — из values, нет в values — строка снимается), комментарии
    как были; ключи values без строки — в конец под строкой note."""
    lines, seen = [], set()
    for ln in Path(path).read_text(encoding="utf-8").split("\n"):
        if not ln or ln.startswith("#"):
            lines.append(ln)
            continue
        case = ln.split("\t", 1)[0]
        seen.add(case)
        if case in values:
            lines.append(case + "\t" + values[case])
    while lines and lines[-1] == "":
        lines.pop()
    more = [k for k in values if k not in seen]
    if more:
        lines += [note] + [k + "\t" + values[k] for k in more]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- 9: пакет yaml-suite (п. 2.6)

YAML_SUITE = Path("Platform/common/vectors/yaml-suite")
YAML_README = """# Векторы yaml-suite: слой 1 на yaml-test-suite (ADR-0092 п. 2; набор Б, раздел «слой 1 сужает YAML 1.2.2»)

Источник — yaml-test-suite (github.com/yaml/yaml-test-suite), данные тега `data-2022-01-17`: архив
`https://github.com/yaml/yaml-test-suite/archive/refs/tags/data-2022-01-17.tar.gz`, sha256
`ccae49c1d010d27c20d315969a97752f95b14642fc1e73755db4eb2df4bb0256`. Лицензия — MIT, текст целиком — `LICENSE` (файл
`License` репозитория, тег `v2022-01-17`, sha256 `c9562189164244554a69ab3f29d2d93ed9492c165723aaaa5fffc932cdbbfc85`).
Приёмка идёт без сети: входы — в пакете, `inputs/<id>.yaml` — байты `in.yaml` теста (402 файла; `id` с `/` — подкаталог).
`expect.tsv`: `id<TAB>suite<TAB>layer1<TAB>rule`:
- `id` — путь каталога теста в архиве, вход — `inputs/<id>.yaml`;
- `suite` — ожидание набора: `error` (вход вне YAML 1.2.2) или `ok`;
- `layer1` — исход слоя 1 манифеста (парсер YAML 1.2.2 и тонкая проверка Н1.1): `ok` или `refused`; `refused` при
  `suite` = `ok` — сужение YAML 1.2.2 нормой (правило тонкой проверки или вход вне подмножества Н1.1), утверждено
  набором Б;
- `rule` — правило тонкой проверки, отказавшее первым (`parser` — отказ парсера; `-` — у `ok`); подсказка, не норма.
Ответ реализации на строку — JSON `{"layer1": "ok"|"refused"}`, по желанию с `"rule"`: строго сравнивается только
`layer1` (иное — красное, ADR-0092 п. 2); `rule` — подсказка, как `diagnostics.tsv` корпуса: в отчёт, без провала
(имена правил реализации — свои; перечень правил тонкой проверки — `common/LAYERS.md`).
"""


# Закреплённый набор yaml-test-suite (ревью Codex RВ7-03): архив тега data-2022-01-17 (sha256 — README пакета,
# VERSIONS.md), распакованный каталог — по содержимому: sha256 строк «путь\0sha256 файла\n» всех файлов по порядку пути.
YTS_FILES = 1887
YTS_TESTS = 402
YTS_DIGEST = "e11b60dbdba6ba9f3a2a9f41b0fbc1c4efdcb7a0aafcf5aa250d56200143e8a5"


def suite_digest(suite):
    """(число файлов, sha256 содержимого) каталога набора."""
    import hashlib
    files = sorted(p for p in Path(suite).rglob("*") if p.is_file() and p.name != ".DS_Store")
    h = hashlib.sha256()
    for f in files:
        h.update(f.relative_to(suite).as_posix().encode("utf-8") + b"\0" +
                 hashlib.sha256(f.read_bytes()).hexdigest().encode("ascii") + b"\n")
    return len(files), h.hexdigest()


def check_suite(suite):
    """Набор — ровно закреплённый: есть, полон, тот же по содержимому; иначе — отказ до первой правки дерева."""
    from v7 import yts
    suite = Path(suite)
    if not suite.is_dir():
        sys.exit("yaml-test-suite %s is missing: unpack the archive of tag data-2022-01-17 (v7/VERSIONS.md) and pass "
                 "--yts DIR" % suite)
    n, digest = suite_digest(suite)
    tests = sum(1 for _ in yts.tests(suite))
    if (n, tests, digest) != (YTS_FILES, YTS_TESTS, YTS_DIGEST):
        sys.exit("yaml-test-suite %s is not the pinned one: %d files, %d tests, sha256 %s (want %d, %d, %s)"
                 % (suite, n, tests, digest, YTS_FILES, YTS_TESTS, YTS_DIGEST))


def yaml_suite(root, suite):
    """expect.tsv по всем тестам закреплённого набора (проверен check_suite до правок дерева)."""
    from v7 import textv7, thin_rules, yts
    rows = []
    for tid, d in yts.tests(Path(suite)):
        try:
            textv7.load_text_map((d / "in.yaml").read_bytes())
            got, rule = "ok", "-"
        except textv7.TextRefused as exc:
            got, rule = "refused", thin_rules.rule_of(exc)
        rows.append([tid, "error" if (d / "error").exists() else "ok", got, rule])
    out = root / YAML_SUITE
    out.mkdir(parents=True, exist_ok=True)
    (out / "README.md").write_text(YAML_README, encoding="utf-8")
    (out / "LICENSE").write_bytes((HERE / "out" / "yts" / "LICENSE").read_bytes())
    for tid, d in yts.tests(Path(suite)):
        dst = out / "inputs" / (tid + ".yaml")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((d / "in.yaml").read_bytes())
    write_tsv(out / "expect.tsv", [], ["id", "suite", "layer1", "rule"], rows)
    return len(rows)


# ---------------------------------------------------------------- 8: читатели в outcomes.tsv

def star_readers(root):
    """Роли уроков, чей абзац «Данные» читает ключ (readers `*`), и разобранные строки каталога — проходом check_spec."""
    import contextlib
    import io
    sys.path.insert(0, str(HERE.parent))
    import check_spec
    check = check_spec.Check(root, None, False)
    with contextlib.redirect_stdout(io.StringIO()):
        for lesson in sorted((root / "Platform").glob("[0-9][0-9]-*/[0-9][0-9]-*.md")):
            if any((lesson.parent / "spec").glob("*.norms.md")):
                check.lesson(lesson.resolve())
    return check.star_readers, dict(check.catalog)        # (key, kind) → строка


def outcome_readers(root):
    """Заготовка столбца `reader`: строки пустого пути — по читателю (проза копируется), прочие — `*`."""
    star, rows = star_readers(root)
    n = 0
    for (key, _kind), row in rows.items():
        if not row["schema"].endswith(".schema.json"):
            continue
        roles = spec.reading_roles(row, star.get(key, set()))
        p = root / "Platform" / row["schema"].replace(".schema.json", ".outcomes.tsv")
        out = []
        for ln in p.read_text(encoding="utf-8").split("\n"):
            if not ln or ln.startswith("#"):
                out.append(ln.replace("Строка: path<TAB>outcome", "Строка: path<TAB>reader<TAB>outcome"))
                continue
            path, rest = ln.split("\t", 1)
            if ln.startswith("path\t"):
                out.append("path\treader\t" + rest)
            elif path == "":
                out += ["\t".join([path, r, rest]) for r in sorted(roles)]
                n += len(roles)
            else:
                out.append("\t".join([path, "*", rest]))
        p.write_text("\n".join(out), encoding="utf-8")
    return n


# ---------------------------------------------------------------- 6: пакет family-read

README = """# Векторы family-read (ADR-0087 доп. (9) п. 2; ADR-0092 Confirmation, набор А и Б)

Чтение семьи данных каталога (`Platform/common/data/catalog.tsv`) общей библиотекой реализации: вход — семья (`key`,
`kind`), режим `writer` или `reader`, текст экземпляра; исход — вердикт, пути отказа (JSON Pointer), исход
`<семья>.outcomes.tsv` (только у читателя). Схема семьи — колонка `schema` каталога (JSON Schema 2020-12), слои — слова
`x-*` схемы и `codec.tsv`.

Таблица `NN.tsv` — семьи урока-владельца NN (колонка `owner` каталога). Строка:
`case<TAB>family<TAB>key<TAB>kind<TAB>mode<TAB>who<TAB>text<TAB>verdict<TAB>paths<TAB>outcome<TAB>note`:
- `family` — шаблон колонки `key` каталога; `key` — конкретный ключ строки: литералы шаблона — точно, плейсхолдер — по
  грамматике таблицы плейсхолдеров `Platform/common/data/README.md`; ключ не по шаблону — `refused`, путь `""` (строка
  целиком, значение не судится; не `/key` — это путь поля `key` семей P/08), исход — строки пустого пути;
- `who` — кто исполняет, JSON-массив ролей: у `writer` — роли операций каталога (`ops`), у `reader` — читатели семьи
  (строки пустого пути `<семья>.outcomes.tsv`: `readers` каталога ∪ участники `cas` и `guard`), в порядке файла;
- `text` — у `row` — JSON-объект полей `items` (значения — строки, как записаны в хранилище); у `object` и `file` —
  текст значения как есть;
- `verdict` — `ok` или `refused`; `paths` — JSON-массив путей отказа (порядок не важен); `outcome` — у писателя `[]`,
  у читателя — JSON-объект «роль → массив путей строк `<семья>.outcomes.tsv`, чей исход у этой роли действует»
  (пустой путь — строка целиком);
- `note` — мутация набора А (`base` — экземпляр без мутации) или id случая набора Б.

Ответ реализации на строку — JSON `{"verdict", "paths", "outcome"}`: строго сравниваются вердикт, множество путей и
исход (у читателя — по каждой роли `who`); `note` и `case` — имена строки.

Ожидания — эталон диалекта (метка `dialect-reference-dc94d0fd1`) с дельтами набора Б ADR-0092 (`1e400` — число вне
binary64: отказ места, писатель не падает). Раннер сравнивает вердикт, множество путей и исходы.

Порядок перебора отображений (D18): у Go перебор `map` случаен — выражение и проверка не должны зависеть от порядка
ключей (уникальность и `prefix_free` — без номеров элементов); набор на Go гоняют не один раз.
"""


def whom(root, row, mode, outcomes, cache):
    """who и исход строки пакета: писатель — роли операций, исход []; читатель — читатели исходов семьи, исход — тот же
    набор путей строк исходов у каждого (заготовка: строки пустого пути — копии по читателям)."""
    if mode == "writer":
        return json.dumps(spec.who_of(row, mode), ensure_ascii=False), []
    roles = spec.family_readers(root, row, cache)
    return json.dumps(roles, ensure_ascii=False), {r: outcomes for r in roles}


def templates_of(root):
    templates, errors = spec.key_templates(root, spec.read_catalog(root))
    if errors:
        sys.exit("family-read: the placeholder table of the catalog keys:\n  " + "\n  ".join(errors))
    return templates


def family_read(root, lessons):
    cat = {(r["key"], r["kind"]): r for r in spec.read_catalog(root)}
    templates = templates_of(root)
    fams = {}
    fixes = {}
    for r in tsv(SETB / "deltas.tsv"):
        if r[0].startswith("family-read/"):
            fixes[r[0][len("family-read/"):]] = r[2]
    tables = {}
    for i, ln in enumerate((SETA / "family-read.jsonl").read_text(encoding="utf-8").splitlines()):
        x = json.loads(ln)
        if x["lesson"] not in lessons:
            continue
        ref = x["ref"]
        verdict, paths, outcomes = ref["verdict"], ref["paths"], ref["outcomes"]
        fix = fixes.get("%s|%s|%s|%s" % (x["family"], x["kind"], x["mode"], x["why"]))
        if fix is not None:
            m = re.fullmatch(r"(\w+) (\[.*?\]) (\[.*\])", fix)      # setb.py пишет списки по repr Python
            verdict, paths, outcomes = m.group(1), ast.literal_eval(m.group(2)), ast.literal_eval(m.group(3))
        row = cat[(x["family"], x["kind"])]
        who, outcomes = whom(root, row, x["mode"], outcomes, fams)
        tables.setdefault(x["lesson"], []).append(
            ["%s-%04d" % (x["lesson"], len(tables.get(x["lesson"], [])) + 1), x["family"],
             templates[(x["family"], x["kind"])].example(), x["kind"], x["mode"], who,
             x["text"], verdict, json.dumps(paths, ensure_ascii=False), json.dumps(outcomes, ensure_ascii=False), x["why"]])
    for r in tsv(SETB / "cases.tsv"):
        if not r[1].startswith("family-read|"):
            continue
        _, fam, mode = r[1].split("|")
        src = json.loads((SETB / "cases" / (r[0] + ".json")).read_text(encoding="utf-8"))
        kind = src["kind"]
        lesson = src["schema"][:2]
        if lesson not in lessons:
            continue
        m = re.fullmatch(r"(\w+) (\[.*?\]) (\[.*\])", r[2])
        row = cat[(fam, kind)]
        who, outs = whom(root, row, mode, json.loads(m.group(3)), fams)
        tables.setdefault(lesson, []).append(
            ["%s-%s" % (lesson, r[0]), fam, templates[(fam, kind)].example(), row["kind"], mode, who, src["text"],
             m.group(1), m.group(2),
             json.dumps(outs, ensure_ascii=False), r[0]])
    d = root / FAMILY_READ
    d.mkdir(parents=True, exist_ok=True)
    (d / "README.md").write_text(README, encoding="utf-8")
    for lesson, rows in sorted(tables.items()):
        rows += key_rows(root, cat, templates, rows, fams)
        write_tsv(d / ("%s.tsv" % lesson), [], HEADER, rows)
    return {k: len(v) for k, v in sorted(tables.items())}


KEY_NOTE = "key: "


def key_rows(root, cat, templates, rows, fams):
    """Строки «ключ не по шаблону» (V7-FAMILY-KEY-PLACEHOLDER-01): у каждой семьи таблицы и режима — по строке на
    плейсхолдер (и на литерал у шаблона без плейсхолдеров); текст — первой строки `ok` семьи в этом режиме; отказ —
    строка целиком, исход — строки пустого пути."""
    lesson = rows[0][0][:2]
    out, seen = [], []
    for r in rows:
        k = (r[1], r[3], r[4])
        if k not in seen and not r[-1].startswith(KEY_NOTE):
            seen.append(k)
    for fam, kind, mode in seen:
        mine = [r for r in rows if (r[1], r[3], r[4]) == (fam, kind, mode) and not r[-1].startswith(KEY_NOTE)]
        text = next((r[6] for r in mine if r[7] == "ok"), mine[0][6])
        row = cat[(fam, kind)]
        who, outs = whom(root, row, mode, [], fams)
        if mode == "reader":
            outcomes = fams[(fam, kind)][1]
            outs = {r: [o.path for o in spec.outcomes_for(outcomes, spec.KEY_REFUSED, r)] for r in outs}
        for what, key in templates[(fam, kind)].off():
            out.append(["%s-k%04d" % (lesson, len(out) + 1), fam, key, kind, mode, who, text, "refused",
                        json.dumps(spec.KEY_REFUSED), json.dumps(outs, ensure_ascii=False), KEY_NOTE + what])
    return out


ADD_NOTE = "add: "


def add_rows(root, base, text, note):
    """Строки family-read по образцу base (case): та же семья и ключ, текст text, у писателя и у читателя (строки семьи
    в обоих режимах, как у образца) — вердикт, пути и исход — стек В7 (spec.judge_family, outcomes_for по ролям who).
    case — `<NN>-x<NNNN>`, note — `add: <note>`; есть строка семьи с той же note — ничего не добавляется. → [case]."""
    d = root / FAMILY_READ
    cat = {(r["key"], r["kind"]): r for r in spec.read_catalog(root)}
    templates = templates_of(root)
    for p in sorted(d.glob("[0-9][0-9].tsv")):
        lines = tsv(p)
        rows = lines[1:]
        src = next((r for r in rows if r[0] == base), None)
        if src is None:
            continue
        fam, key, kind = src[1], src[2], src[3]
        if any(r[1] == fam and r[-1] == ADD_NOTE + note for r in rows):
            return []
        from v7 import stack
        _, _, doc, _, outcomes = spec.load_family(root, cat[(fam, kind)])
        family = stack.Family(doc, kind)
        made = []
        for mode in ("writer", "reader"):
            like = next((r for r in rows if r[1] == fam and r[3] == kind and r[4] == mode), None)
            if like is None:
                continue
            who = json.loads(like[5])
            v = spec.judge_family(family, templates[(fam, kind)], key, kind, text, mode)
            outs = ({r: [o.path for o in spec.outcomes_for(outcomes, v["paths"], r)] for r in who}
                    if mode == "reader" else [])
            n = 1 + sum(1 for r in rows if r[0].startswith(p.stem + "-x"))
            case = "%s-x%04d" % (p.stem, n)
            rows.append([case, fam, key, kind, mode, like[5], text, v["verdict"],
                         json.dumps(v["paths"], ensure_ascii=False), json.dumps(outs, ensure_ascii=False),
                         ADD_NOTE + note])
            made.append(case)
        write_tsv(p, [], HEADER, rows)
        return made
    sys.exit("family-read: no row %s" % base)


def family_keys(root):
    """Пакет family-read на месте (данные «Спецификации»): столбец `key` после `family` — пример по шаблону каталога
    (таблица плейсхолдеров README каталога); строки `key: …` — заново. Повтор — те же байты. → {урок: строк ключа}."""
    cat = {(r["key"], r["kind"]): r for r in spec.read_catalog(root)}
    templates = templates_of(root)
    d = root / FAMILY_READ
    old = ["case", "family", "kind", "mode", "who", "text", "verdict", "paths", "outcome", "note"]
    fams, done = {}, {}
    for p in sorted(d.glob("[0-9][0-9].tsv")):
        lines = tsv(p)
        if lines[0] == old:
            rows = [r[:2] + [templates[(r[1], r[2])].example()] + r[2:] for r in lines[1:]]
        elif lines[0] == HEADER:
            rows = lines[1:]
        else:
            sys.exit("%s: the header is neither the old one nor %s" % (p, "<TAB>".join(HEADER)))
        rows = [r for r in rows if not r[-1].startswith(KEY_NOTE)]
        keys = key_rows(root, cat, templates, rows, fams)
        write_tsv(p, [], HEADER, rows + keys)
        done[p.stem] = len(keys)
    return done


# ---------------------------------------------------------------- всё

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--lessons", default="01,02,03,04,05,06")
    from v7 import yts
    ap.add_argument("--yts", default=str(yts.SUITE), help="распакованный yaml-test-suite data-2022-01-17 (закреплён)")
    ap.add_argument("--keys", action="store_true", help="только столбец key пакета family-read на месте (дерево В7)")
    ap.add_argument("--add-row", nargs=3, metavar=("BASE", "TEXT", "NOTE"),
                    help="строки family-read по образцу BASE: текст TEXT, заметка NOTE, исход — стек В7 (дерево В7)")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    if a.keys:
        print("family-read key rows:", family_keys(root))
        return
    if a.add_row:
        print("family-read rows:", add_rows(root, *a.add_row))
        return
    if not (root / "Platform/02-installer/spec/02.1-installer.form.yaml").is_file():
        sys.exit("the tree has no dialect form of P/02.1: already moved?")
    check_suite(a.yts)                                   # все входы — до первой правки дерева
    standard_files(root)
    implied(root)
    catalog(root)
    print("dialect files removed:", drop_dialect(root))
    print("corpus: worker appended %d, cases added %d" % corpus(root))
    from v7 import vectors
    print("canonical vectors:", vectors.generate(root))
    print("outcomes: rows of the whole row by reader:", outcome_readers(root))
    print("family-read:", family_read(root, set(a.lessons.split(","))))
    print("yaml-suite:", yaml_suite(root, a.yts))
    from v7 import sections
    for norms in sorted((root / "Platform").glob("*/spec/*.norms.md")):
        text = norms.read_text(encoding="utf-8")
        if any(b in text for b, _ in sections.MARKERS.values()):
            print("sections %s: %s" % (norms.relative_to(root), ", ".join(sections.rewrite(norms, root))))


if __name__ == "__main__":
    main()
