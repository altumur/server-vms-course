"""What the resource must leave past its days, declared (the boundary's step 6, ГРАНИЦА-ПЛАТФОРМЫ-И-ПОДСИСТЕМЫ.md §4:
`holds: {table, unit, since, until}`). It was a subsystem's function the resource called (`Resource.kept`, set by the
subsystem's builder of the resource): which buckets somebody said to keep, read in the subsystem's words. Now a spec says
that rows of one of its tables HOLD a unit's buckets for a stretch of time:

    holds:
      table: pins         the rows: `<sub>/<table>/*`
      unit: item          the field naming the unit held — an id of the subsystem the spec is `about` (or of itself), or
                          `<sub>/<id>` as it is (`SubsystemSpec.table_unit`'s rule)
      since: a            the fields bounding the stretch, unix seconds
      until: b
      longest: 604800     optional: a row holds at most this many seconds from its `since` — a stretch a person can mean,
                          not "everything there is" (the review's fourth pass, Т-B6)

and the resource holds a bucket of `(sub, unit)` whose time overlaps such a stretch when the unit IS the unit held, or is
ABOUT it (its spec's `about`, read from its row — a deleted row's too: a tombstone keeps its fields). The alarms' tree of
a unit is held as the unit is (`events.tree_owner`).

Not knowing is not "nothing is held" (the review's seventh and eighth passes):
    a hold row whose bounds do not parse    holds its unit from the bound that parses — or the start of time — to the
                                            other, or its end
    a unit (of a spec with `about`) whose   is held by every hold that reads: whose it is, nobody can say
    row does not parse, is not there, or
    says nobody in its about-field
    a store that does not answer            raises, and the resource's pass sweeps nothing (`Resource.retain`)
"""
from __future__ import annotations

import math

from .doors import parse_ref
from .events import tree_owner
from .rows import PARSE_ERRORS, Table, finite

HOLDS = Table("hold", "holds its unit as far as its stretch reads, until it is mended")
UNITS = Table("unit_row", "its unit is held by every hold that reads, as a unit of nobody's, until it is mended",
              "unit's row")


def parse(name: str, raw, fields_of_table=None, tables: tuple = ()) -> dict:
    """`holds:` as written, checked at load: a table of the spec and three field names; `longest` seconds."""
    if raw is None:
        return {}
    if not isinstance(raw, dict) or set(raw) - {"table", "unit", "since", "until", "longest"} \
            or raw.get("table") not in tables or not all(isinstance(raw.get(k), str) and raw[k] for k in ("unit", "since", "until")):
        raise ValueError(f"spec {name}: `holds:` is {{table: <one of its tables>, unit: <field>, since: <field>, "
                         f"until: <field>, longest?}}, not {raw!r}")
    longest = raw.get("longest")
    if longest is not None and (isinstance(longest, bool) or not isinstance(longest, (int, float)) or longest <= 0):
        raise ValueError(f"spec {name}: holds.longest is seconds, more than none — not {longest!r}")
    return {"table": raw["table"], "unit": raw["unit"], "since": raw["since"], "until": raw["until"],
            "longest": float(longest) if longest is not None else None}


class _Marked:
    """The store, each read a step of the pass's pulse (`Resource._progressed`)."""

    def __init__(self, vars_, progressed):
        self._vars, self._progressed = vars_, progressed

    def get(self, path, *a, **kw):
        out = self._vars.get(path, *a, **kw)
        self._progressed()
        return out

    def list(self, prefix, *a, **kw):
        out = self._vars.list(prefix, *a, **kw)
        self._progressed()
        return out


def _bound(items: dict, field: str, default: float) -> float:
    try:
        return finite(items[field]) if items.get(field) not in (None, "") else default
    except PARSE_ERRORS:
        return default


def kept(vars_, specs, progressed=None):
    """`(sub, unit, start, end) -> bool` for one pass: whether a bucket is held by a row of any loaded spec's `holds`."""
    store = vars_ if progressed is None else _Marked(vars_, progressed)
    by = {s.name: s for s in specs}
    spans: dict[str, list[tuple[float, float]]] = {}
    sound: list[tuple[float, float]] = []
    for spec in specs:
        h = spec.holds
        if not h:
            continue
        prefix = spec.sub.config(h["table"], "")
        for path in store.list(prefix):
            def read(path=path):
                items, _ = store.get(path)
                if items and not isinstance(items, dict):
                    raise TypeError(f"a row is a map, not {type(items).__name__}")
                return items
            items = HOLDS.read(path, read, None)
            if not items:
                continue
            v = items.get(h["unit"])
            ref = (str(v) if parse_ref(str(v)) is not None else spec._ref_in(spec.about_sub or spec.name, v)) \
                if v not in (None, "") else ""
            if not ref:
                continue
            a, b = _bound(items, h["since"], 0.0), _bound(items, h["until"], math.inf)
            whole = a == _bound(items, h["since"], -1.0) and b == _bound(items, h["until"], -1.0)
            if not whole:                                      # held as far as it reads — and counted, once a spell
                HOLDS.garbled(path, ValueError(f"{h['since']}/{h['until']} do not both read as unix seconds"))
            if not a < b and whole:
                continue                                       # both read, and the stretch is empty: it holds nothing
            if not a < b:
                a, b, whole = 0.0, math.inf, False             # the two that parse contradict each other: not known which
            if h["longest"] is not None and whole:
                b = min(b, a + h["longest"])
            spans.setdefault(ref, []).append((a, b))
            if whole:
                sound.append((a, b))
    if not spans:
        return lambda sub, unit, start, end: False
    abouts: dict[tuple[str, str], str | None] = {}

    def about(sub: str, unit: str) -> str | None:
        """The unit `(sub, unit)` is about — "" for none — or None: its row does not parse, nobody can say."""
        key = (sub, unit)
        if key not in abouts:
            spec = by.get(sub)
            if spec is None or not spec.about_sub:
                abouts[key] = ""
            else:
                path = spec.sub.config(spec.rows, unit)

                def read(path=path):
                    items, _ = store.get(path)
                    if items and not isinstance(items, dict):
                        raise TypeError(f"a row is a map, not {type(items).__name__}")
                    if items and not isinstance(items.get(spec.about_field, ""), (str, int, type(None))):
                        raise TypeError(f"`{spec.about_field}` is a value, not {type(items[spec.about_field]).__name__}")
                    return items
                got = UNITS.read(path, read, False)
                # a row that does not read, none at all, or one that names nobody: a unit of nobody's (None) — the
                # buckets are there and nobody can say whose they are
                abouts[key] = (spec.of_row(got) or None) if got else None
        return abouts[key]

    def held(sub: str, unit: str, start: float, end: float) -> bool:
        sub = tree_owner(sub)[0]
        overlap = lambda xs: any(a < end and start < b for a, b in xs)
        if overlap(spans.get(f"{sub}/{unit}", ())):
            return True
        of = about(sub, str(unit))
        if of is None:
            return overlap(sound)
        return bool(of) and overlap(spans.get(of, ()))
    return held
