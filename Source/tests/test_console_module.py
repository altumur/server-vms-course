"""The platform's console module is ONE file for the course and the product (КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md §11, step 6:
«модуль переносится как есть»): the course's `w2cplatform/console.js`, its look `console.css` and the platform's page
`console.html` are the product's `vmsworker/w2cplatform/…`, byte for byte. What is read of the product is its committed
`main` (`productdir.py`); without the product's checkout beside the course the module is skipped: the course builds alone.

What differs today is the debt, `testdata/console_module_debt.txt` — the lines of a change the course leads with and
the product has not taken yet (`step3-module-diff.md` says what each is for), one line per line of the diff:

    <file> | <+ the course's line, - the product's> | <sha1 of the line, stripped, first eight hex digits> | <text>

It only shrinks: a difference not in the debt fails (made good on one side or the other, never written down), and so
does a line of the debt no longer true — `W2C_CONSOLE_SHRINK=1` rewrites the file without those, and never adds one."""
from __future__ import annotations

import difflib
import hashlib
import os
import re
from collections import Counter

import pytest

from tests.productdir import SOURCE, product_file

FILES = ("console.js", "console.css", "console.html")
PRODUCT = "vmsworker/w2cplatform/"                      # on the product's `main`, relative to its root
DEBT = os.path.join(SOURCE, "tests", "testdata", "console_module_debt.txt")
HEAD = ("# console_module_debt.txt — the lines the course's copy of the platform's console module differs from the product's\n"
        "# by (test_console_module.py): a change the course leads with, until the product takes it. It only shrinks.\n"
        "#   <file> | <+ course, - product> | <sha8 of the line, stripped> | <text, cut>   # ADR-NNNN «the other side's owner»\n")
# A debt line exists only by a decision, as a line of `spec_parity_debt.txt` (СЕССИИ.md §1.7): its tail names the ADR and
# the owner of the side that closes it (ADR-0019, the owner's addition of 2026-10-07). The line's text is a line of JS,
# CSS or HTML and may hold a `#` of its own: the tail is the one at its END.
_TAIL = re.compile(r"\s+(#\s*ADR-\d{4}\b[^«]*«[^»]+»)\s*$")
_THEIRS = {f: product_file(PRODUCT + f) for f in FILES}
pytestmark = pytest.mark.skipif(any(v is None for v in _THEIRS.values()),
                                reason="no product beside the course (W2C_PRODUCT_DIR), or no `main` there: the console "
                                       "module is not compared")


def _sha8(line: str) -> str:
    return hashlib.sha1(line.strip().encode("utf-8")).hexdigest()[:8]


def differences() -> list[tuple[str, str, str, str]]:
    """`(file, sign, sha8, text)` for every line the course's copy and the product's `main` differ by, in order."""
    out = []
    for f in FILES:
        theirs = _THEIRS[f].decode("utf-8").split("\n")
        with open(os.path.join(SOURCE, "w2cplatform", f), encoding="utf-8") as fh:
            ours = fh.read().split("\n")
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, theirs, ours, autojunk=False).get_opcodes():
            if tag == "equal":
                continue
            out += [(f, "-", _sha8(x), x.strip()[:100]) for x in theirs[i1:i2]]
            out += [(f, "+", _sha8(x), x.strip()[:100]) for x in ours[j1:j2]]
    return out


def read_debt() -> list[tuple[str, str, str, str, str]]:
    """`(file, sign, sha8, text, tail)` of every line of the debt; `tail` is "" for a line that names no decision."""
    out = []
    if not os.path.exists(DEBT):
        return out
    with open(DEBT, encoding="utf-8") as fh:
        for line in fh:
            if line.strip() and not line.startswith("#"):
                line = line.rstrip("\n")
                m = _TAIL.search(line)
                tail = m.group(1) if m else ""
                f, sign, sha, text = (p.strip() for p in (line[:m.start()] if m else line).split(" | ", 3))
                out.append((f, sign, sha, text, tail))
    return out


def _debt_line(d) -> str:
    return " | ".join(d[:4]) + (f"   {d[4]}" if d[4] else "") + "\n"


def test_the_course_copy_of_the_console_module_is_the_products_but_for_the_debt():
    found, debt = differences(), read_debt()
    have, owed = Counter(d[:3] for d in found), Counter(d[:3] for d in debt)
    new = [d for d in found if have[d[:3]] > owed[d[:3]]]
    gone = [d for d in debt if owed[d[:3]] > have[d[:3]]]
    if gone and not new and os.environ.get("W2C_CONSOLE_SHRINK") == "1":
        left, keep = Counter(owed), []
        for d in debt:                                   # each line as many times as it is still found
            if left[d[:3]] > have[d[:3]]:
                left[d[:3]] -= 1
                continue
            keep.append(d)
        with open(DEBT, "w", encoding="utf-8") as fh:
            fh.write(HEAD + "".join(_debt_line(d) for d in keep))
        gone = []
    assert not new, ("the course's console module differs from the product's main where the debt says nothing — make it "
                     "good on one side or the other: " + "; ".join(f"{f} {s} {t}" for f, s, _, t in new[:10]))
    assert not gone, ("the debt says what is no longer so (the product took it, or the course dropped it) — "
                      "W2C_CONSOLE_SHRINK=1 rewrites it: " + "; ".join(f"{f} {s} {t}" for f, s, _, t in gone[:10]))


def test_every_debt_line_of_the_console_module_names_its_decision_and_the_other_sides_owner():
    """ADR-0019, the owner's addition of 2026-10-07: a line of `console_module_debt.txt` carries `# ADR-NNNN «owner»`
    after its text, the owner of the side that closes it, as a line of `spec_parity_debt.txt` does (СЕССИИ.md §1.7). A
    line without it is red. And the tail is told from a `#` of the line's own text: only the one at its end counts."""
    bare = [_debt_line(d).rstrip("\n") for d in read_debt() if not d[4]]
    assert not bare, "a debt line with no decision — `   # ADR-NNNN «owner»` after its text:\n  " + "\n  ".join(bare)
    m = _TAIL.search("console.css | + | 0123abcd | a { color: #fff; }   # ADR-0019 «Консоль»")
    assert m and m.group(1) == "# ADR-0019 «Консоль»"
    assert _TAIL.search("console.css | + | 0123abcd | a { color: #fff; }") is None
