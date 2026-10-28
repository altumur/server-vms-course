"""Вписать разделы, построенные из стандартных файлов В7, в нормы между маркерами (ADR-0087 п. 3; PLAN-TRANSITION п. 1.2).

    python -m v7.sections Platform/02-installer/spec/02.1-installer.norms.md [ещё нормы…]   (из skills/lesson-spec/scripts;
                                                                                  --root КОРЕНЬ — иной корень)

По маркерам норм: `<!-- form:begin -->` — «Форма» P/02.1 (`<база>.schema.json`, `.relations.json`, `.scalars.tsv`
рядом); `<!-- families:begin -->` — «Семьи данных» главы по каталогу; `<!-- canonical:begin -->` — «Форма
канонического вида» P/02.2 (`02.2-installer.view.schema.json` рядом). Текст между маркерами заменяется построенным.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from v7 import section, spec, textv7, view  # noqa: E402

MARKERS = {"form": (section.FORM_BEGIN, section.FORM_END), "families": (section.FAMILIES_BEGIN, section.FAMILIES_END),
           "canonical": (view.BEGIN, view.END)}


def chapter_prefix(norms):
    """`spec/02.3-installer.norms.md` → `P/02.3`; `spec/02-installer.norms.md` → `P/02`."""
    m = re.fullmatch(r"([0-9]{2})(?:\.(0|[1-9][0-9]?))?-[a-z][a-z-]*\.norms\.md", Path(norms).name)
    if not m:
        raise spec.SpecError("%s: not the norms of a Platform lesson or chapter" % norms)
    return "P/%s" % m.group(1) + (".%s" % m.group(2) if m.group(2) else "")


def chapter_families(root, prefix, catalog=None):
    catalog = spec.read_catalog(root) if catalog is None else catalog
    rows = [r for r in catalog if r.get("owner") == prefix and spec.is_v7_family(r)]
    return [spec.load_family(root, r) for r in rows]


def built(kind, norms, root):
    base = Path(norms).parent / Path(norms).name[:-len(".norms.md")]
    if kind == "form":
        sch = json.loads(Path(str(base) + ".schema.json").read_text(encoding="utf-8"))
        rel = json.loads(Path(str(base) + ".relations.json").read_text(encoding="utf-8"))
        return section.build_form_section(sch, rel, textv7.load_scalars(Path(str(base) + ".scalars.tsv")))
    if kind == "families":
        fams = chapter_families(root, chapter_prefix(norms))
        if not fams:
            raise spec.SpecError("%s: the chapter owns no family with a schema in the catalog" % Path(norms).name)
        return section.build_families_section(Path(norms).resolve(), Path(root).resolve(), fams)
    doc = json.loads((Path(norms).parent / "02.2-installer.view.schema.json").read_text(encoding="utf-8"))
    return view.build_view_section(doc)


def rewrite(norms, root):
    """Переписать в нормах каждый раздел с маркерами; → [вид раздела]."""
    lines = Path(norms).read_text(encoding="utf-8").split("\n")
    done = []
    for kind, (begin, end) in MARKERS.items():
        if lines.count(begin) != 1 or lines.count(end) != 1:
            continue
        text = built(kind, norms, root)
        a, b = lines.index(begin), lines.index(end)
        lines = lines[:a + 1] + text.rstrip("\n").split("\n") + lines[b:]
        done.append(kind)
    Path(norms).write_text("\n".join(lines), encoding="utf-8")
    return done


def main(argv):
    root = Path(__file__).resolve().parents[4]
    if len(argv) >= 2 and argv[0] == "--root":
        root, argv = Path(argv[1]), argv[2:]
    if not argv or any(not a.endswith(".norms.md") for a in argv):
        sys.exit(__doc__)
    for a in argv:
        try:
            done = rewrite(a, root)
        except (spec.SpecError, OSError, ValueError) as exc:
            sys.exit("source error: %s" % exc)
        print("%s: %s" % (a, ", ".join(done) or "no markers"))


if __name__ == "__main__":
    main(sys.argv[1:])
