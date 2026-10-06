"""A subsystem's own numbers on `/metrics`, declared in its spec (the boundary's step 6, ГРАНИЦА-ПЛАТФОРМЫ-И-ПОДСИСТЕМЫ.md
§4: `metrics: [{name, count: table X}, {name, from: heartbeat.f, agg}]`). It was a function of the subsystem's the
console called (`metrics_extra`) — the platform printed lines it had never read. Now the spec says what each number
IS, in two shapes, and the console reads the store and the heartbeats it already reads:

    count: table <t>     rows of one of the spec's tables
        where: {f: v}       …whose field `f` is `v` (or one of a list)
        unheld: true        …that no live hold names (`<sub>/holds/<row>`: a place nobody takes)
        unless: {table, where}  …0 while the other table has such a row
    from: heartbeat.<path> | status.<path>
        path                a dot path into the heartbeat's `extra`, or into each `status` entry; a segment `<name>`
                            is every key of the map there, and the key is the label `name`
        agg                 value (the number; the default) | flag (1 or 0: said and not false, or `equals`) |
                            age (seconds since the unix time said) | label (1, the value as the label `label`) |
                            count (status: entries per worker by the value, the label named as the field; with
                            `equals`, ONE line — the entries that say it, over every worker: a subsystem's running
                            gauge, `console: {running: <its name>}`) |
                            sum, max (over every worker, by the wildcard labels) | histogram (`{buckets, count, sum}`
                            over the edges `buckets`)
        default             what is printed where nothing is said (else no line); for `label`, the label then
        values              `label` only: the closed set of words the field says (ADR-0063) — a word outside it is a
                            garbled field, counted (`FIELDS`), and no line; `default` is one of them
        labels              constant labels added to every line
        live                true: the workers this console saw change within `lost_after`, not every heartbeat
        when                status: only the entries that say this field
    name, type              `<sub>_<name>`, gauge (the default) | counter | histogram

A heartbeat's field is `worker`-labelled, a status entry's `unit`-labelled (its id). Every number through
`rows.number`: a word in one worker's field is that worker's, counted once, never the page's end (the review's
seventh pass, the metrics of a console). Declared, read at load (`parse`), and nothing a subsystem names is known here.
"""
from __future__ import annotations

import math
import re
from decimal import Decimal

from .rows import FIELDS, PARSE_ERRORS, finite, number

AGGS = ("value", "flag", "age", "label", "count", "sum", "max", "histogram")
TYPES = ("gauge", "counter", "histogram")
KEYS = {"name", "type", "labels", "count", "where", "unheld", "unless", "from", "agg", "default", "live", "when", "equals",
        "label", "buckets", "values"}
NAME = re.compile(r"[a-z][a-z0-9_]*")


def _label(value) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _word(x) -> str:
    """A value compared as a word: a bool as `true`/`false`, a number by its value (`value_text`, ADR 0055: `61` and
    `61.0` are one), anything else as it is."""
    if isinstance(x, bool):
        return str(x).lower()
    return value_text(x) if isinstance(x, (int, float)) else str(x)


def _values(v) -> tuple:
    return tuple(_word(x) for x in (v if isinstance(v, list) else [v]))


def _where(name: str, w, what: str) -> dict:
    if w is None:
        return {}
    if not isinstance(w, dict) or not all(isinstance(k, str) and k for k in w):
        raise ValueError(f"spec {name}: metrics {what}: `where` is {{<field>: <value or values>}}, not {w!r}")
    return {k: _values(v) for k, v in w.items()}


# `metrics:` as written, checked: a name, one of the two shapes, words from the lists above. Refused at load, like every
# declaration a console acts on.
def parse(name: str, raw, tables: tuple) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"spec {name}: `metrics:` is a list of {{name, count | from, …}}, not {raw!r}")
    out = []
    for m in raw:
        if not isinstance(m, dict) or not isinstance(m.get("name"), str) or not NAME.fullmatch(m["name"]) \
                or ("count" in m) == ("from" in m):
            raise ValueError(f"spec {name}: a metric is {{name: <a_name>, count: table <t> | from: heartbeat.<path> | "
                             f"status.<path>, …}}, not {m!r}")
        unknown = sorted(set(m) - KEYS)
        if unknown:
            raise ValueError(f"spec {name}: metric {m['name']}: {unknown[0]} is no key of a metric ({', '.join(sorted(KEYS))})")
        typ = str(m.get("type", "histogram" if m.get("agg") == "histogram" else "gauge"))
        if typ not in TYPES:
            raise ValueError(f"spec {name}: metric {m['name']}: type is one of {', '.join(TYPES)}, not {typ!r}")
        e = {"name": m["name"], "type": typ, "labels": {str(k): str(v) for k, v in (m.get("labels") or {}).items()}}
        if "count" in m:
            if "values" in m:                                  # a count is a number of rows: it says no words to close
                raise ValueError(f"spec {name}: metric {m['name']}: `values` closes the words of `agg: label`, not of a "
                                 f"count (ADR-0063)")
            words = str(m["count"]).split()
            if len(words) != 2 or words[0] != "table" or words[1] not in tables:
                raise ValueError(f"spec {name}: metric {m['name']}: count is `table <one of its tables>`, not {m['count']!r}")
            unless = m.get("unless")
            if unless is not None and (not isinstance(unless, dict) or unless.get("table") not in tables):
                raise ValueError(f"spec {name}: metric {m['name']}: unless is {{table: <one of its tables>, where}}, not {unless!r}")
            e.update(count=words[1], where=_where(name, m.get("where"), m["name"]), unheld=m.get("unheld") is True,
                     unless=({"table": unless["table"], "where": _where(name, unless.get("where"), m["name"])}
                             if unless else None))
        else:
            src, _, path = str(m["from"]).partition(".")
            agg = str(m.get("agg", "value"))
            if src not in ("heartbeat", "status") or not path or agg not in AGGS:
                raise ValueError(f"spec {name}: metric {m['name']}: from is heartbeat.<path> or status.<path>, agg one of "
                                 f"{', '.join(AGGS)} — not {m['from']!r}, {agg!r}")
            if agg == "count" and src != "status" or agg == "histogram" and not isinstance(m.get("buckets"), list):
                raise ValueError(f"spec {name}: metric {m['name']}: `count` counts status entries, a histogram names its "
                                 f"`buckets`")
            e.update(src=src, path=path.split("."), agg=agg, default=m.get("default"), live=m.get("live") is True,
                     when=str(m["when"]) if m.get("when") else "", equals=_values(m["equals"]) if "equals" in m else None,
                     label=str(m.get("label", "value")), buckets=[float(b) for b in m.get("buckets") or []],
                     values=_closed(name, m, agg))
        out.append(e)
    return out


# `values: [...]` of a label (ADR-0063): the closed set of words the field says, the same words on both sides. Without
# it a word outside the set (a writer's typo, a state one side added) was quietly a new series no alarm rule sees; with
# it, that word is a garbled field (`_one`). Refused at load (ADR 0012): `values` on any
# agg but `label`; not a list, empty, a word said twice, an item that is not a label word (`spec.LABEL_WORD`, the
# alphabet of a label: letters, digits and _ . : -, up to 64 — a bare `yes` YAML reads as true is no word: quote it);
# a `default` outside the set — what is printed where nothing is said is one of the words the spec promises.
def _closed(name: str, m: dict, agg: str) -> frozenset | None:
    if "values" not in m:
        return None
    from .spec import LABEL_WORD
    v, at = m["values"], f"spec {name}: metric {m['name']}"
    if agg != "label":
        raise ValueError(f"{at}: `values` closes the words of `agg: label`, not of agg {agg!r} (ADR-0063)")
    if not isinstance(v, list) or not v or not all(isinstance(x, str) and LABEL_WORD.fullmatch(x) for x in v):
        raise ValueError(f"{at}: values is a list of words (letters, digits and _ . : -, up to 64, starting with a "
                         f"letter or a digit), not {v!r} (ADR-0063)")
    twice = sorted({x for x in v if v.count(x) > 1})
    if twice:
        raise ValueError(f"{at}: values says {twice[0]!r} twice (ADR-0063)")
    if m.get("default") not in (None, "") and _word(m["default"]) not in v:
        raise ValueError(f"{at}: default {_word(m['default'])!r} is none of values ({', '.join(v)}) (ADR-0063)")
    return frozenset(v)


# Every value a path names in `d`: `[(labels from the wildcards, value)]` — a segment `<k>` walks every key of a map.
def _walk(d, path: list, labels: dict | None = None) -> list[tuple[dict, object]]:
    labels = labels or {}
    if not path:
        return [(labels, d)]
    head, rest = path[0], path[1:]
    if not isinstance(d, dict):
        return []
    if head.startswith("<") and head.endswith(">"):
        return [x for k, v in sorted(d.items()) for x in _walk(v, rest, {**labels, head[1:-1]: str(k)})]
    if head not in d:
        return [(labels, None)] if not rest else []          # the map is there and does not say it: said as nothing
    return _walk(d[head], rest, labels)


def _said(v, equals) -> bool:
    if equals is not None:
        return _word(v) in equals
    return v not in (None, "", 0, False) and str(v).lower() != "false"


def _lbl(labels: dict) -> str:
    return "{" + ",".join(f'{k}="{_label(v)}"' for k, v in labels.items()) + "}" if labels else ""


# The lines of one spec's metrics. `ctl`: the console's controller (its tables, holds, workers); `hbs`: every heartbeat
# of the subsystem as the console read them; `live`: those it saw change; `now`: its clock.
def lines(spec, ctl, hbs: dict, live: dict, now: float) -> list[str]:
    p, out, typed = spec.name, [], set()

    def typeline(m):
        if m["name"] not in typed:
            typed.add(m["name"])
            out.append(f"# TYPE {p}_{m['name']} {m['type']}")

    def say(m, labels: dict, value):
        out.append(f"{p}_{m['name']}{_lbl({**labels, **m['labels']})} {_word(value)}")   # `default` too: `metricText`

    for m in spec.metrics:
        typeline(m)
        if "count" in m:
            out.append(f"{p}_{m['name']}{_lbl(m['labels'])} {_count(m, ctl, live)}")
            continue
        workers = live if m["live"] else hbs
        key = lambda w, path: f"{p}/heartbeats/{w}#{path}"
        if m["src"] == "heartbeat":
            per = [(w, labels, v) for w, hb in sorted(workers.items()) for labels, v in _walk(hb.extra, m["path"])]
            if m["agg"] in ("sum", "max"):
                acc: dict[tuple, float] = {}
                for w, labels, v in per:
                    n = number(key(w, ".".join(m["path"])), v, float, 0.0)
                    k = tuple(labels.items())
                    acc[k] = (acc.get(k, 0.0) + n) if m["agg"] == "sum" else max(acc.get(k, 0.0), n)
                for k, n in sorted(acc.items()):
                    if m["agg"] == "max" and m["default"] is None and not n:
                        continue                            # a max nobody has: no line, as before
                    say(m, dict(k), round(n, 1) if m["agg"] == "max" else n)   # by value (ADR 0055)
                continue
            for w, labels, v in per:
                _one(m, say, {"worker": w, **labels}, v, now, key(w, ".".join(m["path"])))
            continue
        if m["agg"] == "count" and m["equals"] is not None:    # one line: the entries that say it, over every worker
            say(m, {}, sum(1 for hb in workers.values() for st in hb.status
                           if isinstance(st, dict) and "id" in st and (not m["when"] or m["when"] in st)
                           and _said(st.get(m["path"][0]), m["equals"])))
            continue
        for w, hb in sorted(workers.items()):                   # status: each entry that names its unit
            entries = [st for st in hb.status if isinstance(st, dict) and "id" in st and (not m["when"] or m["when"] in st)]
            if m["agg"] == "count":
                counts: dict[str, int] = {}
                for st in entries:
                    v = st.get(m["path"][0], "?")
                    counts[str(v)] = counts.get(str(v), 0) + 1
                for v, n in sorted(counts.items()):
                    say(m, {"worker": w, m["path"][0]: v}, n)
                continue
            for st in entries:
                for labels, v in _walk(st, m["path"]):
                    _one(m, say, {"unit": str(st["id"]), **labels}, v, now, key(w, f"{st['id']}.{'.'.join(m['path'])}"))
    return out


def text(ctl, lost_after: float = 45.0) -> str:
    """One spec's metrics alone, as the console's `/metrics` prints them — what a test or a probe reads."""
    from .console import heartbeats
    hbs, now = heartbeats(ctl.objects, ctl.spec.name + "/"), ctl.wall()
    live = {w: hb for w, hb in hbs.items()
            if ctl.eyes.fresh(ctl.sub.heartbeat_key(w), hb.token, lost_after, hb.ts, ctl.spec.name)}
    return "\n".join(lines(ctl.spec, ctl, hbs, live, now))


# A number in `/metrics` BY ITS VALUE, on both sides (ADR 0055): a whole value whole (`61`, an age of `10`), any other
# in the shortest text that reads back as it (`7.5`; an exponent where that is the shorter, `1e-07`, `1.2345675e+06`,
# `1e+21` — Prometheus reads it); one rule for a sample, a bucket's `le` and a value compared with `equals`. Prometheus
# holds a float64; how a heartbeat happened to spell it (`61` or `61.0`, which the product's reader cannot tell apart)
# does not leak into the line. The product's `sampleText` to the letter: digits for a whole value under 1e15, else Go's
# shortest `%g` (`strconv.FormatFloat(f, 'g', -1, 64)`: the exponent below 1e-4 and from 1e6 up).
def value_text(n) -> str:
    f = float(n)
    if math.isnan(f):
        return "NaN"
    if math.isinf(f):
        return "+Inf" if f > 0 else "-Inf"
    if f.is_integer() and abs(f) < 1e15:
        return str(int(f))
    d = Decimal(repr(f)).normalize()                           # repr: the shortest digits that read back as `f`
    e = d.adjusted()
    if -4 <= e < 6:
        return repr(f)
    sign, digits, _ = d.as_tuple()
    m = str(digits[0]) + ("." + "".join(map(str, digits[1:])) if len(digits) > 1 else "")
    return f"{'-' if sign else ''}{m}e{'+' if e >= 0 else '-'}{abs(e):02d}"


def _one(m, say, labels: dict, v, now: float, key: str) -> None:
    agg = m["agg"]
    if agg == "flag":
        say(m, labels, 1 if _said(v, m["equals"]) else 0)
    elif agg == "label":
        said = v if v not in (None, "") else m["default"]
        if said in (None, ""):
            return
        if m["values"] is not None:
            # A word outside the closed set is a garbled field (ADR-0063): no line, counted once a spell, like a word
            # where a number goes. Its own key: `servers.status` reads the same leaf as a string it may show, and one
            # reading must not undo the other's count; two metrics on one leaf may close it differently.
            vkey = f"{key}@{m['name']}"
            if _word(said) not in m["values"]:
                FIELDS.garbled(vkey, ValueError(f"{_word(said)!r} is none of values ({', '.join(sorted(m['values']))})"))
                return
            FIELDS.parsed(vkey)
        say(m, {**labels, m["label"]: _word(said)}, 1)          # the word as compared: `true`, `61` (`metricText`)
    elif agg == "age":
        t = number(key, v or None, float, None)
        if t is not None:
            say(m, labels, round(max(0.0, now - t), 1))
        elif m["default"] is not None:
            say(m, labels, m["default"])
    elif agg == "histogram":
        try:
            counts = [int(finite(b)) for b in v["buckets"]]
            count, total = int(finite(v["count"])), finite(v["sum"])
        except (*PARSE_ERRORS, KeyError):
            if v is not None:
                FIELDS.garbled(key, ValueError("not a histogram"))
            return
        FIELDS.parsed(key)                                     # half a histogram is a wrong one: all of it, or none
        name = m["name"]
        bucket = {**m, "name": f"{name}_bucket"}
        for le, n in zip(m["buckets"], counts):
            say(bucket, {**labels, "le": value_text(le)}, n)      # one rule for a sample, `le` and `equals` (ADR 0055)
        say(bucket, {**labels, "le": "+Inf"}, count)
        say({**m, "name": f"{name}_sum"}, labels, round(total, 3))
        say({**m, "name": f"{name}_count"}, labels, count)
        return
    else:
        n = number(key, v, float, None)
        if n is None and v is not None:
            n = 0                                              # a word where a number goes: read as not said, 0
        if n is None:
            n = m["default"]
        if n is not None:
            say(m, labels, n)


# A row of a table that says every `where` field's value (one of them; words compared as words). Read here and by the
# console's count of the places a worker of the subsystem would hold (`placement.places`).
def matches(it: dict, where: dict) -> bool:
    return all(str(it.get(k, "")).lower() in [x.lower() for x in vals] for k, vals in where.items())


def where_of(name: str, w, what: str) -> dict:
    return _where(name, w, what)


def _count(m, ctl, live: dict) -> int:
    rows = ctl.table_rows(m["count"])
    if m["unless"] is not None and any(matches(it, m["unless"]["where"]) for it in ctl.table_rows(m["unless"]["table"]).values()):
        return 0
    names = [n for n, it in rows.items() if matches(it, m["where"])]
    if m["unheld"]:
        held = ctl.live_holds()
        names = [n for n in names if n not in held]
    return len(names)
