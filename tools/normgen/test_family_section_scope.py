"""Writer-heading scope controls; source positives use the declared immutable root.

FAMILY_SECTION_SOURCE_ROOT selects the readonly 5a26a070 public projection for
this repair. After source integration the same tests can use the course root.
"""
import copy
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(os.environ.get("FAMILY_SECTION_SOURCE_ROOT", ROOT))
P09_SOURCE = Path(os.environ.get("FAMILY_SECTION_P09_SOURCE_ROOT", SOURCE))
sys.path.insert(0, str(ROOT / "skills/lesson-spec/scripts"))
from v7.section import SchemaSection

SHARED = {
    "en": "Reader and writer bounds (`$defs.writer`, applied by root `allOf`):",
    "ru": "\u041f\u0440\u0435\u0434\u0435\u043b\u044b \u0447\u0438\u0442\u0430\u0442\u0435\u043b\u044f \u0438 \u043f\u0438\u0441\u0430\u0442\u0435\u043b\u044f (`$defs.writer`, \u043f\u0440\u0438\u043c\u0435\u043d\u0435\u043d\u044b \u043a\u043e\u0440\u043d\u0435\u0432\u044b\u043c `allOf`):",
}
WRITER = {"en": "Only at the writer (`$defs.writer`):", "ru": "\u0422\u043e\u043b\u044c\u043a\u043e \u0443 \u043f\u0438\u0441\u0430\u0442\u0435\u043b\u044f (`$defs.writer`):"}
CASES = (("sweep", "<sub>/sweep", "digests", 64),
         ("folders", "platform/folders/<id>", "members", 1000),
         ("memberof", "platform/memberof/<sub>/<manifest:unit.rows>/<id>", "folders", 8))


def source_doc(name):
    return json.loads((SOURCE / "Platform/06-console/data" / (name + ".schema.json")).read_text())


def body(doc, lang, template):
    return SchemaSection(doc, family=True, lang=lang, family_template=template).writer_body()


class FamilySectionScopeTests(unittest.TestCase):
    def test_00_published_shared_writer_scope(self):
        # P06.1:308 and P06.8:114, immutable Source5a26: the whole writer
        # definition is also applied by the root schema, for every reader.
        for name, template, field, maximum in CASES:
            doc = source_doc(name)
            self.assertIn({"$ref": "#/$defs/writer"}, doc["allOf"])
            self.assertEqual(doc["$defs"]["writer"]["properties"][field]["maxItems"], maximum)
            writer_only = copy.deepcopy(doc)
            del writer_only["allOf"]
            for lang in ("en", "ru"):
                with self.subTest(source=name, lang=lang):
                    got = body(doc, lang, template)
                    self.assertEqual(got[0], SHARED[lang])
                    self.assertEqual(got[1:], body(writer_only, lang, template)[1:])

    def test_01_published_p09_shared_writer_scope(self):
        # Immutable Source5a26 P09.1 domain/outcomes and domain/alarms apply
        # their entire writer profiles at the root: 500 names and 100 events.
        for name, template in (("outcomes", "domain/outcomes"), ("alarms", "domain/alarms")):
            doc = json.loads((P09_SOURCE / "Platform/09-agent/data" / (name + ".schema.json")).read_text())
            self.assertIn({"$ref": "#/$defs/writer"}, doc["allOf"])
            writer = doc["$defs"]["writer"]
            if name == "outcomes":
                self.assertEqual(writer["maxProperties"], 500)
            else:
                self.assertEqual(writer["properties"]["events"]["maxItems"], 100)
            writer_only = copy.deepcopy(doc)
            del writer_only["allOf"]
            for lang in ("en", "ru"):
                with self.subTest(source=name, lang=lang):
                    got = body(doc, lang, template)
                    self.assertEqual(got[0], SHARED[lang])
                    self.assertEqual(got[1:], body(writer_only, lang, template)[1:])

    def test_writer_only_and_conditional_root_keep_their_heading(self):
        original = source_doc("sweep")
        writer_only = copy.deepcopy(original)
        del writer_only["allOf"]
        conditional = copy.deepcopy(writer_only)
        conditional["allOf"] = [{"if": {"required": ["digests"]}, "then": {"$ref": "#/$defs/writer"}}]
        for lang in ("en", "ru"):
            plain = body(writer_only, lang, "<sub>/sweep")
            self.assertEqual(plain[0], WRITER[lang])
            self.assertEqual(body(conditional, lang, "<sub>/sweep"), plain)

    def test_contextual_profiles_keep_their_key_scopes(self):
        doc = json.loads((ROOT / "Platform/08-domain/data/deleting.schema.json").read_text())
        for lang in ("en", "ru"):
            got = body(doc, lang, "domain/deleting/<name>")
            self.assertNotIn(SHARED[lang], got)
            self.assertTrue(any("domain/deleting/<name>" in line and "person_writer" in line for line in got))
            self.assertTrue(any("domain/deleting/role:<name>" in line and "role_writer" in line for line in got))


if __name__ == "__main__":
    unittest.main()
