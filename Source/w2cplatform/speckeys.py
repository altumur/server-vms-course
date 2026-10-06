"""Every key a spec may say, at every level: one the platform does not read is refused at load, named with where it
stands (the architect, 2026-10-05: the key sets are closed — nothing is accepted and passed over)."""
# ================================================================================================
# NOTES
# ================================================================================================
# A key nobody reads is a promise nobody keeps: a typo (`requries: resource`) loads and places as if it were not
# there, and another team's key (one the product reads) loads and reads as if the platform did something with it. So the
# load walks the YAML as written and refuses the first key that is not here — `SubsystemSpec.from_dict` asks it last,
# after the readers whose own words say more about the keys they know.
#
# The paths are written as the walk writes them: a map's key after a `.`; `*` where the keys are names (a field, a
# table, an event kind, a token's kind, a family of keys); the items of a list under the list's own path (`metrics.agg`
# is the `agg` of every item of `metrics`). Under an OPAQUE path the spec writes words, a JSON Schema or a match the
# platform reads by its own rule, and nothing is walked.
#
# ## Module-level names
# - `KEYS` — every path a spec may hold (a path's parents may stand too); `NAMED`, `OPAQUE` — as above; `JSON_VALUES` — opaque
#   under a field of `type: json` only (its `default`, `inherit`: any JSON value).
# - `unknown(d)` — the paths of `d` that are none of them, each with the keys as written; `refuse_unknown(name, d)`.
# ================================================================================================
from __future__ import annotations

from . import metrics
from .spec import TREE_WORDS
from .tables import TABLE_KEYS

NAMED = {"unit.fields", "tables", "tables.*.fields", "events.suppress", "display.keys", "display.options",
         "domain.tokens", "domain.names", "secrets.readers", "unit.fields.*.schemes",
         "tables.*.fields.*.schemes"}
OPAQUE = {"display.field_help", "display.kinds", "display.actions", "display.fields", "display.options.*",
          "requests.schema", "tables.*.schema", "unit.fields.*.schema", "tables.*.fields.*.schema",
          "placement.near.prefer", "placement.affinity.strict", "rights.unit_of", "placement.places.where",
          "metrics.where", "metrics.unless.where", "metrics.labels", "unit.derived.items", "unit.derived.on_delete",
          "unit.fields.*.must_match", "tables.*.fields.*.must_match", "domain.shared.schema"}
# …and under these only where the field is `type: json`: its `default` and `inherit` are a JSON value, any — a map or a
# list included (`{type: json, default: {a: 1}}`; the fourteenth review, minor 25: the closed set refused a legal
# default as keys nobody reads). Another type's value is no map, and a map under it is walked and refused as before.
JSON_VALUES = {"unit.fields.*.default", "unit.fields.*.inherit", "tables.*.fields.*.default"}

# A field's own words — of a unit's row and of a table's alike.
FIELD_KEYS = ("type", "default", "required", "inherit", "merge", "bound_to", "fixed", "enum", "schema", "ref",
              "must_match", "unique", "schemes.*.host", "schemes.*.fragment", "schemes.*.none", "credentials.login",
              "credentials.secret", "secret_in.param",
              "secret_in.login", "secret_in.regex", "secret_in.in", "secret_in.schemes", "secret_in.decoded",
              "secret_in.nested")
# …of a table's: what a row written whole says (`tables.py`) — no `inherit`/`merge` (nothing above a table's row), no
# `fixed` or `unique` (a row is written again whole, last write wins).
TABLE_FIELD_KEYS = tuple(k for k in FIELD_KEYS if k not in ("inherit", "merge", "fixed", "unique"))

KEYS = {
    "name", "about.sub", "about.field", "slot.prefix", "slot.name_env", "worker.writes", "worker.reads",
    "worker.requests", "objects.rows", "objects.door", "heartbeat.strings", "secrets.readers.*", "secrets.reads",
    "lease.unconfirmed_max", "snapshot",
    "door.routes", "console.running", "events.older_epochs", "events.suppress.*.window", "events.suppress.*.by",
    "unit.rows", "unit.id", *(f"unit.fields.*.{k}" for k in FIELD_KEYS),
    "unit.derived.row", "unit.derived.items", "unit.derived.on_delete",
    *(f"tables.*.{k}" for k in TABLE_KEYS if k not in ("fields", "journal")), "tables.*.journal.written",
    "tables.*.journal.deleted", *(f"tables.*.fields.*.{k}" for k in TABLE_FIELD_KEYS),
    "placement.capacity.from", "placement.capacity.default", "placement.headroom.from", "placement.constraint",
    "placement.requires", "placement.servers", "placement.tie_break", "placement.near.sub", "placement.near.by",
    "placement.near.of", "placement.near.prefer", "placement.spread_by", "placement.group_by.field",
    "placement.group_by.cut_at", "placement.place_by", "placement.places.table", "placement.places.where",
    "placement.places.server_field", "placement.places.lease", "placement.offers", "placement.home",
    "placement.retire_when.field",
    "placement.retire_when.in", "placement.rebalance.dead_band", "placement.affinity.field", "placement.affinity.table",
    "placement.affinity.server_field", "placement.affinity.strict",
    "holds.table", "holds.unit", "holds.since", "holds.until", "holds.longest",
    "requests.free", "requests.schema", "requests.key", "requests.valid_for", "requests.most_valid",
    "requests.per_person", "requests.settle", "requests.ttl", "requests.stamp", "requests.journal", "requests.elsewhere",
    "rights.unit_of", "rights.routes.view", "rights.routes.edit", "rights.cluster_rows", "rights.reach.group",
    "rights.reach.cluster", "rights.reach.requests", "rights.names.field", "rights.names.unit", "rights.names.sub",
    "rights.names.of",
    "servers.show.table", "servers.show.by", "servers.show.title", "servers.show.columns", "servers.status.field",
    "servers.status.title", "servers.status.of",
    *(f"metrics.{k}" for k in metrics.KEYS), "metrics.unless.table", "metrics.unless.where",
    "display.unit", "display.units", "display.units_count", "display.section", "display.events", "display.field_help",
    "display.kinds", "display.actions", "display.tree.group_by", "display.tree.columns.field",
    "display.tree.columns.title", "display.tree.columns.width", "display.tree.children",
    *(f"display.tree.{w}" for w in TREE_WORDS), "display.keys.*.title", "display.keys.*.about", "display.keys.*.absent",
    "display.general", "display.fields", "display.options.*", "display.form.title", "display.form.state",
    "display.form.placement", "display.form.fields", "display.form.status.field", "display.form.status.since",
    "display.form.status.title", "display.form.note",
    "domain.ref", "domain.view", "domain.reports", "domain.witness.report", "domain.witness.member_field",
    "domain.books", "domain.kept", "domain.tables",
    "domain.tokens.*.lifetime", "domain.tokens.*.claims", "domain.keys.id", "domain.keys.keys",
    "domain.keys.prefix", "domain.shared", "domain.shared.name", "domain.shared.type", "domain.shared.schema",
    "domain.names.*.exclusive_with", "domain.names.*.grant",
    "domain.edit",
}
_TAKEN = KEYS | {p.rsplit(".", i)[0] for p in KEYS for i in range(1, p.count(".") + 1)}


def unknown(d, at: str = "", said: str = "") -> list[str]:
    """The paths of `d` no spec may hold, as written (`unit.fields.source.secrets`), in the order they stand."""
    out: list[str] = []
    if isinstance(d, list):
        for x in d:
            out += unknown(x, at, said)
        return out
    if not isinstance(d, dict):
        return out
    for k, v in d.items():
        p = f"{at}.{'*' if at in NAMED else k}" if at else str(k)
        written = f"{said}.{k}" if said else str(k)
        if p not in _TAKEN:
            out.append(written)
        elif p not in OPAQUE and not (p in JSON_VALUES and d.get("type") == "json"):
            out += unknown(v, p, written)
    return out


def refuse_unknown(name, d: dict) -> None:
    stray = unknown(d)
    if stray:
        raise ValueError(f"spec {name}: no spec says {', '.join(f'`{p}`' for p in stray)} — a key the platform does "
                         f"not read is a mistake or another's word; it is refused, not passed over")
