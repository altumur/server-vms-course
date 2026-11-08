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
sys.path.insert(0, str(ROOT / "skills/lesson-spec/scripts"))
from v7.section import SchemaSection

SHARED = {
    "en": "Reader and writer bounds (`$defs.writer`, applied by root `allOf`):",
    "ru": "Пределы читателя и писателя (`$defs.writer`, применены корневым `allOf`):",
}
WRITER = {"en": "Only at the writer (`$defs.writer`):", "ru": "Только у писателя (`$defs.writer`):"}
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
