"""Machines of the norms (ADR-0120 item 2 (b), addendum (5) items 4, 6): `Platform/NN-*/data/<name>.machine.yaml` with
traces `<name>.traces.tsv`.

The check:
- form: states, events, timers, actions, functions are closed sets; a transition names an event of events, actions of
  actions with the right number of arguments, `to` — a state; every expression — `if`, the arguments of actions, `set:`,
  `invariants:` — compiles in CEL when the machine loads, not when a trace reaches it;
- traces: step 0 of a trace is `input {...}` (it may override const: `{"const": {...}}`), then external events at times
  of virtual clocks; the executor raises the timer events itself (tick, read_expired, wait_expired) in the order
  of env, runs the transitions, checks the invariants after every event and then the
  assertions of the step.
The executor is the reference for the traces, not an implementation; `check_machines.py` is a tool of check_spec, not a norm
(ADR-0120 addendum (5) item 6). The timer semantics below are those of rollout-poll's timers: section.
"""
import json
import re
from pathlib import Path

import yaml

CALL = re.compile(r"^([a-z_]+)(?:\((.*)\))?$", re.S)
EVENT_LINE = re.compile(r"^(input|advance|self|status|commit)(?: (.*))?$", re.S)
BUILTINS = {"has", "size", "all", "exists", "exists_one", "map", "filter", "in", "string", "int", "double", "type"}


def split_args(text):
    out, depth, cur, quote = [], 0, "", None
    for ch in text:
        if quote:
            cur += ch
            if ch == quote:
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
        self.doc = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        self.compiled = {}
        self.form()
        if not self.errors:
            self.compile()

    def error(self, message):
        self.errors.append(f"{self.path.name}: {message}")

    def form(self):
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
        for k, t in enumerate(d["transitions"], 1):
            where = f"transition {k}"
            if t.get("event") not in d["events"]:
                self.error(f"{where}: event {t.get('event')} is not in events")
            if "to" in t and t["to"] not in d["states"]:
                self.error(f"{where}: to {t['to']} is not a state")
            unknown = set(t) - {"event", "if", "do", "to", "stop"}
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
        return out

    def compile(self):
        from cel_expr_python import cel
        self.cel = cel
        T = cel.Type
        cfg = cel.NewEnvConfigFromYaml("name: machine\nextensions:\n  - name: strings\n  - name: two-var-comprehensions\n")
        fns = [cel.FunctionDecl("same_set", [cel.Overload("same_set_list_list", T.BOOL, [T.List(T.DYN), T.List(T.DYN)],
                                                          impl=lambda a, b: sorted(map(str, a)) == sorted(map(str, b)))])]
        names = {"input", "vars", "const", *self.doc["vars"]}
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


class Run:
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


def parse_event(text):
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


def assertions(run, expect):
    bad = []
    for item in [x.strip() for x in expect.split(";") if x.strip()]:
        key, _, want = item.partition("=")
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


def check(path):
    machine = Machine(path)
    traces = machine.path.with_name(machine.path.name.replace(".machine.yaml", ".traces.tsv"))
    if machine.errors:
        return machine.errors, {}
    if not traces.is_file():
        return [f"{machine.path.name}: no traces {traces.name}"], {}
    lines = [line for line in traces.read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
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
            kind, params = parse_event(text)
        except ValueError as exc:
            errors.append(f"{where}: {exc}")
            continue
        if kind == "input":
            runs[trace] = Run(machine, params)
            count += 1
            continue
        run = runs.get(trace)
        if run is None:
            errors.append(f"{where}: no step 0 input")
            continue
        if float(t) < run.now:
            errors.append(f"{where}: time {t} is before {run.now}")
            continue
        run.did, run.violations = [], []
        try:
            run.external(float(t), kind, params)
        except RuntimeError as exc:
            errors.append(f"{where}: {exc}")
            continue
        errors.extend(f"{where}: {m}" for m in run.violations + assertions(run, expect))
    used = {name for _, _, name, _ in machine.calls}
    unused = set(machine.doc["actions"]) - used
    if unused:
        errors.append(f"{machine.path.name}: actions never used by a transition: {sorted(unused)}")
    return errors, {"machine_traces": count}


def machines(root):
    return sorted(Path(root).glob("Platform/*/data/*.machine.yaml"))
