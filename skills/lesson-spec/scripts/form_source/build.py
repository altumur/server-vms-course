"""Вписать построенный раздел формы в нормы главы между маркерами (ADR-0087 п. 3).

    python skills/lesson-spec/scripts/form_source/build.py Platform/02-installer/spec/02.1-installer.norms.md

Источник — рядом с нормами: <глава>.form.yaml, .references.tsv, .scalars.tsv. В нормах маркеры BEGIN и END стоят
отдельными строками; текст между ними заменяется построенным. Без маркеров — раздел печатается в stdout.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from form_source import SourceError, build_section  # noqa: E402
from form_source.section import BEGIN, END  # noqa: E402


def main():
    if len(sys.argv) != 2 or not sys.argv[1].endswith(".norms.md"):
        sys.exit(__doc__)
    norms = Path(sys.argv[1])
    base = norms.parent / norms.name[:-len(".norms.md")]
    try:
        section = build_section(Path(str(base) + ".form.yaml"), Path(str(base) + ".references.tsv"),
                                Path(str(base) + ".scalars.tsv"))
    except SourceError as exc:
        sys.exit("source error: %s" % exc)
    lines = norms.read_text(encoding="utf-8").split("\n") if norms.exists() else []
    if lines.count(BEGIN) != 1 or lines.count(END) != 1:
        sys.stdout.write(section)
        return
    a, b = lines.index(BEGIN), lines.index(END)
    out = lines[:a + 1] + section.rstrip("\n").split("\n") + lines[b:]
    norms.write_text("\n".join(out), encoding="utf-8")
    print("wrote the built section into %s (%d lines)" % (norms, section.count("\n")))


if __name__ == "__main__":
    main()
