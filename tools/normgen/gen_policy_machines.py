"""Closed declarative policies in P/03 stagetests; no SDK effects or new kit part.

The YAML is compiled to an ordered JSON IR. policyrt executes that IR with the
course's pinned CEL implementation. The old TSV machines use gen_machine.py.
"""
import argparse
import copy
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path

import yaml
import lesson
import machine_source

from gen_checks import go_str, gofmt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LESSON = "Platform/03-worker"
RUNTIME = HERE / "policyrt/go"
PARTS = ("contender-writer", "token-cache")
REQUIRED = set("machine norm states initial terminal input types const vars timers events env functions actions invariants transitions".split())
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
NAME = re.compile(r"[a-z][a-z0-9_-]*\Z")
RESERVED = {"input", "vars", "const", "now", "s0", "state"}


class GenError(ValueError):
    pass


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_map(loader, node):
    out = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str) or key in out:
            raise GenError(f"YAML map: repeated or non-string key {key!r}")
        out[key] = loader.construct_object(value_node, deep=True)
    return out


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_map)


def strict_json(text):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise GenError(f"duplicate JSON key {key!r}")
            out[key] = value
        return out
    try:
        v = json.loads(text, object_pairs_hook=pairs,
                       parse_constant=lambda n: (_ for _ in ()).throw(GenError(f"non-JSON number {n}")))
        finite_json(v)
        return v
    except (ValueError, UnicodeError) as exc:
        raise GenError(f"invalid finite Unicode JSON: {exc}") from None


def finite_json(value):
    if value is None or type(value) in (bool, int):
        return
    if isinstance(value, str):
        value.encode("utf-8")
    elif isinstance(value, float) and math.isfinite(value):
        return
    elif isinstance(value, list):
        for v in value:
            finite_json(v)
    elif isinstance(value, dict) and all(isinstance(k, str) for k in value):
        for k, v in value.items():
            finite_json(k)
            finite_json(v)
    else:
        raise GenError("not a finite JSON value")


def split_top(text, delimiter):
    out, start, stack, quote, escape = [], 0, [], None, False
    for i, ch in enumerate(text):
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in "([{<" and (delimiter == "|" or ch != "<"):
            stack.append(ch)
        elif ch in ")]}" or (ch == ">" and delimiter == "|"):
            if not stack:
                raise GenError("unbalanced expression/type")
            stack.pop()
        elif ch == delimiter and not stack:
            out.append(text[start:i].strip())
            start = i + 1
    if quote or stack:
        raise GenError("unbalanced expression/type")
    return out + [text[start:].strip()]


def known_type(typ, types, seen=()):
    if not isinstance(typ, str):
        return False
    choices = split_top(typ, "|")
    if len(choices) > 1:
        return all(known_type(x, types, seen) for x in choices)
    if typ in {"bool", "boolean", "int", "integer", "double", "number", "string", "dyn", "null", "object", "array"}:
        return True
    if typ.startswith("list<") and typ.endswith(">"):
        return known_type(typ[5:-1], types, seen)
    if typ.startswith("map<string,") and typ.endswith(">"):
        return known_type(typ[11:-1].strip(), types, seen)
    return typ in types and typ not in seen and isinstance(types[typ], dict) and all(
        known_type(t, types, (*seen, typ)) for t in types[typ].values())


def typed(value, typ, types):
    finite_json(value)
    choices = split_top(typ, "|")
    if len(choices) > 1:
        for t in choices:
            try:
                return typed(value, t, types)
            except (GenError, ValueError):
                pass
        raise GenError(f"expected {typ}")
    if typ == "dyn" or (typ == "null" and value is None):
        return copy.deepcopy(value)
    if typ in ("bool", "boolean") and type(value) is bool:
        return value
    if typ in ("int", "integer") and type(value) is int and -(2**63) <= value < 2**63:
        return value
    if typ in ("double", "number") and type(value) in (int, float):
        try:
            f = float(value)
        except OverflowError:
            f = float("inf")
        if math.isfinite(f):
            return f if typ == "double" else value
    if typ == "string" and isinstance(value, str):
        return value
    if (typ == "object" and isinstance(value, dict)) or (typ == "array" and isinstance(value, list)):
        return copy.deepcopy(value)
    if typ.startswith("list<") and typ.endswith(">") and isinstance(value, list):
        return [typed(v, typ[5:-1], types) for v in value]
    if typ.startswith("map<string,") and typ.endswith(">") and isinstance(value, dict):
        return {k: typed(v, typ[11:-1].strip(), types) for k, v in value.items()}
    if typ in types and isinstance(value, dict) and set(value) == set(types[typ]):
        return {k: typed(value[k], t, types) for k, t in types[typ].items()}
    raise GenError(f"expected {typ}")


def fields(declarations, types, where, *, record=False):
    if not isinstance(declarations, dict):
        raise GenError(f"{where}: expected a typed field map")
    for n, t in declarations.items():
        if not isinstance(n, str) or (not record and (not IDENT.fullmatch(n) or n in RESERVED)) or not known_type(t, types):
            raise GenError(f"{where}: invalid field/type {n!r}: {t!r}")
        finite_json(n)
    return [{"name": n, "type": t} for n, t in declarations.items()]


def _model(doc, where="machine"):
    """Validate declarations and preserve every order with semantic significance."""
    def require(ok, message):
        if not ok:
            raise GenError(f"{where}: {message}")
    require(isinstance(doc, dict) and set(doc) == REQUIRED, "expected exactly the declared machine sections")
    for section in ("input", "types", "const", "vars", "timers", "events", "functions", "actions", "invariants"):
        require(isinstance(doc[section], dict), f"{section} must be a map")
    for section in ("states", "terminal", "env", "transitions"):
        require(isinstance(doc[section], list), f"{section} must be a list")
    states, terminal, types = doc["states"], doc["terminal"], doc["types"]
    require(states and all(isinstance(s, str) and NAME.fullmatch(s) for s in states) and len(set(states)) == len(states), "unique closed states")
    require(doc["initial"] in states and all(s in states for s in terminal) and len(set(terminal)) == len(terminal), "initial/terminal states")
    require(isinstance(doc["machine"], str) and NAME.fullmatch(doc["machine"]), "closed machine name")
    require(isinstance(doc["norm"], str) and doc["norm"], "nonempty norm")
    require(all(isinstance(x, str) for x in doc["env"]), "env contains prose strings")
    require(not set(doc["functions"]) - {"same_set"}, "only the declared same_set extension is supported")
    for name in {*types, *doc["const"], *doc["vars"], *doc["actions"]}:
        require(IDENT.fullmatch(name), f"invalid identifier {name!r}")
    for name in types:
        require(known_type(name, types), f"invalid/recursive record type {name}")
        fields(types[name], types, f"type {name}", record=True)
    require(not (set(doc["vars"]) & set(doc["const"])) and not ((set(doc["vars"]) | set(doc["const"])) & RESERVED), "reserved/repeated globals")
    finite_json(doc["const"])
    ir = {k: doc[k] for k in ("machine", "norm", "states", "initial", "terminal", "const", "env")}
    ir["types"] = {n: fields(d, types, f"type {n}", record=True) for n, d in types.items()}
    ir["input"] = fields(doc["input"], types, "input")
    ir["functions"] = list(doc["functions"])
    ir["vars"] = []
    for name, v in doc["vars"].items():
        require(isinstance(v, dict) and set(v) == {"type", "init"} and known_type(v["type"], types), f"variable {name}: type/init")
        ir["vars"].append({"name": name, "type": v["type"], "init": typed(v["init"], v["type"], types)})
    ir["events"] = {}
    for name, decl in doc["events"].items():
        require(re.fullmatch(r"[a-z][a-z0-9_]*", name) and name not in ("advance", "input"), f"invalid event {name}")
        ir["events"][name] = fields(decl, types, f"event {name}")
    expressions = []
    def expr(text, label):
        require(isinstance(text, str) and text, f"{label}: CEL text required")
        # Check free functions outside string literals; member functions/macros
        # are checked by CEL itself. No undeclared extension is inferred.
        unquoted = re.sub(r'''"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*' ''', "", text, flags=re.X | re.S)
        allowed = {"has", "size", "all", "exists", "exists_one", "map", "filter", "in", "string", "int", "double", "type"} | set(doc["functions"])
        for name in re.findall(r"(?<![\w.])([A-Za-z_][A-Za-z0-9_]*)\s*\(", unquoted):
            require(name in allowed, f"{label}: undeclared function {name}")
        expressions.append((label, text))
        return text
    ir["actions"] = {}
    for name, action in doc["actions"].items():
        require(isinstance(action, dict) and not set(action) - {"args", "set", "io"}, f"action {name}: args/set/io only")
        require(isinstance(action.get("set", {}), dict), f"action {name}: set map")
        if "io" in action:
            require(isinstance(action["io"], str) and action["io"], f"action {name}: nonempty IO contract")
        a = {"args": fields(action.get("args", {}), types, f"action {name}"), "set": [], "io": action.get("io", "")}
        for n, text in action.get("set", {}).items():
            require(n in doc["vars"], f"action {name}: undeclared variable {n}")
            a["set"].append({"name": n, "expr": expr(text, f"action {name} set {n}")})
        ir["actions"][name] = a
    ir["transitions"], ids = [], set()
    for row in doc["transitions"]:
        require(isinstance(row, dict) and not set(row) - {"id", "event", "from", "if", "do", "to", "stop"}, "transition keys")
        rid = row.get("id")
        require(isinstance(rid, str) and NAME.fullmatch(rid) and rid not in ids, "unique transition id")
        ids.add(rid)
        require(row.get("event") in ir["events"], f"{rid}: declared event required")
        src = row.get("from", [s for s in states if s not in terminal])
        src = [src] if isinstance(src, str) else src
        require(isinstance(src, list) and src and all(s in states and s not in terminal for s in src), f"{rid}: from states")
        require("to" not in row or row["to"] in states, f"{rid}: to state")
        require(type(row.get("stop", False)) is bool, f"{rid}: boolean stop")
        t = {"id": rid, "event": row["event"], "from": src, "if": expr(row.get("if", "true"), rid), "do": [], "stop": row.get("stop", False)}
        if "to" in row:
            t["to"] = row["to"]
        require(isinstance(row.get("do", []), list), f"{rid}: action list")
        for call in row.get("do", []):
            m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\((.*)\)", call, re.S) if isinstance(call, str) else None
            require(m and m[1] in ir["actions"], f"{rid}: declared action call")
            args = split_top(m[2], ",") if m[2].strip() else []
            require(len(args) == len(ir["actions"][m[1]]["args"]), f"{rid}: action arity")
            t["do"].append({"action": m[1], "args": [expr(x, f"{rid} {m[1]}") for x in args]})
        ir["transitions"].append(t)
    ir["invariants"] = [{"name": n, "expr": expr(v, f"invariant {n}")} for n, v in doc["invariants"].items()]
    ir["timers"] = []
    for name, timer in doc["timers"].items():
        require(isinstance(timer, dict) and not set(timer) - {"every", "after", "from", "after_io", "event", "payload"}, f"timer {name}: keys")
        require(("every" in timer) != ("after" in timer) and not ("from" in timer and "after_io" in timer), f"timer {name}: schedule")
        require(timer.get("event") in ir["events"], f"timer {name}: declared event")
        aio = timer.get("after_io", "")
        require(not aio or aio in ir["actions"] and ir["actions"][aio]["io"], f"timer {name}: after_io must name IO action")
        payload = timer.get("payload", {})
        require(isinstance(payload, dict) and set(payload) == set(doc["events"][timer["event"]]), f"timer {name}: complete payload")
        def numeric(value, label):
            require(type(value) in (str, int, float), f"{label}: numeric or CEL")
            if not isinstance(value, str):
                finite_json(value)
            return expr(value if isinstance(value, str) else json.dumps(value), label)
        ir["timers"].append({"name": name, "event": timer["event"], "every": "every" in timer,
                             "duration": numeric(timer.get("every", timer.get("after")), f"timer {name} duration"),
                             "origin": numeric(timer.get("from", "s0"), f"timer {name} origin"), "after_io": aio,
                             "payload": [{"name": k, "expr": expr(v, f"timer {name} payload {k}")} for k, v in payload.items()]})
    # Compile every expression, including unreachable rows and unused actions.
    from cel_expr_python import cel
    cfg = cel.NewEnvConfigFromYaml("name: policy\nextensions:\n  - name: strings\n  - name: two-var-comprehensions\n")
    names = RESERVED | set(doc["const"]) | set(doc["vars"])
    for ev in ir["events"].values():
        names |= {f["name"] for f in ev}
    for a in ir["actions"].values():
        names |= {f["name"] for f in a["args"]}
    fns = [cel.FunctionDecl("same_set", [cel.Overload("same_set_list_list", cel.Type.BOOL,
           [cel.Type.List(cel.Type.DYN), cel.Type.List(cel.Type.DYN)], impl=lambda a, b: sorted(map(str, a)) == sorted(map(str, b)))])] if "same_set" in doc["functions"] else []
    env = cel.NewEnv(config=cfg, variables={n: cel.Type.DYN for n in names}, functions=fns)
    for label, text in expressions:
        try:
            env.compile(text)
        except Exception as exc:
            raise GenError(f"{where}: {label}: CEL does not compile: {exc}") from None
    return ir


def model(doc, where="machine"):
    try:
        return _model(doc, where)
    except GenError:
        raise
    except (TypeError, KeyError, ValueError, UnicodeError, RecursionError) as exc:
        raise GenError(f"{where}: invalid machine declaration: {exc}") from None


def load(path):
    try:
        return model(yaml.load(Path(path).read_text(encoding="utf-8"), Loader=UniqueLoader), str(path))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise GenError(f"{path}: {exc}") from None


def trace_rows(path, ir):
    """Parse physical LF records, never split a JSON string on Unicode separators."""
    rows = [(n, ln.split("\t")) for n, ln in enumerate(Path(path).read_text(encoding="utf-8").split("\n"), 1)
            if ln and not ln.startswith("#")]
    if not rows or rows[0][1] != ["trace", "step", "t", "event", "expect"]:
        raise GenError(f"{path}: expected trace/step/t/event/expect columns")
    seen, trace, step, stamp = set(), None, -1, 0
    var_types = {v["name"]: v["type"] for v in ir["vars"]}
    types = {n: {f["name"]: f["type"] for f in fields} for n, fields in ir["types"].items()}
    result = []
    for line, cells in rows[1:]:
        where = f"{path}:{line}"
        if len(cells) != 5:
            raise GenError(f"{where}: expected five cells")
        name, seq, time, event, expect = cells
        try:
            n, at = int(seq), float(time)
            if not name or not finite_clock(at) or (name == trace and at < stamp):
                raise GenError("finite nondecreasing trace time and a nonempty name required")
            kind, _, payload = event.partition(" ")
            if name != trace:
                if name in seen or n != 0 or kind != "input":
                    raise GenError("a new trace starts at step 0 input")
                seen.add(name)
                trace, step = name, -1
            step += 1
            if n != step or (step and kind == "input"):
                raise GenError("contiguous trace steps required")
            stamp = at
            if kind == "advance":
                if payload.strip():
                    raise GenError("advance has no payload")
            else:
                obj = strict_json(payload or "{}")
                if not isinstance(obj, dict):
                    raise GenError("payload must be an object")
                if kind == "input":
                    overrides = obj.pop("const", {})
                    if not isinstance(overrides, dict) or set(overrides) - set(ir["const"]):
                        raise GenError("const overrides must name declared constants")
                    decl = ir["input"]
                elif kind in ir["events"] and not any(t["event"] == kind for t in ir["timers"]):
                    decl = ir["events"][kind]
                else:
                    raise GenError(f"undeclared external event {kind}")
                if set(obj) != {f["name"] for f in decl}:
                    raise GenError("payload fields differ from declaration")
                for f in decl:
                    typed(obj[f["name"]], f["type"], types)
            if not expect.strip():
                raise GenError("empty assertion")
            for assertion in split_top(expect, ";"):
                key, sep, value = assertion.partition("=")
                key, value = key.strip(), value.strip()
                if not sep:
                    raise GenError("assertion needs =")
                if key == "state":
                    if value not in ir["states"]:
                        raise GenError("assertion names undeclared state")
                elif key == "io":
                    expected = strict_json(value)
                    if not isinstance(expected, list):
                        raise GenError("IO assertion is an ordered list")
                    for intent in expected:
                        if not isinstance(intent, list) or len(intent) != 2 or not isinstance(intent[0], str):
                            raise GenError("IO assertion entry is [action,args]")
                        action = ir["actions"].get(intent[0])
                        if not action or not action["io"] or not isinstance(intent[1], list) or len(intent[1]) != len(action["args"]):
                            raise GenError("IO assertion action/arity")
                        for v, f in zip(intent[1], action["args"]):
                            typed(v, f["type"], types)
                elif key.startswith("var.") and key[4:] in var_types:
                    typed(strict_json(value), var_types[key[4:]], types)
                else:
                    raise GenError(f"unsupported assertion {key}")
        except (ValueError, UnicodeError) as exc:
            raise GenError(f"{where}: {exc}") from None
        result.append({"line": line, "trace": name, "step": n, "t": at, "event": event, "expect": expect})
    if not result:
        raise GenError(f"{path}: no trace rows")
    return result


def finite_clock(at):
    return math.isfinite(at) and at >= 0


def sources(root=ROOT):
    return [Path(root) / LESSON / "forms" / (p + suffix) for p in PARTS for suffix in (".machine.yaml", ".traces.tsv")]


def build(root=ROOT):
    root = Path(root)
    files = {f"go/workerpolicy/{p.name}": p.read_text(encoding="utf-8") for p in sorted(RUNTIME.glob("*.go"))}
    head = ["// Code generated by tools/normgen/gen_policy_machines.py; DO NOT EDIT.", "", "package workerpolicy", "", "import \"fmt\"", ""]
    head += ["// Definition returns a fresh copy of a closed policy IR. IO is an ordered intention only.", "func Definition(name string) ([]byte, error) {", "switch name {"]
    models = {}
    for part in PARTS:
        path = root / LESSON / "forms" / f"{part}.machine.yaml"
        ir = load(path)
        if ir["machine"] != part:
            raise GenError(f"{path}: machine must be {part}")
        models[part] = ir
        head += [f"// Source {path.relative_to(root)} sha256 {hashlib.sha256(path.read_bytes()).hexdigest()}",
                 f"case {go_str(part)}: return []byte({go_str(json.dumps(ir, ensure_ascii=False, separators=(',', ':')))}), nil"]
    head += ['default: return nil, fmt.Errorf("unknown closed policy %q", name)', "}", "}", "", "// Open compiles a closed policy and starts one independent local run.", "func Open(name string, input []byte, at float64) (*Run, error) {", "b, err := Definition(name); if err != nil { return nil, err }; p, err := Compile(b); if err != nil { return nil, err }; return p.New(input, at)", "}", ""]
    files["go/workerpolicy/programs.go"] = gofmt("\n".join(head))
    # Trace assertions are retained as data, interpreted independently by the Go test engine.
    traces = []
    inventory = ["machine\ttrace\tstep\tline\ttest\tstatus"]
    for part in PARTS:
        p = root / LESSON / "forms" / f"{part}.traces.tsv"
        rows = trace_rows(p, models[part])
        inventory += [f"{part}\t{r['trace']}\t{r['step']}\t{r['line']}\tTestDeclaredTraces/{part}\ttranslated" for r in rows]
        text = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
        traces.append(f"{{{go_str(part)}, {go_str(text)}, {go_str(hashlib.sha256(p.read_bytes()).hexdigest())}}}")
    template = (HERE / "policyrt/traces_test.go.txt").read_text(encoding="utf-8")
    files["go/workerpolicy/traces_test.go"] = gofmt(template.replace("//TRACES", ",\n".join(traces) + ","))
    files["go/workerpolicy/inventory.tsv"] = "\n".join(inventory) + "\n"
    sources = [*(root / LESSON / "forms" / f"{part}.{suffix}" for part in PARTS for suffix in ("machine.yaml", "traces.tsv")),
               *sorted(RUNTIME.glob("*.go")), HERE / "policyrt/traces_test.go.txt"]
    return machine_source.go_files(files, generator=__file__, sources=sources, root=root)


def module_files(module, root=ROOT):
    versions = Path(root) / "Platform/common/versions"
    text = (versions / "go.mod").read_text(encoding="utf-8")
    if not re.search(r"github.com/google/cel-go v0\.26\.1\s", text):
        raise GenError("Platform/common/versions/go.mod: expected pinned cel-go v0.26.1")
    return {"go.mod": re.sub(r"^module .*$", f"module {module}", text, count=1, flags=re.M).encode(),
            "go.sum": (versions / "go.sum").read_bytes()}


def vendor(module):
    with tempfile.TemporaryDirectory(prefix="policy-vendor-") as tmp:
        base = Path(tmp)
        pinned = module_files(module)
        for name, data in pinned.items():
            (base / name).write_bytes(data)
        for rel, text in build().items():
            target = base / "internal" / rel[3:]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        env = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off")
        done = subprocess.run(["go", "mod", "vendor"], cwd=base, env=env, capture_output=True, text=True)
        if done.returncode:
            raise GenError(f"policy go mod vendor: {done.stderr[-1000:]}")
        if any((base / n).read_bytes() != b for n, b in pinned.items()):
            raise GenError("policy go mod vendor rewrote the pinned module files")
        return list(pinned.items()) + [(str(p.relative_to(base)), p.read_bytes()) for p in sorted((base / "vendor").rglob("*")) if p.is_file()]


def generate(root=ROOT, out=None):
    out = Path(out or lesson.output_root() / "p03")
    files = build(root)
    for rel, text in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    for name, data in module_files("normgen/p03", root).items():
        (out / "go" / name).write_bytes(data)
    return out


KIT_MD = """
## Closed P/03 policies (part `stagetests`)

`{module}/internal/workerpolicy` contains the declared `contender-writer` and `token-cache` policies,
their shared CEL runtime (cel-go v0.26.1, vendored from the course pin), and all declared trace tests.
Call `Open(name, inputJSON, startSeconds)` for a fresh local run and `run.Step(seconds, event, payloadJSON)`
for each external fact. `run.Snapshot()` returns a detached state/variables observation.
`Observation.IO` lists ordered `[action, args]` intentions. These packages perform no CAS, HTTP,
file or cryptographic operation; connect the intentions to your ordinary SDK code.
The closed trace tests do not replace the stage tests of your `lessonadapter` CALL ports.
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        print(generate(args.root, args.out))
    except GenError as exc:
        parser.exit(1, f"{exc}\n")
