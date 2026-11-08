import hashlib
from pathlib import Path
import tempfile
import unittest

import machine_source


class ExplicitCodeMaps(unittest.TestCase):
    def test_mixed_map_keeps_data_and_bytes_and_editable_ownership(self):
        home = Path(tempfile.mkdtemp(prefix='machine-map-control-'))
        producer = home / 'producer.py'
        producer.write_text('SOURCE = 1\n')
        source = home / 'schema.json'
        source.write_text('{"description":"// preserve data"}\n')
        code = b'// explanatory\npackage demo\nconst url = "http://host//literal"\n'
        data = b'// literal fixture\n'
        result = machine_source.go_files({'closed.go': code, 'yours.go': code, 'form.tsv': data}, generator=producer, sources=[source], root=home, editable=['yours.go'])
        self.assertIsInstance(result['closed.go'], bytes)
        self.assertEqual(result['form.tsv'], data)
        self.assertIn(b'DO NOT EDIT', result['closed.go'])
        self.assertNotIn(b'DO NOT EDIT', result['yours.go'])
        self.assertNotIn(b'explanatory', result['yours.go'])
        self.assertIn(b'http://host//literal', result['closed.go'])
        self.assertIn(hashlib.sha256(source.read_bytes()).hexdigest().encode(), result['closed.go'])

    def test_explicit_code_roster_retains_go_suffixed_fixture_bytes(self):
        home = Path(tempfile.mkdtemp(prefix='machine-map-code-roster-'))
        producer = home/'producer.py'
        producer.write_text('SOURCE = 1\n')
        invalid_fixture = b'// literal malformed input\nfunc not valid @\n'
        result = machine_source.go_files({'go/library.go': b'package sample\n', 'vectors/input.go': invalid_fixture},
                generator=producer, sources=[], root=home, code_paths=['go/library.go'])
        self.assertEqual(result['vectors/input.go'], invalid_fixture)
        self.assertIn(b'DO NOT EDIT', result['go/library.go'])

    def test_actual_shared_fixture_provenance_names_physical_carrier(self):
        import gen_tests
        paths = gen_tests.sources('vectors')
        declared = gen_tests.ROOT / 'Platform/common/vectors/secret-in/fields.yaml'
        self.assertTrue(declared.is_file())
        self.assertIn(declared, paths)
        self.assertNotIn(gen_tests.ROOT / 'Platform/common/vectors/log-mask/fields.yaml', paths)
        self.assertTrue(all(p.is_file() for p in paths))

    def test_actual_missing_input_is_not_silently_omitted(self):
        home = Path(tempfile.mkdtemp(prefix='machine-map-missing-'))
        with self.assertRaises(FileNotFoundError):
            machine_source.go_files({'sample.go': 'package sample\n'}, generator=Path(__file__), sources=[home/'missing.json'], root=home)


if __name__ == '__main__':
    unittest.main()
