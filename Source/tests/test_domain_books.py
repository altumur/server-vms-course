"""A book shown (ADR-0010, the addition of 2026-10-06; ADR-0061): `domain.books` is a list of names — carried, none
shown — or a map `{<book>: {} | {show: [<field>…]}}`, read as the product reads it (`domainBooks`), its refusals in its
words; and a cluster's console answers `GET /domain/<sub>/books/<book>` from its own copy of the book with the fields
`show` names, each item to whoever may view the unit whose `domain.ref` is its key («Архитектор» 2026-10-06). A test of
the platform alone, on testsub: the spec with a book shown is built here (the spec bytes are «Паритет»'s)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.error
import urllib.request

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TESTSUB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata", "testsub.subsystem.yaml")


def _base() -> dict:
    with open(TESTSUB, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _with_books(books) -> dict:
    d = _base()
    d["domain"] = {**d["domain"], "books": books}
    return d


def _refusal(books) -> str:
    from w2cplatform.spec import SubsystemSpec
    try:
        SubsystemSpec.from_dict(_with_books(books))
    except ValueError as e:
        return str(e)
    raise AssertionError(f"taken: {books!r}")


def test_books_are_a_list_carried_or_a_map_each_book_carried_or_shown_by_its_fields():
    from w2cplatform.spec import SubsystemSpec
    listed = SubsystemSpec.load(TESTSUB).domain                       # testsub's own: `books: [tallies]`
    assert listed.books == ("tallies",) and listed.show == {}
    mapped = SubsystemSpec.from_dict(_with_books({"tallies": {}, "counts": {"show": ["n", "at"]}})).domain
    assert mapped.books == ("counts", "tallies") and mapped.show == {"counts": ("n", "at")}   # a map's names, sorted
    assert SubsystemSpec.from_dict(_with_books(["b", "a"])).domain.books == ("b", "a")         # a list's, as written


def test_a_book_is_refused_with_its_path_and_the_products_words():
    """Each refusal as the product's `domainBooks` says it (its keys test, `speckeys_test.go`): a spec of either side
    loads, or is refused, alike on both (ADR-0012)."""
    at = "spec testsub: domain.books"
    for books, said in (
            ({"a": None}, f"{at}.a takes {{}} (carried, not shown) or {{show: [<field>…]}} — not <nil>"),
            ({"a": {"show": []}}, f"{at}.a.show names the fields of the book's entries a page is given, at least one — "
                                  f"not [] (a book not shown says no show)"),
            ({"a": {"show": ["token_secret"]}}, f'{at}.a.show: "token_secret" is a secret, and a secret is never shown'),
            ({"a": {"show": ["n", "n"]}}, f'{at}.a.show names "n" twice'),
            ({"a": {"show": ["Not"]}}, f'{at}.a.show: "Not" is not a field\'s name (lower case, digits, - and _)'),
            ({"A": {}}, f'{at}: "A" is not a name (lower case, digits, - and _)'),
            (["a", "a"], f'{at} names "a" twice'),
            ({"a": {"show": ["n"], "hide": ["m"]}}, f"{at}.a.hide: unknown key"),
            ("a", f"{at} is a list of names or a map {{<book>: {{}} | {{show: [<field>…]}}}}, not a")):
        assert _refusal(books) == said, (books, _refusal(books))
    # the substrings the product's keys test asks, every one
    for books, part in (({"a": {"show": ["n"], "hide": ["m"]}}, "domain.books.a.hide: unknown key"),
                        ({"a": {"show": []}}, "at least one"), ({"a": {"show": ["token_secret"]}}, "a secret is never shown"),
                        ({"a": {"show": ["n", "n"]}}, 'show names "n" twice'),
                        ({"a": None}, "takes {} (carried, not shown) or {show"),
                        ({"a": {"show": ["Not"]}}, "is not a field's name"), ({"A": {}}, '"A" is not a name'),
                        ("a", "a list of names or a map")):
        assert part in _refusal(books), (books, part)


def test_a_key_beside_show_is_no_key_of_a_spec():
    from w2cplatform.speckeys import unknown
    assert unknown({"domain": {"books": {"a": {"show": ["n"]}}}}) == []
    assert unknown({"domain": {"books": ["a"]}}) == []
    assert unknown({"domain": {"books": {"a": {"show": ["n"], "hide": ["m"]}}}}) == ["domain.books.a.hide"]


class Grants:
    """An `Access` with no cryptography: a token is a name, a grant is a line `(capability, unit or None, labels)`."""
    def __init__(self, grants):
        self.grants = grants

    def who(self, token):
        from w2cplatform.access import Denied
        if token not in self.grants:
            raise Denied(401, "token refused: nobody's")
        return {"sub": token}

    def may(self, payload, capability, unit, labels):
        rank = {"view": 0, "edit": 1, "admin": 2}
        mine = self.grants[payload["sub"]]
        if unit is None and capability == "view":
            return bool(mine)
        return any(rank[c] >= rank[capability] and ((set(lab) <= set(labels)) if lab else u in (unit, None))
                   for c, u, lab in mine)


def test_a_book_shows_the_named_fields_of_this_clusters_own_copy_each_item_to_a_viewer_of_its_unit():
    """Of each entry, the fields `show` names and nothing else — the road and its token, a secret item, an entry that is
    no JSON object stay in the process. An item keyed by a unit's `domain.ref` (testsub's: `name`) is seen by a viewer
    of that unit, by its id or by its labels; an item of no unit here only by a view of the whole cluster, which sees
    every item; somebody with no view at all is refused at the gate. A book carried and not shown, or none, is 404; a
    write is 405 — answered here, never handed to the holder."""
    from w2cplatform import catalog
    from w2cplatform.console import Mount, SpecConsole
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.spec import SpecController, SubsystemSpec
    from w2cplatform.variables import FileVariables

    s = SubsystemSpec.from_dict(_with_books({"tallies": {"show": ["n"]}, "counts": {}}))
    catalog.register(s, TESTSUB)                                   # the catalogue's testsub, a book shown
    root = tempfile.mkdtemp(prefix="books-")
    vars_ = FileVariables(os.path.join(root, "config"), volatile=True)
    objects = FsObjectStore(os.path.join(root, "objects"))
    wall = lambda: 1_757_500_000.0                                 # noqa: E731
    ctl = SpecController(s, vars_, objects, wall=wall, cluster="north")
    ctl.create({"name": "c1", "labels": ["room-a"]})
    ctl.create({"name": "c3"})                                     # c7: no unit here
    vars_.put("domain/testsub/tallies", {
        "c1": json.dumps({"n": 1, "road": {"url": "rtsp://relay/c1", "token_secret": "tk-north"}, "token": "tk-plain"}),
        "c2": "tk-bare", "c3": json.dumps({"n": 3}), "c4": json.dumps("tk-string"), "c5": json.dumps([1, "tk-list"]),
        "c7": json.dumps({"n": 7, "at": 5}), "note_secret": "between us"})
    vars_.put("domain/testsub/counts", {"c1": json.dumps({"n": 1})})
    m = Mount(SpecConsole(ctl, wall=wall))
    m.root.gate.impl = Grants({"boss": [("admin", None, [])], "eve": [("view", "testsub/c3", [])],
                               "lab": [("view", None, ["room-a"])], "kim": [("view", "testsub/c9", [])], "nobody": []})
    srv = m.serve("127.0.0.1", 0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def ask(method, path, token=None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        req = urllib.request.Request(base + path, method=method, headers=headers,
                                     data=b"{}" if method in ("POST", "PUT") else None)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()
    try:
        code, body = ask("GET", "/domain/testsub/books/tallies", "boss")
        assert code == 200 and json.loads(body) == {"c1": {"n": 1}, "c3": {"n": 3}, "c7": {"n": 7}}, (code, body)
        for kept in ("tk-north", "tk-plain", "tk-bare", "tk-string", "tk-list", "between us", "note_secret", "road",
                     "rtsp://", '"at"'):
            assert kept not in body, (kept, body)
        for who, want in (("eve", {"c3": {"n": 3}}), ("lab", {"c1": {"n": 1}}), ("kim", {})):
            code, body = ask("GET", "/domain/testsub/books/tallies", who)
            assert (code, json.loads(body)) == (200, want), (who, code, body)
        assert ask("GET", "/domain/testsub/books/tallies", "nobody")[0] == 403      # no view at all: the gate
        assert ask("GET", "/domain/testsub/books/tallies")[0] == 401
        code, body = ask("GET", "/domain/testsub/books/counts", "boss")
        assert code == 404 and "carried and not shown" in body and "tk" not in body, (code, body)
        code, body = ask("GET", "/domain/testsub/books/nothing", "boss")
        assert code == 404 and "testsub declares no book nothing" in json.loads(body)["detail"], (code, body)
        for method in ("POST", "PUT", "DELETE"):
            code, body = ask(method, "/domain/testsub/books/tallies", "boss")
            assert code == 405 and json.loads(body)["error"] == "GET /domain/testsub/books/<book>", (method, code, body)
    finally:
        srv.shutdown()
        srv.server_close()
        SubsystemSpec.load(TESTSUB)                                # the catalogue's testsub as its file says


def test_an_open_console_shows_every_item_and_a_spec_with_a_list_shows_none():
    """A cluster outside any domain has no gate: the console is open, and its book is the whole cluster's view. testsub
    as its file says carries `tallies` and shows nothing of it."""
    from w2cplatform.console import Mount, SpecConsole
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.spec import SpecController, SubsystemSpec
    from w2cplatform.variables import FileVariables
    from w2cplatform import catalog

    root = tempfile.mkdtemp(prefix="books-open-")
    vars_ = FileVariables(os.path.join(root, "config"), volatile=True)
    objects = FsObjectStore(os.path.join(root, "objects"))
    wall = lambda: 1_757_500_000.0                                 # noqa: E731
    vars_.put("domain/testsub/tallies", {"c7": json.dumps({"n": 7})})

    def serve(s):
        catalog.register(s, TESTSUB)
        srv = Mount(SpecConsole(SpecController(s, vars_, objects, wall=wall, cluster="north"), wall=wall)).serve(
            "127.0.0.1", 0)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/domain/testsub/books/tallies") as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
        finally:
            srv.shutdown()
            srv.server_close()
    try:
        assert serve(SubsystemSpec.from_dict(_with_books({"tallies": {"show": ["n"]}}))) == (200, {"c7": {"n": 7}})
        code, body = serve(SubsystemSpec.load(TESTSUB))
        assert code == 404 and "carried and not shown" in body["detail"], (code, body)
    finally:
        SubsystemSpec.load(TESTSUB)
