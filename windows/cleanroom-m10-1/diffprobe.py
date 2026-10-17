"""Differential probe: the same requests to the clean-room door and to the course's old door; print where they differ."""
import json, socket, sys
sys.path.insert(0, "/Users/murat/cleanroom/m10-1/runner")
from harness import Instance
PY = "/private/tmp/adr74-venv/bin/python"
NEW = "python3.12 /Users/murat/cleanroom/m10-1/impl/server.py --data {data} --socket {socket} --role-prefix acc/ --body-limit {body_limit} --row-ceiling {row_ceiling}"
OLD = PY + " " + sys.argv[1] + " --source /Users/murat/w2c/server-vms-course/Source --data {data} --socket {socket} --body-limit {body_limit}"
W = "/v1/write"
def j(o): return json.dumps(o, ensure_ascii=False).encode()
CASES = [  # (guess, name, [steps]); a step is (method, target, body) or ("RAW", bytes)
 (7, "op wrong and key wrong", [("POST", W, j({"op": "bad", "key": "/x"}))]),
 (7, "key wrong and cas wrong", [("POST", W, j({"op": "put", "key": "/x", "items": {}, "cas": 5}))]),
 (7, "items wrong and cas wrong", [("POST", W, j({"op": "put", "key": "acc/a", "items": 5, "cas": 5}))]),
 (8, "no key", [("POST", W, j({"op": "put", "items": {}}))]),
 (8, "key is a number", [("POST", W, j({"op": "put", "key": 5, "items": {}}))]),
 (8, "guard.key is a number", [("POST", W, j({"op": "put", "key": "acc/a", "items": {}, "guard": {"key": 5, "index": ""}}))]),
 (8, "GET without key", [("GET", "/v1/get", None)]),
 (9, "id null", [("POST", W, j({"op": "put", "key": "acc/a", "items": {}, "id": None}))]),
 (9, "id empty", [("POST", W, j({"op": "put", "key": "acc/a", "items": {}, "id": ""}))]),
 (10, "plus in query", [("POST", W, j({"op": "put", "key": "acc/a b", "items": {"v": "space"}})),
                        ("POST", W, j({"op": "put", "key": "acc/a+b", "items": {"v": "plus"}})),
                        ("GET", "/v1/get?key=acc/a+b", None)]),
 (10, "repeated key", [("GET", "/v1/get?key=acc/a&key=acc/b", None)]),
 (10, "bad utf-8 in key", [("GET", "/v1/get?key=acc/%FF", None)]),
 (11, "list without prefix", [("POST", W, j({"op": "put", "key": "acc/z", "items": {}})), ("GET", "/v1/list", None)]),
 (12, "duplicate field", [("POST", W, b'{"op":"put","key":"acc/a","key":"acc/b","items":{}}')]),
 (12, "NaN in extra", [("POST", W, b'{"op":"put","key":"acc/a","items":{},"x":NaN}')]),
 (12, "BOM", [("POST", W, b'\xef\xbb\xbf{"op":"put","key":"acc/a","items":{}}')]),
 (12, "huge number in extra", [("POST", W, b'{"op":"put","key":"acc/a","items":{},"x":1' + b"0" * 400 + b"}")]),
 (22, "double slash key", [("POST", W, j({"op": "put", "key": "acc//b", "items": {}}))]),
 (22, "dot segment", [("POST", W, j({"op": "put", "key": "acc/./b", "items": {}}))]),
 (22, "trailing slash", [("POST", W, j({"op": "put", "key": "acc/b/", "items": {}}))]),
 (24, "size on body over limit", [("POST", W, b"x" * 1048577)]),
 (26, "unknown method", [("PATCH", "/v1/get?key=acc/a", None)]),
 (26, "no HTTP version", [("RAW", b"GET /v1/list\r\n\r\n")]),
 (26, "HTTP/1.0", [("RAW", b"GET /v1/list HTTP/1.0\r\n\r\n")]),
 (27, "lone surrogate in key", [("POST", W, b'{"op":"put","key":"acc/\\ud800","items":{}}')]),
 (27, "lone surrogate in items", [("POST", W, b'{"op":"put","key":"acc/a","items":{"\\ud800":"x"}}')]),
 (28, "replay cas null vs absent", [("POST", W, j({"op": "put", "key": "acc/a", "items": {}, "cas": "", "id": "ab01"})),
                                     ("POST", W, j({"op": "put", "key": "acc/a", "items": {}, "cas": "", "id": "ab01"})),
                                     ("POST", W, j({"op": "put", "key": "acc/r", "items": {}, "id": "ab02"})),
                                     ("POST", W, j({"op": "put", "key": "acc/r", "items": {}, "cas": None, "id": "ab02"}))]),
 (28, "replay items order", [("POST", W, b'{"op":"put","key":"acc/o","items":{"a":"1","b":"2"},"id":"ab03"}'),
                             ("POST", W, b'{"op":"put","key":"acc/o","items":{"b":"2","a":"1"},"id":"ab03"}')]),
 (30, "GET with body", [("GET", "/v1/list?prefix=acc/", b'{"x":1}')]),
 ("-", "delete absent", [("POST", W, j({"op": "delete", "key": "acc/none"}))]),
 ("-", "items value number", [("POST", W, j({"op": "put", "key": "acc/a", "items": {"n": 5}}))]),
 ("-", "prefix without trailing slash", [("POST", W, j({"op": "put", "key": "acc/pq", "items": {}})), ("GET", "/v1/list?prefix=acc/p", None)]),
]
def raw(inst, data):
    s = socket.socket(socket.AF_UNIX); s.settimeout(10); s.connect(inst.socket); s.sendall(data)
    out = b""
    try:
        while chunk := s.recv(65536): out += chunk
    except OSError: pass
    s.close()
    head = out.split(b"\r\n", 1)[0].decode(errors="replace")
    body = out.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in out else b""
    return head, body
def norm(resp):
    if isinstance(resp, tuple):
        code, body = resp
    else:
        code, body = resp.status, resp.body
    try:
        b = json.loads(body); b.pop("error", None) if isinstance(b, dict) else None
        if isinstance(b, dict):
            for k in ("index",): b[k] = "<v>" if k in b and b[k] else b.get(k)
    except Exception:
        b = body[:80]
    return code, b
def run(template, steps):
    inst = Instance(template)
    try:
        out = []
        for st in steps:
            try:
                r = raw(inst, st[1]) if st[0] == "RAW" else inst.door.request(st[0], st[1], st[2])
                out.append(norm(r))
            except Exception as e:
                out.append(("transport", type(e).__name__ + ": " + str(e)[:60]))
        return out
    finally:
        inst.close()
diff = 0
for g, name, steps in CASES:
    a, b = run(NEW, steps), run(OLD, steps)
    same = a == b
    diff += not same
    print(("same " if same else "DIFF ") + f"#{g} {name}")
    if not same:
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y: print(f"     step {i+1}: clean={x}\n             old  ={y}")
print(f"{diff} of {len(CASES)} probes differ")
