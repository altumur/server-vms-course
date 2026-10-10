"""Probe (review 15): which spec keys that NAME A FIELD are not checked against `fields:` at load (ADR-0012).
Each case is a spec that names a field that does not exist; the loader should refuse it. Prints LOADED / REFUSED."""
import copy, sys
sys.path.insert(0, sys.argv[1])
from w2cplatform import catalog
from w2cplatform.spec import SubsystemSpec

BASE = {
    "name": "p", "unit": {"rows": "units", "id": "name",
                          "fields": {"name": {"type": "string", "required": True}, "home": {"type": "string"},
                                     "keep_days": {"type": "int", "default": 7}}},
    "placement": {"capacity": {"from": "capacity", "default": 4}, "place_by": "disk"},
    "tables": {"disks": {"key": "name", "fields": {"name": {"type": "string", "required": True},
                                                   "server": {"type": "string"}, "kind": {"type": "string"},
                                                   "admits": {"type": "bool", "default": True}}},
               "pins": {"key": "name", "fields": {"name": {"type": "string", "required": True},
                                                  "item": {"type": "string"}, "a": {"type": "float"}, "b": {"type": "float"}}}},
}

def case(title, mutate):
    d = copy.deepcopy(BASE)
    mutate(d)
    try:
        SubsystemSpec.from_dict(d)
        print(f"LOADED   {title}")
    except ValueError as e:
        print(f"REFUSED  {title}: {str(e)[:110]}")

case("unit.derived.items names a field that does not exist (dayz)",
     lambda d: d["unit"].__setitem__("derived", [{"row": "retention/{id}", "items": {"days": "keep_dayz"}, "on_delete": {"days": 0}}]))
case("servers.show.by names no field of the table (servre)",
     lambda d: d.__setitem__("servers", {"show": [{"table": "disks", "by": "servre", "title": "Disks"}]}))
case("holds.unit/since/until name no fields of the table (itm, aa, bb)",
     lambda d: d.__setitem__("holds", {"table": "pins", "unit": "itm", "since": "aa", "until": "bb"}))
case("affinity.server_field names no field of the table (servre)",
     lambda d: d["placement"].__setitem__("affinity", {"field": "home", "table": "disks", "server_field": "servre"}))
case("affinity.strict key names no field of the table (kinnd)",
     lambda d: d["placement"].__setitem__("affinity", {"field": "home", "table": "disks", "strict": {"kinnd": "local"}}))
case("places.server_field / where name no fields of the table (servre, rolle)",
     lambda d: d["placement"].__setitem__("places", {"table": "disks", "server_field": "servre", "where": {"rolle": "main"}}))
case("rights.unit_of names no field of the table (itemm)",
     lambda d: d.__setitem__("rights", {"unit_of": {"pins": "itemm"}}))
case("metrics count where names no field of the table (kinnd)",
     lambda d: d.__setitem__("metrics", [{"name": "local_disks", "count": "table disks", "where": {"kinnd": "local"}}]))
case("display.tree.columns field of the row: CHECKED (control)",
     lambda d: d.__setitem__("display", {"tree": {"columns": [{"field": "nope"}]}}))

# the neighbour's field in near.prefer, with the neighbour in the catalogue (ADR-0056: checked where the catalogue is whole)
n = copy.deepcopy(BASE); n["name"] = "nb"; n["placement"].pop("place_by")
catalog.register(SubsystemSpec.from_dict(n))
d = copy.deepcopy(BASE); d["placement"].pop("place_by")
d["placement"]["near"] = {"sub": "nb", "of": "home", "prefer": {"kinnd": "backup"}}
try:
    s = SubsystemSpec.from_dict(d); catalog.register(s); catalog.near_known(s)
    print("LOADED   near.prefer key names no field of the neighbour (kinnd), near_known passed")
except ValueError as e:
    print(f"REFUSED  near.prefer: {str(e)[:110]}")
