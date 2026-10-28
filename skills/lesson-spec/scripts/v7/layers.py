"""Таблица слов слоёв `<имя>.layers.tsv` из схемы `<имя>.schema.json` (после перехода — источник схема, ADR-0092 п. 12).

    python -m v7.layers Platform/08-domain/data/book.schema.json [ещё схемы…]     (из skills/lesson-spec/scripts)

Пишет `.layers.tsv` рядом с каждой схемой: строка на каждую пометку `x-*` (место JSON Pointer, слой, слово, значение).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from v7 import schema  # noqa: E402


def main(argv):
    if not argv or any(not a.endswith(".schema.json") for a in argv):
        sys.exit(__doc__)
    for a in argv:
        p = Path(a)
        out = p.with_name(p.name[:-len(".schema.json")] + ".layers.tsv")
        out.write_text(schema.layer_table(json.loads(p.read_text(encoding="utf-8"))), encoding="utf-8")
        print("wrote %s" % out)


if __name__ == "__main__":
    main(sys.argv[1:])
