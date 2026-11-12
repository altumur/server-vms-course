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

    # The frozen English P/06 slice activates cell-json in the real seams table (spec, origin/spec/0121-p06-review-source
    # fb66713ba, parent 01c2ef539; decisions/inbox/2026-11-06-p06-full-english/seams8-four-cells.json). Exactly four
    # cells are marked: the request of the four data lines. The declaration shifts the former physical lines 3–6 to 4–7.
    # Since d5e9ab4b4 the table has eight data lines, 4–11, each with its marked request cell (below).
    # Per cell: physical line, scenario, SHA-256 of the raw (JSON-encoded) source cell, SHA-256 of the decoded request
    # (= before_sha256 of the former raw cell = the proof row), SHA-256 of the unmarked expect cell.
    SEAMS_CELLS = (
        (4, 's01-folder-name-255-bytes', '191482b241484e40ff213486783ef4663d9395b41a09b49076fbb72597b44489',
         'e8060e5363c50a8ae0f401f3da310bd8c8797b2c238177a46560e787683e4981',
         'a41460504223dc6ff2280cfe85b7ffe1c8b8efea617ec73fb34dc30f26362f00'),
        (5, 's02-folder-name-256-bytes', '7e959239dd759112b27457b2b28bba282e29ef9b5289a4369fb7ef4b777c2d43',
         'd28e3d2e69eaa57c9a473a9230a53e0ef4e2b0a87a1d9518420c327190f8f93e',
         'ac8e85b1b386072ad4caba57a0a49cf6ddecdf1fc73706c95ad0847004799b58'),
        (6, 's03-parent-guard-race', '7394671a68964f3affe5cf22a293cc57e56335e59acd9c2b7088131e38ee8787',
         '94b7936182baa5484f31cfaab2ca4f8e3a4b40d0857ec1d9159722a12063bc1e',
         '5c87d7d2161608b789b4321222e56bf8769f1c3bc182921ac9a1ec3f7594cf84'),
        (7, 's04-membership-key-too-long', '88c608ca6e07f4ad021227850043bec1375700414c6d725f03d024a2424f552b',
         'b5c9a6cf771703e9d77dcaeb9305911009f7232d66435c3fee63fc1fcd24daa9',
         'c0cadec3604415fb97e9abcec72585c52cdb111c3c82af4ab5508af33507ceb9'),
        # d5e9ab4b4 (ADR-0083 (145), the accepted P06 share) added four data lines, s05–s08, with their proof rows in
        # cell-json-sha256.tsv; the first four cells above are unchanged byte for byte.
        (8, 's05-delete-explicit-folder-conflict', 'e487ec2e4650d9031615bebab0d962bf98adecabcf5da2ee827b5d9f66996a4f',
         'beb66902dcce4dcd3a57f3e7a5e58b6eea8dbfed94ec3fcafbac4b80c4aac10a',
         '8e035287e9e22dbff3315f6080be0622340196af1023f9e3382e03e925726d9d'),
        (9, 's06-delete-explicit-membership-conflict', 'da90ccad9c73f2e51312900aac857238b9f45ff2296d9b2f6111dbf52bc7cd41',
         '0691ca93ff53255580e4d5c4f417ddce179932b31fe4769926e781698d119f6f',
         '58b19b9ef020470ebcfb53c3c0f2eb1f8bfbb2503db193d987d8f61bf8833c80'),
        (10, 's07-delete-explicit-consistent', 'c1f053826da5d0f0330daf2b2ceb0c88f6759185fa8abb561a8ef424cb7e3142',
         '05caabf346d6b28c8c543ebec5bb1145bc7314121fefc57806032ea90f6c333b',
         '0abed79b1b14b8201b0c6e7bd075cb2e2838a3a2cc232bf4a8234f642b7c2d75'),
        (11, 's08-delete-explicit-folder-only', '30b028b3ba4a07026ce5d00747306e167ab04f09ff99fd8ba29aecd01c85e949',
         '121137164c27d5f262d0a751cc7a095fd9579461c598f61bce59c517cf9fece5',
         '0abed79b1b14b8201b0c6e7bd075cb2e2838a3a2cc232bf4a8234f642b7c2d75'),
    )

    def test_real_seams_four_marked_cells(self):
        def sha(text):
            return hashlib.sha256(text.encode()).hexdigest()
        text = (ROOT / SEAMS).read_bytes().decode('utf-8')
        lines = text.split('\n')
        columns, positional = source_cells.wire_headers(ROOT)[Path(SEAMS)]
        self.assertEqual((columns, positional), (['scenario', 'step', 'request', 'expect'], True))
        names, rows, errors = source_cells.table(text, columns, positional)
        self.assertEqual((names, errors), (('request',), []))
        # one declaration first, the two former comment lines after it, then exactly the data lines of SEAMS_CELLS
        self.assertEqual(lines[0], '# cell-json: request')
        self.assertEqual([n for n, line in enumerate(lines, 1) if line.startswith('#')], [1, 2, 3])
        self.assertEqual([n for n, line in enumerate(lines, 1) if line and not line.startswith('#')],
                         [cell[0] for cell in self.SEAMS_CELLS])
        self.assertEqual(lines[-1], '')
        self.assertEqual([line for line, _ in rows], [cell[0] for cell in self.SEAMS_CELLS])
        # the proof rows of this table: exactly the request cells of SEAMS_CELLS, before = decoded
        manifest = (ROOT / 'Platform/common/data/cell-json-sha256.tsv').read_bytes().decode('utf-8')
        proof = {}
        for line in manifest.split('\n'):
            cells = line.split('\t')
            if cells[0] == SEAMS:
                self.assertNotIn((cells[1], cells[2]), proof)
                proof[(cells[1], cells[2])] = tuple(cells[3:])
        self.assertEqual(set(proof), {(str(cell[0]), 'request') for cell in self.SEAMS_CELLS})
        for (number, scenario, source_sha, decoded_sha, expect_sha), (line, row) in zip(self.SEAMS_CELLS, rows):
            with self.subTest(line=number):
                raw = lines[number - 1].split('\t')
                self.assertEqual(len(raw), 4)
                self.assertEqual(sha(raw[2]), source_sha)                 # the marked source cell, byte-exact
                self.assertEqual(json.loads(raw[2]), row['request'])      # decoded once, by the existing decoder
                self.assertEqual(sha(row['request']), decoded_sha)        # = the former raw cell before marking
                self.assertEqual(proof[(str(number), 'request')], (decoded_sha, decoded_sha))
                with self.assertRaises(ValueError):                       # no second decoding: the value is not JSON
                    source_cells.decode(row['request'])
                self.assertEqual(row, dict(scenario=raw[0], step=raw[1], request=row['request'], expect=raw[3]))
                self.assertEqual((raw[0], raw[1], sha(raw[3])), (scenario, '1', expect_sha))   # unmarked cells untouched


if __name__ == '__main__':
    unittest.main()
