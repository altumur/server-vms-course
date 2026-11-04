"""The poll machine of P/02.4 Н1.9 (ADR-0120 item 2 (b), addendum (5) item 4) agrees with its traces; mutations of the
machine are refused."""
import shutil
import tempfile
import unittest
from pathlib import Path

import check_machines

ROOT = Path(__file__).resolve().parents[3]
MACHINE = ROOT / "Platform/02-installer/data/rollout-poll.machine.yaml"
TRACES = MACHINE.with_name("rollout-poll.traces.tsv")


class Machines(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.machine = self.dir / MACHINE.name
        shutil.copy(MACHINE, self.machine)
        shutil.copy(TRACES, self.dir / TRACES.name)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def mutate(self, old, new, needle):
        text = self.machine.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1, old)
        self.machine.write_text(text.replace(old, new), encoding="utf-8")
        errors = check_machines.check(self.machine)[0]
        self.assertTrue(any(needle in e for e in errors), errors)

    def test_agrees(self):
        errors, stats = check_machines.check(MACHINE)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(stats["machine_traces"], 26)

    def test_rupture_keeps_target(self):                 # (31) item 1
        self.mutate('set: {target: "target.filter(t, t.v != v)", need:', 'set: {target: "target", need:', "rupture-drops-target")

    def test_target_moves(self):                         # (32) item 4: without a break the target does not move
        self.mutate("r.leader_id == leader_id && !target.exists(t, t.v == v) && !reads.exists(x, v in x.who)",
                    "r.leader_id == leader_id && !reads.exists(x, v in x.who)", "need_has_no_target")

    def test_no_hold(self):                              # answers before the own member's answer
        self.mutate('{event: status, if: "!self_replied", do: ["hold(v, r)"], stop: true}',
                    '{event: status, if: "false", do: ["hold(v, r)"], stop: true}', "held-before-self")

    def test_last_counts_quorum(self):                   # (32) item 2
        self.mutate("input.voters.all(v, v == input.self || v in alive)", "size(alive) >= 2", "last-two-of-three")

    def test_no_composition_check(self):                 # (37) item 1
        self.mutate("!same_set(r.voters, input.voters) || r.members != input.members", "false", "voters-changed")

    def test_leaderless_skips_composition(self):         # (5) item 4 (c): no leader — a break only after the check
        lines = self.machine.read_text(encoding="utf-8").splitlines()
        i = next(k for k, l in enumerate(lines) if "same_set(r.voters" in l)
        j = next(k for k, l in enumerate(lines) if "!has(r.leader_id)" in l)
        lines.insert(i, lines.pop(j))
        self.machine.write_text("\n".join(lines) + "\n", encoding="utf-8")
        errors = check_machines.check(self.machine)[0]
        self.assertTrue(any("voters-changed-no-leader" in e for e in errors), errors)

    def test_invariant(self):                            # live only with a target reached
        self.mutate("target.exists(t, t.v == v && r.applied >= t.c)", "true", "invariant live_has_target")

    def test_compiles_at_load(self):                     # (5) item 4 (b): every expression compiles at load
        self.mutate('one_target: "target.all(', 'one_target: "target.all((', "does not compile")

    def test_unknown_action(self):
        self.mutate('do: ["drop_read(n)"]', 'do: ["forget_read(n)"]', "is not in actions")

    def test_wrong_arity(self):
        self.mutate('do: ["drop_read(n)"]', 'do: ["drop_read(n, c)"]', "takes 1 arguments")

    def test_unknown_function(self):
        self.mutate("!same_set(r.voters, input.voters)", "!equal_sets(r.voters, input.voters)", "not in functions")

    def test_set_unknown_variable(self):
        self.mutate('set: {held: "[]"}', 'set: {holding: "[]"}', "set holding is not a variable")


if __name__ == "__main__":
    unittest.main()
