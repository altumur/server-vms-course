#!/usr/bin/env python3
"""Prints the tables of the report from results.tsv (counts and the table of runs)."""
import os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[1] if len(sys.argv) > 1 else HERE
rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(out, "results.tsv"))]
h, rows = rows[0], rows[1:]
R = [dict(zip(h, r)) for r in rows]
total = len(R)
match = sum(r["match"] == "yes" for r in R)
print(f"total={total} match={match} tools={dict(collections.Counter(r['tool'] for r in R))} kinds={dict(collections.Counter(r['kind'] for r in R))} actual={dict(collections.Counter(r['actual'] for r in R))} secs={sum(float(r['secs']) for r in R):.1f}")
print("mismatches:", [r["id"] for r in R if r["match"] != "yes"])
print("timeouts:", [r["id"] for r in R if r["actual"] == "timeout"])
print()
print("| id | экземпляр | инвариант | вид | инстр. | шаги | ожидание | факт | с |")
print("|---|---|---|---|---|---|---|---|---|")
for r in R:
    t = "apalache" if r["tool"] == "verify" else "rust"
    print(f"| {r['id']} | {r['module']} | {r['invariant']} | {r['kind']} | {t} | {r['max_steps']} | {r['expect']} | {r['actual']} | {r['secs']} |")
