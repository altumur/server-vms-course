"""C2: a domain reference resolves to one member's local ID before queueing."""

from tests.frozen_data import frozen_testdata
import json
import threading
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import yaml

from w2cplatform import catalog
from w2cplatform.cluster.variables import FakeVariables
from w2cplatform.domain.api import ApiError, ConsoleAPI
from w2cplatform.domain.console import Console
from w2cplatform.domain.federation import Cluster, DomainDirectory, Federation, Unreachable
from w2cplatform.domain.pending import PendingEdits
from w2cplatform.spec import SubsystemSpec
from w2cplatform.trust.memberkey import MemberKey


class Objects:
    """Only published snapshots, with an independently unreachable member."""
    def __init__(self):
        self.data, self.up = {}, True

    def get(self, key):
        if not self.up:
            raise Unreachable("member snapshot unavailable")
        return self.data.get(key)

    def list(self, prefix):
        if not self.up:
            raise Unreachable("member listing unavailable")
        return sorted(k for k in self.data if k.startswith(prefix))


def row(local_id="local-counter", sub="testsub", ref="SERIAL-42"):
    return {"id": local_id, "name": local_id, "serial": ref, "ref": ref, "sub": sub,
            "worker": "w1", "server": "server1", "start": 1}


@contextmanager
def site():
    raw = yaml.safe_load((frozen_testdata() / 'testsub.subsystem.yaml').read_text())
    raw["unit"]["fields"]["serial"] = {"type": "string", "required": True}
    raw["domain"]["ref"] = "serial"
    raw["snapshot"].append("serial")
    specs = [SubsystemSpec.from_dict({**json.loads(json.dumps(raw).replace("testsub/", sub + "/")), "name": sub})
             for sub in ("testsub", "testsub2")]
    variables = FakeVariables()
    key = MemberKey.load_or_make(variables)
    members = {name: {"key": key.pub, "seal": key.seal_pub} for name in ("north", "south")}
    variables.put("domain/members", {"doc": json.dumps({"rev": 1, "members": members})})
    now = lambda: 1757500000.0
    objects = {name: Objects() for name in members}
    fed = Federation({name: Cluster(name, FakeVariables(), objects[name]) for name in members})
    directory, pending = DomainDirectory(fed, now), PendingEdits(variables, now)
    known, asked = {}, []
    def last_known(ref):
        asked.append(ref)
        return known.get(ref)
    def direct_console(_):
        raise AssertionError("the domain must queue rather than call a member console")
    with patch.object(catalog, "_loaded", {s.name: s for s in specs}), patch.object(catalog, "_derived", {}):
        api = ConsoleAPI(directory, pending=pending, last_known=last_known)
        def publish(member, *rows):
            for sub in ("testsub", "testsub2"):
                objects[member].data[sub + "/snapshot/w1"] = json.dumps({
                    "ts": now(), "counters": [r for r in rows if r["sub"] == sub]}).encode()
        yield SimpleNamespace(api=api, directory=directory, pending=pending, variables=variables,
                              objects=objects, known=known, asked=asked, publish=publish)


@contextmanager
def http(e):
    con = Console(e.directory, None, e.api, pending=e.pending, holder_vars=e.variables)
    server = ThreadingHTTPServer(("127.0.0.1", 0), con.handler())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = "http://127.0.0.1:" + str(server.server_address[1])
    def call(method, path, key, body=None):
        request = Request(url + path, method=method, data=json.dumps(body or {}).encode(),
                          headers={"Content-Type": "application/json", "Idempotency-Key": key})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)
    try:
        yield call
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
        assert not thread.is_alive()


def rejected(fn, status=None):
    try:
        fn()
    except ApiError as error:
        if status is not None:
            assert error.status == status, error
        else:
            assert 400 <= error.status < 600, error
        return
    raise AssertionError("an unresolved reference was queued")


def no_edits(e):
    assert e.pending.of("north") == {} and e.pending.of("south") == {}


def test_api_and_http_resolve_a_domain_serial_to_the_current_members_local_id():
    with site() as e:
        current = row()
        e.publish("north", current)
        # A previous view is not allowed to overwrite the current local identity.
        e.known["SERIAL-42"] = ("north", row("obsolete-local"))
        result = e.api.update_unit("SERIAL-42", {"start": 7}, "api-current", sub="testsub")
        assert e.pending.of("north")[result["kept"]]["path"] == "/testsub/counters/local-counter"
        with http(e) as call:
            for method in ("PUT", "DELETE"):
                status, result = call(method, "/domain/testsub/counters/SERIAL-42", "http-" + method,
                                      {"start": 9} if method == "PUT" else {})
                assert status == 202, (status, result)
                edit = e.pending.of("north")[result["kept"]]
                assert edit["method"] == method and edit["path"] == "/testsub/counters/local-counter"
        assert e.pending.of("south") == {}


def test_complete_current_absence_cannot_resurrect_a_last_known_unit():
    with site() as e:
        e.known["SERIAL-42"] = ("north", row())
        rejected(lambda: e.api.update_unit("SERIAL-42", {"start": 7}, "api-absent", sub="testsub"), 404)
        with http(e) as call:
            for method in ("PUT", "DELETE"):
                status, reply = call(method, "/domain/testsub/counters/SERIAL-42", "absent-" + method,
                                     {"start": 7} if method == "PUT" else {})
                assert status == 404, (status, reply)
        no_edits(e)


def test_contested_current_owners_cannot_be_resolved_from_last_known():
    with site() as e:
        e.publish("north", row("north-local"))
        e.publish("south", row("south-local"))
        e.known["SERIAL-42"] = ("north", row("north-local"))
        rejected(lambda: e.api.update_unit("SERIAL-42", {"start": 7}, "api-contested", sub="testsub"), 409)
        with http(e) as call:
            status, reply = call("PUT", "/domain/testsub/counters/SERIAL-42", "http-contested", {"start": 7})
            assert status == 409, (status, reply)
        no_edits(e)


def test_only_an_unreachable_known_owner_allows_queueing_from_its_previous_view():
    with site() as e:
        e.known["SERIAL-42"] = ("north", row("offline-local"))
        e.objects["north"].up = False
        result = e.api.update_unit("SERIAL-42", {"start": 7}, "api-offline", sub="testsub")
        assert result["cluster"] == "north"
        assert e.pending.of("north")[result["kept"]]["path"] == "/testsub/counters/offline-local"
        with http(e) as call:
            status, result = call("DELETE", "/domain/testsub/counters/SERIAL-42", "http-offline")
            assert status == 202, (status, result)
            assert e.pending.of("north")[result["kept"]]["path"] == "/testsub/counters/offline-local"
        assert e.pending.of("south") == {}


def test_an_unreachable_other_member_does_not_revive_an_absent_known_owner():
    with site() as e:
        e.known["SERIAL-42"] = ("north", row())
        e.objects["south"].up = False
        rejected(lambda: e.api.update_unit("SERIAL-42", {"start": 7}, "api-other-down", sub="testsub"), 503)
        with http(e) as call:
            status, reply = call("PUT", "/domain/testsub/counters/SERIAL-42", "http-other-down", {"start": 7})
            assert status == 503, (status, reply)
        no_edits(e)


def test_a_last_known_unit_of_another_subsystem_cannot_resolve_this_route():
    with site() as e:
        e.known["SERIAL-42"] = ("north", row(sub="testsub2"))
        e.objects["north"].up = False
        rejected(lambda: e.api.update_unit("SERIAL-42", {"start": 7}, "api-other-sub", sub="testsub"))
        with http(e) as call:
            status, reply = call("PUT", "/domain/testsub/counters/SERIAL-42", "http-other-sub", {"start": 7})
            assert 400 <= status < 600, (status, reply)
        no_edits(e)


def test_a_current_unit_of_another_subsystem_cannot_resolve_this_route():
    with site() as e:
        e.publish("north", row(sub="testsub2"))
        rejected(lambda: e.api.update_unit("SERIAL-42", {"start": 7}, "api-current-sub", sub="testsub"))
        with http(e) as call:
            status, reply = call("DELETE", "/domain/testsub/counters/SERIAL-42", "http-current-sub")
            assert 400 <= status < 600, (status, reply)
        no_edits(e)
