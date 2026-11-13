"""The poll machine of P/02.4 Н1.9 (ADR-0120 item 2 (b), addendum (5) item 4) agrees with its traces; mutations of the
machine are refused."""
import shutil
import tempfile
import unittest
from pathlib import Path

import check_machines

ROOT = Path(__file__).resolve().parents[3]
MACHINE = ROOT / "Platform/02-installer/forms/rollout-poll.machine.yaml"     # раскладка ADR-0124: формы — в forms/
TRACES = MACHINE.with_name("rollout-poll.traces.tsv")


class Machines(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.machine = self.dir / MACHINE.name
        shutil.copy(MACHINE, self.machine)
        shutil.copy(TRACES, self.dir / TRACES.name)

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
        self.mutate("r.leader_id == leader_id) ? target : target.filter(t, t.v != v)", "r.leader_id == leader_id) ? target : target", "rupture-drops-target")

    def test_target_moves(self):                         # (32) item 4: without a break the target does not move
        self.mutate("(!target.exists(t, t.v == v) && !reads.exists(x, v in x.who) && !(v in need)",
                    "(!reads.exists(x, v in x.who) && !(v in need)", "need_has_no_target")

    def test_no_hold(self):                              # answers before the own member's answer
        self.mutate('event: status, if: "!self_replied", do: ["hold(v, r)"], stop: true}',
                    'event: status, if: "false", do: ["hold(v, r)"], stop: true}', "held-before-self")

    def test_transition_id(self):                        # ADR-0122 доп. (1) п. 4: адрес перехода
        self.mutate("{id: tick-2, event: tick,", "{id: tick-1, event: tick,", "id tick-1 repeats")


    def test_last_counts_quorum(self):                   # (32) item 2
        self.mutate("input.voters.all(v, v == input.self || v in alive)", "size(alive) >= 2", "last-two-of-three")

    def test_no_composition_check(self):                 # (37) item 1
        self.mutate('if: "!same_set(r.voters, input.voters) || r.members != input.members", do', 'if: "false", do', "voters-changed")

    def test_leaderless_skips_composition(self):         # (5) item 4 (c): no leader — a break only after the check
        lines = self.machine.read_text(encoding="utf-8").splitlines()
        i = next(k for k, l in enumerate(lines) if "same_set(r.voters" in l)
        j = next(k for k, l in enumerate(lines) if 'if: "r.leader_id == \'\'"' in l)
        lines.insert(i, lines.pop(j))
        self.machine.write_text("\n".join(lines) + "\n", encoding="utf-8")
        errors = check_machines.check(self.machine)[0]
        self.assertTrue(any("voters-changed-no-leader" in e for e in errors), errors)

    def test_no_leader_composition_check(self):          # (6) item 1 (Ф1)
        self.mutate('if: "!leaderless && v == leader_id && r != null && (!same_set', 'if: "false && (!same_set', "leader-voters-changed")

    def test_leader_goes_last_with_last(self):           # (6) item 2 (Ф3): «leader goes last» only without -last
        self.mutate("if: \"!input.last && r.state == 'Leader' && size(input.voters) > 1\"", "if: \"r.state == 'Leader' && size(input.voters) > 1\"", "last-passes")

    def test_silent_voter_keeps_target(self):            # (6) item 5 (б), Ф9: no answer by the deadline — tick puts the break
        self.mutate('target: "target.filter(t, self_replied && t.v in replied)"', 'target: "target"', "target-voter-silent")

    def test_invariant(self):                            # live only with a target reached
        self.mutate("target.exists(t, t.v == v && r.applied >= t.c)", "true", "invariant live_has_target")

    def test_compiles_at_load(self):                     # (5) item 4 (b): every expression compiles at load
        self.mutate('one_target: "target.all(', 'one_target: "target.all((', "does not compile")

    def test_unknown_action(self):
        self.mutate('if: "c == null", do: ["drop_read(n)"]', 'if: "c == null", do: ["forget_read(n)"]', "is not in actions")

    def test_wrong_arity(self):
        self.mutate('if: "c == null", do: ["drop_read(n)"]', 'if: "c == null", do: ["drop_read(n, c)"]', "takes 1 arguments")

    def test_unknown_function(self):
        self.mutate('if: "!same_set(r.voters, input.voters)', 'if: "!equal_sets(r.voters, input.voters)', "not in functions")

    def test_set_unknown_variable(self):
        self.mutate('set: {held: "held + [', 'set: {holding: "held + [', "set holding is not a variable")




class DeclaredMachines(unittest.TestCase):
    """The shared class has no rollout constants or event names outside rollout-poll."""

    def setUp(self):
        import copy
        import yaml
        self.copy, self.yaml = copy.deepcopy, yaml
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.path = self.dir / "counter.machine.yaml"
        self.doc = {
            "machine": "counter", "norm": "test fixture",
            "states": ["active", "done"], "initial": "active", "terminal": ["done"],
            "input": {}, "types": {}, "const": {},
            "vars": {"count": {"type": "int", "init": 0}},
            "timers": {}, "events": {"add": {"n": "int"}, "finish": {}}, "env": [],
            "functions": {},
            "actions": {
                "bump": {"args": {"n": "int"}, "set": {"count": "count + n"}},
                "report": {"args": {"n": "int"}, "io": "observe an actual effect elsewhere"},
            },
            "invariants": {"nonnegative": "count >= 0"},
            "transitions": [
                {"id": "add", "event": "add", "from": "active",
                 "do": ["bump(n)", "report(count)"], "stop": True},
                {"id": "finish", "event": "finish", "from": "active", "to": "done"},
            ],
        }

    def machine(self, doc=None):
        self.path.write_text(self.yaml.safe_dump(doc or self.doc, allow_unicode=True, sort_keys=False))
        return check_machines.Machine(self.path)

    def trace(self, rows, doc=None):
        self.machine(doc)
        self.path.with_name("counter.traces.tsv").write_text(
            "trace\tstep\tt\tevent\texpect\n" + "\n".join(rows) + "\n")
        return check_machines.check(self.path)

    def test_declared_states_events_io_and_terminal(self):
        errors, stats = self.trace([
            "counter\t0\t0\tinput {}\tstate=active; var.count=0",
            'counter\t1\t0\tadd {"n":2}\tdid=io report [2]; var.count=2',
            "counter\t2\t1\tfinish {}\tstate=done",
            'counter\t3\t2\tadd {"n":100}\tstate=done; var.count=2; not=io report [102]',
        ])
        self.assertEqual(errors, [])
        self.assertEqual(stats["machine_traces"], 1)

    def test_literal_unicode_line_separator_stays_inside_a_tsv_cell(self):
        doc = self.copy(self.doc)
        doc["events"]["text"] = {"value": "string"}
        doc["actions"]["text"] = {"args": {"value": "string"}, "io": "observe text"}
        doc["transitions"].append({"id": "text", "event": "text", "from": "active", "do": ["text(value)"]})
        mark = chr(0x2028)
        errors, _ = self.trace(["unicode\t0\t0\tinput {}\t", f'unicode\t1\t1\ttext {{"value":"{mark}"}}\tio=[["text",["{mark}"]]]'], doc)
        self.assertEqual(errors, [])

    def test_action_argument_split_preserves_escaped_quote_and_comma(self):
        self.assertEqual(check_machines.split_args(r'"a\",b", 7'), [r'"a\",b"', '7'])

    def test_unknown_events_payload_names_types_and_integer_precision(self):
        for event in ['foreign {}', 'add {"n":"2"}', 'add {"n":true}',
                      'add {"n":2,"extra":3}', "add {}", 'add {"n":9223372036854775808}']:
            with self.subTest(event=event):
                errors, _ = self.trace(["bad\t0\t0\tinput {}\t", f"bad\t1\t1\t{event}\t"])
                self.assertTrue(errors, event)

    def test_duplicate_keys_and_nonobject_payload(self):
        for event in ['add {"n":1,"n":2}', "add [1]", 'add {"n":NaN}']:
            with self.subTest(event=event):
                errors, _ = self.trace(["bad\t0\t0\tinput {}\t", f"bad\t1\t1\t{event}\t"])
                self.assertTrue(errors, event)

    def test_from_and_terminal_are_checked_at_load(self):
        for source in ["foreign", "done", ["active", "done"]]:
            doc = self.copy(self.doc)
            doc["transitions"][0]["from"] = source
            self.assertTrue(self.machine(doc).errors, source)
        doc = self.copy(self.doc)
        doc["terminal"] = ["foreign"]
        self.assertTrue(self.machine(doc).errors)

    def test_bad_typed_declaration_and_unknown_action(self):
        for section in ["events", "actions"]:
            doc = self.copy(self.doc)
            if section == "events":
                doc["events"]["add"]["n"] = "unimplemented-type"
            else:
                doc["transitions"][0]["do"] = ["unimplemented(count)"]
            self.assertTrue(self.machine(doc).errors)

    def test_positive_and_negative_invariants(self):
        errors, _ = self.trace(["good\t0\t0\tinput {}\t", 'good\t1\t0\tadd {"n":1}\tvar.count=1'])
        self.assertEqual(errors, [])
        errors, _ = self.trace(["bad\t0\t0\tinput {}\t", 'bad\t1\t0\tadd {"n":-1}\t'])
        self.assertTrue(any("nonnegative" in x for x in errors), errors)

    def test_own_every_timer_no_rollout_consts(self):
        doc = self.copy(self.doc)
        doc["const"] = {"PERIOD": 2}
        doc["events"]["tick"] = {}
        doc["timers"] = {"pulse": {"every": "PERIOD", "from": "s0", "event": "tick"}}
        doc["transitions"].append({"id": "pulse", "event": "tick", "from": "active",
                                   "do": ["bump(1)", "report(count)"], "stop": True})
        errors, _ = self.trace([
            "timer\t0\t0\tinput {}\tvar.count=0",
            "timer\t1\t0\tadvance\tvar.count=1; did=io report [1]",
            "timer\t2\t4\tadvance\tvar.count=3; did=io report [3]",
            "timer\t3\t5\tfinish {}\tstate=done",
            "timer\t4\t10\tadvance\tvar.count=3; not=io report [4]",
        ], doc)
        self.assertEqual(errors, [])

    def test_after_io_payload_and_exact_deadline(self):
        doc = self.copy(self.doc)
        doc["const"] = {"WAIT": 2}
        doc["events"].update({"ask": {"rid": "string"}, "expired": {"rid": "string"}})
        doc["actions"]["request"] = {"args": {"rid": "string"}, "io": "read by the real adapter"}
        doc["timers"] = {"wait": {"after_io": "request", "after": "WAIT", "event": "expired",
                                  "payload": {"rid": "rid"}}}
        doc["transitions"] += [
            {"id": "ask", "event": "ask", "from": "active", "do": ["request(rid)"], "stop": True},
            {"id": "expire", "event": "expired", "from": "active", "do": ["bump(1)", "report(count)"],
             "stop": True},
        ]
        errors, _ = self.trace([
            "io\t0\t0\tinput {}\t",
            'io\t1\t1\task {"rid":"one"}\tdid=io request ["one"]; var.count=0',
            'io\t2\t1\task {"rid":"two"}\tdid=io request ["two"]; var.count=0',
            "io\t3\t2.9\tadvance\tvar.count=0",
            "io\t4\t3\tadvance\tvar.count=2; did=io report [2]",
        ], doc)
        self.assertEqual(errors, [])
        errors, _ = self.trace(["bad\t0\t0\tinput {}\t", 'bad\t1\t0\texpired {"rid":"x"}\t'], doc)
        self.assertTrue(any("only by the executor" in x for x in errors), errors)

    def test_clock_and_zero_period_fail_closed(self):
        doc = self.copy(self.doc)
        doc["events"]["tick"] = {}
        doc["timers"] = {"bad": {"every": 0, "event": "tick"}}
        errors, _ = self.trace(["bad\t0\t0\tinput {}\t"], doc)
        self.assertTrue(any("positive every" in x for x in errors), errors)
        errors, _ = self.trace(["bad\t0\t0\tinput {}\t", 'bad\t1\t2\tadd {"n":1}\t',
                                'bad\t2\t1\tadd {"n":1}\t'])
        self.assertTrue(any("before" in x for x in errors), errors)

    def test_typed_input_and_initial_invariant(self):
        doc = self.copy(self.doc)
        doc["input"] = {"who": "string"}
        errors, _ = self.trace(['bad\t0\t0\tinput {"who":1}\t'], doc)
        self.assertTrue(errors)
        doc = self.copy(self.doc)
        doc["vars"]["count"]["init"] = -1
        errors, _ = self.trace(["bad\t0\t0\tinput {}\t"], doc)
        self.assertTrue(any("nonnegative" in x for x in errors), errors)

    def test_declared_from_filters_other_active_state(self):
        doc = self.copy(self.doc)
        doc["states"].insert(1, "waiting")
        doc["events"]["wait"] = {}
        doc["transitions"].append({"id": "wait", "from": "active", "event": "wait", "to": "waiting"})
        errors, _ = self.trace(["from\t0\t0\tinput {}\t", "from\t1\t0\twait {}\tstate=waiting",
                                'from\t2\t1\tadd {"n":3}\tvar.count=0; not=io report [3]'], doc)
        self.assertEqual(errors, [])

    def test_exact_io_and_quoted_assertion_separator(self):
        doc = self.copy(self.doc)
        doc["events"]["echo"] = {"s": "string"}
        doc["actions"]["echo"] = {"args": {"s": "string"}, "io": "echo a controlled label"}
        doc["transitions"].append({"id": "echo", "event": "echo", "from": "active",
                                   "do": ["echo(s)"], "stop": True})
        errors, _ = self.trace([
            "io\t0\t0\tinput {}\tio=[]",
            'io\t1\t0\techo {"s":"a;b"}\tio=[["echo",["a;b"]]]',
            "io\t2\t1\tfinish {}\tstate=done; io=[]",
            'io\t3\t2\techo {"s":"late"}\tio=[]',
        ], doc)
        self.assertEqual(errors, [])
        errors, _ = self.trace([
            "bad\t0\t0\tinput {}\t",
            'bad\t1\t0\techo {"s":"unexpected"}\tio=[]',
        ], doc)
        self.assertTrue(any("IO:" in x for x in errors), errors)

    def test_zero_after_io_fires_in_the_same_step(self):
        doc = self.copy(self.doc)
        doc["events"].update({"ask": {}, "timeout": {}})
        doc["actions"]["request"] = {"args": {}, "io": "request"}
        doc["timers"] = {"wait": {"after_io": "request", "after": 0, "event": "timeout"}}
        doc["transitions"] += [
            {"id": "ask", "event": "ask", "from": "active", "do": ["request()"], "stop": True},
            {"id": "timeout", "event": "timeout", "from": "active", "do": ["bump(1)"], "stop": True},
        ]
        errors, _ = self.trace([
            "now\t0\t0\tinput {}\t",
            'now\t1\t0\task {}\tvar.count=1; io=[["request",[]]]',
        ], doc)
        self.assertEqual(errors, [])

    def test_input_clock_origin_and_invalid_clock(self):
        doc = self.copy(self.doc)
        doc["events"]["tick"] = {}
        doc["timers"] = {"pulse": {"every": 2, "from": "s0", "event": "tick"}}
        doc["transitions"].append({"id": "pulse", "event": "tick", "from": "active",
                                   "do": ["bump(1)"], "stop": True})
        errors, _ = self.trace(["clock\t0\t10\tinput {}\tvar.count=0",
                                "clock\t1\t10\tadvance\tvar.count=1",
                                "clock\t2\t11.9\tadvance\tvar.count=1",
                                "clock\t3\t12\tadvance\tvar.count=2"], doc)
        self.assertEqual(errors, [])
        for clock in ["NaN", "Infinity", "-1", "not-time"]:
            errors, _ = self.trace([f"bad\t0\t{clock}\tinput {{}}\t"], doc)
            self.assertTrue(errors, clock)

    def test_malformed_yaml_is_reported(self):
        self.path.write_text("machine: [\n")
        errors, _ = check_machines.check(self.path)
        self.assertTrue(any("YAML" in x for x in errors), errors)


class PublishedWorkerPolicies(unittest.TestCase):
    """A wrong local decision must fail a published trace, even with well-formed declarations."""

    def copied(self, name):
        import yaml
        directory = Path(tempfile.mkdtemp(prefix='worker-policy-'))
        self.addCleanup(shutil.rmtree, directory)
        source = ROOT / f'Platform/03-worker/forms/{name}.machine.yaml'
        machine = directory / source.name
        shutil.copy(source, machine)
        traces = source.with_name(f'{name}.traces.tsv')
        shutil.copy(traces, directory / traces.name)
        return machine, yaml.safe_load(source.read_text()), yaml

    def mutant(self, name, change):
        machine, doc, yaml = self.copied(name)
        change(doc)
        machine.write_text(yaml.safe_dump(doc, sort_keys=False))
        errors, _ = check_machines.check(machine)
        self.assertTrue(errors, name)
        self.assertTrue(any('step' in e for e in errors), errors)

    def test_both_worker_policy_trace_sets(self):
        for name, count in [('contender-writer', 8), ('token-cache', 12)]:
            machine, _, _ = self.copied(name)
            errors, stats = check_machines.check(machine)
            self.assertEqual(errors, [])
            self.assertEqual(stats['machine_traces'], count)

    def test_contender_priority_mutant(self):
        def change(d):
            step = next(t for t in d['transitions'] if t['id'] == 'choose-refused-first')
            step['do'] = ['choose_phase(ever_capture ? "nameless" : (foreign ? "refused" : "waiting"), wall)']
        self.mutant('contender-writer', change)

    def test_contender_since_rewrite_mutant(self):
        self.mutant('contender-writer', lambda d: d['actions']['choose_phase']['set'].update(since='wall'))

    def test_contender_first_capture_back_mutant(self):
        def change(d):
            step = next(t for t in d['transitions'] if t['id'] == 'first-capture-no-back')
            step['do'].insert(0, 'name_back()')
        self.mutant('contender-writer', change)

    def test_cache_early_persist_mutant(self):
        def change(d):
            step = next(t for t in d['transitions'] if t['id'] == 'new-candidate-no-file-yet')
            step['do'].append('persist(candidate_handle)')
        self.mutant('token-cache', change)

    def test_cache_unknown_key_replacement_mutant(self):
        def change(d):
            step = next(t for t in d['transitions'] if t['id'] == 'unknown-key-current-waits')
            step['do'].append('request("")')
        self.mutant('token-cache', change)

    def test_cache_same_day_boundary_mutant(self):
        def change(d):
            step = next(t for t in d['transitions'] if t['id'] == 'blocked-through-this-day')
            step['if'] = 'day < blocked_day'
        self.mutant('token-cache', change)

    def test_cache_revoked_word_identity_mutant(self):
        def change(d):
            step = next(t for t in d['transitions'] if t['id'] == 'revoked-current')
            step['do'][0] = 'reject(current_handle)'
        self.mutant('token-cache', change)


if __name__ == "__main__":
    unittest.main()
