"""A named door of the common acceptance before the method of a scenarios.tsv step (README «Doors»; P01.155, scenario 21)."""

from pathlib import Path
import tempfile
import unittest

import check_spec

README = """# Common acceptance

**Doors** — the prefix of `request`.

| Door | Where | Lesson |
|---|---|---|
| `store` | the store door | 5 |
| `admin` | the store door through `admin.sock` | 5 |

**Request.**

| Form | Meaning | Lesson |
|---|---|---|
"""


class ScenarioDoors(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "Platform/common/acceptance").mkdir(parents=True)
        (root / "Platform/common/acceptance/README.md").write_text(README, encoding="utf-8")
        self.check = check_spec.Check(root)
        self.path = root / "scenarios.tsv"

    def errors(self, request, expect='200 {"ok": true}'):
        self.check.errors = []
        self.check.scenario_form(self.path, 7, request, expect)
        return [str(e) for e in self.check.errors]

    def test_known_door_accepted(self):
        self.assertEqual(self.errors('admin POST /v1/write {"op": "put", "items": {}}'), [])
        self.assertEqual(self.errors('store GET /v1/read?key=acc/a'), [])

    def test_unknown_door_refused(self):
        errors = self.errors('nosuchdoor POST /v1/write {}')
        self.assertTrue(any("unknown door nosuchdoor" in e for e in errors), errors)

    def test_plain_forms_unchanged(self):
        self.assertEqual(self.errors('POST /v1/write {}'), [])
        self.assertTrue(any("unsupported request form" in e for e in self.errors('FETCH /v1/write')))


if __name__ == "__main__":
    unittest.main()
