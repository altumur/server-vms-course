"""Набор Б (ADR-0092 Confirmation): черновик таблицы намеренных дельт — НА УТВЕРЖДЕНИЕ ЧЕЛОВЕКОМ (п. 11).

    python -m v7.setb          → out/setb/deltas.tsv (из out/seta/*.jsonl и перечней пп. 3–6 ниже)

Строка: id<TAB>old<TAB>new<TAB>basis<TAB>check<TAB>status. id — `corpus/<случай>` (P/02.1), `classes/<случай>`,
`diagnostics/<случай>`, `canonical/<строка cases.tsv>`, `family-read/<семья>|<kind>|<режим>|<мутация>`. check — чем
подтверждён новый исход: `стек В7` (наборы этого стенда), `слой 1` (тонкая проверка YAML — вне поручения генератора,
исход ожидаемый по ответу решения). status — всегда «на утверждение человеком».
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from v7.seta import CORPUS, ROOT, tsv  # noqa: E402

SETA = HERE / "out" / "seta"
STATUS = "на утверждение человеком"

# п. 3: 11 отклонений Н1.1 от YAML 1.2.2 (замер YAML записки, таблица (в)) — принять YAML 1.2.2.
P3_REFUSED = {   # норма принимала, парсер YAML 1.2.2 отказывает
    "c5_key_long_1025_ok": "неявный ключ длиннее 1024 знаков (YAML 1.2.2 § 7.4.2)",
    "c5_unit_minus_word_ok": "`unit: -` — элемент списка, не слово",
    "c9_flow_lone_dash_spaced": "`[ - , a ]` — ошибка разбора YAML",
}
P3_PARSED = {    # норма отказывала text, YAML 1.2.2 читает; вердикт держит посторонний отказ (нет `worker`)
    "c5_key_question_mark": "`?x:` — простой ключ `?x`",
    "c5_value_question_mark": "значение `?x` — слово",
    "c5_value_next_line_flow": "значение потоком строкой ниже ключа",
    "c5_value_next_line_plain": "слово строкой ниже ключа",
    "c5_value_next_line_quoted": "строка в кавычках ниже ключа",
    "c7_seq_dash_scalar_below": "скаляр строкой ниже голого `-`",
    "c7_word_continuation_comment": "` # c` в строке продолжения — комментарий",
    "c8_word_hash_space": "`counter# c` — `#` часть слова",
}
# п. 4: TAB вне комментариев и `{k:}` — отказ нормой (правила тонкой проверки, тип text).
P4 = {"c3_tab_quoted_ok": "TAB в строке в кавычках", "c3_tab_block_ok": "TAB в блочном скаляре",
      "c4_block_tab_content_ok": "TAB в содержимом блочного скаляра", "c6_flow_map_empty_value": "`{k:}`"}
P4_CANONICAL = {"corpus-c3_tab_block_ok": 51, "corpus-c3_tab_quoted_ok": 53, "corpus-c4_block_tab_content_ok": 54}


def jl(name):
    p = SETA / name
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def deltas():
    out = []
    man = {r["case"]: r for r in jl("manifest.jsonl")}
    classes = {c: k for c, k in tsv(CORPUS / "classes.tsv") if c != "case"}

    def old_of(case):
        r = man[case]["ref"]
        return "ok" if r[0] == "ok" else "refused:%s" % classes.get(case, r[1])

    # п. 8 — «4.0 в месте целого» отменено
    for case, r in sorted(man.items()):
        if not r["verdict_eq"]:
            out.append(("corpus/" + case, old_of(case), "ok", "ADR-0092 п. 8: целое по значению; приведение 4.0 → 4",
                        "стек В7"))
            out.append(("canonical/corpus-" + case, "нет вектора (отказ загрузчика)",
                        "новый вектор: принятый вход, целое приведено", "ADR-0092 п. 8; ADR-0087 доп. (7) правка «набор "
                        "пополняется c5_int_*»", "стек В7"))
    for case, why in sorted(P3_REFUSED.items()):
        out.append(("corpus/" + case, old_of(case), "refused:text", "ADR-0092 п. 3 (принять YAML 1.2.2): " + why,
                    "слой 1"))
    for case, why in sorted(P3_PARSED.items()):
        out.append(("corpus/" + case, old_of(case), "refused:form",
                    "ADR-0092 п. 3: YAML 1.2.2 читает (%s); отказ держит посторонний отказ формы" % why, "слой 1"))
    for case, why in sorted(P4.items()):
        out.append(("corpus/" + case, old_of(case), "refused:text", "ADR-0092 п. 4: %s — отказ нормой" % why, "слой 1"))
    for case, no in sorted(P4_CANONICAL.items()):
        out.append(("canonical/%s" % case, "вектор (строка cases.tsv %d)" % no, "строки нет: вход отказан (п. 4)",
                    "ADR-0092 п. 4; Confirmation «векторы canonical 51, 53, 54»", "слой 1"))
    # п. 6 — класс отказа по слою
    for case, cls in sorted(classes.items()):
        if case in P3_REFUSED or case in P3_PARSED or case in P4 or case not in man:
            continue
        r = man[case]
        new = "text" if cls == "text" else ("relations" if r["ref"][1] == "relations" else "form")
        if new != cls:
            out.append(("classes/" + case, cls, new, "ADR-0092 п. 6: класс — тип по слою", "стек В7"))
    # п. 5 — пути и строки отказа загрузчика манифеста — подсказка
    for case, paths, lines in tsv(CORPUS / "diagnostics.tsv"):
        if case == "case":
            continue
        out.append(("diagnostics/" + case, "пути %s, строки %s — строго" % (paths, lines), "подсказка, не норма",
                    "ADR-0092 п. 5 (вердикт и код выхода строги)", "—"))
    # дефекты эталона семей
    for r in jl("families.diff.jsonl"):
        old = "%s %s %s" % (r["ref"]["verdict"], r["ref"]["paths"], r["ref"]["outcomes"])
        new = "%s %s %s" % (r["v7"]["verdict"], r["v7"]["paths"], r["v7"]["outcomes"])
        why = r["why"]
        basis = ("дефект эталона: писатель падает на 1e400 в JCS" if r["ref"]["verdict"] == "crash" else
                 "дефект эталона: читатель принимает 1e400 (число вне binary64; codec.tsv json — без бесконечностей)"
                 if r["ref"]["verdict"] == "ok" else
                 "дефект эталона: 1e400 в тексте места encoding — отказ кодека места (codec.tsv), не значения внутри")
        out.append(("family-read/%s|%s|%s|%s" % (r["family"], r["kind"], r["mode"], why), old, new, basis, "стек В7"))
    return out


def main():
    rows = deltas()
    d = HERE / "out" / "setb"
    d.mkdir(parents=True, exist_ok=True)
    head = "id\told\tnew\tbasis\tcheck\tstatus\n"
    (d / "deltas.tsv").write_text(head + "".join("\t".join(x + (STATUS,)) + "\n" for x in rows), encoding="utf-8")
    from collections import Counter
    print(len(rows), dict(Counter(x[0].split("/")[0] for x in rows)))


if __name__ == "__main__":
    main()
