"""Сверка английского источника спецификации с производным русским текстом (ADR-0121 п. 3; ADR-0120 доп. (5) п. 7).

Две раскладки на время перехода (ADR-0124 доп. (1) п. 6): урок с каталогом `ru/` — новая, без — прежняя.
- Новая (ADR-0124): английский `X` на каноническом пути — источник, перевод — `ru/X` того же урока (тот же путь от корня
  урока) с пометкой «производный от `X`, руками не правится». Ссылки перевода ведут в переводы (`ru/Y`, русский якорь),
  ссылки источника — в источник (`Y`, английский якорь): при сверке цель перевода `<урок>/ru/Y#якорь` читается как
  `<урок>/Y#английский-якорь` по парам заголовков `Y` и `ru/Y` (один к одному). Построенные блоки сверяются по
  разрешённым целям ссылок: у источника и перевода глубина путей разная. Мелкие дома — корень курса
  (`НОРМАТИВНЫЕ-СЛОВА.md`, `КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md`; доп. (1) п. 4) и каталог модуля (`VMS/README.md`) с `ru/`:
  пара — свой файл `X` ↔ `ru/X`; прочие файлы рядом (записки курса, `Platform/lessons.tsv`) — не источники.
- Прежняя (ADR-0121): английский `<каталог>/en/<имя>.en.md` — источник (нормы — в `spec/en/`); русский
  `<каталог>/<имя>.md` — производный, с пометкой «производный от en, руками не правится».
Сверяется по разделам `##` и `###`, по порядку: разделов столько же,
уровни те же, у каждого раздела равны
- номера норм `Н…` в заголовках;
- множества ссылок: `P/NN[.K][-MM]`, `ADR-NNNN`, `Н…`, id находок (`C01-ROW-INDEX-LOST-01`), цели ссылок Markdown
  (путём от корня, у английского файла на каталог глубже);
- множество HTTP-кодов (100–599 целым словом) и множество слов отказов (виды `kind` таблиц Н4 урока) — в `code`-вставках
  и блоках кода;
- `code`-вставки русского раздела есть и в английском (английский МОЖЕТ добавить свои: алгоритм называет переменные);
- числа русской прозы раздела есть в английской;
- таблицы: столько же, строк столько же; в каждой ячейке — те же числа и `code`-вставки, ячейка без кириллицы — та же;
- блоки кода с пометкой языка (```yaml …) — по строкам: строк столько же, у каждой тот же отступ, тот же ключ, те же
  числа; строка без кириллицы (вне комментария `#`) — та же; переводятся только комментарии и русская проза значений.
  Блок без пометки — процедура: английский пишет её нумерованным алгоритмом (ADR-0120 п. 1 (а)), построчно не сверяется.
Чеклист: id `P/…-MM` — те же, в том же порядке. Кириллица в английском — только в `code`, «…», номерах `Н…`, целях
ссылок, именах файлов, прежних уроков (`М10A_Platform/…`, `М10/11`) и id ревью (`А1`): русские слова там — нарушение.
Блоки `families`, `form`, `canonical` (sections.py): в раскладке ADR-0124 источник несёт английский блок, перевод —
русский (ADR-0121 доп. (3) п. 1); сверка построчно — форма строки, `code` (метки по словарю `Platform/common/placeholders.tsv`),
числа, цели ссылок. В прежней раскладке — байт в байт.
"""
import os
import re
from pathlib import Path

MARK = "производный от en, руками не правится"      # прежняя раскладка (ADR-0121)
REQ_ANCHOR = re.compile(r"^<!-- (?:req|removed): [^\n]*-->\n", re.M)   # якоря требований (ADR-0122 доп. (1) п. 1)
# Машинный Markdown: байты продукта (промпты ассистента V/11 `harness/**`), уже английские, без перевода и вне пар
# (ADR-0124 доп. (1) п. 4; tools/layout/migrate.py — то же правило).
MACHINE_MD = re.compile(r"(?:^|/)harness/")


def mark(rel):
    """The mark of a translation in the layout of ADR-0124 (addendum (1) item 8 (1)): the source by its path from the
    root of the lesson."""
    return f"производный от `{rel}`, руками не правится"


MODULES = ("Platform", "VMS")


def home_of(path, root):
    """The home of a path in the layout of ADR-0124 → (home, path from the home) or None:
    - a lesson (or `common`): a directory `Platform/<x>` or `VMS/<x>` that holds `ru/` — any path in it;
    - a shallow home (ADR-0124 доп. (1) п. 4): the root of the course or a module directory `Platform`, `VMS` that holds
      `ru/` — its `ru/…` and its own file `X` that has the translation `ru/X` (the notes beside it are not sources)."""
    root = Path(root)
    try:
        parts = Path(os.path.normpath(Path(path))).relative_to(root).parts
    except ValueError:
        return None
    if not parts:
        return None
    if parts[0] in MODULES and len(parts) >= 3 and parts[1] not in ("en", "ru"):
        home = root / parts[0] / parts[1]
        return (home, Path(*parts[2:])) if (home / "ru").is_dir() else None
    if parts[0] in MODULES:
        home, rest = root / parts[0], parts[1:]
    elif len(parts) == 1 or parts[0] in ("en", "ru"):
        home, rest = root, parts
    else:
        return None
    if not rest or not (home / "ru").is_dir():
        return None
    if rest[0] == "ru" or (len(rest) == 1 and (home / "ru" / rest[0]).is_file()):
        return home, Path(*rest)
    return None


def slug(text):
    """GitHub's anchor of a heading text: lower case; letters, digits, marks, `-`, `_` kept; spaces → `-`."""
    import unicodedata
    return "".join("-" if ch == " " else ch for ch in text.lower()
                   if ch in "-_ " or unicodedata.category(ch)[0] in "LNM")


def heading_text(raw):
    raw = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = re.sub(r"(`+)(.+?)\1", r"\2", raw)
    raw = re.sub(r"(\*\*|__|\*)(.+?)\1", r"\2", raw)
    return raw.strip()


def anchors_in_order(text):
    """[(level, anchor)] of the ATX headings outside code blocks, in order; a repeated anchor gets -1, -2…"""
    seen, out = {}, []
    for line in re.sub(r"^(`{3,}|~{3,})[^\n]*\n.*?^\1[ \t]*$", "", text, flags=re.M | re.S).splitlines():
        m = re.match(r"^(#{1,6})[ \t]+(.+?)[ \t#]*$", line)
        if m:
            base = slug(heading_text(m.group(2)))
            n = seen.get(base, 0)
            seen[base] = n + 1
            out.append((len(m.group(1)), base if n == 0 else f"{base}-{n}"))
    return out


_ANCHORS = {}


def source_anchor(source, translation, anchor):
    """A Russian anchor of the translation → the English anchor of its source (headings one to one), else as is."""
    key = (source, translation)
    if key not in _ANCHORS:
        try:
            en = anchors_in_order(Path(source).read_text(encoding="utf-8"))
            ru = anchors_in_order(Path(translation).read_text(encoding="utf-8"))
            _ANCHORS[key] = {r: e for (_, r), (_, e) in zip(ru, en)} if [a for a, _ in en] == [a for a, _ in ru] else {}
        except OSError:
            _ANCHORS[key] = {}
    return _ANCHORS[key].get(anchor, anchor)


def as_source(rel, root):
    """A target `<урок>/ru/Y[#a]` (path from the root) → `<урок>/Y[#английский a]` when `Y` is a source of a lesson in
    the layout of ADR-0124; any other target as is."""
    path, _, anchor = rel.partition("#")
    moved = home_of(Path(root) / path, root)
    if moved and len(moved[1].parts) >= 2 and moved[1].parts[0] == "ru":
        source = (moved[0] / Path(*moved[1].parts[1:])).relative_to(Path(root))
        if (Path(root) / source).exists():
            if "#" in rel:
                anchor = source_anchor(Path(root) / source, Path(root) / path, anchor)
            return source.as_posix() + ("#" + anchor if "#" in rel else "")
    return rel
H2 = re.compile(r"^###? ", re.M)                   # разделы и подразделы: сверка по каждому
FENCE = re.compile(r"^[ \t]*```[^\n]*\n.*?^[ \t]*```[ \t]*$", re.M | re.S)   # и с отступом — блок внутри пункта списка
SPAN = re.compile(r"(`+)(.+?)\1", re.S)
NORM_NO = re.compile(r"(?<![\wА-Яа-яЁё])[НN][0-9]+(?:\.[0-9]+)*[а-яa-e]?(?!\w|\.[0-9])")   # N… латиницей — доп. (5) п. 1
LESSON = re.compile(r"(?<![\w/])P/[0-9]{2}(?:\.[0-9]+)?(?:-[0-9]{2})?(?![0-9])")
ADR = re.compile(r"\bADR-[0-9]{4}\b")
FINDING = re.compile(r"(?<![\w-])[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-[0-9]{2}(?![\w-])")
CODE = re.compile(r"(?<![\w.])[1-5][0-9]{2}(?![\w.])")
LINK = re.compile(r"\]\(([^()\s]+)\)")
CHECK_ID = re.compile(r"^- \[[ xX]\] \*\*(P/[0-9.]+-[0-9]+)\*\*", re.M)
TABLE_ROW = re.compile(r"^\|.*\|[ \t]*$", re.M)
CYR = re.compile(r"[А-Яа-яЁё]")
# Суффиксы шагов и метки ревью — латиницей и в источнике, и в переводе (ADR-0121 доп. (3) п. 3): 4a, 2b, A1, G-29, V7, P1;
# кириллица там — нарушение правила «Кириллица в английском» ниже (разрешены только номера норм Н… и прежние уроки М10–М12).
# Модуль, ещё не переведённый на латиницу меток, — прежнее разрешение (VMS — «Спецификация VMS»); список только сокращается.
LABELS_PENDING = {"VMS"}
# Уроки, где номера разделов уже латиницей N… (ADR-0121 доп. (5) п. 1): Н<цифра> в источнике — отказ; список растёт до всех.
NUMBERS_DONE = ("Platform/", "НОРМАТИВНЫЕ-СЛОВА.md", "КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md")
CYR_NUMBER = re.compile(r"(?<![\wА-Яа-яЁё])Н[0-9]")
# Таблица меток ключей каталога — сырые ключи catalog.tsv (их читает читатель «Генераторов»): метки в ней — как в каталоге,
# пока каталог не сменится вместе с генераторами (ADR-0121 доп. (5) п. 3).
RAW_LABEL_FILES = {"Platform/common/data/README.md"}
RU_LABEL = re.compile(r"<([^<>`\n|=]*[А-Яа-яЁё][^<>`\n|=]*)>")
LEGACY_LABELS = [re.compile(r"(?<![\w])М[0-9]+[A-Z]?(?:_[A-Za-z]+)?(?:/[0-9]+)?"),
                 re.compile(r"(?<![\w-])[А-ЯЁ]-?[0-9]+[а-я]?(?![\w])|(?<![\w])[0-9]+[а-я](?![\w])"),
                 re.compile(r"<[^<>`\n|=]*[А-Яа-яЁё][^<>`\n|=]*>")]          # и русские метки подстановки
ALLOWED_CYR = [SPAN, re.compile(r"«[^»\n]*»"), NORM_NO, LINK,
               re.compile(r"[\wА-Яа-яЁё.-]*[А-Яа-яЁё][\wА-Яа-яЁё.-]*\.(?:md|tsv|yaml|json)\b"),   # имена файлов
               re.compile(r"(?<![\w])М1[0-2][A-Z]?(?:_[A-Za-z]+)?(?:/[0-9]+)?"),   # прежние уроки М10, М11, М12A
               ]               # заполнители кода — те же, что в русском: <роль>, <форма>, <т>   # id находок ревью по-русски: А1, А10


def sections(text):
    """Text → [(title, body)] by `## ` headings; the part before the first one is section 0 («»)."""
    starts = [m.start() for m in H2.finditer(text)]
    bounds = [0, *starts, len(text)]
    out = []
    for a, b in zip(bounds, bounds[1:]):
        part = text[a:b]
        title = part.split("\n", 1)[0].lstrip("#").strip() if part.startswith("#") else ""
        out.append((title, part))
    return out


def kinds_of(ru_text):
    """Refusal words: the first code span of the `kind` column (third) of the Н4 table of the Russian text."""
    words = set()
    for title, body in sections(ru_text):
        if not re.match(r"[НN]4(?:\s|$)", title):
            continue
        for row in TABLE_ROW.findall(body):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", row.strip().strip("|"))]
            if len(cells) >= 3 and re.fullmatch(r"[1-5][0-9]{2}", cells[1]):      # шапка таблицы — не строка
                span = SPAN.search(cells[2])
                if span and re.fullmatch(r"[a-z]+", span.group(2)):
                    words.add(span.group(2))
    return words


def code_parts(body):
    return [m.group(2) for m in SPAN.finditer(FENCE.sub("", body))] + FENCE.findall(body)


def links(body, base, root):
    out = set()
    text = SPAN.sub(lambda m: m.group(0) if m.string.startswith("](", m.end()) else " ", FENCE.sub("", body))   # «](…)» внутри кода — не ссылка
    for target in LINK.findall(text):
        path = target.split("#", 1)[0]
        if not path:                                   # a heading of the same file: its anchor follows the language
            out.add("#")
            continue
        if re.match(r"[a-z]+:", path):
            out.add(target)
            continue
        whole = os.path.normpath(base / path)
        try:
            rel = Path(whole).relative_to(root)
        except ValueError:
            rel = Path(whole)
        out.add(as_source(rel.as_posix() + ("#" + target.split("#", 1)[1] if "#" in target else ""), root))
    return out


def facts(body, base, root, kinds, pair=()):
    prose = body
    code = code_parts(body)
    linktext = re.sub(r"\[`[^`\n]*`\]\(", "[](", FENCE.sub("", body))   # путь в тексте ссылки — у en на каталог глубже
    spans = {m.group(2) for m in SPAN.finditer(linktext)}
    words = {w for part in code for w in re.findall(r"[a-z]+", part) if w in kinds}
    return {
        "norm numbers in headings": [m.group(0) for line in body.splitlines() if line.startswith("#")
                                     for m in NORM_NO.finditer(line)],
        "references": (set(LESSON.findall(prose)) | set(ADR.findall(prose)) | set(NORM_NO.findall(prose))
                       | set(FINDING.findall(prose))),
        "link targets": links(body, base, root) - set(pair),
        "HTTP codes": set(CODE.findall(prose)),
        "refusal words": words,
        "tables rows": [len(TABLE_ROW.findall(t)) for t in re.split(r"\n[ \t]*\n", FENCE.sub("", body))
                        if TABLE_ROW.search(t)],
        "spans": spans,
    }


NUMBER = re.compile(r"(?<![\w.,])[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})+(?![\w])|(?<![\w.])[0-9]+(?:[.,][0-9]+)*(?![\w])")


def numbers(text, lang):
    """Numbers of a text by value of notation: groups of thousands by a space, «250 000» — one number; Russian «0,5» —
    decimal comma, English «250,000» — a comma before exactly three digits separates thousands («0.5» ≡ «0,5»)."""
    out = []
    for token in NUMBER.findall(text):
        token = re.sub(r"[ \u00a0\u202f]", "", token)
        if lang == "en":
            token = re.sub(r",(?=[0-9]{3}(?![0-9]))", "", token)
        out.append(token.replace(",", "."))
    return out
TAGGED = re.compile(r"^[ \t]*```([A-Za-z]+)[^\n]*\n(.*?)^[ \t]*```[ \t]*$", re.M | re.S)
TAGGED_FENCE = TAGGED
KEY = re.compile(r"^(\s*(?:- )?)([^\s:#][^:#]*?):(?=\s|$)")


def code_part(line):
    """A line of a code block without its comment (` #…` outside quotes)."""
    quote = None
    for k, ch in enumerate(line):
        if quote:
            quote = None if ch == quote else quote
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (k == 0 or line[k - 1] in " \t"):
            return line[:k].rstrip()
    return line.rstrip()


def cells(row):
    """A table row → cells; an escaped «\\|» (inside a code span of a cell) does not split it."""
    return [c.strip() for c in re.split(r"(?<!\\)\|", row.strip().strip("|"))]


STEP = re.compile(r"^[ \t>]*(?:[-*] )?[0-9]+[a-zа-яё]?[.)][ \t]", re.M)   # нумерованный шаг: прозой или в блоке


# Переводы с прежним псевдокодом, ещё не пересобранные по источнику (ADR-0121 доп. (3) М (3)): сверка шагов у них
# отложена до пересборки — P/02 после веток ревью урока, VMS — «Спецификация VMS». Список только сокращается.
STEPS_PENDING = {
    "Platform/02-installer/spec/02.1-installer.norms.md", "Platform/02-installer/spec/02.2-installer.norms.md",
    "Platform/02-installer/spec/02.3-installer.norms.md", "Platform/02-installer/spec/02.5-installer.norms.md",
    "VMS/02-rec/spec/02.4-rec.norms.md", "VMS/05-detjob/spec/05.3-detjob.norms.md", "VMS/05-detjob/spec/05.4-detjob.norms.md",
    "VMS/06-detedge/spec/06.2-detedge.norms.md", "VMS/07-auto/spec/07.3-auto.norms.md",
    "VMS/11-backend/spec/11.2-backend.norms.md", "VMS/12-psim/spec/12.3-psim.norms.md",
}


def steps(body):
    """The numbered steps of a section — in prose and inside code blocks without a language mark (a procedure written
    as pseudocode), not inside tagged blocks (yaml data)."""
    return len(STEP.findall(TAGGED_FENCE.sub("", body)))


def strict(rb, eb, count_steps=True, root=None):
    """ADR-0120 доп. (5) п. 7: values, orders and identifiers of code blocks, tables and prose agree (placeholder labels
    by the dictionary of `root`, by default the course of this script)."""
    root = Path(__file__).resolve().parents[3] if root is None else root
    out = []
    if count_steps and steps(rb) != steps(eb):     # ADR-0121 доп. (3) М (3): процедура Н3 — прозой или блоком
        out.append(f"numbered steps: {steps(eb)}, ru {steps(rb)} — rebuild the translation by the source")
    rt, et = TAGGED.findall(rb), TAGGED.findall(eb)
    if [t for t, _ in rt] != [t for t, _ in et]:
        out.append(f"tagged code blocks differ: ru {[t for t, _ in rt]}, en {[t for t, _ in et]}")
    for k, ((tag, rcode), (_, ecode)) in enumerate(zip(rt, et), 1):
        rl, el = rcode.splitlines(), ecode.splitlines()
        if len(rl) != len(el):
            out.append(f"code block {k} ({tag}): {len(el)} lines, ru {len(rl)} — translate comments and prose values only")
            continue
        for no, (r, e) in enumerate(zip(rl, el), 1):
            rc, ec = code_part(r), code_part(e)
            where = f"code block {k} ({tag}) line {no}"
            if len(r) - len(r.lstrip()) != len(e) - len(e.lstrip()):
                out.append(f"{where}: indentation differs")
            rk, ek = KEY.match(rc), KEY.match(ec)
            if rk and not CYR.search(rk.group(2)) and (not ek or rk.group(0) != ek.group(0)):
                out.append(f"{where}: key {rk.group(2)!r}, en {ek and ek.group(2)!r}")
            if not CYR.search(rc) and rc != ec:
                out.append(f"{where}: {ec!r}, ru {rc!r} — only comments are translated here")
            elif sorted(numbers(rc, "ru")) != sorted(numbers(ec, "en")):
                out.append(f"{where}: numbers {sorted(numbers(ec, 'en'))}, ru {sorted(numbers(rc, 'ru'))}")
    rtab = [t for t in re.split(r"\n[ \t]*\n", FENCE.sub("", rb)) if TABLE_ROW.search(t)]
    etab = [t for t in re.split(r"\n[ \t]*\n", FENCE.sub("", eb)) if TABLE_ROW.search(t)]
    for k, (r, e) in enumerate(zip(rtab, etab), 1):
        for no, (rr, er) in enumerate(zip(TABLE_ROW.findall(r), TABLE_ROW.findall(e)), 1):
            rc, ec = cells(rr), cells(er)
            if len(rc) != len(ec):
                out.append(f"table {k} row {no}: {len(ec)} cells, ru {len(rc)}")
                continue
            for c, (x, y) in enumerate(zip(rc, ec), 1):
                where = f"table {k} row {no} cell {c}"
                xs, ys = LINK.sub("]()", x), LINK.sub("]()", y)
                if not CYR.search(xs) and not re.search(r"\[[^\]]*[A-Za-z]{3}", xs) and xs != ys:
                    out.append(f"{where}: {y!r}, ru {x!r}")
                elif sorted(numbers(SPAN.sub("", xs), "ru")) != sorted(numbers(SPAN.sub("", ys), "en")):
                    out.append(f"{where}: numbers {sorted(numbers(SPAN.sub('', ys), 'en'))}, ru {sorted(numbers(SPAN.sub('', xs), 'ru'))}")
                elif ({as_english_labels(m.group(2), root) for m in SPAN.finditer(xs)}
                      - {as_english_labels(m.group(2), root) for m in SPAN.finditer(ys)}):
                    out.append(f"{where}: code spans {sorted({m.group(2) for m in SPAN.finditer(xs)} - {m.group(2) for m in SPAN.finditer(ys)})} missing")
    rp = TABLE_ROW.sub("", LINK.sub("]()", FENCE.sub("", rb)))
    ep = TABLE_ROW.sub("", LINK.sub("]()", FENCE.sub("", eb)))
    missing = set(numbers(rp, "ru")) - set(numbers(ep, "en"))
    if missing:
        out.append(f"numbers of the Russian prose missing: {sorted(missing)}")
    return out


BUILT = re.compile(r"<!-- (families|form|canonical):begin -->.*?<!-- \1:end -->", re.S)


def resolved(block, path, root):
    """A built block with the targets of its links resolved from its file to paths from the root (ADR-0124: the source
    and its translation lie at different depths, the block is the same)."""
    def one(m):
        target = m.group(1)
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            return m.group(0)
        whole = os.path.normpath(Path(path).parent / target.split("#", 1)[0])
        try:
            rel = Path(whole).relative_to(root).as_posix()
        except ValueError:
            rel = whole
        return "](/" + as_source(rel + ("#" + target.split("#", 1)[1] if "#" in target else ""), root) + ")"
    return LINK.sub(one, block)


PLACEHOLDERS = Path("Platform/common/placeholders.tsv")   # словарь меток ru → en (ADR-0121 доп. (3) пп. 1, 4)
_LABELS = {}


def labels(root):
    """The dictionary of placeholder labels `Platform/common/placeholders.tsv` → {ru: en}; empty without the file."""
    key = str(Path(root).resolve())
    if key not in _LABELS:
        out = {}
        try:
            rows = [ln for ln in (Path(root) / PLACEHOLDERS).read_text(encoding="utf-8").splitlines()
                    if ln and not ln.startswith("#")]
        except OSError:
            rows = []
        for ln in rows[1:]:
            ru, _, en = ln.partition("\t")
            out[ru] = en
        _LABELS[key] = out
    return _LABELS[key]


def as_english_labels(text, root):
    """Labels of the Russian text → those of the source by the dictionary: `<имя>` → `<name>`, `⟨вариант 1⟩` →
    `⟨variant 1⟩`; a label outside the dictionary stays."""
    table = labels(root)
    text = re.sub(r"<([^<>`\n]+)>", lambda m: "<%s>" % table.get(m.group(1), m.group(1)), text)
    text = re.sub(r"(?<= )\(([^()\s]+)\)$", lambda m: "(%s)" % table.get(m.group(1), m.group(1)), text)   # «.<имя> (имя)»
    return re.sub(r"⟨(\S+)( [0-9]+)⟩", lambda m: "⟨%s%s⟩" % (table.get(m.group(1), m.group(1)), m.group(2)), text)


def line_shape(line):
    """The shape of a line of a built block: a heading of its level, a table row of its cells, a list item, an empty line
    or prose."""
    if not line.strip():
        return "empty"
    if line.startswith("#"):
        return "heading " + line.split(" ", 1)[0]
    if line.startswith("|"):
        return "row of %d cells" % len(re.split(r"(?<!\\)\|", line.strip())[1:-1])
    if line.startswith("- "):
        return "item"
    return "prose"


def built_pair(ru_block, en_block, root):
    """A built block of the translation and of the source (ADR-0121 addendum (3) item 1): the source carries the English
    block, the translation the Russian one, both built from the same rows of `catalog.tsv` and the files of the form.
    Line by line: as many lines; each of the same shape, with the same code spans (labels of both read by the dictionary:
    the texts of the data carry one label for both), numbers and targets of links (resolved). → [message]."""
    out = []
    rl, el = ru_block.split("\n"), en_block.split("\n")
    if len(rl) != len(el):
        return ["%d lines, ru %d" % (len(el), len(rl))]
    for no, (r, e) in enumerate(zip(rl, el), 1):
        if line_shape(r) != line_shape(e):
            out.append("line %d: %s, ru %s" % (no, line_shape(e), line_shape(r)))
            continue
        rs = [as_english_labels(m.group(2), root) for m in SPAN.finditer(r)]
        es = [as_english_labels(m.group(2), root) for m in SPAN.finditer(e)]   # метки данных — общие, и у источника
        if rs != es:
            out.append("line %d: code spans %s, ru %s" % (no, [x for x in es if x not in rs][:3],
                                                         [x for x in rs if x not in es][:3]))
            continue
        rn, en = re.findall(r"[0-9]+", SPAN.sub(" ", r)), re.findall(r"[0-9]+", SPAN.sub(" ", e))
        if sorted(rn) != sorted(en):
            out.append("line %d: numbers %s, ru %s" % (no, sorted(en), sorted(rn)))
        elif LINK.findall(r) != LINK.findall(e):
            out.append("line %d: links %s, ru %s" % (no, LINK.findall(e), LINK.findall(r)))
    return out


def compare(ru_text, en_text, ru_path, en_path, root):
    """→ list of messages (empty: the texts agree). Built blocks between `<!-- …:begin/end -->` (sections.py): in the layout
    of ADR-0124 the source carries the English block, the translation the Russian one — compared line by line
    (built_pair; the targets of links resolved from each file); in the former layout — byte for byte."""
    en_text = REQ_ANCHOR.sub("", en_text)           # якоря требований и надгробия — только у источника (ADR-0122 доп. (1) п. 1)
    ru_blocks, en_blocks = BUILT.findall(ru_text), BUILT.findall(en_text)
    built_ru, built_en = [m.group(0) for m in BUILT.finditer(ru_text)], [m.group(0) for m in BUILT.finditer(en_text)]
    new = home_of(Path(ru_path).resolve(), Path(root).resolve()) is not None
    if new:
        r = Path(root).resolve()
        built_ru = [resolved(b, Path(ru_path).resolve(), r) for b in built_ru]
        built_en = [resolved(b, Path(en_path).resolve(), r) for b in built_en]
    pre = []
    if ru_blocks != en_blocks:
        pre.append(f"built blocks differ: ru {ru_blocks}, en {en_blocks}")
    elif new:                                       # раскладка ADR-0124: источник — английский блок, перевод — русский
        for kind, r, e in zip(ru_blocks, built_ru, built_en):
            pre.extend(f"built block «{kind}»: {m}" for m in built_pair(r, e, root)[:5])
    elif built_ru != built_en:                      # прежняя раскладка: блок один, байт в байт
        pre.append(f"built blocks differ: ru {ru_blocks}, en {en_blocks} (the English source carries them as built)")
    ru_text, en_text = BUILT.sub("<!-- built -->", ru_text), BUILT.sub("<!-- built -->", en_text)
    root, ru_path, en_path = Path(root).resolve(), Path(ru_path).resolve(), Path(en_path).resolve()
    want = mark(home_of(ru_path, root)[1].relative_to("ru").as_posix()) if new else MARK
    marked = want in ("\n".join(ru_text.splitlines()[:12]) if new else ru_text)
    ru_text = ru_text.replace(want, "производный", 1)   # пометка — не текст: её путь в `code` у источника не повторяется
    errors_pre = pre
    kinds = kinds_of(ru_text) or lesson_kinds(ru_path)
    errors = list(errors_pre)
    ru_ids, en_ids = CHECK_ID.findall(ru_text), CHECK_ID.findall(en_text)
    if ru_ids != en_ids:
        errors.append(f"checklist ids differ: ru {ru_ids} / en {en_ids}")
    ru_s, en_s = sections(ru_text), sections(en_text)
    try:
        count_steps = Path(en_path).resolve().relative_to(root).as_posix() not in STEPS_PENDING
    except ValueError:
        count_steps = True
    if len(ru_s) != len(en_s):
        errors.append(f"{len(en_s)} sections «##»/«###», the Russian text has {len(ru_s)}")
    for (rt, rb), (et, eb) in zip(ru_s, en_s):
        where = f"section «{et or '(head)'}» (ru «{rt or '(head)'}»)"
        rl, el = len(rb) - len(rb.lstrip("#")), len(eb) - len(eb.lstrip("#"))
        if rl != el:
            errors.append(f"{where}: heading level {el}, ru {rl}")
        rn, en = NORM_NO.match(rt), NORM_NO.match(et)
        if (rn and rn.group(0)) != (en and en.group(0)):
            errors.append(f"{where}: heading norm number {en and en.group(0)}, ru {rn and rn.group(0)}")
        pair = {Path(os.path.normpath(Path(p))).relative_to(root).as_posix() for p in (ru_path, en_path)}
        rf = facts(rb, Path(ru_path).parent, root, kinds, pair)
        ef = facts(eb, Path(en_path).parent, root, kinds, pair)
        errors.extend(f"{where}: {m}" for m in strict(rb, eb, count_steps=count_steps, root=root))
        for key in rf:
            if key in ("spans", "refusal words"):          # английский МОЖЕТ добавить: алгоритм называет, «unit» — и слово
                missing = rf[key] - ef[key]
                if key == "spans":                         # метки подстановки — по словарю (ADR-0121 доп. (3) п. 4)
                    missing = {x for x in missing if as_english_labels(x, root) not in ef[key]}
                if missing:
                    errors.append(f"{where}: {'code spans' if key == 'spans' else key} of the Russian text missing: {sorted(missing)}")
            elif rf[key] != ef[key]:
                if isinstance(rf[key], set):
                    errors.append(f"{where}: {key} differ: only ru {sorted(rf[key] - ef[key])}, "
                                  f"only en {sorted(ef[key] - rf[key])}")
                else:
                    errors.append(f"{where}: {key} differ: ru {rf[key]}, en {ef[key]}")
    try:
        legacy = Path(en_path).resolve().relative_to(root).parts[0] in LABELS_PENDING
    except ValueError:
        legacy = False
    allowed = ALLOWED_CYR + (LEGACY_LABELS if legacy else [])
    rest = FENCE.sub(" ", en_text)
    for pattern in allowed:
        rest = pattern.sub(" ", rest)
    for fence in FENCE.findall(en_text):                     # блоки кода — тоже по-английски, кроме «…» и Н…
        rest += "\n" + re.sub("|".join([r"«[^»\n]*»", NORM_NO.pattern] + [x.pattern for x in allowed[4:]]), " ", fence)
    try:
        numbers_done = Path(en_path).resolve().relative_to(root).as_posix().startswith(NUMBERS_DONE)
    except ValueError:
        numbers_done = False
    if numbers_done:                                 # номер раздела источника — латиницей (ADR-0121 доп. (5) п. 1)
        for line in LINK.sub("]()", BUILT.sub(" ", en_text)).splitlines():
            if CYR_NUMBER.search(line):
                errors.append(f"a Cyrillic section number Н… in the source (N… since ADR-0121 addendum (5)): {line.strip()[:80]!r}")
    try:
        raw_labels = Path(en_path).resolve().relative_to(root).as_posix() in RAW_LABEL_FILES
    except ValueError:
        raw_labels = False
    if not legacy and not raw_labels:               # метка подстановки источника — английская, по словарю (ADR-0121 доп. (3) п. 4)
        for m in RU_LABEL.finditer(LINK.sub("]()", BUILT.sub(" ", en_text))):
            if CYR.search(re.sub(r"Н[0-9][0-9.]*[а-я]?|«[^»]*»|М1[0-2][A-Z]?(?:/[0-9]+)?", "", m.group(1))):
                errors.append(f"a Russian placeholder label in the source: <{m.group(1)}> — the English one of {PLACEHOLDERS}")
    if not marked:
        errors.append(f"the Russian text has no mark «{want}» in its head")
    for line in rest.splitlines():
        if CYR.search(line):
            errors.append(f"Cyrillic outside code, «…», Н-numbers and file names: "
                          f"{line.strip()[:80]!r}")
    return errors


def pairs(root):
    """English sources → (ru, en), в Platform/, VMS/ и в корне курса:
    - урок с `ru/` (ADR-0124): каждый `*.md` урока вне `ru/` и `journal/` — источник `X`, перевод — `ru/X`;
    - мелкий дом с `ru/` (корень курса, каталог модуля; ADR-0124 доп. (1) п. 4): каждый `ru/X.md` — перевод своего `X`;
    - урок без `ru/` (ADR-0121 п. 1): `<каталог>/en/<имя>.en.md` ↔ `<каталог>/<имя>.md` (нормы в `spec/en/`, у прочих
      каталогов — `en/` рядом); корневые НОРМАТИВНЫЕ-СЛОВА и КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ — `en/` в корне (ADR-0124 доп. (1)
      п. 4)."""
    root = Path(root)
    homes = sorted(h for h in [*root.glob("Platform/*"), *root.glob("VMS/*")] if (h / "ru").is_dir())
    out = []
    for home in homes:
        for x in sorted(home.rglob("*.md")):
            rel = x.relative_to(home)
            if rel.parts[0] not in ("ru", "journal") and not MACHINE_MD.search(rel.as_posix()):
                out.append((home / "ru" / rel, x))
    for home in [root, *(root / m for m in MODULES)]:
        if (home / "ru").is_dir():
            out.extend((ru, home / ru.name) for ru in sorted((home / "ru").glob("*.md")))
    for en in sorted([*root.glob("Platform/**/en/*.en.md"), *root.glob("VMS/**/en/*.en.md"), *root.glob("en/*.en.md")]):
        if not any(en.is_relative_to(h) for h in homes):
            out.append((en.parent.parent / en.name.replace(".en.md", ".md"), en))
    yield from sorted(out, key=lambda p: p[1])


def lesson_kinds(ru_path):
    """Refusal words of the lesson: the Н4 tables of its spec/*.norms.md (README приёмки и векторов своей Н4 не имеют)."""
    path = Path(ru_path).resolve()
    for parent in path.parents:
        spec = parent / "spec"
        if spec.is_dir() and any(spec.glob("*.norms.md")):
            words = set()
            for norms in spec.glob("*.norms.md"):
                words |= kinds_of(norms.read_text(encoding="utf-8"))
            return words
    return set()
