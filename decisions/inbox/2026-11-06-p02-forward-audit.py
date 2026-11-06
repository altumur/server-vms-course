"""Reproduce the source-only P02 forward basis; no generator/output writes.

Run from the course root with the lesson-spec Python environment. The fixed
merge commit is the source input; this audit and its reports are later evidence.
Physical TSV records use LF/TAB, including deliberately unusual payload bytes.
"""
from collections import Counter
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import subprocess
import sys

PUBLISHED = "5a355d41ba49239726e89997609b135db5268d73"
AUTHOR = "828e2583fe90d8f959bdf7d4088132f5ecb96699"
SOURCE = "294825d2490765884f6a1186410ccc7dafd74f33"
BASE = "9093e65320c63efb0733c7e2477b8141ab91b14b"
MAP = Path("decisions/inbox/2026-11-06-p02-forward-basis.tsv")
REPORT = Path("decisions/inbox/2026-11-06-p02-forward-proof.json")
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "skills/lesson-spec/scripts"))
import en_mirror
import source_cells


def git(*args):
    return subprocess.check_output(["git", *args])


def tree(ref):
    result = {}
    for entry in git("ls-tree", "-rz", "--full-tree", ref).split(b"\0"):
        if entry:
            meta, path = entry.split(b"\t", 1)
            mode, kind, oid = meta.decode().split()
            assert kind == "blob", (ref, path, kind)
            result[path.decode()] = (mode, oid)
    return result


def get(ref, path):
    return git("show", ref + ":" + path)


def digest(data):
    return sha256(data).hexdigest()


published, author, source = (tree(ref) for ref in (PUBLISHED, AUTHOR, SOURCE))
assert git("show", "-s", "--format=%P", SOURCE).decode().strip().split() == [PUBLISHED, AUTHOR]
assert git("merge-base", PUBLISHED, AUTHOR).decode().strip() == BASE
reviews = ["dc76e8f33", "29f619228", "c58743b5"]
for ref in reviews:
    assert subprocess.run(["git", "merge-base", "--is-ancestor", ref, SOURCE]).returncode == 0
assert subprocess.run(["git", "merge-base", "--is-ancestor", "8f2873279bfc264911a1f296ec96fec89139b7b0", SOURCE]).returncode == 1

paths = sorted(set(published) | set(author) | set(source))
changed = [p for p in paths if published.get(p) != source.get(p)]
assert len(changed) == 756
assert all(p == "decisions/adr-norms.tsv" or source.get(p) == author.get(p) for p in changed)
assert not any(p.startswith(("tools/", "Platform/01-store/", "Platform/03-worker/", "Platform/04-controller/", "VMS/")) for p in changed)
assert all((ROOT / p).read_bytes() == get(SOURCE, p) for p in changed)

identity = {}
for prefix, ref, expected in [
    ("Platform/02-installer/", AUTHOR, author),
    ("Platform/01-store/", PUBLISHED, published),
    ("Platform/03-worker/", PUBLISHED, published),
    ("Platform/04-controller/", PUBLISHED, published),
    ("Platform/09-agent/", PUBLISHED, published),
    ("tools/", PUBLISHED, published),
    ("VMS/", PUBLISHED, published),
]:
    selected = {p: v for p, v in source.items() if p.startswith(prefix)}
    assert selected == {p: v for p, v in expected.items() if p.startswith(prefix)}, prefix
    identity[prefix] = {"basis": ref, "files": len(selected), "git_entries_sha256": digest(json.dumps(selected, sort_keys=True).encode())}

# Both ledger deltas are append-only. Preserve every published byte and append
# the 21 exact author rows, without replacing the published G09/root records.
ledger = "decisions/adr-norms.tsv"
base_rows = get(BASE, ledger).decode().split("\n")
author_rows = get(AUTHOR, ledger).decode().split("\n")
extra = [r for r in author_rows if r and r not in base_rows]
assert len(extra) == 21 and all(r in author_rows for r in base_rows if r)
expected = get(PUBLISHED, ledger).rstrip(b"\n") + b"\n" + ("\n".join(extra) + "\n").encode()
assert get(SOURCE, ledger) == expected

# The forward map covers every path whose identity differs among the two
# inputs and the merged source, including inherited published helpers/outputs.
# Listing an inherited output is provenance only; its bytes are never rewritten.
mapped = [p for p in paths if not (published.get(p) == author.get(p) == source.get(p))]
oids = sorted({v[1] for t in (published, author, source) for p in mapped if (v := t.get(p))})
stream = BytesIO(subprocess.check_output(["git", "cat-file", "--batch"], input=("\n".join(oids) + "\n").encode()))
hashes = {}
for oid in oids:
    header = stream.readline().decode().split()
    assert header[0] == oid and header[1] == "blob"
    hashes[oid] = digest(stream.read(int(header[2])))
    assert stream.read(1) == b"\n"
header = ["path", "basis", "published_mode_blob", "author_mode_blob", "source_mode_blob", "published_sha256", "author_sha256", "source_sha256"]
map_rows = []
classes = Counter()
for p in mapped:
    a, b, c = (t.get(p) for t in (published, author, source))
    basis = "published5a" if c == a else "author828" if c == b else "append-both-ledger"
    assert basis != "append-both-ledger" or p == ledger
    classes[basis] += 1
    meta = [" ".join(v) if v else "-" for v in (a, b, c)]
    sha = [hashes[v[1]] if v else "-" for v in (a, b, c)]
    map_rows.append([p, basis, *meta, *sha])
MAP.write_text("# Exact source forward basis; fixed source commit " + SOURCE + "\n" + "\t".join(header) + "\n" + "".join("\t".join(row) + "\n" for row in map_rows), encoding="utf-8")

# Existing language map and proof are frozen, including the complete P02
# source, 947-case roster, 220 canonical expectations and N/English edits.
language_map = "decisions/inbox/2026-11-06-adr0121-p02-source-map.tsv"
preservation = "decisions/inbox/2026-11-06-adr0121-p02-preservation.json"
assert digest(get(SOURCE, language_map)) == "4ce59e1cc659fbf30f94931c629ed63fc320006e366651f6764bea411520f91d"
assert get(SOURCE, preservation) == get(AUTHOR, preservation)
frozen = json.loads(get(SOURCE, preservation))
assert frozen["corpus_count"] == 947 and frozen["verdicts"] == {"ok": 203, "refused": 744}
assert frozen["canonical_count"] == 220
registry = "skills/lesson-spec/scripts/v7/sections-meaning-deltas.tsv"
assert source[registry] == published[registry]
assert subprocess.run(["git", "merge-base", "--is-ancestor", "579641982", SOURCE]).returncode == 0
assert source["Platform/common/data/catalog.tsv"] == published["Platform/common/data/catalog.tsv"]
assert source["skills/lesson-spec/scripts/source_cells.py"] == published["skills/lesson-spec/scripts/source_cells.py"]
for p in ("skills/lesson-spec/scripts/en_mirror.py", "skills/lesson-spec/scripts/v7/test_spec.py", "skills/lesson-spec/scripts/v7/vectors.py"):
    assert source[p] == author[p]

proof_rows = [r.split("\t") for r in (ROOT / "Platform/common/data/cell-json-sha256.tsv").read_bytes().decode().split("\n") if r and not r.startswith("#")][1:]
assert len(proof_rows) == 715
tables = sorted({r[0] for r in proof_rows})
assert len(tables) == 8
forms = source_cells.wire_headers(ROOT)
byte_proof = []
for table in tables:
    columns, positional = forms.get(Path(table), (None, False))
    names, decoded, errors = source_cells.table((ROOT / table).read_bytes().decode(), columns, positional)
    assert not errors, (table, errors)
    before_ref = "2ebffcaa59ab7694fb90d7f6d29410b44adcd619" if table.startswith("Platform/common/") else "cac140972cfc4e949e2859adbe4afde10fa3c7ff" if table.startswith("Platform/01-store/") else frozen["baseline"]
    old = [(n, line.split("\t")) for n, line in enumerate(get(before_ref, table).decode().split("\n"), 1) if line and not line.startswith("#")]
    if not positional:
        _, cols = old.pop(0)
    else:
        cols = columns
    before = [(n, dict(zip(cols, cells))) for n, cells in old]
    assert len(before) == len(decoded), table
    for (old_line, a), (new_line, b) in zip(before, decoded):
        for name in names:
            assert a[name].encode() == b[name].encode(), (table, new_line, name)
            byte_proof.append({"table": table, "before": before_ref, "before_line": old_line, "line": new_line, "column": name, "before_sha256": digest(a[name].encode()), "decoded_sha256": digest(b[name].encode())})
assert len(byte_proof) == 715
exec_proof = [r for r in byte_proof if "/vectors/exec/" in r["table"]]
assert len(exec_proof) == 19
assert all(r["line"] == r["before_line"] + 1 for r in exec_proof)
source_errors = source_cells.errors(ROOT, [p for p in en_mirror.english_sources(ROOT, ("Platform/", "VMS/")) if p.suffix == ".tsv"])
assert not source_errors, source_errors
pair_errors = []
pair_count = 0
for ru, en in en_mirror.pairs(ROOT):
    if "/02-installer/" in str(en) and ru.is_file():
        pair_count += 1
        pair_errors.extend(en_mirror.compare(ru.read_text(), en.read_text(), ru, en, ROOT))
assert not pair_errors, pair_errors
language_errors = en_mirror.full_english_errors(ROOT, ("Platform/02-installer/",))
assert not language_errors, language_errors

report = {
    "published": PUBLISHED, "author": AUTHOR, "source_merge": SOURCE,
    "merge_base": BASE, "review_ancestors": reviews,
    "source8f_and_p04_absent": True, "source_delta_files": len(changed),
    "forward_map": str(MAP), "forward_map_sha256": digest(MAP.read_bytes()),
    "forward_map_rows": len(map_rows), "forward_map_basis": classes,
    "identity_groups": identity, "ledger_p02_appended_rows": len(extra),
    "p02_language_map_sha256": digest(get(SOURCE, language_map)),
    "p02_preservation_identical_to_author": True,
    "corpus": {"cases": 947, "ok": 203, "refused": 744, "all_source_bytes_identical_to_author": True},
    "canonical": {"cases": 220, "all_source_bytes_identical_to_author": True},
    "byte_proof_cells": len(byte_proof), "byte_proof_tables": len(tables),
    "exec_cells": exec_proof, "byte_proof": byte_proof,
    "p02_mirror_pairs": pair_count, "mirror_errors": [], "english_errors": [], "source_cells_errors": [],
    "registry579_and_published_common_helpers_retained": True,
    "no_runtime_or_output_regeneration_claim": True,
}
REPORT.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: report[k] for k in ("source_merge", "source_delta_files", "forward_map_sha256", "forward_map_rows", "forward_map_basis", "byte_proof_cells", "byte_proof_tables", "p02_mirror_pairs")}, indent=2))
