"""The request trace: what a cluster's processes say to the store, in the product's own API.

The lessons show every store call as the request the handle sends to its server's configstore daemon — the role's
socket, the method and route, the body, the answer:

    # vmsworker w-srv-a-1 on srv-a → /run/configstore/vmsworker.sock
    POST /v1/write {"op": "put", "key": "vms/slots/w-srv-a-1", "cas": "", "items": {…}}
    → 200 {"index": 1004}

Written by hand, those examples drift from the code the first time the code changes. So they are not written by
hand: the stand runs the real controller, workers and console through the real handle (`ConfigstoreVariables`),
whose transport is the daemon's own API over the daemon's own state machine in this process
(`storemachine.local_transport`), and `TraceLog.transport` records each request and answer as it passes — the
bytes the handle would have put on the socket, nothing rebuilt. `test_trace.py` sends the same calls over a real
unix socket and compares.

Two things are left out of what is printed, and only out of the printing: the operation id (`"id"` in every write,
a fresh uuid per call — a trace must read the same on every run), and the percent-encoding of the query (`key=vms/…`,
not `key=vms%2F…`). A write's body is printed with `op`, `key` and `cas` first, so its first line says what is asked.

Objects are files on each server now (`cluster://`) and are not in the store's trace. A scene about them turns on
`objects=True`, and the stand's object stores add their own lines: a file written on a server, and a request to the
resource on the reader's server (`GET /v1/objects?…`).

    log = TraceLog(roots={"/tmp/clustervms-x1": "/data"})
    h = ConfigstoreVariables(path, transport=log.transport("console on srv-a", path, local_transport(...)))
    ...
    print(log.render())
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from urllib.parse import unquote


@dataclass
class Call:
    who: str
    door: str
    method: str
    target: str
    body: dict | None
    status: int
    answer: object
    kind: str = "store"                 # "store" | "objects" | "file" | "join"

    @property
    def op(self) -> str:
        """`get`, `list`, `put`, `delete` — what a store call asked; the method for anything else."""
        if self.kind == "store" and self.target.startswith("/v1/get"):
            return "get"
        if self.kind == "store" and self.target.startswith("/v1/list"):
            return "list"
        if self.kind == "store" and isinstance(self.body, dict):
            return str(self.body.get("op", self.method))
        return self.method

    @property
    def write(self) -> bool:
        return self.op in ("put", "delete")


def body_shown(body: dict) -> dict:
    """A write's body as printed: no operation id, `op`, `key` and `cas` first."""
    shown = {k: body[k] for k in ("op", "key", "cas") if k in body}
    shown.update({k: v for k, v in body.items() if k not in shown and k != "id"})
    return shown


@dataclass
class TraceLog:
    roots: dict = field(default_factory=dict)          # temporary paths -> what the lesson shows instead
    calls: list = field(default_factory=list)
    objects: bool = False                              # record object operations too (a scene about them)

    def mark(self) -> int:
        return len(self.calls)

    def _clean(self, s: str) -> str:
        for real, shown in self.roots.items():
            s = s.replace(real, shown)
        return s

    def transport(self, who: str, door: str, inner):
        """`inner` — a `ConfigstoreVariables` transport — with every request and answer recorded under `who`."""
        def call(method: str, target: str, raw: bytes | None, headers: dict, timeout: float) -> tuple[int, bytes]:
            code, got = inner(method, target, raw, headers, timeout)
            try:
                answer = json.loads(got or b"{}")
            except ValueError:
                answer = got.decode(errors="replace")
            self.calls.append(Call(who, door, method, target, json.loads(raw) if raw else None, code, answer))
            return code, got
        return call

    def render(self, since: int = 0, until: int | None = None, who: bool = True, width: int = 110,
               writes: bool = False, kinds: tuple | None = None) -> str:
        out = []
        for c in self.calls[since:until]:
            if writes and not c.write:
                continue
            if kinds is not None and c.kind not in kinds:
                continue
            if who:
                out.append(f"# {c.who} → {c.door}")
            out += self._request(c, width)
            if c.kind != "file":
                ans = c.answer
                text = "" if ans is None else " " + json.dumps(ans, ensure_ascii=False,
                                                               indent=2 if len(json.dumps(ans)) > width else None)
                out.append(f"→ {c.status}{text}")
            out.append("")
        return self._clean("\n".join(out).rstrip() + "\n")

    @staticmethod
    def _request(c: Call, width: int) -> list[str]:
        line = f"{c.method} {unquote(c.target)}"
        if c.body is None:
            return [line]
        body = body_shown(c.body) if c.kind == "store" else c.body
        whole = f"{line} {json.dumps(body, ensure_ascii=False)}"
        if len(whole) <= width or not isinstance(body.get("items"), dict) or not body["items"]:
            return [whole]
        head = {k: v for k, v in body.items() if k != "items"}
        first = json.dumps(head, ensure_ascii=False)[:-1] + ', "items": {'
        rows = [f'  {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}'
                for k, v in body["items"].items()]
        return [f"{line} {first}", *[r + "," for r in rows[:-1]], rows[-1], "}}"]
