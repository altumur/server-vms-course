"""Independent current-source controls for the family-read regression repair.

Run with the pinned lesson-spec Python; only Platform public source is read.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills/lesson-spec/scripts"))
from v7 import family_refresh, spec, stack


def family(name, kind="row"):
    return stack.Family(json.loads((ROOT / "Platform" / name).read_text()), kind)


class CurrentFamilyControls(unittest.TestCase):
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

    def test_current_revision_keeps_other_mutation_and_missing_control(self):
        _, maximum, outcomes = family_refresh.source_rules(ROOT)
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
