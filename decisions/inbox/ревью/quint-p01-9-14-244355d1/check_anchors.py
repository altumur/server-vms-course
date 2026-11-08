#!/usr/bin/env python3
"""Сверка якорей отчёта и моделей по байтам среза 244355d1 (git show <pin>:<path>, строка N содержит подстроку)."""
import pathlib, subprocess, sys
PIN = "244355d161139bd6fe65fd68c7e5134598c21ba3"
HERE = pathlib.Path(__file__).resolve().parent
bad = n = 0
for row in (HERE / "anchors.tsv").read_text(encoding="utf8").splitlines()[1:]:
    path, line, sub = row.split("\t", 2)
    n += 1
    lines = subprocess.run(["git", "-C", str(HERE), "show", f"{PIN}:{path}"], capture_output=True, check=True).stdout.decode("utf8").split("\n")
    idx = int(line) - 1
    if sub in lines[idx]: continue
    # точное совпадение подстроки, допуск ±0
    bad += 1
    hit = [i + 1 for i, l in enumerate(lines) if sub in l][:3]
    print(f"BAD {path}:{line} no «{sub}» (нашлась в строках {hit})")
print(f"checked {n}, bad {bad}"); sys.exit(1 if bad else 0)
