"""Probe 15/A: mutations of a spec for both loaders (course spec.py, product unit.go).

usage: python mutate.py <base.subsystem.yaml> <out dir>
Writes <out dir>/<case>.subsystem.yaml for every mutation, plus base.subsystem.yaml (the round-tripped base).
"""
import copy
import sys

import yaml

base_path, out = sys.argv[1], sys.argv[2]
with open(base_path, encoding="utf-8") as f:
    BASE = yaml.safe_load(f)


def m(name):
    def deco(fn):
        MUT.append((name, fn))
        return fn
    return deco


MUT = []


@m("base")
def _(d): pass


@m("hb_worker")
def _(d): d["heartbeat"]["strings"].append("worker")


@m("status_worker")
def _(d): d["servers"]["status"].append({"field": "worker", "title": "W"})


@m("status_url")
def _(d): d["servers"]["status"].append({"field": "url", "title": "U"})


@m("tie_break_random")
def _(d): d["placement"]["tie_break"] = "random"


@m("requires_nothing")
def _(d): d["placement"]["requires"] = "nothing"


@m("servers_both")
def _(d): d["placement"]["servers"] = "both"


@m("about_field_not_fixed")
def _(d): d["unit"]["fields"]["of"].pop("fixed", None)


@m("fixed_yes")
def _(d): d["unit"]["fields"]["of"]["fixed"] = "yes"


@m("required_yes")
def _(d): d["unit"]["fields"]["name"]["required"] = "yes"


@m("table_servers")
def _(d): d["tables"]["servers"] = {"key": "name", "fields": {"name": {"type": "string"}}}


@m("table_marks")
def _(d): d["tables"]["marks"] = {"key": "name", "fields": {"name": {"type": "string"}}}


@m("rows_servers")
def _(d): d["unit"]["rows"] = "servers"


@m("enum_on_list")
def _(d): d["unit"]["fields"]["tags"]["enum"] = ["a", "b"]


@m("enum_empty")
def _(d): d["unit"]["fields"]["mode"]["enum"] = []


@m("slot_prefix_long")
def _(d): d["slot"]["prefix"] = "abcdefghij"


@m("slot_prefix_digit")
def _(d): d["slot"]["prefix"] = "t1"


@m("capacity_default_float")
def _(d): d["placement"]["capacity"]["default"] = 2.5


@m("capacity_default_string")
def _(d): d["placement"]["capacity"]["default"] = "5"


@m("capacity_default_true")
def _(d): d["placement"]["capacity"]["default"] = True


@m("capacity_default_absent")
def _(d): d["placement"]["capacity"].pop("default")


@m("objects_rows_heartbeats")
def _(d): d["objects"]["rows"].append("heartbeats/*")


@m("objects_rows_commands")
def _(d): d["objects"]["rows"].append("commands/*")


@m("objects_door_heartbeats")
def _(d): d["objects"]["door"].append("heartbeats/*")


@m("display_events_word")
def _(d): d.setdefault("display", {})["events"] = "no"


@m("table_field_fixed")
def _(d): d["tables"]["shelves"]["fields"]["zone"]["fixed"] = True


@m("table_field_inherit")
def _(d): d["tables"]["shelves"]["fields"]["zone"]["inherit"] = "x"


@m("default_map_string")
def _(d): d["unit"]["fields"]["zone"] = {"type": "string", "default": {"a": 1}}


@m("inherit_map_string")
def _(d): d["unit"]["fields"]["zone"] = {"type": "string", "inherit": {"a": 1}}


@m("requests_per_person_frac")
def _(d): d["requests"]["per_person"] = 2.5


@m("requests_ttl_nan")
def _(d): d["requests"]["ttl"] = float("nan")


@m("requests_valid_past_most")
def _(d): d["requests"]["valid_for"] = 700


@m("field_type_text")
def _(d): d["unit"]["fields"]["zone"]["type"] = "text"


@m("unit_id_nosuch")
def _(d): d["unit"]["id"] = "nosuch"


@m("dead_band_word")
def _(d): d["placement"]["rebalance"] = {"dead_band": "fast"}


@m("dead_band_negative")
def _(d): d["placement"]["rebalance"] = {"dead_band": -1}


@m("worker_reads_bare")
def _(d): d["worker"]["reads"] = ["testsub"]


@m("secrets_reader_domainconsole")
def _(d): d["secrets"]["readers"]["door/signer"] = ["domainconsole"]


@m("worker_writes_undeclared")
def _(d): d["worker"]["writes"] = ["ghosts"]


@m("unplaced_zero")
def _(d): d["placement"]["unplaced"] = {"delete_after": 0}


@m("holds_longest_zero")
def _(d): d["holds"]["longest"] = 0


@m("places_place_by_server")
def _(d): d["placement"]["place_by"] = "server"


@m("near_prefer_without_of")
def _(d): d["placement"]["near"].pop("of")


@m("display_tree_unknown")
def _(d): d.setdefault("display", {}).setdefault("tree", {})["colour"] = "red"


@m("metric_unknown_agg")
def _(d): d["metrics"][1]["agg"] = "median"


@m("bound_to_string")
def _(d): d["unit"]["fields"]["feed_secret"]["bound_to"] = "feed"


@m("door_routes_dup")
def _(d): d["door"]["routes"] = ["read", "read"]


@m("snapshot_secret")
def _(d): d["snapshot"].append("feed_secret")


@m("about_sub_self")
def _(d): d["about"]["sub"] = d["name"]


@m("offers_string")
def _(d): d["placement"]["offers"] = "true"


@m("heartbeat_strings_dup")
def _(d): d["heartbeat"]["strings"] = ["jam", "jam"]


@m("heartbeat_strings_server")
def _(d): d["heartbeat"]["strings"] = ["server"]


@m("secrets_reads_empty")
def _(d): d["secrets"]["reads"] = [""]


@m("places_lease_lenient")
def _(d): d["placement"]["places"]["lease"] = "lenient"


@m("suppress_window_zero")
def _(d): d["events"]["suppress"]["tally.tick"]["window"] = 0


@m("unit_derived_with_unplaced")
def _(d): d["placement"]["unplaced"] = {"delete_after": 60}


@m("tables_list_only_writes")
def _(d):
    d["tables"] = ["shelves", "notches"]
    for k in ("holds", "rights", "servers"):
        d.pop(k, None)
    d["placement"].pop("affinity", None)
    d["metrics"] = [x for x in d["metrics"] if "count" not in x]


@m("spread_by_eq_group_by")
def _(d):
    d["placement"]["group_by"] = "zone"
    d["placement"]["spread_by"] = "zone"


@m("name_platform")
def _(d): d["name"] = "platform"


@m("rows_asked")
def _(d): d["unit"]["rows"] = "asked"


for name, fn in MUT:
    d = copy.deepcopy(BASE)
    fn(d)
    with open(f"{out}/{name}.subsystem.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(d, f, sort_keys=False, allow_unicode=True, width=4096, default_flow_style=False)
print(len(MUT), "cases written to", out)
