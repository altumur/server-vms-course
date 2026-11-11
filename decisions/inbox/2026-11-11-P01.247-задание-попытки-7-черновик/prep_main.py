"""P01.247: the same loop's prep of the filled draft on today's main (the M of attempt 7 is cut from it after the spec tasks):
stage_prep with task specs pointed at a main tree (norm_trace_prep reads the items from task["specs"]), the mode items of
P01.216 and the method marks [test|reading|stand] of P01.176/P01.228 on them — the loop does not read the marks yet.
Run: python3 -I prep_main.py <minimax-loop tree> <filled task json> <main tree>"""
import sys, os, re
from collections import Counter
mm, task_p, main = sys.argv[1:4]
sys.path.insert(0, mm)
import loop, norm_trace as nt, mode_trace as mdt
t = loop.load_task(task_p); t["specs"] = os.path.abspath(main)
class R: pass
r = R(); r.map = {"specs": t["specs"]}
plan = loop.stage_prep(t, r); st = plan["stages"]; n = plan.get("norm_trace")
print("stages", len(st), [s["stage"] for s in st])
print("code_at", [s["stage"] for s in st if any(c["gate_kind"] == "code" for c in s["checks"])])
print("norm_trace", n["items"], n["by_stage"])
les = t["lesson"]
items = nt.read_items(t["specs"], les)
got, ms = mdt.mode_items(t["specs"], les, items)
print("mode_stages", ms)
lab = {}
for it in items:
    ln = open(os.path.join(t["specs"], les, "spec", it["file"]), encoding="utf-8").read().split("\n")[it["line"] - 1]
    # the mark stands right after the id or after the label «**Scope: production.**» (P01.228; fixed by P01.248)
    m = re.match(r"^- \[ \] \*\*[^*]+\*\*(?: \*\*Scope: production\.\*\*)?\s*\[([^\]]+)\]", ln)
    lab[it["id"]] = m.group(1) if m else None
print("mode_items", len(got), "marks", dict(Counter(lab[i] for i in got)))
print("mode items without the mark test", [i for i in got if "test" not in (lab[i] or "")])
print("all items marks", dict(Counter(lab.values())))
print("items without the mark test", sorted(i for i in lab if "test" not in (lab[i] or "")))
print("items with no mark right after the id", [i for i in lab if lab[i] is None])
