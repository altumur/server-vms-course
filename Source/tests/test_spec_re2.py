"""Every regular expression a spec writes is a subset of RE2 (the architect, 6 Oct): a JSON Schema `pattern` wherever a
schema stands — a field of the unit or of a table, a table's schema, the requests' schema, a document of the domain, at
any depth — and a url field's `secret_in[].regex`. One spec for course and product (ADR 0019), and the product reads it
with Go's `regexp`: what Go will not compile, or reads otherwise, the course refuses at load, naming the path and the
construct (the strict loader, ADR 0012). Escaped look-alikes stand. A test of the platform alone, on specs built here
from `testdata/testsub*.yaml`; and every spec of the course still loads."""
from __future__ import annotations

import copy
import glob
import os
import re

import yaml

from w2cplatform.schema import re2_fault
from w2cplatform.spec import SubsystemSpec

HERE = os.path.dirname(os.path.abspath(__file__))
TESTDATA = os.path.join(HERE, "testdata")
BS = "\\"

# (pattern, the construct its refusal names) — Python compiles every one of them, Go none (the last two it reads otherwise)
NOT_RE2 = (
    ("a(?=b)", "a lookahead `(?=` at 1"),
    ("a(?!b)", "a negative lookahead `(?!` at 1"),
    ("(?<=a)b", "a lookbehind `(?<=` at 0"),
    ("(?<!a)b", "a negative lookbehind `(?<!` at 0"),
    ("(a)" + BS + "1", "a backreference `" + BS + "1` at 3"),
    ("(?P<name>a)(?P=name)", "a named backreference `(?P=` at 11"),
    ("(?>a)", "an atomic group `(?>` at 0"),
    ("(a)?(?(1)b|c)", "a conditional `(?(` at 4"),
    ("a*+", "a possessive quantifier `*+` at 1"),
    ("a++", "a possessive quantifier `++` at 1"),
    ("a?+", "a possessive quantifier `?+` at 1"),
    ("a{2}+", "a possessive quantifier `{2}+` at 1"),
    ("a" + BS + "Z", "an anchor RE2 lacks (it has `" + BS + "z`) `" + BS + "Z` at 1"),
    ("(?x)a", "an inline flag RE2 lacks (it reads i, m, s, U) `(?x)` at 0"),
    ("(?a:a)", "an inline flag RE2 lacks (it reads i, m, s, U) `(?a:` at 0"),
    ("(?u)a", "an inline flag RE2 lacks (it reads i, m, s, U) `(?u)` at 0"),
    ("(?i-x:a)", "an inline flag RE2 lacks (it reads i, m, s, U) `(?i-x:` at 0"),
    ("(?#note)a", "a comment `(?#` at 0"),
    (BS + "u0041", "an escape RE2 lacks"),
    (BS + "U00000041", "an escape RE2 lacks"),
    (BS + "N{DIGIT ONE}", "an escape RE2 lacks"),
    (BS + "é", "an escaped non-ASCII character"),
    ("[" + BS + "b]", "a backspace escape in a class `" + BS + "b` at 1"),
    ("[" + BS + "1]", "a one-digit octal escape in a class `" + BS + "1` at 1"),
    ("a{1001}", "a count past RE2's 1000 `{1001}` at 1"),
    ("[[:alpha:]]", "a POSIX class to Go, characters to Python `[:` at 1"),
    ("a{,3}", "a count with no lower bound"),
)
# …and what Python refuses itself — its words come first at load, so only the scan is asked here
PYTHON_REFUSES_FIRST = ((BS + "g<1>", "a backreference `" + BS + "g<1>`"), (BS + "Ga", "an anchor RE2 lacks"),
                        ("(?L)a", "an inline flag RE2 lacks"))
# what looks like one of them and is not: escaped, inside a class, or RE2 to the letter
LOOK_ALIKES = (BS + "(?=a" + BS + ")", "[(?=]", "[(?<!]", BS + "(?P=x" + BS + ")", BS + "(?>a" + BS + ")", "[(?(]",
               "a" + BS + "*+", "a" + BS + "++", "[*+?]+", BS + BS + "1", "[" + BS + BS + "1]", BS + "123", "[" + BS + "12]",
               BS + "0", "[a{,3}]", BS + "{,3}", "a{}+", "a{1000}", "a+?", "(?i)a", "(?ims:a)", "(?-i:a)", "(?P<name>a)",
               "[]a]", "[^]a]+", BS + "Aa" + BS + "b", "[" + BS + "d" + BS + "w]")


def _testsub(name: str) -> dict:
    with open(os.path.join(TESTDATA, f"{name}.subsystem.yaml")) as f:
        return yaml.safe_load(f)


def _places(pattern: str):
    """(the path a refusal names, the spec with `pattern` there) — every place a spec writes a regular expression."""
    regex = pattern + "(?P<secret>.)"                    # a `secret_in` regex names what it finds
    d = _testsub("testsub")
    d["unit"]["fields"]["name"]["schema"] = {"pattern": pattern}
    yield "spec testsub: field name: schema: pattern", d
    d = _testsub("testsub")
    d["requests"]["schema"]["properties"]["unit"]["pattern"] = pattern
    yield "spec testsub: requests.schema.unit: pattern", d
    d = _testsub("testsub")
    d["domain"]["shared"][2]["schema"]["items"]["properties"]["counter"]["pattern"] = pattern
    yield "spec testsub: domain.shared.rounds: schema/items.counter: pattern", d
    d = _testsub("testsub2")
    d["tables"]["shelves"]["fields"]["zone"]["schema"] = {"anyOf": [{"maxLength": 0}, {"not": {"pattern": pattern}}]}
    yield "spec testsub2: tables.shelves: field zone: schema/anyOf[1]/not: pattern", d
    d = _testsub("testsub2")
    d["tables"]["shelves"]["schema"]["then"]["properties"]["kind"] = {"pattern": pattern}
    yield "spec testsub2: tables.shelves.schema/then.kind: pattern", d
    d = _testsub("testsub2")
    d["unit"]["fields"]["feed"]["secret_in"][2]["regex"] = regex
    yield "spec testsub2: field feed: secret_in[2].regex", d
    d = _testsub("testsub2")
    d["tables"]["shelves"]["fields"]["feed"]["secret_in"][2]["regex"] = regex
    yield "spec testsub2: tables.shelves: field feed: secret_in[2].regex", d


def test_a_pattern_go_does_not_compile_is_refused_at_load_with_its_path_and_its_construct_wherever_it_stands():
    """Lookahead, lookbehind (both kinds), a numbered and a named backreference, an atomic group, a conditional,
    possessive quantifiers, `\\Z`, inline flags but i/m/s/U, a comment, Python's own escapes, and what Go reads
    otherwise — each refused in a schema's pattern and in a `secret_in` regex, the refusal naming where and what."""
    for pattern, construct in NOT_RE2:
        assert re.compile(pattern)                       # Python reads it, and says nothing
        for path, d in _places(pattern):
            shown = pattern if path.endswith("pattern") else pattern + "(?P<secret>.)"
            try:
                SubsystemSpec.from_dict(d)
            except ValueError as e:
                assert f"{path} {shown!r} holds {construct}" in str(e), (path, construct, str(e))
                assert "what Go will not compile or reads otherwise the course refuses at load" in str(e), str(e)
                assert "ADR 0019" in str(e), str(e)
                continue
            raise AssertionError(f"{path}: {pattern!r} loaded")
    for pattern, construct in PYTHON_REFUSES_FIRST:
        assert construct in re2_fault(pattern), (pattern, re2_fault(pattern))


def test_an_escaped_look_alike_and_plain_re2_load_everywhere():
    """`\\(?=` is a parenthesis and a question mark, `[(?=]` three characters, `\\\\1` a backslash and a one,
    `\\123` an octal character to both readers, `(?i)` a flag Go reads: the scan walks escapes and classes as the parser
    does, and none of them is refused, in any place."""
    for pattern in LOOK_ALIKES:
        assert re2_fault(pattern) == "", (pattern, re2_fault(pattern))
        for path, d in _places(pattern):
            SubsystemSpec.from_dict(d)


def _regexes(node, at=""):
    """(path, regular expression) of every `pattern` and `regex` a spec holds, at any depth."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("pattern", "regex") and isinstance(v, str):
                yield f"{at}.{k}", v
            else:
                yield from _regexes(v, f"{at}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _regexes(v, f"{at}[{i}]")


def test_every_spec_of_the_course_loads_and_writes_only_re2():
    """`Source/vms/*.subsystem.yaml` and `testdata/testsub*.yaml` load as they are — `rec`'s edge volume url says
    «no other scheme than file://» by `anyOf`/`not`, not by a lookahead — and every regex in them is RE2."""
    paths = sorted(glob.glob(os.path.join(HERE, "..", "vms", "*.subsystem.yaml"))) + \
        sorted(glob.glob(os.path.join(TESTDATA, "testsub*.subsystem.yaml")))
    assert len(paths) >= 6, paths
    seen = 0
    for p in paths:
        SubsystemSpec.load(p)
        with open(p) as f:
            for where, rx in _regexes(yaml.safe_load(f)):
                assert re2_fault(rx) == "", (os.path.basename(p), where, re2_fault(rx))
                seen += 1
    assert seen >= 10, seen


def _matches(pattern: str, value: str) -> bool:
    """Through the one door a value meets a schema's pattern at: `schema.load`, then `schema.check`."""
    from w2cplatform import schema
    try:
        schema.check(schema.load({"type": "string", "pattern": pattern}, "probe"), value)
        return True
    except schema.Invalid:
        return False


def test_a_pattern_is_read_as_go_reads_it_ascii_classes_and_dollar_the_end_of_the_text():
    """What both compile but read apart is read Go's way, not refused (the architect, 6 Oct): `$` is the end of the
    text — `abc` and a newline is not `^abc$` — but under `(?m)` the end of a line, as to both; `\\d`, `\\w`, `\\b` are
    ASCII — Arabic-Indic digits are no `\\d` — and `\\s` is Go's, without the vertical tab; `\\$` and `[$]` a dollar."""
    arabic = chr(0x663) + chr(0x664)                     # ٣٤
    nl, vt, tab = chr(10), chr(11), chr(9)
    assert _matches("^abc$", "abc") and not _matches("^abc$", "abc" + nl)
    assert _matches("^" + BS + "d+$", "34") and not _matches("^" + BS + "d+$", arabic)
    assert not _matches("^" + BS + "w+$", "é") and not _matches(BS + "bé", "é")
    assert _matches(BS + "s", " ") and not _matches(BS + "s", vt) and not _matches("[" + BS + "s]", vt)
    assert _matches(BS + "S", vt) and not _matches(BS + "S", tab)
    assert _matches("^a" + BS + "$", "a$") and not _matches("^a" + BS + "$", "a")
    assert _matches("^[$]$", "$") and not _matches("^[$]$", "$" + nl)
    assert _matches("(?m)^a$", "a" + nl + "b") and _matches("(?m:^a$)", "b" + nl + "a" + nl + "c")
    assert not _matches("(?m)a(?-m:$)", "a" + nl + "b")
    from w2cplatform.secrets import SecretRules, hide_in_url
    rules = SecretRules.parse([{"regex": "^/pin/(?P<secret>" + BS + "d+)$", "in": "path"}], "field t")
    assert hide_in_url("https://h/pin/34", rules) == "https://h/pin/***"
    assert hide_in_url("https://h/pin/" + arabic, rules) == "https://h/pin/" + arabic    # no `\d` to Go, nor here
