#!/usr/bin/env python3
"""Генератор rolloutpoll_traces.qnt из канона Platform/02-installer/forms/rollout-poll.traces.tsv.

Запуск: python3 gen_traces.py <путь-к-traces.tsv> <выход.qnt>
Время в сотых секунды; значения t, ROLLOUT_WAIT и событий только из трасс.
Каждая трасса — один run (Quint), шаг трассы — один переход; expect — assert по состоянию.
"""
import json, sys, re

def qset(xs):
    return "Set(" + ", ".join('"%s"' % x for x in sorted(xs)) + ")"

def centi(t):
    # десятичная запись времени в сотые, без округления
    from decimal import Decimal
    return int(Decimal(t) * 100)

def ident(name):
    return "tr_" + re.sub(r"[^A-Za-z0-9_]", "_", name)

def reply(obj, inp):
    if obj is None:
        return '{ some: false, st: "Follower", lid: "", applied: 0, memOK: true }'
    mem = sorted(obj.get("voters", [])) == sorted(inp["voters"]) and obj.get("members", {}) == inp["members"]
    return '{ some: true, st: "%s", lid: "%s", applied: %d, memOK: %s }' % (
        obj["state"], obj.get("leader_id", ""), obj.get("applied", 0), "true" if mem else "false")

def did_rec(s):
    # did=/not=: «tick 0», «send_status 0», «read_commit 1 a,b,c», «read_expired 1»,
    # «wait_expired», «pass», «refuse 2 voters changed», «commit 1»
    parts = s.split(" ", 1)
    name = parts[0]
    rest = parts[1].strip() if len(parts) > 1 else ""
    k, n, who, word = -1, -1, [], ""
    if name in ("tick", "send_status"):
        k = int(rest)
    elif name == "read_commit":
        m = rest.split(" ", 1)
        n = int(m[0])
        who = [w for w in (m[1].split(",") if len(m) > 1 else []) if w]
    elif name in ("read_expired", "commit"):
        n = int(rest)
    elif name == "refuse":
        m = rest.split(" ", 1)
        n = int(m[0])
        word = m[1] if len(m) > 1 else ""
    elif name in ("wait_expired", "pass"):
        pass
    else:
        raise SystemExit("did: " + s)
    return 'recD("%s", %d, %d, %s, "%s")' % (name, k, n, qset(who), word.replace('"', '\\"'))

def asserts(expect):
    out = []
    for raw in expect.split(";"):
        e = raw.strip()
        if not e:
            continue
        key, _, val = e.partition("=")
        key = key.strip()
        val = val.strip()
        if key == "state":
            out.append('st.mst == "%s"' % val)
        elif key in ("alive", "need", "replied"):
            xs = [x for x in val.split(",") if x]
            out.append("st.%s == %s" % (key, qset(xs)))
        elif key.startswith("target."):
            v = key.split(".", 1)[1]
            if val == "-":
                out.append('not(st.target.exists(t => t.v == "%s"))' % v)
            else:
                out.append('st.target.exists(t => t.v == "%s" and t.c == %d)' % (v, int(val)))
        elif key == "reads":
            items = val.split()
            recs = []
            for it in items:
                n, _, who = it.partition(":")
                recs.append("{ n: %d, who: %s }" % (int(n), qset([w for w in who.split(",") if w])))
            out.append("st.reads == Set(%s)" % ", ".join(recs))
        elif key == "did":
            out.append("hasDid(st.did, %s)" % did_rec(val))
        elif key == "not":
            out.append("not(hasDid(st.did, %s))" % did_rec(val))
        else:
            raise SystemExit("expect key: " + e)
    return out

MUT = 0

def main():
    src, outp = sys.argv[1], sys.argv[2]
    global MUT
    MUT = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    rows = []
    for line in open(src, encoding="utf8"):
        if line.startswith("#") or not line.strip():
            continue
        rows.append(line.rstrip("\n").split("\t"))
    hdr = rows[0]
    rows = rows[1:]
    traces = {}
    order = []
    for r in rows:
        name, st, t, ev = r[0], r[1], r[2], r[3]
        exp = r[4] if len(r) > 4 else ""
        if name not in traces:
            traces[name] = []
            order.append(name)
        traces[name].append((int(st), t, ev, exp))
    runs = []
    for name in order:
        steps = traces[name]
        inp = None
        wait = 30000
        chain = []
        for st, t, ev, exp in steps:
            if ev.startswith("input"):
                inp = json.loads(ev.split(" ", 1)[1])
                inp.setdefault("allow_downtime", False)
                c = inp.get("const", {})
                if "ROLLOUT_WAIT" in c:
                    wait = int(c["ROLLOUT_WAIT"]) * 100
                allow = "true" if inp.get("allow_downtime") else "false"
                last = "true" if inp.get("last") else "false"
                ctx = ("%s, \"%s\", %s, %s" % (qset(inp["voters"]), inp["self"], last, allow))
                chain.append(("tinit(%s, %d)" % (qset(inp["voters"]), wait), exp))
                continue
            tc = centi(t)
            parts = ev.split(" ", 3)
            kind = parts[0]
            pre = "fireAll(st.with(\"did\", List()), %d, %s, %s)" % (tc, ctx, "true, %d" % MUT)
            if kind == "advance":
                chain.append(("tset(%s)" % pre, exp))
            elif kind == "self":
                k = int(parts[1])
                j = ev.split(" ", 2)[2]
                obj = None if j.strip() == "null" else json.loads(j)
                chain.append(("tset(onSelf(%s, %d, %s, %s, true, %d))" % (pre, k, reply(obj, inp), ctx.rsplit(",", 1)[0], MUT), exp))
            elif kind == "status":
                k = int(parts[1])
                v = parts[2]
                j = ev.split(" ", 3)[3]
                obj = None if j.strip() == "null" else json.loads(j)
                chain.append(("tset(onStatus(%s, %d, \"%s\", %s, %s, true, %d))" % (pre, k, v, reply(obj, inp), qset(inp["voters"]), MUT), exp))
            elif kind == "commit":
                n = int(parts[1])
                c = -1 if parts[2] == "null" else int(parts[2])
                chain.append(("tset(onCommit(%s, %d, %d, true, %d, %d))" % (pre, n, c, MUT, tc), exp))
            else:
                raise SystemExit("event: " + ev)
        body = []
        for act, exp in chain:
            asrt = asserts(exp)
            if asrt:
                body.append("%s.then(tcheck(%s))" % (act, " and ".join("(%s)" % a for a in asrt)))
            else:
                body.append(act)
        runs.append("  run %s = %s\n" % (ident(name), "\n    .then(".join(
            [body[0]] + [b + ")" for b in body[1:]])))
    head = """// -*- mode: Bluespec; -*-
// СГЕНЕРИРОВАНО gen_traces.py из Platform/02-installer/forms/rollout-poll.traces.tsv на срезе
// 244355d161139bd6fe65fd68c7e5134598c21ba3 (%d трасс, %d строк). Не править руками.
module rolloutpoll_traces {
  import rolloutpoll(SELF="a", VOTERS=Set("a","b","c"), LAST=false, ALLOW_DOWN=false, WAIT=30000, MAX_K=6, MUT=0, TRACK_DID=true).* from "./rolloutpoll"
  action tset(s: St): bool = all { st' = s, answered' = answered, commited' = commited }
  action tinit(v: Set[str], w: int): bool = all { st' = mkInit(v, w), answered' = Set(), commited' = Set() }
  action tcheck(c: bool): bool = all { assert(c), st' = st, answered' = answered, commited' = commited }
  pure def hasDid(ds: List[Did], rec: Did): bool = ds.select(d => d == rec).length() > 0
""" % (len(order), len(rows))
    tail = "}\n"
    open(outp, "w", encoding="utf8").write(head + "\n".join(runs) + tail)
    print("traces", len(order), "rows", len(rows))

if __name__ == "__main__":
    main()
