"""Build the P/01 kit (ADR-0083 addendum 86, item 2).

  python tools/normgen/kit/build_kit.py <dst> --module <import-path-to-dst/01-store> [--part <part> ...]
Install checks, jsonstrict, writecheck under <dst>/01-store/internal. checks comes from out/p01-1/go/checks and must match write-checks.tsv; jsonstrict/writecheck come from kit/go with rewritten module imports. Replace closed component directories in full.

Optional parts: flags/refusals/families with form/generator/judge provenance; box requires door, flags, refusals, writecheck; admin requires flags and supplies closed dispatch plus one-time editable command files; vectors supplies tests, command and one-time editable adapters; stagetests requires door and supplies tests/coreadapter with editable Open; door supplies generated apidoor independently of implementation-owned internal/door. launch requires admin and the connected door/flags/stagetests components. Write KIT.md with the model-facing English API and kit.manifest.json with paths, SHA256, line counts and origins.

--export <sha> [--specs <cammeta-specs-repo>] reads Platform from that export and tools/normgen from a clean course HEAD via git archive. Dirty generator code refuses. Regenerate and build in a temporary tree without changing the course. Record clean course/export pins in the manifest and SOURCE.txt.

--seed <tree> preserves implementation code when a cycle overlays the kit: install editable files only when absent or still byte-identical to the previous kit's manifest SHA. Record kept/refreshed files. Other destination content is untouched."""
import argparse
import os
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(HERE.parent))
import gen_tests  # noqa: E402 -- tests part
import gen_flags  # noqa: E402 -- flags part
import gen_refusals  # noqa: E402 -- refusals part
import gen_checks  # noqa: E402 -- writecheck freshness
import gen_door  # noqa: E402 -- door freshness
import gen_launch  # noqa: E402 -- launch part
import gen_core  # noqa: E402 -- core part
import gen_versioned_doors  # noqa: E402 -- P/08 metadata in the existing core part
import gen_families  # noqa: E402 -- families part
import gen_row_writes  # noqa: E402 — P03-only pure constructor overlay in the families part
sys.path.insert(0, str(HERE.parent / "contracts"))
import kitside  # noqa: E402 -- lesson surfaces for contracts adapters
sys.path.insert(0, str(HERE.parent / "contracts/gen"))
import gen_heartbeat  # noqa: E402 -- heartbeat reader's two externally owned families
import gen_admin  # noqa: E402 -- admin part
import gen_box  # noqa: E402 -- box part
import gen_manifest  # noqa: E402 -- P/02 loader part
import gen_cmdtests  # noqa: E402 -- non-HTTP lesson stagetests (P/02)
import gen_policy_machines  # noqa: E402 — closed P/03 policies inside stagetests
import gen_rollout  # noqa: E402 -- P/02 rollout-poll part
import gen_door_lesson  # noqa: E402 -- door for lessons after P/01 (P/06 part 3a)
import gen_machine  # noqa: E402 -- P/03 slot-capture and P/04 slot-fate/slot-release machine parts
import gen_vectors  # noqa: E402 -- vectors for a lesson without a door (P/02)
import lesson  # noqa: E402 -- lesson selection (--lesson, default 01-store; ADR-0125 addendum 5, item 2)
L = lesson.CURRENT
TABLE = L.form("write-checks.tsv")
GENERATED = L.out / "go/checks"
HANDWRITTEN = HERE / "go"
PLACEHOLDER = '"kitmodule/internal/'
MODULE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._~-]*(/[A-Za-z0-9._~-]+)*")

# checks files: (name, origin, repository source). The generator copies runtime.go and prims.go
# from its handwritten sources and generates checks.go from the table.
CHECKS_FILES = [
    ("checks.go", "generated", f"tools/normgen/out/{L.slug}/go/checks/checks.go"),
    ("runtime.go", "handwritten", "tools/normgen/runtime/go/runtime.go"),
    ("prims.go", "handwritten", "tools/normgen/prims/go/prims.go"),
]
KIT_FILES = [
    ("jsonstrict", "jsonstrict.go"),
    ("writecheck", "writecheck.go"),
]
# Door: gen_door.py generates door.go from OpenAPI; runtime.go copies its handwritten runtime.
OPENAPI = L.openapi
DOOR = L.out / "go/apidoor"
DOOR_FILES = [
    ("door.go", "generated", f"tools/normgen/out/{L.slug}/go/apidoor/door.go"),
    ("runtime.go", "handwritten", "tools/normgen/doorrt/go/runtime.go"),
]


class KitError(Exception):
    pass


NORMGEN = ROOT / "tools/normgen"


def entry(path):
    path = Path(path)
    return {"path": str(path.relative_to(ROOT)), "sha256": sha256(path.read_bytes())}


def fresh_check(gen, src, sub, names):
    """Verify all copied output against a fresh generator run (Codex C2). A form SHA alone cannot prove generator, runtime/primitives or out freshness; generation failures and mismatches become KitError."""
    # Preparation recorded exact source/code/runtime inputs and output hashes.
    # Consumption validates that set, never repairs it by calling generate().
    ready = checked_outputs()
    for name in names:
        if not (ready[L.slug] / sub / name).is_file():
            raise KitError(f"prepared {L.slug}/{sub}/{name} is missing")


def checked_outputs():
    try:
        value = lesson.output_manifest()
        ready = lesson.ready_outputs(profiles=tuple(value["profiles"]))
    except (lesson.LessonError, OSError) as exc:
        raise KitError(str(exc)) from None
    if L.slug not in ready:
        raise KitError(f"prepared set does not contain {L.slug}")
    return ready


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def lines(data):
    return data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1)


def git_head():
    try:
        done = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "tools/normgen",
                                f"{L.rel}/data"], capture_output=True, text=True, check=True).stdout.strip()
        return done.stdout.strip() + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return None


MACHINES = ("slot-capture", "slot-fate", "slot-release")    # gen_machine.py: each part uses the lesson's forms/<part>.tsv.
PARTS = ("vectors", "stagetests", "door", "flags", "refusals", "launch", "core", "families", "admin", "box", "loader", "rollout-poll") + MACHINES + ("contracts",)       # Parts beyond writecheck (ADR-0126 addendum 2, item 1 names).
CONTRACTS = NORMGEN / "contracts"                    # Shared contracts package: handwritten runtime judged by test_contracts.py.


EXAMPLES = HERE / "examples"                # One Go connection example per part, compiled by kit/test_kit.py.
EXAMPLE_ORDER = ("writecheck", "door", "flags", "refusals", "families", "vectors", "stagetests", "launch", "admin")


def connect_md(parts, module):
    """Read each part's connection example verbatim from kit/examples/<part>.go (ADR-0083 addendum 95, item 2)."""
    out = ["", "## Connect: one example per part", "",
           "Read this, not the generated bodies: the signatures above and these examples are the whole API you need. "
           "Each example compiles against this kit (the kit's own test builds them).", ""]
    for part in EXAMPLE_ORDER:
        if part not in parts:
            continue
        text = (EXAMPLES / f"{part}.go").read_text(encoding="utf-8")
        text = text.replace('"kitmodule/internal/', f'"{module}/internal/').split("\n", 2)[2]   # Omit package example.
        out += [f"### `{part}`", "", "```go", text.rstrip("\n"), "```", ""]
    return "\n".join(out)


EXPORTED = re.compile(r"^(?:func ([A-Z]\w*)|func \([^)]*\) [A-Z]\w*|type ([A-Z]\w*)|(?:var|const) ([A-Z]\w*))", re.M)
BLOCK = re.compile(r"^(?:var|const) \(\n(.*?)^\)", re.M | re.S)


def exported_md(internal, dst, module):
    """Read actual exported package functions, types, variables and constants from source rather than a remembered list."""
    out = ["## Exported names (by package)", ""]
    for pkg in sorted({p.parent for p in Path(dst).rglob("*.go") if not p.name.endswith("_test.go")}):
        names = set()
        for f in pkg.glob("*.go"):
            if f.name.endswith("_test.go"):
                continue
            text = f.read_text(encoding="utf-8")
            for m in EXPORTED.finditer(text):
                names.add(next(g for g in m.groups() if g) if any(m.groups()) else None)
            for b in BLOCK.finditer(text):
                names |= set(re.findall(r"^\t([A-Z]\w*)", b[1], re.M))
        names.discard(None)
        if names:
            rel = pkg.relative_to(Path(dst) / L.kit_dir)
            out.append(f"- `{module}/{rel}`: " + ", ".join(f"`{n}`" for n in sorted(names)))
    return "\n".join(out) + "\n"


def provenance(parts, files, judged):
    """Record part provenance (ADR-0125 addendum 1, item 6(a); Codex C2): form, generator, runtime, judge paths/SHA256; output is an ordered path+SHA digest; judged is the optional --judged part=link, otherwise null."""
    def output(*components):
        own = sorted((f["path"], f["sha256"]) for f in files if f["component"] in components and not f.get("editable"))
        return sha256("".join(f"{p}\t{h}\n" for p, h in own).encode())
    table = {
        "writecheck": (("normgen", "kit"), {"form": gen_checks.tsv_input.source_files(TABLE, root=ROOT) if TABLE.is_file() else [],
                                   "generator": NORMGEN / "gen_checks.py",
                                   "generators": [NORMGEN / "gen_checks.py", NORMGEN / "tsv_input.py"],
                                   "handwritten": [NORMGEN / "runtime/go/runtime.go", NORMGEN / "prims/go/prims.go"]
                                   + [HANDWRITTEN / sub / name for sub, name in KIT_FILES],
                                   "judge": NORMGEN / "test_gen_checks.py"}),
        "door": (("door",), {"form": [OPENAPI], "generator": NORMGEN / "gen_door.py",
                          "handwritten": [NORMGEN / "doorrt/go/runtime.go"], "judge": NORMGEN / "door_judge.py"}),
        "vectors": (("vectors",), {"form": gen_tests.sources("vectors") if L.key == lesson.DEFAULT else [L.form("stages.kit.tsv")],
                                "generator": NORMGEN / "gen_tests.py",
                                "generators": [NORMGEN / p for p in ("gen_tests.py", "gen_stagetests.py", "gen_cmdtests.py",
                                                                    "gen_checks.py", "common_vectors.py", "wire.py",
                                                                    "vector_consumers.py", "tsv_input.py", "gate.py")],
                                "judge": NORMGEN / "vector_judge.py"}),
        "stagetests": (("stagetests",), {"form": gen_tests.sources("stagetests") if L.key == lesson.DEFAULT else [L.form("stages.kit.tsv"),
                                               L.path("acceptance/1/scenarios.tsv"),
                                               L.path("acceptance/1/seams.tsv"),
                                               L.path("acceptance/3/seams.tsv")],
                                      "generator": NORMGEN / "gen_stagetests.py",
                                      "generators": [NORMGEN / p for p in ("gen_stagetests.py", "gen_tests.py", "gen_checks.py",
                                                                          "gen_cmdtests.py", "tsv_input.py", "gate.py",
                                                                          "gen_door.py", "yamlsub.py")],
                                      "judge": NORMGEN / "scenario_judge.py"}),
    }
    out = {}
    for part in parts:
        if part == "contracts":
            out[part] = {"form": [entry(f) for f in gen_heartbeat.sources()],
                         "generator": entry(CONTRACTS / "gen/gen_nfkc.py"),
                         "generators": [entry(CONTRACTS / "gen/gen_nfkc.py"), entry(CONTRACTS / "gen/gen_heartbeat.py")],
                         "judge": entry(NORMGEN / "test_contracts.py"),
                         "handwritten": [entry(f) for f in sorted(CONTRACTS.rglob("*.go"))
                                         if not f.read_bytes().startswith(b"// Code generated")],
                         "output": output("contracts")}
        elif part == "door" and L.key != lesson.DEFAULT:
            out[part] = {**gen_door_lesson.provenance(), "output": output("door")}
        elif part == "vectors" and L.key != lesson.DEFAULT:    # Other lessons, including HTTP P/06, use gen_vectors.
            out[part] = {**gen_vectors.provenance(), "output": output("vectors")}
        elif part == "stagetests" and L.key != lesson.DEFAULT:
            out[part] = {**gen_cmdtests.provenance(), "output": output("stagetests")}
        elif part in MACHINES:
            out[part] = {**gen_machine.provenance(part), "output": output(part)}
        elif part in ("flags", "refusals", "launch", "core", "families", "admin", "box", "loader", "rollout-poll"):
            mod = {"flags": gen_flags, "refusals": gen_refusals, "launch": gen_launch,
                   "core": gen_versioned_doors if L.key == "08-domain" else gen_core,
                   "families": gen_families, "admin": gen_admin, "box": gen_box, "loader": gen_manifest,
                   "rollout-poll": gen_rollout}[part]
            out[part] = {**mod.provenance(), "output": output(part)}
            if part == "families" and gen_row_writes.enabled():
                overlay = gen_row_writes.provenance()
                for key in ("form", "generators", "handwritten"):
                    entries = out[part].get(key, []) + overlay[key]
                    out[part][key] = list({e["path"]: e for e in entries}.values())
                out[part]["judges"] = [out[part]["judge"], overlay["judge"]]
        else:
            component, t = table[part]
            out[part] = {"form": [entry(f) for f in t["form"] if f.is_file()], "generator": entry(t["generator"]),
                         "handwritten": [entry(f) for f in t.get("handwritten", [])], "judge": entry(t["judge"]),
                         "output": output(*component)}
            if "generators" in t:
                out[part]["generators"] = [entry(f) for f in t["generators"]]
        out[part]["judged"] = judged.get(part)
    return out


DECL = re.compile(rb"^(?:func (?:\(\w+ \*?(\w+)\) )?(\w+)\(|type (\w+) )", re.M)


def declarations(data):
    """Read top-level Go declarations: functions, methods (Type.name) and types."""
    return {(f"{m[1].decode()}." if m[1] else "") + (m[2] or m[3]).decode() for m in DECL.finditer(data)}


def own_taken(target, data):
    """Do not install an implementation stub if its file exists or its declaration already lives in another package file. This supports moved/combined implementation functions and avoids duplicate declarations breaking the build."""
    if target.exists():
        return True
    mine = declarations(data)
    for f in target.parent.glob("*.go") if target.parent.is_dir() else ():
        if not f.name.endswith("_test.go") and mine & declarations(f.read_bytes()):
            return True
    return False


def seed_rule(dst, seed):
    """Seed rule (Architect, 2026-11-05, attempt 28 from27): install editable files only when absent from the seed or still byte-identical to their prior kit.manifest.json SHA. Otherwise retain model code. Without a seed, use own_taken on dst. Return (taken(target, data), kept, refreshed)."""
    kept, refreshed = [], []
    if seed is None:
        return (lambda target, data: own_taken(target, data)), kept, refreshed
    seed = Path(seed)
    try:
        prior = json.loads((seed / "kit.manifest.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        prior = {"files": []}
    put = {f["path"]: f["sha256"] for f in prior.get("files", []) if f.get("editable")}

    def taken(target, data):
        rel = str(Path(target).relative_to(dst))
        mine = seed / rel
        if mine.is_file() and put.get(rel) == sha256(mine.read_bytes()):
            others = [f for f in mine.parent.glob("*.go") if f != mine and not f.name.endswith("_test.go")]
            if not any(declarations(data) & declarations(f.read_bytes()) for f in others):
                refreshed.append(rel)
                return False
        if own_taken(mine, data):
            kept.append(rel)
            return True
        return own_taken(target, data)
    return taken, kept, refreshed


DELIVERIES = ("internal", "model-launch")
RETIRED_ADAPTERS = {"slotname.go", "sealing.go", "valuesbytype.go"}
PUBLIC_PROBES = ("copy_stream.py", "store_fitness.py", "store_probe_http.py", "store_probes.py", "README.md")
LEGACY_EXPORT = "ce8d6db6219dbd38d358acbc81e3d429e7789950"


def delivery_request(delivery, dst, parts, seed):
    """Tool-only delivery policy; internal builds retain their historical behavior."""
    if delivery not in DELIVERIES:
        raise KitError(f"unknown delivery {delivery!r}")
    if delivery == "internal":
        return
    if L.key != lesson.DEFAULT or L.slug != "p01-1":
        raise KitError("model-launch delivery supports export P/01 only")
    if "box" in parts:
        raise KitError("model-launch delivery refuses the retired box part")
    if seed is not None:
        raise KitError("model-launch delivery refuses seed; use a new empty destination")
    dst = Path(dst)
    if dst.is_symlink() or (dst.exists() and (not dst.is_dir() or any(dst.iterdir()))):
        raise KitError("model-launch delivery requires a new empty destination")


def delivery_identity(root, context):
    """Require actual export context and its single Platform source pin."""
    export, course = context.get("export_commit"), context.get("course_commit")
    if (context.get("kind") != "export" or not isinstance(export, str)
            or re.fullmatch(r"[0-9a-f]{40}", export) is None or export == LEGACY_EXPORT
            or not isinstance(course, str) or re.fullmatch(r"[0-9a-f]{40}", course) is None):
        raise KitError("model-launch delivery requires pinned non-legacy export/code context")
    pin_file = Path(root) / "Platform/COURSE_COMMIT"
    if not pin_file.is_file() or pin_file.is_symlink():
        raise KitError("model-launch delivery requires Platform/COURSE_COMMIT")
    pin = pin_file.read_text(encoding="utf-8").strip()
    if re.fullmatch(r"[0-9a-f]{40}", pin) is None or context.get("source_pin", pin) != pin:
        raise KitError("invalid/inconsistent Platform/COURSE_COMMIT identity")
    return {"source_commit": pin, "code_commit": course, "export_commit": export}


def delivery_predicates():
    """Project exactly two reviewed handwritten definitions, never the sealing algorithm."""
    source = CONTRACTS / "go/sealing.go"
    data = source.read_bytes()
    specs = (
        ("b64Canonical", rb"^func b64Canonical\(s string\) \(\[\]byte, bool\) \{\n.*?^}\n",
         "3132646af3776d2529dc85caaee85862ace84e12f75cbfd86875322c5c63c319"),
        ("LooksSealed", rb"^func LooksSealed\(v string\) bool \{[^\n]*}\n",
         "a05dad6a9a60027d76b82b23cbbd770f85e32c55364d0969043f2ea0ed857dc1"),
    )
    closure = b"var b64 = base64.RawURLEncoding.Strict()\n"
    if len(re.findall(b"^" + re.escape(closure), data, re.M)) != 1:
        raise KitError("sealing predicate closure changed")
    definitions, spans = [], []
    for name, pattern, expected in specs:
        matches = list(re.finditer(pattern, data, re.M | re.S))
        if (len(re.findall(rb"^func " + name.encode() + rb"\(", data, re.M)) != 1
                or len(matches) != 1 or sha256(matches[0][0]) != expected):
            raise KitError(f"original sealing definition changed or is not unique: {name}")
        m = matches[0]
        definitions.append(m[0])
        spans.append({"name": name, "byte_start": m.start(), "byte_end_exclusive": m.end(),
                      "line_start": data[:m.start()].count(b"\n") + 1,
                      "line_end": data[:m.end()].count(b"\n"), "sha256": expected})
    helper = (b'// Handwritten predicates projected for model-launch delivery; DO NOT EDIT.\n'
              b'package contracts\n\nimport (\n\t"encoding/base64"\n\t"strings"\n)\n\n'
              + closure + b"\n" + b"\n".join(definitions))
    projection = {"input": {"path": str(source.relative_to(ROOT)), "sha256": sha256(data)},
                  "delivered_definitions": spans,
                  "closure": closure.decode().rstrip("\n"), "origin": "handwritten",
                  "excluded_algorithms": ["slotname.go", "sealing.go"]}
    return helper, projection


def build(dst, module, parts=(), judged=None, seed=None, *, delivery="internal"):
    delivery_request(delivery, dst, parts, seed)
    checked_outputs()  # Validate before any destination/seed copy; never prepare here.
    prepared = lesson.output_manifest()
    declared = prepared["parts"][L.slug]
    model = delivery == "model-launch"
    identity, predicate_data, projection, probe_files = {}, None, None, []
    if model:
        identity = delivery_identity(ROOT, prepared["context"])
        if (os.environ.get(COURSE_ENV) != identity["code_commit"]
                or os.environ.get(EXPORT_ENV) != identity["export_commit"]):
            raise KitError("model-launch environment differs from checked export context")
        if "contracts" in parts:
            predicate_data, projection = delivery_predicates()
        for name in PUBLIC_PROBES:
            source = ROOT / "Platform/01-store/probes" / name
            if not source.is_file() or source.is_symlink():
                raise KitError(f"missing regular public probe source: {source}")
            probe_files.append((name, source.read_bytes(), str(source.relative_to(ROOT))))
    if not set(parts) <= set(declared):
        raise KitError("requested kit parts are absent from the prepared set")
    dst = Path(dst)
    if set(judged or {}) - set(("writecheck",) + PARTS):
        raise KitError(f"--judged: unknown parts {sorted(set(judged) - set(('writecheck',) + PARTS))}")
    if not MODULE.fullmatch(module) or "//" in module or module.endswith("/"):
        raise KitError(f"--module {module!r} is not a Go import path")
    has_wc = TABLE.is_file()                          # writecheck exists for lessons with forms/write-checks.tsv (P/01).
    http = L.openapi.is_file() and L.key == lesson.DEFAULT   # P/01 stagetests use apidoor; all other lessons, including HTTP P/05, use gen_cmdtests.
    table_sha = sha256(TABLE.read_bytes()) if has_wc else None
    if has_wc:
        fresh_check(gen_checks, TABLE, "go/checks", [n for n, _, _ in CHECKS_FILES])
    if set(parts) - set(PARTS):
        raise KitError(f"--part {sorted(set(parts) - set(PARTS))}: one of {list(PARTS)}")
    if "rollout-poll" in parts and "stagetests" not in parts:
        raise KitError("--part rollout-poll needs --part stagetests: the traces call lessonadapter.RolloutPoll")
    if "stagetests" in parts and http and "door" not in parts:
        raise KitError("--part stagetests needs --part door: the stage tests go through coreadapter over apidoor "
                       "(ADR-0126 addendum (7) item 5)")
    if "vectors" in parts and gen_tests.common_vectors.uses_families(L.key) and "families" not in parts:
        raise KitError("--part vectors needs --part families: the vector command reads common/family-read by the "
                       "kit's families (ADR-0125 addendum (5) item 5)")
    if "admin" in parts and "flags" not in parts:
        raise KitError("--part admin needs --part flags: the subcommands get *flags.Flags of the form")
    if "box" in parts and not ({"door", "flags", "refusals"} <= set(parts) and has_wc):
        raise KitError("--part box needs --part door, --part flags, --part refusals and the writecheck part: box answers "
                       "by apidoor, reads *flags.Flags, refuses by refusals and parses by jsonstrict")
    if "loader" in parts and L.key != "02-installer":
        raise KitError("--part loader is the loader of P/02.1 (lesson 02-installer)")
    if "launch" in parts and "admin" not in parts:
        raise KitError("--part launch needs --part admin: launch.Main gives the subcommands of admin_ops to admin.Run "
                       "(Architect 2026-11-05)")
    if "launch" in parts and not {"door", "flags", "stagetests"} <= set(parts):
        raise KitError("--part launch needs --part door, --part flags and --part stagetests: the frame parses by flags "
                       "and serves coreadapter.Handle over apidoor (ADR-0083 addendum (95) item 3)")
    if "core" in parts and L.key == "08-domain" and "door" not in parts:
        raise KitError("--part core metadata of P/08 needs --part door")
    if "core" in parts and L.key != "08-domain" and not {"door", "stagetests"} <= set(parts):
        raise KitError("--part core needs --part door and --part stagetests: the core is the coreadapter.Core of the "
                       "stage tests over apidoor.Handler (ADR-0083 addendum (95) item 3)")
    kit_parts = (["writecheck"] if has_wc else []) + sorted(set(parts))
    parts_set = list(kit_parts)
    # Required producer/runtime/judge inputs must exist before touching dst/seed.
    try:
        provenance(parts_set, [], judged or {})
    except OSError as exc:
        raise KitError(f"prepared provenance dependency: {exc}") from None
    try:
        tests = [(f, "vectors") for f in (gen_tests.kit_files(module, "vectors") if L.key == lesson.DEFAULT
                                           else gen_vectors.kit_files(module))] if "vectors" in parts else []
        if "stagetests" in parts:
            tests += [(f, "stagetests") for f in (gen_tests.kit_files(module, "stagetests") if http
                                                    else gen_cmdtests.kit_files(module))]
        rollout_files = gen_rollout.kit_files(module) if "rollout-poll" in parts else []
        flag_files = gen_flags.kit_files() if "flags" in parts else []
        refusal_files = gen_refusals.kit_files() if "refusals" in parts else []
        launch_files = gen_launch.kit_files(module) if "launch" in parts else []
        core_files = ((gen_versioned_doors if L.key == "08-domain" else gen_core).kit_files(module)
                      if "core" in parts else [])
        family_files = gen_families.kit_files() if "families" in parts else []
        if family_files and L.key == "03-worker":
            family_files += gen_row_writes.kit_files()
        admin_files = gen_admin.kit_files(module) if "admin" in parts else []
        box_files = gen_box.kit_files(module) if "box" in parts else []
        loader_files = gen_manifest.kit_files(module) if "loader" in parts else []
        loader_root = prepared_vendor(module) if "loader" in parts else []
        policy_root = prepared_vendor(module) if L.key == "03-worker" and "stagetests" in parts else []
        loader_wired = gen_manifest.wired(module) if "loader" in parts else {}
        machine_files = [(p, f) for p in sorted(set(parts) & set(MACHINES)) for f in gen_machine.kit_files(p, module)]
    except (gen_machine.GenError, gen_tests.GenError, gen_flags.GenError, gen_refusals.GenError, gen_launch.GenError,
            gen_core.GenError, gen_families.GenError, gen_admin.GenError, gen_box.GenError, gen_manifest.GenError, gen_cmdtests.GenError,
            gen_rollout.GenError, gen_vectors.GenError, gen_versioned_doors.GenError, gen_policy_machines.GenError) as exc:
        raise KitError(str(exc)) from None
    door_lesson = "door" in parts and L.key != lesson.DEFAULT
    try:
        door_lesson_files = gen_door_lesson.kit_files() if door_lesson else []
    except gen_door_lesson.GenError as exc:
        raise KitError(str(exc)) from None
    openapi_sha = sha256(OPENAPI.read_bytes()) if "door" in parts and not door_lesson else None
    if openapi_sha:
        fresh_check(gen_door, OPENAPI, "go/apidoor", [n for n, _, _ in DOOR_FILES])
    internal = dst / L.kit_dir / "internal"
    files = []
    taken, kept, refreshed = seed_rule(dst, seed)

    def put(rel_dir, name, data, origin, component, source):
        target = Path(os.path.normpath(internal / rel_dir / name))      # ../cmd/vectors sits alongside internal/.
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files.append({"path": str(target.relative_to(dst)), "sha256": sha256(data), "lines": lines(data),
                      "origin": origin, "component": component, "source": source})

    for sub in (("checks", "jsonstrict", "writecheck") if has_wc else ()) + \
            (("workerpolicy", "../vendor") if policy_root else ()) + \
            (gen_rollout.KIT_DIRS if rollout_files else ()) + sum((gen_tests.PART_DIRS[p] for p in ("vectors", "stagetests") if p in parts), ()) + \
            (("apidoor",) if openapi_sha or door_lesson else ()) + (gen_flags.KIT_DIRS if flag_files else ()) + \
            (gen_refusals.KIT_DIRS if refusal_files else ()) + (("launch",) if launch_files else ()) + \
            (gen_families.KIT_DIRS if family_files else ()) + (("manifest", "../vendor") if loader_files else ()) + \
            sum((gen_machine.kit_dirs(p) for p in sorted(set(parts) & set(MACHINES))), ()):
        if Path(os.path.normpath(internal / sub)).exists():
            shutil.rmtree(os.path.normpath(internal / sub))
    for name, origin, source in CHECKS_FILES if has_wc else ():
        put("checks", name, (GENERATED / name).read_bytes(), origin, "normgen", source)
    for sub, name in KIT_FILES if has_wc else ():
        data = (HANDWRITTEN / sub / name).read_bytes()
        if PLACEHOLDER.encode() in data:
            data = data.replace(PLACEHOLDER.encode(), f'"{module}/internal/'.encode())
        elif sub == "writecheck":
            raise KitError(f"{sub}/{name}: no import {PLACEHOLDER}… to rewrite")
        put(sub, name, data, "handwritten", "kit", str((HANDWRITTEN / sub / name).relative_to(ROOT)))

    contract_adapters = {}
    if "contracts" in parts:                           # Shared contracts package and its vector adapters.
        contract_root = L.out / "go/contracts"
        contract_files = sorted(contract_root.rglob("*.go"))
        if not contract_files or not (contract_root / "contracts.go").is_file():
            raise KitError("prepared contracts roster is empty/incomplete")
        for f in contract_files:
            data = f.read_bytes()       # nfkc_tables.go comes from contracts/gen/gen_nfkc.py (Unicode15.0.0).
            rel = f.relative_to(contract_root).as_posix()
            if model and rel in ("slotname.go", "sealing.go"):
                continue
            origin = "generated" if rel in ("nfkc_tables.go", "heartbeat/families.go") else "handwritten"
            source = (L.output_source(f) if origin == "generated" else
                      "tools/normgen/famrt2/go/runtime.go" if rel == "heartbeat/runtime.go" else
                      str((CONTRACTS / "go" / rel).relative_to(ROOT)))
            put("contracts", rel, data, origin, "contracts", source)
        if model:
            put("contracts", "delivery_predicates.go", predicate_data, "handwritten", "contracts",
                projection["input"]["path"])
            files[-1]["projection"] = projection
        for f in sorted((CONTRACTS / "adapters").glob("*.go")):
            fn = re.search(r"^func ([A-Z]\w*)\((?:table|input|file|raw)\b", f.read_text(), re.M)[1]
            contract_adapters[f"{fn.lower()}.go"] = f
        if model:
            for name in RETIRED_ADAPTERS:
                contract_adapters.pop(name, None)
    for (sub, name, data, origin, source, own), component in tests:
        if sub == "vectoradapter" and name in contract_adapters:   # Replace the stub with a contracts-backed adapter, still implementation-owned.
            f = contract_adapters[name]
            data = kitside.fill(f.read_text(encoding="utf-8"), L.out / "go/vectortests").encode()
            data = data.replace(PLACEHOLDER.encode(), f'"{module}/internal/'.encode())
            origin, source = "handwritten", str(f.relative_to(ROOT))
        if core_files and (sub, name) == ("coreadapter", "open.go"):
            continue                    # The core part's open.go already returns its core.
        if (sub, name) in loader_wired:
            data, origin, component = loader_wired[sub, name], "generated", "loader"   # Scaffold wired to manifest.
        if own and taken(Path(os.path.normpath(internal / sub / name)), data):
            continue                    # Preserve the implementation adapter.
        put(sub, name, data, origin, component, source)
        if own:
            files[-1]["editable"] = True
    if openapi_sha:
        for name, origin, source in DOOR_FILES:
            put("apidoor", name, (DOOR / name).read_bytes(), origin, "door", source)
    for sub, name, data, origin, source in door_lesson_files:
        put(sub, name, data, origin, "door", source)
    for sub, name, data, origin, source in flag_files:
        put(sub, name, data, origin, "flags", source)
    for sub, name, data, origin, source in refusal_files:
        put(sub, name, data, origin, "refusals", source)
    for sub, name, data, origin, source in family_files:
        put(sub, name, data, origin, "families", source)
    for sub, name, data, origin, source in rollout_files:
        put(sub, name, data, origin, "rollout-poll", source)
    for part, (sub, name, data, origin, source, own) in machine_files:
        if own and taken(Path(os.path.normpath(internal / sub / name)), data):
            continue                    # Machine actions and procedures belong to the implementation.
        put(sub, name, data, origin, part, source)
        if own:
            files[-1]["editable"] = True
    for sub, name, data, origin, source, own in admin_files:
        if own and taken(Path(os.path.normpath(internal / sub / name)), data):
            continue                    # Preserve implementation subcommands.
        put(sub, name, data, origin, "admin", source)
        if own:
            files[-1]["editable"] = True
    for sub, name, data, origin, source, own in box_files:
        put(sub, name, data, origin, "box", source)          # Entirely closed: replace in full.
    for sub, name, data, origin, source, own in loader_files:
        put(sub, name, data, origin, "loader", source)       # Entirely closed: replace in full.
    for relp, data in loader_root:                          # Module root: go.mod/go.sum become implementation-owned after seeding, plus vendor/.
        sub, name = os.path.split(relp)
        sub = os.path.join("..", sub)
        own = relp in ("go.mod", "go.sum")
        if own and taken(Path(os.path.normpath(internal / sub / name)), data):
            continue
        put(sub, name, data, "vendored" if relp.startswith("vendor/") else "generated", "loader",
            "Platform/common/versions" + ("" if own else " (go mod vendor)"))
        if own:
            files[-1]["editable"] = True
    for relp, data in policy_root:
        sub, name = os.path.split(relp)
        own = relp in ("go.mod", "go.sum")
        if own and taken(Path(os.path.normpath(internal / ".." / relp)), data):
            continue
        put(os.path.join("..", sub), name, data, "vendored" if relp.startswith("vendor/") else "generated",
            "stagetests", "Platform/common/versions" + (" (go mod vendor)" if relp.startswith("vendor/") else ""))
        if own:
            files[-1]["editable"] = True
    for sub, name, data, origin, source, own in launch_files:
        if own and taken(Path(os.path.normpath(internal / sub / name)), data):
            continue                    # Preserve implementation main.go and frame.
        put(sub, name, data, origin, "launch", source)
        if own:
            files[-1]["editable"] = True
    for sub, name, data, origin, source, own in core_files:
        if own and taken(internal / sub / name, data):
            continue                    # Preserve the implementation core.
        put(sub, name, data, origin, "core", source)
        if own:
            files[-1]["editable"] = True
    for name, data, source in probe_files:
        put("../publicprobes", name, data, "handwritten", "publicprobes", source)
    stagetests_md = (gen_tests.KIT_MD_STAGETESTS if http else gen_cmdtests.KIT_MD) if "stagetests" in parts else ""
    if policy_root:
        stagetests_md += gen_policy_machines.KIT_MD
    doc = ((KIT_MD if has_wc else KIT_MD_LESSON.replace("{lesson}", L.code).replace("{dir}", L.kit_dir))
           + ((gen_tests.kit_md() if L.key == lesson.DEFAULT else gen_vectors.KIT_MD) if "vectors" in parts else "")
           + stagetests_md + (gen_rollout.KIT_MD if rollout_files else "") + (KIT_DOOR_MD if openapi_sha else "")
           + (gen_door_lesson.kit_md() if door_lesson else "")
           + (gen_flags.kit_md() if flag_files else "") + (gen_refusals.kit_md() if refusal_files else "")
           + (gen_families.kit_md() if family_files else "") + (gen_admin.kit_md() if admin_files else "")
           + (gen_row_writes.KIT_MD if family_files and gen_row_writes.enabled() else "")
           + (gen_box.kit_md() if box_files else "")
           + (gen_manifest.kit_md() if loader_files else "")
           + (gen_launch.KIT_MD if launch_files else "")
           + ((gen_versioned_doors if L.key == "08-domain" else gen_core).KIT_MD if core_files else "")
           + "".join(gen_machine.kit_md(p) for p in sorted(set(parts) & set(MACHINES)))
           + ((KIT_MODEL_CONTRACTS_MD if model else KIT_CONTRACTS_MD) if "contracts" in parts else "")).replace("{module}", module)
    if model:
        doc += KIT_MODEL_MD.format(**identity)
    if policy_root:
        doc = doc.replace("Standard library only, Go 1.22.", "Go 1.22; the closed policies use vendored cel-go v0.26.1 from Platform/common/versions.")
    connect = connect_md(kit_parts, module) if L.key == lesson.DEFAULT else ""   # Part examples are P/01 code.
    doc = (doc + connect + exported_md(internal, dst, module)).encode("utf-8")
    (dst / "KIT.md").write_bytes(doc)
    # Attempt provenance (addendum 86, item 3) counts separately by origin (generated|handwritten) and component:
    # normgen is the generator and its runtime.go/prims.go; kit is handwritten jsonstrict/writecheck.
    totals, parts = {}, {}
    for f in files:
        totals[f["origin"]] = totals.get(f["origin"], 0) + f["lines"]
        parts[f["component"]] = parts.get(f["component"], 0) + f["lines"]
    manifest = {
        "kit": ("P/01 pack B (ADR-0083 amendment 86): N2.1 write checks and strict JSON body parser, Go" if has_wc
                else f"{L.code} kit (ADR-0125 addendum (5)): the generated parts of the lesson, Go"),
        "module": module,
        "parts": kit_parts,
        "commit": os.environ.get(COURSE_ENV) or git_head(),
        "export": os.environ.get(EXPORT_ENV) or None,
        "table": {"path": str(TABLE.relative_to(ROOT)), "sha256": table_sha} if has_wc else None,
        "files": files,
        "provenance": provenance(parts_set, files, judged or {}),
        "doc": {"path": "KIT.md", "sha256": sha256(doc), "lines": lines(doc)},
        "lines": totals,
        "lines_by_component": parts,
    }
    if model:
        manifest["delivery"] = {"mode": delivery, **identity,
                                "prepared_manifest_sha256": os.environ[lesson.OUTPUT_RECEIPT_ENV],
                                "contracts_projection": projection,
                                "publicprobes": {"files": list(PUBLIC_PROBES),
                                                 "source": "Platform/01-store/probes",
                                                 "semantics": "public observation checkers; no SUT/provider qualification"}}
        if projection is not None:
            cp = manifest["provenance"]["contracts"]
            cp["input_handwritten"] = cp.pop("handwritten")
            delivered_sources = {f["source"] for f in files if f["component"] == "contracts"
                                 and f["origin"] == "handwritten" and "projection" not in f}
            cp["handwritten"] = [entry(ROOT / p) for p in sorted(delivered_sources)]
            cp["delivery_projection"] = projection
    if openapi_sha:
        manifest["openapi"] = {"path": str(OPENAPI.relative_to(ROOT)), "sha256": openapi_sha}
    if seed is not None:
        manifest["seed"] = {"kept": sorted(set(kept)), "refreshed": sorted(set(refreshed))}
    (dst / "kit.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
    return manifest


KIT_MD = """# Kit: write checks of P/01.1 N2.1 (Go)

Ready-made Go packages under `01-store/internal/`. They are part of your tree, but **do not edit them** (writes there are
closed): import and call them. `kit.manifest.json` lists every file with its sha256.

| Package | Import path | Origin |
|---|---|---|
| `writecheck` | `{module}/internal/writecheck` | handwritten: parser + checks in one call — **use this** |
| `jsonstrict` | `{module}/internal/jsonstrict` | handwritten: the strict JSON parser of N2.1 |
| `checks` | `{module}/internal/checks` | generated from `Platform/01-store/forms/write-checks.tsv` |

Standard library only, Go 1.22. All functions are pure and safe for concurrent use.

## `writecheck.Check` — the body of `POST /v1/write`

```go
func Check(body []byte, sock string, lim map[string]int64,
    allowed func(sock, op, key string) bool) (*writecheck.Refusal, any)

type Refusal struct {
    Code   int            // HTTP status: 400, 403 or 413
    Kind   string         // refusal kind: "badrequest", "badkey", "forbidden", "toolarge"
    Fault  map[string]any // other fields of the refusal body, nil if none (values int64 or string)
    N      int            // row of write-checks.tsv; 0 = the JSON parse failed
    Check  string         // name of that row; "json" = the JSON parse
    Reason string         // parse reason or fault error: for your log only
}
```

- `body` — the whole decoded body bytes. Call it only after the HTTP framing and the body limit of N2.1 (`413` before the
  body is parsed); the kit does not read HTTP.
- `sock` — the role of the caller's socket (P/01.2 N1.1 identity): `admin`, `console`, `domain` or a role name.
- `lim` — the lesson values of `BATCH_WRITES`, `BATCH_GUARDS`, `ROW_CEILING` (P/01.1 N1). A missing name panics
  (a code error, not an input error). `JSON_DEPTH` is fixed by N2.1 (128) and is not taken from `lim`.
- `allowed(sock, op, key)` — the rights of P/01.2 N3 «check», `op` is `read`, `write` or `delete`. You implement it;
  the kit calls it for the target key and for guard keys. `nil` panics.

Result:

- `(*Refusal, nil)` with `N == 0` — the body is not JSON by N2.1 (a repeated field name at any level, `NaN`,
  `Infinity`, a BOM, not UTF-8, deeper than 128, any RFC 8259 syntax error): always `400 badrequest`.
- `(*Refusal, body)` with `N > 0` — the first violated row of the table. Answer `Code` with the JSON body
  `{"kind": Kind}` plus every field of `Fault` (for `413 toolarge`: `limit`, `key`, `size`). Nothing is written.
- `(nil, body)` — every check passed: execute the command by N3 with `body`.

`Reason`, `N` and `Check` are never sent to the caller (a refusal does not quote the input).

### The parsed body

`body` is `map[string]any` when no refusal (a non-object body is refused by row 1). Values:
`nil` (null), `bool`, `int64`, `float64`, `string`, `[]any`, `map[string]any`.

- A number without `.`, `e`, `E` that fits int64 is `int64`; any other number is `float64`; a number beyond binary64
  is `±Inf` (`not_after: 1e400` is refused by its row, not by the parser). `not_after`/`not_before` may arrive as
  `int64` or `float64`: compare by value.
- A lone surrogate (`\\ud800`) becomes U+FFFD in the string. The rows already refuse it where it matters (`key`,
  `guard.key`, the keys of `writes` and `guards` — `badkey`; `items` — `badrequest`); in extra fields it is not read.
- Extra fields stay in the map: do not read them.
- `op: floor` passes the table on the `admin` socket only (row 3); everything after that is P/01.3 N2 — yours.

## What the kit does NOT do

- HTTP: the request line, headers, routes, methods, `Content-Length` / chunked framing, the body limit, the early
  refusal and drain, the query of `GET /v1/get` and `GET /v1/list` (all N2.1 — yours).
- The store state (N3): `cas` and `guard` compared with the stored rows, the `id` memory and its answers, admission
  of `not_after` / `not_before` against the clock, writing and the index. The table checks only the form.
- Rights: the kit does not know the rights; it asks `allowed`. Identity of the socket (P/01.2) is yours.

## Lower level (normally not needed)

```go
// jsonstrict: value, JSON Pointers of strings with a lone surrogate (sorted, nil if none), or a parse error.
func jsonstrict.Decode(body []byte, depth int) (value any, lone []string, err *jsonstrict.Error)
type jsonstrict.Error struct { Code int; Kind string; Reason string; Offset int } // always 400 "badrequest"
const jsonstrict.Depth = 128

// checks: the table on an already parsed body.
func checks.Check(in checks.Input) *checks.Refusal
type checks.Input struct { Body any; Sock string; Lone []string; Lim map[string]int64; Fns checks.Fns }
```
"""


KIT_CONTRACTS_MD = """
## Part `contracts`: the common contracts of the platform (handwritten once, judged by the common vectors)

| Package | Import path | Origin |
|---|---|---|
| `contracts` | `{module}/internal/contracts` | the kit's implementation of `Platform/common/contracts/*.md` — closed; use it in your code |
| `heartbeat` | `{module}/internal/contracts/heartbeat` | `ReadResource(key, text)` and `ReadWorker(key, text)` over the generated P/03 and P/05 families |

The functions are the pure computations of their contracts (the instance and the box, the slot names, the labels, the
event journal: names, buckets, lines…; the outcome of a store answer for its client; the revocation files revoked and
crl.pem by the centers; the login and the password in a url value — the display and the refusal, the log mask of
free text, the mask at the input; the url field rules from their declarations; NFKC of Unicode 15.0.0; the loopback
threshold and the IP literal of peer; the schema check at start; the object address and the read outcome; freshness by LOST_AFTER; the fault words of
the doors; the envelope enc:v2, the AAD path, the ring file and resealing a value; the values by type of a row; peer — the
client about the server of another cluster; the domain token check; agent signatures and signed batch knocks;
the turn state machine; domain keys and revocation merging; may and scope coverage; heartbeat reading by the foreign
families, including whole-object, field and status-element outcomes).

`Record(keys, row, kinds)` checks only the caller's accepted kinds (term, backup, grant, members, shared); use
`ParseRecordInput` at the vector command boundary and `TakeMemberRecord` for the members-row freshness bound.
`MergeEvents(inputJSON)` merges console/worker resource replies; `FilterResourceEvents(inputJSON)` applies the
resource's own query and cut, preserving complete source rows. Both return a JSON object and an error for invalid
command inputs. The caller supplies replies, epoch reads and visibility inputs; these functions perform no I/O.
Reading files, the environment and the clock is yours. With the part
`vectors`, the adapters of the tables they cover (`vectoradapter/<package>.go`) call this package — yours to change
like any adapter. `tools/normgen/test_contracts.py` runs the common vectors of every lesson against them.
"""

KIT_MODEL_CONTRACTS_MD = """
## Part `contracts`: delivered projection

Import `{module}/internal/contracts` for the retained computations; the exported-name inventory below lists the
actual delivered API. `internal/contracts/heartbeat` retains its generated family readers. The closed slot-name
and sealing algorithms are retired from this delivery: no Seal/Open, AAD, keyring, envelope or reseal API is supplied.
Only the existing handwritten `b64Canonical` and `LooksSealed` definitions are extracted byte for byte from the
original sealing source into `internal/contracts/delivery_predicates.go`, with their base64/strings closure.
The manifest records the original input SHA and exact definition spans/hashes separately from the delivered file.
Retained keys, record and agent-signature code uses `b64Canonical`; values code uses `LooksSealed`.

Where assigned by the lesson, ordinary generated YOURS `SlotName`, `Sealing` and `ValuesByType` vectoradapter
scaffolds keep their existing signatures and unimplemented errors; the closed contracts adapters do not replace
them. The delivered vector inventory below determines the lesson's targets; no unassigned scaffolds are added.
Other covered vector adapters continue to call retained contracts. Vectors, expectations and command inventory
remain present; an unimplemented adapter does not report success.
"""

KIT_MODEL_MD = """
## Model-launch delivery

This is a tool delivery mode for export P/01, with no new platform part, setting, port, native command or Go ABI.
Box is excluded. Admin and launch are retained pending the Architect's weekly decision (ADR129(29)); their runtime
and flags are unchanged. Generated/editable ownership is recorded per file. Internal regeneration copies are inputs,
not additional delivered algorithms.

Source identity: Platform/COURSE_COMMIT `{source_commit}`. Code identity: `{code_commit}`.
Export identity: `{export_commit}`. Historical identifiers inside public probe files and their README remain intact.

`01-store/publicprobes/` contains exactly four sibling Python programs (`copy_stream.py`, `store_fitness.py`,
`store_probe_http.py`, `store_probes.py`) plus README.md, unchanged from `Platform/01-store/probes` of this export.
These are public observation checkers. They do not start or qualify a provider or establish SUT/production PASS.
From that directory, with PYTHONPATH unset, use `python3.12 -B -m store_probes --list` for the eight-probe inventory
and required bindings. The store_probes entrypoint supports the sibling imports using its own directory; importing
an arbitrary sibling module by an unrelated loader is not the entrypoint contract. No capture means missing inputs
(exit 3); MissingBinding reports absent concrete observations/bindings. OBSERVATION_PASS only judges supplied
observations, with native_executed and production_passed both zero. Budget values and native observation bindings
belong to the acceptance programme. README's historical relative spec links refer to the export's spec tree.
"""

KIT_DOOR_MD = """
## Part `door`: package `apidoor` — the doors of the store from the OpenAPI (generated)

Import path `{module}/internal/apidoor` (package `apidoor`: your own `internal/door`, if any, stays yours), generated by `tools/normgen/gen_door.py` from
`Platform/01-store/spec/01-store.api.openapi.yaml` (`door.go`; `runtime.go` is its handwritten environment). It is the
mechanical part of the doors: what the OpenAPI says as a form. The frame of HTTP, the limits of N2.1, the identity,
the order «frame → route → identity → body» and the store (N3) are yours. Standard library only, Go 1.22.

```go
// Route — the operation by the method and the raw request-target; the path is compared byte for byte.
// An unknown path — 404; a method that is not of its path — 405 where the path declares 405, otherwise 404;
// refusal is ready to send. Ops: OpGet, OpList, OpWrite, OpRights, OpStatus, OpJoin, OpLeave, OpMetrics.
func Route(method, target string) (op Op, query string, refusal *Response)

type Response struct { Code int; Header [][2]string; Body []byte } // send as is (no body for HEAD)

// Handler — you implement it: one method per operation. C is your call context (the role socket, …).
type Handler[C any] interface {
    Get(c C, q GetQuery) Answer       // GetQuery{Key string}
    List(c C, q ListQuery) Answer     // ListQuery{Prefix *string}: nil — absent
    Write(c C, body []byte) Answer    // writecheck.Check the body (Cmd, BatchCmd); op floor — then DecodeFloorCmd
    Rights(c C) Answer
    Status(c C) Answer
    Join(c C, body []byte) Answer     // jsonstrict.Decode, then DecodeJoin
    Leave(c C, body []byte) Answer    // jsonstrict.Decode, then DecodeLeave
    Metrics(c C) Answer               // Metrics200 — text/plain
    QueryRefused(c C, op Op, e *QueryError) Answer
}
// Dispatch parses the query of op by the OpenAPI and calls the method; a query out of form calls QueryRefused.
func Dispatch[C any](h Handler[C], c C, op Op, query string, body []byte) Answer

type QueryError struct { Param string; Reason QueryReason; Schema string; Rule string }
// Reason: QueryAbsent, QueryRepeated (the parameter is not an array), QueryValue (not by the schema of the
// parameter; Schema — its components/schemas name, e.g. "Key"; Rule — "utf8", "minLength", "not", …).
// Which refusal (kind) each gives, the OpenAPI does not say as a form: you decide by the norms.

type Answer struct { Code int; Body Body; RetryAfter *int64 } // nil: absent; otherwise seconds, checked by op schema
// The implementation computes the replay-limit delay; connection-limit responses use exactly 1.
// Encode — the answer on the wire; refuses a code, a schema or a header not declared for op, and a body out of its
// schema (an error: nothing is sent — it is a bug of yours).
func Encode(op Op, a Answer) (*Response, error)
// Refuse — a refusal from kind, the error text and fields (writecheck.Refusal: Code, Kind, Fault) into the one
// declared refusal schema of (op, code) that the object matches.
func Refuse(op Op, code int, kind, msg string, fields map[string]any) (Answer, error)
// AnswerOf — an answer from a JSON value (map[string]any, string, int64, json.Number, …): the one declared schema.
func AnswerOf(op Op, code int, v any) (Answer, error)
// Decode<Schema> — a request body that write-checks.tsv does not judge: FloorCmd, Join, Leave.
func DecodeJoin(v any) (Join, *Violation)
```

Bodies are Go types of the schemas, fields in the order of `properties`; an optional field is a pointer (nil — absent),
a `const` field is not a field (it is always sent), an optional `const` is a `bool`. `Row` is `Row1` (a readable row
`{Items, Index}`), `Row2` (absent: `items: null, index: ""`) or `Row3` (`{Index}` and `unreadable: true`). Faults:
`BadKeyFault{Error}`, `BadRequestFault{Error}`, `ForbiddenFault{Error}`, `ConflictFault{Error, Index}`,
`BatchConflictFault{Error, Key, Index}`, `ExpiredFault`, `EarlyFault`, `GuardFault{Error, Key, Index}`,
`RowTooLargeFault{Error, Key, Size, Limit}`, `BodyTooLargeFault{Error, Limit, Size *int64}`, `UnavailableFault`,
`AmbiguousFault`, `Refused`. Others: `Listing{Keys}`, `Written{Index, Again}`, `Status`, `RightsFile`, `Empty`.
The names of a map are written in the order of UTF-8 bytes. `type: integer` is a JSON number written without a
fraction and an exponent (`1.0` is not an integer).

What the door does NOT do: the byte limit of a key (1024, N1), which `kind` a query refusal is, `HEAD` without a body,
the body limit, the identity and the rights, the store.
"""


COURSE_ENV, EXPORT_ENV = "NORMGEN_KIT_COURSE", "NORMGEN_KIT_EXPORT"
SPECS = Path(os.environ.get("CAMMETA_SPECS", Path.home() / "cammeta-specs"))
# Temporary regeneration order: door and flags precede core and launch, which read their outputs.
REGEN = ("gen_checks.py", "gen_door.py", "gen_flags.py", "gen_refusals.py", "gen_tests.py", "gen_stagetests.py",
         "gen_core.py", "gen_admin.py", "gen_box.py", "gen_launch.py", "gen_families.py")
# Regenerate non-HTTP P/02 by selected parts: P/01-only producers refuse its inputs.
PART_GENS = {"flags": ("gen_flags.py",), "refusals": ("gen_refusals.py",), "stagetests": ("gen_cmdtests.py",),
             "rollout-poll": ("gen_rollout.py",),
             "families": (("gen_families.py", "gen_row_writes.py") if L.key == "03-worker" else ("gen_families.py",)),
             "vectors": (("gen_families.py", "gen_vectors.py")
                         if gen_tests.common_vectors.uses_families(L.key) else ("gen_vectors.py",)),
             "loader": ("gen_manifest.py",),
             "contracts": ("contracts/gen/gen_heartbeat.py",),
             "core": ("gen_versioned_doors.py",),
             **{m: ("gen_machine.py",) for m in MACHINES}, "door": ("gen_door_lesson.py",)}


def regen(parts, *, delivery="internal"):
    """Choose regeneration producers: P/01 retains the complete REGEN order; other lessons select PART_GENS by parts."""
    if L.key == lesson.DEFAULT:
        order = tuple(g for g in REGEN if delivery != "model-launch" or g != "gen_box.py")
        return order + (PART_GENS["contracts"] if "contracts" in parts else ())
    gens = []
    for p in parts:
        if p not in PART_GENS:
            raise KitError(f"--part {p}: no generator of it for lesson {L.key} yet")
        gens += [g for g in PART_GENS[p] if g not in gens]
    return tuple(gens)


# Internal verification profiles, not the future line-delivery roster. The
# queued removal of box/admin/handwritten loader is a separate coordinated change.
PROFILE_PARTS = {
    "p01-1": ("door", "flags", "refusals", "families", "vectors", "stagetests", "core", "admin", "box", "launch", "contracts"),
    "p02": ("flags", "refusals", "families", "vectors", "stagetests", "loader", "rollout-poll", "contracts"),
    "p03": ("flags", "refusals", "families", "vectors", "stagetests", "slot-capture", "contracts"),
    "p04": ("flags", "refusals", "families", "vectors", "stagetests", "slot-fate", "slot-release", "contracts"),
    "p05": ("door", "flags", "refusals", "families", "vectors", "stagetests", "contracts"),
    "p06": ("door", "flags", "refusals", "families", "vectors", "stagetests", "contracts"),
    "p08": ("door", "families", "vectors", "core", "contracts"),
    "p09": ("door", "flags", "refusals", "families", "vectors", "stagetests", "contracts"),
    "p10": ("door", "vectors", "contracts"),
}


def _copy_inputs(stage, inputs, source_root, code_root):
    for group, root in (("code", Path(code_root)), ("source", Path(source_root))):
        directories = []
        for row in inputs[group]:
            target = stage / row["path"]
            if row["type"] == "directory":
                target.mkdir(parents=True, exist_ok=True)
                directories.append((target, row["mode"]))
            else:
                data = (root / row["path"]).read_bytes()
                if sha256(data) != row["sha256"]:
                    raise KitError(f"input changed while materializing {row['path']}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                target.chmod(row["mode"])
        for target, mode in reversed(directories):
            target.chmod(mode)


def _finish_output(parts):
    """Prepare dependencies once; consumption reads these bytes, not vendor/render."""
    if "contracts" in parts:
        source = CONTRACTS / "go"
        files = sorted(source.rglob("*.go"))
        if not files or not (source / "contracts.go").is_file():
            raise KitError("contracts source roster is empty/incomplete")
        heartbeat = gen_heartbeat.render()
        if set(heartbeat) != {"families.go", "runtime.go"}:
            raise KitError("heartbeat projection is empty/incomplete")
        for f in files:
            rel = f.relative_to(source)
            data = heartbeat[f.name].encode() if rel.parts[0] == "heartbeat" and f.name in heartbeat else f.read_bytes()
            target = L.out / "go/contracts" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    vendored = (gen_manifest.vendor(L.go_module) if "loader" in parts else
                gen_policy_machines.vendor(L.go_module) if L.key == "03-worker" and "stagetests" in parts else [])
    for rel, data in vendored:
        target = L.out / "go" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    # Do not seal a set that cannot supply the declared provenance on consumption.
    required = (["writecheck"] if TABLE.is_file() else []) + list(parts)
    provenance(required, [], {})


def prepare(parts=(), *, profiles=None, output_root=None, source_root=ROOT, code_root=ROOT, context=None,
            delivery="internal"):
    """Explicit creation in an empty external root; never repairs an existing set.

    Full verification: prepare(profiles=lesson.PROFILES). A selected/component or
    historical/export set has its own root and identity, never a full-nine claim.
    """
    profiles = lesson._profiles((L.slug,) if profiles is None else profiles)
    output_root = Path(output_root or lesson.output_root())
    if not output_root.is_absolute() or output_root.is_symlink():
        raise KitError("prepared output root must be an absolute regular directory")
    output_root = output_root.resolve()
    if output_root.is_relative_to(Path(code_root).resolve() / "tools/normgen"):
        raise KitError("prepared output must be outside tools/normgen")
    if output_root.exists() and any(output_root.iterdir()):
        raise KitError("output root is not empty; create a new set explicitly")
    context = dict(context or {"kind": "current" if set(profiles) == set(lesson.PROFILES) else "component"})
    if delivery not in DELIVERIES:
        raise KitError(f"unknown delivery {delivery!r}")
    if delivery == "model-launch":
        if profiles != ("p01-1",):
            raise KitError("model-launch preparation supports export P/01 only")
        delivery_identity(source_root, context)
    inputs = lesson.output_inputs(source_root, code_root, kind=context["kind"])
    plans = {}
    for slug in profiles:
        selected = (parts[slug] if isinstance(parts, dict) else parts) or PROFILE_PARTS[slug]
        if not selected or len(selected) != len(set(selected)) or any(p not in PARTS for p in selected):
            raise KitError(f"invalid/empty parts for {slug}")
        plans[slug] = tuple(selected)
        if delivery == "model-launch":
            delivery_request(delivery, output_root, selected, None)
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="normgen-inputs-") as tmp:
        stage = Path(tmp)
        _copy_inputs(stage, inputs, source_root, code_root)
        normgen = stage / "tools/normgen"
        for slug, selected in plans.items():
            nn = "01" if slug == "p01-1" else slug[1:]
            keys = [r.split("\t")[1] for r in (stage / "Platform/lessons.tsv").read_text().split("\n")
                    if r and not r.startswith("#") and r.split("\t")[0] == nn]
            if len(keys) != 1:
                raise KitError(f"no unique source lesson for profile {slug}")
            env = dict(os.environ, NORMGEN_LESSON=keys[0], NORMGEN_OUT=str(output_root), PYTHONDONTWRITEBYTECODE="1")
            code = ("import sys;sys.path.insert(0,'kit');import build_kit as k;"
                    f"parts={selected!r};"
                    "import subprocess;"
                    f"gens=k.regen(parts,delivery={delivery!r});"
                    "\nfor g in gens:\n"
                    " if g=='contracts/gen/gen_heartbeat.py': continue\n"
                    " r=subprocess.run([sys.executable,g],capture_output=True,text=True)\n"
                    " if r.returncode: raise k.KitError(g+': '+(r.stderr or r.stdout))\n"
                    " if k.NORMGEN.joinpath('out').exists(): raise k.KitError(g+': recreated repository out')\n"
                    "k._finish_output(parts)\n")
            done = subprocess.run([sys.executable, "-c", code], cwd=normgen, env=env, capture_output=True, text=True)
            if done.returncode:
                raise KitError(f"prepare {slug}: {(done.stderr or done.stdout).strip()}")
        declared_parts = {slug: list(dict.fromkeys((["writecheck"] if slug == "p01-1" else []) + list(selected)))
                          for slug, selected in plans.items()}
    try:
        return lesson.record_outputs(output_root, source_root=source_root, code_root=code_root,
                                     profiles=profiles, parts=declared_parts, context=context, inputs=inputs)
    except lesson.LessonError as exc:
        raise KitError(str(exc)) from None


def prepared_vendor(module):
    """Read the prepared pinned vendor closure, rewriting only the module name."""
    root = L.out / "go"
    vendor = sorted((root / "vendor").rglob("*"))
    files = [p for p in vendor if p.is_file()]
    if not files or not (root / "vendor/modules.txt").is_file():
        raise KitError("prepared vendor closure is empty/incomplete")
    mod = (root / "go.mod").read_bytes()
    if len(re.findall(rb"(?m)^module .+$", mod)) != 1:
        raise KitError("prepared go.mod must have one module")
    pinned_mod = (ROOT / "Platform/common/versions/go.mod").read_bytes()
    pinned_sum = (ROOT / "Platform/common/versions/go.sum").read_bytes()
    if (re.sub(rb"(?m)^module .+$", b"module versions", mod) != pinned_mod or
            (root / "go.sum").read_bytes() != pinned_sum):
        raise KitError("prepared pinned module inputs changed; prepare a new vendor closure")
    required = re.findall(rb"(?m)^[ \t]*([A-Za-z0-9][^ \t\r\n]*)[ \t]+(v[0-9][^ \t\r\n]*)(?:[ \t]+//[^\n]*)?$", pinned_mod)
    explicit, current = [], None
    for line in (root / "vendor/modules.txt").read_bytes().splitlines():
        if line.startswith(b"# "):
            cells = line[2:].split()
            current = tuple(cells) if len(cells) == 2 else None
        elif line.startswith(b"## ") and b"explicit" in [word.strip() for word in line[3:].split(b";")]:
            explicit.append(current)
    if not required or len(required) != len(set(required)) or len(explicit) != len(set(explicit)) or set(explicit) != set(required):
        raise KitError("prepared vendor explicit module/version roster differs from the pinned module requirements")
    mod = re.sub(rb"(?m)^module .+$", ("module " + module).encode(), mod)
    return [("go.mod", mod), ("go.sum", (root / "go.sum").read_bytes())] + [
        (str(p.relative_to(root)), p.read_bytes()) for p in files]


def git(*args, cwd):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    if done.returncode:
        raise KitError(f"git {' '.join(args)} in {cwd}: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout


def unpack(repo, rev, path, into, exclude=()):
    """Extract committed path bytes from repo/rev into a directory with git archive, without the working tree."""
    tar = git("archive", "--format=tar", rev, "--", path,
              *(":(exclude)" + p for p in exclude), cwd=repo)
    done = subprocess.run(["tar", "-x", "-C", str(into)], input=tar, capture_output=True)
    if done.returncode:
        raise KitError(f"tar: {done.stderr.decode(errors='replace').strip()}")


# Lesson paths in documentation (ADR-0125 addendum 5, item 2); other prose describes P/01.
KIT_MD = KIT_MD.replace("Platform/01-store/", L.rel + "/").replace("`01-store/internal/`", f"`{L.kit_dir}/internal/`")
KIT_DOOR_MD = KIT_DOOR_MD.replace("Platform/01-store/spec/01-store.api.openapi.yaml",
                                  str(L.openapi.relative_to(ROOT)))


KIT_MD_LESSON = """# Kit: the generated parts of {lesson} (Go)

Ready-made Go packages under `{dir}/internal/`, generated from the forms of the lesson (ADR-0125 addendum (5)). The closed
ones are part of your tree, but **do not edit them** (writes there are closed): import and call them. The files marked
**yours** are stubs you edit — the kit puts each once and never overwrites it. `kit.manifest.json` lists every file
with its sha256 and whether it is yours (`editable`). Standard library only, Go 1.22.
"""


def build_from_export(dst, module, parts, judged, export, specs=SPECS, root=ROOT, seed=None, *, delivery="internal"):
    """Build from a clean course HEAD using an export's inputs; seed follows seed_rule. Return the manifest."""
    delivery_request(delivery, dst, parts, seed)
    dst = Path(dst).resolve()
    seed = Path(seed).resolve() if seed is not None else None
    if git("status", "--porcelain", "--", "tools/normgen", cwd=root).strip():
        raise KitError("tools/normgen has uncommitted changes: a kit is built only from a clean commit of the course")
    course = git("rev-parse", "HEAD", cwd=root).decode().strip()
    try:
        sha = git("rev-parse", "--verify", f"{export}^{{commit}}", cwd=specs).decode().strip()
    except KitError as exc:
        raise KitError(f"--export {export}: not a commit of {specs}: {exc}") from None
    if delivery == "model-launch" and sha == LEGACY_EXPORT:
        raise KitError("model-launch delivery refuses the legacy export")
    with tempfile.TemporaryDirectory(prefix="kit-export-") as t, \
            tempfile.TemporaryDirectory(prefix="kit-generated-") as generated:
        stage = Path(t)
        unpack(root, course, "tools/normgen", stage, exclude=("tools/normgen/out",))
        unpack(specs, sha, "Platform", stage)
        gens = stage / "tools/normgen"
        env = dict(os.environ, NORMGEN_OUT=generated, PYTHONDONTWRITEBYTECODE="1",
                   **{COURSE_ENV: course, EXPORT_ENV: sha})
        context = {"kind": "export", "course_commit": course, "export_commit": sha}
        if delivery == "model-launch":
            context["source_pin"] = delivery_identity(stage, context)["source_commit"]
        delivery_arg = f",delivery={delivery!r}" if delivery != "internal" else ""
        creator = ("import os,sys;sys.path.insert(0,'kit');import build_kit as k;"
                   f"k.prepare({tuple(parts)!r},profiles=({L.slug!r},),context={context!r}{delivery_arg});"
                   "print(os.environ[k.lesson.OUTPUT_RECEIPT_ENV])")
        done = subprocess.run([sys.executable, "-c", creator], cwd=gens, env=env, capture_output=True, text=True)
        if done.returncode:
            raise KitError(f"prepare export {sha[:9]}: {(done.stderr or done.stdout).strip()}")
        receipt = done.stdout.removesuffix("\n")
        if re.fullmatch(r"[0-9a-f]{64}", receipt) is None:
            raise KitError("export creator did not return a strict creation receipt")
        env[lesson.OUTPUT_RECEIPT_ENV] = receipt
        cmd = [sys.executable, str(gens / "kit/build_kit.py"), str(dst), "--module", module]
        if delivery != "internal":
            cmd += ["--delivery", delivery]
        cmd += sum((["--part", p] for p in parts), []) + sum((["--judged", f"{k}={v}"] for k, v in judged.items()), [])
        cmd += ["--seed", str(seed)] if seed is not None else []
        done = subprocess.run(cmd, cwd=stage, capture_output=True, text=True, env=env)
        if done.returncode:
            raise KitError((done.stderr or done.stdout).strip())
    manifest = json.loads((dst / "kit.manifest.json").read_text(encoding="utf-8"))
    built = " ".join(["python3 tools/normgen/kit/build_kit.py <kit> --module", module]
                     + [f"--part {p}" for p in parts] + [f"--export {sha}"]
                     + ([f"--delivery {delivery}"] if delivery != "internal" else [])
                     + (["--seed <seed>"] if seed else []))
    sd = manifest.get("seed")
    seeded = (f"seed {seed}: the files of the model kept, not in the kit ({len(sd['kept'])}): {' '.join(sd['kept'])}; "
              f"the untouched stubs of the former kit refreshed ({len(sd['refreshed'])}): {' '.join(sd['refreshed'])}\n"
              if sd else "")
    (dst / "SOURCE.txt").write_text(
        f"export {sha} (cammeta-specs): the inputs — Platform/ of the export, byte for byte (git archive)\n"
        f"course {course} (clean): tools/normgen — the generators, the hand-written kit code; out regenerated on the "
        f"export inputs\nmodule {module}\nparts: {' '.join(manifest['parts'])}\n{seeded}built: {built}\n"
        + (f"delivery {delivery}; source Platform/COURSE_COMMIT {manifest['delivery']['source_commit']}; "
           f"creator prepared manifest SHA256 {receipt}\n"
           "publicprobes: unchanged Platform/01-store/probes from this export; historical embedded pins retained\n"
           if delivery == "model-launch" else ""), encoding="utf-8")
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dst", help=f"the attempt directory (the kit goes to <dst>/{L.kit_dir}/internal)")
    ap.add_argument("--module", default=L.module, help=f"Go import path of <dst>/{L.kit_dir} (default {L.module})")
    ap.add_argument("--lesson", default=L.key, help="the lesson NN-<name> (lesson.py; default 01-store)")
    ap.add_argument("--part", action="append", default=[], choices=PARTS, help="an extra part of the kit")
    ap.add_argument("--judged", action="append", default=[], metavar="PART=REF",
                    help="the judge result of this output of a part (a queue id, a report path) — into provenance")
    ap.add_argument("--export", metavar="SHA", help="the inputs from this commit of cammeta-specs (Platform/), the code "
                    "from the clean HEAD of the course")
    ap.add_argument("--specs", default=str(SPECS), help="the git repository of the exports (default ~/cammeta-specs)")
    ap.add_argument("--delivery", choices=DELIVERIES, default="internal",
                    help="tool-only delivery mode; model-launch requires export P/01 and a new empty destination")
    ap.add_argument("--seed", help="the seed tree (the code of a former attempt with its kit.manifest.json): editable "
                    "files of the model stay out of the kit, untouched stubs of the former kit are refreshed")
    args = ap.parse_args(argv)
    judged = {}
    for j in args.judged:
        part, sep, ref = j.partition("=")
        if not sep or not ref:
            print(f"build_kit: --judged {j!r}: want PART=REF", file=sys.stderr)
            return 1
        judged[part] = ref
    try:
        delivery_request(args.delivery, args.dst, args.part, args.seed)
        if args.delivery == "model-launch" and not args.export and lesson.owns_output_root():
            raise KitError("model-launch needs --export or a supplied prepared export set; no implicit preparation")
        if not args.export and lesson.owns_output_root():
            # CLI creation is explicit here. build() itself only consumes a set.
            # A caller-supplied NORMGEN_OUT is never recreated, even if invalid.
            prepare(tuple(args.part), profiles=(L.slug,))
        manifest = (build_from_export(args.dst, args.module, args.part, judged, args.export, Path(args.specs),
                                      seed=args.seed, delivery=args.delivery)
                    if args.export else build(args.dst, args.module, args.part, judged, args.seed,
                                              delivery=args.delivery))
    except KitError as exc:
        print(f"build_kit: {exc}", file=sys.stderr)
        return 1
    print(f"build_kit: {len(manifest['files'])} files in {args.dst}/{L.kit_dir}/internal; lines {manifest['lines']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
