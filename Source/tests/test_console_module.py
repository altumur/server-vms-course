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
from collections import Counter

import pytest

from tests.productdir import SOURCE, product_file

FILES = ("console.js", "console.css", "console.html")
PRODUCT = "vmsworker/w2cplatform/"                      # on the product's `main`, relative to its root
DEBT = os.path.join(SOURCE, "tests", "testdata", "console_module_debt.txt")
HEAD = ("# console_module_debt.txt — the lines the course's copy of the platform's console module differs from the product's\n"
        "# by (test_console_module.py): a change the course leads with, until the product takes it. It only shrinks.\n"
        "#   <file> | <+ course, - product> | <sha8 of the line, stripped> | <text, cut>\n")
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


def read_debt() -> list[tuple[str, str, str, str]]:
    out = []
    if not os.path.exists(DEBT):
        return out
    with open(DEBT, encoding="utf-8") as fh:
        for line in fh:
            if line.strip() and not line.startswith("#"):
                f, sign, sha, text = (p.strip() for p in line.rstrip("\n").split(" | ", 3))
                out.append((f, sign, sha, text))
    return out


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
            fh.write(HEAD + "".join(" | ".join(d) + "\n" for d in keep))
        gone = []
    assert not new, ("the course's console module differs from the product's main where the debt says nothing — make it "
                     "good on one side or the other: " + "; ".join(f"{f} {s} {t}" for f, s, _, t in new[:10]))
    assert not gone, ("the debt says what is no longer so (the product took it, or the course dropped it) — "
                      "W2C_CONSOLE_SHRINK=1 rewrites it: " + "; ".join(f"{f} {s} {t}" for f, s, _, t in gone[:10]))
