#!/usr/bin/env python3
"""Сверка: для каждого прогона из results.tsv sha256 текста модели (с подстановками) равен записанному в файле прогона."""
import csv, hashlib, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import run
HERE = pathlib.Path(__file__).resolve().parent
bad = 0
byid = {run.runid(r): r for r in run.RS}
rows = list(csv.DictReader(open(HERE / "results.tsv", encoding="utf8"), delimiter="\t"))
for row in rows:
    r = byid.get(row["id"])
    if r is None:
        bad += 1; print("нет в таблице запусков:", row["id"]); continue
    want = hashlib.sha256(run.patched_source(r).encode()).hexdigest()
    head = (HERE / row["file"]).read_text(encoding="utf8").split("\n", 4)
    got = next(l for l in head if l.startswith("# sha256"))
    if want not in got:
        bad += 1; print("sha не совпал:", row["id"])
print(f"проверено {len(rows)}, расхождений {bad}, отклонений от ожиданий {sum(1 for x in rows if x['match'] != 'ok')}")
sys.exit(1 if bad else 0)
