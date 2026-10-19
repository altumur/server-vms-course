"""Вписать построенный раздел «Семьи данных» в нормы главы-владельца между маркерами (ADR-0088 п. 7).

    python skills/lesson-spec/scripts/form_source/build_families.py Platform/02-installer/spec/02.3-installer.norms.md

Семьи — строки каталога Platform/common/data/catalog.tsv с owner этой главы (P/NN.K) и колонкой schema; схема
NN-<процесс>/data/<семья>.form.yaml и исходы <семья>.outcomes.tsv рядом. В нормах маркеры
<!-- families:begin --> и <!-- families:end --> стоят отдельными строками; текст между ними заменяется построенным.
Без маркеров — раздел печатается в stdout (нормы не меняются).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from form_source import SourceError  # noqa: E402
from form_source.families import BEGIN, END, build_for_norms  # noqa: E402


def main():
    if len(sys.argv) != 2 or not sys.argv[1].endswith(".norms.md"):
        sys.exit(__doc__)
    norms = Path(sys.argv[1])
    try:
        section = build_for_norms(norms)
    except (SourceError, OSError) as exc:
        sys.exit("source error: %s" % exc)
    lines = norms.read_text(encoding="utf-8").split("\n")
    if lines.count(BEGIN) != 1 or lines.count(END) != 1:
        sys.stdout.write(section)
        return
    a, b = lines.index(BEGIN), lines.index(END)
    out = lines[:a + 1] + section.rstrip("\n").split("\n") + lines[b:]
    norms.write_text("\n".join(out), encoding="utf-8")
    print("wrote the built section into %s (%d lines)" % (norms, section.count("\n")))


if __name__ == "__main__":
    main()
