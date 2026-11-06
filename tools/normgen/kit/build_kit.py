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
    with tempfile.TemporaryDirectory(prefix="kit-fresh-") as tmp:
        out = Path(tmp) / L.slug
        try:
            gen.generate(src, out)
        except gen.GenError as exc:
            raise KitError(f"tools/normgen/{Path(gen.__file__).name}: {exc}") from None
        for name in names:
            kept = NORMGEN / "out" / L.slug / sub / name
            new = (out / sub / name).read_bytes()
            if not kept.is_file() or kept.read_bytes() != new:
                raise KitError(f"{kept} differs from a fresh run of tools/normgen/"
                               f"{Path(gen.__file__).name} (the form, the generator or its handwritten environment "
                               f"changed, or out was edited): run the generator")


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


def connect_md(parts, module, constants=None):
    """Read each part's connection example verbatim from kit/examples/<part>.go (ADR-0083 addendum 95, item 2)."""
    out = ["", "## Connect: one example per part", "",
           "Read this, not the generated bodies: the signatures above and these examples are the whole API you need. "
           "Each example compiles against this kit (the kit's own test builds them).", ""]
    for part in EXAMPLE_ORDER:
        if part not in parts:
            continue
        text = (EXAMPLES / f"{part}.go").read_text(encoding="utf-8")
        if part == "writecheck":
            text = gen_flags.bind_p01(text, "example", constants is not None, error=KitError)
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
    consts = ROOT / gen_flags.P01_CONSTANTS
    const_sources = (gen_checks.tsv_input.source_files(consts, root=ROOT)
                     if L.key == lesson.DEFAULT and consts.is_file() else [])
    const_generators = [NORMGEN / "gen_flags.py"] if const_sources else []
    table = {
        "writecheck": (("normgen", "kit"), {"form": (gen_checks.tsv_input.source_files(TABLE, root=ROOT) if TABLE.is_file() else []) + const_sources,
                                   "generator": NORMGEN / "gen_checks.py",
                                   "generators": [NORMGEN / "gen_checks.py", NORMGEN / "tsv_input.py"] + const_generators,
                                   "handwritten": [NORMGEN / "runtime/go/runtime.go", NORMGEN / "prims/go/prims.go"]
                                   + [HANDWRITTEN / sub / name for sub, name in KIT_FILES],
                                   "judge": NORMGEN / "test_gen_checks.py"}),
        "door": (("door",), {"form": [OPENAPI], "generator": NORMGEN / "gen_door.py",
                          "handwritten": [NORMGEN / "doorrt/go/runtime.go"], "judge": NORMGEN / "door_judge.py"}),
        "vectors": (("vectors",), {"form": gen_tests.sources("vectors") if L.key == lesson.DEFAULT else [L.form("stages.tsv")],
                                "generator": NORMGEN / "gen_tests.py",
                                "generators": [NORMGEN / p for p in ("gen_tests.py", "gen_stagetests.py", "gen_cmdtests.py",
                                                                    "gen_checks.py", "common_vectors.py", "wire.py",
                                                                    "vector_consumers.py", "tsv_input.py", "gate.py")] + const_generators,
                                "judge": NORMGEN / "vector_judge.py"}),
        "stagetests": (("stagetests",), {"form": gen_tests.sources("stagetests") if L.key == lesson.DEFAULT else [L.form("stages.tsv"),
                                               L.path("acceptance/1/scenarios.tsv"),
                                               L.path("acceptance/1/seams.tsv"),
                                               L.path("acceptance/3/seams.tsv")],
                                      "generator": NORMGEN / "gen_stagetests.py",
                                      "generators": [NORMGEN / p for p in ("gen_stagetests.py", "gen_tests.py", "gen_checks.py",
                                                                          "gen_cmdtests.py", "tsv_input.py", "gate.py")],
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


def build(dst, module, parts=(), judged=None, seed=None):
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
    try:
        constants = gen_flags.p01_constants(ROOT) if has_wc and L.key == lesson.DEFAULT else None
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
        loader_root = gen_manifest.vendor(module) if "loader" in parts else []
        policy_root = gen_policy_machines.vendor(module) if L.key == "03-worker" and "stagetests" in parts else []
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
        if sub == "jsonstrict":
            data = gen_flags.bind_p01(data.decode(), sub, constants is not None, error=KitError).encode()
        if PLACEHOLDER.encode() in data:
            data = data.replace(PLACEHOLDER.encode(), f'"{module}/internal/'.encode())
        elif sub == "writecheck":
            raise KitError(f"{sub}/{name}: no import {PLACEHOLDER}… to rewrite")
        put(sub, name, data, "handwritten", "kit", str((HANDWRITTEN / sub / name).relative_to(ROOT)))
    if constants is not None:
        put("jsonstrict", "constants.go", constants.encode(), "generated", "kit", "tools/normgen/gen_flags.py")

    contract_adapters = {}
    if "contracts" in parts:                           # Shared contracts package and its vector adapters.
        for name, text in gen_heartbeat.render().items():
            path = CONTRACTS / "go/heartbeat" / name
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                raise KitError("contracts heartbeat is stale: run contracts/gen/gen_heartbeat.py")
        for f in sorted((CONTRACTS / "go").rglob("*.go")):
            data = f.read_bytes()       # nfkc_tables.go comes from contracts/gen/gen_nfkc.py (Unicode15.0.0).
            origin = "generated" if data.startswith(b"// Code generated") else "handwritten"
            put("contracts", str(f.relative_to(CONTRACTS / "go")), data, origin, "contracts", str(f.relative_to(ROOT)))
        for f in sorted((CONTRACTS / "adapters").glob("*.go")):
            fn = re.search(r"^func ([A-Z]\w*)\((?:table|input|file|raw)\b", f.read_text(), re.M)[1]
            contract_adapters[f"{fn.lower()}.go"] = f
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
    stagetests_md = (gen_tests.KIT_MD_STAGETESTS if http else gen_cmdtests.KIT_MD) if "stagetests" in parts else ""
    if policy_root:
        stagetests_md += gen_policy_machines.KIT_MD
    base_md = KIT_MD
    if constants is not None:
        base_md = (base_md.replace("fixed by N2.1 (128)", "fixed by `forms/runtime-constants.tsv` (`jsonstrict.JsonDepth`)")
                   .replace("deeper than 128", "deeper than `jsonstrict.JsonDepth`")
                   .replace("const jsonstrict.Depth = 128", "const jsonstrict.Depth = jsonstrict.JsonDepth"))
        base_md += ("\n`jsonstrict/constants.go` is generated by the existing runtime-constants class from "
                    "`forms/runtime-constants.tsv`: `JsonDepth`, `HeaderBytes`, `BatchWrites`, `BatchGuards`. "
                    "They are norm values, never environment settings. The base writecheck part includes them "
                    "without requiring part flags; `flags` projects the same form when selected.\n")
    doc = ((base_md if has_wc else KIT_MD_LESSON.replace("{lesson}", L.code).replace("{dir}", L.kit_dir))
           + ((gen_tests.kit_md() if L.key == lesson.DEFAULT else gen_vectors.KIT_MD) if "vectors" in parts else "")
           + stagetests_md + (gen_rollout.KIT_MD if rollout_files else "") + (KIT_DOOR_MD if openapi_sha else "")
           + (gen_door_lesson.kit_md() if door_lesson else "")
           + (gen_flags.kit_md() if flag_files else "") + (gen_refusals.kit_md() if refusal_files else "")
           + (gen_families.kit_md() if family_files else "") + (gen_admin.kit_md() if admin_files else "")
           + (gen_row_writes.KIT_MD if family_files and gen_row_writes.enabled() else "")
           + (gen_box.kit_md() if box_files else "")
           + (gen_manifest.kit_md() if loader_files else "")
           + (gen_launch.kit_md() if launch_files else "")
           + ((gen_versioned_doors if L.key == "08-domain" else gen_core).KIT_MD if core_files else "")
           + "".join(gen_machine.kit_md(p) for p in sorted(set(parts) & set(MACHINES)))
           + (KIT_CONTRACTS_MD if "contracts" in parts else "")).replace("{module}", module)
    if policy_root:
        doc = doc.replace("Standard library only, Go 1.22.", "Go 1.22; the closed policies use vendored cel-go v0.26.1 from Platform/common/versions.")
    connect = connect_md(kit_parts, module, constants) if L.key == lesson.DEFAULT else ""   # Part examples are P/01 code.
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

type Answer struct { Code int; Body Body; RetryAfter bool } // RetryAfter — the header Retry-After: 1 where declared
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
             "vectors": ("gen_families.py", "gen_vectors.py"), "loader": ("gen_manifest.py",),
             "contracts": ("contracts/gen/gen_heartbeat.py",),
             "core": ("gen_versioned_doors.py",),
             **{m: ("gen_machine.py",) for m in MACHINES}, "door": ("gen_door_lesson.py",)}


def regen(parts):
    """Choose regeneration producers: P/01 retains the complete REGEN order; other lessons select PART_GENS by parts."""
    if L.key == lesson.DEFAULT:
        return REGEN + (PART_GENS["contracts"] if "contracts" in parts else ())
    gens = []
    for p in parts:
        if p not in PART_GENS:
            raise KitError(f"--part {p}: no generator of it for lesson {L.key} yet")
        gens += [g for g in PART_GENS[p] if g not in gens]
    return tuple(gens)


def git(*args, cwd):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    if done.returncode:
        raise KitError(f"git {' '.join(args)} in {cwd}: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout


def unpack(repo, rev, path, into):
    """Extract committed path bytes from repo/rev into a directory with git archive, without the working tree."""
    tar = git("archive", "--format=tar", rev, "--", path, cwd=repo)
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


def build_from_export(dst, module, parts, judged, export, specs=SPECS, root=ROOT, seed=None):
    """Build from a clean course HEAD using an export's inputs; seed follows seed_rule. Return the manifest."""
    dst = Path(dst).resolve()
    seed = Path(seed).resolve() if seed is not None else None
    if git("status", "--porcelain", "--", "tools/normgen", cwd=root).strip():
        raise KitError("tools/normgen has uncommitted changes: a kit is built only from a clean commit of the course")
    course = git("rev-parse", "HEAD", cwd=root).decode().strip()
    try:
        sha = git("rev-parse", "--verify", f"{export}^{{commit}}", cwd=specs).decode().strip()
    except KitError as exc:
        raise KitError(f"--export {export}: not a commit of {specs}: {exc}") from None
    with tempfile.TemporaryDirectory(prefix="kit-export-") as t:
        stage = Path(t)
        unpack(root, course, "tools/normgen", stage)
        unpack(specs, sha, "Platform", stage)
        if git("ls-tree", "--name-only", sha, "Source/tests/testdata", cwd=specs).strip():
            unpack(specs, sha, "Source/tests/testdata", stage)   # Course manifests referenced by vectors (P/02 canonical).
        gens = stage / "tools/normgen"
        for g in regen(parts):
            done = subprocess.run([sys.executable, g], cwd=gens, capture_output=True, text=True)
            if done.returncode:
                raise KitError(f"{g} on the export {sha[:9]}: {(done.stderr or done.stdout).strip()[-2000:]}")
        cmd = [sys.executable, str(gens / "kit/build_kit.py"), str(dst), "--module", module]
        cmd += sum((["--part", p] for p in parts), []) + sum((["--judged", f"{k}={v}"] for k, v in judged.items()), [])
        cmd += ["--seed", str(seed)] if seed is not None else []
        env = dict(os.environ, **{COURSE_ENV: course, EXPORT_ENV: sha})
        done = subprocess.run(cmd, cwd=stage, capture_output=True, text=True, env=env)
        if done.returncode:
            raise KitError((done.stderr or done.stdout).strip())
    manifest = json.loads((dst / "kit.manifest.json").read_text(encoding="utf-8"))
    built = " ".join(["python3 tools/normgen/kit/build_kit.py <kit> --module", module]
                     + [f"--part {p}" for p in parts] + [f"--export {sha}"] + (["--seed <seed>"] if seed else []))
    sd = manifest.get("seed")
    seeded = (f"seed {seed}: the files of the model kept, not in the kit ({len(sd['kept'])}): {' '.join(sd['kept'])}; "
              f"the untouched stubs of the former kit refreshed ({len(sd['refreshed'])}): {' '.join(sd['refreshed'])}\n"
              if sd else "")
    (dst / "SOURCE.txt").write_text(
        f"export {sha} (cammeta-specs): the inputs — Platform/ of the export, byte for byte (git archive)\n"
        f"course {course} (clean): tools/normgen — the generators, the hand-written kit code; out regenerated on the "
        f"export inputs\nmodule {module}\nparts: {' '.join(manifest['parts'])}\n{seeded}built: {built}\n", encoding="utf-8")
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
        manifest = (build_from_export(args.dst, args.module, args.part, judged, args.export, Path(args.specs),
                                      seed=args.seed)
                    if args.export else build(args.dst, args.module, args.part, judged, args.seed))
    except KitError as exc:
        print(f"build_kit: {exc}", file=sys.stderr)
        return 1
    print(f"build_kit: {len(manifest['files'])} files in {args.dst}/{L.kit_dir}/internal; lines {manifest['lines']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
