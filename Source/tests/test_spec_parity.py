"""The course and the product describe the same subsystems by one YAML (the user's decision, «спеки yaml одинаковые»).
Held here from the course's side, as the product holds it from its own (`vmsworker/vms/spec_parity_test.go`): the key
paths of each spec both have are the same, and what differs today is the debt in `testdata/spec_parity_debt.txt` — a
byte copy of the product's file, which only shrinks; and every spec of the product loads with the course's loader,
what it refuses today being the debt in `testdata/spec_load_debt.txt`, which only shrinks too. Without the product's
checkout beside the course (`productdir.py`) the module is skipped: the course builds alone.

`W2C_SPEC_SHRINK=1` rewrites both debts without the lines no longer true; nothing ever adds one — a new difference is
made good, on one side or the other, not written down."""
from __future__ import annotations

import copy
import glob
import os
import re

import pytest
import yaml

from tests.productdir import SOURCE, product_dir

PRODUCT = product_dir()
PRODUCT_SPECS = os.path.join(PRODUCT, "vmsworker", "vms") if PRODUCT else ""
pytestmark = pytest.mark.skipif(not glob.glob(os.path.join(PRODUCT_SPECS, "*.subsystem.yaml")),
                                reason="no product beside the course (W2C_PRODUCT_DIR): the specs are not compared")

COURSE_SPECS = os.path.join(SOURCE, "vms")
TESTDATA = os.path.join(SOURCE, "tests", "testdata")
PARITY_DEBT = os.path.join(TESTDATA, "spec_parity_debt.txt")
LOAD_DEBT = os.path.join(TESTDATA, "spec_load_debt.txt")
# The product's writer's head (`W2C_SPEC_PARITY_WRITE`): the two files are one, byte for byte.
PARITY_HEAD = ("# spec_parity_debt.txt — the keys the course's specs and the product's differ by (spec_parity_test.go).\n"
               "# A line goes when both sides have the key, or neither; a new difference is not written here but made good.\n")
LOAD_HEAD = ("# spec_load_debt.txt — the key paths of the product's specs the course's loader refuses (test_spec_parity.py),\n"
             "# `<spec>:<key path>`. A line goes when the course reads the key or the product drops it; none is ever added.\n")

# The product's reading of a spec, line by line — its regular expressions, its order (`specKeyPaths`).
_KEY = re.compile(r"^([A-Za-z0-9_.\-\"']+)\s*:\s*(.*)$")
_INLINE = re.compile(r"([A-Za-z_][\w\-]*)\s*:")
_COMMENT = re.compile(r"\s+#.*$")
# under these a spec holds data — words, a JSON Schema, vendor forms — not declarations
_DATA = re.compile(r"(^|\.)(kinds|field_help|schema|secret_in)(\.|$)|^display(\.|$)")


def spec_key_paths(path: str) -> set[str]:
    """The key paths of a YAML spec, block and inline, leaving out what lies under data — as the product reads them."""
    out, stack = set(), []
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
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


def _differences() -> set[str]:
    found = set()
    for c in sorted(glob.glob(os.path.join(COURSE_SPECS, "*.subsystem.yaml"))):
        name = os.path.basename(c)
        theirs = os.path.join(PRODUCT_SPECS, name)
        if not os.path.exists(theirs):
            continue                                     # a subsystem only the course has
        a, b = spec_key_paths(c), spec_key_paths(theirs)
        found |= {f"course-only {name} {p}" for p in a - b} | {f"product-only {name} {p}" for p in b - a}
    return found


def _debt(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        lines = (_COMMENT.sub("", ln).strip() for ln in f.read().split("\n"))
    return {ln for ln in lines if ln and not ln.startswith("#")}


def _hold(found: set[str], path: str, head: str, what: str) -> None:
    debt = _debt(path)
    fresh, gone = sorted(found - debt), sorted(debt - found)
    if gone and os.environ.get("W2C_SPEC_SHRINK"):
        with open(path, "w", encoding="utf-8") as f:
            f.write(head + "".join(f"{ln}\n" for ln in sorted(debt & found)))
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


def test_the_parity_debt_is_the_products_file_byte_for_byte():
    """One debt for both sides: the course's file is the product's, byte for byte — whenever the product's is true of the
    specs as they stand. While the product's lags (its own test fails: the course's specs moved since it was written),
    the comparison waits for it and says what the product's file is short of and holds too many of."""
    theirs = os.path.join(PRODUCT_SPECS, "spec_parity_debt.txt")
    if not os.path.exists(theirs):
        print("  the product keeps no spec_parity_debt.txt: nothing to compare")
        return
    found = _differences()
    if _debt(theirs) != found:
        print(f"  waiting for the product: its spec_parity_debt.txt is not true of the specs as they stand — it should "
              f"strike {len(_debt(theirs) - found)} lines and is short of {len(found - _debt(theirs))}")
        return
    with open(theirs, "rb") as a, open(PARITY_DEBT, "rb") as b:
        assert a.read() == b.read(), f"the course's {PARITY_DEBT} is not the product's {theirs} byte for byte — copy it"


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
    `spec_load_debt.txt` as `<spec>:<key path>` until it is closed, and the list only shrinks."""
    found = set()
    for p in sorted(glob.glob(os.path.join(PRODUCT_SPECS, "*.subsystem.yaml"))):
        with open(p, encoding="utf-8") as f:
            d = yaml.safe_load(f)
        found |= {f"{d.get('name')}:{k}" for k in refused_paths(d)}
    _hold(found, LOAD_DEBT, LOAD_HEAD, "key paths of the product's specs the course's loader refuses")


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
