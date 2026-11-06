"""Test rollout-poll freshness, all scaffold tests fail without panic, seam-derived fixture responses pass, and state/refusal-word/missing-result mutants fail. Internal assertions remain excluded; neither generator nor fixture judge implements the machine."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TRACES = ROOT / "Platform/02-installer/forms/rollout-poll.traces.tsv"
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")

FAKE = r'''package lessonadapter

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
)

func RolloutPoll(input json.RawMessage, events []Event) Poll {
	var in struct{ Self string }
	_ = json.Unmarshal(input, &in)
	parts := []string{strconv.Itoa(len(events)), string(input)}
	for _, e := range events {
		parts = append(parts, strconv.FormatFloat(e.T, 'g', -1, 64)+" "+e.Event)
	}
	key := strings.Join(parts, "\x00")
	if p, ok := polls[key]; ok {
		return p
	}
	return Poll{State: fmt.Sprint("unknown ", len(events))}
}
'''


def answers():
    """Map (input, event prefix) to the expected observation directly from traces."""
    out = {}
    rows = [ln.split("\t") for ln in TRACES.read_text(encoding="utf-8").split("\n") if ln and not ln.startswith("#")][1:]
    traces = {}
    for name, step, t, event, expect in rows:
        tr = traces.setdefault(name, {"input": None, "events": []})
        asserts = [a.strip() for a in expect.split(";") if a.strip()]
        if step == "0":
            tr["input"] = event[6:]
        else:
            tr["events"].append(format(float(t), "g") + " " + event)
        state = next((a[6:] for a in asserts if a.startswith("state=")), None)
        if state is None:
            continue
        ref = next((a for a in asserts if a.startswith("did=refuse ")), None)
        res = None
        if state == "refused":
            _, code, word = ref.split(" ", 2)
            res = (int(code), word)
        key = "\x00".join([str(len(tr["events"])), tr["input"], *tr["events"]])
        assert out.get(key, (state, res)) == (state, res), f"traces disagree on one prefix: {name} step {step}"
        out[key] = (state, res)
    return out


def answers_go():
    lines = ["package lessonadapter", "", "var polls = map[string]Poll{"]
    for k, (state, res) in answers().items():
        r = "nil" if res is None else f"&PollResult{{Code: {res[0]}, Word: {json.dumps(res[1], ensure_ascii=False)}}}"
        lines.append(f"\t{json.dumps(k, ensure_ascii=False)}: {{State: {json.dumps(state)}, Result: {r}}},")
    lines.append("}")
    return "\n".join(lines) + "\n"


def results(mod):
    done = subprocess.run(["go", "test", "-count=1", "-json", "./rollouttests/"], cwd=mod, capture_output=True,
                          text=True, env=GOENV)
    res, panics = {}, 0
    for line in done.stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("Action") == "output" and "panicked" in e.get("Output", ""):
            panics += 1
        if e.get("Test") and "/" in e["Test"] and e["Action"] in ("pass", "fail"):
            res[e["Test"]] = e["Action"]
    return res, panics


@unittest.skipUnless(TRACES.is_file(), "no P/02 traces")
class Rollout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="rollout-")
        cls.out = Path(cls.tmp.name) / "out"
        env = dict(os.environ, NORMGEN_LESSON="02-installer")
        for gen in ("gen_cmdtests.py", "gen_rollout.py"):
            done = subprocess.run([sys.executable, str(HERE / gen), str(cls.out)], capture_output=True, text=True, env=env)
            assert done.returncode == 0, done.stderr
        cls.mod = cls.out / "go"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fake(self, mutate=None):
        t = Path(tempfile.mkdtemp(dir=self.tmp.name))
        shutil.copytree(self.mod, t / "go")
        (t / "go/lessonadapter/poll.go").unlink()
        text = answers_go()
        if mutate:
            self.assertIn(mutate[0], text)
            text = text.replace(mutate[0], mutate[1], 1)
        (t / "go/lessonadapter/fake.go").write_text(FAKE, encoding="utf-8")
        (t / "go/lessonadapter/answers.go").write_text(text, encoding="utf-8")
        return t / "go"

    def test_out_fresh(self):
        for rel in ("rollouttests/traces_test.go", "rollouttests/engine_test.go", "rollouttests/inventory.tsv"):
            self.assertEqual((self.mod / rel).read_bytes(), (HERE / "out/p02/go" / rel).read_bytes(), rel)

    def test_inventory(self):
        inv = (self.mod / "rollouttests/inventory.tsv").read_text(encoding="utf-8")
        self.assertGreaterEqual(inv.count("\ttranslated\t"), len(answers()))   # Identical trace prefixes must yield one answer.
        self.assertIn("\texcluded\tan internal variable of the machine", inv)

    def test_stub_red(self):
        res, panics = results(self.mod)
        self.assertEqual(set(res.values()), {"fail"})
        self.assertEqual(panics, 0)

    def test_fake_green(self):
        res, _ = results(self.fake())
        inv = (self.mod / "rollouttests/inventory.tsv").read_text(encoding="utf-8")
        self.assertEqual(len(res), inv.count("\ttranslated\t"))
        self.assertEqual({n for n, a in res.items() if a != "pass"}, set())

    def test_mutants(self):
        for old, new, why in (('State: "passed"', 'State: "polling"', "state"),
                              ('Word: "voters changed"', 'Word: "voters changed!"', "word"),
                              ('Result: &PollResult{Code: 2,', 'Result: &PollResult{Code: 1,', "code")):
            res, _ = results(self.fake((old, new)))
            self.assertTrue(any(a == "fail" for a in res.values()), f"mutant survived: {why}")

    def test_review_traces_and_downtime_input(self):
        """The five review traces execute their observable checks; changing the flag loses exactly its three traces."""
        mod = self.fake()
        res, panics = results(mod)
        new_checks = {
            "TestRolloutPoll_Trace_TwoVotersLastRefused/step6",
            "TestRolloutPoll_Trace_TwoVotersLastRefused/step9",
            "TestRolloutPoll_Trace_TwoVotersLastDowntimePasses/step1",
            "TestRolloutPoll_Trace_TwoVotersDowntimePasses/step1",
            "TestRolloutPoll_Trace_DowntimeThreeVotersPolls/step1",
            "TestRolloutPoll_Trace_DowntimeThreeVotersPolls/step3",
            "TestRolloutPoll_Trace_VoterWithoutAddress/step7",
            "TestRolloutPoll_Trace_VoterWithoutAddress/step8",
        }
        self.assertTrue(new_checks <= set(res), new_checks - set(res))
        self.assertTrue(all(res[name] == "pass" for name in new_checks))
        self.assertEqual(panics, 0)
        path = mod / "lessonadapter/fake.go"
        text = path.read_text()
        self.assertIn("string(input)", text)
        path.write_text(text.replace("string(input)",
            r'strings.Replace(string(input), "\"allow_downtime\": true", "\"allow_downtime\": false", 1)', 1))
        mutant, panics = results(mod)
        self.assertEqual({name.split("/")[0] for name, action in mutant.items() if action == "fail"}, {
            "TestRolloutPoll_Trace_TwoVotersLastDowntimePasses",
            "TestRolloutPoll_Trace_TwoVotersDowntimePasses",
            "TestRolloutPoll_Trace_DowntimeThreeVotersPolls",
        })
        self.assertEqual(panics, 0)


if __name__ == "__main__":
    unittest.main()
