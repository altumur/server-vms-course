"""Правила тонкой проверки слоя 1 (ADR-0092 п. 2) и их охват — на решение «Архитектору»; отказы слоя 1 на корректном
YAML 1.2.2 (yaml-test-suite) — отдельный раздел Б.

    python -m v7.thin_rules   → out/setb/thin-rules.tsv, out/setb/yts-refusals.tsv

thin-rules.tsv: rule<TAB>check<TAB>where<TAB>basis<TAB>corpus<TAB>yts. where — откуда правило: «п. 2» (перечень решения),
«п. 4», «Н1.1:95», «Н1.1:46», «Н1.1» (норма есть, в перечне п. 2 нет), «дефект парсера» (yaml-test-suite: правило держит
YAML 1.2.2 там, где парсер отступает). corpus — случаи корпуса P/02.1 (вход с `worker:` по п. 7), где слой 1 отказал этим
правилом первым; yts — тесты yaml-test-suite (и с `error`), где парсер (ruamel) разобрал вход, а слой 1 отказал этим
правилом. Обходы без отказа: D13 (`\\/` в Go), D16 (LF в конец текста без LF) — правилами не считаются.
"""
import re
import sys
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from v7 import seta, textv7, yts  # noqa: E402

# (id, образец сообщения отказа, проверка, откуда, основание)
RULES = [
    ("bytes-utf8", r"not UTF-8", "текст — UTF-8", "п. 2", "байты"),
    ("bytes-bom", r"^BOM$", "без BOM первым знаком", "п. 2", "байты; Н1.1 encoding"),
    ("value-char", r"in a value", "те же знаки в значении после экранирования (`\\x07`, `\\u2028`, суррогаты)",
     "Н1.1", "Н1.1 escape: «знак результата подчиняется encoding»"),
    ("bytes-char", r"^character U\+", "без C0 (кроме TAB, LF, CR), DEL, C1, U+FFFE/FFFF, U+2028/2029", "п. 2",
     "байты; Н1.1 encoding"),
    ("lone-cr", r"lone CR", "одиночный CR — отказ, CRLF → LF", "Н1.1", "Н1.1 encoding"),
    ("tab", r"TAB", "TAB только в комментарии", "п. 4", "ADR-0092 п. 4"),
    ("doc-end", r"`\.\.\.`", "`...` — отказ", "Н1.1:46", "Н1.1 document; yaml.v3 не сообщает (D17)"),
    ("directive", r"directive", "директива `%` — отказ", "Н1.1:46", "Н1.1 document"),
    ("doc-second", r"second document", "`---` только первым, до содержимого", "п. 2", "один документ — по байтам"),
    ("doc-start-content", r"content on the `---` line", "на строке `---` — только комментарий", "Н1.1",
     "Н1.1 document"),
    ("doc-start-col", r"not at column 1", "`---` с колонки 1", "Н1.1", "Н1.1 document"),
    ("root", r"root is a block mapping|empty file", "корень — блочное отображение с колонки 1; не пустой файл",
     "п. 2", "ADR-0092 п. 2"),
    ("anchor-alias-tag-merge", r"anchor|alias|tag|merge key", "якорь, псевдоним, тег, `<<` — отказ", "п. 2",
     "ADR-0092 п. 2"),
    ("key-collection", r"a key is a collection", "ключ-коллекция — отказ", "п. 2", "ADR-0092 п. 2"),
    ("key-nonstring", r"a plain key read as", "простой ключ, который таблица скаляров читает не строкой — отказ", "Н1.1",
     "Н1.1 keys (не в перечне п. 2; ревью Claude Б-8)"),
    ("duplicate", r"said twice", "повтор ключа — отказ", "п. 2", "ADR-0092 п. 2"),
    ("depth", r"deeper than 64", "глубина > 64 — отказ", "п. 2", "ADR-0092 п. 2"),
    ("rare-95", r"Н1\.1:95", "поток и строка в кавычках на несколько строк, `|2`, `? …`", "Н1.1:95", "ADR-0092 п. 2"),
    ("flow-empty", r"\{k:\}", "`{k:}` — ключ потока без значения", "п. 4", "ADR-0092 п. 4; D10"),
    ("escape", r"escape", "в двойных кавычках — только экранирования YAML 1.2.2", "дефект парсера",
     "HRE5 (yaml.v3 принимает `\\'`, D12); Н1.1 escape — список уже"),
    ("comment-tight", r"comment without a space", "`#` вплотную после кавычки, `]`, `}` — отказ", "дефект парсера",
     "SU5Z (D11); Н1.1 comment: «`]# c`, `\"a\"# c` — не комментарий» — есть в Н1.1"),
    ("block-header", r"block scalar header", "после `|`/`>` и указателя — пробел или конец строки",
     "дефект парсера", "X4QW (yaml.v3, D14)"),
    ("block-leading", r"leading empty line", "начальные пустые строки блочного скаляра не глубже первой строки",
     "дефект парсера", "S98Z (yaml.v3, D15)"),
    ("parser", r".", "ошибка парсера YAML", "парсер", "YAML 1.2.2 (ruamel.yaml 0.19.1 / go.yaml.in/yaml/v3 v3.0.5)"),
]


def rule_of(exc):
    if exc.rule == "parser":
        return "parser"
    for rid, pat, *_ in RULES:
        if rid == "parser":
            continue
        if re.search(pat, exc.msg):
            return rid
    return "parser"


def main():
    warnings.simplefilter("ignore")
    hits = {r[0]: [] for r in RULES}
    for case, _ in seta.tsv(seta.CORPUS / "verdicts.tsv"):
        if case == "case":
            continue
        data, _aug = seta.corpus_bytes(case)
        try:
            textv7.load_text_map(data)
        except textv7.TextRefused as exc:
            hits[rule_of(exc)].append(case)
    bhits = {r[0]: [] for r in RULES}
    mods = [("", textv7)]
    import os
    from v7 import gorun
    if os.path.exists(gorun.BIN):
        mods.append(("go:", gorun.Go().text))      # у Go правила D14, D15 решают сами (ruamel отказывает и без них)
    for f in sorted((HERE / "out" / "setb" / "cases").glob("*.subsystem.yaml")):
        seen = set()
        for tag, mod in mods:
            try:
                mod.load_text_map(f.read_bytes())
            except mod.TextRefused as exc:
                rid = rule_of(exc)
                if rid not in seen:
                    bhits[rid].append(tag + f.name.split(".")[0])
                    seen.add(rid)
    yhits = {r[0]: [] for r in RULES}
    refusals = []
    from ruamel.yaml import YAML
    for tid, d in yts.tests(yts.SUITE):
        data = (d / "in.yaml").read_bytes()
        try:
            textv7.load_text_map(data)
            continue
        except textv7.TextRefused as exc:
            rid = rule_of(exc)
        try:
            list(YAML(typ="safe", pure=True).parse(data.decode("utf-8")))
            parsed = True
        except Exception:                        # noqa: BLE001
            parsed = False
        if parsed:
            yhits[rid].append(tid)
        if not (d / "error").exists():
            refusals.append((tid, (d / "===").read_text("utf-8").strip(), rid, "парсер разобрал" if parsed else
                             "парсер отказал"))
    out = HERE / "out" / "setb"
    lines = ["# Правила тонкой проверки слоя 1 — на решение «Архитектору» (поручение по ревью набора Б, п. 5).",
             "# corpus — случаи P/02.1 (с `worker:` по п. 7), где правило отказало первым; yts — тесты yaml-test-suite",
             "# data-2022-01-17 (и тесты с `error`), где ruamel разобрал вход, а правило отказало. Обходы без отказа — D13",
             "# (`\\/` у Go), D16 (LF в конец текста без LF) — не правила.",
             "# setb — случаи набора Б (out/setb/cases), где правило отказало первым (Python; `go:` — только у Go).",
             "rule\tcheck\twhere\tbasis\tcorpus\tsetb\tyts"]
    for rid, _pat, check, where, basis in RULES:
        lines.append("\t".join([rid, check, where, basis, "%d: %s" % (len(hits[rid]), " ".join(hits[rid])),
                                "%d: %s" % (len(bhits[rid]), " ".join(bhits[rid])),
                                "%d: %s" % (len(yhits[rid]), " ".join(yhits[rid]))]))
    (out / "thin-rules.tsv").write_text("\n".join(lines) + "\n", "utf-8")
    head = ["# Набор Б, раздел «слой 1 сужает YAML 1.2.2»: тесты yaml-test-suite data-2022-01-17 без `error` (корректный",
            "# YAML 1.2.2), которые слой 1 (Python; Go — те же исходы, v7/yts.py) отказывает. rule — правило отказа;",
            "# parser — разобрал ли вход парсер (если нет — сужение от парсера, не от правила). Сужение у Go то же, что у Python:",
            "# расхождения парсеров закрыты обходами (3UYS — D13).",
            "id\ttitle\trule\tparser"]
    (out / "yts-refusals.tsv").write_text("\n".join(head + ["\t".join(r) for r in refusals]) + "\n", "utf-8")
    from collections import Counter
    print("corpus", {k: len(v) for k, v in hits.items() if v})
    print("yts", {k: len(v) for k, v in yhits.items() if v}, "refusals of valid YAML", len(refusals),
          Counter(r[3] for r in refusals))


if __name__ == "__main__":
    main()
