"""C5: named worker-owned families are not generic console CRUD tables."""
from tests.test_worker_pass import raw_spec, refused
from w2cplatform.spec import SubsystemSpec


def test_worker_owned_list_family_loads_and_console_has_no_crud_declaration():
    for name in ("testsub", "testsub2"):
        raw = raw_spec(name)
        raw["worker"] = {"writes": ["entries"]}
        spec = SubsystemSpec.from_dict(raw)
        assert spec.worker_writes == ("entries",)
        assert name + "/entries/*" in spec.acl_worker_role()
        assert not spec.table_specs
        assert name + "/entries/*" not in spec.acl_console()
        raw["worker"]["writes"] = ["items"]
        assert name + "/items/*" in SubsystemSpec.from_dict(raw).acl_worker_role()


def test_object_worker_table_keeps_its_fields_and_unknown_families_and_maps_are_refused():
    for name in ("testsub", "testsub2"):
        raw = raw_spec(name)
        del raw["door"]
        raw["tables"] = {"entries": {"key": "name", "fields": {"name": {"type": "string"}}}}
        raw["worker"] = {"writes": ["entries"]}
        spec = SubsystemSpec.from_dict(raw)
        assert "entries" in spec.table_specs
        assert name + "/entries/*" in spec.acl_worker_role()
        assert name + "/entries/*" not in spec.acl_console()
        raw["tables"] = ["entries"]
        raw["worker"]["writes"] = ["missing"]
        refused(raw)
        # ADR-0074's October 14 decision removes the former fields map, even for a declared family.
        raw["worker"]["writes"] = {"entries": ["name"]}
        refused(raw)


def test_worker_object_table_stays_typed_and_all_console_mutations_are_denied_before_body_read():
    import json
    from tests.conftest import Box
    from tests.test_worker_pass import Access, Handler, dispatch
    from w2cplatform.console import SpecConsole
    from w2cplatform.spec import SpecController
    from w2cplatform.tables import write_row
    from w2cplatform.cluster.rights import roles
    from w2cplatform.rights import allowed
    from w2cplatform.variables import Forbidden
    import pytest

    for name in ("testsub", "testsub2"):
        raw = raw_spec(name)
        del raw["door"]
        raw["tables"] = {"entries": {"key": "name", "fields": {"name": {"type": "string", "required": True},
            "size": {"type": "int"}, "ready": {"type": "bool"}, "identity": {"type": "string"}}}}
        raw["worker"] = {"writes": ["entries"]}
        spec, box = SubsystemSpec.from_dict(raw), Box()
        worker = box.vars.as_writer(name + "worker", spec.acl_worker_role())
        write_row(spec, "entries", worker, {"name": "a", "size": 7, "ready": True, "identity": "origin-a"})
        key = name + "/entries/a"
        before = box.vars.get(key)
        con = SpecConsole(SpecController(spec, box.vars, box.objects, wall=box.wall))
        con.gate.impl = Access()
        for path in ("/entries", "/entries/a"):
            h = Handler(path)
            assert dispatch(con, h, "GET", path) == 200
            data = json.loads(h.wfile.getvalue())
            row = data["entries"][0] if path == "/entries" else data
            assert row["size"] == 7 and row["ready"] is True and row["identity"] == "origin-a"
        class Unread:
            def read(self, n): raise AssertionError("worker-owned table mutation read the body")
        for method, path in (("POST", "/entries"), ("PUT", "/entries/a"), ("DELETE", "/entries/a")):
            h = Handler(path)
            h.rfile = Unread()
            assert dispatch(con, h, method, path) == 403
            assert json.loads(h.wfile.getvalue()) == {"error": "denied", "detail": "written by its worker"}
            assert box.vars.get(key) == before
        console = box.vars.as_writer("console", spec.acl_console())
        with pytest.raises(Forbidden):
            console.put(key, {"name": "edited"}, cas=before[1])
        with pytest.raises(Forbidden):
            console.delete(key, cas=before[1])
        compiled = roles([spec], "tests")["console"]
        assert not allowed(compiled["write"], key, "write")
        assert not allowed(compiled["delete"], key, "delete")
        assert allowed(compiled["read"], key, "read")


def test_named_family_never_gets_generic_crud_without_an_explicit_pass():
    from tests.conftest import Box
    from tests.test_worker_pass import Access, Client, Handler, dispatch
    from w2cplatform.console import SpecConsole
    from w2cplatform.spec import SpecController

    for name in ("testsub", "testsub2"):
        raw = raw_spec(name)
        del raw["door"]
        raw["worker"] = {"writes": ["entries"]}
        spec = SubsystemSpec.from_dict(raw)
        box, client = Box(), Client()
        con = SpecConsole(SpecController(spec, box.vars, box.objects, wall=box.wall), worker_client=client)
        con.gate.impl = Access()
        for method, path in (("GET", "/entries"), ("POST", "/entries"),
                             ("PUT", "/entries/name"), ("DELETE", "/entries/name")):
            assert dispatch(con, Handler(path), method, path) == 404
        assert not client.calls and not box.vars.list(name + "/entries/")
