# Semantic delta of assembled M and J-input filters between two commits (operators of P02.52).
import sys, os, json
sys.dont_write_bytecode = True
W = str(__import__("pathlib").Path(__file__).resolve().parent.parent); sys.path.insert(0, W + "/operator")
import b7_export_pair as b, judge_input_export as ji
SRC = sys.argv[3]
def side(C):
    fd = b._open_dir(b._canonical(SRC))
    try: entries = b._source(fd, C)
    finally: os.close(fd)
    entries[b.MARKER] = ("100644", None, (C + "\n").encode())
    raw, value, sources = b._assemble(entries)
    m = {x["path"]: x["disposition"] for x in value["files"]}
    tree = {p: (mm, o) for p, (mm, o, _) in entries.items() if p != b.MARKER}
    jraw, jsrc = ji.assemble(SRC, tree)
    jv = json.loads(jraw)
    jd = {x["path"]: x.get("selection", x.get("disposition")) for x in jv["files"]}
    return entries, m, jd, sources, jsrc
A, B = sys.argv[1], sys.argv[2]
ea, ma, ja, sa, jsa = side(A); eb, mb, jb, sb, jsb = side(B)
out = {"from": A, "to": B, "M_sources_to": sb, "JI_sources_to": jsb}
pa, pb = set(ma) | set(ja), set(mb) | set(jb)
def rec(p, m, j): return {"path": p, "M": m.get(p), "JI": j.get(p)}
out["added"] = [rec(p, mb, jb) for p in sorted(pb - pa)]
out["removed"] = [rec(p, ma, ja) for p in sorted(pa - pb)]
out["changed"] = [{"path": p, "M": [ma.get(p), mb.get(p)], "JI": [ja.get(p), jb.get(p)]} for p in sorted(pa & pb) if ma.get(p) != mb.get(p) or ja.get(p) != jb.get(p)]
out["counts"] = {"added": len(out["added"]), "removed": len(out["removed"]), "changed": len(out["changed"]), "records_from": len(pa), "records_to": len(pb)}
print(json.dumps(out, indent=1, ensure_ascii=False))
