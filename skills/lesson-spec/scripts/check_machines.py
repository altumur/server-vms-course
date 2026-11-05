"""Machines of the norms (ADR-0120 item 2 (b), addendum (5) items 4, 6): `Platform/NN-*/forms/<name>.machine.yaml` (the
layout of ADR-0124; `data/` in the former one) with traces `<name>.traces.tsv` next to it.

The check:
- form: states, events, timers, actions, functions are closed sets; a transition names an event of events, actions of
  actions with the right number of arguments, `to` — a state; every expression — `if`, the arguments of actions, `set:`,
  `invariants:` — compiles in CEL when the machine loads, not when a trace reaches it;
- traces: step 0 of a trace is `input {...}` (it may override const: `{"const": {...}}`), then external events at times
  of virtual clocks; declared external events have exact typed payloads, declared timers raise their own events,
  and declared IO actions are observed as io <name> <JSON argument array>. The executor runs ordered transitions,
  checks invariants after every event and then assertions of the step. It executes no IO.
The executor is the reference for the traces, not an implementation; `check_machines.py` is a tool of check_spec, not a norm
(ADR-0120 addendum (5) item 6). rollout-poll retains its legacy trace vocabulary and timer interpreter; generic
machines take events, constants, timers, states and IO actions only from their declarations.
"""
import copy
import json
import math
import re
from pathlib import Path

import yaml

CALL = re.compile(r"^([a-z_][a-z0-9_]*)(?:\((.*)\))?$", re.S)
EVENT_LINE = re.compile(r"^(input|advance|self|status|commit)(?: (.*))?$", re.S)
BUILTINS = {"has", "size", "all", "exists", "exists_one", "map", "filter", "in", "string", "int", "double", "type"}


def split_args(text):
    out, depth, cur, quote, escaped = [], 0, "", None, False
    for ch in text:
        if quote:
            cur += ch
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
            continue
        cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


class Machine:
    def __init__(self, path):
        self.path = Path(path)
        self.errors = []
        self.compiled = {}
        try:
            self.doc = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            self.doc, self.generic = {}, True
            self.error(f"not a YAML machine: {exc}")
            return
        if not isinstance(self.doc, dict):
            self.generic = True
            self.error("machine is a map")
            return
        self.generic = self.doc.get("machine") != "rollout-poll"
        self.form()
        if not self.errors:
            self.compile()

    def error(self, message):
        self.errors.append(f"{self.path.name}: {message}")

    def form(self):
        if self.generic:
            generic_form(self)
            return
        d = self.doc
        for key in ("machine", "norm", "states", "initial", "input", "types", "const", "vars", "timers", "events", "env",
                    "functions", "actions", "invariants", "transitions"):
            if key not in d:
                self.error(f"no section {key}")
        if self.errors:
            return
        if d["initial"] not in d["states"]:
            self.error(f"initial {d['initial']} is not a state")
        for name, action in d["actions"].items():
            unknown = set(action) - {"args", "set", "io"}
            if unknown:
                self.error(f"action {name}: unknown keys {sorted(unknown)}")
            for var in action.get("set", {}):
                if var not in d["vars"]:
                    self.error(f"action {name}: set {var} is not a variable")
        self.calls = []
        tids = [t.get("id") for t in d["transitions"]]
        for dup in sorted({i for i in tids if i and tids.count(i) > 1}):
            self.error(f"transition id {dup} repeats")
        for k, t in enumerate(d["transitions"], 1):
            where = f"transition {k}"
            if t.get("event") not in d["events"]:
                self.error(f"{where}: event {t.get('event')} is not in events")
            if "to" in t and t["to"] not in d["states"]:
                self.error(f"{where}: to {t['to']} is not a state")
            if not re.fullmatch(r"[a-z][a-z0-9_-]*", str(t.get("id", ""))):
                self.error(f"{where}: id {t.get('id')!r} is not [a-z][a-z0-9_-]* (ADR-0122 доп. (1) п. 4)")
            unknown = set(t) - {"id", "event", "if", "do", "to", "stop"}
            if unknown:
                self.error(f"{where}: unknown keys {sorted(unknown)}")
            for action in t.get("do", []):
                m = CALL.match(action)
                if not m or m[1] not in d["actions"]:
                    self.error(f"{where}: action {action!r} is not in actions")
                    continue
                args = split_args(m[2]) if m[2] else []
                if len(args) != len(d["actions"][m[1]].get("args", [])):
                    self.error(f"{where}: {m[1]} takes {len(d['actions'][m[1]].get('args', []))} arguments, given {len(args)}")
                self.calls.append((k, t["event"], m[1], args))
        if self.errors:
            return
        for where, expr, _ in self.expressions():
            for name in re.findall(r"(?<![\w.'])([a-z_][A-Za-z_]*)\s*\(", expr):
                if name not in BUILTINS and name not in d["functions"]:
                    self.error(f"{where}: calls {name}(), not in functions")

    def expressions(self):
        """[(where, expression, extra variable names)] — everything that compiles at load."""
        d, out = self.doc, []
        for k, t in enumerate(d["transitions"], 1):
            if "if" in t:
                out.append((f"transition {k} if", t["if"], d["events"][t["event"]]))
        for k, event, name, args in self.calls:
            for a in args:
                out.append((f"transition {k} {name} argument", a, d["events"][event]))
        for name, action in d["actions"].items():
            for var, expr in action.get("set", {}).items():
                out.append((f"action {name} set {var}", expr, action.get("args", [])))
        for name, expr in d["invariants"].items():
            out.append((f"invariant {name}", expr, []))
        if self.generic:
            for name, timer in d["timers"].items():
                extra = d["actions"].get(timer.get("after_io"), {}).get("args", {})
                for field in ("every", "after", "from"):
                    if isinstance(timer.get(field), str):
                        out.append((f"timer {name} {field}", timer[field], extra))
                for key, expr in timer.get("payload", {}).items():
                    out.append((f"timer {name} payload {key}", expr, extra))
            out.append(("timer default origin", "s0", []))
        return out

    def compile(self):
        from cel_expr_python import cel
        self.cel = cel
        T = cel.Type
        cfg = cel.NewEnvConfigFromYaml("name: machine\nextensions:\n  - name: strings\n  - name: two-var-comprehensions\n")
        fns = [cel.FunctionDecl("same_set", [cel.Overload("same_set_list_list", T.BOOL, [T.List(T.DYN), T.List(T.DYN)],
                                                          impl=lambda a, b: sorted(map(str, a)) == sorted(map(str, b)))])]
        names = {"input", "vars", "const", *self.doc["vars"]}
        if self.generic:
            names |= {"now", "s0", "state", *self.doc["const"]}
        for params in self.doc["events"].values():
            names |= set(params)
        for action in self.doc["actions"].values():
            names |= set(action.get("args", []))
        self.names = names
        self.env = cel.NewEnv(config=cfg, variables={x: T.DYN for x in names}, functions=fns)
        for where, expr, _ in self.expressions():
            try:
                self.compiled[expr] = self.env.compile(expr)
            except Exception as exc:                          # noqa: BLE001 — the message names the place
                self.error(f"{where} does not compile: {exc}")


class RolloutRun:
    """The reference executor: transitions by the file, actions by set/io, timers on virtual clocks."""

    def __init__(self, machine, inp):
        self.m, self.d = machine, machine.doc
        self.const = {**self.d["const"], **inp.pop("const", {})}
        self.input = inp
        self.state = self.d["initial"]
        self.vars = {name: json.loads(json.dumps(spec["init"])) for name, spec in self.d["vars"].items()}
        self.now, self.next_tick, self.wait = 0.0, 0, self.const["ROLLOUT_WAIT"]
        self.reads = {}              # n → deadline of a target read
        self.did, self.violations = [], []

    def ev(self, expr, params):
        data = {x: None for x in self.m.names}
        data.update(self.vars, vars=self.vars, input=self.input, const=self.const, **params)
        out = self.m.compiled[expr].eval(data=data)
        if out.type() == self.m.cel.Type.ERROR:
            raise RuntimeError(f"CEL error in {expr!r}: {out.value()}")
        return out.plain_value()

    def event(self, kind, params):
        if self.state != "polling":
            return
        for t in self.d["transitions"]:
            if t["event"] != kind:
                continue
            if "if" in t and not self.ev(t["if"], params):
                continue
            for call in t.get("do", []):
                m = CALL.match(call)
                values = [self.ev(a, params) for a in split_args(m[2])] if m[2] else []
                self.act(m[1], values)
            if "to" in t:
                self.state = t["to"]
                return
            if t.get("stop"):
                return

    def act(self, name, values):
        action = self.d["actions"][name]
        params = dict(zip(action.get("args", []), values))
        new = {var: self.ev(expr, params) for var, expr in action.get("set", {}).items()}
        if name == "send_status":                          # io: the reads of batch k; no answer by tick(k + 1) — no event
            self.did.append(f"send_status {values[0]}")
        if name == "read_commit":                          # io: the read next_read and its deadline
            self.reads[self.vars["next_read"]] = self.now + self.const["READ"]
            self.did.append(f"read_commit {self.vars['next_read']} {','.join(sorted(self.vars['need']))}")
        if name == "pass":
            self.did.append("pass")
        if name == "refuse":
            self.did.append(f"refuse {values[0]} {values[1]}")
        self.vars.update(new)
        if action.get("io"):
            self.did.append("io " + name + " " + json.dumps(values, ensure_ascii=False,
                                                          separators=(",", ":"), sort_keys=True))

    def deliver(self, kind, params, label):
        if self.state != "polling":                        # passed and refused take no events
            return
        self.did.append(label)
        self.event(kind, params)
        if self.state == "polling":
            for name, expr in self.d["invariants"].items():
                if not self.ev(expr, {}):
                    self.violations.append(f"invariant {name} broken after {label}")

    def due(self, until):
        """Raise the timer events up to `until`, one instant at a time, in the order of env."""
        while self.state == "polling":
            times = list(self.reads.values()) + [self.next_tick * self.const["BATCH"]]
            if self.wait is not None:
                times.append(self.wait)
            t = min(times)
            if t > until:
                return
            self.now = t
            for n in sorted(n for n, at in self.reads.items() if at == t):
                del self.reads[n]
                self.deliver("read_expired", {"n": n}, f"read_expired {n}")
            if self.next_tick * self.const["BATCH"] == t:
                k = self.next_tick
                self.next_tick += 1
                self.deliver("tick", {"k": k}, f"tick {k}")
            if self.wait == t:
                self.wait = None
                self.deliver("wait_expired", {}, "wait_expired")

    def external(self, t, kind, params):
        self.due(t)
        self.now = max(self.now, t)
        if kind == "advance":
            return
        if kind == "commit":
            self.reads.pop(params["n"], None)
        label = {"self_status": "self", "status": "status", "commit": "commit"}[kind]
        self.deliver(kind, params, f"{label} {params.get('k', params.get('n'))}")


def parse_event(text, machine=None):
    if machine is not None and machine.generic:
        kind, _, rest = text.partition(" ")
        if kind == "advance":
            if rest.strip():
                raise ValueError("advance has no payload")
            return kind, {}
        if kind != "input" and kind not in machine.doc["events"]:
            raise ValueError(f"undeclared event {kind}")
        params = strict_json(rest or "{}")
        if not isinstance(params, dict):
            raise ValueError("event payload is an object")
        return kind, params
    m = EVENT_LINE.match(text)
    if not m:
        raise ValueError(f"event {text!r}")
    kind, rest = m[1], m[2] or ""
    if kind == "input":
        return "input", json.loads(rest)
    if kind == "advance":
        return "advance", {}
    if kind == "self":
        k, body = rest.split(" ", 1)
        return "self_status", {"k": int(k), "r": json.loads(body)}
    if kind == "status":
        k, v, body = rest.split(" ", 2)
        return "status", {"k": int(k), "v": v, "r": json.loads(body)}
    n, c = rest.split(" ", 1)
    return "commit", {"n": int(n), "c": json.loads(c)}



def assertion_parts(text):
    out, start, depth, quoted, escaped = [], 0, 0, False, False
    for i, ch in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif ch == "\\\\":
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == ";" and depth == 0:
            if text[start:i].strip():
                out.append(text[start:i].strip())
            start = i + 1
    if text[start:].strip():
        out.append(text[start:].strip())
    return out

def assertions(run, expect):
    bad = []
    for item in (assertion_parts(expect) if isinstance(run, GenericRun) else
                 [x.strip() for x in expect.split(";") if x.strip()]):
        key, _, want = item.partition("=")
        if key == "io" and isinstance(run, GenericRun):
            got = [[line.split(" ", 2)[1], strict_json(line.split(" ", 2)[2])]
                   for line in run.did if line.startswith("io ")]
            try:
                expected = strict_json(want)
            except ValueError as exc:
                bad.append(f"IO assertion: {exc}")
                continue
            if got != expected:
                bad.append(f"IO: {got!r}, expected {expected!r}")
            continue
        if key.startswith("var.") and isinstance(run, GenericRun):
            name = key[4:]
            if name not in run.vars:
                bad.append(f"unknown variable {name}")
                continue
            try:
                expected = strict_json(want)
            except ValueError as exc:
                bad.append(f"variable assertion {name}: {exc}")
                continue
            if run.vars[name] != expected:
                bad.append(f"variable {name}: {run.vars[name]!r}, expected {expected!r}")
            continue
        if key == "state":
            got = run.state
        elif key in ("alive", "need", "replied"):
            got, want = ",".join(sorted(run.vars[key])), ",".join(sorted(w for w in want.split(",") if w))
        elif key.startswith("target."):
            got = str(next((t["c"] for t in run.vars["target"] if t["v"] == key[7:]), "-"))
        elif key == "reads":
            got = " ".join(f"{x['n']}:{','.join(sorted(x['who']))}" for x in sorted(run.vars["reads"], key=lambda x: x["n"]))
        elif key == "did":
            if want in run.did:
                continue
            got = "|".join(run.did)
        elif key == "not":
            if want not in run.did:
                continue
            got, want = "|".join(run.did), f"no {want}"
        else:
            bad.append(f"unknown assertion {key}")
            continue
        if got != want:
            bad.append(f"{key}: {got!r}, expected {want!r}")
    return bad


# ---------------------------------------------------------------- declared policy machines (rollout compatibility stays above)

def strict_json(text):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError(f"duplicate JSON key {key}")
            out[key] = value
        return out

    def constant(word):
        raise ValueError(f"non-JSON number {word}")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def json_value(value):
    if value is None or isinstance(value, bool):
        return True
    if isinstance(value, str):
        try:
            value.encode("utf-8")
            return True
        except UnicodeError:
            return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(json_value(x) for x in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and json_value(k) and json_value(v) for k, v in value.items())
    return False


def type_parts(text):
    depth, start, out = 0, 0, []
    for i, ch in enumerate(text):
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif ch == "|" and depth == 0:
            out.append(text[start:i].strip())
            start = i + 1
    return out + [text[start:].strip()]


def known_type(text, types, seen=()):
    if not isinstance(text, str):
        return False
    choices = type_parts(text)
    if len(choices) > 1:
        return all(known_type(x, types, seen) for x in choices)
    if text in {"bool", "boolean", "int", "integer", "double", "number", "string", "dyn", "null", "object", "array"}:
        return True
    if text.startswith("list<") and text.endswith(">"):
        return known_type(text[5:-1], types, seen)
    if text.startswith("map<string,") and text.endswith(">"):
        return known_type(text[11:-1].strip(), types, seen)
    if text in types and text not in seen:
        record = types[text]
        return isinstance(record, dict) and all(known_type(t, types, (*seen, text)) for t in record.values())
    return False


def typed(value, text, types):
    """Validate and normalize only declared doubles; integers and version strings stay exact."""
    choices = type_parts(text)
    if len(choices) > 1:
        for choice in choices:
            try:
                return typed(value, choice, types)
            except ValueError:
                pass
        raise ValueError(f"expected {text}")
    if not json_value(value):
        raise ValueError("not a finite Unicode JSON value")
    if text == "dyn":
        return copy.deepcopy(value)
    if text == "null" and value is None:
        return None
    if text in ("bool", "boolean") and type(value) is bool:
        return value
    if text in ("int", "integer") and type(value) is int and -(2 ** 63) <= value < 2 ** 63:
        return value
    if text in ("double", "number") and type(value) in (int, float):
        try:
            out = float(value)
        except OverflowError:
            out = float("inf")
        if math.isfinite(out):
            return out if text == "double" else value
    if text == "string" and isinstance(value, str):
        return value
    if text == "object" and isinstance(value, dict):
        return copy.deepcopy(value)
    if text == "array" and isinstance(value, list):
        return copy.deepcopy(value)
    if text.startswith("list<") and text.endswith(">") and isinstance(value, list):
        return [typed(x, text[5:-1], types) for x in value]
    if text.startswith("map<string,") and text.endswith(">") and isinstance(value, dict):
        return {k: typed(v, text[11:-1].strip(), types) for k, v in value.items()}
    if text in types and isinstance(types[text], dict):
        return typed_record(value, types[text], types)
    raise ValueError(f"expected {text}")


def typed_record(value, declarations, types):
    if not isinstance(value, dict):
        raise ValueError("expected an object")
    if set(value) != set(declarations):
        raise ValueError(f"payload fields: missing {sorted(set(declarations) - set(value))}, "
                         f"unknown {sorted(set(value) - set(declarations))}")
    return {name: typed(value[name], spec, types) for name, spec in declarations.items()}


def generic_form(m):
    d = m.doc
    m.calls = []
    required = {"machine", "norm", "states", "initial", "terminal", "input", "types", "const", "vars", "timers",
                "events", "env", "functions", "actions", "invariants", "transitions"}
    if missing := required - set(d):
        m.error(f"no section {', '.join(sorted(missing))}")
    if extra := set(d) - required:
        m.error(f"unknown sections {sorted(extra)}")
    if m.errors:
        return
    for name in ("input", "types", "const", "vars", "timers", "events", "functions", "actions", "invariants"):
        if not isinstance(d[name], dict):
            m.error(f"{name}: expected a map")
    for name in ("states", "terminal", "env", "transitions"):
        if not isinstance(d[name], list):
            m.error(f"{name}: expected a list")
    if m.errors:
        return
    ident = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    state_id = re.compile(r"[a-z][a-z0-9_-]*")
    if not d["states"] or any(not isinstance(s, str) or not state_id.fullmatch(s) for s in d["states"]) \
            or len(set(d["states"])) != len(d["states"]):
        m.error("states: unique nonempty closed state names")
    if d["initial"] not in d["states"]:
        m.error("initial is not in states")
    if any(s not in d["states"] for s in d["terminal"]) or len(set(d["terminal"])) != len(d["terminal"]):
        m.error("terminal: unique members of states")
    if not isinstance(d["machine"], str) or not state_id.fullmatch(d["machine"]):
        m.error("machine: a closed name")
    if not isinstance(d["norm"], str) or not d["norm"]:
        m.error("norm: a nonempty source")
    if not all(isinstance(x, str) for x in d["env"]):
        m.error("env: prose strings")
    reserved = {"input", "vars", "const", "now", "s0", "state"}
    declarations = {}
    for scope in ("input", "types", "const", "vars", "actions"):
        for name in d[scope]:
            if not isinstance(name, str) or not ident.fullmatch(name):
                m.error(f"{scope}: invalid identifier {name!r}")
    for name, typ in d["input"].items():
        if not known_type(typ, d["types"]):
            m.error(f"input {name}: unknown type {typ!r}")
    for name, spec in d["vars"].items():
        if not isinstance(spec, dict) or set(spec) != {"type", "init"}:
            m.error(f"var {name}: only type and init")
            continue
        if not known_type(spec["type"], d["types"]):
            m.error(f"var {name}: unknown type")
            continue
        try:
            typed(spec["init"], spec["type"], d["types"])
        except ValueError as exc:
            m.error(f"var {name} init: {exc}")
    if not all(json_value(v) for v in d["const"].values()):
        m.error("const: finite Unicode JSON values")
    for name in set(d["const"]) | set(d["vars"]):
        if name in reserved or (name in d["const"] and name in d["vars"]):
            m.error(f"{name}: reserved or repeated global")
    for name, params in d["events"].items():
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", name) or name in {"input", "advance"}:
            m.error(f"event {name!r}: invalid or reserved")
        if not isinstance(params, dict):
            m.error(f"event {name}: typed payload map required")
            continue
        declarations[f"event {name}"] = params
    for name, action in d["actions"].items():
        if not isinstance(action, dict) or set(action) - {"args", "set", "io"}:
            m.error(f"action {name}: only args, set and io")
            continue
        args = action.get("args", {})
        if not isinstance(args, dict):
            m.error(f"action {name}: typed args map required")
            continue
        declarations[f"action {name}"] = args
        if "io" in action and (not isinstance(action["io"], str) or not action["io"]):
            m.error(f"action {name}: io is a nonempty contract description")
        if not isinstance(action.get("set", {}), dict):
            m.error(f"action {name}: set is a map")
            continue
        for var, expr in action.get("set", {}).items():
            if var not in d["vars"] or not isinstance(expr, str):
                m.error(f"action {name}: set names an existing variable with a CEL expression")
    for where, decl in declarations.items():
        for name, typ in decl.items():
            if not isinstance(name, str) or not ident.fullmatch(name) or name in reserved:
                m.error(f"{where}: invalid or reserved payload name {name!r}")
            if not known_type(typ, d["types"]):
                m.error(f"{where} {name}: unknown type {typ!r}")
    if set(d["functions"]) - {"same_set"}:
        m.error("functions: only the implemented same_set extension")
    seen = set()
    for n, t in enumerate(d["transitions"], 1):
        where = f"transition {n}"
        if not isinstance(t, dict) or set(t) - {"id", "event", "from", "if", "do", "to", "stop"}:
            m.error(f"{where}: unknown keys or not a map")
            continue
        tid = t.get("id")
        if not isinstance(tid, str) or not state_id.fullmatch(tid) or tid in seen:
            m.error(f"{where}: invalid or duplicate id")
        if not isinstance(tid, str):
            continue
        seen.add(tid)
        if not isinstance(t.get("event"), str) or t.get("event") not in d["events"]:
            m.error(f"{where}: undeclared event")
        sources = t.get("from", [s for s in d["states"] if s not in d["terminal"]])
        if isinstance(sources, str):
            sources = [sources]
        if not isinstance(sources, list) or not sources or any(s not in d["states"] for s in sources):
            m.error(f"{where}: from names declared states")
        elif any(s in d["terminal"] for s in sources):
            m.error(f"{where}: transition from terminal")
        if "to" in t and t["to"] not in d["states"]:
            m.error(f"{where}: to names a declared state")
        if "stop" in t and type(t["stop"]) is not bool:
            m.error(f"{where}: stop is boolean")
        if "if" in t and not isinstance(t["if"], str):
            m.error(f"{where}: if is CEL text")
        if not isinstance(t.get("do", []), list):
            m.error(f"{where}: do is an action list")
            continue
        for call in t.get("do", []):
            match = CALL.fullmatch(call) if isinstance(call, str) else None
            if not match or match[1] not in d["actions"]:
                m.error(f"{where}: action {call!r} is not declared")
                continue
            args = split_args(match[2]) if match[2] else []
            if len(args) != len(d["actions"][match[1]].get("args", {})):
                m.error(f"{where}: wrong arity of {match[1]}")
            m.calls.append((n, t["event"], match[1], args))
    for name, timer in d["timers"].items():
        if not isinstance(timer, dict) or set(timer) - {"every", "after", "from", "after_io", "event", "payload"}:
            m.error(f"timer {name}: unknown keys")
            continue
        if ("every" in timer) == ("after" in timer):
            m.error(f"timer {name}: exactly one of every and after")
        if "from" in timer and "after_io" in timer:
            m.error(f"timer {name}: from and after_io are exclusive")
        if "after_io" in timer and (not isinstance(timer["after_io"], str)
                                   or timer["after_io"] not in d["actions"]
                                   or not d["actions"][timer["after_io"]].get("io")):
            m.error(f"timer {name}: after_io names an IO action")
        if not isinstance(timer.get("event"), str) or timer.get("event") not in d["events"]:
            m.error(f"timer {name}: undeclared event")
            continue
        payload = timer.get("payload", {})
        if not isinstance(payload, dict) or set(payload) != set(d["events"][timer["event"]]) \
                or not all(isinstance(v, str) for v in payload.values()):
            m.error(f"timer {name}: payload maps every declared event field to CEL")
        for field in ("every", "after", "from"):
            if field in timer and type(timer[field]) not in (int, float, str):
                m.error(f"timer {name}: {field} is numeric or CEL")
    for name, expr in d["invariants"].items():
        if not isinstance(expr, str):
            m.error(f"invariant {name}: CEL text")
    if m.errors:
        return
    for where, expr, _ in m.expressions():
        for name in re.findall(r"(?<![\w.'])([a-z_][A-Za-z_]*)\s*\(", expr):
            if name not in BUILTINS and name not in d["functions"]:
                m.error(f"{where}: calls {name}(), not in functions")


class GenericRun:
    """Declared events and timers; IO is observed, never executed by this reference."""

    def __init__(self, machine, inp, at=0.0):
        self.m, self.d = machine, machine.doc
        if type(at) not in (int, float) or not math.isfinite(at) or at < 0:
            raise ValueError("input clock is finite and nonnegative")
        supplied = copy.deepcopy(inp)
        overrides = supplied.pop("const", {})
        if not isinstance(overrides, dict) or set(overrides) - set(self.d["const"]):
            raise ValueError("const overrides name declared constants")
        self.const = {**self.d["const"], **overrides}
        if not all(json_value(v) for v in self.const.values()):
            raise ValueError("const: finite JSON values")
        self.input = typed_record(supplied, self.d["input"], self.d["types"])
        self.state = self.d["initial"]
        self.vars = {name: typed(spec["init"], spec["type"], self.d["types"])
                     for name, spec in self.d["vars"].items()}
        self.now = self.s0 = float(at)
        self.did, self.violations = [], []
        self.pending, self.origins, self.serial = {}, {}, 0
        self.sync_timers()
        self.invariants("input")

    def ev(self, expr, params=None):
        if type(expr) in (int, float):
            return expr
        data = {x: None for x in self.m.names}
        data.update(self.const)
        data.update(self.vars)
        data.update(input=self.input, vars=self.vars, const=self.const, now=self.now, s0=self.s0, state=self.state)
        data.update(params or {})
        out = self.m.compiled[expr].eval(data=data)
        if out.type() == self.m.cel.Type.ERROR:
            raise RuntimeError(f"CEL error in {expr!r}: {out.value()}")
        return out.plain_value()

    def invariants(self, label):
        for name, expr in self.d["invariants"].items():
            if self.ev(expr) is not True:
                self.violations.append(f"invariant {name} broken after {label}")

    def active(self):
        return self.state not in self.d["terminal"]

    def event(self, kind, params):
        if not self.active():
            return
        for t in self.d["transitions"]:
            sources = t.get("from", [s for s in self.d["states"] if s not in self.d["terminal"]])
            sources = [sources] if isinstance(sources, str) else sources
            if t["event"] != kind or self.state not in sources:
                continue
            if "if" in t:
                guard = self.ev(t["if"], params)
                if type(guard) is not bool:
                    raise ValueError(f"transition {t['id']}: condition is not bool")
                if not guard:
                    continue
            for call in t.get("do", []):
                match = CALL.fullmatch(call)
                values = [self.ev(x, params) for x in split_args(match[2])] if match[2] else []
                self.act(match[1], values)
            if "to" in t:
                self.state = t["to"]
                break
            if t.get("stop"):
                break
        self.sync_timers()

    def act(self, name, values):
        action = self.d["actions"][name]
        params = typed_record(dict(zip(action.get("args", {}), values)), action.get("args", {}), self.d["types"])
        new = {var: typed(self.ev(expr, params), self.d["vars"][var]["type"], self.d["types"])
               for var, expr in action.get("set", {}).items()}
        self.vars.update(new)
        if action.get("io"):
            self.did.append("io " + name + " " + json.dumps(list(params.values()), ensure_ascii=False,
                                                          separators=(",", ":"), sort_keys=True))
            for timer_name, timer in self.d["timers"].items():
                if timer.get("after_io") == name:
                    self.serial += 1
                    self.arm((timer_name, self.serial), timer, self.now, params)

    def arm(self, key, timer, origin, context=None):
        duration = self.ev(timer.get("every", timer.get("after")), context)
        if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0 \
                or ("every" in timer and duration == 0):
            raise ValueError(f"timer {key}: positive every or nonnegative after required")
        if type(origin) not in (int, float) or not math.isfinite(origin) or origin < 0:
            raise ValueError(f"timer {key}: from is a finite nonnegative clock")
        due = origin if "every" in timer else origin + duration
        self.pending[key] = {"due": max(self.now, due), "period": duration if "every" in timer else None,
                             "timer": timer, "context": dict(context or {})}

    def sync_timers(self):
        if not self.active():
            self.pending.clear()
            return
        for name, timer in self.d["timers"].items():
            if "after_io" in timer:
                continue
            origin = self.ev(timer.get("from", "s0"))
            duration = self.ev(timer.get("every", timer.get("after")))
            if type(origin) not in (int, float) or not math.isfinite(origin) or origin < 0:
                raise ValueError(f"timer {name}: from is a finite nonnegative clock")
            if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0 \
                    or ("every" in timer and duration == 0):
                raise ValueError(f"timer {name}: positive every or nonnegative after required")
            signature = (origin, duration)
            if self.origins.get(name) != signature:
                self.origins[name] = signature
                self.arm((name, 0), timer, origin)

    def deliver(self, kind, params, label):
        params = typed_record(params, self.d["events"][kind], self.d["types"])
        if not self.active():
            return
        self.did.append(label)
        self.event(kind, params)
        self.invariants(label)

    def due(self, until):
        count = 0
        order = {name: n for n, name in enumerate(self.d["timers"])}
        while self.active() and self.pending:
            key, entry = min(self.pending.items(), key=lambda x: (x[1]["due"], order[x[0][0]], x[0][1]))
            if entry["due"] > until:
                break
            count += 1
            if count > 10000:
                raise RuntimeError("timer zero-time cycle or too many timer firings in one trace step")
            self.now = entry["due"]
            timer = entry["timer"]
            if entry["period"] is None:
                self.pending.pop(key)
            else:
                self.pending[key] = {**entry, "due": self.now + entry["period"]}
            params = {name: self.ev(expr, entry["context"]) for name, expr in timer.get("payload", {}).items()}
            self.deliver(timer["event"], params, "timer " + key[0])

    def external(self, t, kind, params):
        if type(t) not in (int, float) or not math.isfinite(t) or t < self.now:
            raise ValueError("trace time is finite and nondecreasing")
        self.due(t)
        self.now = t
        if kind == "advance":
            return
        if kind not in self.d["events"]:
            raise ValueError(f"undeclared event {kind}")
        if any(timer["event"] == kind for timer in self.d["timers"].values()):
            raise ValueError(f"timer event {kind} is raised only by the executor")
        self.deliver(kind, params, "event " + kind)
        self.due(t)                       # an after=0 timer armed by this event is visible in this step


def Run(machine, inp, at=0.0):
    return GenericRun(machine, inp, at) if machine.generic else RolloutRun(machine, inp)

def check(path):
    machine = Machine(path)
    traces = machine.path.with_name(machine.path.name.replace(".machine.yaml", ".traces.tsv"))
    if machine.errors:
        return machine.errors, {}
    if not traces.is_file():
        return [f"{machine.path.name}: no traces {traces.name}"], {}
    lines = [line for line in traces.read_text(encoding="utf-8").split("\n") if line and not line.startswith("#")]
    if not lines or lines[0].split("\t") != ["trace", "step", "t", "event", "expect"]:
        return [f"{traces.name}: columns must be trace, step, t, event, expect"], {}
    runs, count, errors = {}, 0, []
    for no, line in enumerate(lines[1:], 2):
        cells = line.split("\t")
        if len(cells) != 5:
            errors.append(f"{traces.name} row {no}: 5 cells")
            continue
        trace, step, t, text, expect = cells
        where = f"{traces.name} {trace} step {step}"
        try:
            stamp = float(t)
            if not math.isfinite(stamp) or stamp < 0:
                raise ValueError("trace clock is finite and nonnegative")
            kind, params = parse_event(text, machine)
        except ValueError as exc:
            errors.append(f"{where}: {exc}")
            continue
        if kind == "input":
            try:
                runs[trace] = Run(machine, params, stamp)
                count += 1
                if machine.generic:
                    run = runs[trace]
                    errors.extend(f"{where}: {msg}" for msg in run.violations + assertions(run, expect))
            except (ValueError, RuntimeError, KeyError) as exc:
                errors.append(f"{where}: {exc}")
            continue
        run = runs.get(trace)
        if run is None:
            errors.append(f"{where}: no step 0 input")
            continue
        if stamp < run.now:
            errors.append(f"{where}: time {t} is before {run.now}")
            continue
        run.did, run.violations = [], []
        try:
            run.external(stamp, kind, params)
        except (RuntimeError, ValueError, KeyError) as exc:
            errors.append(f"{where}: {exc}")
            continue
        errors.extend(f"{where}: {m}" for m in run.violations + assertions(run, expect))
    used = {name for _, _, name, _ in machine.calls}
    unused = set(machine.doc["actions"]) - used
    if unused:
        errors.append(f"{machine.path.name}: actions never used by a transition: {sorted(unused)}")
    return errors, {"machine_traces": count}


def machines(root):
    """Machines: `forms/` of a lesson in the layout of ADR-0124, `data/` in the former one (addendum (1) item 6)."""
    return sorted([*Path(root).glob("Platform/*/forms/*.machine.yaml"), *Path(root).glob("Platform/*/data/*.machine.yaml")])
