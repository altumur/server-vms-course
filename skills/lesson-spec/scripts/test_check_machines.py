"""Автомат опроса P/02.4 Н1.9 (ADR-0120 п. 2 (б)) сходится со своими трассами, а мутации автомата дают отказ."""
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
        self.assertGreaterEqual(stats["machine_traces"], 18)

    def test_rupture_keeps_target(self):                 # (31) п. 1
        self.mutate('do: ["rupture(v)", "mark_replied(v)"]}', 'do: ["mark_replied(v)"]}', "rupture-drops-target")

    def test_target_moves(self):                         # (32) п. 4: цель без разрыва не двигается
        self.mutate("&& !(v in target) && !reads.exists(n, v in reads[n])", "&& !reads.exists(n, v in reads[n])",
                    "rupture-drops-target")

    def test_no_hold(self):                              # ответы раньше своего члена
        self.mutate('{event: status, if: "!self_replied", do: ["hold(v, r)"], stop: true}',
                    '{event: status, if: "false", do: ["hold(v, r)"], stop: true}', "held-before-self")

    def test_last_counts_quorum(self):                   # (32) п. 2
        self.mutate("input.voters.all(v, v == input.self || v in alive)", "size(alive) >= 2", "last-two-of-three")

    def test_no_composition_check(self):                 # (37) п. 1
        self.mutate("!same_set(r.voters, input.voters) || r.members != input.members", "false", "voters-changed")

    def test_unknown_action(self):
        self.mutate('do: ["drop_read(n)"]', 'do: ["forget_read(n)"]', "is not in actions")

    def test_unknown_function(self):
        self.mutate("!same_set(r.voters, input.voters)", "!equal_sets(r.voters, input.voters)", "not in functions")


if __name__ == "__main__":
    unittest.main()
