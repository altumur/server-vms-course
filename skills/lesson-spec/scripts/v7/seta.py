"""Набор А (ADR-0092 Confirmation): стандартный стек со слоями против эталона диалекта на тех же входах.

    python -m v7.seta manifest [--go] [--out ФАЙЛ]     корпус P/02.1 (verdicts.tsv): вердикт и слой
    python -m v7.seta canonical [--out ФАЙЛ]           векторы canonical P/02.2: байты вида
    python -m v7.seta families [--go] [--out ФАЙЛ]     корпус семей (family_corpus.py): вердикт, пути, исход

Эталон — навык `form_source` на текущем коммите (judge.Loader, families.Judge + outcomes_for, canonical). Выход —
строки JSON на случай и сводка; расхождение — с классом (слой, дефект библиотеки, дефект эталона, дельта Б).
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from form_source.judge import Loader  # noqa: E402

from v7 import stack  # noqa: E402

ROOT = HERE.parents[3]
SPEC = ROOT / "Platform/02-installer/spec"
CORPUS = ROOT / "Platform/02-installer/acceptance/1"
OUT = HERE / "out"

# Класс эталона → слой В7 (ADR-0092 п. 6): форменные value/key/name/reference — form; связи — relations.
LAYER = {"text": "text", "name": "form", "key": "form", "value": "form", "reference": "form"}


def tsv(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").split("\n"):
        if line and not line.startswith("#"):
            rows.append(line.split("\t"))
    return rows


def reference_loader():
    return Loader(SPEC / "02.1-installer.form.yaml", SPEC / "02.1-installer.references.tsv",
                  SPEC / "02.1-installer.scalars.tsv")


def v7_manifest(go=None, text=None):
    sch = json.loads((OUT / "02.1-installer.schema.json").read_text(encoding="utf-8"))
    rel = json.loads((OUT / "02.1-installer.relations.json").read_text(encoding="utf-8"))
    return stack.Manifest(sch, rel, go.cel() if go else None, text), sch


def ref_layer(r):
    if r["verdict"] == "ok":
        return None
    return "relations" if r["layer"] == "relations" else LAYER[r["class"]]


TEXT = None                                      # слой 1: None — свой (v7.textv7); --text ref — textlayer эталона


def manifest(go=None):
    ref = reference_loader()
    m, sch = v7_manifest(go, TEXT if TEXT is not None or go is None else go.text)
    out = []
    for case, verdict in tsv(CORPUS / "verdicts.tsv"):
        if case == "case":
            continue
        data = (CORPUS / "cases" / (case + ".subsystem.yaml")).read_bytes()
        r = ref.judge(data)
        if go is not None:
            v = go.manifest(m, data)
        else:
            v = m.judge(data)
        rl = ref_layer(r)
        rrows = sorted({no for _, no in r.get("fired") or []})
        vpaths = v["paths"]
        if v["layer"] == "relations":            # эталон называет пути строк класса файла (value раньше reference)
            cls = m.cls
            vpaths = stack.canonical(p for no, p in v["fired"] if cls[no] == v["relations_class"])
        row = {"case": case, "expect": verdict, "ref": [r["verdict"], rl, r["paths"], rrows],
               "v7": [v["verdict"], v["layer"], vpaths, v.get("rows", [])]}
        row["verdict_eq"] = r["verdict"] == v["verdict"]
        row["layer_eq"] = rl == v["layer"]
        row["paths_eq"] = r["paths"] == vpaths
        row["rows_eq"] = rrows == v.get("rows", [])
        out.append(row)
    return out


def summary(rows, keys):
    s = {"cases": len(rows)}
    for k in keys:
        s[k] = sum(1 for r in rows if r[k])
    return s


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["manifest", "canonical", "families"])
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--text", choices=["v7", "ref"], default="v7")
    a = ap.parse_args(argv)
    global TEXT
    if a.text == "ref":
        from form_source.source import textlayer
        TEXT = textlayer
    go = None
    if a.go:
        from v7 import gorun
        go = gorun.Go()
    if a.what == "manifest":
        rows = manifest(go)
        keys = ["verdict_eq", "layer_eq", "paths_eq", "rows_eq"]
    elif a.what == "canonical":
        from v7 import project
        rows = project.seta()
        keys = ["bytes_eq"]
    else:
        from v7 import family_corpus
        rows = family_corpus.seta(go)
        keys = ["verdict_eq", "paths_eq", "outcome_eq"]
    tag = ("-go" if a.go else "") + ("-reftext" if a.text == "ref" else "")
    out = Path(a.out) if a.out else OUT / "seta" / ("%s%s.jsonl" % (a.what, tag))
    out.parent.mkdir(parents=True, exist_ok=True)
    if a.what == "families":                     # корпус — family-read.jsonl; здесь — только расхождения
        if not a.go:
            keep = ("family", "kind", "schema", "lesson", "mode", "text", "why", "ref")
            (OUT / "seta" / "family-read.jsonl").write_text(
                "".join(json.dumps({k: r[k] for k in keep}, ensure_ascii=False, sort_keys=True) + "\n"
                        for r in rows), encoding="utf-8")
        rows_out = [r for r in rows if not all(r[k] for k in keys)]
        out = out.with_suffix(".diff.jsonl")
    else:
        rows_out = rows
    out.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows_out),
                   encoding="utf-8")
    s = summary(rows, keys)
    (OUT / "seta" / ("%s%s.summary.json" % (a.what, tag))).write_text(json.dumps(s, ensure_ascii=False, sort_keys=True) + "\n",
                                                   encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))
    for r in rows:
        if not all(r[k] for k in keys[:1]):
            print("DIFF", json.dumps(r, ensure_ascii=False)[:400])


if __name__ == "__main__":
    main()
