"""Probe (review 15): a `unit.derived.items` entry naming a field that does not exist loads (ADR-0012) — and what the
resource then reads: the derived retention row is written EMPTY, `retention_days` falls back to the default (365),
the operator's `keep_days: 7` never reaches the resource."""
import sys
sys.path.insert(0, sys.argv[1])
from w2cplatform.memvariables import MemVariables
from w2cplatform.objects import FsObjectStore
from w2cplatform.spec import SpecController, SubsystemSpec
from w2cplatform.resource import retention_days
import tempfile

spec = SubsystemSpec.from_dict({
    "name": "p", "unit": {"rows": "units", "id": "name",
                          "fields": {"name": {"type": "string", "required": True}, "keep_days": {"type": "int", "default": 7}},
                          "derived": [{"row": "retention/{id}", "items": {"days": "keep_dayz"}, "on_delete": {"days": 0}}]},
    "placement": {"capacity": {"from": "capacity", "default": 4}},
})
print("loaded: derived items =", spec.derived[0].items)
vars_ = MemVariables()
ctl = SpecController(spec, vars_, FsObjectStore(tempfile.mkdtemp()))
ctl.create({"name": "u1", "keep_days": 7})
print("unit row:", vars_.get("p/units/u1")[0])
print("derived row p/retention/u1:", vars_.get("p/retention/u1")[0])
print("retention_days(p, u1) as the resource reads it:", retention_days(vars_, "p", "u1"), "(the operator said 7)")
