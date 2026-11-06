"""P/08 versioned-door metadata of the existing core part; no new KIT_PARTS (ADR-0125, ADR-0127).

Only the closed TSV columns, OpenAPI operations/headers/captures and req anchors are read. The ordinary core
still resolves the selected family row, computes member parts, judges conditions and supplies result indexes.
"""
import hashlib
import re
import sys
from pathlib import Path

import lesson
from gen_checks import gofmt, go_str
from gen_door_lesson import Docs, GenError as DoorError, METHODS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
L = lesson.CURRENT
COLUMNS = ["method", "path", "row", "revision", "etag", "if_match", "absent_revision", "norm"]
FORM = "Platform/08-domain/forms/versioned-doors.tsv"
API = "Platform/08-domain/spec/08-domain.api.openapi.yaml"
JUDGE = HERE / "test_gen_versioned_doors.py"
PLACE = re.compile(r"<([a-z][a-z0-9_]*)>")
ANCHOR = re.compile(r"P/08(?:\.[0-9]+)?-R[0-9]{3}")


class GenError(Exception):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inputs(root=ROOT):
    root = Path(root)
    form, api = root / FORM, root / API
    if not form.is_file():
        raise GenError(f"no {FORM}: the P/08 core metadata form must be published first")
    norms = sorted((root / "Platform/08-domain/spec").glob("*.norms.md"))
    anchors = {a for p in norms for a in re.findall(r"<!-- req: (P/08(?:\.[0-9]+)?-R[0-9]{3}) -->", p.read_text())}
    try:
        docs = Docs(api)
        ops, needed = {}, set()
        for path, item in docs.doc.get("paths", {}).items():
            item, base = docs.deref(item, api)
            for method in METHODS:
                if method not in item:
                    continue
                op, op_base = docs.deref(item[method], base)
                captures, if_match = set(), False
                for value in item.get("parameters", []) + op.get("parameters", []):
                    p, _ = docs.deref(value, op_base)
                    if p.get("in") == "path":
                        captures.add(p["name"])
                    if p.get("in") == "header" and p.get("name", "").lower() == "if-match":
                        if_match = True
                etag = False
                for code, value in op.get("responses", {}).items():
                    response, _ = docs.deref(value, op_base)
                    if re.fullmatch(r"2[0-9Xx]{2}", str(code)) and any(
                            h.lower() == "etag" for h in response.get("headers", {})):
                        etag = True
                key = (method.upper(), path)
                ops[key] = {"captures": captures, "etag": etag, "if_match": if_match}
                if etag or if_match:
                    needed.add(key)
        if ("POST", "/domain/batch") in ops:
            needed.add(("POST", "/domain/batch"))
    except (DoorError, OSError, KeyError, TypeError) as exc:
        raise GenError(f"{API}: {exc}") from None
    if not needed:
        raise GenError(f"{API}: no versioned operations in the P/08 OpenAPI")
    lines = [(n, s) for n, s in enumerate(form.read_text(encoding="utf-8").split("\n"), 1)
             if s and not s.startswith("#")]
    if not lines or lines[0][1].split("\t") != COLUMNS:
        raise GenError(f"{FORM}: header must be {'<TAB>'.join(COLUMNS)}")
    rows, seen = [], set()
    for n, text in lines[1:]:
        cells = text.split("\t")
        def bad(message):
            raise GenError(f"{FORM}:{n}: {message}")
        if len(cells) != len(COLUMNS):
            bad(f"{len(cells)} cells, expected {len(COLUMNS)}")
        r = dict(zip(COLUMNS, cells))
        key = r["method"], r["path"]
        if key in seen:
            bad(f"duplicate operation {key}")
        if key not in ops:
            bad(f"not an OpenAPI operation: {key}")
        seen.add(key)
        if r["revision"] not in ("doc.rev", "revision", "rev", "-"):
            bad("revision must be doc.rev|revision|rev|-")
        if r["etag"] not in ("true", "false"):
            bad("etag must be true|false")
        if (r["etag"] == "true") != ops[key]["etag"]:
            bad("etag differs from the OpenAPI success headers")
        if r["if_match"] not in ("optional", "optional-index", "ignored", "base-rev"):
            bad("if_match must be optional|optional-index|ignored|base-rev")
        if r["if_match"] != "ignored" and not ops[key]["if_match"]:
            bad("If-Match is not declared in OpenAPI")
        if r["if_match"] == "ignored" and ops[key]["if_match"]:
            bad("ignored requires no declared If-Match in OpenAPI")
        if r["absent_revision"] not in ("0", "-"):
            bad("absent_revision must be 0|-")
        if r["if_match"] == "optional-index" and r["absent_revision"] != "-":
            bad("optional-index requires absent_revision=-")
        if r["revision"] == "-" and (r["etag"] != "false" or r["if_match"] not in ("optional-index", "ignored")):
            bad("revision=- requires etag=false and if_match=optional-index|ignored")
        norm = r["norm"].split(",")
        if len(set(norm)) != len(norm) or any(not ANCHOR.fullmatch(a) or a not in anchors for a in norm):
            bad("norm must be a comma-separated list of distinct existing P/08 req anchors")
        if r["if_match"] == "base-rev" and "P/08.0-R006" not in norm:
            bad("base-rev requires P/08.0-R006")
        row = r["row"]
        if row in ("-", "writes[]"):
            r["kind"] = "NoVersionRow" if row == "-" else "BatchVersionRows"
            r["template"] = ""
        else:
            parts = row.split("/")
            if any(not re.fullmatch(r"[a-z0-9][a-z0-9_-]*|<[a-z][a-z0-9_]*>", p) for p in parts):
                bad("row is not a literal/template key, - or writes[]")
            places = set(PLACE.findall(row))
            if places - ops[key]["captures"] - {"part"}:
                bad(f"row placeholders are not path captures: {sorted(places - ops[key]['captures'] - {'part'})}")
            if "part" in places and row != "domain/member-rows/<part>":
                bad("<part> is only the core-computed member-list shard")
            r["kind"], r["template"] = "SelectedVersionRow", row
        if (row == "writes[]") != (key == ("POST", "/domain/batch")):
            bad("writes[] is the per-write batch selector, not a store key")
        r["norms"] = norm
        rows.append(r)
    if needed != seen:
        raise GenError(f"{FORM}: operation coverage differs: missing {sorted(needed - seen)}, extra {sorted(seen - needed)}")
    return rows, [form] + sorted(docs.cache) + norms


HEAD = '''// Code generated by tools/normgen/gen_versioned_doors.py; DO NOT EDIT.
// Package coreadapter — versioned-door metadata for the ordinary P/08 core.
package coreadapter

// VersionRowKind keeps creation, a selected row and the individual writes of a batch distinct.
type VersionRowKind string
const (
    NoVersionRow VersionRowKind = "none"
    SelectedVersionRow VersionRowKind = "selected"
    BatchVersionRows VersionRowKind = "writes"
)
type RevisionField string
const (
    DocumentRevision RevisionField = "doc.rev"
    RowRevision RevisionField = "revision"
    RevField RevisionField = "rev"
    NoRevision RevisionField = "-"
)
type IfMatchMode string
const (
    OptionalIfMatch IfMatchMode = "optional"
    IgnoredIfMatch IfMatchMode = "ignored"
    BaseRevisionIfMatch IfMatchMode = "base-rev"
    OptionalIndexIfMatch IfMatchMode = "optional-index"
)

// VersionedDoor is metadata, not a store procedure. A selected RowTemplate uses path captures; <part> is
// computed by the ordinary core, never a new path/environment parameter. Empty RowTemplate is not a key.
// ETag means the quoted RESULT INDEX, not the revision, including creation and member deletion.
// BaseRevisionIfMatch gives If-Match priority, falls back to base_rev and preserves the R006 incompatibility refusal.
// OptionalIndexIfMatch names an optional result-index condition, with no absent logical revision default.
// NoRevision means no logical revision field; it is distinct from the NoVersionRow creation selector.
// AbsentRevisionZero applies only to a CONFIRMED absent selected row (per write for BatchVersionRows).
// Unknown/unreadable reads, guards, identity, repeat memory and condition ordering remain the core's procedure.
type VersionedDoor struct {
    Method, Path string
    RowKind VersionRowKind
    RowTemplate string
    Revision RevisionField
    ETag bool
    IfMatch IfMatchMode
    AbsentRevisionZero bool
    Norms []string
}
'''

TAIL = '''
func copyVersionedDoor(d VersionedDoor) VersionedDoor {
    d.Norms = append([]string{}, d.Norms...)
    return d
}
// VersionedDoors returns independent metadata values in form order.
func VersionedDoors() []VersionedDoor {
    out := make([]VersionedDoor, len(versionedDoors))
    for i, d := range versionedDoors { out[i] = copyVersionedDoor(d) }
    return out
}
// VersionedDoorFor takes the selected OpenAPI path TEMPLATE, not an unparsed request URL.
func VersionedDoorFor(method, pathTemplate string) (VersionedDoor, bool) {
    for _, d := range versionedDoors {
        if d.Method == method && d.Path == pathTemplate { return copyVersionedDoor(d), true }
    }
    return VersionedDoor{}, false
}
'''


def render(root=ROOT, lesson_key=None):
    if (lesson_key or L.key) != "08-domain":
        raise GenError("versioned-door core metadata is declared only for lesson 08-domain")
    rows, sources = inputs(root)
    head = HEAD.split("package coreadapter", 1)
    text = head[0] + "".join(f"// {p.relative_to(root)} sha256 {sha(p)}\n" for p in sources)
    text += "package coreadapter" + head[1] + "\nvar versionedDoors = []VersionedDoor{\n"
    revisions = {"doc.rev": "DocumentRevision", "revision": "RowRevision", "rev": "RevField", "-": "NoRevision"}
    modes = {"optional": "OptionalIfMatch", "ignored": "IgnoredIfMatch", "base-rev": "BaseRevisionIfMatch",
             "optional-index": "OptionalIndexIfMatch"}
    for r in rows:
        text += (f"{{Method:{go_str(r['method'])}, Path:{go_str(r['path'])}, RowKind:{r['kind']}, "
                 f"RowTemplate:{go_str(r['template'])}, Revision:{revisions[r['revision']]}, "
                 f"ETag:{r['etag']}, IfMatch:{modes[r['if_match']]}, AbsentRevisionZero:{str(r['absent_revision']=='0').lower()}, "
                 f"Norms:[]string{{{','.join(go_str(n) for n in r['norms'])}}}}},\n")
    return {"coreadapter/versioned_doors.go": gofmt(text + "}\n" + TAIL)}


def generate(out=L.out, root=ROOT, lesson_key=None):
    files = render(root, lesson_key)
    gdir = Path(out) / "core"
    for rel, text in files.items():
        path = gdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return gdir


def kit_files(module, out=L.out):
    files = []
    for rel, text in render().items():
        path = Path(out) / "core" / rel
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            raise GenError(f"{path} is stale: run gen_versioned_doors.py --lesson 08-domain")
        sub, name = rel.rsplit("/", 1)
        files.append((sub, name, path.read_bytes(), "generated", L.output_source(path, out), False))
    return files


def provenance():
    import tsv_input

    _, sources = inputs()
    def entry(p):
        return {"path": str(p.relative_to(ROOT)), "sha256": sha(p)}
    sources = list(dict.fromkeys(p for src in sources for p in
                                (tsv_input.source_files(src, root=ROOT) if src.suffix == ".tsv" else [src])))
    return {"form": [entry(p) for p in sources], "generator": entry(Path(__file__).resolve()),
            "generators": [entry(Path(__file__).resolve()), entry(Path(tsv_input.__file__))],
            "handwritten": [entry(HERE / "yamlsub.py"), entry(HERE / "gen_door_lesson.py"), entry(HERE / "gen_checks.py")],
            "judge": entry(JUDGE)}


KIT_MD = '''
## Part `core`: P/08 versioned-door metadata

`{module}/internal/coreadapter/versioned_doors.go` is generated and closed. `VersionedDoors()` lists the metadata;
`VersionedDoorFor(method, pathTemplate)` looks up the already selected OpenAPI operation. The ordinary core owns
the procedure: read/resolve the family row, compute `<part>`, compare conditions, keep repeat memory and write.
`NoVersionRow`, `SelectedVersionRow` and `BatchVersionRows` are different selectors; empty RowTemplate is never a key.
Revision names the logical field. ETag=true means the quoted result index, including creation/member deletion;
false means no success ETag. `BaseRevisionIfMatch` retains R006 priority/fallback/incompatibility refusals.
`NoRevision` denotes no logical revision field (`-`), independently of the row selector. `OptionalIndexIfMatch`
denotes an optional result-index condition and no absent revision default; neither token supplies a store procedure.
`AbsentRevisionZero` supplies 0 only for confirmed absence, per write for a batch; unknown reads never become 0.
This is the existing `core` part's metadata; it does not supply a P/08 core implementation or a new process input.
'''


def main(argv):
    try:
        print(generate(Path(argv[1]) if len(argv) > 1 else L.out))
    except (GenError, OSError) as exc:
        print(f"gen_versioned_doors: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
