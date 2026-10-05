"""The VMS page's core is the product's (the boundary's step 3: «copy with a check»). `vms/shell.html` of the course is
the course's own page, written by its lessons over the platform's console module; but how it reaches the bytes — the
holders' doors, the timeline merged from every door and every place, what yields to what, the pieces, the live picture —
is ONE code for the course and the product: `whereAt`, `doorOf`, `doorFetch`, `yieldCut`, `loadTimeline`, `segmentURL`,
`play`, `playNext`, `negotiateLive`, `stopLive`, each the product's `vmsworker/vms/shell.html` on its `main`
(`productdir.py`), between the course page's two «core» lines. Without the product's checkout beside the course this is
skipped: the course builds alone.

What differs is the debt, `testdata/shell_core_debt.txt` — where the course leads and the product has not followed yet
(the places a recording may lie on are the rows of the table rec's spec names, `places.table`, read at `/rec/<table>`;
the product still takes its cached `vols` when the table is called `volumes`), one line per line of the diff:

    <function> | <+ the course's line, - the product's> | <sha1 of the line, stripped, first eight hex digits> | <text>

It only shrinks: a difference not in the debt fails, and so does a line of the debt no longer true —
`W2C_SHELL_CORE_SHRINK=1` rewrites the file without those, and never adds one."""
from __future__ import annotations

import difflib
import hashlib
import os
import re
from collections import Counter

import pytest

from tests.productdir import SOURCE, product_file

CORE = ("whereAt", "doorOf", "doorFetch", "yieldCut", "loadTimeline", "segmentURL", "play", "playNext",
        "negotiateLive", "stopLive")
PRODUCT = "vmsworker/vms/shell.html"
OURS = os.path.join(SOURCE, "vms", "shell.html")
BEGIN, END = "// ── core: COPY WITH A CHECK", "// ── end of core"
DEBT = os.path.join(SOURCE, "tests", "testdata", "shell_core_debt.txt")
HEAD = ("# shell_core_debt.txt — the lines the core of the course's VMS page (vms/shell.html) differs from the product's by\n"
        "# (test_shell_core.py): where the course leads, until the product follows. It only shrinks.\n"
        "#   <function> | <+ course, - product> | <sha8 of the line, stripped> | <text, cut>\n")
_THEIRS = product_file(PRODUCT)
pytestmark = pytest.mark.skipif(_THEIRS is None, reason="no product beside the course (W2C_PRODUCT_DIR), or no `main` "
                                                        "there: the VMS page's core is not compared")


def cut(text: str, name: str) -> list[str] | None:
    """The lines of the top-level function `name`: its first line, the indented ones after it, its closing `}`."""
    lines = text.split("\n")
    head = re.compile(r"^(async )?function " + re.escape(name) + r"\(")
    for i, line in enumerate(lines):
        if head.match(line):
            out, j = [line], i + 1
            while j < len(lines) and (lines[j].startswith((" ", "\t")) or lines[j] == ""):
                out.append(lines[j])
                j += 1
            if j < len(lines) and lines[j] == "}":
                out.append("}")
            while out and out[-1] == "":
                out.pop()
            return out
    return None


def _sha8(line: str) -> str:
    return hashlib.sha1(line.strip().encode("utf-8")).hexdigest()[:8]


def _ours() -> str:
    with open(OURS, encoding="utf-8") as f:
        return f.read()


def differences() -> list[tuple[str, str, str, str]]:
    """`(function, sign, sha8, text)` for every line the course's core and the product's `main` differ by, in order."""
    theirs, ours = _THEIRS.decode("utf-8"), _ours()
    out = []
    for name in CORE:
        a, b = cut(theirs, name), cut(ours, name)
        assert a is not None, f"the product's page has no function {name}: the core changed there — agree it first"
        assert b is not None, f"the course's page has no function {name}"
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if tag != "equal":
                out += [(name, "-", _sha8(x), x.strip()[:100]) for x in a[i1:i2]]
                out += [(name, "+", _sha8(x), x.strip()[:100]) for x in b[j1:j2]]
    return out


def read_debt() -> list[tuple[str, str, str, str]]:
    out = []
    if os.path.exists(DEBT):
        with open(DEBT, encoding="utf-8") as fh:
            for line in fh:
                if line.strip() and not line.startswith("#"):
                    out.append(tuple(p.strip() for p in line.rstrip("\n").split(" | ", 3)))
    return out


def test_the_core_functions_stand_in_the_marked_block_of_the_course_page():
    """Each core function is between the page's two «core» lines, and nothing but them and comments is there: what is
    checked against the product is one place, and a function moved out of it would leave the check silently."""
    page = _ours()
    assert page.count(BEGIN) == 1 and page.count(END) == 1
    block = page[page.index(BEGIN):page.index(END)].split("\n", 1)[1]
    for name in CORE:
        assert re.search(r"^(async )?function " + re.escape(name) + r"\(", block, re.M), f"{name} is not in the core"
        assert len(re.findall(r"^(async )?function " + re.escape(name) + r"\(", page, re.M)) == 1, f"{name} twice"
    left = block
    for name in CORE:
        left = left.replace("\n".join(cut(page, name)), "")
    assert all(not ln.strip() or ln.lstrip().startswith("//") for ln in left.split("\n")), \
        "the core block holds more than the core's functions"


def test_the_core_of_the_course_page_is_the_products_but_for_the_debt():
    found, debt = differences(), read_debt()
    have, owed = Counter(d[:3] for d in found), Counter(d[:3] for d in debt)
    new = [d for d in found if have[d[:3]] > owed[d[:3]]]
    gone = [d for d in debt if owed[d[:3]] > have[d[:3]]]
    if gone and not new and os.environ.get("W2C_SHELL_CORE_SHRINK") == "1":
        left, keep = Counter(owed), []
        for d in debt:
            if left[d[:3]] > have[d[:3]]:
                left[d[:3]] -= 1
                continue
            keep.append(d)
        with open(DEBT, "w", encoding="utf-8") as fh:
            fh.write(HEAD + "".join(" | ".join(d) + "\n" for d in keep))
        gone = []
    assert not new, ("the core of the course's VMS page differs from the product's main where the debt says nothing — "
                     "make it good on one side or the other: " + "; ".join(f"{f} {s} {t}" for f, s, _, t in new[:10]))
    assert not gone, ("the debt says what is no longer so (the product followed, or the course went back) — "
                      "W2C_SHELL_CORE_SHRINK=1 rewrites it: " + "; ".join(f"{f} {s} {t}" for f, s, _, t in gone[:10]))
