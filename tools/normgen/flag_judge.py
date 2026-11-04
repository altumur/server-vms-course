"""Судья части `flags` (ADR-0125 № 3, доп. (1) п. 1): пробы запуска собранного демона по таблице «Daemon flags».

Запуск (на CT 103, python с cel_expr_python — /opt/check-env/lesson-spec/bin/python):
  python tools/normgen/flag_judge.py --cmd './bin/configstore' [--stub] [--cwd <каталог>] [--rights-file <файл>]
      [--tls-dir <каталог>] [--ok-wait 2] [--json <итог.json>] [--fuzz N --seed S]

Модель — своя, не из генератора: таблица `Platform/01-store/forms/daemon-flags.tsv` читается заново, типы словаря
шапки разбираются здесь же, `required` и `bad` вычисляет оракул CEL (cel_expr_python, как check_forms), `loopback` —
примитив normgen (prims/python). Каждая проба — командная строка; ожидание — отказ запуска (код 2) или запуск.

Пробы:
- по таблице: каждый флаг демона с годным значением (недостающие обязательные дописываются), неверные значения его
  типа, флаг без значения, чужой флаг (`-no-such-flag`, снятый `-socket`), флаг другой команды, обязательные
  (`required`) и отказы `bad`;
- по сценариям приёмки главы 1.3: строки `@store-start` без `kit=` (ожидание `ok` или `@exit 2`) — независимый вход;
- `--fuzz N` — ещё N случайных строк (только с `--stub`: сверка значений).
Нормативные пробы гоняются всегда; пробы соглашений пакета (повтор флага, `-x=v`, `--`, подкоманды) — только с `--stub`.

Исход пробы на демоне: отказ — код 2 не позже 10 с; запуск — через `--ok-wait` с процесс жив или вышел с кодом ≠ 2
(его снимает SIGTERM, затем SIGKILL). С `--stub` (заглушка tools/normgen/flags/stub) — ещё флаг отказа и все поля Flags.
`--box` — сборка без raft (ключ профиля store_build: box): проба запуска с флагами группы (-join, -door, -voters,
-bootstrap, -raft, -raft-bind, -group-size 3|5) может кончиться кодом 2 (Н4 1.3 box_no_raft).
Пробы с `-rights` / `-tls` на демоне требуют `--rights-file` / `--tls-dir` (содержимое — не форма), иначе пропущены.
Итог: `flags: P/N PASS|FAIL` (пропуски — отдельно); код 0 — все прошли, 1 — нет, 2 — ошибка запуска судьи.
"""
import argparse
import json
import os
import random
import re
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TABLE = ROOT / "Platform/01-store/forms/daemon-flags.tsv"
SCENARIOS = ROOT / "Platform/01-store/acceptance/3/scenarios.tsv"
sys.path.insert(0, str(HERE / "prims/python"))
from prims import prim_loopback  # noqa: E402

COLUMNS = ["flag", "type", "default", "default_text", "required", "commands", "bad", "norm"]
SHORT = {"id": "ID", "api": "API", "tls": "TLS"}
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", re.A)
INT = re.compile(r"-?(0|[1-9][0-9]*)", re.A)
DUR = re.compile(r"((?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(ns|us|µs|μs|ms|s|m|h))", re.A)
NS = {"ns": 1, "us": 10 ** 3, "µs": 10 ** 3, "μs": 10 ** 3, "ms": 10 ** 6, "s": 10 ** 9, "m": 60 * 10 ** 9,
      "h": 3600 * 10 ** 9}
I64 = 2 ** 63


class Bad(Exception):
    pass


# ---------------------------------------------------------------- модель

def read_table(path=TABLE):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    body = [x for x in lines if not x.startswith("#")]
    if body[0].split("\t") != COLUMNS:
        raise SystemExit(f"flag_judge: {path}: columns are not {COLUMNS}")
    rows = []
    for x in body[1:]:
        r = dict(zip(COLUMNS, x.split("\t")))
        r["commands"] = r["commands"].split(",")
        r["field"] = "".join(SHORT.get(p, p.capitalize()) for p in r["flag"].lstrip("-").split("-"))
        rows.append(r)
    return rows


def v_addr(s):
    if s.startswith("["):
        end = s.find("]")
        if end < 0 or s[end + 1:end + 2] != ":":
            raise Bad("not host:port")
        host, port = s[1:end], s[end + 2:]
        if "[" in host or "[" in port or "]" in port:
            raise Bad("not host:port")
    else:
        host, sep, port = s.rpartition(":")
        if not sep or ":" in host or "[" in s or "]" in s:
            raise Bad("not host:port")
    if not re.fullmatch(r"[0-9]{1,5}", port, re.A) or int(port) > 65535:
        raise Bad("port")
    return s


def v_int(s, lo, hi):
    if not INT.fullmatch(s) or s in ("-",):
        raise Bad("int")
    n = int(s)
    if not -I64 <= n < I64 or n < lo or (hi is not None and n > hi):
        raise Bad("range")
    return n


def v_duration(s):
    rest = s
    if rest[:1] in "+-":
        if rest[0] == "-" and rest[1:] not in ("0", ""):
            raise Bad("negative")
        rest = rest[1:]
    if rest == "0":
        return 0
    if not rest:
        raise Bad("duration")
    total, pos = 0, 0
    for m in DUR.finditer(rest):
        if m.start() != pos:
            raise Bad("duration")
        num, unit = m.group(1)[:-len(m.group(2))], m.group(2)
        whole, _, frac = num.partition(".")
        total += int(whole or 0) * NS[unit] + (int(frac) * NS[unit] // 10 ** len(frac) if frac else 0)
        pos = m.end()
    if pos != len(rest):
        raise Bad("duration")
    if s.startswith("-") and total:
        raise Bad("negative")
    return total


def parse_value(t, raw):
    """→ (значение CEL, значение поля); Bad — вне типа."""
    if t in ("path", "dir", "file"):
        if raw == "":
            raise Bad("empty")
        return raw, raw
    if t == "addr":
        return v_addr(raw), raw
    if t == "id":
        if not ID.fullmatch(raw):
            raise Bad("id")
        return raw, raw
    if t == "duration":
        return raw, v_duration(raw)
    if t == "bytes:>0":
        n = v_int(raw, 1, None)
        return n, n
    if t.startswith("int:"):
        lo, hi = t[4:].split("..")
        n = v_int(raw, int(lo), int(hi) if hi else None)
        return n, n
    if t.startswith("enum:"):
        vals = t[5:].split("|")
        if raw not in vals:
            raise Bad("enum")
        ints = all(INT.fullmatch(v) for v in vals)
        return (int(raw), int(raw)) if ints else (raw, raw)
    if t.startswith("list:"):
        want = 2 if t.endswith("/addr") else 1
        if raw == "":
            raise Bad("empty list")
        out = []
        for el in raw.split(","):
            ident, at, rest = el.partition("@")
            if not at or not ID.fullmatch(ident):
                raise Bad("element")
            addrs = rest.split("/")
            if len(addrs) != want:
                raise Bad("element")
            for a in addrs:
                v_addr(a)
            out.append([ident] + addrs)
        return raw, out
    raise AssertionError(t)


def zero(t):
    if t == "bool":
        return False
    if t in ("bytes:>0", "duration") or t.startswith("int:") or (t.startswith("enum:") and all(
            INT.fullmatch(v) for v in t[5:].split("|"))):
        return 0
    if t.startswith("list:"):
        return []
    return ""


class Model:
    def __init__(self, rows):
        from cel_expr_python import cel
        self.cel, self.rows = cel, rows
        self.by = {r["flag"]: r for r in rows}
        self.commands = []
        for r in rows:
            for c in r["commands"]:
                if c not in self.commands:
                    self.commands.append(c)
        T = cel.Type
        cfg = cel.NewEnvConfigFromYaml("name: flags\nextensions:\n  - name: strings\n")
        loop = cel.FunctionDecl("loopback", [cel.Overload("loopback_string", T.BOOL, [T.STRING], impl=prim_loopback)])
        self.env = cel.NewEnv(config=cfg, variables={"f": T.Map(T.STRING, T.DYN), "cmd": T.STRING}, functions=[loop])
        self.compiled = {}
        for r in rows:
            for col in ("required", "bad"):
                if r[col]:
                    self.compiled[r["flag"], col] = self.env.compile(r[col])

    def true(self, flag, col, f, cmd):
        v = self.compiled[flag, col].eval(data={"f": f, "cmd": cmd})
        return v.type() != self.cel.Type.ERROR and v.plain_value() is True

    def expect(self, argv, env):
        """→ ("refuse", слово) | ("ok", поля)."""
        if argv and argv[0] != "daemon" and argv[0] in self.commands:
            cmd, args = argv[0], argv[1:]
        else:
            cmd, args = "daemon", argv
            if args and (len(args[0]) < 2 or args[0][0] != "-"):
                return "refuse", args[0]
        f, fields, given, pos = {}, {}, set(), []
        k = 0
        while k < len(args):
            tok = args[k]
            if tok == "--":
                if cmd == "daemon" and args[k + 1:]:
                    return "refuse", args[k + 1]
                pos += args[k + 1:]
                break
            if len(tok) < 2 or tok[0] != "-":
                if cmd == "daemon":
                    return "refuse", tok
                pos.append(tok)
                k += 1
                continue
            name, eq, raw = tok.partition("=")
            if name in given or name not in self.by or cmd not in self.by[name]["commands"]:
                return "refuse", name
            r = self.by[name]
            if r["type"] == "bool":
                if eq:
                    return "refuse", name
                f[name], fields[r["field"]] = True, True
            else:
                if not eq:
                    if k + 1 >= len(args):
                        return "refuse", name
                    k += 1
                    raw = args[k]
                try:
                    f[name], fields[r["field"]] = parse_value(r["type"], raw)
                except Bad:
                    return "refuse", name
            given.add(name)
            k += 1
        for r in self.rows:
            if cmd in r["commands"] and r["flag"] not in given and r["required"] != "false" and (
                    r["required"] == "true" or self.true(r["flag"], "required", f, cmd)):
                return "refuse", r["flag"]
        for r in self.rows:
            if r["flag"] in given and r["bad"] and self.true(r["flag"], "bad", f, cmd):
                return "refuse", r["flag"]
        later = []
        for r in self.rows:
            fld = r["field"]
            if fld in fields:
                continue
            fields[fld] = zero(r["type"])
            if cmd not in r["commands"] or r["default"] == "-":
                continue
            d = r["default"]
            if d.startswith("="):
                later.append((fld, self.by[d[1:]]["field"]))
            elif d.startswith("$"):
                val = env.get(d[1:], "")
                if val:
                    try:
                        fields[fld] = parse_value(r["type"], val)[1]
                    except Bad:
                        return "refuse", r["flag"]
            elif r["type"] != "bool":
                fields[fld] = parse_value(r["type"], d)[1]
        for fld, other in later:
            fields[fld] = fields[other]
        fields.update(Cmd=cmd, Given=sorted(given), Args=pos)
        return "ok", fields


# ---------------------------------------------------------------- пробы

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Probes:
    def __init__(self, model, tmp, stub, rights, tls):
        self.m, self.tmp, self.stub, self.rights, self.tls = model, Path(tmp), stub, rights, tls
        self.out, self.k = [], 0

    def fresh(self):
        self.k += 1
        d = self.tmp / f"p{self.k}"
        d.mkdir()
        return ["-dir", str(d / "data"), "-sockets", str(d / "sock")]

    @staticmethod
    def without(argv, flag):
        """argv без флага flag и его значения."""
        out, k = [], 0
        while k < len(argv):
            if argv[k] == flag:
                k += 2
                continue
            out.append(argv[k])
            k += 1
        return out

    def good(self, r):
        """Годные значения типа флага (список слов)."""
        t = r["type"]
        if r["flag"] == "-rights":
            return [self.rights] if self.rights else ([str(self.tmp / "rights.json")] if self.stub else [])
        if r["flag"] == "-tls":
            return [self.tls] if self.tls else ([str(self.tmp / "tls")] if self.stub else [])
        if t in ("path", "dir", "file"):
            return [str(self.tmp / f"v{self.k}-{r['field'].lower()}")]
        if t == "addr":
            return [f"127.0.0.1:{free_port()}", f"localhost:{free_port()}"]
        if t == "id":
            return ["s1", "Node_2.a-b"]
        if t == "duration":
            return ["5s", "250ms", "1m30s"]
        if t == "bytes:>0":
            return ["1", "4096"]
        if t.startswith("int:"):
            lo = int(t[4:].split("..")[0])
            return [str(lo), str(lo + 7)]
        if t.startswith("enum:"):
            return t[5:].split("|")
        if t == "list:id@addr":
            return [f"s1@127.0.0.1:{free_port()}", f"s1@127.0.0.1:{free_port()},s2@localhost:{free_port()}"]
        if t == "list:id@addr/addr":
            return [f"s1@127.0.0.1:{free_port()}/127.0.0.1:{free_port()}"]
        return []

    BAD = {"path": [""], "dir": [""], "file": [""], "addr": ["nohost", "127.0.0.1:65536", "127.0.0.1:99999", "127.0.0.1:x", "::1:80",
           "127.0.0.1:"], "id": ["_x", "a b", "x" * 129, ""], "duration": ["5", "x", "-1s"],
           "bytes:>0": ["0", "512KiB", "-5", "1.5", "x", "007"], "list:id@addr": ["", "s1", "s1@nohost",
           "s1@127.0.0.1:1,", "_x@127.0.0.1:1"], "list:id@addr/addr": ["", "s1@127.0.0.1:1", "s1@127.0.0.1:1/x"]}

    def bad(self, r):
        t = r["type"]
        if t.startswith("enum:"):
            return ["bogus", "2", ""]
        if t.startswith("int:"):
            lo, hi = t[4:].split("..")
            return [str(int(lo) - 1), "x", "1.5", "+3"] + ([str(int(hi) + 1)] if hi else [])
        return self.BAD.get(t, [])

    def add(self, name, argv, normative=True, env=None):
        env = {"SERVER_NAME": "judge"} if env is None else env
        kind, want = self.m.expect(argv, env)
        self.out.append({"name": name, "argv": argv, "env": env, "expect": kind, "want": want,
                         "normative": normative})

    def complete(self, argv, keep=None):
        """Дописать обязательные флаги демона, которых требует модель, годными значениями (кроме keep)."""
        for _ in range(8):
            kind, want = self.m.expect(argv, {"SERVER_NAME": "judge"})
            if kind == "ok" or want == keep or want not in self.m.by or want in argv:
                return argv
            r = self.m.by[want]
            if r["required"] == "false" or not self.good(r):
                return argv
            argv = argv + [want, self.good(r)[0]]
        return argv

    def build(self, fuzz=0, seed=0):
        daemon = [r for r in self.m.rows if "daemon" in r["commands"]]
        self.add("start: -dir and -sockets", self.fresh())
        self.add("start: no -dir", ["-sockets", str(self.tmp / "nodir-sock")])
        for r in daemon:
            flag = r["flag"]
            for v in ([] if r["type"] == "bool" else self.good(r)):
                self.add(f"good {flag} {v}", self.complete(self.without(self.fresh(), flag) + [flag, v]))
            if r["type"] == "bool":
                self.add(f"good {flag}", self.complete(self.fresh() + [flag]))
                self.add(f"bool {flag}=true", self.complete(self.fresh() + [f"{flag}=true"]), normative=False)
            for v in self.bad(r):
                self.add(f"bad {flag} {v!r}", self.without(self.fresh(), flag) + [flag, v])
            if r["type"] != "bool":
                self.add(f"no value {flag}", self.without(self.fresh(), flag) + [flag])
            once = [flag] + ([] if r["type"] == "bool" else (self.good(r)[:1] or ["x"]))
            self.add(f"repeat {flag}", self.complete(self.without(self.fresh(), flag) + once + once), normative=False)
        for word in ("-no-such-flag", "-socket", "--dir", "-Dir", "-"):
            self.add(f"foreign {word}", self.fresh() + [word, "x"])
        for r in self.m.rows:
            if "daemon" not in r["commands"]:
                v = [] if r["type"] == "bool" else (self.good(r)[:1] or ["x"])
                self.add(f"other command {r['flag']} at daemon", self.fresh() + [r["flag"]] + v)
        for r in daemon:
            if r["required"] not in ("true", "false"):
                for trig in re.findall(r'"(-[a-z-]+)" in f', r["required"]):
                    tr = self.m.by[trig]
                    v = [] if tr["type"] == "bool" else self.good(tr)[:1]
                    if trig == "-group-size":
                        v = ["3"]
                    argv = self.complete(self.fresh() + [trig] + v, keep=r["flag"])
                    if self.m.expect(argv, {"SERVER_NAME": "judge"}) != ("refuse", r["flag"]):
                        raise SystemExit(f"flag_judge: no probe isolates required {r['flag']} by {trig}")
                    self.add(f"required {r['flag']} by {trig}", argv)
            if r["bad"]:
                for trig in re.findall(r'"(-[a-z-]+)" in f', r["bad"]):
                    if trig == "-tls":
                        for host in ("10.0.0.1", "192.0.2.7", "[2001:db8::1]", "0.0.0.0", "[::1]", "127.9.9.9",
                                     "::ffff:127.0.0.1", "[::ffff:127.0.0.1]", "LOCALHOST", ""):
                            addr = f"{host}:{free_port()}"
                            self.add(f"bad {r['flag']} {addr} without -tls", self.fresh() + [r["flag"], addr])
                    else:
                        tr = self.m.by[trig]
                        v = [] if tr["type"] == "bool" else self.good(tr)[:1]
                        argv = self.complete(self.fresh() + [r["flag"]] + ([] if r["type"] == "bool" else
                                                                         self.good(r)[:1]) + [trig] + v)
                        if self.m.expect(argv, {"SERVER_NAME": "judge"}) != ("refuse", r["flag"]):
                            raise SystemExit(f"flag_judge: no probe isolates bad {r['flag']} with {trig}")
                        self.add(f"bad {r['flag']} with {trig}", argv)
        self.scenarios()
        if self.stub:
            self.subcommands()
            self.conventions()
            if fuzz:
                self.fuzz(fuzz, seed)
        return self.out

    def scenarios(self):
        for line in SCENARIOS.read_text(encoding="utf-8").splitlines():
            cells = line.split("\t")
            if len(cells) != 4 or not cells[2].startswith("@store-start "):
                continue
            words = cells[2].split()[1:]
            member, rest = words[0], words[1:]
            if any(w.startswith("kit=") for w in rest):
                continue
            ports = {}
            rest = [re.sub(r"\{(api|raft)@(\w+)\}", lambda m: ports.setdefault(m[0], f"127.0.0.1:{free_port()}"), w)
                    for w in rest]
            argv = self.fresh() + ["-id", member] + rest
            want = "refuse" if cells[3] == "@exit 2" else "ok"
            kind, got = self.m.expect(argv, {"SERVER_NAME": "judge"})
            if kind != want:
                raise SystemExit(f"flag_judge: the model disagrees with {SCENARIOS.name} {cells[0]} {cells[1]}: "
                                 f"{cells[3]} vs {kind} {got}")
            self.add(f"scenario 1.3 {cells[0]} step {cells[1]}", argv)

    def subcommands(self):
        for cmd in self.m.commands:
            if cmd == "daemon":
                continue
            own = [r for r in self.m.rows if cmd in r["commands"]]
            argv = [cmd]
            for r in own:
                if r["required"] == "true":
                    argv += [r["flag"]] + ([] if r["type"] == "bool" else self.good(r)[:1])
            self.add(f"{cmd}: required only", argv, normative=False)
            for r in own:
                v = [] if r["type"] == "bool" else self.good(r)[:1]
                self.add(f"{cmd}: {r['flag']}", argv + [r["flag"]] + v + ["pos1"], normative=False)
            for r in self.m.rows:
                if cmd not in r["commands"]:
                    v = [] if r["type"] == "bool" else (self.good(r)[:1] or ["x"])
                    self.add(f"{cmd}: foreign {r['flag']}", argv + [r["flag"]] + v, normative=False)
                    break
            req = [r for r in own if r["required"] == "true"]
            if req:
                self.add(f"{cmd}: no {req[0]['flag']}", [cmd], normative=False)
        self.add("unknown subcommand", ["frobnicate", "-dir", "x"], normative=False)
        self.add("explicit daemon word", ["daemon", "-dir", "x"], normative=False)

    def conventions(self):
        d = self.fresh()
        self.add("-dir=value", [f"-dir={d[1]}", "-sockets", d[3]], normative=False)
        self.add("-- ends flags", d + ["--", "-no-such-flag"], normative=False)
        self.add("positional at daemon", d + ["word"], normative=False)
        self.add("SERVER_NAME out of id", d, normative=False, env={"SERVER_NAME": "_bad"})
        self.add("no SERVER_NAME", d, normative=False, env={})
        self.add("SERVER_NAME with -join", d + ["-join", f"127.0.0.1:{free_port()}"], normative=False)

    def fuzz(self, n, seed):
        rnd = random.Random(seed)
        words = [r["flag"] for r in self.m.rows] + ["-no-such", "--", "word", "-x=1"]
        for k in range(n):
            argv = [rnd.choice(self.m.commands)] if rnd.random() < 0.3 else []
            for _ in range(rnd.randint(0, 8)):
                w = rnd.choice(words)
                r = self.m.by.get(w)
                if r and r["type"] != "bool":
                    pool = (self.good(r) or ["x"]) + self.bad(r)
                    v = rnd.choice(pool)
                    argv += [f"{w}={v}"] if rnd.random() < 0.15 else [w, v]
                else:
                    argv.append(w)
            env = rnd.choice([{"SERVER_NAME": "judge"}, {}, {"SERVER_NAME": "_x"}])
            self.add(f"fuzz {k}", argv, normative=False, env=env)


# ---------------------------------------------------------------- исполнение

RAFT = ("-join", "-door", "-voters", "-bootstrap", "-raft", "-raft-bind")


def raft_flags(argv):
    """Проба с флагами группы: сборка без raft (store_build box) отказывает её кодом 2 (Н4 1.3 box_no_raft)."""
    gs = [argv[k + 1] for k, a in enumerate(argv[:-1]) if a == "-group-size"]
    return any(a.split("=")[0] in RAFT for a in argv) or any(v in ("3", "5") for v in gs)


def run(cmd, cwd, probe, stub, ok_wait, box=False):
    argv = shlex.split(cmd) + probe["argv"]
    env = {k: v for k, v in os.environ.items() if k != "SERVER_NAME"}
    env.update(probe["env"])
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
    limit = 10 if probe["expect"] == "refuse" else ok_wait
    try:
        out, err = proc.communicate(timeout=limit)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        code = None
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                break
            try:
                out, err = proc.communicate(timeout=3)
                break
            except subprocess.TimeoutExpired:
                continue
    alive = code is None
    if probe["expect"] == "refuse":
        if code != 2:
            return f"want a start refusal (code 2 within 10 s), got {'alive' if alive else f'code {code}'}"
    elif code == 2 and not (box and raft_flags(probe["argv"])):
        return f"want a start, got code 2: {err.decode(errors='replace').strip()[:300]}"
    if not stub:
        return None
    try:
        got = json.loads(out.decode())
    except ValueError:
        return f"the stub did not print JSON: {out[:200]!r}"
    if probe["expect"] == "refuse":
        if got != {"refusal": probe["want"]}:
            return f"want the refusal of {probe['want']}, got {got}"
        return None
    if code != 0:
        return f"the stub exited {code}"
    fields = got.get("fields", {})
    fields["Given"] = sorted(fields.get("Given", []))
    if fields != probe["want"]:
        diff = {k: (probe["want"].get(k), fields.get(k)) for k in set(fields) | set(probe["want"])
                if probe["want"].get(k) != fields.get(k)}
        return f"fields differ (want, got): {diff}"
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cmd", required=True, help="the daemon command (shell words); the probe flags are appended")
    ap.add_argument("--cwd", default=".")
    ap.add_argument("--stub", action="store_true", help="the stub of tools/normgen/flags/stub: compare the values too")
    ap.add_argument("--rights-file")
    ap.add_argument("--tls-dir")
    ap.add_argument("--ok-wait", type=float, default=2.0)
    ap.add_argument("--box", action="store_true", help="a build without raft (profile store_build: box): a start "
                    "probe with group flags may end with code 2 (P/01.3 box_no_raft)")
    ap.add_argument("--fuzz", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--table", default=str(TABLE))
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    try:
        model = Model(read_table(a.table))
    except ImportError:
        print("flag_judge: cel_expr_python is needed (/opt/check-env/lesson-spec/bin/python)", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="flag-judge-") as tmp:
        probes = Probes(model, tmp, a.stub, a.rights_file, a.tls_dir).build(a.fuzz, a.seed)
        results, skipped = [], 0
        for p in probes:
            if not a.stub and (not p["normative"] or any(
                    x in p["argv"] for x in ("-rights", "-tls")) and p["expect"] == "ok" and not (
                    a.rights_file if "-rights" in p["argv"] else a.tls_dir)):
                skipped += 1
                continue
            why = run(a.cmd, a.cwd, p, a.stub, a.ok_wait if not a.stub else 10, a.box)
            results.append({"name": p["name"], "argv": p["argv"], "expect": p["expect"], "ok": why is None,
                            "why": why})
            if why:
                print(f"FAIL {p['name']}: {shlex.join(p['argv'])}: {why}", flush=True)
    passed = sum(r["ok"] for r in results)
    verdict = "PASS" if passed == len(results) and results else "FAIL"
    print(f"flags: {passed}/{len(results)} {verdict}" + (f" (skipped {skipped})" if skipped else ""))
    if a.json:
        Path(a.json).write_text(json.dumps({"passed": passed, "total": len(results), "skipped": skipped,
                                            "verdict": verdict, "results": results}, ensure_ascii=False, indent=1))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
