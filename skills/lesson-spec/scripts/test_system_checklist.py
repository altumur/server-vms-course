"""The system checklist (ADR-0130 Addendum (19) п. 6): an optional h2 after the readiness checklist in both languages;
its ids are checklist ids (id-map, ru↔en) and carry no stage of stages.tsv."""
import tempfile
import unittest
from pathlib import Path

import en_mirror
from check_spec import SYSTEM_EN, SYSTEM_RU, Check

ROOT = Path(__file__).resolve().parents[3]
RU = ROOT / "Platform/01-store/ru/spec/01.1-store.norms.md"
EN = ROOT / "Platform/01-store/spec/01.1-store.norms.md"


class StageAndSystem(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="system-checklist-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "Platform/01-store"
        (self.home / "spec").mkdir(parents=True)
        (self.home / "forms").mkdir()
        (self.home / "spec/01.1-store.norms.md").write_text(
            "## Readiness checklist\n\n- [ ] **P/01.1-01** First item.\n\n"
            f"## {SYSTEM_EN}\n\n- [ ] **P/01.1-02** Needs a host.\n", encoding="utf-8")

    def stages(self, cell):
        (self.home / "forms/stages.tsv").write_text(f"n\tstage\tnorms\tgate\n1\ts1\t{cell}\tbuild\n", encoding="utf-8")
        result = Check(self.root, scope="platform")
        result.stage_norms(self.home, "P/01")
        return result.errors

    def test_system_item_needs_no_stage(self):
        self.assertEqual(self.stages("P/01.1-01"), [])

    def test_system_item_at_a_stage_refuses(self):
        errors = self.stages("P/01.1-01; P/01.1-02")
        self.assertTrue(any("P/01.1-02 is a system checklist item" in e for e in errors), errors)


class NormsOutline(unittest.TestCase):
    def norms(self, text):
        result = Check(ROOT, scope="platform")
        ids = result.norms(Path("x.norms.md"), text, "P/01.1", allow_empty=True)
        return ids, result.errors, result.system_ids

    BASE = "".join(f"## N{i} x\n\ntext\n\n" for i in range(6)) + "## Решает реализация\n\nx\n\n"

    def test_system_section_after_readiness_counts_its_ids(self):
        ids, errors, system = self.norms(self.BASE + "## Чеклист готовности\n\n- [ ] **P/01.1-01** a\n\n"
                                         f"## {SYSTEM_RU}\n\n- [ ] **P/01.1-02** b\n")
        self.assertEqual(ids, ["P/01.1-01", "P/01.1-02"])
        self.assertEqual(system, {"P/01.1-02"})
        self.assertEqual(errors, [])

    def test_system_section_before_readiness_refuses(self):
        _, errors, _ = self.norms(self.BASE + f"## {SYSTEM_RU}\n\n- [ ] **P/01.1-02** b\n\n"
                                  "## Чеклист готовности\n\n- [ ] **P/01.1-01** a\n")
        self.assertTrue(any("comes once, after" in e for e in errors), errors)


class PairMirror(unittest.TestCase):
    def test_section_in_one_language_only_refuses(self):
        ru, en = RU.read_text(encoding="utf-8"), EN.read_text(encoding="utf-8")
        self.assertEqual(en_mirror.compare(ru, en, RU, EN, ROOT), [])
        en2 = en.rstrip("\n") + f"\n\n## {SYSTEM_EN}\n\n- [ ] **P/01.1-99** Needs a host.\n"
        errors = en_mirror.compare(ru, en2, RU, EN, ROOT)
        self.assertTrue(errors, "a system checklist only in the English source must be refused")


if __name__ == "__main__":
    unittest.main()
