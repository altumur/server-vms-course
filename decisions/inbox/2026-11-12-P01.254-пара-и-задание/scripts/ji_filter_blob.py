# P01.180: the assembled J-input filter of J (operator's assemble), cross-checked with check_spec's export_lists on archive-C.
import sys, os, json, hashlib, subprocess
sys.dont_write_bytecode = True
W = str(__import__("pathlib").Path(__file__).resolve().parent.parent); sys.path.insert(0, W + "/operator"); sys.path.insert(0, W + "/archive-C/skills/lesson-spec/scripts")
import judge_input_export as ji, export_lists
gd, J = sys.argv[1], sys.argv[2]
tree = {}
for e in subprocess.run(["git", "--git-dir=" + gd, "ls-tree", "-r", "-z", J], capture_output=True, check=True).stdout.split(b"\0"):
    if e:
        h, p = e.split(b"\t", 1); m, t, o = h.split(); tree[p.decode()] = (m.decode(), o.decode())
raw, src = ji.assemble(gd, tree)
asm, errs, _ = export_lists.assemble(W + "/archive-C")
mine = {x["path"]: x for x in json.loads(raw)["files"]}
theirs = {x["path"]: x for x in asm["judge"]}
key = "selection" if any("selection" in x for x in mine.values()) else "disposition"
same = (not errs) and {p: x.get(key) for p, x in mine.items()} == {p: x.get(key) for p, x in theirs.items()}
print(json.dumps({"ji_filter_blob": hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest(), "ji_filter_sha256": hashlib.sha256(raw).hexdigest(),
                  "sources": src, "records": len(mine), "include": sum(1 for x in mine.values() if x.get(key) == "include"),
                  "equal_check_spec_export_lists_judge": same, "field": key}, indent=1))
