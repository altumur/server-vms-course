"""Shared normgen parser for stages.tsv gate cells (ADR-0126 addenda (1) item 8 and (7) items 2, 3).

A gate is a semicolon-separated conjunction. Each check has no whitespace: <kind>:<argument>[:<argument>]. Kinds are tests:<chapter>:<scenarios|*>[:seams], accept:<chapter>:<scenarios|*>, seams:<chapter>:<scenarios|*>, verdicts:<chapter>:<cases|*>, puts:<chapter>:<cases|*> for P/02, vectors:<package>, vectors:<owner>/<package>, code:*, and build. Chapters use NN.K or NN for a single-chapter lesson.

Empty elements, trailing semicolons, whitespace, unknown kinds and duplicates raise GateError rather than silently dropping checks (Codex C4). test_gate.py verifies agreement with check_forms.gate_errors."""
import re
from dataclasses import dataclass

CH = r"[0-9]+(?:\.[0-9]+)?"            # Chapter NN.K or single-chapter lesson NN (P/04; ADR-0125 addendum (5)).
ITEM = re.compile(rf"tests:({CH}):(\*|[a-z0-9][a-z0-9-]*(?:,[a-z0-9][a-z0-9-]*)*)(:seams)?"
                  rf"|accept:({CH}):(\*|[a-z0-9][a-z0-9-]*(?:,[a-z0-9][a-z0-9-]*)*)"
                  r"|vectors:([a-z0-9][a-z0-9-]*|(?:common|[0-9]{2}-[a-z0-9-]+)/[a-z0-9-]+)|build"
                  rf"|(verdicts|puts):({CH}):(\*|[a-z0-9][a-z0-9_-]*(?:,[a-z0-9][a-z0-9_-]*)*)"
                  rf"|seams:({CH}):(\*|[a-z0-9][a-z0-9-]*(?:,[a-z0-9][a-z0-9-]*)*)|code:\*")


class GateError(ValueError):
    pass


@dataclass(frozen=True)
class Check:
    kind: str                 # tests | accept | seams | vectors | build | verdicts | puts | code
    text: str
    chapter: str = None       # tests, accept, seams, verdicts, puts
    names: tuple = None       # tests/accept use scenario names; verdicts/puts use first-column case names; None denotes '*'.
    seams: bool = False       # tests with :seams, or seams: selects seams.tsv
    package: str = None       # vectors: package or owner/package, preserved in full


def parse(gate, where="gate"):
    """Parse a gate cell into [Check] in cell order."""
    if gate == "":
        raise GateError(f"{where}: empty gate")
    out, seen = [], set()
    for text in gate.split(";"):
        m = ITEM.fullmatch(text)
        if not m:
            what = "an empty item" if text == "" else ("a space in an item" if re.search(r"\s", text)
                                                       else f"item {text!r}")
            raise GateError(f"{where}: {what} — not tests:<chapter>:<scenarios|*>[:seams], accept:<chapter>:"
                            f"<scenarios|*>, seams:<chapter>:<scenarios|*>, verdicts:<chapter>:<cases|*>, "
                            f"puts:<chapter>:<cases|*>, vectors:<package>, vectors:<owner>/<package>, code:* or build")
        if text in seen:
            raise GateError(f"{where}: item {text!r} repeats")
        seen.add(text)
        if m[1]:
            names = None if m[2] == "*" else tuple(m[2].split(","))
            c = Check("tests", text, m[1], names, bool(m[3]))
        elif m[4]:
            c = Check("accept", text, m[4], None if m[5] == "*" else tuple(m[5].split(",")))
        elif m[6]:
            c = Check("vectors", text, package=m[6])
        elif m[7]:
            c = Check(m[7], text, m[8], None if m[9] == "*" else tuple(m[9].split(",")))
        elif m[10]:
            c = Check("seams", text, m[10], None if m[11] == "*" else tuple(m[11].split(",")), True)
        elif text == "code:*":
            c = Check("code", text)
        else:
            c = Check("build", text)
        if c.names is not None and len(set(c.names)) != len(c.names):
            raise GateError(f"{where}: a scenario repeats in {text!r}")
        out.append(c)
    return out


def vector_packages(gate, owner):
    """Return full package identities; only unqualified names belong to the lesson."""
    return {c.package if "/" in c.package else f"{owner}/{c.package}"
            for c in parse(gate) if c.kind == "vectors"}
