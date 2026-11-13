"""Independent current-source controls for the family-read regression repair.

Run with the pinned lesson-spec Python; only Platform public source is read.
"""
import json
import io
import subprocess
import tarfile
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills/lesson-spec/scripts"))
from v7 import family_refresh, spec, stack


def family(name, kind="row"):
    return stack.Family(json.loads((ROOT / "Platform" / name).read_text()), kind)


class CurrentFamilyControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The one-time migration has exact source143 prose guards. Its input is
        # an explicit historical fixture; current family behavior below uses ROOT.
        cls.source143_tmp = tempfile.TemporaryDirectory(prefix="family-source143-")
        cls.addClassCleanup(cls.source143_tmp.cleanup)
        cls.source143_root = Path(cls.source143_tmp.name)
        data = subprocess.check_output(["git", "archive", "ca38a0818", "Platform/08-domain"], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            archive.extractall(cls.source143_root, filter="data")

    def test_source143_published_pending_and_outcomes_cells(self):
        _, maximum, rules = family_refresh.source_rules(self.source143_root)
        lines = (ROOT / spec.FAMILY_READ / "08.tsv").read_text().splitlines()
        rows = {line.split("\t")[0]: dict(zip(spec.FR_HEADER, line.split("\t"))) for line in lines[1:]}
        other = rows["08-1612"]
        self.assertEqual(family_refresh.migrated(other, maximum, rules), other)
        row = rows["08-1556"]
        got = family_refresh.migrated(row, maximum, rules)
        self.assertEqual(json.loads(got["outcome"]), {"domain": [""], "domainagent": [""]})
        self.assertEqual({k:v for k,v in got.items() if k != "outcome"},
                         {k:v for k,v in row.items() if k != "outcome"})

    def test_source143_root_seq_and_bad_name_outcomes(self):
        _, _, all_rules = family_refresh.source_rules(self.source143_root)
        rules = all_rules["domain/pending/<member>"]
        who = ["domain", "domainagent"]
        cases = (([], []), (["/seq"], ["/seq"]), (["/bad-name"], ["/*"]),
                 (["/seq", "/bad-name"], ["/seq"]), ([""], [""]),
                 (["", "/seq"], [""]), (["", "/bad-name"], [""]),
                 (["", "/seq", "/bad-name"], [""]))
        for paths, expected in cases:
            with self.subTest(paths=paths):
                self.assertEqual(family_refresh.pending_reader_outcomes(rules, paths, who),
                                 {role: expected for role in who})

    def test_source143_pending_actual_reader_scope(self):
        catalog = next(r for r in spec.read_catalog(ROOT) if r["key"] == "domain/pending/<member>")
        _, _, doc, _, source_outcomes = spec.load_family(ROOT, catalog)
        pending = stack.Family(doc, "row", family_template=catalog["key"])
        lines = (ROOT / spec.FAMILY_READ / "08.tsv").read_text().splitlines()
        sample = next(dict(zip(spec.FR_HEADER, line.split("\t"))) for line in lines[1:]
                      if line.startswith("08-1555\t"))
        edit = next(v for k,v in json.loads(sample["text"]).items() if k != "seq")
        cases = ((50, False, False, [], []), (50, True, False, ["/seq"], ["/seq"]),
                 (1, False, True, ["/bad-name"], ["/*"]),
                 (51, False, False, [""], [""]), (51, True, False, ["", "/seq"], [""]),
                 (51, False, True, ["", "/bad-name"], [""]),
                 (51, True, True, ["", "/bad-name", "/seq"], [""]))
        for count, bad_seq, bad_name, paths, outcome in cases:
            with self.subTest(count=count, bad_seq=bad_seq, bad_name=bad_name):
                value = {"seq": "bad" if bad_seq else "1",
                         **{"e-%012x" % i: edit for i in range(count)}}
                if bad_name:
                    del value["e-%012x" % (count - 1)]
                    value["bad-name"] = edit
                got = pending.judge(value, "reader")
                self.assertEqual(got["paths"], paths)
                for role in ("domain", "domainagent"):
                    self.assertEqual([o.path for o in spec.outcomes_for(source_outcomes, got["paths"], role)], outcome)

    def test_refresh_ledger_collision_before_read_and_external_neighbor(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            course = home / "course"
            table = course / spec.FAMILY_READ / "08.tsv"
            table.parent.mkdir(parents=True)
            table.write_text("\t".join(spec.FR_HEADER) + "\n" + "\t".join(
                ["unchanged", "other/family", "other/family", "row", "writer", "[]", "{}", "ok", "[]", "[]", "base"]) + "\n")
            witnesses = [course / "Source/witness", course / "VMS/PLATFORM_PIN"]
            for path in witnesses:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"unchanged witness")
            alias = home / "outside-alias.json"
            alias.symlink_to(table)
            originals = {path: path.read_bytes() for path in [table, *witnesses]}
            with patch.object(family_refresh, "source_rules") as source:
                for ledger in [table, *witnesses, course / "tools/proof.json", alias]:
                    with self.subTest(ledger=ledger), self.assertRaisesRegex(ValueError, "outside the course root"):
                        family_refresh.refresh(course, ledger)
                source.assert_not_called()
            self.assertEqual({path: path.read_bytes() for path in originals}, originals)
            proof = home / "fresh-external-proof.json"
            with patch.object(family_refresh, "source_rules", return_value=({}, 2000, {})):
                result = family_refresh.refresh(course, proof)
            self.assertEqual(result["changed"], 0)
            self.assertEqual({path: path.read_bytes() for path in originals}, originals)
            ledger = json.loads(proof.read_text())
            self.assertEqual(ledger["rows_before"], 1)
            self.assertEqual(ledger["rows_after"], 1)
            self.assertEqual(ledger["old_sha256"], ledger["new_sha256"])

    def test_time_row_and_nested_json_lexemes(self):
        row = family("01-store/data/epoch_floor.schema.json")
        grants = family("08-domain/data/grants.schema.json")
        for mode in ("writer", "reader"):
            for token, allowed in (("1.123", True), ("1.1234", False), ("1.0001", False), ("1e0", False), ("-1", False)):
                with self.subTest(mode=mode, token=token):
                    got = row.judge({"floor": "1", "generation_at": token}, mode)
                    self.assertEqual(got["paths"], [] if allowed else ["/generation_at"])
                    for raw in (token, json.dumps(token)):
                        if mode == "writer" and raw == "1e0":
                            continue  # JCS rejects this notation at /doc before the time place.
                        doc = '{"lines":[{"by":"a","cap":"view","scope":"*","subject":"a","until":' + raw + '}]}'
                        value = {"doc": doc, "revision": "1"}
                        got = grants.judge(value, mode)
                        self.assertEqual(got["paths"], [] if allowed else ["/doc/lines/0/until"])

    def test_publication_sent_at_keeps_its_own_numeric_form(self):
        rows = (ROOT / spec.FAMILY_READ / "08.tsv").read_text().splitlines()
        source = next(dict(zip(spec.FR_HEADER, line.split("\t"))) for line in rows[1:]
                      if "\tdomain/members/<member>/reported\t" in line and line.endswith("\tbase"))
        catalog = next(r for r in spec.read_catalog(ROOT) if r["key"] == source["family"])
        report = family(catalog["schema"], "object")
        value = json.loads(source["text"])
        value["sent_at"] = 1.12345  # P01 R012: copied publication time has its own form.
        for mode in ("reader", "writer"):
            self.assertEqual(report.judge(value, mode)["paths"], [])

    def test_decoded_numeric_time_has_current_bound(self):
        obj = family("08-domain/data/view.schema.json", "object")
        for mode in ("writer", "reader"):
            for value, allowed in ((1.123, True), (1.1234, False), (True, False)):
                got = obj.judge({"as_of": value, "holder": "a", "complete": True}, mode)
                self.assertEqual(got["paths"], [] if allowed else ["/as_of"])

    def test_source143_revision_migration_keeps_other_mutation_and_missing_control(self):
        _, maximum, outcomes = family_refresh.source_rules(self.source143_root)
        row = dict(zip(spec.FR_HEADER, ["private-control", "domain/groups/<name>", "domain/groups/ops", "row", "writer", '["domain"]',
                                       '{"name":"ops","members":"bad-list"}', "refused", '["/members"]', "[]", "members: wrong type"]))
        got = family_refresh.migrated(row, maximum, outcomes)
        self.assertEqual(json.loads(got["text"]), {"name": "ops", "members": "bad-list", "revision": "1"})
        self.assertEqual({k:v for k,v in got.items() if k != "text"}, {k:v for k,v in row.items() if k != "text"})
        row.update(case="g08-groups-revision-absent-reader", mode="reader", who='["domain","domainconsole"]', paths="[]", verdict="ok")
        got = family_refresh.migrated(row, maximum, outcomes)
        self.assertEqual(got["text"], row["text"])
        self.assertEqual(json.loads(got["paths"]), ["/revision"])
        self.assertEqual(json.loads(got["outcome"]), {"domain": [""], "domainconsole": [""]})
        self.assertEqual(family_refresh.migrated(got, maximum, outcomes), got)

    def test_current_revision_absent_and_unreadable_use_current_family_outcomes(self):
        catalog = spec.read_catalog(ROOT)
        corpus = [dict(zip(spec.FR_HEADER, line.split("\t"))) for line in
                  (ROOT / spec.FAMILY_READ / "08.tsv").read_text().splitlines()[1:]]
        for template in family_refresh.REVISION_FAMILIES:
            declaration = next(r for r in catalog if r["key"] == template)
            _, _, doc, _, outcomes = spec.load_family(ROOT, declaration)
            current = stack.Family(doc, "row", family_template=template)
            base = next(json.loads(r["text"]) for r in corpus if r["family"] == template
                        and r["mode"] == "reader" and r["verdict"] == "ok"
                        and "revision" in json.loads(r["text"]))
            for value in (None, "bad", "0"):
                row = dict(base)
                if value is None:
                    row.pop("revision")
                else:
                    row["revision"] = value
                with self.subTest(family=template, revision=value):
                    result = current.judge(row, "reader")
                    self.assertEqual(result["verdict"], "refused")
                    self.assertIn("/revision", result["paths"])
                    roles = {o.reader for o in outcomes if o.path == "" and o.reader != "*"}
                    self.assertTrue(roles)
                    for role in roles:
                        selected = spec.outcomes_for(outcomes, result["paths"], role)
                        self.assertTrue(selected)
                        self.assertTrue(all(o.unit == "row" for o in selected))

    def test_actual_pending_name_count_excludes_seq(self):
        # Use the real edit form, with valid dynamic names. This isolates layer 3
        # name counting from unrelated propertyNames failures in the old corpus.
        lines = (ROOT / spec.FAMILY_READ / "08.tsv").read_text().splitlines()
        rows = [dict(zip(spec.FR_HEADER, line.split("\t"))) for line in lines[1:]]
        source = next(r for r in rows if r["case"] == "08-1555")
        edit = next(v for k,v in json.loads(source["text"]).items() if k != "seq")
        pending = family("08-domain/data/pending.schema.json")
        for mode in ("writer", "reader"):
            for count in (50, 51):
                value = {"seq": "1", **{"e-%012x" % i: edit for i in range(count)}}
                got = pending.judge(value, mode)
                self.assertEqual(got["paths"], [] if count == 50 else [""])


if __name__ == "__main__":
    unittest.main()
