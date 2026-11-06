"""Shared key grammars preserve the four types formerly collapsed by translation."""
from pathlib import Path
import tempfile
import unittest

from v7 import spec

ROOT = Path(__file__).resolve().parents[3]


class TypedKeys(unittest.TestCase):
    def test_distinct_grammars(self):
        table, errors = spec.placeholder_table(ROOT)
        self.assertEqual(errors, [])
        host = spec.KeyTemplate('<host>', table)
        server = spec.KeyTemplate('<server>', table)
        self.assertTrue(host.matches('Cam.Example'))
        self.assertFalse(server.matches('Cam.Example'))
        self.assertTrue(server.matches('srv-a'))
        self.assertTrue(spec.KeyTemplate('<object-key>', table).matches('sub/blobs/hash'))
        self.assertFalse(spec.KeyTemplate('<key>', table).matches('sub/blobs/hash'))

    def test_source_is_independent_of_human_dictionary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / spec.KEYS_TABLE
            target.parent.mkdir(parents=True)
            target.write_bytes((ROOT / spec.KEYS_TABLE).read_bytes())
            mirror = root / 'Platform/common/ru/data/README.md'
            mirror.parent.mkdir(parents=True)
            mirror.write_text('deliberately invalid human mirror')
            self.assertEqual(spec.placeholder_table(root), spec.placeholder_table(ROOT))
            target.write_text(target.read_text() + '<host>\t^(?:x)$\tx\tduplicate\n')
            self.assertTrue(any('twice' in e for e in spec.placeholder_table(root)[1]))

    def test_closed_unit_vocabulary(self):
        units = [line.split('\t')[0] for line in (ROOT / 'Platform/common/data/outcome-units.tsv').read_text().splitlines()
                 if line and not line.startswith('#')][1:]
        self.assertEqual(tuple(units), spec.UNITS)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'closed.outcomes.tsv'
            for old_or_wrong in ('строка', 'поле', 'элемент', 'item'):
                path.write_text('\t'.join(spec.OUTCOME_HEADER) + '\n'
                                + f'\tconsole\tx\t1\t{old_or_wrong}\tn\n')
                with self.subTest(unit=old_or_wrong), self.assertRaises(spec.SpecError):
                    spec.load_outcomes(path, {'type': 'object'})


if __name__ == '__main__':
    unittest.main()
