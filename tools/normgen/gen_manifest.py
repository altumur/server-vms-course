"""Generate the closed P/02 loader part: strict P/02.1 manifest loading and P/02.2 canonical view (Architect, 2026-11-05; ADR-0125 addendum(5)).

  python3 tools/normgen/gen_manifest.py [<out>]
Always lesson02-installer; default out/p02. Architect optionA pins go.yaml.in/yaml/v3, santhosh-tekuri/jsonschema/v6 and cel-go through common/versions/go.mod. Embed export form bytes as data and validate their compatibility with manifestrt/go, based on the course V7 Go stack.

Validate scalars.tsv headers/kinds/limits; known schema x-* keywords and exact layers.tsv correspondence; translate x-complement-of to standard JSON Schema while x-integer adds nothing beyond manifest type:integer. Preserve informational x-owner/x-default-text/x-class. Relations allow exactly strings and two-var-comprehensions extensions and depth/template/text overloads; D8 rewrites double( to double(dyn(.

Emit runtime text/value/form/relations/view/manifest.go, embedded forms/ and forms.go, module requirements pinned by versions/go.mod and copied go.sum. test_gen_manifest.py runs947 verdicts with classes, 220canonical cases, 402yaml-suite cases and mutants."""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import lesson  # noqa: E402
L = lesson.get("02-installer")              # Loader always belongs to lesson02 regardless of the selected lesson.

DEFAULT_OUT = L.out
RUNTIME = HERE / "manifestrt/go"
RUNTIME_FILES = ("text.go", "value.go", "form.go", "relations.go", "view.go", "manifest.go")
SPEC = L.path("spec")
SCHEMA = SPEC / "02.1-installer.schema.json"
RELATIONS = SPEC / "02.1-installer.relations.json"
LAYERS = SPEC / "02.1-installer.layers.tsv"
SCALARS = SPEC / "02.1-installer.scalars.tsv"
VERSIONS = ROOT / "Platform/common/versions"
JUDGE = HERE / "test_gen_manifest.py"
FORMS = {"forms/schema.json": SCHEMA, "forms/relations.json": RELATIONS, "forms/scalars.tsv": SCALARS}
LAYER_WORDS = {"x-integer-place", "x-opaque", "x-ordered", "x-complement-of", "x-integer"}
REFERENCE_WORDS = {"x-owner", "x-default-text", "x-class"}
SCALAR_KINDS = {"null", "true", "false", "int", "float", "nonfinite", "string"}
EXTENSIONS = ["strings", "two-var-comprehensions"]
FUNCTIONS = {"depth": [("depth_dyn", ["dyn"], "int")],
             "template": [("template_dyn_list_list_bool", ["dyn", "list", "list", "bool"], "bool")],
             "text": [("text_list", ["list"], "list")]}
LIBRARIES = ("github.com/google/cel-go", "github.com/santhosh-tekuri/jsonschema/v6", "go.yaml.in/yaml/v3")


class GenError(Exception):
    pass


def rel(p):
    return str(Path(p).relative_to(ROOT))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check_scalars():
    lines = [x for x in SCALARS.read_text(encoding="utf-8").split("\n") if x and not x.startswith("#")]
    if not lines or lines[0].split("\t") != ["kind", "pattern", "norm"]:
        raise GenError(f"{rel(SCALARS)}: header kind<TAB>pattern<TAB>norm")
    limits = set()
    for x in lines[1:]:
        c = x.split("\t")
        if len(c) != 3:
            raise GenError(f"{rel(SCALARS)}: {x!r}: 3 columns")
        if c[0] == "limit":
            m = re.fullmatch(r"(int_max|float_max)=(.+)", c[1])
            if not m:
                raise GenError(f"{rel(SCALARS)}: limit {c[1]!r}")
            limits.add(m[1])
        elif c[0] not in SCALAR_KINDS:
            raise GenError(f"{rel(SCALARS)}: kind {c[0]!r} is outside the runtime ({sorted(SCALAR_KINDS)})")
        else:
            re.compile(c[1])
    if limits != {"int_max", "float_max"}:
        raise GenError(f"{rel(SCALARS)}: limits int_max and float_max")


def schema_words(node, ptr=""):
    if isinstance(node, dict):
        for k, v in node.items():
            if k.startswith("x-"):
                yield ptr, k, v
            yield from schema_words(v, ptr + "/" + k.replace("~", "~0").replace("/", "~1"))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from schema_words(v, f"{ptr}/{i}")


def check_schema():
    doc = json.loads(SCHEMA.read_text(encoding="utf-8"))
    places = set()
    for ptr, k, v in schema_words(doc):
        if k in REFERENCE_WORDS:
            continue
        if k not in LAYER_WORDS:
            raise GenError(f"{rel(SCHEMA)}: {ptr}: word {k} is outside the runtime ({sorted(LAYER_WORDS)})")
        places.add((ptr, k))
    rows = set()
    lines = [x for x in LAYERS.read_text(encoding="utf-8").split("\n") if x and not x.startswith("#")]
    if not lines or lines[0].split("\t") != ["place", "layer", "word", "value"]:
        raise GenError(f"{rel(LAYERS)}: header place<TAB>layer<TAB>word<TAB>value")
    for x in lines[1:]:
        c = x.split("\t")
        if len(c) != 4:
            raise GenError(f"{rel(LAYERS)}: {x!r}: 4 columns")
        rows.add((c[0], c[2]))
    if places != rows:
        raise GenError(f"{rel(LAYERS)} and {rel(SCHEMA)} disagree: only in the schema {sorted(places - rows)[:5]}, "
                       f"only in the table {sorted(rows - places)[:5]}")


def check_relations():
    doc = json.loads(RELATIONS.read_text(encoding="utf-8"))
    env = doc.get("env") or {}
    ext = [e.get("name") for e in env.get("extensions") or []]
    if sorted(ext) != sorted(EXTENSIONS):
        raise GenError(f"{rel(RELATIONS)}: extensions {ext}, the runtime has {EXTENSIONS}")
    if [(v.get("name"), v.get("type_name")) for v in env.get("variables") or []] != [("doc", "dyn")]:
        raise GenError(f"{rel(RELATIONS)}: variables — exactly doc: dyn")
    fns = {}
    for f in env.get("functions") or []:
        fns[f["name"]] = [(o["id"], [a["type_name"] for a in o["args"]], o["return"]["type_name"])
                          for o in f["overloads"]]
    if fns != FUNCTIONS:
        raise GenError(f"{rel(RELATIONS)}: functions {fns}, the runtime has {FUNCTIONS} (LAYERS § 5, layer 7)")
    nos = set()
    for r in doc.get("rows") or []:
        if not isinstance(r.get("no"), int) or r["no"] in nos or not r.get("cel"):
            raise GenError(f"{rel(RELATIONS)}: row {r.get('no')!r}: a unique number and cel")
        nos.add(r["no"])
        if re.search(r"\bdouble\((?!dyn\()", r["cel"]):
            raise GenError(f"{rel(RELATIONS)}: row {r['no']}: double(…) without dyn(…) — the workaround of D8 "
                           f"(Platform/common/versions/DEFECTS.md; cel-go v0.26.1: no such overload double(int))")
    if not nos:
        raise GenError(f"{rel(RELATIONS)}: no rows")


def requires():
    text = (VERSIONS / "go.mod").read_text(encoding="utf-8")
    blocks = re.findall(r"^require \((.*?)^\)", text, re.S | re.M)
    if not blocks:
        raise GenError(f"{rel(VERSIONS / 'go.mod')}: no require")
    got = {ln.split()[0] for b in blocks for ln in b.strip().split("\n") if ln.strip()}
    for lib in LIBRARIES:
        if lib not in got:
            raise GenError(f"{rel(VERSIONS / 'go.mod')}: {lib} is not pinned")
    return "".join(f"\nrequire ({b.rstrip()}\n)\n" for b in blocks)


FORMS_GO = '''// Code generated by tools/normgen/gen_manifest.py; DO NOT EDIT.
// The standard files of P/02.1, byte for byte (Platform/02-installer/spec):
%(sources)s
package manifest

import _ "embed"

//go:embed forms/schema.json
var schemaJSON string

//go:embed forms/relations.json
var relationsJSON string

//go:embed forms/scalars.tsv
var scalarsTSV string
'''


def render():
    """Return {output-go-relative path: bytes}."""
    check_scalars()
    check_schema()
    check_relations()
    files = {}
    for name in RUNTIME_FILES:
        files[f"manifest/{name}"] = (RUNTIME / name).read_bytes()
    for dst, src in FORMS.items():
        files[f"manifest/{dst}"] = src.read_bytes()
    sources = "".join(f"//   {rel(src)} sha256 {sha(src)}\n" for src in FORMS.values())
    files["manifest/forms.go"] = (FORMS_GO % {"sources": sources}).encode("utf-8")
    return files


def go_mod(out):
    """Use versions/go.mod with the lesson module name (go1.22.0/toolchain go1.22.10 avoids Go rewriting it) and copy versions/go.sum."""
    requires()
    text = (VERSIONS / "go.mod").read_text(encoding="utf-8")
    text = re.sub(r"^module .*$", f"module {L.go_module}", text, count=1, flags=re.M)
    return text.encode("utf-8"), (VERSIONS / "go.sum").read_bytes()


def generate(out=DEFAULT_OUT):
    if L.key != "02-installer":
        raise GenError("gen_manifest: the loader of P/02.1 is the part of the lesson 02-installer")
    gdir = Path(out) / "go"
    if (gdir / "manifest").exists():
        shutil.rmtree(gdir / "manifest")
    for relp, data in render().items():
        (gdir / relp).parent.mkdir(parents=True, exist_ok=True)
        (gdir / relp).write_bytes(data)
    mod, s = go_mod(out)
    (gdir / "go.mod").write_bytes(mod)
    (gdir / "go.sum").write_bytes(s)
    return gdir / "manifest"


def kit_files(module, out=DEFAULT_OUT):
    """Return [(internal directory, name, bytes, origin, source, editable)]; stale output raises GenError."""
    files = []
    for relp, data in sorted(render().items()):
        kept = Path(out) / "go" / relp
        if not kept.is_file() or kept.read_bytes() != data:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_manifest.py")
        sub, name = relp.rsplit("/", 1)
        files.append((sub, name, data, "generated", L.output_source(kept, out), False))
    return files


def provenance():
    import tsv_input

    def entry(path):
        return {"path": rel(path), "sha256": sha(path)}
    forms = [SCHEMA, RELATIONS, LAYERS, SCALARS, VERSIONS / "go.mod", VERSIONS / "go.sum"]
    forms = list(dict.fromkeys(p for src in forms for p in
                              (tsv_input.source_files(src, root=ROOT) if src.suffix == ".tsv" else [src])))
    return {"form": [entry(p) for p in forms],
            "generator": entry(Path(__file__).resolve()),
            "generators": [entry(Path(__file__).resolve()), entry(Path(tsv_input.__file__))],
            "handwritten": [entry(RUNTIME / n) for n in RUNTIME_FILES], "judge": entry(JUDGE)}


# Loader wires YOURS scaffolds for other parts to the manifest package.
# They remain implementation-owned: install once without overwriting, following build_kit --seed rules.
WIRED = {
    ("lessonadapter", "load.go"): '''// Generated by tools/normgen/gen_cmdtests.py, wired by the part loader (tools/normgen/gen_manifest.py). YOURS from
// here: the kit puts this file once and never overwrites it.

package lessonadapter

import "{module}/internal/manifest"

// Load runs the regular loader of P/02.1 N3 (the part loader: internal/manifest — text → form → relations) on exactly
// the bytes of one manifest file; the refusal names the file, its Class is the layer.
func Load(source string, text []byte) Loaded {
	m, r := manifest.Load(source, text)
	if r != nil {
		return Loaded{Class: r.Class, Message: r.Message}
	}
	return Loaded{OK: true, Name: m.Name}
}
''',
    ("vectoradapter", "canonical.go"): '''// Generated by tools/normgen/gen_vectors.py, wired by the part loader (tools/normgen/gen_manifest.py). YOURS from
// here: the kit puts this file once and never overwrites it.

package vectoradapter

import "{module}/internal/manifest"

// Canonical — 02-installer/canonical cases.tsv (stand:canonical): the JCS bytes of the canonical view (P/02.2 N1.1)
// of the manifest file (internal/manifest); a refusal of the load — code 2 (the view is not built).
func Canonical(source string, text []byte) Answer {
	b, r := manifest.Canonical(source, text)
	if r != nil {
		return Answer{Code: 2, Value: r.Message}
	}
	return Answer{Raw: b}
}
''',
    ("vectoradapter", "yamlsuite.go"): '''// Generated by tools/normgen/gen_vectors.py, wired by the part loader (tools/normgen/gen_manifest.py). YOURS from
// here: the kit puts this file once and never overwrites it.

package vectoradapter

import "{module}/internal/manifest"

// YamlSuite — common/yaml-suite expect.tsv: layer 1 of the manifest text (internal/manifest.Layer1) on in.yaml:
// {layer1: "ok" | "refused", rule} — only layer1 is compared.
func YamlSuite(table string, cells map[string]string, files map[string][]byte) Answer {
	rule, _, refused := manifest.Layer1(files["in.yaml"])
	if refused {
		return Answer{Value: map[string]any{"layer1": "refused", "rule": rule}}
	}
	return Answer{Value: map[string]any{"layer1": "ok"}}
}
''',
}


def wired(module):
    """Return {(internal directory, filename): bytes} for wired scaffolds."""
    return {k: v.replace("{module}", module).encode("utf-8") for k, v in WIRED.items()}


def vendor(module):
    """Return module-root files: go.mod, go.sum and vendored pinned dependencies from the local module cache without network; missing modules raise GenError."""
    import subprocess
    import tempfile
    mod = re.sub(r"^module .*$", f"module {module}", (VERSIONS / "go.mod").read_text(encoding="utf-8"), count=1,
                 flags=re.M).encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="loader-vendor-") as t:
        t = Path(t)
        for relp, data in render().items():
            (t / "internal" / relp).parent.mkdir(parents=True, exist_ok=True)
            (t / "internal" / relp).write_bytes(data)
        (t / "go.mod").write_bytes(mod)
        (t / "go.sum").write_bytes((VERSIONS / "go.sum").read_bytes())
        env = dict(__import__("os").environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off")
        done = subprocess.run(["go", "mod", "vendor"], cwd=t, capture_output=True, text=True, env=env)
        if done.returncode:
            raise GenError(f"go mod vendor: {done.stderr.strip()[-600:]}")
        out = [("go.mod", (t / "go.mod").read_bytes()), ("go.sum", (t / "go.sum").read_bytes())]
        for f in sorted((t / "vendor").rglob("*")):
            if f.is_file():
                out.append((str(f.relative_to(t)), f.read_bytes()))
    if out[0][1] != mod:
        raise GenError("go mod vendor rewrote go.mod: the pinned versions are not tidy")
    return out


KIT_MD = """
## Part `loader`: the strict loader of the manifest and its canonical view (generated, closed)

| File | Origin |
|---|---|
| `{module}/internal/manifest/` | kit (closed): `Load`, `Canonical`, `Layer1` — P/02.1 N3 load and P/02.2 N3 build view |
| `{module}/internal/manifest/forms/` | the standard files of P/02.1 byte for byte (schema, relations, scalars) |
| `go.mod`, `go.sum`, `vendor/` | the pinned libraries of `Platform/common/versions` (P/02.1 «Implementation decides» item 1): go.yaml.in/yaml/v3 v3.0.5, santhosh-tekuri/jsonschema/v6 v6.0.2, cel-go v0.26.1 — vendored, no network |
| `internal/lessonadapter/load.go`, `internal/vectoradapter/canonical.go`, `yamlsuite.go` | **yours**, already wired to `manifest` |

The loader is the whole of P/02.1 N3 `load`: layer 1 (the pinned YAML parser and the thin check of N1.1, with the
workarounds of DEFECTS.md), the form (JSON Schema 2020-12 and the layer words), the relations (the CEL rows of
`relations.json` and the functions depth, template, text) — in the normative order text → form → relations. A refusal has
`Class` (`text` | `form` | `relations`) and a `Message` that names the file; the path is a hint (N4).

```go
func Load(source string, data []byte) (*manifest.Manifest, *manifest.Refusal)   // Manifest{Name, Tree}
func Canonical(source string, data []byte) ([]byte, *manifest.Refusal)       // JCS bytes of the view (P/02.2 N1.1)
func Layer1(data []byte) (rule, message string, refused bool)                  // layer 1 alone (yaml-suite)
```

Use the same `manifest.Load` wherever your installer reads a manifest (`manifest put`, the catalogue): the
catalogue checks over several manifests (P/02.1 N3 `load_catalogue`) are **yours** (`lessonadapter.LoadCatalogue`).
Keep `go.mod` with these requirements; if you add a module, run `go mod vendor` again.
"""


def kit_md():
    return KIT_MD


def main(argv):
    out = Path(argv[0]) if argv else DEFAULT_OUT
    try:
        print(generate(out))
    except GenError as exc:
        print(f"gen_manifest: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
