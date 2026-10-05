"""The domain's console — the process that serves the domain's door to browsers and tools, in the standard library.
The domain holder runs it pointed at every cluster. Every route but `/healthz` is the platform's and the specs'
(`declared`): what a subsystem's units are called, which of its rows the door serves — never a route a subsystem wrote.

ONE SET OF PATHS, LITERALLY (the contract of the console module, §10a; ADR-0003): every human route of the holder
lives under `/domain/*`, the same path a cluster console forwards without rewriting, and the page on either is the
platform's module. `/api/*` is the processes' (`signer_service.py`: carry, member, relay, holder, login) — none here.

    GET  /domain                                the domain's view, as the pass composed it (`ReadView.doc`): the
                                                members (a list, the holder among them), the topology, who knocks
    GET  /domain/keys                           every key under `domain/` in the holder's stores (`keysview.py`)
    GET  /spec, /mounts                         for the module: no root (`{name: "", rows: null}` — the page says
                                                `sections: ["domain"]`), and every spec this process loaded
                                                (`SPEC_DIR`) a mount, `{root: "", mounts: {<sub>: describe}}`
    GET  /domain/<sub>/<rows>?q=&page=&size=&cluster=   the read model of a subsystem of the directory (`<rows>`: its
                                                spec's name for its units), with each row's age and its cluster's state
    PUT  /domain/<sub>/<rows>/<ref>             proxied to the owning cluster's console; Idempotency-Key required;
                                                refuses placement fields, and any field but its spec's `domain.edit`
    GET  /domain/<sub>/<table>                  a row a spec keeps at the holder and serves (`domain.tables`), as kept
    GET  /domain/causes                         silence grouped by failure domain: one server, one cause
    GET  /domain/where/<ref>                    the directory of directories, incompleteness included
    GET  /domain/members                        the domain's members: who, admitted how and when, which root each
                                                pinned (`pinned`), and who is knocking
    POST /domain/members                        {name} — accept one that is knocking: an admin of the domain only
    DELETE /domain/members/<name>               a member leaves: an admin of the domain only
    GET  /domain/topology                       the domain's topology: centre, star relays, who reaches it via whom
    PUT  /domain/topology                       {base_rev, centre?, star?, via?} — CAS, checked; an admin of the
                                                domain only (`topology.py`)
    PUT  /domain/break-glass/<cluster>          {password} — that cluster's emergency password set or rotated: its
                                                hash, sealed (`breakglass.py`); an admin of the domain only
    GET  /healthz

What a subsystem computes or streams on the domain — a catalogue of what one unit may ask another, its own numbers — is
its worker's door, which a page reaches by the address the shared view names; it is not this door's.

Each pass also leaves what it saw as `domain/view` in the domain holder's object store, which that cluster's
own console serves at `GET /domain` (feedback X): one tree for a site whose domain lives in its server room. Its
`url` is this door (`CONSOLE_URL`, else `http://CONSOLE_HOST:CONSOLE_PORT`): where that console forwards `/domain/X`.

Stateless: kill it, start another, the first pass rebuilds everything.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from w2cplatform.console import Deadlined, open_doors, read_body
from w2cplatform.variables import Conflict

from . import declared
from .api import ApiError, ConsoleAPI
from .federation import DomainDirectory
from .readview import ReadView

log = logging.getLogger("domain.console")
# The tables of what others wrote that `/healthz` counts (`w2cplatform.rows`): members' objects, grants, user records,
# and the trust rows a cluster holds (the review's eighth pass: "counted, named" — and shown).
GARBLED_SHOWN = ("member_object", "grant", "user", "trust_row")
# The holder's page (the console module's contract, §10a): the module mounted with `sections: ["domain"]`, nothing else.
HOLDER_PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "page.html")


class Console:
    def __init__(self, directory: DomainDirectory, view: ReadView, api: ConsoleAPI, refresh_interval: float = 5.0,
                 publish_to=None, pending=None, topology=None, admin=None, members=None, viewer=None, holder_vars=None,
                 sealer=None, url: str | None = None):
        """`publish_to`: the domain holder's object store — each pass leaves the view there as `domain/view`,
        for that cluster's own console to draw (feedback X). `holder_vars`: the holder's store, where the tables the
        specs serve are kept (`domain.tables`). `url`: where this door is, said in the view for a cluster console to
        forward the domain's routes to."""
        self.directory, self.view, self.api, self.refresh_interval = directory, view, api, refresh_interval
        self.publish_to, self.pending, self.holder_vars, self.sealer = publish_to, pending, holder_vars, sealer
        # The operator's topology, and `admin(subject) -> bool`: who may edit it. Each pass also makes the domain's
        # copy of every reporting member read where the topology says it reports.
        self.topology, self.admin, self.members = topology, admin, members
        # `viewer(subject) -> bool`: who may LOOK (feedback CA). Given, every `GET /domain*` asks for a token and a
        # `view` on the domain; not given, reading stays open as the earlier lessons left it.
        self.viewer = viewer
        self.url = url
        self._stop = threading.Event()

    # Each step of the pass in a try of its own, and what one raises SAID (М10's seventh review, part 2): one `try` with
    # `except Exception: pass` around all five, so a member object that did not parse in the first froze the view of
    # the whole domain — every cluster's time stood still — and the log was empty. A step that raises is logged with
    # its trace once, until it succeeds again (`refresh_failures` counts every one), and the steps after it run. The
    # bookkeeping is `domain.steps.Steps`, which the signer's loop and the books' pass share (the review's eighth
    # pass); what is failing now is on `/healthz`.
    def _refresher(self):
        while not self._stop.is_set():
            self._steps(
                ("following the members", self._follow_members),
                ("following the topology", self._follow_topology),
                ("the read view's pass", self.view.refresh),
                ("publishing the read view", self._publish_view),
                ("collecting kept edits", self._collect_pending))
            self._stop.wait(self.refresh_interval)

    def _steps(self, *steps) -> None:
        if "_pass" not in self.__dict__:
            from .steps import Steps
            self._pass = Steps("domain console", self.refresh_interval, log)
        self._pass.run(*steps)

    @property
    def refresh_failures(self) -> int:
        return self._pass.failures if "_pass" in self.__dict__ else 0

    def health(self) -> dict:
        """What `/healthz` says: the passes, the steps failing now, and what others wrote that does not parse."""
        from w2cplatform.rows import counts
        out = {"ok": True, "passes": self.view.passes, **(self._pass.said() if "_pass" in self.__dict__ else {})}
        garbled = {n: sum(c.values()) for n, c in counts().items() if n in GARBLED_SHOWN and c}
        return {**out, **({"garbled": garbled} if garbled else {})}

    def _follow_members(self) -> None:
        if self.members is not None and self.publish_to is not None:
            from .members import apply as follow_members
            follow_members(self.view.fed, self.members, self.publish_to, self.topology)

    def _follow_topology(self) -> None:
        if self.topology is not None and self.publish_to is not None:
            from .topology import apply
            apply(self.view.fed, self.topology, self.publish_to)

    def tables(self) -> dict:
        """Every table a spec serves, as the holder keeps it: {`<sub>/<table>`: items}."""
        if self.holder_vars is None:
            return {}
        out = {}
        for s in declared.specs():
            for t in s.domain.tables:
                items, _ = self.holder_vars.get(f"{s.domain_prefix}{t}")
                out[f"{s.name}/{t}"] = dict(items or {})
        return out

    def extra(self) -> dict:
        """What the view carries of the records this console keeps: the topology, the list of members and who knocks,
        and where this door is."""
        out = {"url": self.url} if self.url else {}
        if self.topology is not None:
            out["topology"] = self.topology.read()
        if self.members is not None:
            out["member_list"] = self.members.read()
            out["knocking"] = self.members.knocking(self.publish_to) if self.publish_to is not None else []
        if self.pending is not None:
            # the edits kept for a cluster that is off (Lesson 9): waiting, or refused by the member — the course keeps
            # a member's outcome on the entry it answers, so `outcomes` are the refused ones
            out["pending"], out["outcomes"] = {}, {}
            for name, c in self.view.fed.clusters.items():
                if c.is_domain_holder:
                    continue
                entries = self.pending.of(name)
                waiting = [{"what": ref, "id": ref, "rev": e.get("rev"), "fields": sorted(e.get("fields") or {})}
                           for ref, e in entries.items() if not e.get("refused")]
                refused = [{"what": ref, "id": ref, "status": 409, "error": e["refused"]}
                           for ref, e in entries.items() if e.get("refused")]
                if waiting:
                    out["pending"][name] = waiting
                if refused:
                    out["outcomes"][name] = refused
        return out

    def view_doc(self) -> tuple[int, dict]:
        """`GET /domain`: the view this console's last pass left, with its age; composed now when it leaves none."""
        if self.publish_to is not None:
            from w2cplatform.console import domain_view
            st, doc = domain_view(self.publish_to, self.view.wall(), self.view.lost_after)
            if st != 404:
                return st, doc
        return 200, {**self.view.doc(self.tables(), self.extra()), "age": 0.0, "silent": False}

    def _publish_view(self) -> None:
        if self.publish_to is not None:
            self.view.publish(self.publish_to, self.tables(), self.extra())

    def _collect_pending(self) -> None:
        if self.pending is not None:
            self.pending.collect(self.view.fed)              # what the members' reports say became of kept edits

    def handler(self):
        console = self

        # BOUNDED LIKE EVERY DOOR (М10's sixth review: "every HTTP door in the code base"). It was a thread for every
        # connection with no bound, no deadline on a request, and bodies read to whatever `Content-Length` said —
        # before the caller's token was looked at. The server and the handler's reading are the platform's
        # (`ConsoleServer`, `Deadlined`): so many connections at once and so many to one address, the request line
        # and headers under a deadline, a body of at most `MAX_BODY`.
        #
        # …AND WITH THE CONSOLE'S RESERVE AND THE BOX'S LANE (М10's seventh review, major: "the domain's console and the
        # signer have neither"). Its bounds are the console's (`Bounds`: `CONSOLE_PER_ADDRESS`, `CONSOLE_RESERVE`, the
        # monitors in `CONSOLE_MONITORS`), and the box's own door is a unix socket when `DOMAIN_CONSOLE_UNIX` names one
        # (`open_doors`). There is no door in here — a person's token is the signer's to give — so a connection of the
        # reserve is answered on `/healthz` alone (`RESERVE`), and a listed monitor's on `/healthz`.
        class H(Deadlined, BaseHTTPRequestHandler):
            MAX_BODY = 1 << 20
            RESERVE = ("/healthz",)

            def parse_request(self):
                return super().parse_request() and not self.busy_unless(self.RESERVE, urlsplit(self.path).path)

            def _send(self, status: int, body: dict | list):
                raw = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _text(self, status: int, text: str):
                raw = text.encode()
                self.send_response(status)
                self.send_header("Content-Type", "text/plain; version=0.0.4")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _token(self):
                auth = self.headers.get("Authorization", "")
                return auth[7:] if auth.startswith("Bearer ") else None

            # The body of a PUT or a POST, an object — or None, the 400 already sent (the ninth review's sweep): read bare,
            # a body that was not JSON, or JSON that was not an object, dropped the connection with no answer at all.
            def _body(self):
                from w2cplatform.rows import PARSE_ERRORS
                try:
                    body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                    if not isinstance(body, dict):
                        raise TypeError(f"the body is a JSON object, not {type(body).__name__}")
                except PARSE_ERRORS as e:
                    self._send(400, {"detail": f"the body does not parse: {e}"})
                    return None
                return body

            def do_GET(self):
                u = urlsplit(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                try:
                    if u.path == "/healthz":
                        return self._send(200, console.health())
                    # the holder's page: the platform's console module with the domain alone (§10a, `page.html`), open
                    # as a cluster console's page is — what it shows it asks of the gated routes below
                    from w2cplatform.console import MODULE_ROUTES, page_csp, send_file, send_module
                    if u.path in ("/", "/index.html"):
                        send_file(self, HOLDER_PAGE, "text/html; charset=utf-8",
                                  headers=(("Content-Security-Policy", page_csp(HOLDER_PAGE)),))
                        return
                    if u.path in MODULE_ROUTES:
                        return send_module(self, u.path, q)
                    if console.viewer is not None and (u.path.startswith("/domain") or u.path in ("/spec", "/mounts")):
                        subject = console.api._subject(self._token())
                        if subject is not None and not console.viewer(subject):
                            return self._send(403, {"detail": f"{subject} may not look at the domain: no `view` on it"})
                    declared_route = console.route(u.path)
                    if declared_route is not None:
                        kind, sub, name = declared_route
                        if kind == "rows":
                            return self._send(200, console.view.list(q.get("q", ""), int(q.get("page", 1)),
                                                                     int(q.get("size", 50)), q.get("cluster"), sub=sub))
                        items, _ = console.holder_vars.get(declared.table(sub, name)) if console.holder_vars is not None else (None, 0)
                        return self._send(200, dict(items or {}))
                    if u.path == "/domain":
                        return self._send(*console.view_doc())
                    if u.path == "/domain/keys":
                        from .keysview import keys
                        return self._send(200, keys(console.holder_vars, console.publish_to, console.view.wall()))
                    if u.path == "/spec":
                        return self._send(200, {"name": "", "rows": None})   # no root, and no key of its own
                    if u.path == "/mounts":
                        from w2cplatform.console import describe
                        return self._send(200, {"root": "", "mounts": {s.name: describe(s)
                                                                       for s in declared.catalog.specs()}})
                    if u.path == "/domain/causes":
                        return self._send(200, [c.__dict__ | {"sentence": c.sentence()} for c in console.view.causes()])
                    if u.path == "/domain/topology" and console.topology is not None:
                        return self._send(200, console.topology.read())
                    if u.path == "/domain/members" and console.members is not None:
                        doc = console.members.read()
                        if console.publish_to is None:
                            return self._send(200, {**doc, "knocking": []})
                        own = console.members.own_root()
                        pinned = {n: console.members.pinned(n, console.publish_to, own) for n in doc["members"]}
                        return self._send(200, {**doc, "pinned": pinned, "knocking": console.members.knocking(console.publish_to)})
                    if u.path.startswith("/domain/where/"):
                        a = console.directory.where(u.path.rsplit("/", 1)[1])
                        return self._send(200 if a.found else (404 if a.complete else 503),
                                          a.__dict__ | {"complete": a.complete, "sentence": a.sentence()})
                    self._send(404, {"detail": "no such route"})
                except ApiError as e:
                    self._send(e.status, {"detail": e.detail})
                except Exception as e:                     # noqa: BLE001
                    self._send(500, {"detail": str(e)})

            def do_PUT(self):
                u = urlsplit(self.path)
                if u.path == "/domain/topology" and console.topology is not None:
                    return self._topology()
                if u.path.startswith("/domain/break-glass/") and console.holder_vars is not None:
                    return self._break_glass(u.path[len("/domain/break-glass/"):])
                parent, _, ref = u.path.rpartition("/")
                target = console.route(parent)
                if target is None or target[0] != "rows" or not ref:
                    return self._send(404, {"detail": "no such route"})
                key = self.headers.get("Idempotency-Key")
                if not key:
                    return self._send(400, {"detail": "Idempotency-Key header is required: a retried PUT must be the same PUT"})
                if not read_body(self, self.MAX_BODY):
                    return
                fields = self._body()
                if fields is None:
                    return
                try:
                    resp = console.api.update_unit(ref, fields, key, self._token(), sub=target[1])
                    self._send(202 if resp.get("pending") else 200, resp)    # kept for a cluster that is off: accepted, not applied
                except ApiError as e:
                    self._send(e.status, {"detail": e.detail})

            def do_POST(self):
                u = urlsplit(self.path)
                if not (u.path == "/domain/members" and console.members is not None):
                    return self._send(404, {"detail": "no such route"})
                if not read_body(self, self.MAX_BODY):
                    return
                body = self._body()
                if body is None:
                    return
                try:
                    subject = console.api._subject(self._token())
                    if console.admin is not None and subject is not None and not console.admin(subject):
                        raise ApiError(403, f"{subject} is not an admin of the domain: members are the domain's")
                    console.members.accept(str(body["name"]), by=subject, domain_objects=console.publish_to)
                    self._send(200, console.members.read())
                except KeyError:
                    self._send(400, {"detail": "name the cluster to accept"})
                except ApiError as e:
                    self._send(e.status, {"detail": e.detail})

            def do_DELETE(self):
                u = urlsplit(self.path)
                if not (u.path.startswith("/domain/members/") and console.members is not None):
                    return self._send(404, {"detail": "no such route"})
                name = u.path.rsplit("/", 1)[1]
                try:
                    subject = console.api._subject(self._token())
                    if console.admin is not None and subject is not None and not console.admin(subject):
                        raise ApiError(403, f"{subject} is not an admin of the domain: members are the domain's")
                    if not console.members.remove(name, by=subject):
                        return self._send(404, {"detail": f"{name} is not a member of this domain"})
                    self._send(200, console.members.read())
                except ApiError as e:
                    self._send(e.status, {"detail": e.detail})

            def _break_glass(self, cluster: str):
                from .breakglass import set_password
                if not read_body(self, self.MAX_BODY):
                    return
                body = self._body()
                if body is None:
                    return
                try:
                    subject = console.api._subject(self._token())
                    if console.admin is not None and subject is not None and not console.admin(subject):
                        raise ApiError(403, f"{subject} is not an admin of the domain: the emergency accounts are the domain's")
                    if not isinstance(body.get("password"), str) or not body["password"]:
                        raise ApiError(400, "name the new emergency password")
                    set_password(console.holder_vars, cluster, body["password"], time.time(), console.sealer,
                                 by=subject)
                    self._send(200, {"cluster": cluster, "set": True})
                except ApiError as e:
                    self._send(e.status, {"detail": e.detail})

            def _topology(self):
                if not read_body(self, self.MAX_BODY):
                    return
                body = self._body()
                if body is None:
                    return
                try:
                    subject = console.api._subject(self._token())
                    if console.admin is not None and subject is not None and not console.admin(subject):
                        raise ApiError(403, f"{subject} is not an admin of the domain: the topology is the domain's")
                    rev = console.topology.edit(lambda d: d.update({k: body[k] for k in ("centre", "star", "via") if k in body}),
                                                int(body.get("base_rev", 0)), known=set(console.view.fed.clusters), by=subject,
                                                domain=console.view.fed.domain_holder.name)
                    self._send(200, {"rev": rev, **console.topology.read()})
                except Conflict as e:
                    self._send(409, {"detail": str(e)})
                except ApiError as e:
                    self._send(e.status, {"detail": e.detail})

            def log_message(self, *a):
                pass

        return H

    # `/domain/<sub>/<name>` by declaration: ("rows", sub, rows) for the read view of a subsystem of the directory,
    # ("table", sub, name) for a table its spec serves; None for anything else.
    def route(self, path: str):
        parts = path.split("/")
        if len(parts) != 4 or parts[:2] != ["", "domain"]:
            return None
        sub, name = parts[2], parts[3]
        s = declared.spec(sub)
        if s is None:
            return None
        if name == s.rows and declared.unit_rows(sub):
            return ("rows", sub, name)
        if declared.table(sub, name) is not None:
            return ("table", sub, name)
        return None

    def serve(self, host: str = "127.0.0.1", port: int = 8090) -> ThreadingHTTPServer:
        threading.Thread(target=self._refresher, daemon=True, name="readview").start()
        return open_doors(host, port, self.handler(), unix_env="DOMAIN_CONSOLE_UNIX", say=False)

    def stop(self, srv: ThreadingHTTPServer) -> None:
        self._stop.set()
        srv.shutdown()
        srv.server_close()


def main() -> None:
    """python3 -m w2cplatform.domain.console — the domain's console."""
    import os
    import signal
    import threading

    from w2cplatform.trust.tokens import PERSON, verify
    from .runtime import federation_from_env
    from .agent import ClusterTrust

    fed = federation_from_env()
    directory = DomainDirectory(fed)
    view = ReadView(fed, lost_after=float(os.environ.get("LOST_AFTER", "45")))
    trust = ClusterTrust(fed.domain_holder.vars)

    def verifier(token: str) -> str:
        from .agent import Untrusted
        try:
            ks, revoked = trust.keyset(), trust.revoked()
        except Untrusted as e:                                           # "I cannot check", not a 500 (the review's eighth pass)
            raise ApiError(503, f"nobody can be checked: {e}") from None
        if ks is None:
            raise ApiError(503, "no signer key set in this cluster yet (is the domain agent running?)")
        return verify(token, ks, revoked, kind=PERSON)["sub"]       # the domain's door is a person's (CE)

    def consoles(cluster: str):
        # Forwarding to a member's console needs a connection TO the member, and the domain opens none
        # (`domain/uplink.py`): the edit is kept, and the member's agent takes it home on its next pass.
        from .federation import Unreachable
        raise Unreachable(f"{cluster} is reached only by its own agent; the edit waits for its next pass")

    from .pending import PendingEdits
    pending = PendingEdits(fed.domain_holder.vars)
    api = ConsoleAPI(directory, consoles, verifier=verifier if os.environ.get("AUTH", "1") == "1" else None,
                     pending=pending, last_known=view.last_known)
    # Each pass also leaves the view in the domain holder's own object store, for that cluster's console to
    # draw the domain as the root of its tree (`GET /domain` there). The domain holder's objects are the
    # domain's; no other member's store is written.
    from .topology import Topology

    # The domain's own grants (`domain/grants/domain`, feedback CA) — not the carried grants of whichever cluster
    # holds the domain today, which a move would change.
    from .grants import domain_may

    def admin(subject: str) -> bool:
        return domain_may(fed.domain_holder.vars, subject, "admin", time.time())

    def viewer(subject: str) -> bool:
        return domain_may(fed.domain_holder.vars, subject, "view", time.time())

    from .members import Members
    from .uplink import _CopyObjects
    topology = Topology(fed.domain_holder.vars)
    configured = [n for n, c in fed.clusters.items() if isinstance(c.objects, _CopyObjects)]
    members = Members(fed.domain_holder.vars, configured=lambda: configured, domain=fed.domain_holder.name)
    console = Console(directory, view, api, refresh_interval=float(os.environ.get("REFRESH_INTERVAL", "5")),
                      publish_to=fed.domain_holder.objects, holder_vars=fed.domain_holder.vars,
                      sealer=__import__("w2cplatform.sealing", fromlist=["Sealer"]).Sealer.from_env(os.environ),
                      pending=pending, topology=topology, admin=admin, members=members, viewer=viewer,
                      url=os.environ.get("CONSOLE_URL") or f"http://{os.environ.get('CONSOLE_HOST', '127.0.0.1')}:"
                                                           f"{os.environ.get('CONSOLE_PORT', '8443')}")
    srv = console.serve(os.environ.get("CONSOLE_HOST", "0.0.0.0"), int(os.environ.get("CONSOLE_PORT", "8443")))
    stop = threading.Event()
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    stop.wait()
    console.stop(srv)


if __name__ == "__main__":
    main()
