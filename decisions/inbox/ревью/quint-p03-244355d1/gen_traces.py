#!/usr/bin/env python3
"""Переносит трассы форм Platform/03-worker/forms/*.traces.tsv в тесты Quint.

Запуск: python3 gen_traces.py <каталог forms>
Пишет traces_ok.qnt, traces_since_reset.qnt, traces_no_back.qnt, traces_persist_early.qnt.
"""
import json, re, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = sys.argv[1]


def qs(x):
    return json.dumps(str(x), ensure_ascii=False)


def qio(arr):
    # Элемент вида [name, [args]]: аргументы делятся на строки и числа в исходном порядке.
    out = []
    for name, args in arr:
        strs = [a for a in args if isinstance(a, str)]
        nums = [a for a in args if isinstance(a, (int, float)) and not isinstance(a, bool)]
        out.append("{ name: %s, strs: [%s], nums: [%s] }" % (
            qs(name), ", ".join(qs(s) for s in strs), ", ".join(str(int(n)) for n in nums)))
    return "[" + ", ".join(out) + "]"


CW_EVENTS = {"observe": "cwObserveA", "acquired": "cwAcq", "lost": "cwLo"}
TC_VARS = {"current_handle": "tc.curH", "revoked_word": "tc.revoked", "usable": "tc.usable"}
CW_VARS = {"since": "cw.since", "phase": "cw.phase", "episode_lost": "cw.lostEp"}


def event_call(machine, ev, payload):
    if machine == "cw":
        if ev == "observe":
            return "cwObserveA(%s, %s, %s, %d)" % (str(payload["withdrawn"]).lower(), str(payload["foreign"]).lower(),
                                                   str(payload["due"]).lower(), int(payload["wall"]))
        if ev == "acquired":
            return "cwAcq"
        if ev == "lost":
            return "cwLo"
    else:
        kind = ev
        op = str(payload.get("opened", False)).lower()
        return "tcE(%s, %s, %s, %s, %d)" % (qs(kind), op, qs(payload.get("handle", "")), qs(payload.get("jti", "")), int(payload.get("day", 0)))
    raise ValueError(ev)


def conds(machine, expect):
    res = []
    for part in [p.strip() for p in expect.split(";") if p.strip()]:
        key, _, val = part.partition("=")
        if key == "state":
            st = ("cw.st" if machine == "cw" else "tc.st")
            res.append("%s == %s" % (st, qs(val)))
        elif key == "io":
            res.append("io == %s" % qio(json.loads(val)))
        elif key.startswith("var."):
            name = key[4:]
            target = (CW_VARS if machine == "cw" else TC_VARS).get(name)
            if target is None:
                raise ValueError("unknown var " + name)
            res.append("%s == %s" % (target, json.dumps(json.loads(val), ensure_ascii=False)))
        else:
            raise ValueError("expect: " + part)
    return res


def load(machine, fname):
    traces = {}
    order = []
    with open(os.path.join(FORMS, fname), encoding="utf-8") as f:
        next(f)
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            tr, step, _t, event, expect = line.split("\t")
            if tr not in traces:
                traces[tr] = []
                order.append(tr)
            traces[tr].append((int(step), event, expect))
    return order, traces


def tname(machine, tr):
    return "t_" + machine + "_" + re.sub(r"[^a-z0-9_]", "_", tr.lower())


def build():
    blocks = []
    runs = []
    for machine, fname in (("cw", "contender-writer.traces.tsv"), ("tc", "token-cache.traces.tsv")):
        order, traces = load(machine, fname)
        for tr in order:
            rows = sorted(traces[tr], key=lambda r: r[0])
            acts = ["init"]
            for step, ev, expect in rows:
                if ev.startswith("input"):
                    pass
                elif ev == "advance":
                    acts.append("tick")
                else:
                    parts = ev.split(" ", 1)
                    payload = json.loads(parts[1]) if len(parts) > 1 else {}
                    acts.append(event_call(machine, parts[0], payload))
                cs = conds(machine, expect)
                if cs:
                    acts.append("check(" + " and ".join(cs) + ")")
                else:
                    acts.append("tick")
            body = acts[0] + "".join("\n    .then(%s)" % a for a in acts[1:])
            n = tname(machine, tr)
            runs.append(n)
            blocks.append("  run %s = %s" % (n, body))
    return blocks, runs


def write(fname, mut):
    blocks, runs = build()
    src = ("// Сформировано gen_traces.py из Platform/03-worker/forms/*.traces.tsv на срезе 244355d1. Не редактировать вручную.\n"
           "module %s {\n  import p03_forms(MUT_FORM=%s).* from \"./p03_forms\"\n\n"
           "  action check(c: bool): bool = all { assert(c), cw' = cw, tc' = tc, io' = io }\n\n" % (fname, json.dumps(mut)))
    src += "\n\n".join(blocks) + "\n}\n"
    with open(os.path.join(HERE, fname + ".qnt"), "w", encoding="utf-8") as f:
        f.write(src)
    return len(runs)


counts = {}
for name, mut in (("traces_ok", "none"), ("traces_since_reset", "since_reset"),
                  ("traces_no_back", "no_back_after_loss"), ("traces_persist_early", "persist_early")):
    counts[name] = write(name, mut)
print(counts)
