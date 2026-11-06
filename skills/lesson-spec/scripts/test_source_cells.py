"""Source-form conformance and complete byte preservation, ADR-0121 (6)."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import source_cells

ROOT = Path(__file__).resolve().parents[3]


class SourceCells(unittest.TestCase):
    def test_shared_conformance_vectors(self):
        for case in json.loads((ROOT / 'Platform/common/vectors/source-cells/cases.json').read_text()):
            with self.subTest(case=case['case']):
                names, rows, errors = source_cells.table(case['text'], case['columns'], case['positional'])
                self.assertEqual(not errors, case['valid'], errors)
                if case['valid']:
                    self.assertEqual(list(names), case['declared'])
                    self.assertEqual([[n, row] for n, row in rows], case['rows'])

    def test_no_declaration_leaves_raw_table_alone(self):
        self.assertEqual(source_cells.table('raw\nplain\n'), ((), [], []))

    def test_complete_byte_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'Platform/common/vectors/sample/cases.tsv'
            path.parent.mkdir(parents=True)
            path.write_text('# cell-json: raw\nraw\n"\\u0436"\n')
            manifest = root / 'Platform/common/data/cell-json-sha256.tsv'
            manifest.parent.mkdir(parents=True)
            self.assertTrue(source_cells.errors(root, [path]))
            header = 'table\tline\tcolumn\tbefore_sha256\tdecoded_sha256\n'
            sha = hashlib.sha256('\u0436'.encode()).hexdigest()
            row = f'{path.relative_to(root)}\t3\traw\t{sha}\t{sha}\n'
            manifest.write_text(header + row)
            self.assertEqual(source_cells.errors(root, [path]), [])
            for invalid in (header, header + row + row, header + row.replace(sha, '0' * 64, 1),
                            header + row.replace('\t3\t', '\t4\t')):
                manifest.write_text(invalid)
                self.assertTrue(source_cells.errors(root, [path]))

    def test_real_source_byte_proof(self):
        paths = [ROOT / line.split('\t')[0] for line in
                 (ROOT / 'Platform/common/data/cell-json-sha256.tsv').read_text().splitlines()
                 if line.startswith('Platform/')]
        self.assertEqual(source_cells.errors(ROOT, sorted(set(paths))), [])


if __name__ == '__main__':
    unittest.main()
