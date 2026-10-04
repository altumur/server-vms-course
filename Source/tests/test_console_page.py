"""The page draws what operators typed — a mark's note, a camera's name — and what cameras said. It draws it as TEXT
(the platform review, second pass, blocker 2): every `innerHTML` goes through the escaping template `h`, and the
console sends a Content-Security-Policy that names the page's own script by its hash and allows no other.
"""
import base64
import hashlib
import re
import urllib.request

from w2cplatform.console import PAGE, page_csp
from tests.conftest import Box
from tests.test_console_gate import _console


def test_every_innerhtml_of_the_page_is_drawn_through_the_escaping_template():
    page = open(PAGE, encoding="utf-8").read()
    sites = [(i, line) for i, line in enumerate(page.splitlines(), 1) if ".innerHTML = " in line]
    assert len(sites) > 20                                             # the page draws a lot; this is the lint, not a count
    for i, line in sites:
        rhs = line.split(".innerHTML = ", 1)[1]
        # a literal with nothing interpolated, or a template whose interpolations `h` escapes
        assert "${" not in rhs or "h`" in rhs, (i, line)
    # the continuation lines of a multi-line template, too: a template with data in it is `h`'s
    for i, line in enumerate(page.splitlines(), 1):
        if re.match(r"^\s+`[^`]*\$\{", line):
            raise AssertionError(f"line {i}: a template with data outside h`…`: {line.strip()[:80]}")


def test_the_console_names_its_own_script_in_a_content_security_policy_and_no_other():
    page = open(PAGE, encoding="utf-8").read()
    scripts = re.findall(r"<script>(.*?)</script>", page, re.S)
    assert len(scripts) == 1 and not re.search(r"\son\w+=\"", page)     # one inline script, no handlers in the markup
    digest = "'sha256-" + base64.b64encode(hashlib.sha256(scripts[0].encode()).digest()).decode() + "'"
    assert page_csp() == f"script-src {digest}; object-src 'none'; base-uri 'none'"
    box = Box()
    ctl, rec, m, srv, base = _console(box)
    try:
        with urllib.request.urlopen(base + "/") as r:
            assert r.headers["Content-Security-Policy"] == page_csp()
            assert "text/html" in r.headers["Content-Type"]
    finally:
        srv.shutdown()
