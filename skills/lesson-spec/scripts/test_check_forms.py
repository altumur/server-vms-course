"""Мутации форм ADR-0125 P/01: каждая порча формы, прозы или OpenAPI даёт отказ check_forms."""
import copy
import hashlib
import json
import re
import shutil
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import check_forms
import check_cyrillic

ROOT = Path(__file__).resolve().parents[3]
LESSON = ROOT / "Platform/01-store"
JOURNAL = "decisions/journal/platform/01-store"


# Frozen prose witness from ec48a8949, before the form became the sole source. Two rows follow later form
# changes: the flag -api-bind (9d0271662, P01.233, P/01.3-R409) and `import`, `restore` in the commands of
# -max-value (c51d4d70e, P01.177); the meaning cells are those of the current P/01.3 «Daemon flags» list.
LEGACY_FLAG_PROSE = r'''**Daemon flags** — a closed set (the store pilot, A3, A8). A flag outside the table is a start refusal, code 2. The machine form of the table — [`forms/daemon-flags.tsv`](../forms/daemon-flags.tsv) (ADR-0125): type, default, required, commands; `check_spec` checks that it agrees with this table.

| Flag | Type | Default | Meaning |
|---|---|---|---|
| `-dir` | path | none: required, without it a start refusal, code 2 | the data directory of the daemon; the mark `FORMAT` (`format` above); also of `recover`, `restore`, `import` — they write into the directory of a stopped daemon on a box (ADR-0125 addendum (2) item 1) |
| `-id` | member id (N2) | in a group (`-join`, `-door`, `-group-size 3` or `5`) none: required; otherwise — `SERVER_NAME` (P/02.4 N1.2) | the member name in `members`, `voters`, `leader_id`; also of `recover` |
| `-sockets` | directory path | `/run/configstore` | the socket directory, flat (`sockets` above); the commands `status`, `join`, `leave`, `admit`, `backup`, `restore`, `import`, `rights` find `admin.sock` by it, `recover` does not (ADR-0125 addendum (2) item 1) |
| `-rights` | file path | none: without it — only `admin.sock` (chapter 1.2 N1.2) | the rights file |
| `-tls` | directory path | none: required with -join or a non-loopback -api/-raft | the root of the certificate kits (N1.6), mTLS of `-raft` and `-api` |
| `-raft` | `host:port` | none | the raft address that the daemon names to its partners |
| `-raft-bind` | `host:port` | `-raft` | the address on which the daemon listens for raft, if it differs from the named one |
| `-api` | `host:port` | none: without it there is no service HTTP door for partners | the address of the service doors of N2 for partners; the value of `members` and `leader` in `/v1/status`; without `-api` the member is not in `members` (the map can be `{}`; C01-STATUS-MEMBERS-NOAPI, the Architect's decision of 2026-10-26) |
| `-api-bind` | `host:port` | `-api` | the address on which the daemon listens for the service doors of N2, if it differs from the declared `-api` (R409) |
| `-bootstrap` | no value | off | the first server of the group (`join` above); with `-join` — a start refusal |
| `-join` | `host:port` | none | the `-api` address of a group member through which the daemon joins (`join` above); always with `-tls` |
| `-group-size` | `1` \| `3` \| `5` | `1` | the declared group size, the same on all servers |
| `-force` | no value | off | joining at a transitional evenness (`join` above), also of the command `join`; for `restore`, `import`, `recover` — only the clock refusal |
| `-isolated` | no value | off | only for `recover`, required: the operator confirms that the former group and the writers are isolated and nothing was handed out above upper (N3 step 0); without it `recover` is a refusal before changes (guess of stage C S02, the Architect's decision of 2026-10-23) |
| `-upper` | integer 0 … 2^53 − 1 | none | only for `recover`: the bound of the lost tail of epochs known to the operator; it only raises the computed upper (`floor.generation`): upper := max(computed, N); N below the computed one — a refusal before changes (guess of stage C S02, the Architect's decision of 2026-10-23) |
| `-peers` | a comma-separated list `id@<raft host:port>/<api host:port>` | none: required for `recover` | only for `recover`: the recovered membership — the remaining members, the one being recovered (`-id`) among them; the id and both addresses are required for each: raft — the address of the raft membership, api — the value of `members` in `/v1/status`; any other notation — a refusal before changes (guess of stage C S03, the Architect's decision of 2026-10-23) |
| `-door` | no value | off | a door without a vote (`door` above) |
| `-voters` | a comma-separated list `id@host:port` | none: required with `-door`, without it a start refusal, code 2 | the voters for a door without a vote: the id and the `-api` address |
| `-tuning` | `default` \| `lan` \| `slow` | `default` | the raft timing profile (`tuning` above) |
| `-leader-wait` | duration | `5s` | the leader wait (`leader_wait` above) |
| `-max-value` | bytes, > 0 (`0` and not a number — a start refusal, code 2; reconciliation of python and go M10/6–11, B7) | `512KiB` | the row ceiling (chapter 1.1 N4, `{row_ceiling}` of «Stand»); also of `import`, `restore`: the ceiling of the offline transfer on a box |
| `-max-body` | bytes, > 0 (as `-max-value`) | `1MiB` | the read limit of the HTTP body of `POST /v1/write` (chapter 1.1 N2, `{body_limit}` of «Stand»), separately from the row ceiling `-max-value` (log of cammeta-python, lesson 11 № 24) |
| `-max-conns`, `-api-conns`, `-api-per-address` | integer > 0 | 64, 32, 8 | connection limits (below) |
| `-index-base` | integer ≥ 0 | 0 | for `import`: the version base (`import` above) |
| `-groups` | no value | off | only for `rights` (`admin_ops` above; ADR-0125 addendum (2) item 1) |
| `--from` | file path | none: required for `restore`, `import` | only for `restore`, `import`: the input — the backup copy (`copy` above; `admin_ops` above; ADR-0125 addendum (2) item 1) |
'''


class Forms(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.lesson = self.tmp / "Platform/01-store"
        for part in ("forms", "spec", "acceptance", "vectors"):
            shutil.copytree(LESSON / part, self.lesson / part)
        for name in ("jcs", "rights-evaluator"):
            rel = f"Platform/common/vectors/{name}"
            shutil.copytree(ROOT / rel, self.tmp / rel)
        rel = "Platform/common/vectors/consumers.tsv"
        shutil.copyfile(ROOT / rel, self.tmp / rel)
        (self.tmp / JOURNAL).mkdir(parents=True)
        for path in (ROOT / JOURNAL).glob("*.tsv"):     # history files and the id map req-id-map.tsv (P01.283)
            shutil.copy(path, self.tmp / JOURNAL / path.name)

    def edit(self, rel, old, new):
        path = self.lesson / rel
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1, old)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def live_anchor(self, *besides):
        """The first live req anchor of 01.1 of the copy whose id is not among `besides` (from the data, not written
        here)."""
        text = (self.lesson / "spec/01.1-store.norms.md").read_text(encoding="utf-8")
        return next(m[0] for m in re.finditer(r"<!-- req: (P/01\.1-R[0-9]{3}) -->", text) if m[1] not in besides)

    def flags(self):
        return check_forms.check_flags(self.lesson / "forms/daemon-flags.tsv")[0]

    def refusals(self):
        return check_forms.check_refusals(self.lesson / "forms/refusals.tsv")[0]

    def legacy_flag_prose(self):
        (self.lesson / "spec/00-legacy.norms.md").write_text(LEGACY_FLAG_PROSE, encoding="utf-8")

    def test_legacy_flag_prose_passes(self):
        self.legacy_flag_prose()
        self.assertEqual(self.flags(), [])

    def test_clean(self):
        self.assertEqual(self.flags(), [])
        self.assertEqual(self.refusals(), [])

    def test_flag_missing(self):
        self.legacy_flag_prose()
        text = (self.lesson / "forms/daemon-flags.tsv").read_text(encoding="utf-8")
        line = next(x for x in text.split("\n") if x.startswith("-tuning\t"))
        self.edit("forms/daemon-flags.tsv", line + "\n", "")
        self.assertTrue(self.flags())

    def test_flag_default(self):
        self.legacy_flag_prose()
        self.edit("forms/daemon-flags.tsv", "\t524288\t512KiB\t", "\t524289\t512KiB\t")
        self.assertTrue(self.flags())
        self.edit("forms/daemon-flags.tsv", "\t524289\t512KiB\t", "\t1048576\t1MiB\t")
        self.assertTrue(self.flags())                          # the prose writes 512KiB

    def test_flag_required_and_cel(self):
        self.legacy_flag_prose()
        self.edit("forms/daemon-flags.tsv", "-isolated\tbool\tfalse\toff\ttrue\t", "-isolated\tbool\tfalse\toff\tfalse\t")
        self.assertTrue(self.flags())
        self.edit("forms/daemon-flags.tsv", '"-join" in f\tP/01.3 N1.3 join', '"-join" in\tP/01.3 N1.3 join')
        self.assertTrue(self.flags())

    def test_flag_type_and_commands(self):
        self.legacy_flag_prose()
        self.edit("forms/daemon-flags.tsv", "-tuning\tenum:default|lan|slow\t", "-tuning\tenum:default|lan|fast\t")
        self.assertTrue(self.flags())
        self.edit("forms/daemon-flags.tsv", "\trecover\t\tP/01.3 N3 recover", "\tdaemon\t\tP/01.3 N3 recover")
        self.assertTrue(self.flags())

    def test_two_hyphens_only_from(self):               # --from — имя прозы; иное с двумя дефисами — отказ
        self.legacy_flag_prose()
        self.edit("forms/daemon-flags.tsv", "--from\tfile\t", "--input\tfile\t")
        self.assertTrue(self.flags())

    def test_stage_kit_parts(self):                     # kit и parts — только части перечня
        self.assertEqual(check_forms.check_stage_parts(self.lesson / "forms/stages.kit.tsv")[0], [])
        self.edit("forms/stages.kit.tsv", "\t-\tdoor,refusals\t", "\t-\tdoor,shell\t")
        self.assertTrue(check_forms.check_stage_parts(self.lesson / "forms/stages.kit.tsv")[0])

    def test_stage_depends(self):                       # depends — только прежние этапы; launch — часть пакета
        self.edit("forms/stages.kit.tsv", "\tlaunch\tlaunch\t1\t", "\tlaunch\tlaunch\t4\t")   # launch — этап 2 (bf64f4058)
        self.assertTrue(any("depends" in e for e in check_forms.check_stage_parts(self.lesson / "forms/stages.kit.tsv")[0]))

    def test_stage_gate(self):                          # gate списком, tests:<глава>:<сценарии>[:seams]
        self.edit("forms/stages.kit.tsv", "s4-parallel-cas:seams", "s9-nothing:seams")
        self.assertTrue(any("s9-nothing" in e for e in check_forms.check_stage_parts(self.lesson / "forms/stages.kit.tsv")[0]))
        self.edit("forms/stages.kit.tsv", "s9-nothing:seams", "s4-parallel-cas:seam")
        self.assertTrue(check_forms.check_stage_parts(self.lesson / "forms/stages.kit.tsv")[0])

    def test_req_anchors(self):                         # ADR-0122 доп. (1) п. 1: номера требований
        self.assertEqual(check_forms.check_req_anchors(self.lesson)[0], [])
        self.edit("spec/01.1-store.norms.md", "<!-- req: P/01.1-R002 -->", "<!-- req: P/01.1-R001 -->")
        self.assertTrue(any("repeats" in e for e in check_forms.check_req_anchors(self.lesson)[0]))
        self.edit("spec/01.1-store.norms.md", "<!-- req: P/01.1-R001 -->\nA common rule", "<!-- req: P/01.2-R002 -->\nA common rule")
        self.assertTrue(any("not of this chapter" in e for e in check_forms.check_req_anchors(self.lesson)[0]))

    def test_req_tombstone(self):
        anchor = self.live_anchor("P/01.1-R002")
        self.edit("spec/01.1-store.norms.md", anchor, "<!-- removed: P/01.1-R002 by ADR-0122 -->\n" + anchor)
        self.assertTrue(any("reuses a removed" in e for e in check_forms.check_req_anchors(self.lesson)[0]))

    def test_req_merged_by_the_id_map(self):            # ADR-0133 доп. (93): слитый id резервирует карта журнала
        path = self.tmp / JOURNAL / "req-id-map.tsv"                 # the map of the journal and a row of ours
        path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + "\nP/01.1-R998\tP/01.1-R002\t"
                        "spec/01.1-store.norms.md#N1\tP01.283\n", encoding="utf-8")
        self.assertEqual(check_forms.check_req_anchors(self.lesson)[0], [])     # the map alone reserves, no anchor
        # a paragraph of several rules under one anchor is one requirement
        anchor = self.live_anchor("P/01.1-R002")
        self.edit("spec/01.1-store.norms.md", anchor,
                  "<!-- req: P/01.1-R997 -->\nThe store MUST A. It MUST NOT B. If C, then it MUST D.\n\n" + anchor)
        self.assertEqual(check_forms.check_req_anchors(self.lesson)[0], [])
        self.edit("spec/01.1-store.norms.md", "<!-- req: P/01.1-R997 -->", "<!-- req: P/01.1-R998 -->")
        errors = check_forms.check_req_anchors(self.lesson)[0]
        self.assertTrue(any("anchor P/01.1-R998 reuses a number merged into P/01.1-R002" in e for e in errors), errors)

    def test_seams(self):                               # ADR-0126 доп. (7) п. 1: закрытая грамматика швов
        path = self.lesson / "acceptance/1/seams.tsv"
        self.assertEqual(check_forms.check_seams(path)[0], [])
        self.edit("acceptance/1/seams.tsv", "@clock +600", "@clock 600s")
        self.assertTrue(check_forms.check_seams(path)[0])
        self.edit("acceptance/1/seams.tsv", "@clock 600s", "@clock +0.987654321")       # доли секунды (P/01.1 Н3, spec103)
        self.assertEqual(check_forms.check_seams(path)[0], [])
        good = path.read_text(encoding="utf-8")
        for bad in ("@clock +.25", "@clock +0.", "@clock +1e3", "@clock +01", "@clock +0.1234567891"):
            path.write_text(good.replace("@clock +0.987654321\t", bad + "\t"), encoding="utf-8")
            self.assertTrue(check_forms.check_seams(path)[0], bad)
        path.write_text(good, encoding="utf-8")
        self.edit("acceptance/1/seams.tsv", "@clock +0.987654321", "@clock +600")
        self.edit("acceptance/1/seams.tsv", "one 200 {", "200 {")
        self.assertTrue(any("after @parallel" in e for e in check_forms.check_seams(path)[0]))

    def test_refusal_code_kind(self):
        self.edit("forms/refusals.tsv", "1.1\t9\tguard_mismatch\thttp\t412\t", "1.1\t9\tguard_mismatch\thttp\t409\t")
        self.assertTrue(self.refusals())

    def test_refusal_rows_cover_prose(self):
        text = (self.lesson / "forms/refusals.tsv").read_text(encoding="utf-8")
        line = next(x for x in text.split("\n") if x.startswith("1.2\t11\t"))
        self.edit("forms/refusals.tsv", line + "\n", "")
        self.assertTrue(self.refusals())

    def test_refusal_openapi(self):
        self.edit("spec/01-store.api.openapi.yaml", "kind: {const: early}", "kind: {const: tooearly}")
        self.assertTrue(self.refusals())

    def test_refusal_fields(self):
        self.edit("forms/refusals.tsv", "\tlimit,key,size\t", "\tlimit,key,size,index\t")
        self.assertTrue(self.refusals())

    def test_write_checks_agree(self):
        self.edit("forms/refusals.tsv", "1.1\t1\tkey_rules\thttp\t400\tbadkey\t", "1.1\t1\tkey_rules\thttp\t400\tbadrequest\t")
        self.assertTrue(self.refusals())

    def test_typed_catalogue_without_outcome_is_complete(self):
        path = self.lesson / "forms/refusals.tsv"
        head = next(line for line in path.read_text().splitlines() if line and not line.startswith("#"))
        self.assertNotIn("outcome", head.split("\t"))
        errors, stats = check_forms.check_refusals(path)
        self.assertEqual(errors, [])
        rows = [line.split("\t") for line in path.read_text().splitlines() if line and not line.startswith("#")][1:]
        # Counted from the form itself: the catalogue grows with the norms (59 rows in 2026-11, more later).
        self.assertEqual(stats, {"refusal_rows": len(rows), "refusal_chapters": len({r[0] for r in rows}),
                                 "refusal_cause_names": len(rows)})
        self.assertEqual(stats["refusal_chapters"], 3)

    def test_typed_causes_missing_unknown_repeated_or_hidden(self):
        path = self.lesson / "spec/01.1-store.norms.md"
        good = path.read_text()
        line = next(line for line in good.splitlines() if line.startswith("- `ambiguous_barrier`:"))
        for replacement in ("", line.replace("`ambiguous_barrier`:", "`invented_refusal`:"), line + "\n" + line,
                            "```md\n" + line + "\n```", "> " + line):
            with self.subTest(replacement=replacement[:60]):
                path.write_text(good.replace(line, replacement))
                self.assertTrue(self.refusals())

    def test_typed_cause_and_caller_are_required(self):
        path = self.lesson / "spec/01.2-store.norms.md"
        good = path.read_text()
        line = next(line for line in good.splitlines() if line.startswith("- `list_form`:"))
        for replacement in ("- `list_form`: Caller action: fix the request.",
                            "- `list_form`: malformed input. Caller action:",
                            "- `list_form`: malformed input. Caller action: .",
                            "- `list_form`: malformed input without caller action."):
            with self.subTest(replacement=replacement):
                path.write_text(good.replace(line, replacement))
                self.assertTrue(any("cause and Caller action" in e for e in self.refusals()))

    def test_typed_catalogue_requires_a_real_n4_reference(self):
        path = self.lesson / "spec/01.1-store.norms.md"
        good = path.read_text()
        link = "[`forms/refusals.tsv`](../forms/refusals.tsv)"
        self.assertEqual(good.count(link), 1)
        for replacement in ("`forms/refusals.tsv`", "[`forms/refusals.tsv`](../other/refusals.tsv)",
                            "\n\n```md\n" + link + "\n```\n\n", "\n\n> " + link + "\n\n"):
            with self.subTest(replacement=replacement):
                path.write_text(good.replace(link, replacement))
                self.assertTrue(self.refusals())

    def test_typed_catalogue_detects_a_whole_missing_chapter(self):
        path = self.lesson / "forms/refusals.tsv"
        path.write_text("\n".join(line for line in path.read_text().splitlines() if not line.startswith("1.2\t")) + "\n")
        self.assertTrue(any("01.2-store.norms.md" in e and "not in this chapter's catalogue" in e
                            for e in self.refusals()))

    def test_typed_catalogue_validates_code_fields_cells_and_cause_groups(self):
        path = self.lesson / "forms/refusals.tsv"
        good = path.read_text()
        row = next(line for line in good.splitlines() if line.startswith("1.1\t9\tguard_mismatch\t"))
        cases = {"row": "x", "code": "exit 2", "fields": "key,key", "kind": "", "headers": "", "norm": ""}
        head = check_forms.REF_COLUMNS
        for column, value in cases.items():
            with self.subTest(column=column):
                cells = row.split("\t")
                cells[head.index(column)] = value
                path.write_text(good.replace(row, "\t".join(cells)))
                self.assertTrue(self.refusals())
        path.write_text(good.replace("1.1\t9\tguard_mismatch\t", "1.1\t8\tguard_mismatch\t"))
        self.assertTrue(any("cause group is 9" in e for e in self.refusals()))

    def test_typed_required_fields_cannot_be_dropped_or_made_optional(self):
        path = self.lesson / "forms/refusals.tsv"
        good = path.read_text()
        for fields in ("-", "key,index?", "key?,index"):
            with self.subTest(fields=fields):
                path.write_text(good.replace("\tguard\tkey,index\t", "\tguard\t" + fields + "\t"))
                self.assertTrue(any("required OpenAPI fields" in e for e in self.refusals()))

    def test_typed_code_kind_requires_an_actual_openapi_response(self):
        import yaml
        path = self.lesson / "spec/01-store.api.openapi.yaml"
        good = path.read_text()
        for bad_ref in ("#/components/responses/Conflict", "#/components/responses/Missing"):
            with self.subTest(ref=bad_ref):
                doc = yaml.safe_load(good)
                doc["paths"]["/v1/write"]["post"]["responses"]["412"] = {"$ref": bad_ref}
                path.write_text(yaml.safe_dump(doc))
                self.assertTrue(any("412 guard is not in the OpenAPI responses" in e for e in self.refusals()))
        doc = yaml.safe_load(good)
        doc["components"]["responses"]["Guard"] = {"$ref": "#/components/responses/Guard"}
        path.write_text(yaml.safe_dump(doc))
        self.assertTrue(any("412 guard is not in the OpenAPI responses" in e for e in self.refusals()))

    def test_check_row_code_differs_from_its_refusal(self):   # OBSH.49: дубль code/kind сверяет check_refusals
        self.edit("forms/write-checks.tsv", "\tfloor_socket\tsock != \"admin\"\t403\t", "\tfloor_socket\tsock != \"admin\"\t401\t")
        errors = self.refusals()
        self.assertTrue(any("write-checks.tsv:" in e and "check floor_socket" in e and "'401'" in e and "'403'" in e
                            for e in errors), errors)


class RefusalLinks(unittest.TestCase):
    """OBSH.49 (ADR-0133 доп. (90), (91)): `check` строки формы проверок — имя отказа `refusals.tsv`; code и kind равны."""
    HEAD = "n\tid\top\tgroup\teach\tcheck\twhen\tcode\tkind\tfault\tnorm"

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.forms = Path(temp.name) / "Platform/99-fixture/forms"
        self.forms.mkdir(parents=True)
        self.refusals = self.forms / "refusals.tsv"
        self.write_refusals([("key_rules", "400", "badkey"), ("rights", "403", "forbidden")])

    def write_refusals(self, rows):
        lines = ["# comment", "\t".join(check_forms.REF_COLUMNS)]
        lines += [f"9\t{i}\t{name}\thttp\t{code}\t{kind}\t-\t-\t-\tP/99 N4" for i, (name, code, kind) in enumerate(rows, 1)]
        self.refusals.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_checks(self, rows, name="write-checks.tsv"):
        lines = ["# comment one", "# comment two", self.HEAD]
        lines += [f"{i}\twc-{i}\t*\t\t\t{check}\ttrue\t{code}\t{kind}\t\tP/99 N2" for i, (check, code, kind) in enumerate(rows, 1)]
        (self.forms / name).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def errors(self):
        return check_forms.check_refusal_links(self.refusals)

    def test_match(self):
        self.write_checks([("key_rules", "400", "badkey"), ("rights", "403", "forbidden")])
        self.write_checks([("rights", "403", "forbidden")], name="read-checks.tsv")
        self.assertEqual(self.errors(), [])

    def test_code_differs(self):
        self.write_checks([("key_rules", "400", "badkey"), ("rights", "401", "forbidden")])
        errors = self.errors()
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("write-checks.tsv:5 (wc-2) check rights: code '401' differs from code '403' of refusals.tsv:4 rights",
                      errors[0])

    def test_kind_differs(self):
        self.write_checks([("key_rules", "400", "badrequest")], name="service-checks.tsv")
        errors = self.errors()
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("service-checks.tsv:4 (wc-1) check key_rules: kind 'badrequest' differs from kind 'badkey' "
                      "of refusals.tsv:3 key_rules", errors[0])

    def test_no_link_is_not_checked(self):            # имя не из каталога — не отказ; пара code/kind из каталога
        self.write_checks([("not_a_refusal", "403", "forbidden")], name="rights-checks.tsv")
        self.assertEqual(self.errors(), [])

    def test_ambiguous_link(self):
        self.write_refusals([("key_rules", "400", "badkey"), ("rights", "403", "forbidden"), ("rights", "403", "forbidden")])
        self.write_checks([("rights", "403", "forbidden")])
        errors = self.errors()
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("write-checks.tsv:4 (wc-1) check rights: ambiguous link", errors[0])
        self.assertIn("refusals.tsv:4, refusals.tsv:5", errors[0])

    def test_course_data_has_no_divergence(self):     # нынешние данные курса: ноль расхождений, связи есть
        linked = 0
        for path in check_forms.refusal_forms(ROOT):
            self.assertEqual(check_forms.check_refusal_links(path), [], path)
            names = {r["name"] for _, r in check_forms._tsv_lines(path)[1]}
            for table in path.parent.glob("*-checks.tsv"):
                linked += sum(r.get("check") in names for _, r in check_forms._tsv_lines(table)[1])
        self.assertGreater(linked, 0)


class FormsAllLessons(unittest.TestCase):         # ADR-0125 доп. (5): грамматика форм для уроков кроме P/01
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.lesson = self.tmp / "Platform/02-installer"
        shutil.copytree(ROOT / "Platform/02-installer/acceptance", self.lesson / "acceptance")

    def gate(self, check):
        return check_forms.gate_errors(self.lesson, "s", check)

    def test_case_gates(self):
        first = next(ln.split("\t")[0] for ln in (self.lesson / "acceptance/1/verdicts.tsv").read_text(encoding="utf-8").splitlines()
                     if ln and not ln.startswith("#"))
        self.assertEqual(self.gate("verdicts:2.1:*"), [])
        self.assertEqual(self.gate(f"verdicts:2.1:{first}"), [])
        self.assertTrue(self.gate("verdicts:2.1:no-such-case"))
        self.assertEqual(self.gate("puts:2.2:first,same_twice"), [])
        self.assertTrue(self.gate("puts:2.2:case"))                # строка заголовка — не случай
        self.assertTrue(self.gate("puts:2.4:*"))                   # нет таблицы главы
        self.assertTrue(self.gate("verdict:2.1:*"))                # вид вне грамматики
        self.assertTrue(self.gate("accept:2.1:*"))                 # accept — только scenarios.tsv

    def test_parts_and_commands(self):
        self.assertTrue({"families", "admin", "core", "rollout-poll"} <= check_forms.KIT_PARTS)
        self.assertTrue(check_forms.COMMAND.fullmatch("manifest-put"))
        self.assertFalse(check_forms.COMMAND.fullmatch("Put"))
        for ok in ("-dir", "--sha256", "$INSTANCE_ID", "<subsystem>"):
            self.assertTrue(check_forms.FLAG_NAME.fullmatch(ok), ok)
        for bad in ("$instance", "<Sub>", "dir", "---x", "$1X"):
            self.assertFalse(check_forms.FLAG_NAME.fullmatch(bad), bad)

    def test_process_seams(self):                     # швы не по HTTP: RUN, CALL, @file, @read (грамматика stagetests)
        path = self.lesson / "acceptance/1/seams.tsv"
        good = ["# P/02 seams (test)", "# scenario\tstep\trequest\texpect",
                's1-put\t1\t@file $data/in.yaml inputs/cam.yaml\tok',
                's1-put\t2\t@file $run/note "a b"\tok',
                's1-put\t3\tRUN w2cctl manifest put inputs/cam.yaml\texit 0',
                's1-put\t4\tRUN w2cctl manifest put "x y" $id\texit 2; stderr ~"unit.fields"',
                's1-put\t5\tRUN w2cctl show\texit 0; stdout {"n": 1}; stdout-text "ok\\n"; stderr ~"w"',
                's1-put\t6\tCALL parse-manifest {"text":"a: 1"}\t{"verdict":"refused"}',
                's1-put\t7\tCALL parse-manifest {}\t@exit 2',
                's1-put\t8\t@read $data/FORMAT\t{"format":"configstore"}',
                's1-put\t9\t@read $manifest/testsub\t@absent',
                's1-put\t10\t@read $run/log\ttext "done"']
        path.write_text("\n".join(good) + "\n", encoding="utf-8")
        self.assertEqual(check_forms.check_seams(path)[0], [])
        bad = [('RUN w2cctl  put', 'exit 0'), ('RUN w2cctl "unterminated', 'exit 0'), ('RUN w2cctl put', 'exit x'),
               ('RUN w2cctl put', 'exit 0; stderr ~"a"; stdout {}'), ('RUN w2cctl put', 'exit 0; stdout-text plain'),
               ('CALL Parse {}', '{}'), ('CALL parse {not json}', '{}'), ('CALL parse {}', 'refused'),
               ('@file /etc/x inputs/a', 'ok'), ('@file $data/x a.yaml', 'ok'), ('@file $data/x inputs/a', '200'),
               ('@read data/FORMAT', '{}'), ('@read $data/FORMAT', 'text plain')]
        for request, expect in bad:
            path.write_text("\n".join(good[:2] + [f"s1-put\t1\t{request}\t{expect}"]) + "\n", encoding="utf-8")
            self.assertTrue(check_forms.check_seams(path)[0], (request, expect))

    def test_parallel_process_and_operator_commands(self):
        path = self.lesson / "acceptance/1/seams.tsv"
        path.write_text("# t\n# scenario\tstep\trequest\texpect\n"
                        's2\t1\t@parallel 2\tok\n'
                        's2\t2\tCALL parse-manifest {}\teach {"verdict":"ok"}\n'
                        's2\t3\t@parallel 2\tok\n'
                        's2\t4\tRUN w2cctl show\tone exit 0; stdout {"a":1}; rest exit 2; stderr ~"busy"\n', encoding="utf-8")
        self.assertEqual(check_forms.check_seams(path)[0], [])
        forms = self.lesson / "forms"
        forms.mkdir()
        head = "command\tprocess\tprefix\tpositionals\tnorm\n"
        good = 'manifest-put\tw2cctl\t["manifest","put"]\t{"type":"array","items":{"type":"string"},"minItems":1,"maxItems":1}\tP/02.3 Н3\n'
        (forms / "operator-commands.tsv").write_text(head + good, encoding="utf-8")
        self.assertEqual(check_forms.check_operator_commands(forms / "operator-commands.tsv")[0], [])
        for bad in (good + good,                                                     # повтор
                    good.replace('["manifest","put"]', '"manifest put"'),            # prefix не массив
                    good.replace('"minItems":1,"maxItems":1', '"minItems":2,"maxItems":1'),
                    good.replace('{"type":"string"}', '{"type":"integer"}'),
                    good.replace("P/02.3 Н3", " ")):
            (forms / "operator-commands.tsv").write_text(head + bad, encoding="utf-8")
            self.assertTrue(check_forms.check_operator_commands(forms / "operator-commands.tsv")[0], bad)

    def test_single_chapter_lesson(self):              # урок одной главой (P/04): глава 4, acceptance/ без K, P/04-RNNN
        one = self.tmp / "Platform/04-controller"
        (one / "acceptance").mkdir(parents=True)
        (one / "spec").mkdir()
        (one / "acceptance/scenarios.tsv").write_text("# s\n# scenario\tstep\trequest\texpect\n01-a\t1\tGET /x\t200 {}\n", encoding="utf-8")
        (one / "acceptance/seams.tsv").write_text("# s\n# scenario\tstep\trequest\texpect\ns1\t1\t@reopen\tok\n", encoding="utf-8")
        self.assertEqual(check_forms.gate_errors(one, "s", "accept:4:01-a"), [])
        self.assertEqual(check_forms.gate_errors(one, "s", "tests:4:*:seams"), [])
        self.assertTrue(check_forms.gate_errors(one, "s", "accept:4:02-b"))
        (one / "spec/04-controller.norms.md").write_text("<!-- req: P/04-R001 -->\nx\n<!-- req: P/04.1-R002 -->\n", encoding="utf-8")
        errs = check_forms.check_req_anchors(one)[0]
        self.assertEqual(len(errs), 1, errs)                   # P/04.1-R002 не этого файла; P/04-R001 — годен
        self.assertTrue({"slot-capture", "slot-fate", "slot-release"} <= check_forms.KIT_PARTS)

    def test_http_without_kind(self):                  # P/05: тело http без kind — по названной схеме OpenAPI
        lesson = self.tmp / "Platform/05-resource"
        (lesson / "spec").mkdir(parents=True)
        (lesson / "forms").mkdir()
        (lesson / "spec/05-resource.api.openapi.yaml").write_text(
            "openapi: 3.1.0\ncomponents:\n  schemas:\n    ResourceDenied:\n      type: object\n      required: [detail, error]\n"
            "      properties: {detail: {type: string}, error: {const: refused}, role: {type: string}}\n", encoding="utf-8")
        (lesson / "spec/05.1-resource.norms.md").write_text("## Н4 Refusals\n\nThe catalogue is forms/refusals.tsv.\n", encoding="utf-8")
        head = "\t".join(check_forms.REF_COLUMNS + ["word", "response_schema", "cause", "outcome", "diagnostic", "caller"])
        def row(fields, schema):
            return "\t".join(["5.1", "1", "resource_role", "http", "403", "-", fields, "-", "-", "P/05.1 Н4",
                              "refused", schema, "c", "403 refused", "d", "client"])
        path = lesson / "forms/refusals.tsv"
        for fields, schema, ok in (("detail,error,role?", "ResourceDenied", True), ("detail,error", "ResourceDenied", True),
                                   ("detail", "ResourceDenied", False), ("detail,error,x", "ResourceDenied", False),
                                   ("detail,error", "NoSuch", False), ("-", "-", True), ("error", "-", False)):
            path.write_text(head + "\n" + row(fields, schema) + "\n", encoding="utf-8")
            errs = check_forms.check_refusals(path)[0]
            self.assertEqual(not errs, ok, (fields, schema, errs))

        dr = lesson / "forms/door-roles.tsv"
        (lesson / "spec/05-resource.api.openapi.yaml").write_text(
            "openapi: 3.1.0\npaths:\n  /v1/units:\n    get: {}\n    post: {}\ncomponents: {schemas: {}}\n", encoding="utf-8")
        for body, ok in (("GET\t/v1/units\tconsole,<sub>worker\tP/05.1 Н2", True), ("GET\t/v1/units\t*\tP/05.1 Н2", True),
                         ("PUT\t/v1/units\tconsole\tP/05.1 Н2", False), ("GET\t/v1/nope\tconsole\tx", False),
                         ("GET\t/v1/units\tConsole\tx", False), ("GET\t/v1/units\tconsole\t ", False)):
            dr.write_text("method\tpath\troles\tnorm\n" + body + "\n", encoding="utf-8")
            self.assertEqual(not check_forms.check_door_roles(dr)[0], ok, body)


class Wire(unittest.TestCase):                     # провод векторов wire.tsv (wire.md): настоящая форма и мутации
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())          # Platform ссылками, копия — только wire.tsv
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        vectors = self.tmp / "Platform/common/vectors"
        vectors.mkdir(parents=True)
        for real, place in ((ROOT / "Platform", self.tmp / "Platform"), (ROOT / "Platform/common", self.tmp / "Platform/common"),
                            (ROOT / "Platform/common/vectors", vectors)):
            for entry in real.iterdir():
                if not (place / entry.name).exists() and entry.name != "wire.tsv":
                    (place / entry.name).symlink_to(entry)
        shutil.copyfile(ROOT / "Platform/common/vectors/wire.tsv", vectors / "wire.tsv")
        (self.tmp / "Source").symlink_to(ROOT / "Source")   # фикстуры canonical от корня выгрузки
        self.path = vectors / "wire.tsv"
        self.good = self.path.read_text(encoding="utf-8")

    def errors(self):
        """Ошибки сверх ошибок настоящей формы (номер строки снят: мутация может сдвинуть строки)."""
        if not hasattr(self, "base"):
            self.base = {self.norm(e) for e in check_forms.check_wire(self.path)[0]} if self.path.read_text(
                encoding="utf-8") == self.good else set()
        return [e for e in check_forms.check_wire(self.path)[0] if self.norm(e) not in self.base]

    @staticmethod
    def norm(message):
        return re.sub(r"^wire\.tsv: row [0-9]+ ", "wire.tsv: ", message)

    def row(self, package, table, surface):
        return next(x for x in self.good.split("\n") if x.startswith(f"{package}\t{table}\t{surface}\t"))

    def mutate(self, old, new, row=None):
        if not hasattr(self, "base"):
            self.errors()
        base = row or self.good
        self.assertEqual(base.count(old), 1, old)
        text = self.good.replace(row, row.replace(old, new)) if row else self.good.replace(old, new)
        self.path.write_text(text, encoding="utf-8")
        return self.errors()

    def test_real_form_clean(self):                  # настоящая форма — без ошибок; красный здесь — дефект данных формы
        errors, stats = check_forms.check_wire(ROOT / "Platform/common/vectors/wire.tsv")
        self.assertEqual(errors, [])
        self.assertGreaterEqual(stats["wire_bindings"], 27)        # форма растёт по урокам (P/05 +2)

    def test_lf_only_lines(self):                   # U+2028 в ячейке — байт ячейки, не конец строки (JCS P/01)
        jcs = self.tmp / "Platform/common/vectors/jcs/canonical_json.tsv"
        self.assertIn(" ", jcs.read_text(encoding="utf-8"))
        table = self.tmp / "t.tsv"
        table.write_text("a\tb\nx y\tz w\x85\n", encoding="utf-8")
        self.assertEqual(check_forms.lf_lines(table), ["a\tb", "x y\tz w\x85"])
        errors, rows = check_forms.vector_rows(table, ["a", "b"], False)
        self.assertEqual((errors, len(rows)), ([], 1))

    def test_columns(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate(row, row + "\textra"))                       # лишняя колонка
        self.assertTrue(self.mutate(row, row.rsplit("\t", 1)[0]))                # пропущенная колонка
        self.assertTrue(self.mutate("package\ttable\tsurface\theader", "package\tsurface\ttable\theader"))

    def test_triple_repeats(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(any("repeats" in e for e in self.mutate(row, row + "\n" + row)))

    def test_surface(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate("\tvectors\t", "\tfunction\t", row))

    def test_compare(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate("\tvalue\t", "\tequal\t", row))
        self.assertTrue(self.mutate("\tvalue\t", "\t-\t", row))                  # «-» — только layout
        self.assertTrue(self.mutate("\tvalue\t", '\t"value"\t', row))            # кавычки — не CSV

    def test_column_not_in_header(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate('{"column":"expect","decode":"cell"}', '{"column":"wanted","decode":"cell"}', row))
        self.assertTrue(self.mutate('"cells":{"input":{"column":"input"}}', '"cells":{"input":{"column":"inp"}}', row))

    def test_value_constructor(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate('{"column":"expect","decode":"cell"}', '{"cell":"expect","decode":"cell"}', row))
        self.assertTrue(self.mutate('{"column":"expect","decode":"cell"}', '{"column":"expect","decode":"yaml"}', row))
        self.assertTrue(self.mutate('{"column":"expect","decode":"cell"}', '{"omit":true}', row))

    def test_when_compiles(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate('"variant":"","when":"true","cells"', '"variant":"","when":"row[","cells"', row))
        self.assertTrue(self.mutate('"variant":"","when":"true","cells"', '"variant":"","when":"row","cells"', row))
        self.assertTrue(self.mutate('"variant":"","when":"true","cells"', '"variant":"","when":"x == 1","cells"', row))

    def test_two_expectations(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        exp = '{"variant":"","when":"true","code":0,"value":{"column":"expect","decode":"cell"}}'
        self.assertTrue(any("2 expectations" in e for e in self.mutate(exp, exp + "," + exp, row)))
        ring = self.row("common/sealing", "ring.tsv", "vectors")             # пересекающиеся when одного variant
        self.assertTrue(any("select one row" in e for e in self.mutate(
            '"when":"row[\\"case\\"].startsWith(\\"rotate\\") && owner', '"when":"owner', ring)))

    def test_fixture_missing(self):
        row = self.row("common/log-mask", "cases.tsv", "vectors")
        self.assertTrue(self.mutate("../secret-in/fields.yaml", "../secret-in/nope.yaml", row))
        self.assertTrue(self.mutate("../secret-in/fields.yaml", "../../../../../etc/hosts", row))
        yaml_row = self.row("common/yaml-suite", "expect.tsv", "vectors")
        self.assertTrue(self.mutate("inputs/{id}.yaml", "inputs/{id}.yml", yaml_row))

    def test_layout_inputs(self):
        row = self.row("common/journal", "modes.tsv", "layout")
        self.assertTrue(self.mutate("\t[]\t{}\t", '\t[{"variant":"","cells":{"path":{"column":"path"}}}]\t{}\t', row))

    def test_header_against_table(self):
        row = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate("\tcase,input,expect,note\t", "\tcase,input,note,expect\t", row))
        lm = self.row("common/log-mask", "cases.tsv", "vectors")
        self.assertTrue(self.mutate("\t-,raw,masked,note\t", "\t-,raw,masked\t", lm))

    def test_group_constant(self):               # группа без своего столбца в case — case не постоянен
        row = self.row("02-installer/platform-lists", "cases.tsv", "vectors")
        self.assertTrue(self.mutate('"case":"list"', '"case":"word"', row))

    def test_foreign_owner(self):                    # общий пакет — только потребители consumers.tsv
        crl = self.row("common/store-client", "cases.tsv", "vectors")
        self.assertTrue(any("consumers.tsv" in e for e in self.mutate('"when":"true","cells"', '"when":"owner == \\"07-console-module\\"","cells"', crl)))

    def test_lesson_package_owner(self):             # потребители — строки consumers.tsv ∪ урок-владелец пакета урока
        row = self.row("06-console/rid", "rid.tsv", "stand:rid")
        self.assertTrue(any("not a consumer" in e for e in self.mutate('owner == \\"06-console\\"', 'owner == \\"01-store\\"', row)))
        self.consumers("06-console/rid\ttemplate.tsv\t03-worker\t", None)    # без строки when с 03-worker — чужой
        self.assertTrue(any("not a consumer" in e and "template.tsv" in e for e in self.errors()))

    def consumers(self, start, new):
        """Строка consumers.tsv, начинающаяся с `start`, заменена на `new` (None — удалена; копия вместо ссылки)."""
        path = self.path.parent / "consumers.tsv"
        text = path.read_text(encoding="utf-8")
        path.unlink()
        lines = text.split("\n")
        hit = [i for i, ln in enumerate(lines) if ln.startswith(start)]
        self.assertEqual(len(hit), 1, start)
        lines[hit[0]:hit[0] + 1] = [] if new is None else [new]
        path.write_text("\n".join(lines), encoding="utf-8")

    def test_consumers_form(self):                  # wire.md: повтор, неизвестный урок, пакет или таблица — ошибка формы
        start = "06-console/rid\ttemplate.tsv\t03-worker\t"
        line = next(ln for ln in (self.path.parent / "consumers.tsv").read_text(encoding="utf-8").split("\n") if ln.startswith(start))
        for new, word in ((line + "\n" + line, "repeats"),
                          (line.replace("\t03-worker\t", "\t99-nope\t"), "lesson '99-nope'"),
                          (line.replace("06-console/rid\t", "rid\t"), "package 'rid'"),
                          (line.replace("06-console/rid\t", "99-nope/rid\t"), "package '99-nope/rid'"),
                          (line.replace("06-console/rid\t", "common/rid\t"), "package 'common/rid'"),
                          (line.replace("\ttemplate.tsv\t", "\tnope.tsv\t"), "table 'nope.tsv'")):
            self.base = set()
            self.consumers(start, new)
            self.assertTrue(any(word in e for e in check_forms.check_wire(self.path)[0]), word)
            (self.path.parent / "consumers.tsv").unlink()
            (self.path.parent / "consumers.tsv").symlink_to(ROOT / "Platform/common/vectors/consumers.tsv")

    def test_assert_tests(self):                  # test: prefix | absent | no-leak (min_bytes ≥ 1 только у no-leak)
        row = self.row("common/family-read", "01.tsv", "vectors")
        old = '{"pointer":"/paths","compare":"set","value":{"column":"paths","decode":"json"}},{"pointer":"/outcome","compare":"value"'
        leak = '{"pointer":"/text","test":"no-leak","value":{"column":"key","decode":"text"},"min_bytes":4},'
        self.assertEqual(self.mutate(old, leak + old, row), [])
        self.assertEqual(self.mutate(old, leak.replace('{"column":"key","decode":"text"}', '{"literal":["s1","s2"]}') + old, row), [])
        self.assertTrue(self.mutate(old, leak.replace('"no-leak"', '"contains"') + old, row))       # test вне списка
        self.assertTrue(self.mutate(old, leak.replace(',"min_bytes":4', '') + old, row))            # no-leak без min_bytes
        self.assertTrue(self.mutate(old, leak.replace('"min_bytes":4', '"min_bytes":0') + old, row))
        self.assertTrue(self.mutate(old, leak.replace('{"column":"key","decode":"text"}', '{"literal":7}') + old, row))
        self.assertEqual(self.mutate(old, leak.replace('{"column":"key","decode":"text"}',
                                                       '{"array":[{"literal":"fixture-password"}]}') + old, row), [])
        self.assertTrue(self.mutate(old, leak.replace('{"column":"key","decode":"text"}', '{"array":[{"literal":7}]}') + old, row))
        self.assertTrue(self.mutate(old, '{"pointer":"/text","test":"absent","min_bytes":4},' + old, row))
        for whole in ("true", "false"):                                                             # whole — только no-leak
            self.assertEqual(self.mutate(old, leak.replace('"min_bytes":4', f'"min_bytes":4,"whole":{whole}') + old, row), [])
        self.assertTrue(self.mutate(old, leak.replace('"min_bytes":4', '"min_bytes":4,"whole":"yes"') + old, row))
        self.assertTrue(self.mutate(old, '{"pointer":"/text","test":"prefix","value":{"literal":"x"},"whole":true},' + old, row))

    def test_layout_any_table(self):              # layout допустим для любой таблицы, правило пустых ячеек прежнее
        crl = self.row("common/crl", "cases.tsv", "vectors")
        layout = "\t".join(["common/crl", "cases.tsv", "layout", "case,input,expect,note", "[]", "{}", "[]", "-", "[]", "-",
                            "common/vectors/crl/README.md"])
        self.assertEqual(self.mutate(crl, crl + "\n" + layout), [])
        fault = self.row("common/fault", "fault.tsv", "layout")   # настоящая привязка: таблица без шапки (P/03, P/06)
        self.assertTrue(self.mutate("\t-,word,status\t", "\t-,word\t", fault))
        self.assertTrue(self.mutate(crl, crl + "\n" + layout.replace("\t[]\t-\tcommon", "\t[]\tvalue\tcommon")))


class SeamFiles(unittest.TestCase):                     # находка spec103: швы урока одной главой (acceptance/seams.tsv)
    def test_flat_and_chapter_seams_found(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            for rel in ("Platform/04-controller/acceptance/seams.tsv", "Platform/01-store/acceptance/1/seams.tsv"):
                (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
                (tmp / rel).write_text("# s\n# scenario\tstep\trequest\texpect\n", encoding="utf-8")
            found = {str(p.relative_to(tmp)) for p in check_forms.seam_files(tmp)}
            self.assertEqual(found, {"Platform/04-controller/acceptance/seams.tsv", "Platform/01-store/acceptance/1/seams.tsv"})
        finally:
            shutil.rmtree(tmp)


class OpenAPIRouting(unittest.TestCase):                # P/05: x-route-priority, x-path-capture/decode/error
    BASE = """openapi: 3.1.0
paths:
  /v1/objects:
    x-route-priority: 50
    get: {responses: {'200': {description: ok}}}
  /v1/objects/{key}:
    x-route-priority: 60
    get:
      parameters:
        - {name: key, in: path, required: true, schema: {type: string}, x-path-capture: remainder, x-path-decode: percent-segment,
           x-path-error: {GET: {status: 400, response_schema: ResourceError}}}
      responses: {'200': {description: ok}, '400': {description: bad}}
components: {schemas: {ResourceError: {type: object}}}
"""

    def run_on(self, text):
        tmp = Path(tempfile.mkdtemp())
        try:
            f = tmp / "05-resource.api.openapi.yaml"
            f.write_text(text, encoding="utf-8")
            return check_forms.check_openapi_routing(f)[0]
        finally:
            shutil.rmtree(tmp)

    def test_clean_and_mutations(self):
        self.assertEqual(self.run_on(self.BASE), [])
        for old, new in (("x-route-priority: 60", "x-route-priority: 50"),        # повтор
                         ("x-route-priority: 60", "x-route-priority: 0"),         # не ≥ 1
                         ("    x-route-priority: 50\n", ""),                       # не у всех
                         ("x-path-capture: remainder", "x-path-capture: rest"),
                         ("x-path-decode: percent-segment", "x-path-decode: raw"),
                         ("{GET: {status: 400", "{PUT: {status: 400"),              # метода нет у пути
                         ("status: 400, response_schema: ResourceError", "status: 404, response_schema: ResourceError"),  # нет в ответах
                         ("response_schema: ResourceError}", "response_schema: NoSuch}"),
                         ("{name: key, in: path", "{name: key, in: query")):
            self.assertTrue(self.run_on(self.BASE.replace(old, new, 1)), (old, new))
        two = self.BASE.replace("/v1/objects/{key}:", "/v1/objects/{key}/{part}:").replace(
            "        - {name: key", "        - {name: part, in: path, required: true, schema: {type: string}, x-path-capture: segment}\n        - {name: key")
        self.assertTrue(self.run_on(two))                                         # remainder не последний


class QueryLexeme(unittest.TestCase):                   # P/05 x-query-lexeme
    def errs(self, schema_type, lex, where="query"):
        return check_forms.query_lexeme_errors("t", {"in": where, "name": "from", "schema": {"type": schema_type}, "x-query-lexeme": lex})

    def test_rules(self):
        num = {"pattern": "^(?:-?[0-9](?:_?[0-9])*)$", "parse": "number", "strip": "_"}
        self.assertEqual(self.errs("number", num), [])
        self.assertEqual(self.errs("integer", {"pattern": "^[0-9]+$", "parse": "integer"}), [])
        self.assertEqual(self.errs("string", {"pattern": "^(?:0|[1-9][0-9]*)$", "parse": "uint64"}), [])
        bad = [("number", dict(num, pattern="[0-9]+")), ("number", dict(num, pattern="^([0-9]$")), ("number", dict(num, parse="float")),
               ("integer", num), ("number", dict(num, strip="-")), ("integer", {"pattern": "^[0-9]+$", "parse": "integer", "strip": "_"}),
               ("string", {"pattern": "^[0-9]+$", "parse": "integer"}), ("number", {"parse": "number"}), ("number", dict(num, extra=1))]
        for st, lex in bad:
            self.assertTrue(self.errs(st, lex), (st, lex))
        self.assertTrue(self.errs("number", num, where="path"))


class RuntimeConstants(unittest.TestCase):              # P/06 runtime-constants.tsv
    def test_rules(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            lesson = tmp / "Platform/06-console"
            (lesson / "spec").mkdir(parents=True)
            (lesson / "forms").mkdir()
            (lesson / "spec/06.1-console.norms.md").write_text("<!-- req: P/06.1-R030 -->\nx\n", encoding="utf-8")
            f = lesson / "forms/runtime-constants.tsv"
            head = "name\tvalue\tunit\tnorm\tmeaning\n"
            good = "CHANGES_TICK\t1\ts\tP/06.1-R030\tthe listing tick\n"
            f.write_text(head + good, encoding="utf-8")
            self.assertEqual(check_forms.check_runtime_constants(f)[0], [])
            for bad in (good + good, good.replace("CHANGES_TICK", "changes_tick"), good.replace("\t1\t", "\t0\t"),
                        good.replace("\t1\t", "\t01\t"), good.replace("\ts\t", "\tns\t"), good.replace("P/06.1-R030", "P/06.1-R999"),
                        good.replace("P/06.1-R030", "P/05.1-R030"), good.replace("the listing tick", " ")):
                f.write_text(head + bad, encoding="utf-8")
                self.assertTrue(check_forms.check_runtime_constants(f)[0], bad)
        finally:
            shutil.rmtree(tmp)

    def check_rows(self, rows):
        with tempfile.TemporaryDirectory() as tmp:
            lesson = Path(tmp) / "Platform/03-worker"
            (lesson / "spec").mkdir(parents=True)
            (lesson / "forms").mkdir()
            (lesson / "spec/03.3-worker.norms.md").write_text(
                "<!-- req: P/03.3-R005 -->\n", encoding="utf-8")
            (lesson / "spec/03.6-worker.norms.md").write_text(
                "<!-- req: P/03.6-R012 -->\n", encoding="utf-8")
            path = lesson / "forms/runtime-constants.tsv"
            text = "name\tvalue\tunit\tnorm\tmeaning\n" + "".join(
                "\t".join(row) + "\n" for row in rows)
            path.write_text(text, encoding="utf-8")
            before = path.read_bytes()
            result = check_forms.check_runtime_constants(path)
            self.assertEqual(path.read_bytes(), before)
            return result

    def constant_row(self, value="250", unit="ms"):
        return ("WAKE_GAP_MS", value, unit, "P/03.3-R005", "minimum event gap")

    def test_ms_rows_keep_values_and_units(self):
        rows = [self.constant_row(),
                ("PERFORM_GRACE_MS", "200", "ms", "P/03.6-R012", "grace"),
                ("REQUESTS_HOLD_MS", "500", "ms", "P/03.6-R012", "look hold")]
        self.assertEqual(self.check_rows(rows), ([], {"runtime_constants": 3}))

    def test_existing_units_and_positive_int64_boundaries(self):
        for unit in ("count", "s", "ms", "bytes"):
            for value in ("1", "250", "9223372036854775807"):
                with self.subTest(unit=unit, value=value):
                    self.assertEqual(self.check_rows([self.constant_row(value, unit)]),
                                     ([], {"runtime_constants": 1}))

    def test_unknown_units_still_refuse(self):
        for unit in ("ns", "MS", "millisecond", "", "ms "):
            with self.subTest(unit=unit):
                errors, _ = self.check_rows([self.constant_row(unit=unit)])
                self.assertEqual(len(errors), 1)
                self.assertIn("unit", errors[0])

    def test_ms_integer_grammar_still_refuses(self):
        for value in ("0", "-1", "1.5", "true", "0250", "1e3", "\u0661", "+250", " 250"):
            with self.subTest(value=value):
                errors, _ = self.check_rows([self.constant_row(value)])
                self.assertEqual(len(errors), 1)
                self.assertIn("value", errors[0])

    def test_int64_overflow_refuses_without_integer_conversion(self):
        for value in ("9223372036854775808", "9999999999999999999", "1" + "0" * 5000):
            with self.subTest(digits=len(value)):
                errors, _ = self.check_rows([self.constant_row(value, "s")])
                self.assertEqual(len(errors), 1)
                self.assertIn("int64", errors[0])

    def test_ms_duplicate_anchor_and_meaning_guards_remain(self):
        good = self.constant_row()
        variants = [[good, good],
                    [good[:3] + ("P/03.3-R999", good[4])],
                    [good[:3] + ("P/04-R005", good[4])],
                    [good[:4] + (" ",)],
                    [("wake_gap_ms",) + good[1:]]]
        for rows in variants:
            with self.subTest(rows=rows):
                self.assertTrue(self.check_rows(rows)[0])


class WireP06(unittest.TestCase):                  # расширения провода P/06 (wire.md «P/06 transport constructors»)
    setUp, errors, row, mutate = Wire.setUp, Wire.errors, Wire.row, Wire.mutate
    norm = staticmethod(Wire.norm)

    def test_arg_file_json(self):
        rid = self.row("06-console/rid", "rid.tsv", "stand:rid")
        self.assertTrue(self.mutate('"decode":"raw-json"', '"decode":"yaml"', rid))
        self.assertEqual(self.mutate('"decode":"raw-json"', '"decode":"text"', rid), [])
        self.assertTrue(self.mutate('{"column":"rid","decode":"raw-json"}',
                                    '{"file":{"base":"package","path":"rid.tsv"},"decode":"text"}', rid))
        crl = self.row("common/crl", "cases.tsv", "vectors")                       # json — только у stand
        self.assertTrue(self.mutate('"cells":{"input":{"column":"input"}}', '"arg_file":{"json":{"literal":1}}', crl))

    def test_raw_json_only_in_arg_file(self):
        crl = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(any("raw-json" in e for e in self.mutate('"decode":"cell"', '"decode":"raw-json"', crl)))
        digest = self.row("06-console/request-digest", "digest.tsv", "stand:request-digest")
        self.assertTrue(any("raw-json" in e for e in self.mutate('{"column":"sha256","decode":"text"}',
                                                                 '{"column":"sha256","decode":"raw-json"}', digest)))

    def test_map(self):
        fault = self.row("common/fault", "fault.tsv", "vectors")
        self.assertTrue(any("requires group_by" in e for e in self.mutate('"group_by":[],', '', fault)))
        self.assertTrue(any("map key" in e for e in self.mutate('"map":{"key":"word"', '"map":{"key":"status"', fault)))
        self.assertTrue(self.mutate('"map":{"key":"word"', '"map":{"key":"nope"', fault))
        self.assertTrue(self.mutate('"value":{"column":"status","decode":"json"}}', '"value":{"group":{"column":"status","decode":"json"}}}', fault))
        crl = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate('{"column":"expect","decode":"cell"}',
                                    '{"map":{"key":"case","value":{"column":"expect","decode":"cell"}}}', crl))

    def test_input_roles_from_readme(self):          # роли колонок задаёт README: вход может читать колонку ожидания
        digest = self.row("06-console/request-digest", "digest.tsv", "stand:request-digest")
        self.assertEqual(self.mutate('"input":{"column":"input","decode":"text"}', '"input":{"column":"canonical","decode":"text"}',
                                     digest), [])
        crl = self.row("common/crl", "cases.tsv", "vectors")                # cells {} без group_by — вызов на строку
        self.assertEqual(self.mutate('"cells":{"input":{"column":"input"}}', '"cells":{}', crl), [])

    def test_marker_ignore(self):                    # marker.ignore — отказ; assert маркера без test — ignore годен
        ex = self.row("02-installer/exec", "cases.tsv", "stand:exec")
        old = '"value":{"object":{"result":{"literal":"refused"}}}}]'
        self.assertTrue(self.mutate(old, old[:-2] + ',"ignore":["/argv"]}]', ex))
        self.assertEqual(self.mutate(old, old[:-2] + ',"assert":[{"pointer":"/result","value":{"literal":"refused"},'
                                                     '"ignore":["/x"]}]}]', ex), [])
        self.assertTrue(self.mutate(old, old[:-2] + ',"assert":[{"pointer":"/result","test":"prefix","value":{"literal":"r"},'
                                                    '"ignore":["/x"]}]}]', ex))

    def test_ignore(self):
        pool = self.row("common/pool", "cases.tsv", "vectors")
        self.assertEqual(self.errors(), [])
        for bad in ('[""]', '[]', '["/fates","/fates"]', '["/fates","/fates/0"]', '["fates"]', '"/fates"'):
            self.assertTrue(self.mutate('"ignore":["/fates"]', f'"ignore":{bad}', pool), bad)
        self.assertTrue(any("console pool" in e for e in self.mutate('"ignore":["/fates"]', '"ignore":["/other"]', pool)))
        self.assertTrue(any("console pool" in e for e in self.mutate(',"ignore":["/fates"]', '', pool)))   # у 06-console — обязателен
        self.assertEqual(self.mutate('"owner == \\"04-controller\\"","code":0,"value":{"column":"expect","decode":"json"}}',
                                     '"owner == \\"04-controller\\"","code":0,"value":{"column":"expect","decode":"json"},'
                                     '"ignore":["/load"]}', pool), [])                                  # 04-controller — правило не его
        fr = self.row("common/family-read", "01.tsv", "vectors")
        old = '{"pointer":"/paths","compare":"set","value":{"column":"paths","decode":"json"}},{"pointer":"/outcome","compare":"value"'
        self.assertEqual(self.mutate(old, '{"pointer":"/a","value":{"literal":{}},"ignore":["/x","/xy"]},' + old, fr), [])
        self.assertTrue(self.mutate(old, '{"pointer":"/a","test":"absent","ignore":["/x"]},' + old, fr))
        self.assertTrue(self.mutate(old, '{"pointer":"/a","value":{"literal":{}},"ignore":["/x/~1","/x/~1/y"]},' + old, fr))

    def test_cel_json(self):
        ph = self.row("common/password-hash", "cases.tsv", "stand:password-hash")
        self.assertTrue(self.mutate('json(row[\\"input\\"])', 'json(row[\\"input\\"], \\"x\\")', ph))   # арность
        self.assertTrue(self.mutate('json(row[\\"input\\"])', 'json(1)', ph))
        self.assertTrue(any("non-JSON" in e for e in self.mutate('json(row[\\"input\\"])', 'json(row[\\"case\\"])', ph)))

    def test_at(self):                               # at: {"at":{"value":column|literal,"pointer":"/…"},"decode":"json"?}
        pool = self.row("02-installer/workers-script", "cases.tsv", "stand:workers-script")
        col = '{"column":"expect","decode":"json"}'
        at = '{"at":{"value":' + col + ',"pointer":"/start"}}'
        self.assertEqual(self.mutate(col, at, pool), [])                                     # проходящий случай
        self.assertEqual(self.mutate(col, '{"at":{"value":{"literal":{"a":"[1]"}},"pointer":"/a"},"decode":"json"}', pool), [])
        for bad in (at.replace(col, '{"at":{"value":' + col + ',"pointer":"/start"}}'),    # вложенный at
                    at.replace(col, '{"object":{"x":' + col + '}}'),                          # не column и не literal
                    at.replace('"/start"', '""'), at.replace('"/start"', '"start"'), at.replace('"/start"', '"/a~2"'),
                    at[:-1] + ',"decode":"text"}',                                            # внешний decode ≠ json
                    at[:-1] + ',"decode":"json"}',                                            # выбрано не строка
                    at.replace('"/start"', '"/nope"'),                                         # указателя нет в строках
                    '{"at":{"value":{"literal":{"a":1}},"pointer":"/b"}}',
                    '{"at":{"value":' + col + ',"pointer":"/start","extra":1}}'):
            self.assertTrue(self.mutate(col, bad, pool), bad)
        rid = self.row("06-console/rid", "rid.tsv", "stand:rid")                              # at во входе — отказ
        self.assertTrue(self.mutate('{"column":"rid","decode":"raw-json"}',
                                    '{"at":{"value":{"literal":{"a":"x"}},"pointer":"/a"}}', rid))
        crl = self.row("common/crl", "cases.tsv", "vectors")
        self.assertTrue(self.mutate('"cells":{"input":{"column":"input"}}',
                                    '"cells":{"input":{"at":{"value":{"column":"input","decode":"json"},"pointer":"/ca"}}}', crl))

    def test_arg_file_json_closed(self):             # wire.md: в arg_file json — column text|json|raw-json, literal, object, array
        rid = self.row("06-console/rid", "rid.tsv", "stand:rid")
        self.assertTrue(self.mutate('{"column":"rid","decode":"raw-json"}', '{"column":"rid","decode":"cell"}', rid))
        self.assertTrue(self.mutate('"rid":{"column":"rid","decode":"raw-json"}', '"rid":{"omit":true}', rid))
class VersionedDoors(unittest.TestCase):                # P/08 versioned-doors.tsv: настоящая форма и мутации
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.lesson = self.tmp / "Platform/08-domain"
        shutil.copytree(ROOT / "Platform/08-domain/spec", self.lesson / "spec")
        (self.lesson / "forms").mkdir()
        self.path = self.lesson / "forms/versioned-doors.tsv"
        self.good = (ROOT / "Platform/08-domain/forms/versioned-doors.tsv").read_text(encoding="utf-8")
        self.api = next((self.lesson / "spec").glob("*.api.openapi.yaml"))

    def errors(self, text):
        self.path.write_text(text, encoding="utf-8")
        return check_forms.check_versioned_doors(self.path)[0]

    def line(self, method, path):
        return next(x for x in self.good.split("\n") if x.startswith(f"{method}\t{path}\t"))

    def cell(self, method, path, column, value):
        line = self.line(method, path)
        cells = line.split("\t")
        cells[check_forms.VDOOR_COLUMNS.index(column)] = value
        return self.good.replace(line + "\n", "\t".join(cells) + "\n")

    def test_real_form_clean(self):
        errors, stats = check_forms.check_versioned_doors(ROOT / "Platform/08-domain/forms/versioned-doors.tsv")
        self.assertEqual(errors, [])
        self.assertEqual(stats["versioned_doors"], 24)
        self.assertEqual(self.errors(self.good), [])

    def test_mutations(self):
        head = "\t".join(check_forms.VDOOR_COLUMNS)
        users = self.line("PUT", "/domain/users/{name}")
        bad = {
            "extra column": self.good.replace(head, head + "\tnote").replace(users, users + "\tx"),
            "missing column": self.good.replace("\tabsent_revision\t", "\t"),
            "source column": self.good.replace(head, head + "\tsource").replace(users, users + "\tx"),
            "unknown operation": self.good.replace(users, users.replace("PUT\t/domain/users/{name}", "PUT\t/domain/nope/{name}")),
            "uncovered operation": self.good.replace(users + "\n", ""),
            "repeat": self.good.replace(users + "\n", users + "\n" + users + "\n"),
            "revision": self.cell("PUT", "/domain/users/{name}", "revision", "version"),
            "etag": self.cell("PUT", "/domain/users/{name}", "etag", "yes"),
            "etag against OpenAPI": self.cell("PUT", "/domain/users/{name}", "etag", "false"),
            "if_match": self.cell("PUT", "/domain/users/{name}", "if_match", "required"),
            "if_match against OpenAPI": self.cell("PUT", "/domain/users/{name}", "if_match", "ignored"),
            "absent_revision": self.cell("PUT", "/domain/users/{name}", "absent_revision", "1"),
            "row kind": self.cell("PUT", "/domain/users/{name}", "row", "domain/users/{name}"),
            "row placeholder": self.cell("PUT", "/domain/users/{name}", "row", "domain/users/<user>"),
            "norm anchor": self.cell("PUT", "/domain/users/{name}", "norm", "P/08.0-R005,P/08.0-R999"),
            "norm foreign lesson": self.cell("PUT", "/domain/users/{name}", "norm", "P/06.1-R030"),
            "norm form": self.cell("PUT", "/domain/users/{name}", "norm", "P/08.0 Н1.9"),
            "norm empty": self.cell("PUT", "/domain/users/{name}", "norm", ""),
            "base-rev without R006": self.cell("PUT", "/domain/topology", "norm", "P/08.0-R005"),
            "optional-index with absent 0": self.cell("PUT", "/domain/grants/{cluster}", "if_match", "optional-index"),
            "revision - with etag true": self.cell("PUT", "/domain/users/{name}", "revision", "-"),
            "revision - with if_match optional": self.cell("DELETE", "/domain/users/{name}", "revision", "-"),
            "revision - with base-rev": self.both("PUT", "/domain/topology",
                                                   {"revision": "-", "etag": "false", "absent_revision": "-"}),
        }
        for what, text in bad.items():
            self.assertNotEqual(text, self.good, what)
            self.assertTrue(self.errors(text), what)

    def both(self, method, path, values):
        line = self.line(method, path)
        cells = line.split("\t")
        for column, value in values.items():
            cells[check_forms.VDOOR_COLUMNS.index(column)] = value
        return self.good.replace(line + "\n", "\t".join(cells) + "\n")

    def test_new_values_pass(self):                     # решение «Архитектора» 2026-11-06: `-` и optional-index
        ok = {
            "optional-index": self.cell("PUT", "/domain/users/{name}", "if_match", "optional-index"),
            "revision - optional-index": self.both("DELETE", "/domain/users/{name}",
                                                   {"revision": "-", "if_match": "optional-index"}),
            "revision - ignored": self.cell("POST", "/domain/batch", "revision", "-"),
        }
        for what, text in ok.items():
            self.assertNotEqual(text, self.good, what)
            self.assertEqual(self.errors(text), [], what)

    def test_new_rules_alone(self):                     # каждое новое правило даёт ровно свою ошибку
        cases = {
            "needs absent_revision -": self.cell("PUT", "/domain/grants/{cluster}", "if_match", "optional-index"),
            "needs etag false": self.both("PUT", "/domain/users/{name}", {"revision": "-", "if_match": "optional-index"}),
            "needs if_match optional-index or ignored": self.cell("DELETE", "/domain/users/{name}", "revision", "-"),
        }
        for what, text in cases.items():
            errors = self.errors(text)
            self.assertEqual(len(errors), 1, (what, errors))
            self.assertIn(what, errors[0])

    def test_openapi_side(self):                        # новая операция с If-Match без строки формы — отказ
        text = self.api.read_text(encoding="utf-8")
        self.assertEqual(self.errors(self.good), [])
        self.api.write_text(text.replace("\npaths:\n", "\npaths:\n  /domain/extra:\n    put:\n      parameters:\n"
                                         "        - $ref: '#/components/parameters/IfMatch'\n"
                                         "      responses: {'200': {description: ok}}\n", 1), encoding="utf-8")
        self.assertTrue(self.errors(self.good))



RWB_CATALOG = ("key\tkind\towner\tops\treaders\twhen\tversion\tschema\tnorm\n"
               "<sub>/state/<имя>/<id>\trow\tP/03.6\tguard=<s>worker\t<s>worker\tunit.state\t1\t03-worker/data/state.schema.json\tP/03.6 Н1.7\n"
               "<sub>/epoch/<id>\trow\tP/03.2\tcreate=<s>worker\t<s>worker\t-\t1\t03-worker/data/epoch.schema.json\tP/03.2 Н1.5\n"
               "<sub>/<manifest:unit.rows>/<id>\trow\tP/06.1\tcas=console\tconsole\t-\t1\tmanifest\tP/06.1 Н1.2\n")
RWB_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["born", "revision", "epoch", "value"],
              "properties": {"born": {"type": "string"}, "revision": {"$ref": "#/$defs/common.pos53"},
                             "epoch": {"$ref": "#/$defs/common.pos53"}, "value": {}},
              "$defs": {"common.pos53": {"type": "integer", "minimum": 1}}}
RWB_DECLS = ("#start /sub string\n#start /unit string\n#start /born string\n#start /revision integer\n"
             "#start /epoch integer\n#start /epoch_index string\n#input /name string\n#input /value dyn\n")
RWB_KEY = "{start:/sub}/state/{input:/name}/{start:/unit}"
RWB_GUARD = "{start:/sub}/epoch/{start:/unit}\tstart:/epoch_index"
RWB_NORM = "P/03.6-R018,P/03.6-R029"
RWB_GOOD = ("\t".join(check_forms.RWB_COLUMNS) + "\n" + RWB_DECLS +
            "".join(f"state\t{RWB_KEY}\t/{f}\t{s}\t/{f}\t{RWB_GUARD}\t{RWB_NORM}\n"
                    for f, s in (("born", "start"), ("revision", "start"), ("epoch", "start"), ("value", "input"))))


class RowWriteBindings(unittest.TestCase):              # P/03 row-write-bindings.tsv (P03-GEN-01): фикстура и мутации
    def setUp(self):
        import json
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.lesson = self.tmp / "Platform/03-worker"
        for d in ("forms", "spec", "data"):
            (self.lesson / d).mkdir(parents=True)
        (self.tmp / "Platform/common/data").mkdir(parents=True)
        (self.tmp / "Platform/common/data/catalog.tsv").write_text(RWB_CATALOG, encoding="utf-8")
        (self.lesson / "data/state.schema.json").write_text(json.dumps(RWB_SCHEMA), encoding="utf-8")
        (self.lesson / "spec/03.6-worker.norms.md").write_text(
            "## Н1\n<!-- req: P/03.6-R018 -->\ntext\n<!-- req: P/03.6-R029 -->\ntext\n", encoding="utf-8")
        self.path = self.lesson / "forms/row-write-bindings.tsv"

    def errors(self, text):
        self.path.write_text(text, encoding="utf-8")
        return check_forms.check_row_write_bindings(self.path)[0]

    def row(self, field, text=RWB_GOOD):
        return next(x for x in text.split("\n") if x.startswith("state\t") and x.split("\t")[2] == field)

    def cell(self, field, column, value, text=RWB_GOOD):
        line = self.row(field, text)
        cells = line.split("\t")
        cells[check_forms.RWB_COLUMNS.index(column)] = value
        return text.replace(line + "\n", "\t".join(cells) + "\n")

    def all_cells(self, column, value):
        text = RWB_GOOD
        for f in ("/born", "/revision", "/epoch", "/value"):
            text = self.cell(f, column, value, text)
        return text

    def test_good(self):
        self.path.write_text(RWB_GOOD, encoding="utf-8")
        errors, stats = check_forms.check_row_write_bindings(self.path)
        self.assertEqual(errors, [])
        self.assertEqual(stats["row_write_bindings"], 4)
        const = self.cell("/born", "source", "const")
        self.assertEqual(self.errors(self.cell("/born", "value", '""', const)), [])   # const "" — синтаксис

    def test_real_lessons(self):                        # настоящая форма урока, если она есть в main
        for path in check_forms.row_write_binding_forms(ROOT):
            self.assertEqual(check_forms.check_row_write_bindings(path)[0], [], path)

    def test_mutations(self):
        head = "\t".join(check_forms.RWB_COLUMNS)
        bad = {
            "header extra": RWB_GOOD.replace(head, head + "\tmeaning", 1),
            "header order": RWB_GOOD.replace(head, head.replace("field\tsource", "source\tfield"), 1),
            "header short": RWB_GOOD.replace(head, head.replace("\tnorm", ""), 1),
            "write name": self.all_cells("write", "State"),
            "write field repeats": RWB_GOOD + self.row("/born") + "\n",
            "key differs": self.cell("/epoch", "key", "{start:/sub}/state/{input:/name}/x"),
            "guard_key differs": self.cell("/epoch", "guard_key", "{start:/sub}/epoch/x"),
            "guard_version differs": self.cell("/epoch", "guard_version", "input:/name"),
            "field not pointer": self.cell("/born", "field", "born"),
            "field nested": self.cell("/born", "field", "/born/x"),
            "foreign property": self.cell("/born", "field", "/made"),
            "required not bound": RWB_GOOD.replace(self.row("/epoch") + "\n", ""),
            "source": self.cell("/born", "source", "snapshot"),
            "value no slash": self.cell("/born", "value", "born"),
            "value empty": self.cell("/born", "value", ""),
            "value undeclared": self.cell("/born", "value", "/made"),
            "value of other source": self.cell("/value", "source", "start"),
            "value CEL": self.cell("/revision", "value", "/revision + 1"),
            "const CEL": self.cell("/revision", "value", "start.revision + 1", self.cell("/revision", "source", "const")),
            "const not strict JSON": self.cell("/revision", "value", "NaN", self.cell("/revision", "source", "const")),
            "const type": self.cell("/revision", "value", '"1"', self.cell("/revision", "source", "const")),
            "declaration type": RWB_GOOD.replace("#input /value dyn", "#input /value any"),
            "declaration repeats": RWB_GOOD.replace("#input /value dyn", "#input /value dyn\n#input /value string"),
            "declaration form": RWB_GOOD.replace("#input /value dyn", "#input value dyn"),
            "type against schema": RWB_GOOD.replace("#start /revision integer", "#start /revision string"),
            "key placeholder undeclared": self.all_cells("key", "{start:/sub}/state/{input:/nom}/{start:/unit}"),
            "key placeholder not string": self.all_cells("key", "{start:/sub}/state/{input:/name}/{start:/epoch}"),
            "key placeholder part of segment": self.all_cells("key", "{start:/sub}/state/x{input:/name}/{start:/unit}"),
            "key placeholder name": self.all_cells("key", "{start:/sub}/state/{arg:/name}/{start:/unit}"),
            "key CEL": self.all_cells("key", "start.sub + '/state'"),
            "key foreign family": self.all_cells("key", "{start:/sub}/state"),
            "key family without schema": self.all_cells("key", "{start:/sub}/{input:/name}/{start:/unit}"),
            "guard_key template": self.all_cells("guard_key", "{start:/sub}/epoch/{now}"),
            "guard_version form": self.all_cells("guard_version", "/epoch_index"),
            "guard_version undeclared": self.all_cells("guard_version", "start:/version"),
            "guard_version not string": self.all_cells("guard_version", "start:/epoch"),
            "guard one filled (key)": self.all_cells("guard_version", "-"),
            "guard one filled (version)": self.all_cells("guard_key", "-"),
            "norm empty": self.cell("/born", "norm", ""),
            "norm absent anchor": self.cell("/born", "norm", "P/03.6-R018,P/03.6-R999"),
            "norm foreign lesson": self.cell("/born", "norm", "P/06.1-R030"),
            "norm repeats": self.cell("/born", "norm", "P/03.6-R018,P/03.6-R018"),
            "norm form": self.cell("/born", "norm", "P/03.6 Н1.7"),
        }
        self.assertEqual(self.errors(RWB_GOOD), [])
        self.assertEqual(self.errors(self.all_cells("guard_key", "-").replace("\tstart:/epoch_index\t", "\t-\t")), [])
        for what, text in bad.items():
            self.assertNotEqual(text, RWB_GOOD, what)
            self.assertTrue(self.errors(text), what)


TURN_WIRE_ROW = 'common/turn\tcases.tsv\tvectors\tcase,input,expect,note\t[{"variant":"","when":"(owner == \\"04-controller\\" && json(row[\\"input\\"])[\\"kind\\"] == \\"placement\\") || (owner in [\\"08-domain\\",\\"09-agent\\"] && json(row[\\"input\\"])[\\"kind\\"] == \\"signer\\") || (owner == \\"06-console\\" && json(row[\\"input\\"])[\\"kind\\"] == \\"operations\\")","cells":{"input":{"column":"input"}}}]\t{}\t[{"variant":"","code":0,"value":{"column":"expect","decode":"json"}}]\tturn\t[]\t{"type":"array","frame":"json"}\tcommon/vectors/turn/README.md#run'   # decisions/inbox/2026-11-06-p06-review-proposals/c4-wire-row.proposed.tsv (391efde0d)
TURN_OPS_ROWS = ['operations-take-empty\t{"kind":"operations","turn":"testsub/operations-turn","me":{},"steps":[{"read":null,"seen":0},{"reply":"ok","version":1}]}\t[{"write":{"holder":"@new"},"cas":""},"held"]\tProposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.', 'operations-take-released\t{"kind":"operations","turn":"testsub/operations-turn","me":{},"steps":[{"read":{"holder":""},"seen":0,"version":3},{"reply":"ok","version":4}]}\t[{"write":{"holder":"@new"},"cas":3},"held"]\tProposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.', 'operations-busy-live\t{"kind":"operations","turn":"testsub/operations-turn","me":{},"steps":[{"read":{"holder":"c-old"},"seen":44.999,"version":3}]}\t["busy"]\tProposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.', 'operations-take-stale\t{"kind":"operations","turn":"testsub/operations-turn","me":{},"steps":[{"read":{"holder":"c-old"},"seen":45,"version":3},{"reply":"ok","version":4}]}\t[{"write":{"holder":"@new"},"cas":3},"held"]\tProposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.', 'operations-first-sight\t{"kind":"operations","turn":"testsub/operations-turn","me":{},"steps":[{"read":{"holder":"c-old"},"seen":0,"version":3}]}\t["busy"]\tProposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.', 'operations-unreadable\t{"kind":"operations","turn":"testsub/operations-turn","me":{},"steps":[{"read":"@unreadable","seen":0}]}\t["refused"]\tProposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.', 'operations-take-conflict\t{"kind":"operations","turn":"testsub/operations-turn","me":{},"steps":[{"read":null,"seen":0},{"reply":"conflict"}]}\t[{"write":{"holder":"@new"},"cas":""},"not_held"]\tProposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.', 'operations-renew\t{"kind":"operations","turn":"testsub/operations-turn","me":{},"steps":[{"read":null,"seen":0},{"reply":"ok","version":1},{"renew":true},{"reply":"ok","version":2},{"renew":true},{"reply":"conflict"}]}\t[{"write":{"holder":"@new"},"cas":""},"held",{"write":{"holder":"@same"},"cas":1},"held",{"write":{"holder":"@same"},"cas":2},"stop"]\tProposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.', 'operations-guard\t{"kind":"operations","turn":"testsub/operations-turn","me":{},"steps":[{"read":null,"seen":0},{"reply":"ok","version":1},{"target":true,"age":44.999},{"target":true,"age":45}]}\t[{"write":{"holder":"@new"},"cas":""},"held",{"guard":{"key":"testsub/operations-turn","index":1}},"wait"]\tProposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.', 'operations-guard-412\t{"kind":"operations","turn":"testsub/operations-turn","me":{},"steps":[{"read":null,"seen":0},{"reply":"ok","version":1},{"target":true,"age":1},{"target_reply":"412"}]}\t[{"write":{"holder":"@new"},"cas":""},"held",{"guard":{"key":"testsub/operations-turn","index":1}},"stop"]\tProposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.', 'operations-release\t{"kind":"operations","turn":"testsub/operations-turn","me":{},"steps":[{"read":null,"seen":0},{"reply":"ok","version":1},{"end":true},{"reply":"conflict"}]}\t[{"write":{"holder":"@new"},"cas":""},"held",{"write":{"holder":""},"cas":1},"done"]\tProposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.', 'operations-unknown-take-applied\t{"kind":"operations","turn":"testsub/operations-turn","me":{},"steps":[{"read":null,"seen":0},{"reply":"none"},{"read":{"holder":"@same"},"seen":0,"version":1},{"reply":"ok","version":2}]}\t[{"write":{"holder":"@new"},"cas":""},"reread",{"write":{"holder":"@same"},"cas":1},"held"]\tProposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.', 'operations-unknown-take-lost\t{"kind":"operations","turn":"testsub/operations-turn","me":{},"steps":[{"read":null,"seen":0},{"reply":"none"},{"read":null,"seen":0}]}\t[{"write":{"holder":"@new"},"cas":""},"reread","not_held"]\tProposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.', 'operations-unknown-take-foreign\t{"kind":"operations","turn":"testsub/operations-turn","me":{},"steps":[{"read":null,"seen":0},{"reply":"none"},{"read":{"holder":"c-other"},"seen":0,"version":1}]}\t[{"write":{"holder":"@new"},"cas":""},"reread","not_held"]\tProposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.', 'operations-unknown-renew\t{"kind":"operations","turn":"testsub/operations-turn","me":{},"steps":[{"read":null,"seen":0},{"reply":"ok","version":1},{"renew":true},{"reply":"none"},{"read":{"holder":"@same"},"seen":0,"version":2},{"reply":"ok","version":3}]}\t[{"write":{"holder":"@new"},"cas":""},"held",{"write":{"holder":"@same"},"cas":1},"reread",{"write":{"holder":"@same"},"cas":2},"held"]\tProposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.']   # там же c4-turn-cases.proposed.tsv: 15 строк operations


class WireTurn(unittest.TestCase):               # compare=turn — решение «Архитектора» 2026-11-06 (P/06 C4)
    def setUp(self):
        Wire.setUp(self)
        vectors = self.path.parent
        (vectors / "turn").unlink()                 # пакет turn и consumers.tsv — копии с предложенными строками
        shutil.copytree(ROOT / "Platform/common/vectors/turn", vectors / "turn")
        # фикстура не зависит от того, активна ли C4 в ROOT: прежние 33 строки, 3 потребителя и wire без common/turn,
        # затем строки предложения ровно один раз
        self.cases = vectors / "turn/cases.tsv"
        kept = [ln for ln in self.cases.read_text(encoding="utf-8").split("\n") if ln and not ln.startswith("operations-")]
        self.assertEqual(len(kept), 2 + 33)
        self.cases.write_text("\n".join(kept + TURN_OPS_ROWS) + "\n", encoding="utf-8")
        consumers = vectors / "consumers.tsv"
        text = consumers.read_text(encoding="utf-8")
        consumers.unlink()
        start = "common/turn\tcases.tsv\t06-console\t"
        kept = [ln for ln in text.rstrip("\n").split("\n") if not ln.startswith(start)]
        self.assertEqual(sum(ln.startswith("common/turn\t") for ln in kept), 3)
        line = start + "common/vectors/turn/README.md: own operations turn; ADR-0127 P06 C4"
        consumers.write_text("\n".join(kept + [line]) + "\n", encoding="utf-8")
        self.good = "".join(ln for ln in self.good.splitlines(keepends=True)
                            if not ln.startswith("common/turn\tcases.tsv\tvectors\t"))
        self.path.write_text(self.good, encoding="utf-8")

    def check(self, row=TURN_WIRE_ROW, old=None, new=None):
        if old is not None:
            self.assertEqual(row.count(old), 1, old)
            row = row.replace(old, new)
        self.path.write_text(self.good.rstrip("\n") + "\n" + row + "\n", encoding="utf-8")
        return check_forms.check_wire(self.path)[0]

    def case(self, name, old, new):               # порча ячейки expect одной строки по имени случая (note не читается)
        lines = self.cases.read_text(encoding="utf-8").split("\n")
        hit = [i for i, ln in enumerate(lines) if ln.split("\t")[0] == name]
        self.assertEqual(len(hit), 1, name)
        cells = lines[hit[0]].split("\t")
        self.assertEqual(cells[2].count(old), 1, old)
        cells[2] = cells[2].replace(old, new)
        lines[hit[0]] = "\t".join(cells)
        self.cases.write_text("\n".join(lines), encoding="utf-8")

    def test_proposed_row_passes(self):
        errors, stats = check_forms.check_wire(self.path)
        self.assertEqual(errors, [])
        self.assertEqual(self.check(), [])
        calls = check_forms.check_wire(self.path)[1]["wire_calls"] - stats["wire_calls"]
        self.assertEqual(calls, 20 + 2 * 13 + 15)           # 04 — placement, 08 и 09 — signer, 06 — operations

    def test_turn_only_common_turn(self):
        other = Wire.row(self, "common/crl", "cases.tsv", "vectors")
        errors = self.check(other.replace("\tvalue\t", "\tturn\t"))
        self.assertTrue(any("compare turn is only for the binding" in e for e in errors), errors)
        errors = self.check(other.replace("\tvalue\t", '\t{"":"turn"}\t'))      # и картой вариантов — вне списка
        self.assertTrue(any("is not one of" in e for e in errors), errors)

    def test_unknown_freshness_mark(self):
        self.case("operations-take-conflict", '"@new"', '"@fresh"')
        self.assertTrue(any("unknown freshness mark '@fresh'" in e for e in self.check()))

    def test_same_before_new(self):
        self.case("operations-unknown-take-foreign", '"@new"', '"@same"')
        self.assertTrue(any("@same before any @new" in e for e in self.check()))

    def test_holder_alias(self):
        self.case("operations-take-conflict", '{"holder":"@new"}', '{"value":"@new"}')
        self.assertTrue(any("outside holder (no alias)" in e for e in self.check()))
        self.case("operations-take-conflict", '{"value":"@new"}', '{"holder":"@new"}')
        alias = '{"column":"expect","decode":"json"}'
        errors = self.check(old=alias, new='{"object":{"holder":{"literal":"@new"}}}')
        self.assertTrue(any("no holder or value alias" in e for e in errors), errors)

    def test_ignore_turn_field(self):
        errors = self.check(old='"code":0,', new='"code":0,"ignore":["/0/write/holder"],')
        self.assertTrue(any("no ignore or assert" in e for e in errors), errors)

    def test_selector_not_cel(self):
        when = TURN_WIRE_ROW.split('"when":', 1)[1].split(',"cells"', 1)[0]
        errors = self.check(old=when, new='{"owner":"06-console","kind":"operations"}')
        self.assertTrue(any("when is not a CEL string" in e for e in errors), errors)
        errors = self.check(old=when, new='"owner = 06-console"')
        self.assertTrue(any("does not compile" in e for e in errors), errors)
        errors = self.check(old='"variant":"","when":' + when + ',', new='"variant":"",')
        self.assertTrue(any("explicit CEL selector" in e for e in errors), errors)

    def test_turn_markers_empty(self):
        errors = self.check(old="\tturn\t[]\t", new='\tturn\t[{"variant":"","column":"expect","match":"[\\"busy\\"]"}]\t')
        self.assertTrue(any("markers must be []" in e for e in errors), errors)


class TurnMatch(unittest.TestCase):              # compare=turn по меткам: @new всякий раз новая, @same — последняя @new
    W = lambda holder, cas: {"write": {"holder": holder}, "cas": cas}   # noqa: E731

    def test_two_attempts(self):
        W = TurnMatch.W
        expected = [W("@new", ""), "held", W("@same", 1), "stop", W("@new", ""), "held", W("@same", 3), "held"]
        actual = [W("a1", ""), "held", W("a1", 1), "stop", W("a2", ""), "held", W("a2", 3), "held"]
        self.assertEqual(check_forms.turn_match(expected, actual), [])
        same = [W("a1", ""), "held", W("a1", 1), "stop", W("a1", ""), "held", W("a1", 3), "held"]
        self.assertTrue(any("repeats an earlier @new" in e for e in check_forms.turn_match(expected, same)))
        stale = [W("a1", ""), "held", W("a1", 1), "stop", W("a2", ""), "held", W("a1", 3), "held"]
        self.assertTrue(any("is not the last @new" in e for e in check_forms.turn_match(expected, stale)))

    def test_new_new_in_a_row(self):
        W = TurnMatch.W
        expected = [W("@new", ""), "reread", W("@new", "")]
        self.assertEqual(check_forms.turn_match(expected, [W("a1", ""), "reread", W("a2", "")]), [])
        self.assertTrue(any("repeats" in e for e in check_forms.turn_match(expected, [W("a1", ""), "reread", W("a1", "")])))

    def test_exact_rest(self):
        W = TurnMatch.W
        expected = [W("@new", ""), "held", W("", 1), "done"]
        self.assertEqual(check_forms.turn_match(expected, [W("a1", ""), "held", W("", 1), "done"]), [])
        for bad in ([W("@new", ""), "held", W("", 1), "done"],              # литерал метки — не настоящая метка
                    [W("a1", 0), "held", W("", 1), "done"],                  # cas "" — не 0
                    [W("a1", ""), "held", W("a1", 1), "done"],               # holder "" сравнивается точно
                    [W("a1", ""), "held", W("", True), "done"],              # boolean — не число
                    [W("a1", ""), "held", W("", 1), "done", "extra"],
                    [{"write": {"holder": "a1", "x": 1}, "cas": ""}, "held", W("", 1), "done"]):
            self.assertTrue(check_forms.turn_match(expected, bad), bad)
        self.assertEqual(check_forms.turn_match([W("box-a:1", 2)], [W("box-a:1", 2.0)]), [])   # литеральный holder signer


FP_CASES = ROOT / "Platform/02-installer/forms/finite-profile.cases.json"


@unittest.skipUnless(FP_CASES.exists(), "источник C2 P/06 ещё не влит")
class FiniteProfile(unittest.TestCase):          # конечный профиль удаления P/06 C2 — решение «Архитектора» 2026-11-06
    FILES = ("Platform/02-installer/forms/finite-profile.cases.json", "Platform/02-installer/forms/finite-profile.schema.json",
             "Platform/06-console/forms/runtime-constants.tsv", "Platform/06-console/forms/deletion-body-witnesses.json")
    SKELETONS = "Platform/02-installer/forms/finite-profile-skeletons"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        for f in self.FILES:
            (self.tmp / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / f, self.tmp / f)
        shutil.copytree(ROOT / self.SKELETONS, self.tmp / self.SKELETONS)
        self.skel = self.tmp / self.SKELETONS
        self.path = self.tmp / self.FILES[0]
        self.wpath = self.tmp / self.FILES[3]
        self.good = json.loads(FP_CASES.read_text(encoding="utf-8"))

    def errors(self, mutate):
        d = copy.deepcopy(self.good)
        mutate(d)
        self.path.write_text(json.dumps(d), encoding="utf-8")
        return check_forms.check_finite_profile(self.path)[0]

    def case(self, d, name):
        return next(c for c in d["cases"] if c["case"] == name)

    def packet(self, d, case, name):
        return next(k for k in self.case(d, case)["profile"]["packets"] if k["packet"] == name)

    def test_real_cases_pass(self):
        errors, stats = check_forms.check_finite_profile(FP_CASES)
        self.assertEqual(errors, [])
        self.assertEqual(stats["finite_profile_cases"], 13)
        self.assertEqual(stats["finite_profile_skeletons"], 8)
        self.assertEqual(self.errors(lambda d: None), [])

    def test_mutations(self):
        ok, tgt = "bound-exact-B", "unit-delete-target"

        def drop(d):
            ps = self.case(d, ok)["profile"]["packets"]
            ps.remove(self.packet(d, ok, tgt))

        def dup(d):
            ps = self.case(d, ok)["profile"]["packets"]
            ps.append(copy.deepcopy(ps[0]))

        def setp(field, value, packet=tgt):
            return lambda d: self.packet(d, ok, packet).__setitem__(field, value)

        def ctx_desc(field, value, packet=tgt):
            return lambda d: next(x for x in d["owned_context"]["descriptors"] if x["packet"] == packet).__setitem__(field, value)

        bad = {
            "missing packet": (drop, "of the roster is missing"),
            "duplicate packet": (dup, "repeats"),
            "wrong H (greater)": (setp("H", 93744), "!= H 93743 assembled"),
            "wrong H (less)": (setp("H", 93742), "!= H 93743 assembled"),
            "wrong n_folder": (setp("n_folder", 9), "n_folder 9 != descriptor 8"),
            "wrong n_guard": (setp("n_guard", 3), "n_guard 3 != descriptor 4"),
            "wrong n_claim": (setp("n_claim", 0, "claim-acquire"), "n_claim 0 != descriptor 1"),
            "no multiplicity proof": (setp("multiplicity_proof", "owned-descriptor:claim-acquire"), "multiplicity_proof"),
            "free provenance": (lambda d: self.case(d, ok)["profile"]["provenance"].__setitem__("catalogue", "trust-me"),
                                "provenance.catalogue"),
            "pass at bound > B": (lambda d: self.case(d, "bound-B-plus-one").__setitem__("expect", "ok"), "> B 609947875"),
            "refused without reason": (lambda d: self.case(d, "limit-one-above-bound").__setitem__("expect", "refused:form"),
                                       "the judge gives ok"),
            "V not effective": (lambda d: self.case(d, ok)["profile"].__setitem__("row_weight_bytes", 524287),
                                "row_weight_bytes"),
            "F not FOLDER_ROW_MAX": (lambda d: self.case(d, ok)["profile"].__setitem__("folder_weight_bytes", 65535),
                                     "FOLDER_ROW_MAX"),
            "key beyond 1024": (lambda d: self.case(d, ok)["profile"]["metadata"].__setitem__("key_utf8_bytes", 1025),
                                "schema"),
            "context duplicate roster": (lambda d: d["owned_context"]["descriptor_packet_roster"].append("claim-acquire"),
                                         "roster: packet 'claim-acquire' repeats"),
            "context descriptor H": (ctx_desc("H", 93742), "H 93742 != H 93743 assembled"),
            "context skeleton": (ctx_desc("skeleton_entity_bytes", 93138), "the judge gives refused"),
            "context key_json": (ctx_desc("key_json_bytes", 6145), "6*key_utf8_bytes+2"),
            "context version 21": (ctx_desc("version_digits", 21), "version_digits 21"),
            "context put_slots": (ctx_desc("put_slots", 9), "put_slots/timestamp_slots"),
            "context counts": (lambda d: next(x for x in d["owned_context"]["descriptors"] if x["packet"] == tgt)
                               ["counts"].__setitem__("n_folder", 7), "the judge gives refused"),
            "context integer domain": (lambda d: d["owned_context"]["status"].__setitem__("max_body", 2 ** 53),
                                       "outside 0..2^53-1"),
            "expected bound": (lambda d: d["expected_bounds"].__setitem__(tgt, 9531088), "expected_bounds unit-delete-target"),
            "max_bound": (lambda d: d.__setitem__("max_bound", 609947875), "max_bound"),
            "no exact-B case": (lambda d: d["cases"].remove(self.case(d, ok)), "exactly B"),
            "no B+1 case": (lambda d: d["cases"].remove(self.case(d, "bound-B-plus-one")), "B+1"),
        }
        for name, (mutate, needle) in bad.items():
            with self.subTest(name):
                errors = self.errors(mutate)
                self.assertTrue(any(needle in e for e in errors), errors)

    def resign(self, d, packet, raw):
        """Переписать байты скелета и согласованно его sha256, длину и числа в контексте."""
        (self.skel / f"{packet}.json").write_bytes(raw)
        sha = hashlib.sha256(raw).hexdigest()
        pr = next(x for x in d["owned_context"]["metadata-proofs"] if x["packet"] == packet)
        ds = next(x for x in d["owned_context"]["descriptors"] if x["packet"] == packet)
        pr["sha256"] = ds["metadata_skeleton_sha256"] = sha
        pr["bytes"] = ds["skeleton_entity_bytes"] = len(raw)

    def test_byte_skeletons(self):                  # доработка по c34fc58c5: байты скелетов потребляются, числам не верим
        tgt = "unit-delete-target"
        raw = (self.skel / f"{tgt}.json").read_bytes()
        k0, k1 = b"\\u0000" * 3, b"\\u0001" + b"\\u0000" * 2
        self.assertIn(k1, raw)

        def same_numbers_other_bytes(d):            # та же длина, sha согласован, ключ повторён
            self.resign(d, tgt, raw.replace(k1, k0, 1))

        def stale_sha(d):                           # байты подменены, заявленный sha прежний
            (self.skel / f"{tgt}.json").write_bytes(raw.replace(k1, k0, 1))

        def removed(d):
            (self.skel / f"{tgt}.json").unlink()

        def forged_numbers(d):                      # согласованно +1: длина, H дескриптора, H профилей, ожидание
            ds = next(x for x in d["owned_context"]["descriptors"] if x["packet"] == tgt)
            pr = next(x for x in d["owned_context"]["metadata-proofs"] if x["packet"] == tgt)
            ds["skeleton_entity_bytes"] += 1
            pr["bytes"] += 1
            ds["H"] += 1
            for c in d["cases"]:
                for k in c["profile"].get("packets") or []:
                    if isinstance(k, dict) and k.get("packet") == tgt:
                        k["H"] += 1
            d["expected_bounds"][tgt] += 1

        def final_lf(d):                            # LF в скелете при согласованных sha и длине
            self.resign(d, tgt, raw + b"\n")

        def spaced(d):                              # не компактный кодек
            self.resign(d, tgt, raw.replace(b'"op":"batch"', b'"op": "batch"', 1))

        def items_not_empty(d):
            self.resign(d, tgt, raw.replace(b'"items":{}', b'"items":{"a":1}', 1))

        def ctx_meta(k, v):
            return lambda d: d["owned_context"]["metadata"].__setitem__(k, v)

        def dup_proof(d):
            ps = d["owned_context"]["metadata-proofs"]
            ps.append(copy.deepcopy(ps[0]))

        def case_meta(k, v):
            return lambda d: self.case(d, "bound-exact-B")["profile"]["metadata"].__setitem__(k, v)

        bad = {
            "other bytes, same numbers": (same_numbers_other_bytes, "skeleton keys repeat"),
            "stale sha": (stale_sha, "!= declared"),
            "skeleton removed": (removed, "does not resolve"),
            "forged numbers": (forged_numbers, "skeleton has 93139 bytes"),
            "final LF in skeleton": (final_lf, "final LF"),
            "not compact": (spaced, "not exactly the compact-json-utf8"),
            "items not empty": (items_not_empty, "items is not {}"),
            "context LF 0": (ctx_meta("trailing_lf", 0), "metadata.trailing_lf 1 != owned_context.metadata 0"),
            "context LF 2": (ctx_meta("trailing_lf", 2), "trailing_lf 2 is not 0 or 1"),
            "context encoder": (ctx_meta("encoder", "json-ascii"), "encoder 'json-ascii' is not"),
            "case LF differs": (case_meta("trailing_lf", 0), "the judge gives refused"),
            "proofs section gone": (lambda d: d["owned_context"].pop("metadata-proofs"), "is not a list"),
            "proof ref unresolvable": (lambda d: d["owned_context"]["descriptors"][0].__setitem__(
                "metadata_skeleton_proof", "owned-context:metadata-proof"), "does not resolve to"),
            "stale profile proof ref": (lambda d: self.case(d, "bound-exact-B")["profile"]["provenance"].__setitem__(
                "metadata_skeleton_proof", "owned-context:descriptors"), "the judge gives refused"),
            "proof repeats": (dup_proof, "more than one proof"),
            "proof file elsewhere": (lambda d: d["owned_context"]["metadata-proofs"][0].__setitem__(
                "file", "../finite-profile.schema.json"), "differ from its metadata-proofs record"),
        }
        for name, (mutate, needle) in bad.items():
            with self.subTest(name):
                shutil.rmtree(self.skel)
                shutil.copytree(ROOT / self.SKELETONS, self.skel)
                errors = self.errors(mutate)
                self.assertTrue(any(needle in e for e in errors), errors)

    def test_body_witnesses(self):
        errors, stats = check_forms.check_deletion_body_witnesses(self.wpath)
        self.assertEqual(errors, [])
        self.assertEqual(stats["deletion_body_witnesses"], 6)
        good = json.loads(self.wpath.read_text(encoding="utf-8"))
        bad = {
            "limit+1 passes": (lambda d: d["witnesses"]["body_limit1"].__setitem__("within_body_limit", True), "within"),
            "limit refuses": (lambda d: d["witnesses"]["body_limit0"].__setitem__("within_body_limit", False), "within"),
            "no limit-1": (lambda d: d["witnesses"].pop("body_limit-1"), "1048575 bytes"),
            "LF not +1": (lambda d: d["witnesses"]["same_JSON_plus_LF"].__setitem__("entity_bytes", 1048578), "LF witness"),
        }
        for name, (mutate, needle) in bad.items():
            with self.subTest(name):
                d = copy.deepcopy(good)
                mutate(d)
                self.wpath.write_text(json.dumps(d), encoding="utf-8")
                errors = check_forms.check_deletion_body_witnesses(self.wpath)[0]
                self.assertTrue(any(needle in e for e in errors), errors)
class CyrillicJudge(unittest.TestCase):
    """ADR-0121 (8): source mutations, the two exceptions and monotone debt."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.debt = self.root / "debt.tsv"
        self.debt.write_text(check_cyrillic.HEADER + "\n", encoding="utf-8")

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
        return path

    def markers(self):
        for name in check_cyrillic.EXPORT_MARKERS:
            self.put(name, "0123456789abcdef0123456789abcdef01234567\n")

    def judge(self, **kwargs):
        return check_cyrillic.check(self.root, self.debt, **kwargs)

    def registry(self, *rows):
        self.debt.write_text(check_cyrillic.HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")

    def test_requested_source_mutants(self):
        for name in ("Platform/01-store/journal/corrections.tsv", "Platform/02-installer/data/test.shell.html",
                     "Platform/01-store/code/door.go", "Platform/explanations/notes.md",
                     "Platform/.hidden/source.txt"):
            with self.subTest(name=name):
                path = self.put(name, "// Cyrillic: Ж\n")
                self.assertTrue(any(name in e and "new/increased" in e for e in self.judge()[0]))
                path.unlink()

    def test_additional_course_export_sources_are_checked(self):
        for name in ("Platform/07-console-module/CONSOLE-MODULE.md", "Platform/common/NORMATIVE-TERMS.md",
                     "Platform/02-installer/acceptance/1/spec_verdicts/spec_verdicts.tsv",
                     "Platform/common/data/testsub/new/case.json"):
            with self.subTest(name=name):
                path = self.put(name, "Ж")
                self.assertTrue(any(name in e and "new/increased" in e for e in self.judge()[0]))
                path.unlink()

    def test_course_readme_is_not_the_export_readme(self):
        self.put("README.md", "Course notes: Ж")
        self.assertEqual(self.judge()[0], [])
        self.markers()
        errors, stats = self.judge()
        self.assertTrue(any("README.md: Cyrillic letters" in e for e in errors))
        self.assertEqual(stats["cyrillic_export"], 1)

    def test_export_checks_all_homes_and_hidden_files_not_only_known_roots(self):
        self.markers()
        for name in ("README.md", ".gitignore", "tools/new-contract.txt", "Source/new/input.tsv",
                     "changes/old/tasks.md", "new-published-home/schema.yaml"):
            with self.subTest(name=name):
                path = self.put(name, "Ж")
                self.assertTrue(any(name in e and "new/increased" in e for e in self.judge()[0]))
                path.unlink()

    def test_export_only_v11_is_deferred_and_canonical_console_bytes_are_checked(self):
        self.markers()
        # 3e4bcdbc8 removed the V11 deferral: only the 31 exact carriers are exempt, any other V11 file is checked.
        # A VMS/11-backend tree must hold every exact carrier (a deleted one fails); put them.
        self.exact_carrier()
        self.assertEqual(self.judge()[0], [])
        extra = self.put("VMS/11-backend/spec/norms.md", "Ж")
        self.assertTrue(any("VMS/11-backend/spec/norms.md" in e and "new/increased" in e for e in self.judge()[0]))
        extra.unlink()
        for name in ("VMS/01-cam/spec/norms.md", "VMS/new-house/.hidden/model.data", "VMS/11-backend-extra/source.txt",
                     "Platform/07-console-module/module/console.js", "Platform/07-console-module/module/console.css",
                     "Platform/07-console-module/module/console.html", "Source/w2cplatform/console.js", "elsewhere/console.js"):
            with self.subTest(name=name):
                path = self.put(name, "Ж")
                self.assertTrue(self.judge()[0])
                path.unlink()
        # The exception names published files; it must not exempt whole directories.
        self.put("Platform/07-console-module/module/console.js/other.txt", "Ж")
        self.assertTrue(self.judge()[0])

    def test_export_exceptions_preserve_mirrors_and_only_localization_ru(self):
        self.markers()
        self.put("Platform/01-store/ru/spec/norms.md", "Ж")
        self.put(check_cyrillic.LOCALIZATION, "key\ten\tru\na\tEnglish\tЖ\n")
        self.assertEqual(self.judge()[0], [])
        old = self.put("Platform/06-console/data/localization.tsv", "key\ten\tru\na\tEnglish\tЖ\n")
        self.assertTrue(any("Platform/06-console/data/localization.tsv" in e and "new/increased" in e
                            for e in self.judge()[0]))
        old.unlink()
        self.put(check_cyrillic.LOCALIZATION, "key\ten\tru\na\tЖ\tЖ\n")
        self.assertTrue(self.judge()[0])

    def test_explicit_export_without_marker_and_read_only_cli(self):
        self.put("new-published-home/data.txt", "Ж")
        self.assertEqual(self.judge()[0], [])
        self.assertTrue(self.judge(export=True)[0])
        before = self.debt.read_bytes()
        result = subprocess.run([sys.executable, "-B", str(Path(check_cyrillic.__file__)),
                                 "--root", str(self.root), "--debt", str(self.debt), "--export"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("new-published-home/data.txt", result.stdout)
        self.assertEqual(self.debt.read_bytes(), before)

    def test_deleted_tracked_export_marker_does_not_narrow_scope(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        self.markers()
        self.put("README.md", "Ж")
        subprocess.run(["git", "-C", str(self.root), "add", *check_cyrillic.EXPORT_MARKERS, "README.md"], check=True, capture_output=True)
        for name in check_cyrillic.EXPORT_MARKERS:
            (self.root / name).unlink()
        errors, stats = self.judge()
        self.assertTrue(any("README.md" in e for e in errors))
        self.assertEqual(sum("cannot read export marker" in e for e in errors), 2)
        self.assertEqual(stats["cyrillic_export"], 1)

    def test_new_scope_shrink_cannot_add_debt_or_lower_old_debt_at_the_same_time(self):
        self.put("Platform/01-store/old.md", "English")
        self.registry("debt\tPlatform/01-store/old.md\t1")
        self.put("Platform/07-console-module/CONSOLE-MODULE.md", "Ж")
        before = self.debt.read_bytes()
        self.assertTrue(self.judge(shrink=True)[0])
        self.assertEqual(self.debt.read_bytes(), before)

    def test_nested_export_markers_are_exact_equal_full_pins(self):
        self.markers()
        self.assertEqual(self.judge()[0], [])
        first, second = [self.root / name for name in check_cyrillic.EXPORT_MARKERS]
        good = first.read_bytes()
        for path in (first, second):
            for bad in (b"0123456789\n", good[:-1], good + b"\n", good.replace(b"\n", b"\r\n"),
                        good.upper(), b"g" * 40 + b"\n", b" " + good):
                with self.subTest(path=path, bad=bad):
                    path.write_bytes(bad)
                    self.assertTrue(any("expected full 40" in e for e in self.judge()[0]))
            path.write_bytes(good)
            path.unlink()
            self.assertTrue(any("cannot read export marker" in e for e in self.judge()[0]))
            path.write_bytes(good)
        second.write_bytes(b"f" * 40 + b"\n")
        self.assertTrue(any("COURSE_COMMIT differ" in e for e in self.judge()[0]))
        second.write_bytes(good)
        self.put("COURSE_COMMIT", good)
        self.assertTrue(any("root marker is forbidden" in e for e in self.judge()[0]))

    def test_export_missing_both_markers_and_symlinks_fail_explicitly(self):
        self.assertTrue(any("cannot read export marker" in e for e in self.judge(export=True)[0]))
        self.markers()
        path = self.root / check_cyrillic.EXPORT_MARKERS[0]
        before = path.read_bytes()
        path.unlink()
        target = self.put("pin.txt", before)
        path.symlink_to(target)
        self.assertTrue(any("without symlinks" in e for e in self.judge()[0]))

    def test_legacy_root_marker_cannot_select_an_accepted_layout(self):
        self.put("COURSE_COMMIT", "0123456789abcdef0123456789abcdef01234567\n")
        errors, stats = self.judge()
        self.assertEqual(stats["cyrillic_export"], 1)
        self.assertTrue(any("root marker is forbidden" in e for e in errors))
        self.assertEqual(sum("cannot read export marker" in e for e in errors), 2)

    def test_frozen_source_and_old_root_notes_are_not_canonical_scope(self):
        for name in ("Source/tests/testdata/testsub.subsystem.yaml", "Source/w2cplatform/console.js",
                     "NORMATIVE-TERMS.md", "CONSOLE-MODULE.md"):
            self.put(name, "Ж")
        self.assertEqual(self.judge()[0], [])

    def test_only_declared_mirror_homes_are_exempt(self):
        for name in ("Platform/ru/README.md", "Platform/common/ru/wire.tsv", "Platform/01-store/ru/spec/norms.md"):
            self.put(name, "Русский перевод")
        self.assertEqual(self.judge()[0], [])
        for name in ("Platform/01-store/code/ru/code.go", "Platform/explanations/ru/note.md"):
            with self.subTest(name=name):
                path = self.put(name, "Ж")
                self.assertTrue(self.judge()[0])
                path.unlink()

    def test_localization_ru_column_only_by_header(self):
        for header, row in (("key\ten\tru", "hello\tHello\tПривет"),
                            ("# ru\tkey\ten", "Привет\thello\tHello")):
            self.put(check_cyrillic.LOCALIZATION, header + "\n" + row + "\n")
            self.assertEqual(self.judge()[0], [])
        for row in ("Ж\tHello\tПривет", "hello\tЖ\tПривет"):
            self.put(check_cyrillic.LOCALIZATION, "key\ten\tru\n" + row + "\n")
            self.assertTrue(self.judge()[0])

    def test_localization_comments_headers_and_other_paths_are_not_exempt(self):
        for text in ("# Ж\nkey\ten\tru\na\tb\tПривет\n", "key\ten\tru\tЖ\na\tb\tПривет\td\n"):
            self.put(check_cyrillic.LOCALIZATION, text)
            self.assertTrue(self.judge()[0])
        (self.root / check_cyrillic.LOCALIZATION).unlink()
        self.put("Platform/01-store/data/localization.tsv", "key\ten\tru\na\tb\tПривет\n")
        self.assertTrue(self.judge()[0])

    def test_localization_malformed_shape_fails_without_letters(self):
        for text in ("", "key\ten\n", "key\ten\tru\tru\n", "key\ten\tru\na\tb\n",
                     "# comment\na\tb\tc\n"):
            with self.subTest(text=text):
                self.put(check_cyrillic.LOCALIZATION, text)
                self.assertTrue(self.judge()[0])

    def test_unicode_letters_including_new_and_supplementary_blocks(self):
        self.assertEqual(sum(high - low + 1 for low, high in check_cyrillic.LETTER_RANGES), 449)
        letters = "Ж\u0481\u048a\u052f\u1c80\u1c89\u1c8a\u1d2b\u1d78\ua640\ua67f\ua69d\U0001e030\U0001e06d"
        self.put("Platform/01-store/spec/norms.md", letters)
        counts, errors, _ = check_cyrillic.scan(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(sum(counts.values()), len(letters))
        self.put("Platform/01-store/spec/norms.md", "Latin\u0482\u0483\u2de0é漢字")
        self.assertEqual(self.judge()[0], [])             # Cyrillic signs/marks are not letters

    def test_non_utf8_does_not_hide_valid_cyrillic(self):
        self.put("Platform/01-store/data.bin", b"\xff\x00" + "Ж".encode())
        errors, stats = self.judge()
        self.assertTrue(errors)
        self.assertEqual(stats["cyrillic_non_utf8"], 1)

    def test_existing_debt_is_exact_per_file(self):
        self.put("Platform/01-store/a.md", "ЖЖ")
        self.registry("debt\tPlatform/01-store/a.md\t2")
        before = self.debt.read_bytes()
        self.assertEqual(self.judge()[0], [])
        self.assertEqual(self.debt.read_bytes(), before)    # default check is read-only
        self.put("Platform/01-store/b.md", "Ж")
        self.assertTrue(self.judge()[0])
        (self.root / "Platform/01-store/b.md").unlink()
        self.put("Platform/01-store/a.md", "ЖЖЖ")
        self.assertTrue(self.judge()[0])

    def test_shrink_lowers_and_removes_deleted_debt(self):
        self.put("Platform/01-store/a.md", "Ж")
        self.registry("debt\tPlatform/01-store/a.md\t2", "debt\tPlatform/01-store/deleted.md\t3")
        self.assertEqual(len(self.judge()[0]), 2)
        self.assertEqual(self.judge(shrink=True)[0], [])
        self.assertEqual(check_cyrillic.load_debt(self.debt)[:2], ({"Platform/01-store/a.md": 1}, set()))
        self.assertEqual(self.judge()[0], [])

    def test_shrink_refuses_new_or_increased_debt_and_preserves_bytes(self):
        self.put("Platform/01-store/a.md", "ЖЖ")
        for row in ("debt\tPlatform/01-store/a.md\t1", "debt\tPlatform/01-store/other.md\t10"):
            self.registry(row)
            before = self.debt.read_bytes()
            self.assertTrue(self.judge(shrink=True)[0])
            self.assertEqual(self.debt.read_bytes(), before)

    def test_missing_registry_cannot_be_bootstrapped_by_shrink(self):
        self.debt.unlink()
        self.assertTrue(self.judge(shrink=True)[0])
        self.assertFalse(self.debt.exists())

    def test_ready_clean_unit_stays_ready_and_cannot_acquire_debt(self):
        self.put("Platform/01-store/a.md", "English")
        self.assertEqual(self.judge(declare_ready=["Platform/01-store"])[0], [])
        self.assertEqual(check_cyrillic.load_debt(self.debt)[1], {"Platform/01-store"})
        self.assertEqual(self.judge(shrink=True)[0], [])
        before = self.debt.read_bytes()
        self.put("Platform/01-store/a.md", "Ж")
        self.assertTrue(self.judge(shrink=True)[0])
        self.assertEqual(self.debt.read_bytes(), before)

    def test_ready_dirty_or_missing_or_excluded_unit_refused(self):
        self.put("Platform/01-store/a.md", "Ж")
        self.registry("debt\tPlatform/01-store/a.md\t1")
        for unit in ("Platform/01-store", "Platform/missing", "Platform/01-store/a.md",
                     "../Platform", "Platform/ru", "VMS/01-db"):
            before = self.debt.read_bytes()
            self.assertTrue(self.judge(declare_ready=[unit])[0], unit)
            self.assertEqual(self.debt.read_bytes(), before)

    def test_registry_malformed_duplicate_and_ready_debt_conflict(self):
        for row in ("debt\t../escape\t1", "debt\tPlatform/a\t0", "debt\tPlatform/a\t١",
                    "debt\tPlatform/a\t-1", "debt\tPlatform/a\t1\nready\tPlatform/a\t-",
                    "debt\tPlatform/a\t1\ndebt\tPlatform/a\t2", "ready\tPlatform\t-\ndebt\tPlatform/a\t1",
                    "debt\tPlatform/ru/a\t1", "debt\tPlatform//a\t1", "debt\tPlatform/a\\b\t1",
                    "anything\tPlatform/a\t1"):
            self.registry(row)
            self.assertTrue(check_cyrillic.load_debt(self.debt)[2], row)
        self.debt.write_text("wrong header\n")
        self.assertTrue(self.judge()[0])

    def test_checkout_uses_tracked_including_staged_hidden_source(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        self.put("Platform/untracked.md", "Ж")
        self.assertEqual(self.judge()[0], [])
        subprocess.run(["git", "-C", str(self.root), "add", "Platform"], check=True, capture_output=True)
        self.assertTrue(self.judge()[0])
        self.put("Platform/untracked.md", "English")
        self.put("Platform/.hidden.go", "// Ж")
        self.assertEqual(self.judge()[0], [])
        subprocess.run(["git", "-C", str(self.root), "add", "Platform"], check=True, capture_output=True)
        self.assertTrue(self.judge()[0])

    def test_frozen_normgen_is_outside_the_course_scope(self):
        """ADR-0125 доп. (14) п. 3: tools/normgen is frozen; no Cyrillic judgement, debt or readiness there."""
        self.assertEqual(check_cyrillic.FROZEN_SOURCE, ("tools/normgen",))
        self.assertFalse(any(check_cyrillic.under(home, check_cyrillic.FROZEN_SOURCE) for home in check_cyrillic.SCOPES))
        for name in ("tools/normgen/runtime/door.go", "tools/normgen/ru/code.go", "tools/normgen/.hidden.go"):
            self.put(name, "// Ж")
        self.assertEqual(self.judge()[0], [])
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.root), "add", "tools"], check=True, capture_output=True)
        errors, stats = self.judge()
        self.assertEqual(errors, [])
        self.assertEqual(stats["cyrillic_scanned_files"], 0)
        self.assertNotIn("tools/normgen/runtime/door.go", check_cyrillic.scan(self.root)[0])
        with self.assertRaises(ValueError):
            check_cyrillic.check(self.root, self.debt, source_scopes=("tools/normgen",))
        self.registry("debt\ttools/normgen/runtime/door.go\t1")
        self.assertTrue(any("excluded" in e for e in self.judge()[0]))
        self.registry("ready\ttools/normgen\t-")
        self.assertTrue(self.judge()[0])

    def export_git(self):
        self.markers()
        self.put(".gitignore", "ignored/\n__pycache__/\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.root), "add", *check_cyrillic.EXPORT_MARKERS,
                        ".gitignore"], check=True, capture_output=True)

    def test_git_export_includes_untracked_ignored_hidden_and_new_homes(self):
        self.export_git()
        self.assertEqual(self.judge()[0], [])
        for name in ("Platform/.new-house/untracked.md", ".new-house/model.data", ".hidden",
                     "Platform/ignored/model.bin", "ignored/root.data",
                     "Platform/__pycache__/model.data", "__pycache__/model.data",
                     "Platform/.git/model.data", "Platform/.new-house/.git"):
            with self.subTest(name=name):
                path = self.put(name, "Ж")
                for mode in (None, True):
                    errors, stats = self.judge(export=mode)
                    self.assertTrue(any(name + ": Cyrillic letters 1" in e for e in errors), errors)
                    self.assertEqual(stats["cyrillic_export"], 1)
                path.unlink()

    def test_git_and_git_free_export_have_identical_disk_inventory(self):
        self.export_git()
        self.put("Platform/.new-house/untracked.md", b"\xff" + "Ж".encode())
        self.put("ignored/model.data", "Ж")
        with tempfile.TemporaryDirectory() as folder:
            copy_root = Path(folder) / "export"
            shutil.copytree(self.root, copy_root, ignore=shutil.ignore_patterns(".git"))
            for mode in (None, True):
                git_result = self.judge(export=mode)
                disk_result = check_cyrillic.check(copy_root, self.debt, export=mode)
                self.assertTrue(any("Platform/.new-house/untracked.md" in e for e in git_result[0]))
                self.assertEqual(git_result, disk_result)
                self.assertEqual(git_result[1]["cyrillic_non_utf8"], 1)

    def test_git_export_cli_and_failed_shrink_leave_debt_bytes_unchanged(self):
        self.export_git()
        self.put("Platform/old.md", "English")
        self.registry("debt\tPlatform/old.md\t1")
        name = "Platform/.new-house/untracked.md"
        self.put(name, "Ж")
        before = self.debt.read_bytes()
        for flags in ([], ["--export"]):
            for shrink in ([], ["--shrink"]):
                with self.subTest(flags=flags + shrink):
                    self.debt.write_bytes(before)
                    result = subprocess.run([sys.executable, "-B", str(Path(check_cyrillic.__file__)),
                                             "--root", str(self.root), "--debt", str(self.debt),
                                             *flags, *shrink], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn(name + ": Cyrillic letters 1", result.stdout)
                    self.assertEqual(self.debt.read_bytes(), before)

    def test_git_export_keeps_only_declared_language_exceptions(self):
        self.exact_carrier()
        self.export_git()
        self.put("VMS/11-backend/notes.md", "Ж")
        self.assertTrue(any("VMS/11-backend/notes.md" in e for e in self.judge()[0]))
        self.put("VMS/11-backend/notes.md", "English")
        self.put("Platform/01-store/ru/new.md", "Ж")
        self.put(check_cyrillic.LOCALIZATION, "key\ten\tru\na\tEnglish\tЖ\n")
        self.assertEqual(self.judge()[0], [])
        self.put(check_cyrillic.LOCALIZATION, "key\ten\tru\na\tЖ\tЖ\n")
        self.assertTrue(any(check_cyrillic.LOCALIZATION in e for e in self.judge()[0]))

    def test_vms_source_checks_new_hidden_homes_and_never_adds_a_locale_exception(self):
        for name in ("VMS/01-cam/.hidden.txt", "VMS/12-psim/journal/corrections.tsv",
                     "VMS/common/localization.tsv", "VMS/common/id-map.tsv.extra", "VMS/.new/input.bin"):
            with self.subTest(name=name):
                path = self.put(name, b"\xff" + "Ж".encode())
                errors, stats = self.judge()
                self.assertTrue(any(name in e and "new/increased" in e for e in errors), errors)
                self.assertEqual(stats["cyrillic_non_utf8"], 1)
                path.unlink()

    def test_vms_human_mirrors_are_narrow(self):
        for name in ("VMS/ru/README.md", "VMS/common/ru/README.md", "VMS/01-cam/ru/spec/norms.md"):
            self.put(name, "Ж")
        self.assertEqual(self.judge()[0], [])
        for name in ("VMS/new/ru/notes.md", "VMS/01-cam/data/ru/value.tsv", "VMS/common/ru-extra/input.md"):
            path = self.put(name, "Ж")
            self.assertTrue(any(name in e for e in self.judge()[0]))
            path.unlink()

    def exact_carrier(self):
        import hashlib
        name = "VMS/11-backend/consolem.openapi.json"
        from vms_platform_pin import _git
        source = "c8eafc05626112db4c2003b416f762055deaef65"
        # Two carriers re-approved by the VMS Source owner on 2026-11-08 (4e01dde0d); their bytes are in e42018797.
        reapproved = {"VMS/11-backend/README.md": "e42018797", "VMS/11-backend/spec/11.7-backend.norms.md": "e42018797"}
        root = Path(__file__).resolve().parents[3]
        for carrier, sha in check_cyrillic.EXACT_SOURCE_FILES.items():
            blob = _git(root, "show", reapproved.get(carrier, source) + ":" + carrier)
            self.assertEqual(hashlib.sha256(blob if isinstance(blob, bytes) else blob.encode()).hexdigest(), sha, carrier)
            self.put(carrier, blob)
        data = (self.root / name).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         "200d203d4197776892e66a32126998bc8cf0b79a9986ef7ac144c6af230f7124")
        return self.put(name, data), data

    def test_only_exact_carrier_bytes_are_allowed_without_new_debt(self):
        path, data = self.exact_carrier()
        for mode in (False, True):
            if mode:
                self.markers()
            path.write_bytes(data)
            self.assertEqual(self.judge(export=mode)[0], [])
            for changed in (data + b"\n", b"X" + data[1:], b"English", data + "Ж".encode()):
                with self.subTest(mode=mode, changed=changed[-12:]):
                    self.assertNotEqual(changed, data)
                    path.write_bytes(changed)
                    before = self.debt.read_bytes()
                    for shrink in (False, True):
                        errors, _ = self.judge(export=mode, shrink=shrink)
                        self.assertTrue(any("exact source carrier SHA256 mismatch" in e for e in errors), errors)
                        self.assertEqual(self.debt.read_bytes(), before)

    def test_exact_carrier_symlink_and_fifo_refuse_without_reading(self):
        path, data = self.exact_carrier()
        target = self.put("outside-map.tsv", data)
        path.unlink()
        path.symlink_to(target)
        self.assertTrue(any("regular file without symlinks" in e for e in self.judge()[0]))
        path.unlink()
        os.mkfifo(path)
        self.assertTrue(any("regular file without symlinks" in e for e in self.judge()[0]))

    def test_exact_carrier_is_not_a_registry_budget_or_global_ready_permission(self):
        self.exact_carrier()
        for row in ("debt\tVMS/11-backend/consolem.openapi.json\t100000", "ready\tVMS/11-backend\t-"):
            self.registry(row)
            self.assertTrue(self.judge()[0])
        self.debt.write_text(check_cyrillic.HEADER + "\n")
        for unit in ("VMS", "VMS/common", "VMS/11-backend"):
            before = self.debt.read_bytes()
            self.assertTrue(self.judge(declare_ready=[unit])[0], unit)
            self.assertEqual(self.debt.read_bytes(), before)
        self.put("VMS/01-cam/README.md", "English")
        self.assertEqual(self.judge(declare_ready=["VMS/01-cam"])[0], [])
        self.assertEqual(check_cyrillic.load_debt(self.debt)[1], {"VMS/01-cam"})

    def test_vms_git_source_staged_hidden_file_and_deleted_exact_carrier(self):
        self.exact_carrier()
        self.export_git()
        self.put("VMS/01-cam/.new/notes.txt", "Ж")
        self.assertEqual(self.judge(export=False)[0], [])
        subprocess.run(["git", "-C", str(self.root), "add", "VMS"], check=True, capture_output=True)
        self.assertTrue(any("VMS/01-cam/.new/notes.txt" in e for e in self.judge(export=False)[0]))
        (self.root / "VMS/01-cam/.new/notes.txt").unlink()
        (self.root / "VMS/11-backend/consolem.openapi.json").unlink()
        self.assertTrue(any("cannot read exact source carrier" in e for e in self.judge(export=False)[0]))

    def test_vms_git_and_git_free_export_cover_untracked_and_ignored_files(self):
        self.export_git()
        self.put("VMS/.hidden/new.bin", "Ж")
        self.put("VMS/01-cam/__pycache__/model.data", "Ж")
        with tempfile.TemporaryDirectory() as folder:
            copy_root = Path(folder) / "export"
            shutil.copytree(self.root, copy_root, ignore=shutil.ignore_patterns(".git"))
            for mode in (None, True):
                result = self.judge(export=mode)
                self.assertEqual(result, check_cyrillic.check(copy_root, self.debt, export=mode))
                self.assertTrue(any("VMS/.hidden/new.bin" in e for e in result[0]))
                self.assertTrue(any("VMS/01-cam/__pycache__/model.data" in e for e in result[0]))

    def test_export_worktree_git_file_is_metadata_but_untracked_data_is_not(self):
        # A real worktree .git file contains Cyrillic in its local gitdir path.
        donor = self.root / "donor-Ж"
        donor.mkdir()
        for name in check_cyrillic.EXPORT_MARKERS:
            path = donor / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("0" * 40 + "\n")
        subprocess.run(["git", "init", "-q", str(donor)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(donor), "add", *check_cyrillic.EXPORT_MARKERS],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(donor), "-c", "user.name=owned fixture",
                        "-c", "user.email=fixture@invalid", "commit", "-qm", "owned markers"],
                       check=True, capture_output=True)
        export_root = self.root / "export"
        subprocess.run(["git", "-C", str(donor), "worktree", "add", "--detach", str(export_root)],
                       check=True, capture_output=True)
        self.assertTrue((export_root / ".git").is_file())
        self.assertIn("Ж", (export_root / ".git").read_text())
        for mode in (None, True):
            self.assertEqual(check_cyrillic.check(export_root, self.debt, export=mode)[0], [])
        path = export_root / "untracked.data"
        path.write_text("Ж")
        for mode in (None, True):
            errors, _ = check_cyrillic.check(export_root, self.debt, export=mode)
            self.assertTrue(any("untracked.data: Cyrillic letters 1" in e for e in errors), errors)
            self.assertFalse(any(".git:" in e for e in errors), errors)

    def test_git_export_untracked_symlinks_and_fifo_still_fail(self):
        self.export_git()
        target = self.put("ignored/target.data", "English")
        path = self.root / "Platform/alias"
        for directory in (False, True):
            with self.subTest(directory=directory):
                path.symlink_to(target.parent if directory else target, target_is_directory=directory)
                try:
                    self.assertTrue(any("symlink" in e for e in self.judge()[0]))
                finally:
                    path.unlink()
        os.mkfifo(path)
        self.assertTrue(any("not a regular file" in e for e in self.judge()[0]))

    def test_source_git_untracked_and_ignored_files_remain_outside_inventory(self):
        self.export_git()
        self.put("Platform/untracked.md", "Ж")
        self.put("Platform/ignored/model.data", "Ж")
        self.put("Platform/__pycache__/model.data", "Ж")
        self.assertEqual(self.judge(export=False)[0], [])
        subprocess.run(["git", "-C", str(self.root), "add", "Platform/untracked.md"],
                       check=True, capture_output=True)
        self.assertTrue(any("Platform/untracked.md" in e for e in self.judge(export=False)[0]))

    def test_git_free_export_scans_hidden_but_skips_metadata(self):
        self.put("Platform/__pycache__/cache.pyc", "Ж")
        self.put("Platform/.git/config", "Ж")
        self.assertEqual(self.judge()[0], [])
        self.put("Platform/.source/x.txt", "Ж")
        self.assertTrue(self.judge()[0])

    def test_source_symlinks_fail_without_reading_target(self):
        target = self.put("outside.txt", "secret Ж")
        (self.root / "Platform").mkdir()
        (self.root / "Platform/link.md").symlink_to(target)
        self.assertTrue(self.judge()[0])

    def test_special_file_and_missing_root_fail_without_hanging(self):
        path = self.root / "Platform/data.pipe"
        path.parent.mkdir()
        os.mkfifo(path)
        self.assertTrue(any("not a regular file" in e for e in self.judge()[0]))
        self.assertTrue(check_cyrillic.check(self.root / "missing", self.debt)[0])

    def test_invalid_localization_also_blocks_shrink(self):
        self.put(check_cyrillic.LOCALIZATION, "key\ten\tru\na\tb\n")
        before = self.debt.read_bytes()
        self.assertTrue(self.judge(shrink=True)[0])
        self.assertEqual(self.debt.read_bytes(), before)

    def test_cli_default_is_read_only_and_fails_mutant(self):
        self.put("Platform/01-store/journal/a.tsv", "Ж")
        before = self.debt.read_bytes()
        result = subprocess.run([sys.executable, "-B", str(Path(check_cyrillic.__file__)),
                                 "--root", str(self.root), "--debt", str(self.debt)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("new/increased debt", result.stdout)
        self.assertEqual(self.debt.read_bytes(), before)



class RefusalAliasControls(unittest.TestCase):
    """Independent raw typed Source fixtures; only the affected skills checker runs."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.lesson = self.root / "Platform/10-domain-console"
        (self.lesson / "spec").mkdir(parents=True)
        (self.lesson / "forms").mkdir()
        self.api = self.lesson / "spec/10-domain-console.api.openapi.yaml"
        self.form = self.lesson / "forms/refusals.tsv"
        (self.lesson / "spec/10-domain-console.norms.md").write_text(
            "## N4 Refusals\n\nThe catalogue is forms/refusals.tsv.\n")
        self.target = {"type": "object", "required": ["error"], "additionalProperties": False,
                       "properties": {"error": {"type": "string"}, "detail": {"type": "string"}}}
        self.doc = {"openapi": "3.1.0", "components": {"schemas": {
            "Alias": {"$ref": "#/components/schemas/Target"}, "Target": copy.deepcopy(self.target)}}}
        self.write_doc(self.api, self.doc)
        self.write_form()
        self.assertEqual(self.check(), [])  # Complete normal before each independent negative.

    def write_doc(self, path, doc):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc))  # JSON is an unambiguous YAML subset.

    def write_form(self, fields="error", kind="-", schema="Alias"):
        row = ["10", "1", "alias_refusal", "http", "502", kind, fields, "-", "-", "P/10 N4",
               "refused", schema, "cause", "502 refused", "diagnostic", "client"]
        self.form.write_text("\t".join(check_forms.REF_COLUMNS + check_forms.REF_EXTRA) + "\n" + "\t".join(row) + "\n")

    def check(self):
        return check_forms.check_refusals(self.form)[0]

    def assert_error(self, text):
        errors = self.check()
        self.assertTrue(any(text in error for error in errors), errors)

    def test_positive_local_alias_annotations_and_raw_public_mapping(self):
        alias = self.doc["components"]["schemas"]["Alias"]
        alias.update(title="named alias", description="retained annotation",
                     examples=[{"$ref": "instance data, not a schema reference"}])
        self.write_doc(self.api, self.doc)
        self.assertEqual(self.check(), [])
        schemas = check_forms.openapi_schemas(self.lesson)
        self.assertIsInstance(schemas, dict)
        self.assertEqual(schemas, self.doc["components"]["schemas"])
        self.assertEqual(schemas["Alias"], alias)
        self.assertEqual(schemas.origins["Alias"], self.api)

    def test_positive_each_external_hop_uses_its_declaration_base(self):
        middle = self.root / "Platform/08-domain/spec/dotted.alias.api.openapi.yaml"
        final = self.root / "Platform/06-console/spec/target.api.openapi.yaml"
        self.doc["components"]["schemas"]["Alias"] = {
            "$ref": "../../08-domain/spec/dotted.alias.api.openapi.yaml#/components/schemas/Middle"}
        self.write_doc(self.api, self.doc)
        self.write_doc(middle, {"components": {"schemas": {"Middle": {
            "$ref": "../../06-console/spec/target.api.openapi.yaml#/components/schemas/Target"}}}})
        self.write_doc(final, {"components": {"schemas": {"Target": self.target}}})
        self.assertEqual(self.check(), [])
        final.unlink()
        self.assert_error("target.api.openapi.yaml")

    def test_missing_resource_missing_target_and_invalid_reference_uri(self):
        for ref, diagnostic in (
                ("../../06-console/spec/missing.api.openapi.yaml#/components/schemas/Target", "missing.api.openapi.yaml"),
                ("#/components/schemas/Absent", "unresolved schema reference"),
                ("https://example.invalid/a#/components/schemas/X", "nonlocal"),
                ("//example.invalid/a#/components/schemas/X", "nonlocal"),
                ("/tmp/a.openapi.yaml#/components/schemas/X", "nonlocal"),
                ("a.openapi.yaml?query#/components/schemas/X", "nonlocal"),
                ("%XX.openapi.yaml#/components/schemas/X", "invalid schema reference"),
                ("#/components/schemas/Target~2", "pointer escape"),
                ("#anchor", "JSON pointer"), (True, "malformed full response schema")):
            with self.subTest(ref=ref):
                self.doc["components"]["schemas"]["Alias"] = {"$ref": ref}
                self.write_doc(self.api, self.doc)
                self.assert_error(diagnostic)

    def test_wrong_resource_owner_and_physical_owner_are_errors(self):
        target = self.root / "Platform/11-later/spec/later.api.openapi.yaml"
        self.write_doc(target, {"components": {"schemas": {"Target": self.target}}})
        self.doc["components"]["schemas"]["Alias"] = {
            "$ref": "../../11-later/spec/later.api.openapi.yaml#/components/schemas/Target"}
        self.write_doc(self.api, self.doc)
        self.assert_error("earlier owner")
        declared = self.root / "Platform/06-console/spec/target.api.openapi.yaml"
        declared.parent.mkdir(parents=True)
        declared.symlink_to(target)
        self.doc["components"]["schemas"]["Alias"]["$ref"] = "../../06-console/spec/target.api.openapi.yaml#/components/schemas/Target"
        self.write_doc(self.api, self.doc)
        self.assert_error("physical owner")
        self.doc["components"]["schemas"]["Alias"]["$ref"] = "10-domain-console.api.openapi.yaml#/components/schemas/Target"
        self.write_doc(self.api, self.doc)
        self.assert_error("same-resource")

    def test_wrong_resource_extension_and_wrong_target_position(self):
        raw = self.lesson / "spec/target.txt"
        self.write_doc(raw, {"components": {"schemas": {"Target": self.target}}})
        for ref, diagnostic in (("target.txt#/components/schemas/Target", "unsupported schema resource"),
                ("#/components/schemas/Target/examples/0", "schema position"),
                ("#/components/schemas/Target/properties", "schema position"),
                ("#/components/schemas/Target/description", "schema position"),
                ("#/paths/~1bad", "named Schema Object")):
            with self.subTest(ref=ref):
                self.doc["components"]["schemas"]["Alias"] = {"$ref": ref}
                self.write_doc(self.api, self.doc)
                self.assert_error(diagnostic)

    def test_allof_and_ref_siblings_preserve_roles_constraints_and_annotations(self):
        self.doc["components"]["schemas"]["Alias"] = {
            "$ref": "#/components/schemas/Target", "description": "not discarded", "minProperties": 1,
            "allOf": [{"properties": {"trace": {"type": "string"}}, "required": ["trace"]}]}
        self.write_doc(self.api, self.doc)
        self.write_form("error,trace,detail?")
        self.assertEqual(self.check(), [])
        self.write_form("error,trace?,detail?")
        self.assert_error("required properties ['trace']")
        self.doc["components"]["schemas"]["Alias"]["minProperties"] = -1
        self.write_doc(self.api, self.doc)
        self.assert_error("malformed full response schema")

    def test_explicit_fields_are_one_way_optional_not_required_and_all_exist(self):
        for fields, ok in (("error,detail?",True),("error,detail",True),("error",True),
                           ("error?",False),("detail",False),("error,unknown?",False)):
            with self.subTest(fields=fields):
                self.write_form(fields)
                self.assertEqual(not self.check(),ok)

    def test_dash_skips_projection_but_validates_full_schema_and_reference_closure(self):
        self.write_form("-")
        self.assertEqual(self.check(), [])
        self.doc["components"]["schemas"]["Target"]["properties"]["detail"]["type"] = "not-a-type"
        self.write_doc(self.api,self.doc)
        self.assert_error("malformed full response schema")
        self.doc["components"]["schemas"]["Target"] = dict(self.target, properties={
            "error": {"type":"string"}, "detail":{"$ref":"#/components/schemas/Absent"}})
        self.write_doc(self.api,self.doc)
        self.assert_error("unresolved schema reference")

    def test_named_kind_rows_always_validate_the_named_response_schema(self):
        self.doc["components"]["schemas"]["Fault"] = {"properties":{"kind":{"const":"badrequest"}}}
        self.write_doc(self.api,self.doc)
        self.write_form("-",kind="badrequest")
        self.assertEqual(self.check(), [])
        self.doc["components"]["schemas"]["Target"]["required"] = "error"
        self.write_doc(self.api,self.doc)
        self.assert_error("malformed full response schema")
        self.write_form("-",kind="badrequest",schema="Absent")
        self.assert_error("missing or ambiguous response_schema")

    def test_alias_cycles_fail_even_for_dash_and_structural_recursion_stays_valid(self):
        self.doc["components"]["schemas"]["Alias"]["$ref"] = "#/components/schemas/Alias"
        self.write_doc(self.api,self.doc)
        self.write_form("-")
        self.assertEqual(self.check(), [])
        self.doc["components"]["schemas"]["Alias"]["$ref"] = "#/components/schemas/Target"
        self.doc["components"]["schemas"]["Target"]["properties"]["child"] = {"$ref":"#/components/schemas/Target"}
        self.write_doc(self.api,self.doc)
        self.assertEqual(self.check(), [])

        other=self.root/"Platform/common/contracts/local-rule-cycle.api.openapi.yaml"
        self.doc["components"]["schemas"]["Alias"]={"$ref":"../../common/contracts/local-rule-cycle.api.openapi.yaml#/components/schemas/A"}
        self.write_doc(self.api,self.doc)
        self.write_doc(other,{"components":{"schemas":{"A":{"$ref":"other.api.openapi.yaml#/components/schemas/B"}}}})
        self.write_doc(other.with_name("other.api.openapi.yaml"),{"components":{"schemas":{"B":{"$ref":"local-rule-cycle.api.openapi.yaml#/components/schemas/A"}}}})
        self.assert_error("cross-resource schema reference cycle")

    def test_cross_resource_cycle_and_common_to_lesson_are_errors(self):
        other=self.root/"Platform/common/contracts/alias.api.openapi.yaml"
        self.doc["components"]["schemas"]["Alias"]={"$ref":"../../common/contracts/alias.api.openapi.yaml#/components/schemas/Target"}
        self.write_doc(self.api,self.doc)
        self.write_doc(other,{"components":{"schemas":{"Target":{"$ref":"../../10-domain-console/spec/10-domain-console.api.openapi.yaml#/components/schemas/Alias"}}}})
        self.assert_error("common schema cannot refer to a lesson owner")
        self.write_doc(other,{"components":{"schemas":{"Target":{"$ref":"second.api.openapi.yaml#/components/schemas/Next"}}}})
        self.write_doc(other.with_name("second.api.openapi.yaml"),{"components":{"schemas":{"Next":{"$ref":"alias.api.openapi.yaml#/components/schemas/Target"}}}})
        self.assert_error("cross-resource schema reference cycle")

    def test_duplicate_keys_and_ambiguous_schema_origins_never_select_a_winner(self):
        second=self.api.with_name("duplicate.api.openapi.yaml")
        self.write_doc(second,{"components":{"schemas":{"Alias":self.target}}})
        self.assert_error("ambiguous schema 'Alias'")
        second.unlink()
        self.api.write_text('components: {schemas: {Alias: {}, Alias: {}}}\n')
        self.assert_error("duplicate YAML key")

    def test_standalone_schema_full_target_and_owner_data_position(self):
        target=self.root/"Platform/06-console/data/error.schema.json"
        self.write_doc(target,self.target)
        self.doc["components"]["schemas"]["Alias"]={"$ref":"../../06-console/data/error.schema.json"}
        self.write_doc(self.api,self.doc)
        self.assertEqual(self.check(), [])
        wrong=target.parent.parent/"spec/error.schema.json"
        self.write_doc(wrong,self.target)
        self.doc["components"]["schemas"]["Alias"]["$ref"]="../../06-console/spec/error.schema.json"
        self.write_doc(self.api,self.doc)
        self.assert_error("owner's data")

    def test_dash_boolean_schema_has_no_direct_projection(self):
        from unittest.mock import patch
        target=self.root/"Platform/06-console/data/boolean.schema.json"
        target.parent.mkdir(parents=True)
        target.write_text("true")
        self.doc["components"]["schemas"]["Alias"]={"$ref":"../../06-console/data/boolean.schema.json"}
        self.write_doc(self.api,self.doc)
        self.write_form("-")
        original=check_forms._RefusalSchemas.roles
        with patch.object(check_forms._RefusalSchemas,"roles",autospec=True,side_effect=original) as roles:
            self.assertEqual(self.check(), [])
            self.assertEqual(roles.call_args.kwargs,{"project":False})
        self.write_form("error")
        self.assert_error("not in the properties")

    def test_existing_yaml12_source_grammar_preserves_on_and_date_annotations(self):
        self.api.write_text("""openapi: 3.1.0
components:
  schemas:
    Alias:
      $ref: '#/components/schemas/Target'
    Target:
      type: object
      description: 2026-11-08
      required: [error]
      properties:
        error: {type: string}
        on: {type: string}
""")
        self.write_form("error,on?")
        self.assertEqual(self.check(), [])

    def test_subschema_target_keeps_enclosing_schema_validity_and_reference_base(self):
        self.doc["components"]["schemas"]["Container"]={"$defs":{"Fault":self.target},"required":"invalid"}
        self.doc["components"]["schemas"]["Alias"]={"$ref":"#/components/schemas/Container/$defs/Fault"}
        self.write_doc(self.api,self.doc)
        self.assert_error("malformed full response schema")
        del self.doc["components"]["schemas"]["Container"]["required"]
        self.doc["components"]["schemas"]["Container"]["$id"]="https://example.invalid/rebased"
        self.write_doc(self.api,self.doc)
        self.assert_error("resolver-specific schema keyword $id")

    def test_warmed_closure_cache_must_not_hide_selected_file_chain_cycle(self):
        a=self.root/"Platform/06-console/data/A.schema.json"
        b=a.with_name("B.schema.json")
        self.write_doc(a,{"$defs":{"Entry":{"$ref":"B.schema.json#/$defs/Leaf"},
                                   "Cycle":{"$ref":"B.schema.json#/$defs/Return"}}})
        self.write_doc(b,{"$defs":{"Leaf":self.target,"Return":{"$ref":"A.schema.json#/$defs/Cycle"}}})
        self.doc["components"]["schemas"].update({
            "Warm":{"$ref":"../../06-console/data/A.schema.json#/$defs/Entry"},
            "Bad":{"$ref":"../../06-console/data/B.schema.json#/$defs/Return"}})
        self.write_doc(self.api,self.doc)
        model=check_forms.openapi_schemas(self.lesson)
        self.assertEqual(model.errors,[])
        self.assertEqual(model.roles("Warm"),({"error","detail"},{"error"}))
        with self.assertRaisesRegex(ValueError,"cross-resource schema reference cycle"):
            model.roles("Bad")

    def test_disjoint_physical_resource_references_are_not_a_logical_cycle(self):
        a=self.root/"Platform/06-console/data/A.schema.json"
        b=a.with_name("B.schema.json")
        self.write_doc(a,{"$defs":{"Entry":{"$ref":"B.schema.json#/$defs/Scalar"},"Scalar":self.target}})
        self.write_doc(b,{"$defs":{"Scalar":self.target,"Return":{"$ref":"A.schema.json#/$defs/Scalar"}}})
        self.doc["components"]["schemas"].update({
            "Forward":{"$ref":"../../06-console/data/A.schema.json#/$defs/Entry"},
            "Reverse":{"$ref":"../../06-console/data/B.schema.json#/$defs/Return"}})
        self.write_doc(self.api,self.doc)
        model=check_forms.openapi_schemas(self.lesson)
        for name in ("Forward","Reverse"):
            self.assertEqual(model.roles(name),({"error","detail"},{"error"}))

    def test_subschema_enclosing_typed_sibling_refs_remain_full_schema_obligations(self):
        self.doc["components"]["schemas"].update({
            "Alias":{"$ref":"#/components/schemas/Outer/properties/Leaf"},
            "Outer":{"type":"object","properties":{"Leaf":self.target,"Unused":{"type":"string"}},
                     "examples":[{"$ref":"literal annotation data, not a reference"}]}})
        self.write_doc(self.api,self.doc)
        self.assertEqual(self.check(),[])
        later=self.root/"Platform/11-later/data/later.schema.json"
        self.write_doc(later,self.target)
        for ref,diagnostic in (("../../06-console/data/missing.schema.json","missing.schema.json"),
                               ("../../11-later/data/later.schema.json","earlier owner")):
            with self.subTest(ref=ref):
                self.doc["components"]["schemas"]["Outer"]["properties"]["Unused"]={"$ref":ref}
                self.write_doc(self.api,self.doc)
                self.assert_error(diagnostic)

    def test_cached_external_source_byte_change_is_an_error_without_healing(self):
        target=self.root/"Platform/06-console/data/held.schema.json"
        self.write_doc(target,self.target)
        self.doc["components"]["schemas"]["Alias"]={"$ref":"../../06-console/data/held.schema.json"}
        self.write_doc(self.api,self.doc)
        model=check_forms.openapi_schemas(self.lesson)
        self.assertEqual(model.roles("Alias"),({"error","detail"},{"error"}))
        held=target.read_bytes()
        target.write_bytes(held+b" ")
        with self.assertRaisesRegex(ValueError,"source bytes changed"):
            model.roles("Alias")
        target.write_bytes(held)
        with self.assertRaisesRegex(ValueError,"source bytes changed"):
            model.roles("Alias")

    def test_cached_main_source_byte_change_is_an_error_without_healing(self):
        model=check_forms.openapi_schemas(self.lesson)
        self.assertEqual(model.roles("Alias"),({"error","detail"},{"error"}))
        held=self.api.read_bytes()
        self.api.write_bytes(held+b" ")
        with self.assertRaisesRegex(ValueError,"source bytes changed"):
            model.roles("Alias")
        self.api.write_bytes(held)
        with self.assertRaisesRegex(ValueError,"source bytes changed"):
            model.roles("Alias")

    def test_existing_typed_line_schema_normal_direct_shape(self):
        self.doc["components"]["schemas"]["Alias"]={"type":"string","x-line-schema":copy.deepcopy(self.target)}
        self.write_doc(self.api,self.doc)
        self.write_form("-")
        self.assertEqual(self.check(),[])

    def test_existing_typed_line_schema_child_is_a_valid_reference_target(self):
        self.doc["components"]["schemas"].update({
            "Envelope":{"type":"string","x-line-schema":copy.deepcopy(self.target)},
            "Alias":{"$ref":"#/components/schemas/Envelope/x-line-schema"}})
        self.write_doc(self.api,self.doc)
        self.assertEqual(self.check(),[])
        model=check_forms.openapi_schemas(self.lesson)
        self.assertEqual(model.roles("Alias"),({"error","detail"},{"error"}))

    def test_existing_typed_line_schema_dash_rejects_malformed_required_child(self):
        self.doc["components"]["schemas"]["Alias"]={"type":"string","x-line-schema":{"required":"error"}}
        self.write_doc(self.api,self.doc)
        self.write_form("-")
        self.assert_error("malformed full response schema")

    def test_existing_typed_line_schema_dash_rejects_non_schema_or_invalid_shape(self):
        self.write_form("-")
        for child in ("not a schema",[],{"properties":[]},{"type":"unknown"}):
            with self.subTest(child=child):
                self.doc["components"]["schemas"]["Alias"]={"type":"string","x-line-schema":child}
                self.write_doc(self.api,self.doc)
                self.assert_error("malformed full response schema")

    def test_line_schema_and_ref_keys_inside_annotation_values_stay_opaque(self):
        payload={"x-line-schema":{"required":"error","$ref":"../../06-console/data/not-a-schema-resource"}}
        self.doc["components"]["schemas"]["Alias"]={"default":payload,"const":payload,"examples":[payload]}
        self.write_doc(self.api,self.doc)
        self.write_form("-")
        self.assertEqual(self.check(),[])

    def test_existing_typed_line_schema_unused_sibling_refs_are_inventoried(self):
        self.doc["components"]["schemas"].update({
            "Outer":{"type":"object","properties":{"Leaf":copy.deepcopy(self.target)},
                     "x-line-schema":{"$ref":"../../06-console/data/missing-lines.schema.json"}},
            "Alias":{"$ref":"#/components/schemas/Outer/properties/Leaf"}})
        self.write_doc(self.api,self.doc)
        self.assert_error("missing-lines.schema.json")

    def test_canonical_finite_return_to_other_pointer_is_valid(self):
        a=self.root/"Platform/06-console/data/A.schema.json"
        b=a.with_name("B.schema.json")
        self.write_doc(a,{"$defs":{"Start":{"$ref":"B.schema.json#/$defs/Alias"},"Leaf":self.target}})
        self.write_doc(b,{"$defs":{"Alias":{"$ref":"A.schema.json#/$defs/Leaf"}}})
        self.doc["components"]["schemas"]["Alias"]={"$ref":"../../06-console/data/A.schema.json#/$defs/Start"}
        self.write_doc(self.api,self.doc)
        self.assertEqual(self.check(),[])
        model=check_forms.openapi_schemas(self.lesson)
        self.assertEqual(model.roles("Alias"),({"error","detail"},{"error"}))

    def test_canonical_true_closed_cross_resource_pair_is_error(self):
        a=self.root/"Platform/06-console/data/A.schema.json"
        b=a.with_name("B.schema.json")
        self.write_doc(a,{"$defs":{"Start":{"$ref":"B.schema.json#/$defs/Alias"}}})
        self.write_doc(b,{"$defs":{"Alias":{"$ref":"A.schema.json#/$defs/Start"}}})
        self.doc["components"]["schemas"]["Alias"]={"$ref":"../../06-console/data/A.schema.json#/$defs/Start"}
        self.write_doc(self.api,self.doc)
        with self.assertRaisesRegex(ValueError,"cross-resource schema reference cycle"):
            check_forms.openapi_schemas(self.lesson).roles("Alias",project=False)

    def test_canonical_local_recursion_and_foreign_prefix_local_recursion_are_valid(self):
        a=self.root/"Platform/06-console/data/A.schema.json"
        b=a.with_name("B.schema.json")
        tree=copy.deepcopy(self.target)
        tree["properties"]["child"]={"$ref":"#/$defs/Tree"}
        self.write_doc(a,{"$defs":{"Tree":tree}})
        self.doc["components"]["schemas"]["Alias"]={"$ref":"../../06-console/data/A.schema.json#/$defs/Tree"}
        self.write_doc(self.api,self.doc)
        self.assertEqual(self.check(),[])
        self.write_doc(a,{"$defs":{"Start":{"$ref":"B.schema.json#/$defs/Tree"}}})
        self.write_doc(b,{"$defs":{"Tree":tree}})
        self.doc["components"]["schemas"]["Alias"]["$ref"]="../../06-console/data/A.schema.json#/$defs/Start"
        self.write_doc(self.api,self.doc)
        self.assertEqual(self.check(),[])

    def test_canonical_percent_escapes_and_physical_uri_aliases_keep_identity(self):
        a=self.root/"Platform/06-console/data/A.schema.json"
        b=a.with_name("B.schema.json")
        self.write_doc(a,{"$defs":{"Start":{"$ref":"B%2Eschema.json#/%24defs/%41lias"},"Leaf/one~x":self.target}})
        self.write_doc(b,{"$defs":{"Alias":{"$ref":"A.schema.json#/$defs/St%61rt"}}})
        alias=a.with_name("alias.schema.json")
        alias.symlink_to(a)
        self.doc["components"]["schemas"]["Alias"]={"$ref":"../../06-console/data/alias.schema.json#/$defs/Start"}
        self.write_doc(self.api,self.doc)
        model=check_forms.openapi_schemas(self.lesson)
        with self.assertRaisesRegex(ValueError,"cross-resource schema reference cycle"):
            model.roles("Alias")
        first=model._typed_target("../../06-console/data/A.schema.json#/$defs/Leaf~1one~0x",self.api)
        second=model._typed_target("../../06-console/data/alias.schema.json#/%24defs/Leaf%7E1one%7E0x",self.api)
        self.assertEqual(first[1:],second[1:])
        self.assertEqual(first[2],"/$defs/Leaf~1one~0x")
        self.assertEqual(model._node_key(first[1],first[2]),(a.resolve().as_uri(),"/$defs/Leaf~1one~0x"))

    def test_canonical_reverse_cache_orders_do_not_inherit_chain_permissions(self):
        a=self.root/"Platform/06-console/data/A.schema.json"
        b=a.with_name("B.schema.json")
        self.write_doc(a,{"$defs":{"Start":{"$ref":"B.schema.json#/$defs/Alias"},"Leaf":self.target,
                                   "Loop":{"$ref":"B.schema.json#/$defs/Back"}}})
        self.write_doc(b,{"$defs":{"Alias":{"$ref":"A.schema.json#/$defs/Leaf"},"Back":{"$ref":"A.schema.json#/$defs/Loop"}}})
        self.doc["components"]["schemas"].update({"Warm":{"$ref":"../../06-console/data/A.schema.json#/$defs/Start"},
                                                   "Bad":{"$ref":"../../06-console/data/A.schema.json#/$defs/Loop"}})
        self.write_doc(self.api,self.doc)
        for order in (("Warm","Bad"),("Bad","Warm")):
            model=check_forms.openapi_schemas(self.lesson)
            for name in order:
                if name=="Warm":
                    self.assertEqual(model.roles(name),({"error","detail"},{"error"}))
                else:
                    with self.assertRaisesRegex(ValueError,"cross-resource schema reference cycle"):
                        model.roles(name)

    def test_canonical_boolean_and_equal_value_declarations_have_distinct_pointers(self):
        a=self.root/"Platform/06-console/data/A.schema.json"
        self.write_doc(a,{"$defs":{"TrueOne":True,"TrueTwo":True,"FalseOne":False,"FalseTwo":False,
                                   "ObjectOne":self.target,"ObjectTwo":copy.deepcopy(self.target)}})
        model=check_forms.openapi_schemas(self.lesson)
        coordinates=[]
        for name in ("TrueOne","TrueTwo","FalseOne","FalseTwo","ObjectOne","ObjectTwo"):
            node,path,pointer=model._typed_target("../../06-console/data/A.schema.json#/$defs/"+name,self.api)
            self.assertEqual(pointer,"/$defs/"+name)
            coordinates.append(model._node_key(path,pointer))
        self.assertEqual(len(set(coordinates)),6)
        self.assertTrue(all(uri==a.resolve().as_uri() for uri,_ in coordinates))
        self.assertTrue(set(coordinates)<=model.inventoried)

    def test_canonical_reference_bearing_yaml_aliases_keep_declared_locations(self):
        a=self.root/"Platform/06-console/data/A.schema.json"
        b=a.with_name("B.schema.json")
        a.parent.mkdir(parents=True)
        # JSON resources use JSON; the reference-bearing aliases live in OpenAPI YAML.
        api=self.lesson/"spec/aliases.api.openapi.yaml"
        api.write_text("""components:
  schemas:
    First: &shared
      $ref: '../../06-console/data/B.schema.json#/$defs/Leaf'
    Second: *shared
""")
        self.write_doc(b,{"$defs":{"Leaf":self.target}})
        model=check_forms.openapi_schemas(self.lesson)
        first=model._typed_target("#/components/schemas/First",api)
        second=model._typed_target("#/components/schemas/Second",api)
        self.assertIs(first[0],second[0])
        self.assertNotEqual(first[2],second[2])
        self.assertEqual(model.roles("First"),({"error","detail"},{"error"}))
        self.assertEqual(model.roles("Second"),({"error","detail"},{"error"}))
        self.write_doc(b,{"$defs":{"Leaf":{"$ref":"../../10-domain-console/spec/aliases.api.openapi.yaml#/components/schemas/Second"}}})
        # A later-owner ref is rejected before any cycle permission can be inherited.
        with self.assertRaisesRegex(ValueError,"earlier owner"):
            check_forms.openapi_schemas(self.lesson).roles("First")

        common=self.root/"Platform/common/contracts/shared.api.openapi.yaml"
        other=common.with_name("other.api.openapi.yaml")
        common.parent.mkdir(parents=True)
        common.write_text("""components:
  schemas:
    Start: &shared
      $ref: 'other.api.openapi.yaml#/components/schemas/Alias'
    Leaf: *shared
""")
        self.write_doc(other,{"components":{"schemas":{"Alias":{"$ref":"shared.api.openapi.yaml#/components/schemas/Leaf"}}}})
        self.write_doc(b,{"$defs":{"Leaf":self.target}})
        self.doc["components"]["schemas"]["Alias"]={"$ref":"../../common/contracts/shared.api.openapi.yaml#/components/schemas/Start"}
        self.write_doc(self.api,self.doc)
        with self.assertRaisesRegex(ValueError,"cross-resource schema reference cycle.*schemas/Leaf"):
            check_forms.openapi_schemas(self.lesson).roles("Alias")

    def test_canonical_uri_owner_base_and_schema_type_guards_are_preserved(self):
        a=self.root/"Platform/06-console/data/A.schema.json"
        self.write_doc(a,{"$defs":{"Leaf":self.target}})
        self.doc["components"]["schemas"]["Alias"]={"$ref":"../../06-console/data/A.schema.json#/$defs/Leaf"}
        self.write_doc(self.api,self.doc)
        self.assertEqual(self.check(),[])
        later=self.root/"Platform/11-later/data/later.schema.json"
        self.write_doc(later,self.target)
        for ref,diagnostic in (("https://example.invalid/schema#/Leaf","nonlocal"),
                               ("../../11-later/data/later.schema.json","earlier owner"),
                               ("../../06-console/data/A.schema.json#/$defs/Absent","unresolved"),
                               ("../../06-console/data/A.schema.json#/$defs/Leaf/properties","schema position")):
            with self.subTest(ref=ref):
                self.doc["components"]["schemas"]["Alias"]={"$ref":ref}
                self.write_doc(self.api,self.doc)
                self.assert_error(diagnostic)
        self.doc["components"]["schemas"]["Alias"]={"$ref":"../../06-console/data/A.schema.json#/$defs/Leaf"}
        self.write_doc(self.api,self.doc)
        self.write_doc(a,{"$defs":{"Leaf":{"required":"error"}}})
        self.assert_error("malformed full response schema")

    def test_canonical_held_bytes_and_enclosing_schema_obligations_remain(self):
        a=self.root/"Platform/06-console/data/A.schema.json"
        self.write_doc(a,{"$defs":{"Leaf":self.target}})
        self.doc["components"]["schemas"]["Alias"]={"$ref":"../../06-console/data/A.schema.json#/$defs/Leaf"}
        self.write_doc(self.api,self.doc)
        model=check_forms.openapi_schemas(self.lesson)
        self.assertEqual(model.roles("Alias"),({"error","detail"},{"error"}))
        held=a.read_bytes()
        a.write_bytes(held+b" ")
        with self.assertRaisesRegex(ValueError,"source bytes changed"):
            model.roles("Alias")
        a.write_bytes(held)
        with self.assertRaisesRegex(ValueError,"source bytes changed"):
            model.roles("Alias")
        self.write_doc(a,{"$defs":{"Leaf":self.target,"Unused":{"$ref":"missing.schema.json"}}})
        self.assert_error("missing.schema.json")

    def test_canonical_public_target_shape_and_annotation_values_are_unchanged(self):
        payload={"$ref":"unresolved literal data","x-line-schema":{"required":"not a schema"}}
        self.doc["components"]["schemas"]["Target"].update(default=payload,examples=[payload])
        self.write_doc(self.api,self.doc)
        model=check_forms.openapi_schemas(self.lesson)
        self.assertEqual(model,self.doc["components"]["schemas"])
        node,path=model.target("#/components/schemas/Target",self.api)
        self.assertEqual(node,self.doc["components"]["schemas"]["Target"])
        self.assertEqual(path,self.api.resolve())
        self.assertEqual(model.roles("Alias"),({"error","detail"},{"error"}))

    def test_role_facts_normal_dag_is_positive_first(self):
        self.doc["components"]["schemas"]["Alias"]={"allOf":[{"$ref":"#/components/schemas/Target"},
            {"properties":{"trace":{"type":"string"}},"required":["trace"]}]}
        self.write_doc(self.api,self.doc)
        self.write_form("error,trace,detail?")
        self.assertEqual(self.check(),[])

    def test_role_dash_local_self_and_two_node_alias_rings_are_valid(self):
        self.write_form("-")
        for schemas in ({"Alias":{"$ref":"#/components/schemas/Alias"}},
                        {"Alias":{"$ref":"#/components/schemas/Other"},"Other":{"$ref":"#/components/schemas/Alias"}}):
            with self.subTest(schemas=schemas):
                self.doc["components"]["schemas"]=schemas
                self.write_doc(self.api,self.doc)
                self.assertEqual(self.check(),[])
                self.assertIsNone(check_forms.openapi_schemas(self.lesson).roles("Alias",project=False))

    def test_role_productive_local_ref_and_allof_cycles_have_finite_facts(self):
        self.doc["components"]["schemas"].update({
            "Alias":{"$ref":"#/components/schemas/Other","properties":{"error":{"type":"string"}},"required":["error"]},
            "Other":{"allOf":[{"$ref":"#/components/schemas/Alias"}],"properties":{"detail":{"type":"string"}}}})
        self.write_doc(self.api,self.doc)
        model=check_forms.openapi_schemas(self.lesson)
        self.assertEqual(model.roles("Alias"),({"error","detail"},{"error"}))
        self.write_form("error,detail?")
        self.assertEqual(self.check(),[])
        self.write_form("error?,detail")
        self.assert_error("required properties ['error']")

    def test_role_pure_alias_explicit_field_is_missing_fact_not_invalid_source_cycle(self):
        self.doc["components"]["schemas"]["Alias"]={"$ref":"#/components/schemas/Alias"}
        self.write_doc(self.api,self.doc)
        self.assertEqual(check_forms.openapi_schemas(self.lesson).roles("Alias"),(set(),set()))
        errors=self.check()
        self.assertTrue(any("not in the properties" in error for error in errors),errors)
        self.assertFalse(any("cyclic" in error or "cycle" in error for error in errors),errors)

    def test_role_nonrecursive_alternatives_keep_required_intersections(self):
        branch={"properties":{"detail":{"type":"string"}},"required":["detail"]}
        other=copy.deepcopy(branch)
        other["properties"]["trace"]={"type":"string"}
        for word in ("anyOf","oneOf"):
            with self.subTest(word=word):
                self.doc["components"]["schemas"]["Alias"]={"allOf":[{"$ref":"#/components/schemas/Target"}],word:[branch,other]}
                self.write_doc(self.api,self.doc)
                self.write_form("error,detail,trace?")
                self.assertEqual(self.check(),[])
                self.write_form("error,detail?,trace?")
                self.assert_error("required properties ['detail']")

    def test_role_grounded_recursive_alternative_has_derivable_required_facts(self):
        for word in ("anyOf","oneOf"):
            with self.subTest(word=word):
                self.doc["components"]["schemas"]["Alias"]={"properties":{"error":{"type":"string"}},
                    "required":["error"],word:[{"$ref":"#/components/schemas/Alias"},{"$ref":"#/components/schemas/Target"}]}
                self.write_doc(self.api,self.doc)
                self.write_form("error,detail?")
                self.assertEqual(self.check(),[])
                self.write_form("error?,detail?")
                self.assert_error("required properties ['error']")

    def test_role_underdetermined_recursive_alternative_is_projection_gap_not_schema_cycle(self):
        self.doc["components"]["schemas"]["Alias"]={"anyOf":[{"$ref":"#/components/schemas/Alias"},
            {"properties":{"error":{"type":"string"}},"required":["error"]}]}
        self.write_doc(self.api,self.doc)
        self.write_form("-")
        self.assertEqual(self.check(),[])
        model=check_forms.openapi_schemas(self.lesson)
        with self.assertRaisesRegex(ValueError,"underdetermined field projection"):
            model.roles("Alias")
        self.write_form("error")
        errors=self.check()
        self.assertTrue(any("underdetermined field projection" in error for error in errors),errors)
        self.assertFalse(any("cyclic" in error or "cross-resource" in error for error in errors),errors)

    def test_role_local_structural_recursion_foreign_prefix_and_true_crossfile_cycle(self):
        a=self.root/"Platform/06-console/data/A.schema.json"
        b=a.with_name("B.schema.json")
        tree=copy.deepcopy(self.target)
        tree["properties"]["child"]={"$ref":"#/$defs/Tree"}
        self.write_doc(a,{"$defs":{"Start":{"$ref":"B.schema.json#/$defs/Tree"}}})
        self.write_doc(b,{"$defs":{"Tree":tree}})
        self.doc["components"]["schemas"]["Alias"]={"$ref":"../../06-console/data/A.schema.json#/$defs/Start"}
        self.write_doc(self.api,self.doc)
        for fields in ("-","error,child?"):
            self.write_form(fields)
            self.assertEqual(self.check(),[])
        self.write_doc(b,{"$defs":{"Tree":{"$ref":"A.schema.json#/$defs/Start"}}})
        for fields in ("-","error"):
            self.write_form(fields)
            self.assert_error("cross-resource schema reference cycle")

    def test_role_dash_still_checks_full_metadata_refs_held_bytes_and_opaque_annotations(self):
        self.doc["components"]["schemas"]["Alias"]={"$ref":"#/components/schemas/Alias","required":"bad"}
        self.write_doc(self.api,self.doc)
        self.write_form("-")
        self.assert_error("malformed full response schema")
        self.doc["components"]["schemas"]["Alias"]={"$ref":"#/components/schemas/Alias", "default":{"$ref":"literal-not-a-reference"}}
        self.write_doc(self.api,self.doc)
        model=check_forms.openapi_schemas(self.lesson)
        self.assertIsNone(model.roles("Alias",project=False))
        held=self.api.read_bytes()
        self.api.write_bytes(held+b" ")
        with self.assertRaisesRegex(ValueError,"source bytes changed"):
            model.roles("Alias",project=False)
        self.api.write_bytes(held)
        with self.assertRaisesRegex(ValueError,"source bytes changed"):
            model.roles("Alias",project=False)
        self.doc["components"]["schemas"]["Alias"]={"$ref":"https://example.invalid/not-local"}
        self.write_doc(self.api,self.doc)
        self.assert_error("nonlocal")

    def test_schema_position_subschema_and_bad_dialect_are_checked(self):
        self.doc["components"]["schemas"]["Container"]={"$defs":{"Fault":self.target}}
        self.doc["components"]["schemas"]["Alias"]={"$ref":"#/components/schemas/Container/$defs/Fault"}
        self.write_doc(self.api,self.doc)
        self.assertEqual(self.check(), [])
        self.doc["components"]["schemas"]["Container"]["$defs"]["Fault"]["$id"]="https://example.invalid/new-base"
        self.write_doc(self.api,self.doc)
        self.assert_error("resolver-specific schema keyword $id")

if __name__ == "__main__":
    unittest.main()
