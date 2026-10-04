"""A request quoted in a lesson is a request the stand made — every line of it.

The lessons quote the stand's traces: who called through which socket (`# vmsworker w-srv-a-1 on srv-a →
/run/configstore/vmsworker.sock`), request lines in the configstore's API (`GET /v1/get?key=…`, `GET /v1/list?prefix=…`,
`POST /v1/write {…}`, `POST /v1/join {…}`), the resource's object door (`GET /v1/objects?…`), the console's `/metrics`
(`GET /metrics`), a file a process wrote on its own server (`PUT vms/heartbeats/w-srv-a-1`), and every answer (`→ 200 {"index": 1004}`, `→ 200 {"items": null, "index": ""}`, a 403 with its
words, a 409 with the version now). `test_stand.py` keeps the traces equal to the code; this keeps the lessons equal
to the traces.

What is checked, in every lesson of the module (`[0-9][0-9]-*.md`):

- a line anywhere that starts like a request or an answer, or like a trace's header line, is a line of some trace;
- inside a fenced block that quotes a trace (it holds such a line), EVERY line is a line of some trace: a write's body
  (`"holder": "srv-a:4101",`), an answer printed over several lines, a series of `/metrics` — so a value that shifted,
  a key that was renamed, a field that went fails here, with the lesson and the line.

Lines with `...` or `…` are paraphrase — the lesson says so by the ellipsis — and are not checked; nor is anything
outside a fence that does not start like a trace line.

Before the rework the traces were Nomad's Variables API (`PUT /v1/var/…?namespace=default&cas=0`, `{"Items": …}`,
`"ModifyIndex"`). No scene can make such a request now, so a lesson still quoting one is a lesson still to be
rewritten: any line of that format anywhere in a lesson — prose, table or fence — fails the first test, and the checks
above can no longer be passed by a line that no pattern matches. Every lesson of the module is checked; none is
skipped (lessons 06–10 were the last to be rewritten, and the set that skipped them meanwhile is gone).
"""
import glob
import os
import re

from tests.cluster.stand import TRACES

MODULE = os.path.join(os.path.dirname(os.path.dirname(TRACES)), "М11_Cluster")     # the lessons: beside Source/

# A trace's own lines: who called through which door, a request, an answer.
HEADER = re.compile(r"^# \S.* → \S")       # its socket, another daemon's door, a resource, its own files
REQUEST = re.compile(r"^(GET /v1/(get|list|objects)[?/]|POST /v1/(write|join) \{|GET /metrics$|(PUT|GET|DELETE) [a-z][^ ]*$)")
ANSWER = re.compile(r"^→ \d{3}( |$)")

# Nomad's Variables API, as the old traces printed it: a route, a query, a body, a version.
NOMAD = re.compile(r"/v1/vars?[/?]|[?&]namespace=|\"ModifyIndex\"|\{\"Items\"|X-Nomad-Token")


FENCE = re.compile(r"^\s*(```|~~~)")


def _lessons() -> list[str]:
    return sorted(glob.glob(os.path.join(MODULE, "[0-9][0-9]-*.md")))


def _trace_lines() -> set[str]:
    return {l.strip() for p in glob.glob(os.path.join(TRACES, "*.txt"))
            for l in open(p, encoding="utf-8").read().splitlines() if l.strip()}


def _is_trace_line(line: str) -> bool:
    return bool(HEADER.match(line) or REQUEST.match(line) or ANSWER.match(line))


def _elided(line: str) -> bool:
    return "..." in line or "…" in line


def _nomad_lines(text: str) -> list[tuple[int, str]]:
    return [(n, l.strip()) for n, l in enumerate(text.splitlines(), 1) if NOMAD.search(l)]


def quotes(text: str) -> list[tuple[int, str]]:
    """`(line number, stripped line)` of every line of a lesson this test holds to the traces."""
    out, block, start = [], None, 0
    lines = text.splitlines()
    for n, raw in enumerate(lines, 1):
        if FENCE.match(raw):
            if block is None:
                block, start = [], n
            else:
                if any(_is_trace_line(l.strip()) for _, l in block):
                    out += [(k, l.strip()) for k, l in block if l.strip()]
                else:
                    out += [(k, l.strip()) for k, l in block if _is_trace_line(l.strip())]
                block = None
            continue
        if block is not None:
            block.append((n, raw))
        elif _is_trace_line(raw.strip()):
            out.append((n, raw.strip()))
    return [(n, l) for n, l in out if not _elided(l)]


def test_no_lesson_quotes_nomads_api():
    """The old format, anywhere in a lesson: a route of Nomad's Variables API, its `namespace=` query, its `Items` body,
    its `ModifyIndex` — none of it is a request the cluster makes now."""
    found = []
    for lesson in _lessons():
        text = open(lesson, encoding="utf-8").read()
        found += [f"{os.path.basename(lesson)}:{n}: {l}" for n, l in _nomad_lines(text)]
    assert not found, "a lesson still quotes Nomad's Variables API:\n" + "\n".join(found)


def test_every_quoted_line_of_a_trace_is_in_a_trace():
    lines = _trace_lines()
    missing, checked = [], 0
    for lesson in _lessons():
        text = open(lesson, encoding="utf-8").read()
        for n, line in quotes(text):
            checked += 1
            if line not in lines:
                missing.append(f"{os.path.basename(lesson)}:{n}: {line}")
    assert not missing, "quoted in a lesson, made by no scene:\n" + "\n".join(missing)
    assert checked > 200, checked                     # the lessons do quote the traces: a check that checks nothing fails


def test_the_patterns_know_the_traces_own_lines():
    """The checks above are only as good as their patterns: every scene's header, request and answer lines match them,
    so a lesson that quotes one is checked; and the old format matches the Nomad pattern and none of the others."""
    traces = [l for p in glob.glob(os.path.join(TRACES, "*.txt")) for l in open(p, encoding="utf-8").read().splitlines()]
    assert all(_is_trace_line(l) for l in traces if l.startswith(("GET ", "POST ", "PUT ", "DELETE ", "→ ")))
    assert all(HEADER.match(l) for l in traces if l.startswith("# ") and " → " in l), \
        [l for l in traces if l.startswith("# ") and " → " in l and not HEADER.match(l)]
    assert sum(1 for l in traces if HEADER.match(l)) > 100 and sum(1 for l in traces if ANSWER.match(l)) > 100
    assert any(REQUEST.match(l) for l in traces if l == "GET /metrics")
    assert not any(NOMAD.search(l) for l in traces)
    for old in ('PUT /v1/var/vms/slots/w-0?namespace=default&cas=0',
                'GET /v1/vars?prefix=vms/slots/&namespace=default',
                '→ 200 {"Path": "vms/slots/w-0", "ModifyIndex": 1001}',
                '{"Items": {"holder": "alloc-0001", "until": "1757500045.0", "released": "false", "gen": "1"}}'):
        assert NOMAD.search(old), old
        assert not REQUEST.match(old) and not HEADER.match(old), old


def test_a_block_that_quotes_a_trace_is_checked_line_by_line():
    """What `quotes` takes from a lesson: the whole of a fenced block that holds a trace line — its body lines too —,
    only the trace lines of a block that does not (a listing of code), the trace-like lines outside fences, and
    nothing elided."""
    text = "\n".join([
        "Прозой: `GET /v1/get?key=x` не в начале строки.",
        "GET /v1/list?prefix=vms/",
        "```",
        "# vmsworker w-srv-a-1 on srv-a → /run/configstore/vmsworker.sock",
        'POST /v1/write {"op": "put", "key": "k", "cas": "", "items": {',
        '  "holder": "srv-a:4101",',
        "  …",
        "}}",
        "```",
        "```python",
        "def f():",
        "    return 1",
        "```",
    ])
    assert [l for _, l in quotes(text)] == [
        "GET /v1/list?prefix=vms/",
        "# vmsworker w-srv-a-1 on srv-a → /run/configstore/vmsworker.sock",
        'POST /v1/write {"op": "put", "key": "k", "cas": "", "items": {',
        '"holder": "srv-a:4101",',
        "}}",
    ]
