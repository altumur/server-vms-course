"""Probe 15/A, batch 2: a few more mutations of the course testsub2 (see mutate.py)."""
import copy, sys, yaml
base_path, out = sys.argv[1], sys.argv[2]
BASE = yaml.safe_load(open(base_path, encoding="utf-8"))
MUT = []
def m(name):
    def deco(fn): MUT.append((name, fn)); return fn
    return deco
@m("about_field_not_fixed_nowitness")
def _(d): d["unit"]["fields"]["of"].pop("fixed", None); d.pop("domain", None)
@m("table_field_merge")
def _(d): d["tables"]["shelves"]["fields"]["zone"]["merge"] = "union"
@m("table_metrics_shadow")
def _(d): d["tables"]["metrics"] = {"key": "name", "fields": {"name": {"type": "string"}}}
@m("table_events_shadow")
def _(d): d["tables"]["events"] = {"key": "name", "fields": {"name": {"type": "string"}}}
@m("rows_where")
def _(d): d["unit"]["rows"] = "where"
@m("tie_break_absent")
def _(d): d["placement"].pop("tie_break")
@m("bound_to_list_of_one")
def _(d): d["unit"]["fields"]["feed_secret"]["bound_to"] = ["feed"]
@m("required_true_string")
def _(d): d["unit"]["fields"]["name"]["required"] = "true"
@m("secrets_readers_role_number")
def _(d): d["secrets"]["readers"]["door/signer"] = [1]
@m("worker_writes_path")
def _(d): d["worker"]["writes"] = ["shelves/x"]
for name, fn in MUT:
    d = copy.deepcopy(BASE); fn(d)
    yaml.safe_dump(d, open(f"{out}/{name}.subsystem.yaml", "w", encoding="utf-8"), sort_keys=False, allow_unicode=True, width=4096, default_flow_style=False)
print(len(MUT), "cases")
