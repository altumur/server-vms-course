"""М10/1 Н2.1: the same request form on real stores, plus raw HTTP that TSV cannot carry."""
import http.client
import json
import os
import socket
import tempfile
from contextlib import contextmanager

from tests.storage_acceptance import NativeAPI, request
from w2cplatform.configstore import LocalBackend, StoreDaemon
from w2cplatform.memvariables import MemVariables
from w2cplatform.storemachine import Rights, StoreMachine, answer
from w2cplatform.variables import FileVariables


@contextmanager
def _executors():
    with tempfile.TemporaryDirectory() as root:
        machine = StoreMachine()
        daemon = StoreDaemon(LocalBackend(), node_id="parse", sockets=os.path.join(root, "sockets"))
        path = os.path.join(root, "sockets", "admin.sock")
        try:
            yield {
                "machine": lambda method, target, raw: answer(method, target, raw, "admin", Rights(), machine.apply),
                "file": NativeAPI(FileVariables(os.path.join(root, "file"), volatile=True)).request,
                "memory": NativeAPI(MemVariables()).request,
                "http": lambda method, target, raw: request(path, method, target, raw),
            }
        finally:
            daemon.stop()


def _fault(result, status, kind):
    code, body = result
    assert code == status and body["kind"] == kind, result
    assert isinstance(body.get("error"), str) and body["error"], result
    assert set(body) == {"kind", "error"}, result


def test_command_validation_order_precedes_side_effects_on_every_executor():
    cases = [
        (b'{"op":"other","key":"/bad"}', "badrequest"),
        (b'{"op":"put","key":5,"items":{}}', "badrequest"),
        (b'{"op":"put","key":"/bad","items":5}', "badkey"),
        (b'{"op":"put","key":"acc/a","items":5,"guard":{"key":"/bad","index":""}}', "badrequest"),
        (b'{"op":"put","key":"acc/a","items":{},"cas":5,"guard":{"key":"/bad","index":""}}', "badrequest"),
        (b'{"op":"put","key":"acc/a","items":{},"guard":{"key":"/bad","index":""},"id":null}', "badkey"),
        (b'{"op":"put","key":"acc/a","items":{},"guard":{"key":"","index":""}}', "badrequest"),
        (b'{"op":"put","key":"acc/a","items":{},"guard":{"key":"\\ud800","index":""}}', "badkey"),
        (b'{"op":"put","key":"acc/\\ud800","items":{}}', "badkey"),
        (b'{"op":"put","key":"acc/a","items":{"v":"\\ud800"}}', "badrequest"),
        (b'{"op":"put","key":"acc/a","items":{"\\ud800":"v"}}', "badrequest"),
        (b'{"op":"put","key":"acc/a","items":{},"id":null}', "badrequest"),
    ]
    with _executors() as executors:
        for name, call in executors.items():
            for raw, kind in cases:
                _fault(call("POST", "/v1/write", raw), 400, kind)
                assert call("GET", "/v1/list?prefix=acc/", b"") == (200, {"keys": {}}), name


def test_query_names_are_unique_and_prefixes_compare_original_bytes():
    with _executors() as executors:
        for name, call in executors.items():
            for key in ("acc/é", "acc/%zz", "acc/a b", "acc/a+b"):
                code, _ = call("POST", "/v1/write", json.dumps({"op": "put", "key": key, "items": {}}).encode())
                assert code == 200, name
            _fault(call("GET", "/v1/get?key=acc/a&%6Bey=acc/b", b""), 400, "badrequest")
            _fault(call("GET", "/v1/get?irrelevant=x", b""), 400, "badrequest")
            _fault(call("GET", "/v1/get?key=acc/%FF", b""), 400, "badkey")
            _fault(call("GET", "/v1/list?prefix=acc/&pre%66ix=other/", b""), 400, "badrequest")
            assert list(call("GET", "/v1/list?prefix=acc/%C3", b"")[1]["keys"]) == ["acc/é"], name
            assert call("GET", "/v1/list?prefix=acc/%FF", b"") == (200, {"keys": {}}), name
            for target in ("/v1/get?key=acc/%zz", "/v1/get?key=acc/a+b", "/v1/get?key=acc/a%2Bb"):
                assert call("GET", target + "&x=a&x=b", b"bad JSON")[1]["items"] == {}, (name, target)
            assert len(call("GET", "/v1/list", b"")[1]["keys"]) == 4


def test_json_syntax_is_strict_but_unread_fields_do_not_acquire_value_rules():
    refused = [
        b'{"op":"put","key":"acc/a","items":{},"x":{"a":1,"a":2}}',
        b'{"op":"put","key":"acc/a","items":{},"x":[{"a":1,"a":2}]}',
        b'{"op":"put","key":"acc/a","items":{},"x":Infinity}',
        b'{"op":"put","key":"acc/a","items":{},"x":-Infinity}',
        b'\xef\xbb\xbf{"op":"put","key":"acc/a","items":{}}',
        b'{"op":"put","key":"acc/a","items":{"v":"\xff"}}',
        b'{"op":"put","key":"acc/a","items":{},"cas":0.0}',
        b'{"op":"put","key":"acc/a","items":{},"x":' + b'[' * 64 + b'0' + b']' * 64 + b'}',
    ]
    with _executors() as executors:
        for name, call in executors.items():
            for raw in refused:
                _fault(call("POST", "/v1/write", raw), 400, "badrequest")
            extras = [b'"\\udc00"', b'9' * 5000, b'1e' + b'9' * 5000,
                      b'[' * 63 + b'0' + b']' * 63]
            for extra in extras:
                raw = b'{"op":"put","key":"acc/a","items":{},"id":"a1","x":' + extra + b'}'
                code, body = call("POST", "/v1/write?key=x&key=y", raw)
                assert code == 200, (name, code, body)
            # Unread extras do not change the replay fingerprint, even when their types change.
            assert body["again"] is True
            assert call("GET", "/v1/get?key=acc/a", b"")[1]["items"] == {}


def _raw(path, raw):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(5)
        connection.connect(path)
        connection.sendall(raw)
        connection.shutdown(socket.SHUT_WR)
        response = http.client.HTTPResponse(connection)
        response.begin()
        assert response.getheader("Content-Type") == "application/json"
        return response.status, json.loads(response.read())


def test_raw_http_failures_have_fault_envelopes_and_declared_parsing_bounds():
    from w2cplatform.configstore import MAX_HEADER_BYTES, MAX_HEADER_COUNT, MAX_REQUEST_LINE
    with tempfile.TemporaryDirectory() as root:
        daemon = StoreDaemon(LocalBackend(), node_id="http", sockets=root)
        path = os.path.join(root, "admin.sock")
        try:
            for raw in (
                b"GET /v1/list\r\n\r\n",
                b"GET /v1/list HTTP/2.0\r\n\r\n",
                b"GET /v1/list extra HTTP/1.1\r\n\r\n",
                b"GET /v1/list HTTP/1.1\r\nHeader without colon\r\n\r\n",
                b"GET /v1/list HTTP/1.1\r\nBad Name: value\r\n\r\n",
                b"GET /v1/list HTTP/1.1\r\nX: value\r\n folded\r\n\r\n",
                b"GET /v1/list HTTP/1.1\r\nX : value\r\n\r\n",
                b"GET /v1/list HTTP/1.1\r\nX: unfinished",
                b"GET /" + b"a" * (MAX_REQUEST_LINE - len(b"GET / HTTP/1.1\r\n") + 1) + b" HTTP/1.1\r\n\r\n",
                b"GET /v1/list HTTP/1.1\r\nX: " + b"a" * MAX_HEADER_BYTES + b"\r\n\r\n",
                b"GET /v1/list HTTP/1.1\r\n" + b"X: a\r\n" * (MAX_HEADER_COUNT + 1) + b"\r\n",
            ):
                _fault(_raw(path, raw), 400, "badrequest")
            for target in (b"PATCH /v1/get", b"DELETE /v1/write", b"GET //v1/list", b"GET /not-a-route",
                           b"GET http://localhost/v1/get?key=acc/x"):
                _fault(_raw(path, target + b" HTTP/1.1\r\n\r\n"), 404, "badrequest")
            head = b"GET /v1/list?prefix="
            line = head + b"a" * (MAX_REQUEST_LINE - len(head) - len(b" HTTP/1.1\r\n")) + b" HTTP/1.1\r\n\r\n"
            assert _raw(path, line) == (200, {"keys": {}})
            block = b"X: " + b"a" * (MAX_HEADER_BYTES - len(b"X: \r\n\r\n")) + b"\r\n\r\n"
            assert _raw(path, b"GET /v1/list HTTP/1.1\r\n" + block) == (200, {"keys": {}})
            assert _raw(path, b"GET /v1/list HTTP/1.1\r\n" + b"X: a\r\n" * MAX_HEADER_COUNT + b"\r\n") == (200, {"keys": {}})
            assert _raw(path, b"GET /v1/list HTTP/1.0\r\n\r\n") == (200, {"keys": {}})
            # A GET body is unread, even when its alleged size exceeds the POST limit and none arrives.
            assert _raw(path, b"GET /v1/list HTTP/1.1\r\nContent-Length: 999999999\r\n\r\n") == (200, {"keys": {}})
        finally:
            daemon.stop()


def test_chunked_body_is_measured_after_decoding_and_oversize_has_no_size():
    with tempfile.TemporaryDirectory() as root:
        daemon = StoreDaemon(LocalBackend(), node_id="chunks", sockets=root, body_limit=64)
        path = os.path.join(root, "admin.sock")
        headers = b"POST /v1/write HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n"
        try:
            body = b'{"op":"put","key":"acc/a","items":{}}'.ljust(64)
            chunks = b"".join(b"1\r\n" + bytes([c]) + b"\r\n" for c in body) + b"0\r\n\r\n"
            assert _raw(path, headers + chunks)[0] == 200
            both = headers.replace(b"\r\n\r\n", b"\r\nContent-Length: 999999999\r\n\r\n")
            assert _raw(path, both + chunks)[0] == 200  # RFC 9112: chunked takes precedence
            code, fault = _raw(path, headers + b"41\r\n")
            assert code == 413 and fault["kind"] == "toolarge" and fault["limit"] == 64
            assert set(fault) == {"kind", "error", "limit"}  # total size is unknown
            for chunks in (b"z\r\n", b"3\r\n{}\r\n", b"0\r\nBad Trailer\r\n\r\n"):
                _fault(_raw(path, headers + chunks), 400, "badrequest")
            assert request(path, "GET", "/v1/get?key=acc/a", b"")[1]["items"] == {}
        finally:
            daemon.stop()


def test_nonvoting_door_keeps_retries_named_when_unread_numbers_are_huge():
    from w2cplatform.configstoredoor import DoorDaemon
    door = DoorDaemon.__new__(DoorDaemon)
    door.node_id = "parse"
    door.rights = Rights({"writer": {"write": ["acc/*"]}})
    forwarded = []
    def pass_on(method, target, raw, role, deadline, named):
        forwarded.append(named)
        return 200, {"index": "1"}
    door.pass_on = pass_on
    raw = b'{"op":"put","key":"acc/a","items":{},"id":"a1","x":' + b'9' * 5000 + b'}'
    assert door.serve("POST", "/v1/write", raw, "writer", 1) == (200, {"index": "1"})
    assert forwarded == [True]
    _fault(door.serve("POST", "/v1/write", b'{"id":"a1","id":"b2"}', "writer", 1), 400, "badrequest")
    _fault(door.serve("GET", "http://[", b"", "writer", 1), 404, "badrequest")
    assert forwarded == [True]  # both refusals were local, before reaching a voter


def test_ignored_and_refused_bodies_do_not_truncate_tls_replies_when_the_door_closes():
    from tests.test_configstorevars import TLS, _dial
    from w2cplatform import tls
    context = tls.client_context(os.path.join(TLS, "srv-b"))
    with tempfile.TemporaryDirectory() as root:
        daemon = StoreDaemon(LocalBackend(), node_id="srv-a", sockets=root, api=("127.0.0.1", 0),
                             tls_dir=os.path.join(TLS, "srv-a"), body_limit=64)
        try:
            for _ in range(32):
                code, body = _dial(daemon.api_url, context, "srv-a", "GET", "/v1/status", b"ignored, not JSON")
                assert code == 200 and body["rows"] == 0
                _fault(_dial(daemon.api_url, context, "srv-a", "PATCH", "/v1/get", b"ignored"), 404, "badrequest")
                code, body = _dial(daemon.api_url, context, "srv-a", "POST", "/v1/write", b"!" * 65)
                assert code == 413 and body["kind"] == "toolarge" and body["limit"] == 64
                assert isinstance(body["error"], str)
        finally:
            daemon.stop()
