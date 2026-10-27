"""yaml-test-suite закреплённой версии против парсеров слоя 1 (ADR-0092 п. 2): черновик списка отклонений для «Спецификации».

    python -m v7.yts [--suite КАТАЛОГ] [--go]     → out/yts/deviations-<парсер>.tsv и сводка

Набор — yaml-test-suite `data-2022-01-17` (архив github.com/yaml/yaml-test-suite, тег data-2022-01-17, sha256
ccae49c1d010d27c20d315969a97752f95b14642fc1e73755db4eb2df4bb0256), распакован вне репозитория. Проверяется только
парсер (без тонкой проверки): ошибка там, где набор ждёт `error`; без ошибки — документы равны `in.json` (если он есть).
Отклонение — строка таблицы: id<TAB>expect<TAB>got<TAB>note. Тонкая проверка слоя 1 сверх YAML 1.2.2 отклонением парсера
не считается (она — норма Н1.1/п. 2–4).
"""
import argparse
import base64
import json
import math
import sys
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

SUITE = Path("/Users/murat/w2c/v7-stand/yts/yaml-test-suite-data-2022-01-17")


def tests(root):
    for d in sorted(p.parent for p in root.rglob("in.yaml")):
        yield d.relative_to(root).as_posix(), d


def json_stream(text):
    dec, i, out = json.JSONDecoder(), 0, []
    while True:
        while i < len(text) and text[i] in " \t\r\n":
            i += 1
        if i >= len(text):
            return out
        v, i = dec.raw_decode(text, i)
        out.append(v)


def same(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b or (isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def py_docs(data):
    """Разбор — события парсера (ошибка — только парсера); документы для in.json — конструктор safe (его отказ —
    не отклонение разбора: None вместо документов)."""
    from ruamel.yaml import YAML
    y = YAML(typ="safe", pure=True)
    y.version = (1, 2)
    try:
        list(y.parse(data.decode("utf-8")))
    except Exception as exc:                     # noqa: BLE001 — любая ошибка парсера — «ошибка»
        return None, "%s: %s" % (type(exc).__name__, str(exc).split("\n")[0])
    try:
        return [_plain(d) for d in YAML(typ="safe", pure=True).load_all(data.decode("utf-8"))], None
    except Exception:                            # noqa: BLE001
        return "construct", None


def _plain(v):
    if isinstance(v, dict):
        return {(k if isinstance(k, str) else "<nonstring:%s>" % (k,)): _plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return "<%s:%s>" % (type(v).__name__, v)


def go_docs(go, data):
    r = go.call({"op": "yaml_docs", "data": base64.b64encode(data).decode("ascii")})
    if "parse_error" in r:
        return None, r["parse_error"]
    return r["docs"], None


def layer1(text_mod, data):
    """Исход всего слоя 1 (парсер и тонкая проверка) на входе набора: ok или refused:<правило>."""
    try:
        text_mod.load_text_map(data)
        return "ok"
    except text_mod.TextRefused as exc:
        return "refused:%s" % exc.rule


def run(root, docs_fn, text_mod=None):
    rows, ok = [], 0
    for tid, d in tests(root):
        data = (d / "in.yaml").read_bytes()
        n0 = len(rows)
        want_err = (d / "error").exists()
        docs, err = docs_fn(data)
        if want_err:
            if err is None:
                rows.append((tid, "error", "parsed", "принято то, что набор отвергает"))
        elif err is not None:
            rows.append((tid, "ok", "error", err.replace("\n", " ")[:120]))
        elif docs == "construct":
            rows.append((tid, "json", "constructor refused", "разбор принят, конструктор safe отказал (не парсер)"))
        elif (d / "in.json").exists():
            want = json_stream((d / "in.json").read_text(encoding="utf-8"))
            if not same(docs, want):
                rows.append((tid, "json", "different", json.dumps(docs, ensure_ascii=False)[:120]))
        if len(rows) == n0:
            ok += 1
        elif text_mod is not None:
            r = rows[-1]
            rows[-1] = r[:3] + (layer1(text_mod, data), r[3])
    return ok, rows


def main(argv=None):
    warnings.simplefilter("ignore")             # ReusedAnchorWarning ruamel на входах с якорями
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default=str(SUITE))
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.suite)
    if a.go:
        from v7 import gorun
        go = gorun.Go()
        ok, rows = run(root, lambda data: go_docs(go, data), go.text)
        name = "go.yaml.in-yaml-v3.0.5"
    else:
        from v7 import textv7
        ok, rows = run(root, py_docs, textv7)
        name = "ruamel.yaml-0.19.1"
    out = HERE / "out" / "yts"
    out.mkdir(parents=True, exist_ok=True)
    head = ("# yaml-test-suite data-2022-01-17 × %s: отклонения парсера (черновик списка для «Спецификации», ADR-0092 "
            "п. 2). layer1 — исход всего слоя 1 (парсер и тонкая проверка): refused — отклонение закрыто слоем;\n# ok при expect=error — вход вне YAML 1.2.2 принят: дефект парсера, случай корпуса (п. 9).\nid\texpect\tgot\tlayer1\tnote\n" % name)
    (out / ("deviations-%s.tsv" % name)).write_text(head + "".join("\t".join(r) + "\n" for r in rows),
                                                   encoding="utf-8")
    print(json.dumps({"parser": name, "tests": ok + len(rows), "agree": ok, "deviations": len(rows)}))


if __name__ == "__main__":
    main()
