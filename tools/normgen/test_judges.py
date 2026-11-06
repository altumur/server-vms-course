"""Judge regressions (Codex B1): non-execution is failure, not agreement. flag_judge requires a live daemon listening on admin.sock; crashes fail. scenario_judge rejects empty, truncated, unfinished Go output, missing/empty/truncated runner reports and stale inventory. door_judge rejects missing reports, scenarios and steps."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import door_judge
import flag_judge
import gen_stagetests
import scenario_judge


def quiet(fn, argv):
    with redirect_stdout(io.StringIO()):
        return fn(argv)


class ScenarioJudge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        files, cls.inv = gen_stagetests.build()
        cls.inv_text = files["go/stagetests/inventory.tsv"]

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "inventory.tsv").write_text(self.inv_text, encoding="utf-8")
        (self.d / "runner").mkdir()

    def write(self, go_events, runner, inventory=None):
        (self.d / "go.jsonl").write_text("".join(json.dumps(e) + "\n" for e in go_events), encoding="utf-8")
        if runner is not None:
            (self.d / "runner" / "P-01.1-door.json").write_text(
                runner if isinstance(runner, str) else json.dumps(runner), encoding="utf-8")
        if inventory is not None:
            (self.d / "inventory.tsv").write_text(inventory, encoding="utf-8")
        return quiet(scenario_judge.main, ["--inventory", str(self.d / "inventory.tsv"),
                                            "--go-test", str(self.d / "go.jsonl"), "--runner", str(self.d / "runner")])

    def green(self):
        events, sc = [], {}
        for step_id, stage, test, status, *_ in self.inv:
            ch, fname, name, step = step_id.split("/")
            if fname != "scenarios.tsv" or status != "translated":
                continue
            events.append({"Action": "pass", "Test": f"{test}/{step}"})
            sc.setdefault(name, {"steps": []})["steps"].append({"step": int(step), "ok": True})
        return events + [{"Action": "pass"}], {"scenarios": sc}

    def test_green(self):
        ev, rep = self.green()
        self.assertEqual(self.write(ev, rep), 0)

    def test_empty_both(self):
        self.assertEqual(self.write([], None), 1)

    def test_go_not_finished(self):
        ev, rep = self.green()
        self.assertEqual(self.write(ev[:-1], rep), 1)          # No package event means build failure or truncated output.

    def test_go_cut(self):
        ev, rep = self.green()
        self.assertEqual(self.write(ev[:10] + [ev[-1]], rep), 1)

    def test_skip_is_not_match(self):
        ev, rep = self.green()
        ev[0] = dict(ev[0], Action="skip")
        self.assertEqual(self.write(ev, rep), 1)

    def test_runner_absent_empty_cut(self):
        ev, rep = self.green()
        self.assertEqual(self.write(ev, None), 1)
        self.assertEqual(self.write(ev, {"scenarios": {}}), 1)
        self.assertEqual(self.write(ev, json.dumps(rep)[:500]), 1)

    def test_inventory_behind_form(self):
        ev, rep = self.green()
        lines = self.inv_text.split("\n")
        self.assertEqual(self.write(ev, rep, "\n".join(lines[:-3]) + "\n"), 1)


class DoorJudge(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.exp = door_judge.expected_steps(door_judge.SCENARIOS)

    def run_with(self, rep):
        if rep is not None:
            (self.d / "P-01.1-door.json").write_text(json.dumps(rep), encoding="utf-8")
        return quiet(door_judge.main, [str(self.d)])

    def full(self):
        return {"scenarios": {n: {"steps": [{"step": int(s), "ok": True} for s, _ in st]} for n, st in self.exp}}

    def test_green(self):
        self.assertEqual(self.run_with(self.full()), 0)

    def test_empty_and_absent(self):
        self.assertEqual(self.run_with(None), 1)
        self.assertEqual(self.run_with({"scenarios": {}}), 1)

    def test_lost_scenario_and_step(self):
        rep = self.full()
        rep["scenarios"].pop(self.exp[0][0])
        self.assertEqual(self.run_with(rep), 1)
        rep = self.full()
        rep["scenarios"][self.exp[-1][0]]["steps"].pop()
        self.assertEqual(self.run_with(rep), 1)


DAEMON = r"""
import os, socket, sys, time
a = sys.argv[1:]
mode = a[0]
sock = a[a.index("-sockets") + 1] if "-sockets" in a else None
if mode in ("exit0", "exit1", "exit2"):
    sys.exit(int(mode[-1]))
if mode == "kill":
    os.kill(os.getpid(), 9)
if mode == "ready":
    os.makedirs(sock, exist_ok=True)
    s = socket.socket(socket.AF_UNIX); s.bind(os.path.join(sock, "admin.sock")); s.listen(1)
time.sleep(30)
"""


class FlagJudgeStart(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "d.py").write_text(DAEMON, encoding="utf-8")

    def run_probe(self, mode, extra=(), box=False, expect="ok"):
        probe = {"argv": [mode, "-dir", str(self.d / "data"), "-sockets", str(self.d / "sock"), *extra],
                 "env": {}, "expect": expect, "want": None}
        import sys
        return flag_judge.run(f"{sys.executable} {self.d / 'd.py'}", str(self.d), probe, False, 1.5, box)[0]

    def test_ready_is_pass(self):
        self.assertEqual(self.run_probe("ready"), "pass")

    def test_crash_is_fail(self):
        for mode in ("exit1", "exit0", "kill", "exit2"):
            self.assertEqual(self.run_probe(mode), "fail", mode)

    def test_alive_not_ready_is_fail(self):
        self.assertEqual(self.run_probe("hang"), "fail")

    def test_group_without_peers_unverified(self):
        self.assertEqual(self.run_probe("exit1", ["-join", "127.0.0.1:1"]), "unverified")
        self.assertEqual(self.run_probe("hang", ["-group-size", "3"]), "unverified")
        self.assertEqual(self.run_probe("exit2", ["-join", "127.0.0.1:1"]), "fail")

    def test_box_no_raft_separate(self):
        self.assertEqual(self.run_probe("exit2", ["-bootstrap"], box=True), "box_no_raft")

    def test_refusal(self):
        self.assertEqual(self.run_probe("exit2", expect="refuse"), "pass")
        self.assertEqual(self.run_probe("exit1", expect="refuse"), "fail")


if __name__ == "__main__":
    unittest.main()
