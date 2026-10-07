"""The course and the product describe the same subsystems by one YAML (the user's decision, «спеки yaml одинаковые»).
Held here from the course's side, as the product holds it from its own (`vmsworker/vms/spec_parity_test.go`): the key
paths of each spec both have are the same, and what differs today is the debt in `testdata/spec_parity_debt.txt` — a
byte copy of the product's file, which only shrinks; and every spec of the product loads with the course's loader,
what it refuses today being the debt in `testdata/spec_load_debt.txt`, which only shrinks too. What is read of the product is its committed `main` (`productdir.py`), never a working tree a
product author is editing; without the product's checkout beside the course the module is skipped: the course builds
alone.

`W2C_SPEC_SHRINK=1` rewrites both debts without the lines no longer true; nothing ever adds one — a new difference is
made good, on one side or the other, not written down."""
from __future__ import annotations

import copy
import glob
import os
import re

import pytest

from tests.productdir import SOURCE, product_file, product_files
from w2cplatform import specyaml

PRODUCT_SPECS = "vmsworker/vms"                        # on the product's `main`, relative to its root
_THEIRS = product_files(PRODUCT_SPECS, ".subsystem.yaml")
# …and the product's TEST subsystems: its own files, not the course's (the bytes are not one — «Архитектор» 2026-10-07),
# loaded by the course's loader all the same (ADR-0012, ADR-0019: cross-load), their refusals in the load debt too
PRODUCT_TEST_SPECS = "vmsworker/w2cplatform/testdata"
_THEIR_TESTSUBS = product_files(PRODUCT_TEST_SPECS, ".subsystem.yaml")
pytestmark = pytest.mark.skipif(not _THEIRS, reason="no product beside the course (W2C_PRODUCT_DIR), or no `main` "
                                                    "there: the specs are not compared")

COURSE_SPECS = os.path.join(SOURCE, "vms")
TESTDATA = os.path.join(SOURCE, "tests", "testdata")
PARITY_DEBT = os.path.join(TESTDATA, "spec_parity_debt.txt")
LOAD_DEBT = os.path.join(TESTDATA, "spec_load_debt.txt")
# The product's writer's head (`W2C_SPEC_PARITY_WRITE`): the two files are one, byte for byte.
PARITY_HEAD = ("# spec_parity_debt.txt — the keys the course's specs and the product's differ by (spec_parity_test.go).\n"
               "# A line goes when both sides have the key, or neither; a new difference is not written here but made good.\n")
LOAD_HEAD = ("# spec_load_debt.txt — the key paths of the product's specs the course's loader refuses (test_spec_parity.py),\n"
             "# `<spec>:<key path>   # ADR-NNNN «owner»`. A line goes when the course reads the key or the product drops it;\n"
             "# one is added only where a decision brings a key to one side first: its ADR number and the owner of the other\n"
             "# side, who closes it (СЕССИИ.md §1.7).\n")
# СЕССИИ.md §1.7: every line of either debt carries its decision and the other side's owner — `# ADR-NNNN «owner»` after
# the key. The bridge until «Паритет» marks the old lines up: a bare line is taken only if the debts held it on the day
# of §1.7 (8bb36dfd) — `testdata/debt_bare_1_7.txt`, deleted once no bare line is left; a new bare line is a failure.
_TAIL = re.compile(r"#\s*ADR-\d{4}\b[^«]*«[^»]+»")
BARE_1_7 = os.path.join(TESTDATA, "debt_bare_1_7.txt")

# The product's reading of a spec, line by line — its regular expressions, its order (`specKeyPaths`).
_KEY = re.compile(r"^([A-Za-z0-9_.\-\"']+)\s*:\s*(.*)$")
_INLINE = re.compile(r"([A-Za-z_][\w\-]*)\s*:")
_COMMENT = re.compile(r"\s+#.*$")
# under these a spec holds data — words, a JSON Schema, vendor forms — not declarations
_DATA = re.compile(r"(^|\.)(kinds|field_help|schema|secret_in)(\.|$)|^display(\.|$)")


def spec_key_paths(path: str, text: str | None = None) -> set[str]:
    """The key paths of a YAML spec, block and inline, leaving out what lies under data — as the product reads them.
    `text`: the spec's text when it is no file here (the product's `main`)."""
    out, stack = set(), []
    if text is None:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    lines = text.split("\n")
    for line in lines:
        line = _COMMENT.sub("", line.rstrip("\r"))
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if trimmed.startswith("- "):
            trimmed, indent = trimmed[2:], indent + 2
        m = _KEY.match(trimmed)
        if not m:
            continue
        key, val = m.group(1).strip("\"'"), m.group(2)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parts = [k for _, k in stack]
        if _DATA.search(".".join(parts)):
            continue
        p = ".".join(parts + [key])
        out.add(p)
        if val.startswith("{") and not _DATA.search(p):
            out |= {f"{p}.{k}" for k in _INLINE.findall(val)}
        if val == "":
            stack.append((indent, key))
    return out


def spec_list_values(text: str) -> set[str]:
    """The words a spec's lists hold, as `path[word]` — the values the key paths do not see (ADR-0019, its addition:
    `door.routes`, `heartbeat.strings`, `objects.rows`, `snapshot`, `domain.*`, `worker.*`). A list of words gives each
    word; a list of maps gives each map's `name`, or else its `field` (`metrics[].name`, `servers.status[].field`);
    what is no string is no word; nothing under data is read (`_DATA`). As the product reads it
    (`specListValues`, with its own YAML reader)."""
    out: set[str] = set()

    def walk(x, p: str) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                q = f"{p}.{k}" if p else str(k)
                if not _DATA.search(q):
                    walk(v, q)
        elif isinstance(x, list):
            for e in x:
                if isinstance(e, str):
                    out.add(f"{p}[{e}]")
                elif isinstance(e, dict):
                    w = e.get("name", e.get("field"))
                    if isinstance(w, str):
                        out.add(f"{p}[{w}]")

    walk(specyaml.loads(text, "a spec's lists") or {}, "")
    return out


def _differences() -> set[str]:
    found = set()
    for c in sorted(glob.glob(os.path.join(COURSE_SPECS, "*.subsystem.yaml"))):
        name = os.path.basename(c)
        theirs = product_file(f"{PRODUCT_SPECS}/{name}")
        if theirs is None:
            continue                                     # a subsystem only the course has
        with open(c, encoding="utf-8") as f:
            mine = f.read()
        a = spec_key_paths(c) | spec_list_values(mine)
        b = spec_key_paths(name, theirs.decode("utf-8")) | spec_list_values(theirs.decode("utf-8"))
        found |= {f"course-only {name} {p}" for p in a - b} | {f"product-only {name} {p}" for p in b - a}
    return found


def _debt(path: str, text: str | None = None) -> set[str]:
    if text is None:
        if not os.path.exists(path):
            return set()
        with open(path, encoding="utf-8") as f:
            text = f.read()
    lines = (_COMMENT.sub("", ln).strip() for ln in text.split("\n"))
    return {ln for ln in lines if ln and not ln.startswith("#")}


def _lines(path: str) -> list[tuple[str, str]]:
    """`(key, the line as written)` for every debt line of the file — its tail kept."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [(_COMMENT.sub("", ln).strip(), ln) for ln in f.read().split("\n")
                if _COMMENT.sub("", ln).strip() and not ln.startswith("#")]


def _hold(found: set[str], path: str, head: str, what: str) -> None:
    debt = _debt(path)
    fresh, gone = sorted(found - debt), sorted(debt - found)
    if gone and os.environ.get("W2C_SPEC_SHRINK"):
        keep = [ln for k, ln in _lines(path) if k in found]     # the lines still true, as written: their tails stay —
        with open(path, "w", encoding="utf-8") as f:            # read before the file is opened for writing
            f.write(head + "".join(f"{ln}\n" for ln in keep))
        gone = []
    assert not fresh, (f"{len(fresh)} new {what} — give the other side the key, or agree another; the debt is not "
                       f"added to:\n  " + "\n  ".join(fresh))
    assert not gone, (f"{len(gone)} lines of {os.path.basename(path)} are no longer true — strike them "
                      f"(W2C_SPEC_SHRINK=1):\n  " + "\n  ".join(gone))


def test_the_specs_keys_are_the_products_but_for_the_debt_and_the_debt_only_shrinks():
    """The key paths of vms, rec, live and auto (the subsystems both have; det, detjob, survey are the course's alone)
    by the product's reading: block keys and inline maps' keys, nothing under `display`, a field's `schema`, `secret_in`,
    `kinds`, `field_help`. A path on one side alone is a failure unless the debt names it; a debt line no longer true is
    a failure until it is struck."""
    _hold(_differences(), PARITY_DEBT, PARITY_HEAD, "differences of the specs' keys from the product's")


def test_every_debt_line_names_its_decision_and_the_other_sides_owner():
    """СЕССИИ.md §1.7: a debt line exists only by a decision that brought a key to one side first — `# ADR-NNNN
    «owner»` after it, the owner of the side that closes it. A bare line is taken only from the bridge (the debts on
    the day of §1.7), and the bridge goes when no bare line is left."""
    bridge = _debt(BARE_1_7) if os.path.exists(BARE_1_7) else set()
    bare = [f"{os.path.basename(p)}: {ln}" for p in (PARITY_DEBT, LOAD_DEBT) for k, ln in _lines(p)
            if not _TAIL.search(ln) and k not in bridge]
    assert not bare, ("a debt line with no decision — `   # ADR-NNNN «owner»` after the key (СЕССИИ.md §1.7):\n  "
                      + "\n  ".join(bare))
    left = {k for p in (PARITY_DEBT, LOAD_DEBT) for k, ln in _lines(p) if not _TAIL.search(ln)}
    assert not bridge or left, ("no bare line is left in the debts: delete testdata/debt_bare_1_7.txt and its reading")


def test_the_parity_debt_is_the_products_file_byte_for_byte():
    """One debt for both sides: the course's file is the product's, byte for byte — whenever the product's is true of the
    specs as they stand. While the product's lags (its own test fails: the course's specs moved since it was written),
    the comparison waits for it and says what the product's file is short of and holds too many of."""
    raw = product_file(f"{PRODUCT_SPECS}/spec_parity_debt.txt")
    if raw is None:
        print("  the product keeps no spec_parity_debt.txt: nothing to compare")
        return
    found, theirs = _differences(), _debt("", raw.decode("utf-8"))
    if theirs != found:
        print(f"  waiting for the product: its spec_parity_debt.txt is not true of the specs as they stand — it should "
              f"strike {len(theirs - found)} lines and is short of {len(found - theirs)}")
        return
    with open(PARITY_DEBT, "rb") as b:
        assert raw == b.read(), (f"the course's {PARITY_DEBT} is not the product's {PRODUCT_SPECS}/spec_parity_debt.txt "
                                 f"byte for byte — copy it")


def refused_paths(d: dict) -> list[str]:
    """The key paths of a spec the course's loader refuses: every key it reads none of (`speckeys.unknown`), and then,
    one at a time, the path a refusal of a value names (`spec <name>: <path> …`), until what is left loads."""
    from w2cplatform.spec import SubsystemSpec
    from w2cplatform.speckeys import unknown
    out = unknown(d)
    d = copy.deepcopy(d)
    for p in out:
        _drop(d, p.split("."))
    for _ in range(32):
        try:
            SubsystemSpec.from_dict(copy.deepcopy(d))
            return out
        except ValueError as e:
            m = re.match(r"spec \S+: `?([a-z_]+(?:\.[a-z0-9_*\-]+)*)", str(e))
            f = re.match(r"(?:spec \S+: )?(?:(tables\.[a-z0-9_]+): )?field ([a-z0-9_]+): `?([a-z_]+)`?", str(e))
            if f:                                        # a field's own word: `unit.fields.<f>.<key>` (or the table's)
                m = re.match(r"(.*)", f"{f.group(1) or 'unit'}.fields.{f.group(2)}.{f.group(3)}")
            if not m or m.group(1) in out:
                return out + [f"(refused: {e})"]
            out.append(m.group(1))
            _drop(d, m.group(1).split("."))
    return out


def _drop(x, parts: list[str]) -> None:
    if isinstance(x, list):
        for i in x:
            _drop(i, parts)
    elif isinstance(x, dict) and parts[0] in x:
        if len(parts) == 1:
            del x[parts[0]]
        else:
            _drop(x[parts[0]], parts[1:])


def test_every_spec_of_the_product_loads_with_the_courses_loader_but_for_the_debt():
    """A product spec is a course spec (one YAML): the course's loader takes it. The key sets are closed — what it
    refuses is a divergence to close (the course reads the key, the product drops it, or both rename it), named in
    `spec_load_debt.txt` as `<spec>:<key path>` until it is closed, and the list only shrinks. The product's test
    subsystems (`testsub*`, its own bytes) are asked the same: each side's loader takes the other's test specs."""
    assert len(_THEIR_TESTSUBS) == 2, _THEIR_TESTSUBS
    found = set()
    for p in _THEIRS + _THEIR_TESTSUBS:
        d = specyaml.loads(product_file(p), f"the product's {p}")     # the course's one reading of a spec (ADR-0019)
        found |= {f"{d.get('name')}:{k}" for k in refused_paths(d)}
    _hold(found, LOAD_DEBT, LOAD_HEAD, "key paths of the product's specs the course's loader refuses")


def test_the_lists_words_are_read_as_the_products_test_does():
    """A list of words gives each word, a list of maps its maps' `name` (else `field`), a number or a boolean nothing,
    and nothing under data."""
    text = ("door: {routes: [timeline, keeps]}\nheartbeat: {strings: [volume]}\nsnapshot: [name, 5, true]\n"
            "metrics:\n  - {name: m, from: f}\nservers:\n  status:\n    - {field: a.b, title: T}\n"
            "display:\n  tree: {columns: [x]}\nunit:\n  fields:\n    a: {type: url, schema: {enum: [z]}}\n")
    assert spec_list_values(text) == {"door.routes[timeline]", "door.routes[keeps]", "heartbeat.strings[volume]",
                                      "snapshot[name]", "metrics[m]", "servers.status[a.b]"}, sorted(spec_list_values(text))


def test_the_walk_reads_a_spec_as_the_products_test_does():
    """The reading itself, on a made-up spec: a block key's path is its parents', an inline map's keys are its own (all
    of them, a list's maps' too: `param`), a block list item's keys stand at the list's indent plus two, an inline list
    item is no key, and nothing under data is read."""
    import tempfile
    text = ("name: x\nunit:\n  fields:\n    a: {type: url, secret_in: [{param: [p]}]}  # a comment: b\n"
            "    b:\n      type: int\n      schema: {minimum: 1}\nmetrics:\n  - {name: m, from: f}\n"
            "  - name: n\n    from: g\ndisplay:\n  unit: штука\n  tree: {group_by: a}\n")
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(text)
    try:
        got = spec_key_paths(f.name)
    finally:
        os.unlink(f.name)
    assert got == {"name", "unit", "unit.fields", "unit.fields.a", "unit.fields.a.type", "unit.fields.a.secret_in",
                   "unit.fields.a.param", "unit.fields.b", "unit.fields.b.type", "unit.fields.b.schema",
                   "metrics", "metrics.name", "metrics.from", "display"}, sorted(got)
