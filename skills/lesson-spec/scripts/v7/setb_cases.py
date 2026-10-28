"""Случаи набора Б (ADR-0092 пп. 11, 13; доп. (1)) — входами и прогоном: эталон диалекта, стек В7 на Python и на Go.

    python -m v7.setb_cases [--go]   → out/setb/cases.tsv, out/setb/cases/<id>.subsystem.yaml | <id>.json

Случай манифеста — байты файла; ожидание — вердикт и класс (пути — подсказка, п. 5). Случай семьи — семья, режим и текст
экземпляра; ожидание — вердикт, пути и исход `outcomes.tsv` (у семей путь — норма). Столбцы ref, py, go — исход каждого
стека; check — «да», если В7 на обоих языках дал ожидание. `dup` — случай уже есть в наборе А (тот же вход корпуса).
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from form_source import families as fam  # noqa: E402
from v7 import family_corpus as fc  # noqa: E402
from v7 import seta, stack  # noqa: E402

OUT = HERE / "out" / "setb"
W = "worker: {exec: /usr/lib/probe/worker}\n"
UNIT = "unit:\n  rows: things\n  id: numeric\n"
BASE = "name: probe\n" + UNIT + "placement: {capacity: {default: 1}}\n" + W


def fields(spec, unit_id="numeric", extra=""):
    """База с полями единицы: spec — строки `имя: {…}` (отступ добавляется)."""
    body = "".join("    %s\n" % x for x in spec)
    return ("name: probe\nunit:\n  rows: things\n  id: %s\n  fields:\n%s" % (unit_id, body) +
            "placement: {capacity: {default: 1}}\n" + W + extra)


def corpus(case):
    return (seta.CORPUS / "cases" / (case + ".subsystem.yaml")).read_bytes()


def nest(n):
    return "[" * n + "1" + "]" * n


# id, вход (str — текст, bytes — байты), ожидание «вердикт[:класс]», основание, источник, dup (случай набора А)
MANIFEST = [
    ("t01_flow_multiline", BASE + "snapshot: [name,\n  start]\n", "refused:text", "Н1.1:95 (поток на несколько строк); п. 2", "ревью Claude 1.2", ""),
    ("t02_quoted_multiline", BASE + 'display:\n  unit: "counter\n    x"\n', "refused:text", "Н1.1:95", "ревью Claude 1.2", ""),
    ("t03_indent_indicator", BASE + "display:\n  unit: |2\n     counter\n", "refused:text", "Н1.1:95 (`|2`)", "ревью Claude 1.2", ""),
    ("t04_complex_key", BASE + "? display\n: {unit: x}\n", "refused:text", "Н1.1:95 (`? …`)", "ревью Claude 1.2", ""),
    ("t05_doc_end", BASE + "...\n", "refused:text", "Н1.1:46; один документ — по байтам (п. 2; D17)", "ревью Claude 1.2", ""),
    ("t06_directive", "%YAML 1.2\n---\n" + BASE, "refused:text", "Н1.1:46", "ревью Claude 1.2", ""),
    ("t07_block_plain_ok", BASE + "display:\n  unit: |\n    counter\n", "ok", "контроль к t03 (строковое место display.unit; Б-5)", "ревью Claude 1.2, Б-5", ""),
    ("t08_tab_plain", BASE + "display:\n  unit: coun\tter\n", "refused:text", "п. 4", "ADR-0092 п. 4", ""),
    ("t09_tab_quoted", BASE + 'display:\n  unit: "coun\tter"\n', "refused:text", "п. 4 (TAB вне комментариев)", "ADR-0092 п. 4", ""),
    ("t10_tab_comment_ok", BASE + "# a\tb\n", "ok", "п. 4: в комментарии TAB допустим", "ADR-0092 п. 4", "c3_tab_in_comment_ok"),
    ("t11_flow_empty_value", BASE.replace("placement:", "lease: {unconfirmed_max:}\nplacement:"), "refused:text", "п. 4 (`{k:}`)", "ADR-0092 п. 4", "c6_flow_map_empty_value"),
    ("t12_two_documents", BASE + "---\nname: x\n", "refused:text", "один документ (п. 2)", "Н1.1", "yaml_two_documents"),
    ("t13_anchor", BASE + "display: &a {unit: x}\n", "refused:text", "п. 2: якорь", "Н1.1", ""),
    ("t14_alias", BASE + "display: {unit: *a}\n", "refused:text", "п. 2: псевдоним", "Н1.1", ""),
    ("t15_merge_key", BASE + "display: {<<: {unit: x}}\n", "refused:text", "п. 2: `<<`", "Н1.1", "anchor_merge_key"),
    ("t16_tag", BASE + "display: {unit: !!str counter}\n", "refused:text", "п. 2: тег", "Н1.1", ""),
    ("t17_dup_key", BASE + "name: other\n", "refused:text", "п. 2: повтор ключа", "Н1.1", "dup_top_key_name"),
    ("t18_key_collection", BASE + "[a, b]: 1\n", "refused:text", "п. 2: ключ-коллекция", "Н1.1", "c4_key_seq"),
    ("t19_depth_65", fields(["j: {type: json, default: %s}" % nest(61)]), "refused:text", "п. 2: глубина > 64", "Н1.1", "c2_depth_65"),
    ("t20_depth_64_ok", fields(["j: {type: json, default: %s}" % nest(60)]), "ok", "п. 2: глубина 64 допустима; место без связи depth", "решение по набору Б", "c2_depth_64"),
    ("t21_root_not_col1", "".join(" " + x + "\n" for x in BASE.rstrip("\n").split("\n")), "refused:text", "п. 2: корень с колонки 1", "ADR-0092 п. 2", "c4_root_indented"),
    ("t22_root_flow", "{name: probe, unit: {rows: things, id: numeric}, placement: {capacity: {default: 1}}, worker: {exec: /usr/lib/probe/worker}}\n", "refused:text", "п. 2", "ADR-0092 п. 2", "c4_root_flow"),
    ("t23_quoted_true_string", BASE + 'display: {unit: "true"}\n', "ok", "п. 2: скаляр по стилю узла (строковое место; Б-5)", "ADR-0092 п. 2, Б-5", ""),
    ("t24_plain_true_bool", BASE + "display: {unit: true}\n", "refused:form", "п. 2: `true` — bool", "ADR-0092 п. 2, Б-5", ""),
    ("t25_bom", b"\xef\xbb\xbf" + BASE.encode(), "refused:text", "п. 2: байты", "Н1.1", "bom_utf8"),
    ("t26_escape_U_overflow", BASE + 'display: {unit: "\\UFFFFFFFF"}\n', "refused:text", "п. 2; эталон падает (D9: OverflowError)", "генератор В7", ""),
    ("f01_int_4dot0_ok", BASE.replace(W, "worker: {exec: /usr/lib/probe/worker, stop_timeout: 20.0}\n"), "ok", "п. 8: целое по значению, приведение (вид — 20)", "ADR-0092 п. 8", ""),
    ("f02_int_1e1_ok", BASE.replace("default: 1}", "default: 1e1}"), "ok", "п. 8 (вид — 10)", "ADR-0092 п. 8", ""),
    ("f03_int_frac", BASE.replace("default: 1}", "default: 4.5}"), "refused:form", "п. 8: не целое", "ADR-0092 п. 8", ""),
    ("f04_int_below_min", fields(["n: {type: int, default: -9007199254740992}"]), "refused:form", "п. 8; Confirmation int_below_min", "ADR-0092 Confirmation", ""),
    ("f05_int_at_min_ok", fields(["n: {type: int, default: -9007199254740991}"]), "ok", "п. 8; Confirmation int_at_min_ok", "ADR-0092 Confirmation", ""),
    ("f06_int_at_max_ok", fields(["n: {type: int, default: 9007199254740991}"]), "ok", "п. 8", "ADR-0092 п. 8", ""),
    ("f07_int_above_max", fields(["n: {type: int, default: 9007199254740992}"]), "refused:form", "п. 8", "ADR-0092 п. 8", ""),
    ("f08_exec_trailing_nl", BASE.replace(W, 'worker: {exec: "/usr/lib/probe/worker\\n"}\n'), "refused:form", "слой 5 (полное совпадение)", "ревью Claude x5", ""),
    ("f09_prefix_trailing_nl", BASE + 'slot: {prefix: "w\\n"}\n', "refused:form", "слой 5", "ревью Claude x1", ""),
    ("f10_secret_name_newline", fields(['"a\\n_secret": {type: int}']), "refused:form", "точка — `[\\s\\S]` (п. 12)", "ревью Claude x2", ""),
    ("f11_blob_name_64_ok", fields(["%s: {type: blob}" % ("A" * 64)]), "ok", "дополнение name_not_pattern (п. 12)", "MANUAL regex.py", "profile_blob_64_ok"),
    ("f12_blob_name_65", fields(["%s: {type: blob}" % ("A" * 65)]), "refused:form", "дополнение name_not_pattern (п. 12)", "MANUAL regex.py", "profile_blob_65"),
    ("f13_secret_not_string", fields(["x_secret: {type: int}"]), "refused:form", "правило name_pattern", "Н1.3", ""),
    ("f14_secretx_bound_to", fields(["x_secretx: {type: string, bound_to: y}", "y: {type: string}"]), "refused:form", "name_not_pattern `.*_secret` — полное совпадение: `x_secretx` не секрет, bound_to запрещён (Б-2)", "MANUAL regex.py, Б-2", ""),
    ("f15_unknown_top_key", BASE + "zz: 1\n", "refused:form", "п. 6: класс — form", "Н1.2", ""),
    ("f16_one_of_two", corpus("c9_one_of_rule_order"), "refused:form", "DIALECT § 3 one_of; путь — подсказка (п. 5)", "корпус", "c9_one_of_rule_order"),
    ("f17_property_names_reference", corpus("m59_names_no_slash"), "refused:form", "п. 6 (было reference)", "корпус", "m59_names_no_slash"),
    ("r01_default_type_braces", fields(['x: {default: "a{x}"}']), "refused:relations", "связь через default (type = string по умолчанию формы)", "ревью Claude 3.3", ""),
    ("r02_default_url_id", fields(["name: {type: string}", 'x: {type: url, default: "{id}"}'], unit_id="name"), "refused:relations", "связь `type != string` — без `{id}` (Б-4: на url)", "references.tsv `unit.fields.$f.default`, Б-4", ""),
    ("r03_depth_32_ok", corpus("c8_ref12_unit_schema_depth_32_ok"), "ok", "своя функция depth (слой 7)", "корпус", "c8_ref12_unit_schema_depth_32_ok"),
    ("r04_depth_33", corpus("c8_ref12_unit_schema_depth_33"), "refused:relations", "depth", "корпус", "c8_ref12_unit_schema_depth_33"),
    ("r05_template_int_on_string", corpus("r37_requests_plain_number"), "refused:relations", "своя функция template", "корпус", "r37_requests_plain_number"),
    ("r06_text_bool_ok", fields(["f: {type: bool, enum: [true]}"], extra='display: {options: {f: {"true": "Yes"}}}\n'), "ok", "своя функция text: bool строчными (Б-3)", "ревью Claude Б-3", ""),
    ("r06b_text_bool_True", fields(["f: {type: bool, enum: [true]}"], extra='display: {options: {f: {"True": "Yes"}}}\n'), "refused:relations", "text: `True` не каноническая запись bool (Б-3)", "ревью Claude Б-3", ""),
    ("r07_split_unknown_table", BASE + 'metrics: [{name: m, count: "table nosuch"}]\n', "refused:relations", "split (расширение strings); Б-4", "references.tsv `metrics[].count`", ""),
    ("r08_unique_keys", corpus("m59_keys_id_repeat"), "refused:relations", "unique", "корпус", "m59_keys_id_repeat"),
    ("r09_prefix_free", corpus("c4_readers_nested"), "refused:relations", "prefix_free (D18)", "корпус", "c4_readers_nested"),
]

# Круг 2 ревью Б (Claude ef2f45c44, решение «Архитектора»): случаи правил без своего случая корпуса и обходов.
MANIFEST += [
    ("t27_escape_tab_ok", BASE + 'display: {unit: "a\\\tb"}\n', "ok",
     "`\\<TAB>` — экранирование YAML 1.2.2 и Н1.1, не литеральный TAB (п. 4); значение — TAB", "ревью Claude круг 2 Н-2", ""),
    ("t28_doc_start_content", "--- name: probe\n" + BASE[len("name: probe\n"):], "refused:text",
     "Н1.1 document: на строке `---` — только комментарий; отказывает парсер (правило doc-start-content снято)",
     "ревью Claude круг 2 Н-3", ""),
    ("t29_block_header_comment", BASE + "display:\n  unit: |# c\n    counter\n", "refused:text",
     "заголовок блочного скаляра без пробела перед `#` (D14: go.yaml.in/yaml/v3 принимает)", "ревью Claude круг 2 Н-3", ""),
    ("t30_block_leading", BASE + "display:\n  unit: >\n   \n    \n     \n # comment\n", "refused:text",
     "начальные пустые строки глубже первой строки блочного скаляра (D15: go.yaml.in/yaml/v3 принимает, S98Z)",
     "ревью Claude круг 2 Н-3", ""),
    ("t31_last_line_spaces_ok", BASE + "display:\n  unit: |\n    counter\n     ", "ok",
     "обход D16: LF в конец текста без LF; значение по YAML 1.2.2 `counter\\n \\n` (без обхода оба парсера — `counter\\n `)",
     "ревью Claude круг 2 Н-1, Н-3", ""),
    ("t32_trailing_spaces_ok", BASE + "  ", "ok", "строка пробелов в конце без LF — не отказ (правило last-spaces снято)",
     "ревью Claude круг 2 Н-1", ""),
    ("t33_flow_trailing_comma_ok", BASE + "heartbeat:\n  strings: [alpha, beta, ]\n", "ok",
     "YAML 1.2.2, решение «Архитектора» по ADR-0092 доп. (1) 2026-10-28: висячая запятая в потоке (`[a, b, ]` = `[a, b]`) — "
     "12-е снятое отклонение п. 3 (эталон: «empty flow item (trailing comma)»; yaml-test-suite UDR7)",
     "самопроверка SUT п. 3.4", ""),
    ("t33b_flow_map_trailing_comma_ok", BASE + "display: {unit: counter, }\n", "ok",
     "то же у потокового отображения (`{k: v, }` = `{k: v}`); пустой элемент в середине `[a,,b]` — отказ парсера "
     "YAML 1.2.2 (c4_flow_empty_item)", "самопроверка SUT п. 3.4", ""),
    ("t34_flow_leading_comma", BASE + "heartbeat:\n  strings: [, alpha]\n", "refused:text",
     "пустой элемент потока в начале (`[, a]`) — ошибка разбора YAML 1.2.2 (CTN5, 9MAG): отказ парсера обоих стеков; "
     "висячая запятая (t33) — не он", "ревью Claude Д (UDR7)", ""),
    ("t34b_flow_map_double_comma", BASE + "display: {unit: counter,, }\n", "refused:text",
     "две запятые в потоковом отображении (`{k: v,, }`) — ошибка разбора YAML 1.2.2: отказ парсера обоих стеков",
     "ревью Claude Д (UDR7)", ""),
]
# Значение дерева загрузчика (Python и Go) на пути — там, где случай проверяет и значение.
VALUES = {"t27_escape_tab_ok": (["display", "unit"], "a\tb"),
          "t31_last_line_spaces_ok": (["display", "unit"], "counter\n \n"),
          "t33_flow_trailing_comma_ok": (["heartbeat", "strings"], ["alpha", "beta"])}

P3_OK = ["c5_key_question_mark", "c5_value_question_mark", "c5_value_next_line_flow", "c5_value_next_line_plain",
         "c5_value_next_line_quoted", "c7_seq_dash_scalar_below", "c7_word_continuation_comment", "c8_word_hash_space"]
for c in P3_OK:
    MANIFEST.append(("p3_" + c, corpus(c).rstrip(b"\n") + b"\n" + W.encode(), "ok",
                     "п. 3 (YAML 1.2.2 читает) и п. 7 (дополнен `worker:`): отказа нет (Б-1, Kimi Н1)", "корпус " + c, ""))


def family_rows():
    """Случаи семей: вход — строка корпуса семей (family-read.jsonl) по семье и мутации; ожидание — исход эталона, кроме
    дефектов эталона (там — исход В7 с основанием)."""
    rows = [json.loads(x) for x in (HERE / "out/seta/family-read.jsonl").read_text("utf-8").splitlines()]

    cid = None

    def pick(pred, mode=None):
        for r in rows:
            if r["text"] is not None and pred(r) and (mode is None or r["mode"] == mode):
                return r
        raise KeyError("no corpus row for %s" % cid)

    W_, R_ = "writer", "reader"
    sel = [
        ("a01_null_root", lambda r: r["kind"] == "object" and r["why"] == "root null", None, "п. 13: корень null (20 семей-объектов, оба режима)"),
        ("a02_row_null", lambda r: r["kind"] == "row" and r["why"] == "root null", None, "п. 13"),
        ("a03_number_1e400", lambda r: r["family"] == "<sub>/controller/pass" and r["why"].endswith("seconds: number 1e400"), None, "дефект эталона: писатель и читатель принимают 1e400 (Б-7)"),
        ("a04_jcs_1e400_writer", lambda r: "encoded jcs '1e400'" in r["why"], W_, "дефект эталона: писатель jcs падает"),
        ("a05_trailing_nl_sub", lambda r: r["family"].endswith(".lock") and r["why"] == "sub: trailing \\n", None, "п. 13: хвостовой \\n в поле с pattern"),
        ("a06_names_given_bad", lambda r: r["family"] == "<sub>/controller/pass" and r["why"] == "names_given: name 'Bad Name!'", None, "п. 13: имя под propertyNames, исход по пути (Go — слой 4)"),
        ("a08_unique_items", lambda r: r["why"].endswith("duplicate item") and r["ref"]["verdict"] == "refused", None, "слой 4: путь — второе вхождение"),
        ("a09_max_bytes", lambda r: r["why"].endswith(": max_bytes") and r["ref"]["verdict"] == "refused", None, "слой 3: байты UTF-8"),
        ("a10_not_pattern", lambda r: r["why"].endswith("not_pattern match") and r["ref"]["verdict"] == "refused", None, "not: {pattern}"),
        ("a11_not_enum_dot", lambda r: r["why"].endswith("not_enum word") and r["ref"]["verdict"] == "refused", None, "not: {enum}"),
        ("a12_whole_reader", lambda r: r["why"].endswith("integer 1.0") and r["mode"] == R_ and r["ref"]["verdict"] == "refused", R_, "слой 3: целый знак у читателя (whole)"),
        ("a13_exact_reader", lambda r: r["why"].endswith("integer 100.00000000000000001") and r["ref"]["verdict"] == "refused", R_, "слой 3: точное десятичное значение"),
        ("a14_int_1dot0_reader_ok", lambda r: r["why"].endswith("integer 1.0") and r["ref"]["verdict"] == "ok", R_, "слой 3: целое по значению у читателя без whole"),
        ("a15_time_writer", lambda r: r["why"].endswith("time 1.0001"), None, "слой 3: запись времени писателя"),
        ("a16_time_number_1e0", lambda r: r["why"].endswith("time number 1e0"), None, "слой 3: время по записи"),
        ("a17_writer_max_names", lambda r: r["family"] == "platform/manifest/<sub>" and r["why"] == ": name 'zz_extra'", None, "$defs.writer: max_items имён — строка целиком (Б-6)"),
        ("a18_jcs_noncanonical", lambda r: "encoded jcs '{\"b\":1,\"a\":2}'" in r["why"], None, "слой 3: JCS только у писателя"),
        ("a19_outcome_unit_field", lambda r: r["family"] == "<sub>/heartbeats/<имя>" and r["why"] == "outcome /build: wrong type", R_, "DIALECT § 9: единица `поле`"),
        ("a20_doors_writer_name", lambda r: r["family"] == "platform/doors/<сервер>" and r["why"] == ": name 'zz_extra'", None, "$defs.writer: propertyNames писателя"),
    ]
    out = []
    # Выведенные из строки корпуса правкой текста: ключ "" книги (propertyNames с исключением ""), знаки вне ASCII в
    # выражении `\x{…}` common.named_id (п. 14: знак — самим знаком; вне BMP — U+1D7D0).
    book = pick(lambda r: r["schema"] == "08-domain/data/book.form.yaml" and r["why"] == "base", W_)
    units = pick(lambda r: r["family"] == "<sub>/workers/<имя>" and r["why"] == "base", W_)
    derived = [
        ("a07_book_empty_key_ok", book, lambda t: json.dumps(dict(json.loads(t), **{"": '{"missing":[]}'}),
                                                              ensure_ascii=False, separators=(",", ":")),
         "propertyNames с исключением \"\" (ловушка Gemini 4.2)"),
        ("a21_named_id_arabic_digit", units, lambda t: json.dumps(dict(json.loads(t), units="x\u0663"),
                                                                 ensure_ascii=False, separators=(",", ":")),
         "п. 14: `\\x{0660}-\\x{0669}` в common.named_id — цифра U+0663 отказана (Kimi Н4)"),
        ("a21b_named_id_astral_digit", units, lambda t: json.dumps(dict(json.loads(t), units="x\U0001D7D0"),
                                                                  ensure_ascii=False, separators=(",", ":")),
         "п. 14: знак вне BMP `\\x{1D7CE}-\\x{1D7FF}` — U+1D7D0 отказан (Kimi Н4)"),
        ("a21c_named_id_letter_ok", units, lambda t: json.dumps(dict(json.loads(t), units="x\u00e9"),
                                                               ensure_ascii=False, separators=(",", ":")),
         "п. 14: контроль — буква вне ASCII допустима"),
    ]
    refs = {}
    for cid0, base, f, basis in derived:
        for m in (W_, R_):
            r = dict(base, mode=m, text=f(base["text"]), why=cid0)
            key = (r["family"], r["kind"], r["schema"])
            if key not in refs:
                refs[key] = fc.Ref(fam.load_family(seta.ROOT, fc._catrow(r)))
            r["ref"] = refs[key].judge(r["text"], m)
            out.append(("%s.%s" % (cid0, m), r, basis))
    for cid, pred, mode, basis in sel:
        for m in ([mode] if mode else [W_, R_]):
            try:
                r = pick(pred, m)
            except KeyError:
                print("NO ROW", cid, m)
                continue
            out.append(("%s.%s" % (cid, m), r, basis))
    return out


def run_manifest(go):
    ref = seta.reference_loader()
    py, _ = seta.v7_manifest()
    gm = seta.v7_manifest(go, go.text)[0] if go else None

    def short(r, kind):
        if kind == "ref":
            return "ok" if r["verdict"] == "ok" else "refused:" + seta.ref_layer(r)
        return "ok" if r["verdict"] == "ok" else "refused:" + r["layer"]
    res = []
    for cid, data, expect, basis, source, dup in MANIFEST:
        data = data.encode("utf-8") if isinstance(data, str) else data
        try:
            rr = short(ref.judge(data), "ref")
        except Exception as exc:                 # noqa: BLE001 — падение эталона
            rr = "crash:%s" % type(exc).__name__
        pj = py.judge(data)
        pr = short(pj, "v7")
        gj = go.manifest(gm, data) if go else None
        gr = short(gj, "v7") if go else "—"
        ok = pr == expect and (gr == expect or not go)
        if cid in VALUES:
            path, want = VALUES[cid]
            for j in (pj, gj):
                if j is None:
                    continue
                got = j.get("tree")
                for k in path:
                    got = got.get(k) if isinstance(got, dict) else None
                ok = ok and got == want
            basis = basis + "; значение %s = %r проверено" % (".".join(path), want)
        res.append((cid, "corpus", data, expect, basis, source, dup, rr, pr, gr, ok))
    return res


def run_families(go):
    res = []
    out_dir = HERE / "out"
    for cid, r, basis in family_rows():
        rel = "families/" + r["schema"].replace("/data/", "/").replace(".form.yaml", ".schema.json")
        p = out_dir / rel
        alt = out_dir / rel.replace(".schema.json", ".%s.schema.json" % r["kind"])
        p = alt if alt.exists() else p
        sch = json.loads(p.read_text("utf-8"))
        fobj = fam.load_family(seta.ROOT, fc._catrow(r))
        ref = r["ref"]

        def outcome(v):
            if r["mode"] != "reader":
                return []
            return [o.path for o in fam.outcomes_for(fobj.outcomes, v["paths"])]
        pv = fc.v7_judge(sch, r["kind"], r["text"], r["mode"])
        py = {"verdict": pv["verdict"], "paths": pv["paths"], "outcomes": outcome(pv)}
        if go:
            gv = fc.v7_judge(sch, r["kind"], r["text"], r["mode"], go, p)
            gr = {"verdict": gv["verdict"], "paths": gv["paths"], "outcomes": outcome(gv)}
        else:
            gr = None
        defect = "дефект эталона" in basis
        expect = py if defect else ref
        ok = py == expect and (gr is None or gr == expect)
        res.append((cid, "family-read", r, expect, basis, ref, py, gr, ok))
    return res


def fmt(v):
    return "%s %s %s" % (v["verdict"], json.dumps(v["paths"], ensure_ascii=False), json.dumps(v["outcomes"], ensure_ascii=False))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args(argv)
    go = None
    if a.go:
        from v7 import gorun
        go = gorun.Go()
    (OUT / "cases").mkdir(parents=True, exist_ok=True)
    lines = ["# Набор Б, случаи (ADR-0092 пп. 11, 13; утверждает «Архитектор», ревью Kimi и Claude — доп. (1)). Входы —",
             "# out/setb/cases/<id>.subsystem.yaml (манифест) и <id>.json (семья: family, kind, schema, mode, text). Ожидание",
             "# манифеста — вердикт и класс (пути — подсказка, п. 5); семьи — вердикт, пути, исход. ref/py/go — исходы стеков;",
             "# check — В7 на обоих языках дал ожидание; dup — тот же вход уже в наборе А. Строит v7/setb_cases.py.",
             "id\twhere\texpect\tref\tpy\tgo\tcheck\tdup\tbasis\tsource"]
    bad = 0
    for cid, where, data, expect, basis, source, dup, rr, pr, gr, ok in run_manifest(go):
        (OUT / "cases" / (cid + ".subsystem.yaml")).write_bytes(data)
        lines.append("\t".join([cid, where, expect, rr, pr, gr, "да" if ok else "НЕТ", dup, basis, source]))
        bad += not ok
    for cid, where, r, expect, basis, ref, py, gr, ok in run_families(go):
        (OUT / "cases" / (cid + ".json")).write_text(json.dumps(
            {k: r[k] for k in ("family", "kind", "schema", "mode", "text")}, ensure_ascii=False, indent=1) + "\n", "utf-8")
        lines.append("\t".join([cid, "%s|%s|%s" % (where, r["family"], r["mode"]), fmt(expect), fmt(ref), fmt(py),
                                fmt(gr) if gr else "—", "да" if ok else "НЕТ", r["why"], basis, "family-read.jsonl"]))
        bad += not ok
    (OUT / "cases.tsv").write_text("\n".join(lines) + "\n", "utf-8")
    print("cases", len(lines) - 5, "not as expected", bad)


if __name__ == "__main__":
    main()
