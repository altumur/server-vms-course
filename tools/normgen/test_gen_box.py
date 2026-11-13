"""Judge generated box against an independent Python normative model.

  /opt/check-env/lesson-spec/bin/python tools/normgen/test_gen_box.py [-v]
Require Go 1.22. Check output freshness and vet. Independently derive Status, metrics, join/leave/admit/recover, no-raft startup, copy encoding/decoding, import, floor and backup rules from the named P/01.3 clauses, P/01.1 ceiling, state clarification and max_value rule. Compare valid inputs, each input-refusal corruption, UTF-8 key ordering, round trips, generation boundaries and backup symlink containment with Go harness results. Each one-edit package mutant must disagree with the model at least once."""
import lesson as output_lesson
import base64
import csv
import re
from unittest.mock import patch
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen_box  # noqa: E402

OUT = gen_box.DEFAULT_OUT / "go"
MODULE = gen_box.GO_MODULE

HARNESS = r'''package main

import (
	"bufio"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"time"

	"%(m)s/apidoor"
	"%(m)s/box"
	"%(m)s/flags"
)

type cfg struct {
	ID, API string
	TLS     bool
	Max     int64
	MaxBody int64
}

type cs struct {
	Op      string
	Cfg     cfg
	Ix      [3]uint64
	Body    string
	Group   int64
	Join    string
	Door    bool
	Data    string
	Ceiling int64
	Index   uint64
	Rows    []box.Row
	Upper   uint64
	Now     string
	File    string
	Dir     string
}

func answer(op apidoor.Op, a apidoor.Answer) map[string]any {
	r, err := apidoor.Encode(op, a)
	if err != nil {
		return map[string]any{"err": err.Error()}
	}
	return map[string]any{"code": r.Code, "body": string(r.Body)}
}

func main() {
	in := bufio.NewScanner(os.Stdin)
	in.Buffer(make([]byte, 1<<26), 1<<26)
	out := json.NewEncoder(os.Stdout)
	for in.Scan() {
		var c cs
		if err := json.Unmarshal(in.Bytes(), &c); err != nil {
			panic(err)
		}
		bc := box.Config{ID: c.Cfg.ID, API: c.Cfg.API, TLS: c.Cfg.TLS, MaxValue: c.Cfg.Max, MaxBody: c.Cfg.MaxBody}
		ix := box.Indices{Last: c.Ix[0], Commit: c.Ix[1], Applied: c.Ix[2]}
		var logs []string
		logf := func(s string) { logs = append(logs, s) }
		var r any
		switch c.Op {
		case "config":
			v:=box.ConfigOf(&flags.Flags{ID:c.Cfg.ID,API:c.Cfg.API,MaxValue:c.Cfg.Max,MaxBody:c.Cfg.MaxBody})
			r=map[string]any{"max_value":v.MaxValue,"max_body":v.MaxBody}
		case "status":
			r = answer(apidoor.OpStatus, box.Status(bc, ix, nil))
		case "metrics":
			r = answer(apidoor.OpMetrics, box.Metrics(ix))
		case "join":
			r = answer(apidoor.OpJoin, box.Join(bc, []byte(c.Body)))
		case "leave":
			r = answer(apidoor.OpLeave, box.Leave(bc, []byte(c.Body)))
		case "admit":
			r = map[string]any{"code": box.Admit(logf, "x"), "log": logs}
		case "recover":
			r = map[string]any{"code": box.Recover(logf), "log": logs}
		case "start":
			code, refused := box.StartRefusal(&flags.Flags{GroupSize: c.Group, Join: c.Join, Door: c.Door}, logf)
			r = map[string]any{"code": code, "refused": refused}
		case "decode":
			data, _ := base64.StdEncoding.DecodeString(c.Data)
			index, rows, e := box.DecodeCopy(data, c.Ceiling)
			if e != nil {
				r = map[string]any{"refused": true, "line": e.Line, "cause": e.Cause}
			} else {
				if rows == nil {
					rows = []box.Row{}
				}
				r = map[string]any{"refused": false, "index": index, "rows": rows}
			}
		case "encode":
			b, err := box.EncodeCopy(c.Index, c.Rows)
			if err != nil {
				r = map[string]any{"err": err.Error()}
			} else {
				r = map[string]any{"data": base64.StdEncoding.EncodeToString(b)}
			}
		case "floor":
			now, _ := time.Parse(time.RFC3339, c.Now)
			g, f, ok := box.Floor(c.Upper, now)
			r = map[string]any{"generation": g, "floor": f, "ok": ok}
		case "backup":
			r = map[string]any{"inside": box.BackupTarget(c.File, c.Dir) != nil}
		default:
			panic(c.Op)
		}
		if err := out.Encode(r); err != nil {
			panic(err)
		}
	}
	fmt.Fprint(os.Stderr, "")
}
'''


# ---------------------------------------------------------------- normative model

F = gen_box.facts()
def source_flag_default(flag):
    path = HERE.parents[1] / "Platform/01-store/forms/daemon-flags.tsv"
    rows = list(csv.DictReader((line for line in path.read_text().split("\n")
                               if line and not line.startswith("#")), delimiter="\t"))
    found = [row for row in rows if row["flag"] == flag]
    if len(found) != 1 or found[0]["type"] != "bytes:>0" or not re.fullmatch(r"[1-9][0-9]*", found[0]["default"]):
        raise AssertionError(f"one literal positive bytes default required: {flag}")
    return int(found[0]["default"])


CEIL = source_flag_default("-max-value")
BODY_LIMIT = source_flag_default("-max-body")


def status(c, ix):
    return {"id": c["ID"], "state": "Leader", "leader": c["API"], "leader_id": c["ID"], "term": 1, "commit": ix[1],
            "applied": ix[2], "voters": [c["ID"]], "members": {c["ID"]: c["API"]} if c["API"] else {}, "tls": c["TLS"],
            "max_value": c["Max"], "max_body": c["MaxBody"]}


def metrics(ix):
    lines = {"configstore_raft_term": "1", 'configstore_raft_state{state="leader"}': "1",
             "configstore_raft_elections_total": "1", 'configstore_raft_index{kind="last"}': str(ix[0]),
             'configstore_raft_index{kind="commit"}': str(ix[1]), 'configstore_raft_index{kind="applied"}': str(ix[2]),
             "configstore_raft_last_contact_seconds": "0", "configstore_raft_voters": "1",
             "configstore_raft_voters_expected": "1", "configstore_doors": "0"}
    return lines


def parse_metrics(text):
    out = {}
    for ln in text.split("\n"):
        if ln and not ln.startswith("#"):
            k, v = ln.rsplit(" ", 1)
            out[k] = v
    return out


def is_key(k):
    return bool(k) and not k.startswith("/") and ".." not in k.split("/")


def is_version(s):
    import re
    return isinstance(s, str) and re.fullmatch(r"0|[1-9][0-9]{0,19}", s) is not None and int(s) < 2 ** 64


def strict(line):
    def pairs(items):
        ks = [k for k, _ in items]
        if len(ks) != len(set(ks)):
            raise ValueError("dup")
        return dict(items)
    return json.loads(line, object_pairs_hook=pairs, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))


def model_decode(data, ceiling):
    """Return None on refusal, otherwise (index, {key:(items, index)})."""
    import re
    if not data or not data.endswith(b"\n"):
        return None
    try:
        lines = data[:-1].decode("utf-8").split("\n")
        head = strict(lines[0])
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(head, dict) or set(head) != {"format", "version", "index"}:
        return None
    if head["format"] != F["copy_format"] or head["version"] != F["copy_version"] or isinstance(head["version"], bool):
        return None
    if type(head["version"]) is not int or not is_version(head["index"]):
        return None
    index, rows = int(head["index"]), {}
    sub, uid = F["<sub>"][4:-2], F["<id>"][4:-2]
    for ln in lines[1:]:
        try:
            m = strict(ln)
        except ValueError:
            return None
        if not isinstance(m, dict) or set(m) != {"key", "items", "index"}:
            return None
        k, items, ver = m["key"], m["items"], m["index"]
        if not isinstance(k, str) or not is_key(k) or k in rows:
            return None
        if not isinstance(items, dict) or not all(isinstance(v, str) for v in items.values()) or not is_version(ver):
            return None
        if int(ver) > index:
            return None
        if sum(len(a.encode()) + len(b.encode()) for a, b in items.items()) > ceiling:
            return None
        if re.fullmatch(f"(?:{sub})/epoch/(?:{uid})", k) and not is_version(items.get("epoch")):
            return None
        if k == "platform/epoch_floor" and not is_version(items.get("floor")):
            return None
        rows[k] = (items, int(ver))
    return index, rows


def model_floor(upper, now):
    hours = int((now - datetime(2026, 1, 1, tzinfo=timezone.utc)).total_seconds() // 3600)
    g = max((upper >> 32) + 1, hours)
    if g > 2 ** 21 - 1:
        return None
    return g, g << 32


def copy_bytes(index, rows, head=None):
    h = head if head is not None else {"format": F["copy_format"], "version": F["copy_version"], "index": str(index)}
    out = [json.dumps(h)] + [r if isinstance(r, str) else json.dumps(r) for r in rows]
    return ("\n".join(out) + "\n").encode()


def decode_cases():
    good = [{"key": "acc/a", "items": {"v": "1"}, "index": "3"}, {"key": "platform/epoch_floor",
            "items": {"floor": "4294967296", "generation_at": "2026-01-01T00:00:00Z"}, "index": "2"},
            {"key": "testsub/epoch/t1", "items": {"epoch": "5"}, "index": "4"}, {"key": "z/b", "items": {}, "index": "0"}]
    cases = [copy_bytes(9, good), copy_bytes(9, good[::-1]), copy_bytes(0, []), b"", copy_bytes(9, good)[:-1]]

    def mut(i, **kw):
        rows = [dict(r) for r in good]
        rows[i].update(kw)
        return copy_bytes(9, rows)
    cases += [
        copy_bytes(9, good, {"format": "other", "version": 1, "index": "9"}),
        copy_bytes(9, good, {"format": F["copy_format"], "version": 2, "index": "9"}),
        copy_bytes(9, good, {"format": F["copy_format"], "version": 1, "index": "9", "x": 1}),
        copy_bytes(9, good, {"format": F["copy_format"], "version": 1}),
        copy_bytes(9, good, {"format": F["copy_format"], "version": 1, "index": 9}),
        copy_bytes(9, good, {"format": F["copy_format"], "version": 1.0, "index": "9"}),
        copy_bytes(9, good + ["not json"]),
        copy_bytes(9, good + ['{"key": "q", "key": "q", "items": {}, "index": "1"}']),
        copy_bytes(9, good + [good[0]]),
        mut(0, index="10"), mut(0, index="01"), mut(0, items={"v": 1}), mut(0, items=None),
        mut(0, key="/abs"), mut(0, key="a/../b"), mut(0, key=""), mut(0, extra=True),
        mut(2, items={"epoch": "x"}), mut(2, items={"epoch": "05"}), mut(1, items={"floor": "1.0"}),
        copy_bytes(9, good + [{"key": "u", "items": None, "index": "1", "unreadable": True}]),
        copy_bytes(9, good + [{"key": "big", "items": {"v": "x" * (CEIL - 1)}, "index": "1"}]),
        copy_bytes(9, good + [{"key": "big", "items": {"v": "x" * (CEIL - 2)}, "index": "1"}]),
        copy_bytes(9, good + [{"key": "big", "items": {"v": "x" * CEIL}, "index": "1"}]),
        copy_bytes(9, good + ["[1]"]),
        b"\xef\xbb\xbf" + copy_bytes(9, good),
    ]
    return cases


class Box(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("go") is None:
            raise unittest.SkipTest("no go")
        cls.tmp = Path(tempfile.mkdtemp(prefix="judge-box-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def harness(self, mutate=None):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        mod = self.tmp / ("m" if mutate is None else f"m{abs(hash(mutate[0])) % 10 ** 8}")
        shutil.rmtree(mod, ignore_errors=True)
        shutil.copytree(OUT, mod)
        if mutate:
            p = mod / "box" / mutate[0]
            src = p.read_text()
            if mutate[1] not in src:
                raise AssertionError(f"mutant: {mutate[1]!r} not in {mutate[0]}")
            p.write_text(src.replace(mutate[1], mutate[2], 1))
        (mod / "cmd/boxjudge").mkdir(parents=True, exist_ok=True)
        (mod / "cmd/boxjudge/main.go").write_text(HARNESS % {"m": MODULE})
        exe = mod / "boxjudge"
        b = subprocess.run(["go", "build", "-o", str(exe), "./cmd/boxjudge"], cwd=mod, capture_output=True, text=True)
        if b.returncode:
            raise AssertionError(b.stderr)
        return exe

    def cases(self):
        d = self.tmp / "fs"
        shutil.rmtree(d, ignore_errors=True)
        (d / "data").mkdir(parents=True)
        (d / "out").mkdir()
        os.symlink(d / "data", d / "link")
        cfgs = [{"ID": "s1", "API": "127.0.0.1:9001", "TLS": True, "Max": CEIL, "MaxBody": BODY_LIMIT},
                {"ID": "box-2", "API": "", "TLS": False, "Max": 1000, "MaxBody": 2000000}]
        cs = []
        for c in cfgs:
            cs.append(({"Op": "config", "Cfg": c}, ("config", c)))
            for ix in ([0, 0, 0], [7, 7, 7], [2 ** 64 - 1, 5, 4]):
                cs.append(({"Op": "status", "Cfg": c, "Ix": ix}, ("status", c, ix)))
            cs.append(({"Op": "metrics", "Ix": [3, 2, 1]}, ("metrics", [3, 2, 1])))
            for body, want in ((json.dumps({"id": c["ID"], "raft": "127.0.0.1:1", "api": "127.0.0.1:2"}), 200),
                               (json.dumps({"id": c["ID"], "raft": "r", "api": "a", "force": True}), 200),
                               (json.dumps({"id": "other", "raft": "r", "api": "a"}), 409),
                               (json.dumps({"id": "other", "raft": "r", "api": "a", "force": True}), 409),
                               (json.dumps({"id": "x1", "raft": "", "api": ""}), 400),
                               (json.dumps({"id": c["ID"], "raft": "r", "api": "a", "zz": 1}), 400),
                               ('{"id": "a"', 400), ("[1]", 400), ('{"id":"a","id":"a","raft":"r","api":"a"}', 400)):
                cs.append(({"Op": "join", "Cfg": c, "Body": body}, ("code", want)))
            for body, want in (('{"id": ""}', 409), (json.dumps({"id": c["ID"]}), 409), ('{"id": "zz"}', 409),
                               ('{"x": 1}', 400), ("nope", 400)):
                cs.append(({"Op": "leave", "Cfg": c, "Body": body}, ("code", want)))
        cs += [({"Op": "admit"}, ("exit", "nonzero", "the last voter")),
               ({"Op": "recover"}, ("exit", 2, "this build has no raft"))]
        for g, j, door, want in ((1, "", False, False), (3, "", False, True), (5, "", False, True),
                                 (1, "h:1", False, True), (1, "", True, True)):
            cs.append(({"Op": "start", "Group": g, "Join": j, "Door": door}, ("start", want)))
        for data in decode_cases():
            cs.append(({"Op": "decode", "Data": base64.b64encode(data).decode(), "Ceiling": CEIL},
                       ("decode", data, CEIL)))
        rows = [{"Key": k, "Items": it, "Index": ix, "Unreadable": False}
                for k, it, ix in (("b/x", {"v": "é <"}, 2), ("a/y", {}, 1), ("a/x", {"z": "1", "a": "2"}, 3))]
        cs.append(({"Op": "encode", "Index": 3, "Rows": rows}, ("encode", rows, 3)))
        cs.append(({"Op": "encode", "Index": 2, "Rows": rows}, ("encode-err",)))
        for upper, now, want in ((5, "2026-10-17T12:30:00Z", (6948, 29841432772608)),
                                 (30064771072005, "2026-10-17T12:30:00Z", (7001, 30069066039296)),
                                 (0, "2025-06-01T00:00:00Z", (1, 1 << 32)),
                                 ((2 ** 21 - 2) << 32, "2026-10-17T12:30:00Z", (2 ** 21 - 1, (2 ** 21 - 1) << 32)),
                                 ((2 ** 21 - 1) << 32, "2026-10-17T12:30:00Z", None)):
            m = model_floor(upper, datetime.fromisoformat(now.replace("Z", "+00:00")))
            assert m == want, (upper, now, m, want)              # Model from normative examples.
            cs.append(({"Op": "floor", "Upper": upper, "Now": now}, ("floor", want)))
        for f, dd, want in ((d / "data/c.jsonl", d / "data", True), (d / "link/c.jsonl", d / "data", True),
                            (d / "out/c.jsonl", d / "data", False), (d / "data", d / "data", True),
                            (d / "out/c.jsonl", d / "link", False), (d / "link/sub/c", d / "data", True)):
            cs.append(({"Op": "backup", "File": str(f), "Dir": str(dd)}, ("backup", want)))
        return cs

    def mismatches(self, exe):
        cs = self.cases()
        p = subprocess.run([str(exe)], input="\n".join(json.dumps(c) for c, _ in cs) + "\n", capture_output=True,
                           text=True, timeout=120)
        if p.returncode:
            raise AssertionError(f"checking harness exit {p.returncode}, not a semantic kill: {p.stderr[-400:]}")
        got = [json.loads(x) for x in p.stdout.split("\n") if x]
        if len(got) != len(cs):
            raise AssertionError(f"incomplete checking report: {len(got)} answers for {len(cs)} cases")
        bad = []
        for (c, want), g in zip(cs, got):
            if not self.agree(want, g):
                bad.append(f"{c['Op']}: want {str(want)[:120]} got {str(g)[:200]}")
        return bad

    def agree(self, want, g):
        k = want[0]
        if k == "config":
            return g == {"max_value": want[1]["Max"], "max_body": want[1]["MaxBody"]}
        if k == "status":
            return g.get("code") == 200 and json.loads(g["body"]) == status(want[1], want[2])
        if k == "metrics":
            return g.get("code") == 200 and parse_metrics(g["body"]) == metrics(want[1])
        if k == "code":
            if g.get("code") != want[1]:
                return False
            body = json.loads(g["body"])
            return body == {} if want[1] == 200 else body.get("kind") == {409: "refused", 400: "badrequest"}[want[1]]
        if k == "exit":
            ok = g["code"] != 0 if want[1] == "nonzero" else g["code"] == want[1]
            return ok and any(want[2] in x for x in g["log"])
        if k == "start":
            return g["refused"] == want[1] and (g["code"] == 2) == want[1]
        if k == "decode":
            m = model_decode(want[1], want[2])
            if m is None:
                return g["refused"] is True
            if g["refused"]:
                return False
            return g["index"] == m[0] and {r["Key"]: (r["Items"], r["Index"]) for r in g["rows"]} == m[1] and \
                len(g["rows"]) == len(m[1])
        if k == "encode":
            if "data" not in g:
                return False
            data = base64.b64decode(g["data"])
            m = model_decode(data, CEIL)
            keys = [json.loads(x)["key"] for x in data.decode().split("\n")[1:] if x]
            return m is not None and m[0] == want[2] and keys == sorted(keys, key=lambda s: s.encode()) and \
                m[1] == {r["Key"]: (r["Items"], r["Index"]) for r in want[1]}
        if k == "encode-err":
            return "err" in g
        if k == "floor":
            return (not g["ok"]) if want[1] is None else (g["ok"] and (g["generation"], g["floor"]) == want[1])
        if k == "backup":
            return g["inside"] == want[1]
        raise AssertionError(k)

    def test_fresh_and_vet(self):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        files, _ = gen_box.render()
        for rel, text in files.items():
            self.assertEqual((OUT / rel).read_text(encoding="utf-8"), text, f"{rel} is stale: run gen_box.py")
        v = subprocess.run(["go", "vet", "./box/"], cwd=OUT, capture_output=True, text=True)
        self.assertEqual(v.returncode, 0, v.stderr)

    def test_model(self):
        self.assertEqual(self.mismatches(self.harness()), [])

    def test_mutants(self):
        mutants = [
            ("box.go", "State: \"Leader\"", "State: \"Follower\""),
            ("box.go", "Term: 1,", "Term: 2,"),
            ("box.go", "MaxBody: c.MaxBody", "MaxBody: c.MaxValue"),
            ("box.go", "MaxBody: f.MaxBody", "MaxBody: f.MaxValue"),
            ("box.go", "members[c.ID] = c.API", "members[c.ID] = c.ID"),
            ("box.go", "label(\"state\", \"leader\")", "label(\"state\", \"Leader\")"),
            ("box.go", "if j.Id == c.ID {", "if j.Id != \"\" {"),
            ("box.go", "f.GroupSize == 3 || ", ""),
            ("copy.go", "if seen[key] {", "if false && seen[key] {"),
            ("copy.go", "if ix > index {", "if ix > index+1 {"),
            ("copy.go", "if weight > ceiling {", "if weight > ceiling+1 {"),
            ("copy.go", "if epochKey.MatchString(key) && !decimalItem(items, \"epoch\") {", "if false {"),
            ("copy.go", "generation = (upper >> 32) + 1", "generation = (upper >> 32)"),
            ("copy.go", "if generation > MaxGeneration {", "if generation > MaxGeneration+1 {"),
            ("copy.go", "sort.Slice(rs, func(i, j int) bool { return rs[i].Key < rs[j].Key })", ""),
            ("copy.go", "if !sameKeys(head, \"format\", \"version\", \"index\") {", "if false {"),
            ("copy.go", "if f == d || ", "if "),
        ]
        alive = []
        for m in mutants:
            if not self.mismatches(self.harness(m)):
                alive.append(m)
        self.assertEqual(alive, [], "mutants not killed")



class BoxBindings(unittest.TestCase):
    """Current flags are the value oracle; the renderer is only the subject."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='box-source-bindings-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.original_root = gen_box.ROOT
        sources = {name: getattr(gen_box, name) for name in
                   ('NORMS_11', 'NORMS_13', 'FLAGS', 'OPENAPI', 'REFUSALS', 'KEYS_README', 'METRICS', 'STATUS_FIELDS')}
        changes = {'ROOT': self.root}
        for name, source in sources.items():
            target = self.root / source.relative_to(self.original_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            changes[name] = target
        change = patch.multiple(gen_box, **changes)
        change.start()
        self.addCleanup(change.stop)

    def compiled_readback(self, files, name, body):
        ready = output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        mod = self.root / name
        shutil.copytree(ready['p01-1'] / 'go', mod)
        for relative, text in files.items():
            target = mod / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        (mod / 'bindingprobe').mkdir()
        (mod / 'bindingprobe/main.go').write_text('package main\nimport("encoding/json";"os";"reflect";"' +
            MODULE + '/box";"' + MODULE + '/flags")\n' + body)
        done = subprocess.run(['go', 'run', './bindingprobe'], cwd=mod, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, 'component checking build/run failed: ' + done.stderr)
        return json.loads(done.stdout)

    def test_unique_current_flag_binding_and_changed_default(self):
        self.assertEqual(gen_box.facts()['ceiling'], source_flag_default('-max-value'))
        self.assertTrue(gen_box.facts()['status_max_body'])
        original = gen_box.FLAGS.read_text()
        rows = original.split('\n')
        index = next(i for i, line in enumerate(rows) if line.startswith('-max-value\t'))
        cells = rows[index].split('\t')
        cells[2], cells[3] = '777', '777'
        rows[index] = '\t'.join(cells)
        gen_box.FLAGS.write_text('\n'.join(rows))
        self.assertEqual(gen_box.facts()['ceiling'], 777)
        files, _ = gen_box.render()
        self.assertRegex(files['box/copy.go'], r'\bRowCeiling\s*=\s*777\b')
        # The default projection does not replace the instance value in Status.
        self.assertIn('MaxValue: c.MaxValue', files['box/box.go'])
        self.assertIn('MaxBody: c.MaxBody', files['box/box.go'])

    def test_changed_default_and_instance_limits_compile_independently(self):
        text = gen_box.FLAGS.read_text()
        row = next(line for line in text.split('\n') if line.startswith('-max-value\t'))
        cells = row.split('\t')
        cells[2], cells[3] = '777', '777'
        gen_box.FLAGS.write_text(text.replace(row, '\t'.join(cells), 1))
        files, _ = gen_box.render()
        got = self.compiled_readback(files, 'changed-default',
            'func main(){c:=box.ConfigOf(&flags.Flags{MaxValue:123,MaxBody:999});' +
            '_,has:=reflect.TypeOf(c).FieldByName("MaxBody");' +
            'json.NewEncoder(os.Stdout).Encode(map[string]any{"default":box.RowCeiling,"value":c.MaxValue,"body":c.MaxBody,"has_body":has})}')
        self.assertEqual(got, {'default': 777, 'value': 123, 'body': 999, 'has_body': True})

    def test_missing_duplicate_malformed_flag_and_binding_refuse(self):
        original = gen_box.FLAGS.read_text()
        row = next(line for line in original.split('\n') if line.startswith('-max-value\t'))
        for changed in (original.replace(row + '\n', ''), original + row + '\n',
                        original.replace(row, row.replace('bytes:>0', 'bool', 1)),
                        original.replace(row, row.replace('\t524288\t', '\t-\t', 1))):
            self.assertNotEqual(changed, original)
            gen_box.FLAGS.write_text(changed)
            with self.assertRaises(gen_box.GenError):
                gen_box.facts()
        gen_box.FLAGS.write_text(original)
        text = gen_box.NORMS_11.read_text()
        self.assertEqual(text.count('ceiling: ROW_CEILING'), 1)
        for changed in (text.replace('ceiling: ROW_CEILING', 'ceiling: UNKNOWN_VALUE'),
                        text.replace('ceiling: ROW_CEILING', 'ceiling: ROW_CEILING_ALIAS'),
                        text + '\nceiling: ROW_CEILING\n'):
            gen_box.NORMS_11.write_text(changed)
            with self.assertRaises(gen_box.GenError):
                gen_box.facts()

    def test_explicit_old_pin_keeps_config_abi_without_max_body(self):
        import hashlib
        pin = '7b96ff9f84e8090e11922131bc77799f0a0b54e1'
        relative = 'Platform/01-store/spec/01-store.api.openapi.yaml'
        command = ['bash', '-c', 'cd "$1" || exit 1\ngit rev-parse --show-toplevel >&2\nshift\ngit show "$1:$2"',
                   'box-historical-input', str(self.original_root), pin, relative]
        old = subprocess.check_output(command)
        self.assertEqual(hashlib.sha256(old).hexdigest(),
                         'e86407dc83b04cf6013eed6b469702926c9e31f60d7647770696a183e6769d8e')
        gen_box.OPENAPI.write_bytes(old)
        self.assertFalse(gen_box.facts()['status_max_body'])
        files, _ = gen_box.render()
        self.assertNotIn('MaxBody', files['box/box.go'])
        self.assertIn('MaxValue: f.MaxValue', files['box/box.go'])
        got = self.compiled_readback(files, 'historical-api-capability',
            'func main(){c:=box.ConfigOf(&flags.Flags{MaxValue:123,MaxBody:999});' +
            '_,has:=reflect.TypeOf(c).FieldByName("MaxBody");' +
            'json.NewEncoder(os.Stdout).Encode(map[string]any{"value":c.MaxValue,"has_body":has})}')
        self.assertEqual(got, {'value': 123, 'has_body': False})



class BoxReportControls(unittest.TestCase):
    def test_execution_and_partial_reports_never_count_as_mutant_disagreement(self):
        subject = Box()
        cases = [({'Op': 'fixture'}, ('fixture',))]
        for code, output in ((1, ''), (0, ''), (0, '{}\n{}\n')):
            done = subprocess.CompletedProcess([], code, output, 'environment failure' if code else '')
            with self.subTest(code=code, output=output), patch.object(subject, 'cases', return_value=cases), \
                    patch('subprocess.run', return_value=done), self.assertRaises(AssertionError):
                subject.mismatches('/owned-fixture')
        done = subprocess.CompletedProcess([], 0, '{}\n', '')
        with patch.object(subject, 'cases', return_value=cases), patch.object(subject, 'agree', return_value=False), \
                patch('subprocess.run', return_value=done):
            self.assertEqual(len(subject.mismatches('/owned-fixture')), 1)

if __name__ == "__main__":
    unittest.main()
