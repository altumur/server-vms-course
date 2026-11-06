"""Судья части `box` (gen_box.py): сгенерированный пакет box против своей модели нормы на Python.

Запуск: /opt/check-env/lesson-spec/bin/python tools/normgen/test_gen_box.py [-v]   (нужен go 1.22)

1. out свежий: out/p01-1/go/box равен свежему прогону генератора; go vet пакета чистый.
2. Модель: судья сам строит ожидания по местам нормы (P/01.3 Н1.3 `box`, `metrics`, `copy`, `import`, `floor`,
   `admin_ops`; P/01.1 Н1 ceiling; ответ sc. 17 о метке state; spec103 о max_value) — Status, текст /metrics, join/leave
   (свой id, чужой, -force, тело вне формы), admit/recover/старт без raft, вход копии (верная копия и её порча по
   каждому правилу отказа), кодер (порядок ключей, круг «закодировать — прочитать»), floor по примерам нормы и границе
   поколения, backup внутри -dir через ссылку; обвес Go гоняет те же случаи — исходы обязаны совпасть.
3. Мутанты пакета (по одной правке исходника): каждый должен дать хотя бы одно расхождение с моделью.
"""
import base64
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
	"strings"
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
		bc := box.Config{ID: c.Cfg.ID, API: c.Cfg.API, TLS: c.Cfg.TLS, MaxValue: c.Cfg.Max%(max_body_config)s}
		ix := box.Indices{Last: c.Ix[0], Commit: c.Ix[1], Applied: c.Ix[2]}
		var logs []string
		logf := func(s string) { logs = append(logs, s) }
		var r any
		switch c.Op {
		case "status":
			r = answer(apidoor.OpStatus, box.Status(bc, ix, nil))
		case "status-flags":
			f, refused := flags.Parse("daemon", []string{"-dir", "data", "-id", c.Cfg.ID,
				"-max-body", fmt.Sprint(c.Cfg.MaxBody), "-max-value", fmt.Sprint(c.Cfg.Max)},
				func(string) string { return "" })
			if refused != nil { panic(fmt.Sprint(refused)) }
			r = answer(apidoor.OpStatus, box.Status(box.ConfigOf(f), ix, nil))
		case "status-schema":
			var body any
			decoder := json.NewDecoder(strings.NewReader(c.Body))
			decoder.UseNumber()
			if err := decoder.Decode(&body); err != nil { panic(err) }
			e, known := apidoor.CheckSchema("Status", body)
			r = map[string]any{"known": known, "valid": e == nil}
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


# ---------------------------------------------------------------- модель нормы

F = gen_box.facts()
CEIL = 524288


def status(c, ix):
    result = {"id": c["ID"], "state": "Leader", "leader": c["API"], "leader_id": c["ID"], "term": 1, "commit": ix[1],
            "applied": ix[2], "voters": [c["ID"]], "members": {c["ID"]: c["API"]} if c["API"] else {}, "tls": c["TLS"],
            "max_value": c["Max"]}
    if F["status_max_body"]:
        result["max_body"] = c["MaxBody"]
    return result


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
    """→ None (отказ) или (index, {key: (items, index)})."""
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
        (mod / "cmd/boxjudge/main.go").write_text(HARNESS % {
            "m": MODULE, "max_body_config": ", MaxBody: c.Cfg.MaxBody" if F["status_max_body"] else ""})
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
        cfgs = [{"ID": "s1", "API": "127.0.0.1:9001", "TLS": True, "Max": 524288, "MaxBody": 1048576},
                {"ID": "box-2", "API": "", "TLS": False, "Max": 1000, "MaxBody": 2097152}]
        cs = []
        for c in cfgs:
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
            assert m == want, (upper, now, m, want)              # модель — по примерам нормы
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
            return [f"harness exit {p.returncode}: {p.stderr[-400:]}"]
        got = [json.loads(x) for x in p.stdout.split("\n") if x]
        bad = []
        for (c, want), g in zip(cs, got):
            if not self.agree(want, g):
                bad.append(f"{c['Op']}: want {str(want)[:120]} got {str(g)[:200]}")
        if len(got) != len(cs):
            bad.append(f"{len(got)} answers for {len(cs)} cases")
        return bad

    def agree(self, want, g):
        k = want[0]
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
        files, _ = gen_box.render()
        for rel, text in files.items():
            self.assertEqual((OUT / rel).read_text(encoding="utf-8"), text, f"{rel} is stale: run gen_box.py")
        v = subprocess.run(["go", "vet", "./box/"], cwd=OUT, capture_output=True, text=True)
        self.assertEqual(v.returncode, 0, v.stderr)

    def test_model(self):
        self.assertEqual(self.mismatches(self.harness()), [])

    def test_status_body_limits(self):
        if not F["status_max_body"]:
            self.skipTest("this source does not declare Status.max_body")
        source = gen_box.ROOT / "Platform/01-store/acceptance/3/inputs/status-body-limits.json"
        cases = json.loads(source.read_text(encoding="utf-8"))["cases"]
        self.assertEqual(len(cases), 10)
        self.assertEqual(sum(c["valid"] for c in cases), 3)
        exe = self.harness()
        requests = [{"Op": "status-schema", "Body": json.dumps(c["response"])} for c in cases]
        configured = [{"ID": "s1", "Max": 524288, "MaxBody": 2097152},
                      {"ID": "s2", "Max": 731, "MaxBody": 7}]
        requests += [{"Op": "status-flags", "Cfg": c} for c in configured]
        done = subprocess.run([str(exe)], input="\n".join(json.dumps(c) for c in requests) + "\n",
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        answers = [json.loads(line) for line in done.stdout.splitlines()]
        self.assertEqual(len(answers), len(requests))
        for c, got in zip(cases, answers):
            self.assertEqual(got, {"known": True, "valid": c["valid"]}, c["case"])
        for cfg, got in zip(configured, answers[len(cases):]):
            self.assertEqual(got["code"], 200)
            body = json.loads(got["body"])
            self.assertEqual(body["max_body"], cfg["MaxBody"])
            self.assertEqual(body["max_value"], cfg["Max"])
        self.assertIn(source, [gen_box.ROOT / e["path"] for e in gen_box.provenance()["judge_inputs"]])

    def test_mutants(self):
        mutants = [
            ("box.go", "State: \"Leader\"", "State: \"Follower\""),
            ("box.go", "Term: 1,", "Term: 2,"),
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


if __name__ == "__main__":
    unittest.main()
