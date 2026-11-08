import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_kit


class DeliveryCodeBoundary(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix='machine-delivery-control-'))
        self.source = self.home / 'original.go'
        self.raw = b'// original explanatory prose\npackage sample\nconst url = "http://host//literal"\nfunc Mine() {}\n'
        self.source.write_bytes(self.raw)

    def deliver(self, data=None, editable=False):
        with patch.object(build_kit, 'ROOT', self.home):
            return build_kit.machine_delivery('sample.go', self.raw if data is None else data,
                    'handwritten', 'adapter', 'original.go', editable=editable)

    def test_source_identity_hashes_original_carrier_not_rewritten_module(self):
        rewritten = self.raw.replace(b'host', b'destination')
        actual = self.deliver(rewritten)
        self.assertIn(hashlib.sha256(self.raw).hexdigest().encode(), actual)
        self.assertNotIn(b'original explanatory prose', actual)
        self.assertIn(b'http://destination//literal', actual)
        self.assertIn(b'DO NOT EDIT', actual)

    def test_editable_baseline_and_seed_keep_model_bytes_without_closed_marker(self):
        baseline = self.deliver(editable=True)
        self.assertNotIn(b'DO NOT EDIT', baseline)
        seed, dst = self.home/'seed', self.home/'dst'
        seed.mkdir();dst.mkdir()
        owned = seed/'sample.go';owned.write_bytes(baseline)
        (seed/'kit.manifest.json').write_text(json.dumps({'files':[{'path':'sample.go','sha256':build_kit.sha256(baseline),'editable':True}]}))
        taken,kept,refreshed = build_kit.seed_rule(dst, seed)
        self.assertFalse(taken(dst/'sample.go', baseline))
        self.assertEqual(refreshed, ['sample.go'])
        mine = baseline + b'// model comment preserved\n'
        owned.write_bytes(mine)
        self.assertTrue(taken(dst/'sample.go', baseline))
        self.assertEqual(owned.read_bytes(), mine)
        self.assertEqual(kept, ['sample.go'])

    def test_publicprobes_vendor_and_noncode_are_exact_even_without_local_source(self):
        cases = [('probe.py','handwritten','publicprobes'),('third.go','vendored','loader'),('SOURCE.txt','generated','kit')]
        for name, origin, component in cases:
            with self.subTest(name=name):
                data=b'// literal immutable Source or third-party bytes\n'
                self.assertEqual(build_kit.machine_delivery(name,data,origin,component,'absent/source'),data)

    def test_code_without_actual_identity_refuses(self):
        with patch.object(build_kit,'ROOT',self.home), self.assertRaisesRegex(build_kit.KitError, 'identity is absent'):
            build_kit.machine_delivery('a.go',self.raw,'handwritten','adapter','absent.go')


if __name__ == '__main__':
    unittest.main()
