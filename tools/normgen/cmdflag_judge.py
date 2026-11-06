"""Judge for command-based flags (P/02: operator-commands.tsv and daemon-flags.tsv; ADR-0125 addendum (5)).

On CT 103, use /opt/check-env/lesson-spec/bin/python with cel_expr_python:
  python tools/normgen/cmdflag_judge.py --lesson 02-installer [--module-dir <flags-module-directory>] [--json <result>]

The independent model rereads both forms. Like check_forms, its CEL oracle evaluates required and bad over f (numbers as numbers, booleans as true) and cmd. Per command, test a valid base with required options and minimum positionals, too few or too many positionals, unknown and foreign options, repeats, explicit bool values, missing option values, non-decimal numbers (+1, 1e3, .5, inf, abc), -name=value, each omitted required option, required/bad option pairs, and unknown command prefixes. Base strings are selected to make bad false. The flags/cmdharness prints ParseArgv's refusal or command, positionals, given options and field values. Compare acceptance/refusal and, for accepted inputs, command, positionals, given options and numeric values. Non-execution fails. Result: `flags: P/NN N/N PASS|FAIL`; exit 0 means PASS."""
import argparse
import itertools
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import lesson  # noqa: E402 -- lesson selection (ADR-0125 addendum (5), item 2)
L = lesson.CURRENT

NUMBER = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")
BAD_NUMBERS = ("+1", "1e3", ".5", "inf", "abc", "01", "1.", "")
STRING_SAMPLES = ("x", "0" * 64, "a" * 64, "dep")


def rows_of(path):
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")]
    head = lines[0].split("\t")
    return [dict(zip(head, ln.split("\t"))) for ln in lines[1:]]


class Model:
    def __init__(self, flags_path, commands_path):
        from cel_expr_python import cel
        self.cel = cel
        self.flags = rows_of(flags_path)
        for r in self.flags:
            r["commands"] = r["commands"].split(",")
        self.by = {r["flag"]: r for r in self.flags}
        self.commands = []
        for r in rows_of(commands_path):
            schema = json.loads(r["positionals"])
            self.commands.append({"id": r["command"], "process": r["process"], "prefix": json.loads(r["prefix"]),
                                  "min": schema.get("minItems", 0), "max": schema.get("maxItems")})
        T = cel.Type
        cfg = cel.NewEnvConfigFromYaml("name: flags\nextensions:\n  - name: strings\n")
        self.env = cel.NewEnv(config=cfg, variables={"f": T.Map(T.STRING, T.DYN), "cmd": T.STRING})
        self.compiled = {(r["flag"], c): self.env.compile(r[c]) for r in self.flags for c in ("required", "bad")
                         if r[c] and r[c] not in ("true", "false")}

    def true(self, flag, col, f, cmd):
        text = self.by[flag][col]
        if text in ("true", "false"):
            return text == "true"
        v = self.compiled[flag, col].eval(data={"f": f, "cmd": cmd})
        return v.type() != self.cel.Type.ERROR and v.plain_value() is True

    def lookup(self, process, argv):
        best = None
        for c in self.commands:
            p = c["prefix"]
            if c["process"] == process and argv[:len(p)] == p and (best is None or len(p) > len(best["prefix"])):
                best = c
        return best

    def expect(self, process, argv):
        """→ ("refuse",) | ("ok", cmd, args, given, numbers)."""
        c = self.lookup(process, argv)
        if c is None:
            return ("refuse",)
        cmd, args = c["id"], argv[len(c["prefix"]):]
        f, pos, numbers, k = {}, [], {}, 0
        while k < len(args):
            tok = args[k]
            if tok == "--":
                pos += args[k + 1:]
                break
            if len(tok) < 2 or tok[0] != "-":
                pos.append(tok)
                k += 1
                continue
            name, eq, raw = tok.partition("=")
            row = self.by.get(name)
            if row is None or cmd not in row["commands"] or name in f:
                return ("refuse",)
            if row["type"] == "bool":
                if eq:
                    return ("refuse",)
                f[name] = True
            else:
                if not eq:
                    if k + 1 >= len(args):
                        return ("refuse",)
                    k += 1
                    raw = args[k]
                if row["type"] == "number":
                    if not NUMBER.fullmatch(raw):
                        return ("refuse",)
                    f[name] = numbers[name] = float(raw)
                elif row["type"] == "file" and raw == "":
                    return ("refuse",)
                else:
                    f[name] = raw
            k += 1
        if len(pos) < c["min"] or (c["max"] is not None and len(pos) > c["max"]):
            return ("refuse",)
        for r in self.flags:
            if cmd in r["commands"] and r["flag"] not in f and r["required"] != "false" and \
                    self.true(r["flag"], "required", f, cmd):
                return ("refuse",)
        for r in self.flags:
            if r["flag"] in f and r["bad"] and self.true(r["flag"], "bad", f, cmd):
                return ("refuse",)
        return ("ok", cmd, pos, sorted(f), numbers)

    def value(self, row, cmd, f):
        """Choose a typed option sample whose bad predicate is false, if one exists."""
        if row["type"] == "bool":
            return None
        samples = {"number": ("1.5", "0", "85"), "file": ("/tmp/judge-file",)}.get(row["type"], STRING_SAMPLES)
        for s in samples:
            v = float(s) if row["type"] == "number" else s
            if not row["bad"] or not self.true(row["flag"], "bad", {**f, row["flag"]: v}, cmd):
                return s
        return samples[0]

    def probes(self):
        out = []
        for c in self.commands:
            cmd, pre, proc = c["id"], c["prefix"], c["process"]
            own = [r for r in self.flags if cmd in r["commands"]]
            req = [r for r in own if r["required"] == "true"]
            words, f = [], {}
            for r in req:
                v = self.value(r, cmd, f)
                words += [r["flag"]] if v is None else [r["flag"], v]
                f[r["flag"]] = True if v is None else (float(v) if r["type"] == "number" else v)
            pos = [f"p{i}" for i in range(c["min"])]
            base = pre + words + pos
            out.append((proc, base))
            out.append((proc, base + ["-no-such-option", "1"]))
            if c["min"]:
                out.append((proc, pre + words + pos[:-1]))
            if c["max"] is not None:
                out.append((proc, pre + words + [f"p{i}" for i in range(c["max"] + 1)]))
            out.append((proc, pre + words + ["--"] + pos))
            others = [r for r in self.flags if cmd not in r["commands"]]
            if others:
                out.append((proc, base + [others[0]["flag"]] + ([] if others[0]["type"] == "bool" else ["1"])))
            for r in own:
                v = self.value(r, cmd, f)
                given = r["flag"] in f
                rest = [w for w in base]
                if not given:
                    out.append((proc, rest + ([r["flag"]] if v is None else [r["flag"], v])))
                    if v is not None:
                        out.append((proc, rest + [f"{r['flag']}={v}"]))
                        out.append((proc, rest + [r["flag"]]))            # Missing final value.
                    else:
                        out.append((proc, rest + [f"{r['flag']}=true"]))
                out.append((proc, rest + ([r["flag"]] * 2 if v is None else [r["flag"], v, r["flag"], v])))
                if r["type"] == "number":
                    for b in BAD_NUMBERS:
                        out.append((proc, [w for w in rest if w != r["flag"]] + [r["flag"], b]))
            for r in req:
                i = base.index(r["flag"])
                cut = base[:i] + base[i + (1 if r["type"] == "bool" else 2):]
                out.append((proc, cut))
            cond = [r for r in own if r["required"] not in ("true", "false") or r["bad"]]
            for pair in itertools.combinations(own, 2):
                if not any(r in cond for r in pair):
                    continue
                extra = []
                for r in pair:
                    if r["flag"] in f:
                        continue
                    v = self.value(r, cmd, f)
                    extra += [r["flag"]] if v is None else [r["flag"], v]
                out.append((proc, base + extra))
            out.append((proc, pre[:-1] + ["no-such-command"] + words + pos) if len(pre) > 1 else
                       (proc, ["no-such-command"] + words + pos))
        seen, uniq = set(), []
        for proc, argv in out:
            key = (proc, tuple(argv))
            if key not in seen:
                seen.add(key)
                uniq.append((proc, argv))
        return uniq


HARNESS = '''// Harness of cmdflag_judge.py: JSON lines {process, argv} → the outcome of flags.ParseArgv.
package main

import (
	"bufio"
	"encoding/json"
	"os"
	"sort"

	"%s/flags"
)

func main() {
	in := bufio.NewScanner(os.Stdin)
	in.Buffer(make([]byte, 1<<20), 1<<24)
	out := json.NewEncoder(os.Stdout)
	for in.Scan() {
		var c struct {
			Process string   `json:"process"`
			Argv    []string `json:"argv"`
		}
		if err := json.Unmarshal(in.Bytes(), &c); err != nil {
			os.Exit(2)
		}
		fl, r := flags.ParseArgv(c.Process, c.Argv)
		if r != nil {
			_ = out.Encode(map[string]any{"ok": false, "refusal": r.Error()})
			continue
		}
		given := []string{}
		for k := range fl.Given {
			given = append(given, k)
		}
		sort.Strings(given)
		args := fl.Args
		if args == nil {
			args = []string{}
		}
		_ = out.Encode(map[string]any{"ok": true, "cmd": fl.Cmd, "args": args, "given": given, "fields": fl})
	}
}
'''


def field_name(flag):
    initialisms = {"id": "ID", "api": "API", "tls": "TLS"}
    return "".join(initialisms.get(p, p[:1].upper() + p[1:]) for p in flag.lstrip("-").split("-"))


def run_harness(module_dir, cases):
    with tempfile.TemporaryDirectory(prefix="cmdflag-judge-") as t:
        work = Path(t) / "h"
        work.mkdir()
        (work / "main.go").write_text(HARNESS % L.go_module, encoding="utf-8")
        (work / "go.mod").write_text(f"module normgen/cmdflagharness\n\ngo 1.22\n\nrequire {L.go_module} v0.0.0\n\n"
                                     f"replace {L.go_module} => {Path(module_dir).resolve()}\n", encoding="utf-8")
        env = {"GOFLAGS": "-mod=mod", "GOPROXY": "off", "GOWORK": "off", "GOTOOLCHAIN": "local"}
        import os
        env = dict(os.environ, **env)
        exe = Path(t) / "harness"
        done = subprocess.run(["go", "build", "-o", str(exe), "."], cwd=work, capture_output=True, text=True, env=env)
        if done.returncode:
            raise SystemExit(f"cmdflag_judge: the harness: {done.stderr.strip()[-2000:]}")
        data = "".join(json.dumps({"process": p, "argv": a}) + "\n" for p, a in cases)
        done = subprocess.run([str(exe)], input=data, capture_output=True, text=True)
        if done.returncode:
            raise SystemExit(f"cmdflag_judge: the harness exit {done.returncode}: {done.stderr[-2000:]}")
        return [json.loads(line) for line in done.stdout.splitlines()]


def judge(module_dir):
    flags_path, cmds_path = L.form("daemon-flags.tsv"), L.form("operator-commands.tsv")
    if not cmds_path.is_file():
        raise SystemExit(f"cmdflag_judge: {cmds_path.relative_to(ROOT)}: no command form (P/01 — flag_judge.py)")
    model = Model(flags_path, cmds_path)
    cases = model.probes()
    got = run_harness(module_dir, cases)
    bad = []
    if len(got) != len(cases):
        bad.append(f"{len(got)} answers for {len(cases)} probes")
    for (proc, argv), g in zip(cases, got):
        want = model.expect(proc, argv)
        if want[0] == "refuse":
            if g.get("ok") is not False:
                bad.append(f"{proc} {argv}: want a refusal, got {g}")
            continue
        _, cmd, pos, given, numbers = want
        if g.get("ok") is not True:
            bad.append(f"{proc} {argv}: want ok, got {g.get('refusal')}")
            continue
        if (g["cmd"], g["args"], g["given"]) != (cmd, pos, given):
            bad.append(f"{proc} {argv}: want {(cmd, pos, given)}, got {(g['cmd'], g['args'], g['given'])}")
        for flag, v in numbers.items():
            if g["fields"].get(field_name(flag)) != v:
                bad.append(f"{proc} {argv}: {flag} = {g['fields'].get(field_name(flag))}, want {v}")
    return {"lesson": L.key, "cases": len(cases), "pass": len(cases) - len({b.split(':')[0] for b in bad}) if bad
            else len(cases), "fail": bad,
            "accepted": sum(model.expect(p, a)[0] == "ok" for p, a in cases)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--module-dir", default=str(L.out / "go"))
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    try:
        import cel_expr_python  # noqa: F401
    except ImportError:
        print("cmdflag_judge: cel_expr_python is needed (/opt/check-env/lesson-spec/bin/python)", file=sys.stderr)
        return 2
    res = judge(a.module_dir)
    ok = not res["fail"]
    for b in res["fail"][:30]:
        print("FAIL", b)
    print(f"flags: {L.code} {res['cases'] - (len(res['fail']) and len(res['fail']))}/{res['cases']} "
          f"{'PASS' if ok else 'FAIL'} (accepted {res['accepted']})")
    if a.json:
        Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
