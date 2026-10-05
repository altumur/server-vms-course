"""Every key the platform reads in a spec, and every operator of its metrics, is used by a spec (the architect's rule,
2026-10-05): by at least two of the product's subsystems, or by a test subsystem of the platform's own
(`testdata/testsub*.subsystem.yaml`). A key only one subsystem needs is that subsystem's code wearing the platform's
clothes — it goes, or a spec that has nothing to do with the product shows what it is for. A test of the platform alone:
it reads the YAML files, and imports no subsystem's package."""
from __future__ import annotations

import glob
import os

import yaml

from w2cplatform import metrics
from w2cplatform.spec import SubsystemSpec

HERE = os.path.dirname(os.path.abspath(__file__))
TESTSUBS = sorted(glob.glob(os.path.join(HERE, "testdata", "testsub*.subsystem.yaml")))
# The subsystems the code root ships: every spec in a package beside the tests (the product's, by whatever name).
ROOT = os.path.dirname(HERE)
PRODUCT = sorted(p for p in glob.glob(os.path.join(ROOT, "*", "*.subsystem.yaml")) if not p.startswith(HERE + os.sep))

# Where a spec's keys are NAMES (a field, a table, an event kind): one `*` for all of them.
NAMED = {"unit.fields", "tables", "tables.*.fields", "events.suppress"}
# Where a spec writes words or a document the platform passes on whole: not walked.
OPAQUE = {"display.field_help", "display.kinds", "display.actions", "requests.schema", "tables.*.schema",
          "unit.fields.*.schema", "tables.*.fields.*.schema", "placement.near.prefer", "placement.affinity.strict",
          "rights.unit_of", "placement.places.where", "metrics.where", "metrics.unless.where", "metrics.labels",
          "tables.*.journal", "unit.derived.items", "unit.derived.on_delete", "unit.fields.*.must_match",
          "tables.*.fields.*.must_match"}
# Scalars whose VALUE is an operator: `metrics.agg=sum`.
OPERATORS = {"metrics.agg", "metrics.type"}

# What the platform reads, key by key (`spec.py`, `metrics.py`, `tables.py`, `holds.py`, `door.py`). The lists the code
# keeps itself are asserted below to be inside this one, so a key added to the code and not here fails too.
IMPLEMENTED = {
    "name", "about.sub", "about.field", "slot.prefix", "slot.name_env", "worker.writes", "worker.reads", "worker.requests",
    "objects.rows", "snapshot", "door.routes", "console.running", "events.older_epochs", "events.suppress.*.window",
    "events.suppress.*.by",
    "unit.rows", "unit.id", "unit.fields.*.type", "unit.fields.*.default", "unit.fields.*.required",
    "unit.fields.*.inherit", "unit.fields.*.merge", "unit.fields.*.bound_to", "unit.fields.*.fixed",
    "unit.fields.*.enum", "unit.fields.*.schema", "unit.fields.*.ref", "unit.fields.*.must_match",
    "unit.fields.*.unique", "unit.fields.*.schemes", "unit.fields.*.credentials.login",
    "unit.fields.*.credentials.secret", "unit.fields.*.secret_in.param", "unit.fields.*.secret_in.nested",
    "unit.derived.row", "unit.derived.items", "unit.derived.on_delete",
    "tables.*.key", "tables.*.fields.*.type", "tables.*.fields.*.required", "tables.*.fields.*.default",
    "tables.*.fields.*.enum", "tables.*.schema", "tables.*.stamp", "tables.*.journal",
    "placement.capacity.from", "placement.capacity.default", "placement.headroom.from", "placement.constraint",
    "placement.requires", "placement.servers", "placement.tie_break", "placement.near.sub", "placement.near.by",
    "placement.near.of", "placement.near.prefer", "placement.spread_by", "placement.group_by.field",
    "placement.group_by.cut_at", "placement.place_by", "placement.places.table", "placement.places.where", "placement.places.server_field",
    "placement.offers", "placement.home", "placement.retire_when.field", "placement.retire_when.in",
    "placement.rebalance.dead_band", "placement.affinity.field", "placement.affinity.table",
    "placement.affinity.server_field", "placement.affinity.strict",
    "holds.table", "holds.unit", "holds.since", "holds.until", "holds.longest",
    "requests.free", "requests.schema", "requests.key", "requests.valid_for", "requests.most_valid",
    "requests.per_person", "requests.settle", "requests.ttl", "requests.stamp", "requests.journal", "requests.elsewhere",
    "rights.unit_of", "rights.routes.view", "rights.routes.edit", "rights.cluster_rows", "rights.reach.group",
    "rights.reach.cluster", "rights.reach.requests", "rights.names.field", "rights.names.unit", "rights.names.sub",
    "rights.names.of",
    "servers.show.table", "servers.show.by", "servers.show.title", "servers.show.columns",
    "display.unit", "display.units", "display.field_help", "display.kinds", "display.actions", "display.tree.group_by",
    "display.tree.nested_by", "display.tree.columns.field", "display.tree.children",
    *{f"metrics.{k}" for k in metrics.KEYS}, *{f"metrics.agg={a}" for a in metrics.AGGS},
    *{f"metrics.type={t}" for t in metrics.TYPES}, "metrics.unless.table", "metrics.unless.where",
}


def _paths(d, at: str = "") -> set[str]:
    out = set()
    if isinstance(d, list):
        for x in d:
            out |= _paths(x, at)
        return out
    if not isinstance(d, dict):
        return out
    for k, v in d.items():
        key = "*" if at in NAMED else str(k)
        p = f"{at}.{key}" if at else key
        out.add(p)
        if p in OPERATORS and isinstance(v, str):
            out.add(f"{p}={v}")
        if p not in OPAQUE:
            out |= _paths(v, p)
    return out


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_every_key_and_operator_the_platform_reads_is_used_by_two_subsystems_or_by_a_test_subsystem():
    assert len(TESTSUBS) == 2 and len(PRODUCT) >= 2
    for path in TESTSUBS:
        SubsystemSpec.load(path)                                         # each loads as the platform reads it
    mine = set().union(*(_paths(_load(p)) for p in TESTSUBS))
    theirs = [_paths(_load(p)) for p in PRODUCT]
    unused = sorted(k for k in IMPLEMENTED if k not in mine and sum(k in t for t in theirs) < 2)
    assert not unused, f"read by the platform, used by fewer than two subsystems and by no test subsystem: {unused}"
    # …and the vocabulary the code keeps is inside the list above (a key added to the code is a key added here)
    from w2cplatform.spec import REQUEST_KEYS
    from w2cplatform.tables import TABLE_KEYS
    code = {f"tables.*.{k}" for k in TABLE_KEYS if k != "fields"} | {f"requests.{k}" for k in REQUEST_KEYS}
    assert code <= IMPLEMENTED, sorted(code - IMPLEMENTED)


def test_a_key_no_spec_uses_is_found_by_the_walk():
    """The walk itself: names stand as `*`, words passed on whole are not walked, an operator is its value."""
    got = _paths({"unit": {"fields": {"x": {"type": "int", "schema": {"minimum": 1}}}},
                  "metrics": [{"name": "m", "from": "status.phase", "agg": "count", "where": {"a": 1}}]})
    assert {"unit.fields.*.type", "unit.fields.*.schema", "metrics.agg=count", "metrics.where"} <= got
    assert "unit.fields.*.schema.minimum" not in got and "metrics.where.a" not in got
