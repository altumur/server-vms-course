"""A subsystem's tables, declared in its spec and served by the platform's console (the boundary's step 6, ГРАНИЦА-
ПЛАТФОРМЫ-И-ПОДСИСТЕМЫ.md §4: `/keeps`, `/volumes` were a subsystem's routes on the platform's console — `extra` —
and the CRUD of a list of rows is the platform's work). A table is a family of rows `<sub>/<table>/<name>` that is not
units — nothing is placed on it, it has no epoch and no worker — and its spec says what a row is:

    tables:
      pins:
        key: name                 the body's field naming the row; or a name made of fields: "{item}-{a:int}-{b:int}"
        fields: {…}               as a unit's: types, required, defaults, a `*_secret` sealed and `bound_to` its address,
                                  a url's words, `ref`/`must_match`, `schema`
        schema: {…}               the row as a whole, JSON Schema (`schema.py`): what one field cannot say
        stamp: [by, at]           who wrote it and when, set by the console
        journal: {written: <kind>, deleted: <kind>}

and the console serves it (`SpecConsole`, `_table_route`):

    GET    /<table>               every row, as a page may show it: secrets left out, addresses as `hide_in_url` says
                                  them; a row that does not parse shown as one (`garbled`), whoever wrote it; the rows
                                  whose unit the caller may not see left out (`rights.unit_of`); a table that is the
                                  spec's PLACES (`placement.affinity.table`) says who holds each row (`held_by`)
    GET    /<table>/<name>        one row
    POST   /<table>               a row written whole: a new one, or one written again (last write wins: a list, not a
                                  unit) — the secret it does not send kept while the address it is bound to is not
                                  changed; what the subsystem's own rows say of the row agreed with (`must_match` the
                                  other way: a row pointed at by units that would no longer agree is refused)
    DELETE /<table>/<name>        the row goes; 404 for none — a row that does not parse is a row, and goes

Everything a write takes is said in the reply in words, and every write is a line in the console's journal, with who.
"""
from __future__ import annotations

import re

from .doors import safe_segment, unnamable
from .rows import PARSE_ERRORS

KEY_TEMPLATE = re.compile(r"\{([A-Za-z0-9_]+)(:int)?\}")


class TableSpec:
    """One declared table: its name, how a row is named, its fields, the row's schema, what is stamped, the journal."""

    def __init__(self, sub: str, name: str, key: str, fields: dict, schema=None, stamp: tuple = (), journal: dict | None = None):
        self.sub, self.name, self.key, self.fields = sub, name, key, fields
        self.schema, self.stamp, self.journal = schema, tuple(stamp), dict(journal or {})

    @property
    def templated(self) -> bool:
        return "{" in self.key

    def name_of(self, body: dict) -> str:
        """The row's name from the body: its key field, or the template filled in (`{f:int}` — the number, whole)."""
        if not self.templated:
            return str(body.get(self.key) or "")

        def one(m):
            v = body.get(m.group(1))
            if m.group(2):
                return str(int(float(v)))
            return str(v)
        return KEY_TEMPLATE.sub(one, self.key)


TABLE_KEYS = ("key", "fields", "schema", "stamp", "journal")   # what a table of a spec says

def parse(sub: str, raw, field_parser) -> tuple[tuple, dict]:
    """`tables:` as written — a list of names (a family the console's token may write, served by nobody), or a map of
    declarations — as `(names, {name: TableSpec})`. `field_parser(table, fields)` reads the fields as a unit's are read."""
    if raw is None:
        return (), {}
    if isinstance(raw, list):
        return tuple(str(t) for t in raw), {}
    if not isinstance(raw, dict):
        raise ValueError(f"spec {sub}: `tables:` is a list of names or a map of {{<name>: {{key, fields, …}}}}, not {raw!r}")
    from . import schema as _schema
    out = {}
    for t, d in raw.items():
        if d is None:
            continue
        if not isinstance(d, dict) or set(d) - set(TABLE_KEYS) or not isinstance(d.get("key"), str) \
                or not isinstance(d.get("fields") or {}, dict):
            raise ValueError(f"spec {sub}: tables.{t} is {{key, fields, schema, stamp, journal}}, not {d!r}")
        fields = field_parser(t, d.get("fields") or {})
        key = d["key"]
        named = {m.group(1) for m in KEY_TEMPLATE.finditer(key)} if "{" in key else {key}
        if not named or named - set(fields):
            raise ValueError(f"spec {sub}: tables.{t}.key names fields of its rows — {key!r} names {sorted(named - set(fields))}")
        stamp = d.get("stamp") or []
        if not isinstance(stamp, list) or set(stamp) - {"by", "at"}:
            raise ValueError(f"spec {sub}: tables.{t}.stamp is a list of `by`, `at`, not {stamp!r}")
        journal = d.get("journal") or {}
        if not isinstance(journal, dict) or set(journal) - {"written", "deleted"}:
            raise ValueError(f"spec {sub}: tables.{t}.journal is {{written: <kind>, deleted: <kind>}}, not {journal!r}")
        out[str(t)] = TableSpec(sub, str(t), key, fields,
                                _schema.load(d["schema"], f"spec {sub}: tables.{t}.schema") if "schema" in d else None,
                                tuple(stamp), {k: str(v) for k, v in journal.items()})
    return tuple(str(t) for t in raw), out


def refusal_of_name(name: str) -> str | None:
    """Why a row's name may not be one — it becomes a key, an ACL prefix and a label — or None."""
    if not name or not safe_segment(name) or name in (".", ".."):
        return f"a row's name is a name, not a path: {name[:80]!r}"
    bad = unnamable(name, unit=True)
    if bad:
        return f"a row's name may not hold {', '.join(repr(c) for c in bad)}: {name[:80]!r}"
    return None


def shown(items: dict, fields: dict) -> dict:
    """A stored row as a page may see it: values parsed, secrets left out, every address said as `hide_in_url` says it;
    the stamp `at` a number, as every time on a page is."""
    from .secrets import hide_in_url, is_secret_field
    out = {}
    for k, v in items.items():
        if is_secret_field(k):
            continue
        f = fields.get(k)
        try:
            v = f.parse(v) if f is not None else float(v) if k == "at" else v
        except PARSE_ERRORS:
            pass
        out[k] = hide_in_url(v) if isinstance(v, str) and "://" in v else v
    return out


# A ROW WRITTEN WHOLE — refused in words, or stored (sealed, stamped) and returned as `(name, items)`. What a unit's write
# asks, a row's asks too: the fields' types and words (`SubsystemSpec.refuse`, by a spec made of the table's fields), the
# mask and a sealed value refused, a secret kept only for the address it was given for (`bound_to`), the row's own
# schema; and what the subsystem's units say of the row (`must_match` the other way round: a row they point at may not
# be written to say what they no longer agree with). `units()` — the subsystem's live unit rows, asked only then. One
# function for whoever writes a row: the console (`SpecController.write_table_row`) and a subsystem's own code that
# declares one (a unit declaring the place it carries). `said`, when given, is filled with what the write changed of a row
# that was there — `changed` (the fields) and `was` (their values before) — for the journal's line: "give this less"
# says from what. A secret is never said, changed or not.
def write_row(spec, table: str, vars_, body, user: str = "", now: float = 0.0, sealer=None, units=lambda: [],
              said: dict | None = None) -> tuple[str, dict]:
    from .sealing import seal_items
    from .secrets import is_secret_field
    from .spec import Mismatched, Refused, SubsystemSpec, unbound_secret
    from .variables import Garbled
    t = spec.table_specs[table]
    if not isinstance(body, dict):
        raise Refused(f"a row of {table} is a JSON object")
    rowspec = SubsystemSpec(name=f"{spec.name}.{table}", rows=table, fields=t.fields)
    rowspec.refuse(body)
    try:
        name = t.name_of(body)
    except (*PARSE_ERRORS, OverflowError):
        raise Refused(f"a row of {table} is named {t.key}, and the body does not fill it in") from None
    why = refusal_of_name(name)
    if why:
        raise Refused(why)
    key = spec.sub.config(table, name)
    try:
        old, idx = vars_.get(key)
    except Garbled as e:                                  # a row nobody can read is written again whole
        old, idx = None, e.index
    sent = {k: v for k, v in body.items() if not (is_secret_field(k) and (v is None or v == ""))}
    row = {}
    for n, f in t.fields.items():
        if f.required and sent.get(n) in (None, ""):
            raise Refused(f"a row of {table} needs {n}")
        try:
            row[n] = f.take(sent[n]) if sent.get(n) is not None else f.default_value()
        except (*PARSE_ERRORS, OverflowError):            # `"1e12"` where a whole number goes, `1e999`: the sender's 400
            raise Refused(f"{n} is {f.type}, not {str(sent[n])[:60]!r}") from None
        if f.enum and sent.get(n) is not None and row[n] not in f.enum:   # `enum`: one of the values its spec names
            raise Refused(f"{n} is one of {', '.join(map(str, f.enum))}, not {str(sent[n])[:60]!r}")
    was = {}
    for n, f in t.fields.items():
        if old and n in old:
            try:
                was[n] = f.parse(old[n])
            except PARSE_ERRORS:
                was[n] = old[n]
    for n, f in t.fields.items():                         # the secret not sent: kept, for the address it was given for
        if is_secret_field(n) and n not in sent and old and old.get(n):
            why = unbound_secret(n, f.bound_to, was, row) if f.bound_to else None
            if why:
                raise Refused(why)
            row[n] = old[n]                               # as stored: sealed, to this row
    if t.schema is not None:
        from .schema import Invalid, check
        try:
            check(t.schema, {k: v for k, v in row.items() if v not in (None, "")}, table)
        except Invalid as e:
            raise Refused(str(e)) from None
    for n, f in t.fields.items():                         # what the row points at agrees with it (`ref` + `must_match`):
        v = str(row.get(n) or "")                         # the same check `refuse_refs` asks of a unit (ADR 0012)
        if not f.ref or not f.must_match or not v:
            continue
        if f.ref == f"{spec.name}/{table}" and v == name:
            there = row                                   # the row pointing at itself: what it says now
        else:
            try:
                there, _ = vars_.get(f"{f.ref}/{v}")
                if there is not None and not isinstance(there, dict):
                    raise TypeError(type(there).__name__)
            except (Garbled, *PARSE_ERRORS):
                raise Refused(f"{n} names {f.ref}/{v}, whose row does not parse: mend it first — nothing points at a "
                              f"row nobody can read") from None
        if there and there.get("deleted") != "true":
            for theirs, mine in f.must_match.items():
                want = str(there.get(theirs) or "")
                if want and str(row.get(mine) or "") != want:
                    raise Mismatched(f"{n} {v} is {theirs} {want}'s: only that {theirs}'s rows point at it, and {table} "
                                     f"{name} is {mine} {row.get(mine)}'s")
    ref = f"{spec.name}/{table}"
    for n, f in spec.fields.items():                      # the units pointing at it still agree (`must_match`)
        if f.ref != ref or not f.must_match:
            continue
        for unit in units():
            if str(unit.get(n) or "") != name:
                continue
            for theirs, mine in f.must_match.items():
                want = str(row.get(theirs) or "")
                if want and str(unit.get(mine) or "") != want:
                    raise Mismatched(f"{unit['id']} has {n} {name} and is {mine} {unit.get(mine)}'s: the row would say "
                                  f"{theirs} {want} — change {unit['id']} first")
    if said is not None and old:
        blank = lambda v: None if v in (None, "") else v              # noqa: E731 — an empty word is not stored
        changed = [n for n in t.fields if not is_secret_field(n) and blank(was.get(n)) != blank(row.get(n))]
        said.update(changed=changed, was={n: was[n] for n in changed if n in was})
    if "by" in t.stamp:
        row["by"] = user
    if "at" in t.stamp:
        row["at"] = now
    items = {n: (t.fields[n].to_item(v) if n in t.fields else str(v)) for n, v in row.items()
             if v is not None and not (n in t.fields and t.fields[n].type == "string" and v == "" and n not in sent)}
    vars_.put(key, seal_items(sealer, items, key), cas=idx)
    return name, items


def delete_row(spec, table: str, vars_, name: str) -> bool:
    """The row goes; False when there was none. A row that does not parse is a row, and goes."""
    from .variables import Garbled
    if refusal_of_name(name):
        return False
    key = spec.sub.config(table, name)
    try:
        there = vars_.get(key)[0] is not None
    except Garbled:
        there = True
    if there:
        vars_.delete(key)
    return there
