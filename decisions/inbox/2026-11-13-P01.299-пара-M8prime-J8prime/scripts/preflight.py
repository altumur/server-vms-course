# P01.299 preflight: the pair operator's own pre-write checks on C (P02.52 operator), no output, no authorization.
import sys, os, json, hashlib, collections
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(str(__import__("pathlib").Path(__file__).resolve().parent.parent), "operator"))
import b7_export_pair as b
C = sys.argv[1]; gitdir = sys.argv[2]
fd = b._open_dir(b._canonical(gitdir))
entries = b._source(fd, C)
entries[b.MARKER] = ("100644", None, (C + "\n").encode())
raw, value, sources = b._assemble(entries)
sel = b._classification(entries)          # no unlisted files cut out: refusal here is a stop
cases = b._case_boundary(entries, sel)
assert sel[b.DERIVED] == "model_and_judge"
model = {p: e for p, e in entries.items() if sel[p] == "model_and_judge"}
b._legacy_model_content_guard(model)
by = collections.Counter(p.split("/")[1] for p in model if p.count("/") >= 2)
out = {"task": "P01.299", "C": C, "operator_sha256": hashlib.sha256(open(b.__file__, "rb").read()).hexdigest(),
       "assembled_filter_blob": b._blob_id(raw), "assembled_filter_sha256": hashlib.sha256(raw).hexdigest(),
       "filter_sources": sources, "wire_blob": entries[b.WIRE][1],
       "derived_sha256": hashlib.sha256(entries[b.DERIVED][2]).hexdigest(),
       "J_files": len(entries), "M_files": len(model), "cases_removed": len(cases),
       "M_files_by_top_dir": dict(sorted(by.items())),
       "lexical_guard": "pass", "classification": "pass", "case_boundary": "pass"}
print(json.dumps(out, indent=1, ensure_ascii=False))
