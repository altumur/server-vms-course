"""Words @row-spoil and @stderr ~ of the installation tables (README of the common acceptance, P/02 P02.33)."""

from pathlib import Path
import tempfile
import unittest

from v7.vectors import Chapter, split_expect

HEADER = "case\tputs\texpect"


class PutsWords(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.acc = self.root / "acc"
        (self.acc / "puts").mkdir(parents=True)
        for name in ("first", "second"):
            (self.acc / "puts" / (name + ".subsystem.yaml")).write_text("name: %s\n" % name)

    def errors(self, rows):
        (self.acc / "puts.tsv").write_text("# p\n%s\n%s" % (HEADER, "".join(r + "\n" for r in rows)))
        chapter = Chapter(self.root)
        chapter.puts(self.acc)
        return [m for _, m in chapter.errors]

    def test_words_accepted(self):
        self.assertEqual(self.errors(["spoil\tfirst @row-spoil yaml first\t2 1 @stderr ~yaml ~platform/manifest",
                                      "two\tsecond\t0 1"]), [])

    def test_near_typos_refused(self):
        for rows, text in ((["s\tfirst @row-spoli yaml first\t2 1"], "directives"),
                           (["s\tfirst @row-spoil first\t2 1"], "directives"),
                           (["s\tfirst @row-spoil Yaml first\t2 1"], "directives"),
                           (["s\tfirst\t2 1 @stdrr ~x"], "expect is"),
                           (["s\tfirst\t2 1 @stderr x"], "followed by ~"),
                           (["s\tfirst\t2 1 @stderr ~a ~"], "not empty"),
                           (["s\tfirst\t0 1 @stderr ~a"], "only with a code other than 0")):
            errors = self.errors(rows + ["two\tsecond\t0 1"])
            self.assertTrue(any(text in m for m in errors), (rows, text, errors))

    def test_split_expect(self):
        m, subs = split_expect("2 - @stderr ~key of the view ~rev")
        self.assertEqual((m.group(1), m.group(2), subs), ("2", "-", ["key of the view", "rev"]))
        self.assertEqual(split_expect("0 1")[1], [])
        self.assertIsNone(split_expect("2 1 @stderr")[0])


if __name__ == "__main__":
    unittest.main()
