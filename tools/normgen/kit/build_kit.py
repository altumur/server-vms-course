"""Сборка пакета Б для P/01 (ADR-0083 доп. (86) п. 2): проверки Н2.1 и строгий разборщик JSON — в каталог попытки.

Запуск: python tools/normgen/kit/build_kit.py <dst> --module <путь импорта каталога <dst>/01-store> [--part vectors] [--part stagetests] [--part door]
       [--part flags] [--part refusals]

Кладёт в <dst>/01-store/internal/:
- checks/ — пакет, сгенерированный tools/normgen/gen_checks.py из Platform/01-store/forms/write-checks.tsv (берётся
  из tools/normgen/out/p01-1/go/checks; sha256 таблицы в его шапке должен совпасть с таблицей сейчас);
- jsonstrict/, writecheck/ — ручной пакет tools/normgen/kit/go (в writecheck путь "kitmodule/internal/" заменяется на
  "<module>/internal/").
Часть `flags` (--part flags; генератор № 3 ADR-0125 tools/normgen/gen_flags.py, судья flag_judge.py): flags/
(заменяется целиком), паспорт формы, генератора и судьи — в provenance манифеста.
Часть `refusals` (--part refusals; генератор № 4 ADR-0125 tools/normgen/gen_refusals.py, судья refusal_judge.py):
refusals/ (заменяется целиком), паспорт — в provenance.
Часть `vectors` (--part vectors; ADR-0126 доп. (7) п. 4, генератор № 6 ADR-0125 tools/normgen/gen_tests.py): vectortests/,
vectorcmd/, cmd/vectors (заменяются целиком) и заглушка адаптера vectoradapter/ — её реализация правит, кладётся, только если её нет.
Часть `stagetests` (--part stagetests, нужна часть door; ADR-0125 доп. (3), (4), ADR-0126 доп. (7), gen_stagetests.py, судья
scenario_judge.py): stagetests/ (заменяется целиком) и coreadapter/ — coreadapter.go пакета, open.go реализации (кладётся один раз).
Часть `door` (--part door; генератор № 2 ADR-0125 tools/normgen/gen_door.py): door/ (заменяется целиком) — дверь из
Platform/01-store/spec/01-store.api.openapi.yaml (tools/normgen/out/p01-1/go/apidoor → internal/apidoor, пакет apidoor — не затирает internal/door реализации; sha256 OpenAPI в шапке door.go
должен совпасть с OpenAPI сейчас).
Пишет <dst>/KIT.md (API для модели, английский) и <dst>/kit.manifest.json (пути, sha256, строки, происхождение).
Каталоги checks, jsonstrict, writecheck в <dst>/01-store/internal заменяются целиком; прочее в <dst> не трогается.
"""
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
import gen_tests  # noqa: E402 — часть tests
import gen_flags  # noqa: E402 — часть flags
import gen_refusals  # noqa: E402 — часть refusals
import gen_checks  # noqa: E402 — свежесть writecheck
import gen_door  # noqa: E402 — свежесть door
import gen_launch  # noqa: E402 — часть launch
import gen_core  # noqa: E402 — часть core
TABLE = ROOT / "Platform/01-store/forms/write-checks.tsv"
GENERATED = ROOT / "tools/normgen/out/p01-1/go/checks"
HANDWRITTEN = HERE / "go"
PLACEHOLDER = '"kitmodule/internal/'
MODULE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._~-]*(/[A-Za-z0-9._~-]+)*")

# Файлы пакета checks: (имя, происхождение, исходник в репозитории). runtime.go и prims.go генератор копирует
# из своих ручных файлов; checks.go строит по таблице.
CHECKS_FILES = [
    ("checks.go", "generated", "tools/normgen/out/p01-1/go/checks/checks.go"),
    ("runtime.go", "handwritten", "tools/normgen/runtime/go/runtime.go"),
    ("prims.go", "handwritten", "tools/normgen/prims/go/prims.go"),
]
KIT_FILES = [
    ("jsonstrict", "jsonstrict.go"),
    ("writecheck", "writecheck.go"),
]
# Часть door: door.go строит gen_door.py по OpenAPI, runtime.go — копия его ручной среды.
OPENAPI = ROOT / "Platform/01-store/spec/01-store.api.openapi.yaml"
DOOR = ROOT / "tools/normgen/out/p01-1/go/apidoor"
DOOR_FILES = [
    ("door.go", "generated", "tools/normgen/out/p01-1/go/apidoor/door.go"),
    ("runtime.go", "handwritten", "tools/normgen/doorrt/go/runtime.go"),
]


class KitError(Exception):
    pass


NORMGEN = ROOT / "tools/normgen"


def entry(path):
    path = Path(path)
    return {"path": str(path.relative_to(ROOT)), "sha256": sha256(path.read_bytes())}


def fresh_check(gen, src, sub, names):
    """Весь копируемый выход части равен свежему прогону генератора (ревью Codex С2): шапка формы не доказывает,
    что генератор, его ручная среда (runtime, prims, doorrt) и сам out не менялись. GenError, расхождение — KitError."""
    with tempfile.TemporaryDirectory(prefix="kit-fresh-") as tmp:
        out = Path(tmp) / "p01-1"
        try:
            gen.generate(src, out)
        except gen.GenError as exc:
            raise KitError(f"tools/normgen/{Path(gen.__file__).name}: {exc}") from None
        for name in names:
            kept = NORMGEN / "out/p01-1" / sub / name
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
                                "Platform/01-store/data"], capture_output=True, text=True, check=True).stdout.strip()
        return done.stdout.strip() + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return None


PARTS = ("vectors", "stagetests", "door", "flags", "refusals", "launch", "core")       # части сверх writecheck (имена ADR-0126 доп. (2) п. 1)


EXAMPLES = HERE / "examples"                # пример подключения на часть: Go-файл, его собирает kit/test_kit.py
EXAMPLE_ORDER = ("writecheck", "door", "flags", "refusals", "vectors", "stagetests", "launch")


def connect_md(parts, module):
    """Справка подключения (ADR-0083 доп. (95) п. 2): по примеру на часть — файл kit/examples/<часть>.go, дословно."""
    out = ["", "## Connect: one example per part", "",
           "Read this, not the generated bodies: the signatures above and these examples are the whole API you need. "
           "Each example compiles against this kit (the kit's own test builds them).", ""]
    for part in EXAMPLE_ORDER:
        if part not in parts:
            continue
        text = (EXAMPLES / f"{part}.go").read_text(encoding="utf-8")
        text = text.replace('"kitmodule/internal/', f'"{module}/internal/').split("\n", 2)[2]   # без package example
        out += [f"### `{part}`", "", "```go", text.rstrip("\n"), "```", ""]
    return "\n".join(out)


EXPORTED = re.compile(r"^(?:func ([A-Z]\w*)|func \([^)]*\) [A-Z]\w*|type ([A-Z]\w*)|(?:var|const) ([A-Z]\w*))", re.M)
BLOCK = re.compile(r"^(?:var|const) \(\n(.*?)^\)", re.M | re.S)


def exported_md(internal, dst, module):
    """Экспортируемые имена каждого пакета пакета Б (по исходникам, не по памяти): функции, типы, переменные, константы."""
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
            rel = pkg.relative_to(Path(dst) / "01-store")
            out.append(f"- `{module}/{rel}`: " + ", ".join(f"`{n}`" for n in sorted(names)))
    return "\n".join(out) + "\n"


def provenance(parts, files, judged):
    """Паспорт частей (ADR-0125 доп. (1) п. 6 (а); ревью Codex С2): формы, генератор, ручная среда, судья — пути и
    sha256; output — sha256 набора скопированных файлов части (путь и sha256 каждого, по порядку), judged — ссылка на
    результат суда этого выхода (--judged часть=ссылка; без неё — null: суд не назван)."""
    def output(*components):
        own = sorted((f["path"], f["sha256"]) for f in files if f["component"] in components and not f.get("editable"))
        return sha256("".join(f"{p}\t{h}\n" for p, h in own).encode())
    table = {
        "writecheck": (("normgen", "kit"), {"form": [TABLE], "generator": NORMGEN / "gen_checks.py",
                                   "handwritten": [NORMGEN / "runtime/go/runtime.go", NORMGEN / "prims/go/prims.go"]
                                   + [HANDWRITTEN / sub / name for sub, name in KIT_FILES],
                                   "judge": NORMGEN / "test_gen_checks.py"}),
        "door": (("door",), {"form": [OPENAPI], "generator": NORMGEN / "gen_door.py",
                          "handwritten": [NORMGEN / "doorrt/go/runtime.go"], "judge": NORMGEN / "door_judge.py"}),
        "vectors": (("vectors",), {"form": [ROOT / "Platform/01-store/forms/stages.tsv"],
                                "generator": NORMGEN / "gen_tests.py", "judge": NORMGEN / "vector_judge.py"}),
        "stagetests": (("stagetests",), {"form": [ROOT / "Platform/01-store/forms/stages.tsv",
                                               ROOT / "Platform/01-store/acceptance/1/scenarios.tsv",
                                               ROOT / "Platform/01-store/acceptance/1/seams.tsv"],
                                      "generator": NORMGEN / "gen_stagetests.py",
                                      "judge": NORMGEN / "scenario_judge.py"}),
    }
    out = {}
    for part in parts:
        if part in ("flags", "refusals", "launch", "core"):
            mod = {"flags": gen_flags, "refusals": gen_refusals, "launch": gen_launch, "core": gen_core}[part]
            out[part] = {**mod.provenance(), "output": output(part)}
        else:
            component, t = table[part]
            out[part] = {"form": [entry(f) for f in t["form"] if f.is_file()], "generator": entry(t["generator"]),
                         "handwritten": [entry(f) for f in t.get("handwritten", [])], "judge": entry(t["judge"]),
                         "output": output(*component)}
        out[part]["judged"] = judged.get(part)
    return out


def build(dst, module, parts=(), judged=None):
    dst = Path(dst)
    if set(judged or {}) - set(("writecheck",) + PARTS):
        raise KitError(f"--judged: unknown parts {sorted(set(judged) - set(('writecheck',) + PARTS))}")
    if not MODULE.fullmatch(module) or "//" in module or module.endswith("/"):
        raise KitError(f"--module {module!r} is not a Go import path")
    table_sha = sha256(TABLE.read_bytes())
    fresh_check(gen_checks, TABLE, "go/checks", [n for n, _, _ in CHECKS_FILES])
    if set(parts) - set(PARTS):
        raise KitError(f"--part {sorted(set(parts) - set(PARTS))}: one of {list(PARTS)}")
    if "stagetests" in parts and "door" not in parts:
        raise KitError("--part stagetests needs --part door: the stage tests go through coreadapter over apidoor "
                       "(ADR-0126 addendum (7) item 5)")
    if "launch" in parts and not {"door", "flags", "stagetests"} <= set(parts):
        raise KitError("--part launch needs --part door, --part flags and --part stagetests: the frame parses by flags "
                       "and serves coreadapter.Handle over apidoor (ADR-0083 addendum (95) item 3)")
    if "core" in parts and not {"door", "stagetests"} <= set(parts):
        raise KitError("--part core needs --part door and --part stagetests: the core is the coreadapter.Core of the "
                       "stage tests over apidoor.Handler (ADR-0083 addendum (95) item 3)")
    kit_parts = ["writecheck", *sorted(set(parts))]
    parts_set = list(kit_parts)
    try:
        tests = [(f, "vectors") for f in gen_tests.kit_files(module, "vectors")] if "vectors" in parts else []
        tests += [(f, "stagetests") for f in gen_tests.kit_files(module, "stagetests")] if "stagetests" in parts else []
        flag_files = gen_flags.kit_files() if "flags" in parts else []
        refusal_files = gen_refusals.kit_files() if "refusals" in parts else []
        launch_files = gen_launch.kit_files(module) if "launch" in parts else []
        core_files = gen_core.kit_files(module) if "core" in parts else []
    except (gen_tests.GenError, gen_flags.GenError, gen_refusals.GenError, gen_launch.GenError,
            gen_core.GenError) as exc:
        raise KitError(str(exc)) from None
    openapi_sha = sha256(OPENAPI.read_bytes()) if "door" in parts else None
    if openapi_sha:
        fresh_check(gen_door, OPENAPI, "go/apidoor", [n for n, _, _ in DOOR_FILES])
    internal = dst / "01-store/internal"
    files = []

    def put(rel_dir, name, data, origin, component, source):
        target = Path(os.path.normpath(internal / rel_dir / name))      # ../cmd/vectors — рядом с internal
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files.append({"path": str(target.relative_to(dst)), "sha256": sha256(data), "lines": lines(data),
                      "origin": origin, "component": component, "source": source})

    for sub in ("checks", "jsonstrict", "writecheck") + sum((gen_tests.PART_DIRS[p] for p in ("vectors", "stagetests") if p in parts), ()) + \
            (("apidoor",) if openapi_sha else ()) + (gen_flags.KIT_DIRS if flag_files else ()) + \
            (gen_refusals.KIT_DIRS if refusal_files else ()) + (("launch",) if launch_files else ()):
        if Path(os.path.normpath(internal / sub)).exists():
            shutil.rmtree(os.path.normpath(internal / sub))
    for name, origin, source in CHECKS_FILES:
        put("checks", name, (GENERATED / name).read_bytes(), origin, "normgen", source)
    for sub, name in KIT_FILES:
        data = (HANDWRITTEN / sub / name).read_bytes()
        if PLACEHOLDER.encode() in data:
            data = data.replace(PLACEHOLDER.encode(), f'"{module}/internal/'.encode())
        elif sub == "writecheck":
            raise KitError(f"{sub}/{name}: no import {PLACEHOLDER}… to rewrite")
        put(sub, name, data, "handwritten", "kit", str((HANDWRITTEN / sub / name).relative_to(ROOT)))

    for (sub, name, data, origin, source, own), component in tests:
        if core_files and (sub, name) == ("coreadapter", "open.go"):
            continue                    # open.go — у части core: Open уже возвращает её ядро
        if own and (internal / sub / name).exists():
            continue                    # адаптер реализации не трогается
        put(sub, name, data, origin, component, source)
        if own:
            files[-1]["editable"] = True
    if openapi_sha:
        for name, origin, source in DOOR_FILES:
            put("apidoor", name, (DOOR / name).read_bytes(), origin, "door", source)
    for sub, name, data, origin, source in flag_files:
        put(sub, name, data, origin, "flags", source)
    for sub, name, data, origin, source in refusal_files:
        put(sub, name, data, origin, "refusals", source)
    for sub, name, data, origin, source, own in launch_files:
        if own and Path(os.path.normpath(internal / sub / name)).exists():
            continue                    # main.go реализации не трогается
        put(sub, name, data, origin, "launch", source)
        if own:
            files[-1]["editable"] = True
    for sub, name, data, origin, source, own in core_files:
        if (internal / sub / name).exists():
            continue                    # ядро реализации не трогается
        put(sub, name, data, origin, "core", source)
        files[-1]["editable"] = True
    doc = (KIT_MD + (gen_tests.KIT_MD if "vectors" in parts else "")
           + (gen_tests.KIT_MD_STAGETESTS if "stagetests" in parts else "") + (KIT_DOOR_MD if openapi_sha else "")
           + (gen_flags.KIT_MD if flag_files else "") + (gen_refusals.KIT_MD if refusal_files else "")
           + (gen_launch.KIT_MD if launch_files else "") + (gen_core.KIT_MD if core_files else "")).replace("{module}", module)
    doc = (doc + connect_md(kit_parts, module) + exported_md(internal, dst, module)).encode("utf-8")
    (dst / "KIT.md").write_bytes(doc)
    # Паспорт попытки (доп. (86) п. 3) считает порознь: по происхождению (generated | handwritten) и по части
    # (normgen — генератор с его ручной средой runtime.go, prims.go; kit — ручной пакет jsonstrict, writecheck).
    totals, parts = {}, {}
    for f in files:
        totals[f["origin"]] = totals.get(f["origin"], 0) + f["lines"]
        parts[f["component"]] = parts.get(f["component"], 0) + f["lines"]
    manifest = {
        "kit": "P/01 pack B (ADR-0083 amendment 86): Н2.1 write checks and strict JSON body parser, Go",
        "module": module,
        "parts": kit_parts,
        "commit": git_head(),
        "table": {"path": str(TABLE.relative_to(ROOT)), "sha256": table_sha},
        "files": files,
        "provenance": provenance(parts_set, files, judged or {}),
        "doc": {"path": "KIT.md", "sha256": sha256(doc), "lines": lines(doc)},
        "lines": totals,
        "lines_by_component": parts,
    }
    if openapi_sha:
        manifest["openapi"] = {"path": str(OPENAPI.relative_to(ROOT)), "sha256": openapi_sha}
    (dst / "kit.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
    return manifest


KIT_MD = """# Kit: write checks of P/01.1 Н2.1 (Go)

Ready-made Go packages under `01-store/internal/`. They are part of your tree, but **do not edit them** (writes there are
closed): import and call them. `kit.manifest.json` lists every file with its sha256.

| Package | Import path | Origin |
|---|---|---|
| `writecheck` | `{module}/internal/writecheck` | handwritten: parser + checks in one call — **use this** |
| `jsonstrict` | `{module}/internal/jsonstrict` | handwritten: the strict JSON parser of Н2.1 |
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

- `body` — the whole decoded body bytes. Call it only after the HTTP framing and the body limit of Н2.1 (`413` before the
  body is parsed); the kit does not read HTTP.
- `sock` — the role of the caller's socket (P/01.2 Н1.1 identity): `admin`, `console`, `domain` or a role name.
- `lim` — the lesson values of `BATCH_WRITES`, `BATCH_GUARDS`, `ROW_CEILING` (P/01.1 Н1). A missing name panics
  (a code error, not an input error). `JSON_DEPTH` is fixed by Н2.1 (128) and is not taken from `lim`.
- `allowed(sock, op, key)` — the rights of P/01.2 Н3 «проверить», `op` is `read`, `write` or `delete`. You implement it;
  the kit calls it for the target key and for guard keys. `nil` panics.

Result:

- `(*Refusal, nil)` with `N == 0` — the body is not JSON by Н2.1 (a repeated field name at any level, `NaN`,
  `Infinity`, a BOM, not UTF-8, deeper than 128, any RFC 8259 syntax error): always `400 badrequest`.
- `(*Refusal, body)` with `N > 0` — the first violated row of the table. Answer `Code` with the JSON body
  `{"kind": Kind}` plus every field of `Fault` (for `413 toolarge`: `limit`, `key`, `size`). Nothing is written.
- `(nil, body)` — every check passed: execute the command by Н3 with `body`.

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
- `op: floor` passes the table on the `admin` socket only (row 3); everything after that is P/01.3 Н2 — yours.

## What the kit does NOT do

- HTTP: the request line, headers, routes, methods, `Content-Length` / chunked framing, the body limit, the early
  refusal and drain, the query of `GET /v1/get` and `GET /v1/list` (all Н2.1 — yours).
- The store state (Н3): `cas` and `guard` compared with the stored rows, the `id` memory and its answers, admission
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


KIT_DOOR_MD = """
## Part `door`: package `apidoor` — the doors of the store from the OpenAPI (generated)

Import path `{module}/internal/apidoor` (package `apidoor`: your own `internal/door`, if any, stays yours), generated by `tools/normgen/gen_door.py` from
`Platform/01-store/spec/01-store.api.openapi.yaml` (`door.go`; `runtime.go` is its handwritten environment). It is the
mechanical part of the doors: what the OpenAPI says as a form. The frame of HTTP, the limits of Н2.1, the identity,
the order «frame → route → identity → body» and the store (Н3) are yours. Standard library only, Go 1.22.

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

What the door does NOT do: the byte limit of a key (1024, Н1), which `kind` a query refusal is, `HEAD` without a body,
the body limit, the identity and the rights, the store.
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dst", help="the attempt directory (the kit goes to <dst>/01-store/internal)")
    ap.add_argument("--module", required=True, help="Go import path of <dst>/01-store")
    ap.add_argument("--part", action="append", default=[], choices=PARTS, help="an extra part of the kit")
    ap.add_argument("--judged", action="append", default=[], metavar="PART=REF",
                    help="the judge result of this output of a part (a queue id, a report path) — into provenance")
    args = ap.parse_args(argv)
    judged = {}
    for j in args.judged:
        part, sep, ref = j.partition("=")
        if not sep or not ref:
            print(f"build_kit: --judged {j!r}: want PART=REF", file=sys.stderr)
            return 1
        judged[part] = ref
    try:
        manifest = build(args.dst, args.module, args.part, judged)
    except KitError as exc:
        print(f"build_kit: {exc}", file=sys.stderr)
        return 1
    print(f"build_kit: {len(manifest['files'])} files in {args.dst}/01-store/internal; lines {manifest['lines']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
