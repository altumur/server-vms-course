"""Сборка пакетов P/03 и P/04 (build_kit --lesson 03-worker / 04-controller; ADR-0125 доп. (5)): части flags, refusals,
stagetests, машины, families, vectors; пакет компилируется под модулем урока, go vet чист; закрытые тесты машин зелёные, тесты этапов —
красные на заглушках (без паники); editable — ровно адаптер портов и действия машин; KIT.md — справка каждой части;
чужая машина — отказ; P/01, P/02 не задеты (их тесты — test_kit, test_kit_p02)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
NORMGEN = HERE.parent
GOENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
KITS = {"03-worker": ["flags", "refusals", "stagetests", "slot-capture", "families", "vectors"],
        "04-controller": ["flags", "refusals", "stagetests", "slot-fate", "slot-release", "families", "vectors"],
        "06-console": ["door", "families", "vectors"]}  # P/06 до форм: дверь 3а; 3б и части по формам — позже


class KitLessons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("go"):
            raise unittest.SkipTest("go is not in PATH")
        cls.tmp = Path(tempfile.mkdtemp(prefix="kit-lessons-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_kits(self):
        for lesson, parts in KITS.items():
            with self.subTest(lesson=lesson):
                dst = self.tmp / lesson
                cmd = [sys.executable, str(HERE / "build_kit.py"), str(dst), "--lesson", lesson]
                done = subprocess.run(cmd + sum((["--part", p] for p in parts), []), capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stderr)
                man = json.loads((dst / "kit.manifest.json").read_text())
                self.assertEqual(sorted(man["parts"]), sorted(parts))
                self.assertEqual(sorted(man["provenance"]), sorted(parts))
                for f in man["files"]:
                    own = "impl/" in f["path"] or ("/lessonadapter/" in f["path"] and not f["path"].endswith("lessonadapter.go")) \
                        or ("/vectoradapter/" in f["path"] and not f["path"].endswith("vectoradapter.go"))
                    self.assertEqual(bool(f.get("editable")), own, f["path"])
                kit_md = (dst / "KIT.md").read_text()
                titles = ("Part `vectors`", "draft (tools/normgen/wire_draft.py)") + (("Part `door` (3a)",) if lesson == "06-console" else (
                    "Part `flags`: the process inputs", "Part `stagetests`: the stage tests of the lesson over CALL ports",
                    "Part `refusals`"))
                for title in titles:
                    self.assertIn(title, kit_md)
                mod = dst / lesson
                (mod / "go.mod").write_text(f"module {man['module']}\n\ngo 1.22\n")
                done = subprocess.run(["go", "vet", "./..."], cwd=mod, capture_output=True, text=True, env=GOENV)
                self.assertEqual(done.returncode, 0, done.stderr)
                machines = [f"./internal/{p.replace('-', '')}/" for p in parts if p.startswith("slot-")]
                if machines:
                    done = subprocess.run(["go", "test", "-count=1", *machines], cwd=mod, capture_output=True, text=True,
                                          env=GOENV)
                    self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                if "stagetests" in parts:
                    done = subprocess.run(["go", "test", "-count=1", "./internal/stagetests/"], cwd=mod,
                                          capture_output=True, text=True, env=GOENV)
                    self.assertNotEqual(done.returncode, 0)
                    self.assertNotIn("panic:", done.stdout)


if __name__ == "__main__":
    unittest.main()
