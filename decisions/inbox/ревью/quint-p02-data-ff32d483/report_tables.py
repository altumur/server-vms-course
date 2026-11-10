#!/usr/bin/env python3
"""Prints the tables of the report from results.tsv and the ITF of the cost runs."""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[1] if len(sys.argv) > 1 else HERE
rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(out, "results.tsv"))]
h, rows = rows[0], rows[1:]
R = [dict(zip(h, r)) for r in rows]

def main():
    total = len(R)
    match = sum(r["match"] == "yes" for r in R)
    tools = collections.Counter(r["tool"] for r in R)
    kinds = collections.Counter(r["kind"] for r in R)
    actual = collections.Counter(r["actual"] for r in R)
    secs = sum(float(r["secs"]) for r in R)
    print(f"total={total} match={match} tools={dict(tools)} kinds={dict(kinds)} actual={dict(actual)} secs={secs:.1f}")
    print("mismatches:", [r["id"] for r in R if r["match"] != "yes"])
    print("timeouts:", [r["id"] for r in R if r["actual"] == "timeout"])
    print()
    print("| id | модуль | инвариант | вид | инстр. | шаги | ожидание | факт | с |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in R:
        t = "apalache" if r["tool"] == "verify" else "rust"
        print(f"| {r['id']} | {r['module']} | {r['invariant']} | {r['kind']} | {t} | {r['max_steps']} | {r['expect']} | {r['actual']} | {r['secs']} |")
    print()
    # cost table
    def dec(x):
        if isinstance(x, dict):
            if "#bigint" in x: return int(x["#bigint"])
            if "#map" in x: return {dec(a): dec(b) for a, b in x["#map"]}
            if "#set" in x: return [dec(a) for a in x["#set"]]
        return x
    print("| прогон | S | P | W | C | чтений | записей (в т.ч. CAS с конфликтом) | удалений | сравн. пар S^2 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in R:
        if not r["id"].startswith("K"): continue
        p = dict(kv.split("=") for kv in r["overrides"].replace(" ", "").split(","))
        itf = os.path.join(out, "runs", r["id"] + ".itf.json")
        if not os.path.exists(itf): continue
        st = json.load(open(itf))["states"][-1]
        g = lambda n: next(dec(v) for k, v in st.items() if k.endswith("::" + n))
        print(f"| {r['id']} | {p['S']} | {p['P']} | {p['W']} | {p['C']} | {g('reads')} | {g('writes')} | {g('deletes')} | {g('cmp')} |")

main()
