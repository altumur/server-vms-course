"""Построить части главы 2.2 «Канонический вид» из источника формы главы 2.1 (ADR-0089; окно главы 2.2).

    python skills/lesson-spec/scripts/form_source/build_canonical.py section [Platform/02-installer/spec/02.2-installer.norms.md]
    python skills/lesson-spec/scripts/form_source/build_canonical.py schema [<файл .json>]
    python skills/lesson-spec/scripts/form_source/build_canonical.py vectors

Запуск — из корня раскладки (курс или выгрузка); --root <каталог> — иной корень.
section — раздел «Форма канонического вида»: в нормах между строками <!-- canonical:begin --> и <!-- canonical:end -->
          текст заменяется построенным; без нормы или без маркеров — раздел в stdout (нормы не меняются).
schema  — JSON Schema 2020-12 вида (форма 1): в stdout или в названный файл.
vectors — Platform/02-installer/vectors/canonical/: строки corpus-* (каждый ok случай корпуса 2.1) и course-* (каждая
          спека курса) в cases.tsv заново, строки автора — как были; expect/<case>.json всех строк — построенные байты;
          лишние ожидания удаляются. Повтор на тех же входах — те же байты.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from form_source import SourceError  # noqa: E402
from form_source.canonical import BEGIN, END, build_view_section, schema_text  # noqa: E402
from form_source.vectors import NORMS, generate, loader  # noqa: E402


def main(argv):
    root = Path(".")
    if len(argv) >= 2 and argv[0] == "--root":
        root, argv = Path(argv[1]), argv[2:]
    if not argv or argv[0] not in ("section", "schema", "vectors") or len(argv) > 2 or (argv[0] == "vectors" and len(argv) > 1):
        sys.exit(__doc__)
    try:
        if argv[0] == "vectors":
            print("wrote %d vectors into %s" % (generate(root), root / "Platform/02-installer/vectors/canonical"))
            return
        form = loader(root).form
        if argv[0] == "schema":
            text = schema_text(form)
            if len(argv) == 2:
                Path(argv[1]).write_text(text, encoding="utf-8")
                print("wrote the built schema into %s" % argv[1])
            else:
                sys.stdout.write(text)
            return
        section = build_view_section(form)
    except (SourceError, OSError) as exc:
        sys.exit("source error: %s" % exc)
    norms = Path(argv[1]) if len(argv) == 2 else root / NORMS
    lines = norms.read_text(encoding="utf-8").split("\n") if norms.exists() else []
    if lines.count(BEGIN) != 1 or lines.count(END) != 1:
        sys.stdout.write(section)
        return
    a, b = lines.index(BEGIN), lines.index(END)
    out = lines[:a + 1] + section.rstrip("\n").split("\n") + lines[b:]
    norms.write_text("\n".join(out), encoding="utf-8")
    print("wrote the built section into %s (%d lines)" % (norms, section.count("\n")))


if __name__ == "__main__":
    main(sys.argv[1:])
