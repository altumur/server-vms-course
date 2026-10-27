"""Генератор В7 (ADR-0092 п. 12): диалект → JSON Schema 2020-12 + CEL + таблицы своих слоёв, детерминированно.

    python -m v7.build [--root КУРС] [--out КАТАЛОГ]      (из skills/lesson-spec/scripts)

Выход (по умолчанию scripts/v7/out/, не Platform/: нормой стандартные файлы станут только при переходе):
- `02.1-installer.schema.json`, `02.1-installer.layers.tsv` — форма манифеста P/02.1;
- `02.1-installer.relations.json` — среда CEL и строки `references.tsv` выражениями CEL;
- `families/<NN-процесс>/<семья>.schema.json`, `.layers.tsv` — схемы семей каталога (99 семей, файлы схем — по одному);
- `MANIFEST.tsv` — sha256 каждого файла выхода.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from form_source import families as fam  # noqa: E402
from form_source.source import load_form, load_references  # noqa: E402

from v7 import cel, schema  # noqa: E402

FORM = Path("Platform/02-installer/spec/02.1-installer.form.yaml")
REFS = Path("Platform/02-installer/spec/02.1-installer.references.tsv")


def manifest_schema(root):
    form = load_form(root / FORM)
    s = schema.Gen(form).schema("form of a subsystem manifest, P/02.1")
    return form, s


def relations(root, form):
    rows = load_references(root / REFS, form, REFS.name)
    done, bad = cel.translate(form, rows)
    env = dict(cel.ENV)
    env["functions"] = [
        {"name": "depth", "overloads": [{"id": "depth_dyn", "args": [{"type_name": "dyn"}],
                                         "return": {"type_name": "int"}}]},
        {"name": "template", "overloads": [{"id": "template_dyn_list_list_bool",
                                            "args": [{"type_name": "dyn"}, {"type_name": "list"},
                                                     {"type_name": "list"}, {"type_name": "bool"}],
                                            "return": {"type_name": "bool"}}]},
        {"name": "text", "overloads": [{"id": "text_list", "args": [{"type_name": "list"}],
                                        "return": {"type_name": "list"}}]},
    ]
    return {"env": env,
            "rows": [{"no": r.no, "path": r.path_text, "relation": r.text, "class": r.cls, "norm": r.norm,
                      "cel": e, "own": own} for r, e, own in done],
            "untranslated": [{"no": r.no, "relation": r.text, "why": why} for r, why in bad]}


def family_schema(form, kind):
    """Схема семьи; у строки (`row`) — `x-codec` у каждого поля items: типы диалекта по порядку (кодек, слой 3)."""
    s = schema.Gen(form, data=True).schema()
    if kind == "row":
        t, at = form.deref(form.root), s
        while "$ref" in at:                          # корень — ссылка: пометки у определения (оно своё у схемы)
            at = s["$defs"][at["$ref"].rsplit("/", 1)[1]]
        for k, c in (t.properties or {}).items():
            at["properties"][k]["x-codec"] = form.types_of(c)
        if t.names is not None:
            at["additionalProperties"]["x-codec"] = form.types_of(t.names[1])
    if kind == "file":
        s["x-file"] = True
    return s


def all_families(root):
    """[(строка каталога, схема семьи)] — семьи со схемой `data-form/1`, в порядке каталога."""
    common = fam.load_common(root / fam.COMMON)
    out = []
    for row in fam.read_catalog(root):
        if row.get("schema", "-") in ("-", "manifest"):
            continue
        f = fam.load_family(root, row, common)
        out.append((row, f, family_schema(f.form, row["kind"])))
    return out


def write(out, rel, text, sums):
    p = out / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    p.write_bytes(data)
    sums.append((rel, hashlib.sha256(data).hexdigest()))


def build(root, out):
    root, out = Path(root), Path(out)
    sums = []
    form, s = manifest_schema(root)
    write(out, "02.1-installer.schema.json", schema.dumps(s), sums)
    write(out, "02.1-installer.layers.tsv", schema.layer_table(s), sums)
    write(out, "02.1-installer.relations.json", json.dumps(relations(root, form), ensure_ascii=False, indent=1) + "\n",
          sums)
    seen = {}
    for row, f, fs in all_families(root):
        rel = "families/" + row["schema"].replace("/data/", "/").replace(".form.yaml", ".schema.json")
        text = schema.dumps(fs)
        if rel in seen:
            if seen[rel] != text:            # одна схема у нескольких семей — вид один (x-codec, x-file — по kind)
                rel = rel.replace(".schema.json", ".%s.schema.json" % row["kind"])
            else:
                continue
        seen[rel] = text
        write(out, rel, text, sums)
        write(out, rel.replace(".schema.json", ".layers.tsv"), schema.layer_table(fs), sums)
    write(out, "MANIFEST.tsv", "".join("%s\t%s\n" % x for x in sorted(sums)), [])
    return sums


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(HERE.parents[3]))
    ap.add_argument("--out", default=str(HERE / "out"))
    a = ap.parse_args(argv)
    sums = build(a.root, a.out)
    print("%d files → %s" % (len(sums), a.out))


if __name__ == "__main__":
    main()
