"""Probe of ADR-0124 addendum (2): a link of history to a canonical path with a Russian anchor → the mirror `ru/…`.

    python tools/layout/test_layout.py
"""
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import links as L  # noqa: E402
import migrate as M  # noqa: E402

LESSON = "Platform/01-x"
ADR = "decisions/0001-x.md"
FILES = {
    f"{LESSON}/spec/a.md": "# A\n\n## N0. Vocabulary\n\ntext\n",
    f"{LESSON}/ru/spec/a.md": "# А\n\n## Н0. Словарь слов\n\nтекст\n",
    f"{LESSON}/spec/b.md": "# B\n\n## Words\n",
    f"{LESSON}/ru/spec/b.md": "# Б\n\n## Слова\n",
    ADR: (
        "Russian anchor: [н0](../Platform/01-x/spec/a.md#н0-словарь-слов).\n"
        "No anchor: [a](../Platform/01-x/spec/a.md).\n"
        "English anchor: [n0](../Platform/01-x/spec/a.md#n0-vocabulary).\n"
        "Gone: [b](../Platform/01-x/en/b.en.md#words).\n"
        "Into ru already: [ru](../Platform/01-x/ru/spec/a.md#н0-словарь-слов).\n"
    ),
}
WANT = (
    "Russian anchor: [н0](../Platform/01-x/ru/spec/a.md#н0-словарь-слов).\n"
    "No anchor: [a](../Platform/01-x/spec/a.md).\n"
    "English anchor: [n0](../Platform/01-x/spec/a.md#n0-vocabulary).\n"
    "Gone: [b](../Platform/01-x/spec/b.md#words).\n"
    "Into ru already: [ru](../Platform/01-x/ru/spec/a.md#н0-словарь-слов).\n"
)


class HistoryLinks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for rel, text in FILES.items():
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text(text, encoding="utf-8")
        L.forget()

    def tearDown(self):
        L.forget()
        self.tmp.cleanup()

    def rewriter(self):
        rw = M.Rewriter(self.root, {LESSON})
        rw.gone = {f"{LESSON}/en/b.en.md": f"{LESSON}/spec/b.md"}   # the table of the probe, not the course's
        return rw

    def test_history_rewrite(self):
        rw = self.rewriter()
        self.assertEqual(M.file_class(ADR, "", {LESSON}), "history")
        self.assertEqual(rw.rewrite(ADR, table=False), WANT)
        self.assertEqual(rw.stats["links"], 2)
        self.assertEqual(rw.problems, [])

    def test_idempotent(self):
        (self.root / ADR).write_text(WANT, encoding="utf-8")
        self.assertIsNone(self.rewriter().rewrite(ADR, table=False))

    def test_live_text_not_touched_by_the_rule(self):
        note = "NOTE.md"                                  # other: an anchor of the source stays, no ru/
        (self.root / note).write_text("[a](Platform/01-x/spec/a.md#n0-vocabulary)\n", encoding="utf-8")
        self.assertIsNone(self.rewriter().rewrite(note, table=False))

    def test_check(self):
        adr = self.root / ADR
        why = {h: L.broken(adr, h, self.root) for h in L.judged(adr.read_text(encoding="utf-8"))}
        self.assertEqual(why["../Platform/01-x/spec/a.md#н0-словарь-слов"],
                         "history: Russian anchor, into Platform/01-x/ru/spec/a.md")
        self.assertIsNone(why["../Platform/01-x/spec/a.md"])
        self.assertIsNone(why["../Platform/01-x/spec/a.md#n0-vocabulary"])
        self.assertEqual(why["../Platform/01-x/en/b.en.md#words"], "no target")
        (self.root / ADR).write_text(WANT, encoding="utf-8")
        bad, _ = L.check_tree(self.root)
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
