"""Набор Б (ADR-0092 Confirmation, доп. (1)): таблица намеренных дельт — утверждает «Архитектор», ревью Kimi и Claude.

    python -m v7.setb          → out/setb/deltas.tsv, out/setb/canonical-new/*.json

Строка: id<TAB>old<TAB>new<TAB>basis<TAB>check<TAB>status. id:
- `corpus/<случай>` — вердикт загрузчика P/02.1 (вход — с `worker:` по п. 7, если его нет: столбец basis это называет);
- `classes/<случай>` — строка `classes.tsv` (класс сменился или строка снимается; `—` — строки нет, её добавить);
- `diagnostics/<случай>` — строка `diagnostics.tsv` (п. 5);
- `canonical/<строка cases.tsv>` — вектор P/02.2 (снят, новый — байты в `out/setb/canonical-new/`);
- `family-read/<семья>|<kind>|<режим>|<мутация>` — исход чтения семьи.
check — чем подтверждён новый исход (`стек В7`: Python и Go, наборы этого стенда).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from v7.seta import CORPUS, corpus_bytes, tsv  # noqa: E402

SETA = HERE / "out" / "seta"
STATUS = "утверждает «Архитектор» (ADR-0092 доп. (1)); ревью Kimi, Claude"

# п. 3: 11 отклонений Н1.1 от YAML 1.2.2 — принять YAML 1.2.2.
P3 = {
    "c5_key_long_1025_ok": "неявный ключ длиннее 1024 знаков (YAML 1.2.2 § 7.4.2)",
    "c5_unit_minus_word_ok": "`unit: -` — элемент списка, не слово",
    "c9_flow_lone_dash_spaced": "`[ - , a ]` — ошибка разбора YAML",
    "c5_key_question_mark": "`?x:` — простой ключ `?x`",
    "c5_value_question_mark": "значение `?x` — слово",
    "c5_value_next_line_flow": "значение потоком строкой ниже ключа",
    "c5_value_next_line_plain": "слово строкой ниже ключа",
    "c5_value_next_line_quoted": "строка в кавычках ниже ключа",
    "c7_seq_dash_scalar_below": "скаляр строкой ниже голого `-`",
    "c7_word_continuation_comment": "` # c` в строке продолжения — комментарий (значение короче)",
    "c8_word_hash_space": "`counter# c` — `#` часть слова",
}
# п. 4: TAB вне комментариев и `{k:}` — отказ нормой (правила тонкой проверки, тип text).
P4 = {"c3_tab_quoted_ok": "TAB в строке в кавычках", "c3_tab_block_ok": "TAB в блочном скаляре",
      "c4_block_tab_content_ok": "TAB в содержимом блочного скаляра", "c6_flow_map_empty_value": "`{k:}`",
      "c4_default_without_value": "`{… default: }` — ключ потока без значения: `{k:}`"}
P4_CANONICAL = {"corpus-c3_tab_block_ok": 51, "corpus-c3_tab_quoted_ok": 53, "corpus-c4_block_tab_content_ok": 54}
OTHER = {"c2_flow_seq_pair": "п. 2: `[a: 1]` — по YAML 1.2.2 отображение из одной пары, правила в перечне нет; отказ "
                             "держит форма (`snapshot[1]` — не строка)"}


def jl(name):
    p = SETA / name
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def basis(case, aug=False):
    w = "; п. 7: файл дополнен `worker:`" if aug else ""
    if case in P3:
        return "ADR-0092 п. 3 (принять YAML 1.2.2): " + P3[case] + w
    if case in P4:
        return "ADR-0092 п. 4: %s — отказ нормой%s" % (P4[case], w)
    if case.startswith("c5_int_"):
        return "ADR-0092 п. 8: целое по значению; приведение 4.0 → 4" + w
    if case in OTHER:
        return OTHER[case] + w
    return "ADR-0092 п. 6: класс — тип по слою" + w


def deltas():
    out = []
    man = {r["case"]: r for r in jl("manifest.jsonl")}
    classes = {c: k for c, k in tsv(CORPUS / "classes.tsv") if c != "case"}

    def show(r):
        return "ok" if r[0] == "ok" else "refused:%s" % r[1]

    for case, r in sorted(man.items()):
        aug = r.get("p7_worker", False)
        old = "ok" if r["ref"][0] == "ok" else "refused:%s" % classes.get(case, r["ref"][1])
        new = show(r["v7"])
        if not r["verdict_eq"]:
            out.append(("corpus/" + case, old, new, basis(case, aug), "стек В7"))
            if case in classes and new == "ok":
                out.append(("classes/" + case, classes[case], "строка снимается (случай принят)", basis(case, aug),
                            "стек В7"))
        elif r["v7"][0] != "ok" and r["v7"][1] != (classes.get(case) or r["ref"][1]):
            if case in classes:
                out.append(("classes/" + case, classes[case], r["v7"][1], basis(case, aug), "стек В7"))
            else:
                out.append(("classes/" + case, "— (строки нет; эталон: %s)" % r["ref"][1], r["v7"][1] + " — добавить",
                            basis(case, aug), "стек В7"))
    newdir = HERE / "out" / "setb" / "canonical-new"
    newdir.mkdir(parents=True, exist_ok=True)
    from v7 import project, seta
    m, _ = seta.v7_manifest()
    for case, r in sorted(man.items()):
        if r["ref"][0] != "ok" and r["v7"][0] == "ok":
            data, aug = corpus_bytes(case)
            (newdir / ("corpus-%s.json" % case)).write_bytes(project.canonical_bytes(m, data))
            out.append(("canonical/corpus-" + case, "нет вектора (отказ загрузчика)",
                        "новый вектор: out/setb/canonical-new/corpus-%s.json" % case,
                        basis(case, aug) + "; ADR-0087 доп. (7) правка «набор пополняется»", "стек В7"))
    for r in jl("canonical.jsonl"):
        if r["bytes_eq"]:
            continue
        case = r["case"][len("corpus-"):] if r["case"].startswith("corpus-") else r["case"]
        no = P4_CANONICAL.get(r["case"])
        old = "вектор" + (" (строка cases.tsv %d)" % no if no else "")
        new = "строки нет: вход отказан" if r["v7"] is None else "иные байты"
        why = basis(case) + ("; Confirmation «векторы canonical 51, 53, 54»" if no else "")
        out.append(("canonical/%s" % r["case"], old, new, why, "стек В7"))
    for case, paths, lines in tsv(CORPUS / "diagnostics.tsv"):
        if case == "case":
            continue
        out.append(("diagnostics/" + case, "пути %s, строки %s — строго" % (paths, lines), "подсказка, не норма",
                    "ADR-0092 п. 5 (вердикт и код выхода строги)", "—"))
    for r in jl("families.diff.jsonl"):
        old = "%s %s %s" % (r["ref"]["verdict"], r["ref"]["paths"], r["ref"]["outcomes"])
        new = "%s %s %s" % (r["v7"]["verdict"], r["v7"]["paths"], r["v7"]["outcomes"])
        if r["ref"]["verdict"] == "crash":
            why = "дефект эталона: писатель падает на 1e400 в JCS"
        elif r["ref"]["verdict"] == "ok":
            why = ("дефект эталона: %s принимает 1e400 (число вне binary64; codec.tsv json — без бесконечностей)"
                   % ("писатель" if r["mode"] == "writer" else "читатель"))
        else:
            why = "дефект эталона: 1e400 в тексте места encoding — отказ кодека места (codec.tsv), не значения внутри"
        if r["mode"] == "reader" and r["ref"]["outcomes"] != r["v7"]["outcomes"] and r["ref"]["verdict"] == "refused":
            why += "; исход чтения меняется: %s → %s" % (r["ref"]["outcomes"], r["v7"]["outcomes"])
        out.append(("family-read/%s|%s|%s|%s" % (r["family"], r["kind"], r["mode"], r["why"]), old, new, why,
                    "стек В7"))
    return out


def main():
    rows = deltas()
    d = HERE / "out" / "setb"
    head = "id\told\tnew\tbasis\tcheck\tstatus\n"
    (d / "deltas.tsv").write_text(head + "".join("\t".join(x + (STATUS,)) + "\n" for x in rows), encoding="utf-8")
    from collections import Counter
    print(len(rows), dict(Counter(x[0].split("/")[0] for x in rows)))


if __name__ == "__main__":
    main()
