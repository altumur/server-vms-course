"""Автомат нормы (ADR-0120 п. 2 (б)): `Platform/NN-*/data/<имя>.machine.yaml` и трассы `<имя>.traces.tsv`.

Проверка:
- форма: состояния, события, таймеры, действия, функции — закрытые наборы; каждый переход называет событие из events,
  действия из actions, `to` — состояние; таймер даёт событие из events; `if` и аргументы действий компилируются в CEL;
- трассы: каждая трасса — шаг 0 `input {...}`, затем события; после каждого шага сверяются утверждения колонки expect
  прогоном эталонного исполнителя (ниже): state, alive, need, replied, target.<v>, reads, did (действие, которое
  изменило состояние на этом шаге).
Исполнитель — эталон для сверки трасс, не реализация: действия — по их описанию в actions автомата rollout-poll.
"""
import json
import re
from pathlib import Path

import yaml

CALL = re.compile(r"^([a-z_]+)(?:\((.*)\))?$", re.S)
EVENT_LINE = re.compile(r"^(input|tick|self|status|commit|wait)(?: (.*))?$", re.S)


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
        self.form()

    def error(self, message):
        self.errors.append(f"{self.path.name}: {message}")

    def form(self):
        d = self.doc
        for key in ("machine", "norm", "states", "initial", "input", "const", "vars", "timers", "events", "functions",
                    "actions", "transitions"):
            if key not in d:
                self.error(f"no section {key}")
        if self.errors:
            return
        if d["initial"] not in d["states"]:
            self.error(f"initial {d['initial']} is not a state")
        for name, timer in d["timers"].items():
            if timer.get("event") not in d["events"]:
                self.error(f"timer {name}: event {timer.get('event')} is not in events")
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
                self.calls.append((k, m[1], split_args(m[2]) if m[2] else []))
            for name in re.findall(r"(?<![\w.'])([a-z_][A-Za-z_]*)\s*\(", t.get("if", "")):
                if name not in {"has", "size", "all", "exists", "in"} and name not in d["functions"]:
                    self.error(f"{where}: if calls {name}(), not in functions")


class Run:
    """The reference executor of rollout-poll: transitions by the file, actions by their descriptions."""

    def __init__(self, machine, inp):
        from cel_expr_python import cel
        self.cel, self.m, self.input = cel, machine, inp
        T = cel.Type
        cfg = cel.NewEnvConfigFromYaml("name: machine\nextensions:\n  - name: strings\n  - name: two-var-comprehensions\n")
        fns = [cel.FunctionDecl("same_set", [cel.Overload("same_set_list_list", T.BOOL, [T.List(T.DYN), T.List(T.DYN)],
                                                          impl=lambda a, b: sorted(map(str, a)) == sorted(map(str, b)))])]
        names = {"input", "vars", "const", "k", "v", "r", "n", "c", *machine.doc["vars"]}
        self.env = cel.NewEnv(config=cfg, variables={x: T.DYN for x in names}, functions=fns)
        self.cache = {}
        self.state = machine.doc["initial"]
        self.vars = {name: json.loads(json.dumps(spec["init"])) for name, spec in machine.doc["vars"].items()}
        self.did = []

    def ev(self, expr, params):
        if expr not in self.cache:
            self.cache[expr] = self.env.compile(expr)
        data = {**self.vars, "vars": self.vars, "input": self.input, "const": self.m.doc["const"],
                "k": None, "v": None, "r": None, "n": None, "c": None, **params}
        out = self.cache[expr].eval(data=data)
        if out.type() == self.cel.Type.ERROR:
            raise RuntimeError(f"CEL error in {expr!r}: {out.value()}")
        return out.plain_value()

    def event(self, kind, params):
        if self.state != "polling":
            return
        for t in self.m.doc["transitions"]:
            if t["event"] != kind:
                continue
            if "if" in t and not self.ev(t["if"], params):
                continue
            for action in t.get("do", []):
                name, args = CALL.match(action)[1], CALL.match(action)[2]
                values = [self.ev(a, params) for a in split_args(args)] if args else []
                getattr(self, "a_" + name)(*values, params=params)
            if "to" in t:
                self.state = t["to"]
                return
            if t.get("stop"):
                return

    # actions (rollout-poll actions:)
    def a_send_status(self, k, params):
        self.did.append(f"send_status {k}")

    def a_new_partition(self, k, params):
        self.vars.update(k=k, leader=None, leader_id=None, self_replied=False, leaderless=False, read_done=False,
                         replied=[], held=[], alive=[], need=[])

    def a_rupture_unanswered(self, params):
        if not self.vars["self_replied"]:
            self.a_rupture_all(params)
        for v in self.input["voters"]:
            if v not in self.vars["replied"]:
                self.a_rupture(v, params)

    def a_rupture(self, v, params):
        x = self.vars
        x["target"].pop(v, None)
        x["need"] = [u for u in x["need"] if u != v]
        x["alive"] = [u for u in x["alive"] if u != v]
        x["reads"] = {n: [u for u in who if u != v] for n, who in x["reads"].items()}

    def a_rupture_all(self, params):
        self.vars["leaderless"] = True
        for v in self.input["voters"]:
            self.a_rupture(v, params)

    def a_set_leader(self, r, params):
        self.vars.update(leader=r.get("leader"), leader_id=r.get("leader_id"), self_replied=True)

    def a_hold(self, v, r, params):
        self.vars["held"].append({"v": v, "r": r})

    def a_release_held(self, params):
        held, self.vars["held"] = self.vars["held"], []
        self.vars["self_replied"] = True
        for item in held:
            self.event("status", {"k": self.vars["k"], "v": item["v"], "r": item["r"]})

    def a_as_voter(self, r, params):
        self.event("status", {"k": self.vars["k"], "v": self.input["self"], "r": r})

    def a_mark_replied(self, v, params):
        if v not in self.vars["replied"]:
            self.vars["replied"].append(v)

    def a_mark_need(self, v, params):
        if v not in self.vars["need"]:
            self.vars["need"].append(v)

    def a_mark_alive(self, v, params):
        if v not in self.vars["alive"]:
            self.vars["alive"].append(v)

    def a_read_commit(self, params):
        x = self.vars
        if not x["need"] or x["read_done"]:
            return
        n = x["next_read"]
        x["reads"][n] = sorted(x["need"])
        x["need"], x["next_read"], x["read_done"] = [], n + 1, True
        self.did.append(f"read_commit {n} {','.join(x['reads'][n])}")

    def a_set_targets(self, n, c, params):
        for v in self.vars["reads"].pop(n, []):
            self.vars["target"][v] = c

    def a_drop_read(self, n, params):
        self.vars["reads"].pop(n, None)

    def a_refuse(self, code, word, params):
        self.did.append(f"refuse {code} {word}")

    def a_pass(self, params):
        self.did.append("pass")


def parse_event(text):
    m = EVENT_LINE.match(text)
    if not m:
        raise ValueError(f"event {text!r}")
    kind, rest = m[1], m[2] or ""
    if kind == "input":
        return "input", json.loads(rest)
    if kind == "tick":
        return "tick", {"k": int(rest)}
    if kind == "wait":
        return "wait_expired", {}
    if kind == "self":
        k, body = rest.split(" ", 1)
        return "self_status", {"k": int(k), "r": json.loads(body)}
    if kind == "status":
        k, v, body = rest.split(" ", 2)
        return "status", {"k": int(k), "v": v, "r": json.loads(body)}
    n, c = rest.split(" ", 1)
    return "commit", {"n": int(n), "c": json.loads(c)}


def assertions(run, expect):
    """→ list of mismatches of `key=value; …`."""
    bad = []
    for item in [x.strip() for x in expect.split(";") if x.strip()]:
        key, _, want = item.partition("=")
        if key == "state":
            got = run.state
        elif key in ("alive", "need", "replied"):
            got, want = ",".join(sorted(run.vars[key])), ",".join(sorted(w for w in want.split(",") if w))
        elif key.startswith("target."):
            got = str(run.vars["target"].get(key[7:], "-"))
        elif key == "reads":
            got = " ".join(f"{n}:{','.join(who)}" for n, who in sorted(run.vars["reads"].items()))
        elif key == "did":
            got = "|".join(run.did)
            if want in run.did or (want == "" and not run.did):
                continue
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
    if not lines or lines[0].split("\t") != ["trace", "step", "event", "expect"]:
        return [f"{traces.name}: columns must be trace, step, event, expect"], {}
    runs, count, errors = {}, 0, []
    for no, line in enumerate(lines[1:], 2):
        cells = line.split("\t")
        if len(cells) != 4:
            errors.append(f"{traces.name} row {no}: 4 cells")
            continue
        trace, step, text, expect = cells
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
        run.did = []
        try:
            run.event(kind, params)
        except RuntimeError as exc:
            errors.append(f"{where}: {exc}")
            continue
        errors.extend(f"{where}: {m}" for m in assertions(run, expect))
    used = {name for _, name, _ in machine.calls}
    unused = set(machine.doc["actions"]) - used
    if unused:
        errors.append(f"{machine.path.name}: actions never used by a transition: {sorted(unused)}")
    return errors, {"machine_traces": count}


def machines(root):
    return sorted(Path(root).glob("Platform/*/data/*.machine.yaml"))
