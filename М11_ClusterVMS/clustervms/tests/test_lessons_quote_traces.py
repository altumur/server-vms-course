"""A request quoted in a lesson is a request the stand made.

The lessons quote the stand's traces: request lines in the configstore's API (`GET /v1/get?key=…`,
`GET /v1/list?prefix=…`, `POST /v1/write {…}`, `POST /v1/join {…}`), the resource's object door
(`GET /v1/objects?…`), and answers that carry a version (`→ 200 {"index": 1004}`, a row read with its `"index"`, a
409 with the version now). `test_stand.py` keeps the traces equal to the code; this keeps the lessons equal to the
traces. A quoted line that is in no trace file — a version that shifted, a key that was renamed — fails here, with
the lesson and the line. Lines shortened with `...` or `…` are paraphrase and are not checked.

Before the rework the traces were Nomad's Variables API (`PUT /v1/var/…?namespace=…`, `"ModifyIndex"`); a line in
that format is not a request any scene can make now and matches neither pattern below — a lesson still quoting one
is a lesson still to be rewritten, not a check that passes.
"""
import glob
import os
import re

from tests.stand import TRACES

MODULE = os.path.dirname(TRACES)
REQUEST = re.compile(r"^(GET /v1/(get|list|objects)[?/]|POST /v1/(write|join) \{)")
ANSWER = re.compile(r'^→ \d{3} \{.*"index": \d+\}$')


def test_every_quoted_request_and_version_is_in_a_trace():
    traces = "\n".join(open(p, encoding="utf-8").read() for p in glob.glob(os.path.join(TRACES, "*.txt")))
    lines = set(traces.splitlines())
    missing = []
    for lesson in sorted(glob.glob(os.path.join(MODULE, "[0-9][0-9]-*.md"))):
        for n, line in enumerate(open(lesson, encoding="utf-8").read().splitlines(), 1):
            line = line.strip()
            if "..." in line or "…" in line:
                continue
            if (REQUEST.match(line) or ANSWER.match(line)) and line not in lines:
                missing.append(f"{os.path.basename(lesson)}:{n}: {line}")
    assert not missing, "quoted in a lesson, made by no scene:\n" + "\n".join(missing)


def test_the_patterns_know_the_traces_own_lines():
    """The check above is only as good as its patterns: every scene's request lines and versioned answers match
    them, so a lesson that quotes one is checked."""
    traces = [l for p in glob.glob(os.path.join(TRACES, "*.txt")) for l in open(p, encoding="utf-8").read().splitlines()]
    assert any(REQUEST.match(l) for l in traces if l.startswith("POST /v1/write"))
    assert all(REQUEST.match(l) for l in traces if l.startswith(("GET /v1/get?", "GET /v1/list?", "POST /v1/write ")))
    assert sum(1 for l in traces if ANSWER.match(l)) > 50
    assert not ANSWER.match('→ 200 {"Path": "vms/slots/w-0", "ModifyIndex": 1001}')
    assert not REQUEST.match("PUT /v1/var/vms/slots/w-0?namespace=default&cas=0")
