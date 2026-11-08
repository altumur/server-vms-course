import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gen_core
import gen_door
import machine_source


class CoreMachineAnchors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = Path(tempfile.mkdtemp(prefix="machine-core-control-"))
        gen_door.generate(spec_path=gen_core.OPENAPI, out=cls.home)
        cls.door = cls.home / "go/apidoor/door.go"
        with patch.object(gen_core, "DOOR", cls.door):
            cls.files, cls.report = gen_core.render()

    def test_actual_r141_and_all_tags_are_complete_existing_ids_without_prose(self):
        texts = {p: p.read_text(encoding="utf-8") for p in (gen_core.NORMS, gen_core.NORMS_12, gen_core.NORMS_13)}
        known = {a for text in texts.values() for _, _, rows in gen_core.sections(text) for a, _ in rows}
        self.assertGreater(len(gen_core.anchored(gen_core.NORMS)['P/01.1-R141']), gen_core.LINE)
        seen = []
        for name, source in self.files.items():
            self.assertNotIn('DO NOT EDIT', source, name)
            for line in source.splitlines():
                if not line.lstrip().startswith('//'):
                    continue
                if line.startswith('// Source: ') or re.fullmatch(r'// sha256: [0-9a-f]{64}', line):
                    continue
                match = re.fullmatch(r'// req: (P/[0-9]+\.[0-9]+-R[0-9]+)', line)
                self.assertIsNotNone(match, (name, line))
                self.assertIn(match[1], known)
                seen.append(match[1])
        self.assertIn('// req: P/01.1-R141\n', self.files['coreadapter/write.go'])
        self.assertIn('P/01.2-R017', seen)
        self.assertIn('P/01.3-R033', seen)

    def test_missing_source_anchor_refuses_before_emission(self):
        entry = gen_core.IDENTITY[0]
        missing = [(*entry[:2], 'P/01.2-R999999', entry[3]), *gen_core.IDENTITY[1:]]
        with patch.object(gen_core, 'IDENTITY', missing), self.assertRaisesRegex(gen_core.GenError, 'no req anchor'):
            gen_core.identity_comment()

    def test_labels_optional_but_given_label_must_exist_and_have_no_excerpt(self):
        known = set(gen_core.anchored(gen_core.NORMS))
        body = 'package sample\nfunc f() {}\n'
        self.assertEqual(machine_source.go_source(body, anchor_ids=known), body)
        tagged = '// req: P/01.1-R141\n' + body
        self.assertEqual(machine_source.go_source(tagged, anchor_ids=known), tagged)
        for bad in ('// req: P/01.1-R999999\n', '// req: P/01.1-R141 — truncated prose…\n'):
            with self.subTest(comment=bad), self.assertRaisesRegex(machine_source.SourceError, 'one exact existing'):
                machine_source.go_source(bad + body, anchor_ids=known)


if __name__ == '__main__':
    unittest.main()
