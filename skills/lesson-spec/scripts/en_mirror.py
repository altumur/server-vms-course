"""Сверка английского источника спецификации с производным русским текстом (ADR-0121 п. 3; ADR-0120 доп. (5) п. 7).

Английский `<каталог>/en/<имя>.en.md` — источник (нормы — в `spec/en/`); русский `<каталог>/<имя>.md` — производный,
с пометкой «производный от en, руками не правится». Сверяется по разделам `##` и `###`, по порядку: разделов столько же,
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
Блоки `families`, `form`, `canonical` (sections.py) английский несёт байт в байт (ADR-0121 доп. (1) п. 2).
"""
import os
import re
from pathlib import Path

MARK = "производный от en, руками не правится"
H2 = re.compile(r"^###? ", re.M)                   # разделы и подразделы: сверка по каждому
FENCE = re.compile(r"^```[^\n]*\n.*?^```[ \t]*$", re.M | re.S)
SPAN = re.compile(r"(`+)(.+?)\1", re.S)
NORM_NO = re.compile(r"(?<![\wА-Яа-яЁё])Н[0-9]+(?:\.[0-9]+)*[а-я]?(?!\w|\.[0-9])")
LESSON = re.compile(r"(?<![\w/])P/[0-9]{2}(?:\.[0-9]+)?(?:-[0-9]{2})?(?![0-9])")
ADR = re.compile(r"\bADR-[0-9]{4}\b")
FINDING = re.compile(r"(?<![\w-])[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-[0-9]{2}(?![\w-])")
CODE = re.compile(r"(?<![\w.])[1-5][0-9]{2}(?![\w.])")
LINK = re.compile(r"\]\(([^()\s]+)\)")
CHECK_ID = re.compile(r"^- \[[ xX]\] \*\*(P/[0-9.]+-[0-9]+)\*\*", re.M)
TABLE_ROW = re.compile(r"^\|.*\|[ \t]*$", re.M)
CYR = re.compile(r"[А-Яа-яЁё]")
ALLOWED_CYR = [SPAN, re.compile(r"«[^»\n]*»"), NORM_NO, LINK,
               re.compile(r"[\wА-Яа-яЁё.-]*[А-Яа-яЁё][\wА-Яа-яЁё.-]*\.(?:md|tsv|yaml|json)\b"),   # имена файлов
               re.compile(r"(?<![\w])М[0-9]+[A-Z]?(?:_[A-Za-z]+)?(?:/[0-9]+)?"),
               re.compile(r"(?<![\w])[А-ЯЁ][0-9]+(?![\w])"),
               re.compile(r"<[а-яё][а-яё_-]*>")]               # заполнители кода — те же, что в русском: <роль>, <форма>, <т>   # id находок ревью по-русски: А1, А10


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
        if not re.match(r"Н4(?:\s|$)", title):
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
    for target in LINK.findall(FENCE.sub("", body)):
        path = target.split("#", 1)[0]
        if not path or re.match(r"[a-z]+:", path):
            out.add(target)
            continue
        whole = os.path.normpath(base / path)
        try:
            rel = Path(whole).relative_to(root)
        except ValueError:
            rel = Path(whole)
        out.add(rel.as_posix() + ("#" + target.split("#", 1)[1] if "#" in target else ""))
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
TAGGED = re.compile(r"^```([A-Za-z]+)[^\n]*\n(.*?)^```[ \t]*$", re.M | re.S)
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


def strict(rb, eb):
    """ADR-0120 доп. (5) п. 7: values, orders and identifiers of code blocks, tables and prose agree."""
    out = []
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
                elif {m.group(2) for m in SPAN.finditer(xs)} - {m.group(2) for m in SPAN.finditer(ys)}:
                    out.append(f"{where}: code spans {sorted({m.group(2) for m in SPAN.finditer(xs)} - {m.group(2) for m in SPAN.finditer(ys)})} missing")
    rp = TABLE_ROW.sub("", LINK.sub("]()", FENCE.sub("", rb)))
    ep = TABLE_ROW.sub("", LINK.sub("]()", FENCE.sub("", eb)))
    missing = set(numbers(rp, "ru")) - set(numbers(ep, "en"))
    if missing:
        out.append(f"numbers of the Russian prose missing: {sorted(missing)}")
    return out


BUILT = re.compile(r"<!-- (families|form|canonical):begin -->.*?<!-- \1:end -->", re.S)


def compare(ru_text, en_text, ru_path, en_path, root):
    """→ list of messages (empty: the texts agree). Built blocks between `<!-- …:begin/end -->` (sections.py) are
    compared as they are: the English source carries the block byte for byte until sections.py has an English mode."""
    ru_blocks, en_blocks = BUILT.findall(ru_text), BUILT.findall(en_text)
    built_ru, built_en = [m.group(0) for m in BUILT.finditer(ru_text)], [m.group(0) for m in BUILT.finditer(en_text)]
    pre = []
    if built_ru != built_en:
        pre.append(f"built blocks differ: ru {ru_blocks}, en {en_blocks} (the English source carries them as built)")
    ru_text, en_text = BUILT.sub("<!-- built -->", ru_text), BUILT.sub("<!-- built -->", en_text)
    root, ru_path, en_path = Path(root).resolve(), Path(ru_path).resolve(), Path(en_path).resolve()
    errors_pre = pre
    kinds = kinds_of(ru_text) or lesson_kinds(ru_path)
    errors = list(errors_pre)
    ru_ids, en_ids = CHECK_ID.findall(ru_text), CHECK_ID.findall(en_text)
    if ru_ids != en_ids:
        errors.append(f"checklist ids differ: ru {ru_ids} / en {en_ids}")
    ru_s, en_s = sections(ru_text), sections(en_text)
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
        errors.extend(f"{where}: {m}" for m in strict(rb, eb))
        for key in rf:
            if key == "spans":
                missing = rf[key] - ef[key]
                if missing:
                    errors.append(f"{where}: code spans of the Russian text missing: {sorted(missing)}")
            elif rf[key] != ef[key]:
                if isinstance(rf[key], set):
                    errors.append(f"{where}: {key} differ: only ru {sorted(rf[key] - ef[key])}, "
                                  f"only en {sorted(ef[key] - rf[key])}")
                else:
                    errors.append(f"{where}: {key} differ: ru {rf[key]}, en {ef[key]}")
    rest = FENCE.sub(" ", en_text)
    for pattern in ALLOWED_CYR:
        rest = pattern.sub(" ", rest)
    for fence in FENCE.findall(en_text):                     # блоки кода — тоже по-английски, кроме «…» и Н…
        rest += "\n" + re.sub("|".join([r"«[^»\n]*»", NORM_NO.pattern] + [x.pattern for x in ALLOWED_CYR[4:]]), " ", fence)
    if MARK not in ru_text:
        errors.append(f"the Russian text has no mark «{MARK}» in its head")
    for line in rest.splitlines():
        if CYR.search(line):
            errors.append(f"Cyrillic outside code, «…», Н-numbers and file names: "
                          f"{line.strip()[:80]!r}")
    return errors


def pairs(root):
    """English sources → (ru, en): `<каталог>/en/<имя>.en.md` ↔ `<каталог>/<имя>.md` (ADR-0121 п. 1: нормы в `spec/en/`,
    у прочих каталогов — `en/` рядом), в Platform/ и VMS/."""
    root = Path(root)
    for en in sorted([*root.glob("Platform/**/en/*.en.md"), *root.glob("VMS/**/en/*.en.md")]):
        yield en.parent.parent / en.name.replace(".en.md", ".md"), en


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
