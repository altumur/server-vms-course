"""Probe (review 15): what a spec with a misspelt field in `holds:` and `rights.unit_of` does at run time (loaded: see
probe_loader_fields). holds: a pin row stands and holds NOTHING — the resource sweeps the pinned bucket. unit_of: every
row of the table "names nobody" — the console lists it to every viewer."""
import sys, tempfile
sys.path.insert(0, sys.argv[1])
from w2cplatform import holds
from w2cplatform.memvariables import MemVariables
from w2cplatform.spec import SubsystemSpec

mk = lambda unit_field, uo_field: SubsystemSpec.from_dict({
    "name": "p", "unit": {"rows": "units", "id": "name", "fields": {"name": {"type": "string", "required": True}}},
    "placement": {"capacity": {"from": "capacity", "default": 4}},
    "tables": {"pins": {"key": "name", "fields": {"name": {"type": "string", "required": True}, "item": {"type": "string"},
                                                   "a": {"type": "float"}, "b": {"type": "float"}}}},
    "holds": {"table": "pins", "unit": unit_field, "since": "a", "until": "b"},
    "rights": {"unit_of": {"pins": uo_field}},
})
vars_ = MemVariables()
vars_.put("p/pins/pin1", {"name": "pin1", "item": "u1", "a": "100", "b": "200"})   # a person pinned u1's 100..200
for title, spec in (("spelt right (unit: item, unit_of: item)", mk("item", "item")),
                    ("misspelt (unit: itm, unit_of: itemm)", mk("itm", "itemm"))):
    held = holds.kept(vars_, [spec])
    print(f"{title}:")
    print(f"   bucket p/u1 [120, 180) held by pin1? {held('p', 'u1', 120, 180)}  (False: retain sweeps it past its days)")
    print(f"   whose is row pin1 (rights.unit_of)?  {spec.table_unit('pins', vars_.get('p/pins/pin1')[0])}  "
          f"(('', True): names nobody — listed to every viewer, console.py _table_route)")
