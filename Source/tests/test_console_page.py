"""The platform's console page and the module it is built from (КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md; the boundary's step 3).

The page at `/` is the console root's alone — its subsystem's own when one lies beside its spec (`<sub>.shell.html`),
else the platform's; a mounted subsystem serves none. The platform's page is the console module (`/platform/console.js`, its look `/platform/console.css`) and its mount, nothing else — it shows any spec. The
module is served by its version and to anybody, since it draws the login. What a page draws it draws as TEXT (the
module escapes every value; its jsdom tests in `tests/console/` prove it with hostile strings in every field), and the
console sends a Content-Security-Policy that names the page's inline script by its hash and, for a page that loads the
module, this origin — no other script.
"""
import base64
import hashlib
import os
import re
import tempfile
import urllib.error
import urllib.request

from w2cplatform import catalog
from w2cplatform.access import MODULE_ROUTES, OPEN_ROUTES, TRUST_KEYS, Denied
from w2cplatform.console import MODULE, MODULE_CSS, MODULE_VERSION, PAGE, SpecConsole, page_csp, page_of
from tests.conftest import TESTSUB, Box, Served, console_ctl, testsub


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def _digest(script: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'"


def test_the_platforms_page_is_the_console_module_and_its_mount_and_nothing_else():
    """§10: the platform's page is the three lines of §1 — the module, its look, a mount — and no script, word or route
    of its own; no handler in the markup."""
    page = open(PAGE, encoding="utf-8").read()
    scripts = re.findall(r"<script\b([^>]*)>(.*?)</script>", page, re.S)
    assert [s[0].strip() for s in scripts] == [f'src="/platform/console.js?v={MODULE_VERSION}"', ""]
    assert scripts[1][1].strip() == 'window.platformConsole = PlatformConsole.mount(document.getElementById("app"));'
    assert f'<link rel="stylesheet" href="/platform/console.css?v={MODULE_VERSION}">' in page
    assert not re.search(r"\son\w+=", page) and "fetch(" not in page


def test_the_console_names_the_pages_own_script_and_this_origin_in_a_content_security_policy_and_no_other():
    """The platform's page runs its one inline script (by hash) and the module from this origin (`'self'`); a page with
    no `<script src>` gets no `'self'`: its inline scripts, by hash, are all it may run."""
    page = open(PAGE, encoding="utf-8").read()
    inline = re.findall(r"<script>(.*?)</script>", page, re.S)
    assert page_csp() == f"script-src 'self' {_digest(inline[0])}; object-src 'none'; base-uri 'none'"
    d = tempfile.mkdtemp(prefix="page-")
    with open(os.path.join(d, "p.html"), "w") as f:
        f.write("<!doctype html><script>go()</script>")
    assert page_csp(os.path.join(d, "p.html")) == f"script-src {_digest('go()')}; object-src 'none'; base-uri 'none'"
    box = Box()
    with Served(SpecConsole(console_ctl(box), marks_root=box.resource_root, wall=box.wall)) as call:
        status, headers, body = _get(call.base + "/")
        assert status == 200 and "text/html" in headers["Content-Type"]
        assert headers["Content-Security-Policy"] == page_csp() and body == open(PAGE, "rb").read()


def test_the_console_module_and_its_look_are_served_by_their_version_to_anybody():
    """`/platform/console.js` and `/platform/console.css`, by `?v=` or with none: the files as they are; another version
    is 404 and says which one this platform serves. Open (the module draws the login): a console that asks every caller
    for a token serves them without one."""
    assert set(MODULE_ROUTES) <= set(OPEN_ROUTES)
    box = Box()
    con = SpecConsole(console_ctl(box), marks_root=box.resource_root, wall=box.wall)
    with Served(con) as call:
        for path, f, kind in (("/platform/console.js", MODULE, "text/javascript"), ("/platform/console.css", MODULE_CSS, "text/css")):
            for q in ("", f"?v={MODULE_VERSION}"):
                status, headers, body = _get(call.base + path + q)
                assert status == 200 and headers["Content-Type"].startswith(kind) and body == open(f, "rb").read()
            status, _, body = _get(call.base + path + "?v=999")
            assert status == 404 and f"serves {MODULE_VERSION}".encode() in body

        class Nobody:                                    # a cluster in a domain, and a caller with no token
            def who(self, token):
                raise Denied(401, "token refused")
        con.gate.impl = Nobody()
        box.vars.put(TRUST_KEYS, {"current": "k1", "key:k1": "00" * 32})
        assert _get(call.base + "/counters")[0] == 401
        assert _get(call.base + "/platform/console.js")[0] == 200 and _get(call.base + "/")[0] == 200


def test_a_subsystem_with_a_page_beside_its_spec_is_shown_with_it_and_one_without_with_the_platforms():
    """The page at `/` is the subsystem's own when `<sub>.shell.html` lies beside the file its spec was loaded from — its
    CSP by its own scripts — else the platform's: a spec of a directory with no page, or built in code. A page of any
    other name beside the spec — another subsystem's, a bare `shell.html` — is not its page."""
    spec, d = testsub(), tempfile.mkdtemp(prefix="shell-")
    own = os.path.join(d, "testsub.shell.html")
    for name in ("shell.html", "testsub2.shell.html"):
        with open(os.path.join(d, name), "w") as f:
            f.write("<!doctype html><title>not its own</title>")
    was = (dict(catalog._loaded), dict(catalog._files))
    try:
        catalog._files.pop(spec.name, None)
        assert page_of(spec) == PAGE                     # built in code: nobody's file, so nobody's page
        catalog.register(spec, TESTSUB)
        assert page_of(spec) == PAGE                     # a directory with no page of its own
        catalog.register(spec, os.path.join(d, "testsub.subsystem.yaml"))
        assert page_of(spec) == PAGE                     # pages beside it, none of its name
        with open(own, "w") as f:
            f.write("<!doctype html><title>its own</title><script>mine()</script>")
        assert page_of(spec) == own
        box = Box()
        with Served(SpecConsole(console_ctl(box), marks_root=box.resource_root, wall=box.wall)) as call:
            status, headers, body = _get(call.base + "/")
            assert status == 200 and b"its own" in body and headers["Content-Security-Policy"] == page_csp(own)
            assert "'self'" not in headers["Content-Security-Policy"]
    finally:
        with catalog._lock:
            catalog._loaded.clear(); catalog._loaded.update(was[0])
            catalog._files.clear(); catalog._files.update(was[1])
            catalog.version += 1
            catalog._derived.clear()


def test_only_the_consoles_root_serves_a_page_and_a_mounted_subsystem_none():
    """КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md §1: one console process, one page — the root's (`CONSOLE_ROOT`), for its root
    subsystem: `<sub>.shell.html` beside its spec. A subsystem in `/mounts` serves none, though a page of its name lies
    beside its own spec: `/<sub>/` is 404, not its page and not the platform's — the module shows its units on the
    root's page. Its routes are there as before."""
    from w2cplatform.host import spec_console
    from tests.conftest import testsub2
    d = tempfile.mkdtemp(prefix="shell-")
    for name in ("testsub", "testsub2"):
        with open(os.path.join(d, f"{name}.shell.html"), "w") as f:
            f.write(f"<!doctype html><title>{name}'s own</title><script>mine()</script>")
    was = (dict(catalog._loaded), dict(catalog._files))
    box = Box()
    try:
        catalog.register(testsub(), os.path.join(d, "testsub.subsystem.yaml"))
        catalog.register(testsub2(), os.path.join(d, "testsub2.subsystem.yaml"))
        m = spec_console({"testsub": console_ctl(box), "testsub2": console_ctl(box, testsub2())}, "testsub",
                         box.resource_root, wall=box.wall)
        srv = m.serve("127.0.0.1", 0)
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            own = os.path.join(d, "testsub.shell.html")
            for path in ("/", "/index.html"):
                status, headers, body = _get(base + path)
                assert status == 200 and body == open(own, "rb").read(), (path, status)
                assert headers["Content-Security-Policy"] == page_csp(own)
            for path in ("/testsub2/", "/testsub2/index.html", "/testsub2"):
                status, _, body = _get(base + path)
                assert status == 404 and b"the page is the console root's" in body, (path, status, body[:200])
            assert _get(base + "/testsub2/spec")[0] == 200                      # the mount's routes are its own
        finally:
            srv.shutdown(); srv.server_close()
    finally:
        with catalog._lock:
            catalog._loaded.clear(); catalog._loaded.update(was[0])
            catalog._files.clear(); catalog._files.update(was[1])
            catalog.version += 1
            catalog._derived.clear()


def test_the_servers_door_says_what_the_module_shows_of_a_servers_resource():
    """A server's card in the module shows its resource's address and disk: `/servers` says `resource_url` and `space:
    {total, free}` from the resource's heartbeat (the product's fields); a resource that says nothing of its disk, none."""
    import json
    from w2cplatform.resource import heartbeat_key
    box = Box()
    box.objects.put(heartbeat_key("srv-9"), json.dumps({"server": "srv-9", "ts": box.wall(), "url": "http://srv-9:8090",
                                                         "space": {"total": 100, "free": 40}, "mirrors": {}}).encode())
    box.objects.put(heartbeat_key("srv-8"), json.dumps({"server": "srv-8", "ts": box.wall(), "url": "", "mirrors": {}}).encode())
    with Served(SpecConsole(console_ctl(box), marks_root=box.resource_root, wall=box.wall)) as call:
        status, body = call("GET", "/servers")
        assert status == 200 and body["servers"]["srv-9"]["resource_url"] == "http://srv-9:8090"
        assert body["servers"]["srv-9"]["space"] == {"total": 100, "free": 40}
        assert body["servers"]["srv-8"]["space"] is None and body["servers"]["srv-8"]["resource_url"] == ""
