"""Source-form conformance and complete byte preservation, ADR-0121 (6)."""
import hashlib
import json
import os
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
                    for proof in case.get('unmarked_byte_proofs', []):
                        header = case['text'].split('\n')[1].split('\t')
                        before = case['text'].split('\n')[proof['row'] - 1].split('\t')[header.index(proof['column'])]
                        after = dict(rows)[proof['row']][proof['column']]
                        self.assertEqual(hashlib.sha256(before.encode()).hexdigest(), proof['before_sha256'])
                        self.assertEqual(hashlib.sha256(after.encode()).hexdigest(), proof['decoded_sha256'])
                        self.assertEqual(before.encode(), after.encode())

    def test_unmarked_carriage_return_is_not_normalized_by_file_io(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'Platform/common/vectors/sample/cases.tsv'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'# cell-json: payload\nplain\tpayload\nA\rB\t"x"\n')
            manifest = root / 'Platform/common/data/cell-json-sha256.tsv'
            manifest.parent.mkdir(parents=True)
            sha = hashlib.sha256(b'x').hexdigest()
            manifest.write_text('table\tline\tcolumn\tbefore_sha256\tdecoded_sha256\n'
                                + f'{path.relative_to(root)}\t3\tpayload\t{sha}\t{sha}\n')
            self.assertEqual(source_cells.errors(root, [path]), [])

    def test_no_declaration_leaves_raw_table_alone(self):
        self.assertEqual(source_cells.table('raw\nplain\n'), ((), [], []))

    def test_known_scenario_form_keeps_first_row(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'Platform/01-store/acceptance/1/scenarios.tsv'
            path.parent.mkdir(parents=True)
            header = 'scenario\tstep\trequest\texpect'
            for first in ('# ' + header, header):
                text = '# cell-json: request\n' + first + '\nfirst\t1\t"POST /v1/write {not-json"\t400 {}\n'
                path.write_text(text)
                columns, positional = source_cells.wire_headers(root)[path.relative_to(root)]
                names, rows, errors = source_cells.table(text, columns, positional)
                self.assertEqual(errors, [])
                self.assertEqual(names, ('request',))
                self.assertEqual(rows, [(3, dict(scenario='first', step='1', request='POST /v1/write {not-json', expect='400 {}'))])

    def test_checker_uses_the_same_source_step_before_scenario_parsing(self):
        from check_spec import Check, SCENARIO_HEADER
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'scenarios.tsv'
            request = r'POST /v1/write {not-json "literal \\u0436"'
            path.write_text('# scenario\tstep\trequest\texpect\n# cell-json: request\n'
                            + 'first\t1\t' + json.dumps(request) + '\t400 {}\n')
            check = Check(root)
            self.assertEqual(check.tsv(path, 4, SCENARIO_HEADER), [(3, ['first', '1', request, '400 {}'])])
            self.assertEqual(check.errors, [])

    def test_checker_keeps_unmarked_line_separators(self):
        from check_spec import Check
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'sample.tsv'
            for separator in ('\u2028', '\v', '\r'):
                plain = 'A' + separator + 'B'
                path.write_bytes(('# cell-json: payload\nplain\tpayload\n' + plain + '\t"x"\n').encode())
                check = Check(root)
                self.assertEqual(check.tsv(path, 2, ['plain', 'payload']), [(3, [plain, 'x'])])
                self.assertEqual(check.errors, [])

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


SEAMS = 'Platform/06-console/acceptance/8/seams.tsv'
# decisions/inbox/2026-11-06-p06-review-proposals/source-binding-proposal.json (391efde0d): source, expected,
# decoded request, decoded SHA-256
SEAMS_FIXTURES = [
    ('# cell-json: request\n# owned positional source fixture\nowned-first\t1\t"CALL console-folder-create {\\"name\\":\\"\\u0436\\"}"\t{"ok":true}\n', 'valid; first data physical3', 'CALL console-folder-create {"name":"ж"}', '6eddb902c055e34ac8117c0e012ac40daf230afc8c58d4f2eb64d9632e922e85'),
    ('# cell-json: request\n# owned positional source fixture\nowned-first\t1\t"CALL console-folder-create {invalid-inner"\t{"ok":true}\n', 'valid outer; invalid inner remains opaque', 'CALL console-folder-create {invalid-inner', '29e6ed42e2f94991638951154eeb995c459b87b1094e5f9524268d2e7a1655e0'),
    ('# cell-json: request\n# owned positional source fixture\nowned-first\t1\tnot-json\t{"ok":true}\n', 'form error', None, None),
    ('# cell-json: request\n# owned positional source fixture\nowned-first\t1\tnull\t{"ok":true}\n', 'form error', None, None),
    ('# cell-json: request\n# owned positional source fixture\nowned-first\t1\t"\\ud800"\t{"ok":true}\n', 'form error', None, None),
    ('# cell-json: request,request\n# owned positional source fixture\nowned-first\t1\t"CALL console-folder-create {\\"name\\":\\"\\u0436\\"}"\t{"ok":true}\n', 'form error: duplicate declaration column', None, None),
    ('# cell-json: request\n# owned positional source fixture\nowned-first\t"CALL console-folder-create {\\"name\\":\\"\\u0436\\"}"\t{"ok":true}\n', 'form error: wrong width', None, None),
]


class SeamsBinding(unittest.TestCase):               # Architect 2026-11-06: one exact positional path
    def write(self, root, rel, text):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode())
        return path

    def test_exact_path_only(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as elsewhere:
            root = Path(directory)
            self.write(root, 'Platform/06-console/acceptance/9/seams.tsv', 'x\n')
            self.write(root, 'Platform/04-controller/acceptance/8/seams.tsv', 'x\n')
            forms = source_cells.wire_headers(root)
            self.assertEqual(forms[Path(SEAMS)], (['scenario', 'step', 'request', 'expect'], True))
            self.assertEqual([p for p in forms if p.name == 'seams.tsv'], [Path(SEAMS)])
            cwd = os.getcwd()
            try:
                os.chdir(elsewhere)                        # unrelated cwd: the same binding
                self.assertEqual(source_cells.wire_headers(root), forms)
            finally:
                os.chdir(cwd)

    def test_proposal_fixtures(self):
        self.assertEqual(len(SEAMS_FIXTURES), 7)
        for source, expected, request, sha in SEAMS_FIXTURES:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = self.write(root, SEAMS, source)
                columns, positional = source_cells.wire_headers(root)[path.relative_to(root)]
                names, rows, errors = source_cells.table(source, columns, positional)
                manifest = root / 'Platform/common/data/cell-json-sha256.tsv'
                manifest.parent.mkdir(parents=True)
                header = 'table\tline\tcolumn\tbefore_sha256\tdecoded_sha256\n'
                if request is None:                        # form error before build/dispatch
                    self.assertTrue(errors)
                    self.assertTrue(source_cells.errors(root, [path]))
                    continue
                self.assertEqual(errors, [])
                self.assertEqual(names, ('request',))
                raw = source.split('\n')[2].split('\t')
                self.assertEqual(rows, [(3, dict(scenario='owned-first', step='1', request=request, expect=raw[3]))])
                self.assertEqual(hashlib.sha256(request.encode()).hexdigest(), sha)
                self.assertEqual(rows[0][1]['expect'].encode(), raw[3].encode())      # unmarked cell untouched
                self.assertTrue(source_cells.errors(root, [path]))                    # no proof: refused
                manifest.write_text(header + f'{SEAMS}\t3\trequest\t{sha}\t{sha}\n')
                self.assertEqual(source_cells.errors(root, [path]), [])
                manifest.write_text(header + f'{SEAMS}\t3\trequest\t{"0" * 64}\t{"0" * 64}\n')
                self.assertTrue(source_cells.errors(root, [path]))
                moved = Path('Platform/06-console/acceptance/9/seams.tsv')          # undeclared path: not positional
                other = self.write(root, moved.as_posix(), source)
                self.assertNotIn(moved, source_cells.wire_headers(root))
                self.assertTrue(source_cells.errors(root, [other]))

    def test_real_seams_unchanged(self):
        text = (ROOT / SEAMS).read_bytes().decode('utf-8')
        columns, positional = source_cells.wire_headers(ROOT)[Path(SEAMS)]
        self.assertEqual(source_cells.table(text, columns, positional), ((), [], []))


if __name__ == '__main__':
    unittest.main()
