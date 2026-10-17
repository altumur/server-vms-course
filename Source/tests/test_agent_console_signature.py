"""C2: durable CRUD queue, a signed local console, closed route set; testsub only."""

from tests.frozen_data import frozen_testdata
import json
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import yaml
from w2cplatform import catalog
from w2cplatform.cluster.variables import FakeVariables
from w2cplatform.console import Mount, SpecConsole
from w2cplatform.domain.api import ApiError, ConsoleAPI
from w2cplatform.domain.federation import Unreachable
from w2cplatform.objects import FsObjectStore
from w2cplatform.spec import SpecController, SubsystemSpec
from w2cplatform.trust.memberkey import MemberKey, sign_request


class Clock:
    def __init__(self): self.t = 1757500000.0
    def __call__(self): return self.t


@contextmanager
def site():
    raw = yaml.safe_load((frozen_testdata() / "testsub.subsystem.yaml").read_text())
    specs = [SubsystemSpec.from_dict({**json.loads(json.dumps(raw).replace("testsub/", sub+"/")), "name": sub}) for sub in ("testsub", "testsub2")]
    wall, vars_ = Clock(), FakeVariables()
    key = MemberKey.load_or_make(vars_)
    vars_.put("domain/members", {"doc": json.dumps({"rev": 1, "members": {"north": {"key": key.pub, "seal": key.seal_pub}}})})
    with patch.object(catalog, "_loaded", {s.name: s for s in specs}), patch.object(catalog, "_derived", {}):
        yield SimpleNamespace(specs=specs, vars=vars_, key=key, wall=wall)


def raises(status, fn):
    try:
        fn()
    except ApiError as err:
        assert err.status == status, err
        return
    raise AssertionError("the operation was accepted")


@contextmanager
def console(e):
    objects = FsObjectStore(tempfile.mkdtemp())
    mounts = {}
    for s in e.specs:
        ctl = SpecController(s, e.vars, objects, wall=e.wall)
        mounts[s.name] = SpecConsole(ctl, wall=e.wall)
    root = mounts.pop("testsub")
    server = Mount(root, mounts).serve("127.0.0.1", 0)
    try:
        yield "http://127.0.0.1:"+str(server.server_address[1])
    finally:
        server.shutdown(); server.server_close()


def send(url, method, path, raw, key, signing_key, wall, signature_path=None, query=""):
    headers = {"Content-Type": "application/json", "Idempotency-Key": key,
        "X-Agent-Signature": sign_request(signing_key, method, signature_path or path, raw, wall())}
    req = Request(url+path+query, data=raw, method=method, headers=headers)
    try:
        with urlopen(req, timeout=5) as reply:
            return reply.status, json.loads(reply.read())
    except HTTPError as err:
        return err.code, json.loads(err.read())


def test_agent_signature_opens_only_unit_crud_and_preserves_subsystem_prefix_and_replay():
    with site() as e, console(e) as url:
        for s in e.specs:
            path = "/"+s.name+"/"+s.rows
            key = "create-"+s.name
            raw = json.dumps({s.domain.ref: "badge"}, sort_keys=True).encode()
            status, result = send(url, "POST", path, raw, key, e.key, e.wall)
            assert status == 201, (status, result)
            assert send(url, "POST", path, raw, key, e.key, e.wall) == (status, result)
            assert send(url, "POST", path, b'{"name":"other"}', key, e.key, e.wall)[0] == 422
            assert send(url, "PUT", path+"/badge", b'{"start":4}', "edit-"+s.name, e.key, e.wall)[0] == 200
            assert send(url, "DELETE", path+"/badge", b'{}', "delete-"+s.name, e.key, e.wall)[0] == 200
            for foreign in ("/domain/placement", "/servers/s/labels", "/"+s.name+"/policy", "/"+s.name+"/requests"):
                assert send(url, "PUT", foreign, b'{}', "escape", e.key, e.wall)[0] == 403
            assert send(url, "POST", path, b'{"name":"wrong"}', "wrong-key", MemberKey.new(), e.wall)[0] == 403
            assert send(url, "POST", path, b'{"name":"wrong"}', "wrong-path", e.key, e.wall,
                        signature_path="/"+s.rows)[0] == 403
            assert send(url, "PUT", path+"/badge", b'{"password_secret":"private"}', "secret", e.key, e.wall)[0] == 400
            assert send(url, "PUT", path+"/badge", b'{"step":4}', "undeclared", e.key, e.wall)[0] == 400
        old = Clock(); old.t -= 61
        assert send(url, "POST", "/testsub/counters", b'{"name":"old"}', "old", e.key, old)[0] == 403
