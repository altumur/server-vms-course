"""One YAML, two parsers (the user's decision, «спеки yaml одинаковые»): the course reads a spec with PyYAML, the product
with its own strict loader, and that loader reads a flow collection — a `{…}` or a `[…]` — only on one line. A spec
whose flow map runs on to the next line loads here and is refused there, so no spec of the course writes one: it is
one line, or block style."""
from __future__ import annotations

import glob
import os

import yaml

SOURCE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPECS = sorted(glob.glob(os.path.join(SOURCE, "vms", "*.subsystem.yaml"))
               + glob.glob(os.path.join(SOURCE, "tests", "testdata", "*.subsystem.yaml")))
_OPEN = (yaml.FlowMappingStartToken, yaml.FlowSequenceStartToken)
_CLOSE = (yaml.FlowMappingEndToken, yaml.FlowSequenceEndToken)


def flows_across_lines(text: str) -> list[tuple[int, int]]:
    """The outermost flow collections of `text` that open on one line and close on another, as (first, last) line
    numbers from 1."""
    out, opened = [], []
    for tok in yaml.scan(text):
        if isinstance(tok, _OPEN):
            opened.append(tok.start_mark.line)
        elif isinstance(tok, _CLOSE):
            first = opened.pop()
            if not opened and tok.end_mark.line != first:
                out.append((first + 1, tok.end_mark.line + 1))
    return out


def test_no_spec_writes_a_flow_collection_across_lines():
    """Every spec of the VMS and both of the platform's test specs: each `{…}` and `[…]` opens and closes on one line."""
    assert len(SPECS) >= 9, SPECS                                    # seven of the VMS, testsub, testsub2
    found = []
    for p in SPECS:
        with open(p, encoding="utf-8") as f:
            found += [f"{os.path.relpath(p, SOURCE)}:{a}-{b}" for a, b in flows_across_lines(f.read())]
    assert not found, ("a flow collection across lines — the product's loader reads it on one line only; write it on "
                       "one line or in block style:\n  " + "\n  ".join(found))


def test_the_check_sees_a_flow_map_or_list_that_runs_on_and_passes_one_that_does_not():
    """The reading itself: a map or a list continued on the next line is found once, at its outermost; a nested flow on
    one line, and block style holding flows, are not."""
    assert flows_across_lines("a: {b: 1,\n   c: [1, 2]}\nd: [1,\n 2]\n") == [(1, 2), (3, 4)]
    assert flows_across_lines("a: {b: {c: [1, 2]}, d: 3}\ne:\n  - {f: 1}\n  - g: [1]\n") == []
