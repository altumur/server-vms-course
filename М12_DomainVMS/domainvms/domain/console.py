"""The cluster console — the process that serves browsers, in the standard
library. One of the two cluster-level jobs (the other is the live gateway);
the domain holder runs the same one pointed at every cluster.

    GET  /api/cameras?q=&page=&size=&cluster=   the read model, with each row's age and its cluster's state
    GET  /api/causes                            silence grouped by failure domain: one server, one cause
    GET  /api/where/<camera>                    the directory of directories, incompleteness included
    PUT  /api/cameras/<camera>                  proxied to the owning cluster's console; Idempotency-Key required;
                                                refuses placement fields
    GET  /api/members                           the domain's members: who, admitted how and when, which root each
                                                pinned (`pinned`), and who is knocking
    POST /api/members                           {name} — accept one that is knocking: an admin of the domain holder only
    DELETE /api/members/<name>                  a member leaves: an admin of the domain holder only
    GET  /api/catalog                           what a scenario between cameras may name: the actions one camera may
                                                ask another, and per camera what it said it raises and can do (`can`)
    GET  /api/topology                          the domain's topology: centre, star relays, who reaches it via whom
    PUT  /api/topology                          {base_rev, centre?, star?, via?} — CAS, checked; an admin of the
                                                domain holder only (`domain/topology.py`)
    GET  /healthz

Each pass also leaves what it saw as `domain/view` in the domain holder's object store, which that cluster's
own console serves at `GET /domain` (feedback X): one tree for a site whose domain lives in its server room.

Stateless: kill it, start another, the first pass rebuilds everything.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from w2cplatform.console import Deadlined, open_doors, read_body

from .api import ApiError, ConsoleAPI
from .federation import DomainDirectory
from .readview import ReadView

log = logging.getLogger("domain.console")
# The tables of what others wrote that `/healthz` counts (`w2cplatform.rows`): members' objects, grants, user records,
# and the trust rows a cluster holds (the review's eighth pass: "counted, named" — and shown).
GARBLED_SHOWN = ("member_object", "grant", "user", "trust_row")


class Console:
    def __init__(self, directory: DomainDirectory, view: ReadView, api: ConsoleAPI, refresh_interval: float = 5.0,
                 publish_to=None, crossings=None, pending=None, topology=None, admin=None, members=None, viewer=None):
        """`publish_to`: the domain holder's object store — each pass leaves the view there as `domain/view`,
        for that cluster's own console to draw (feedback X). `crossings`: Lesson 13's, to say who records what."""
        self.directory, self.view, self.api, self.refresh_interval = directory, view, api, refresh_interval
        self.publish_to, self.crossings, self.pending = publish_to, crossings, pending
        # The operator's topology, and `admin(subject) -> bool`: who may edit it. Each pass also makes the domain's
        # copy of every reporting member read where the topology says it reports.
        self.topology, self.admin, self.members = topology, admin, members
        # `viewer(subject) -> bool`: who may LOOK (feedback CA). Given, every `GET /api/*` asks for a token and a
        # `view` on the domain; not given, reading stays open as the earlier lessons left it.
        self.viewer = viewer
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

    def _publish_view(self) -> None:
        if self.publish_to is not None:
            self.view.publish(self.publish_to, self.crossings.all() if self.crossings else None)

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
                    if console.viewer is not None and u.path.startswith("/api/"):
                        subject = console.api._subject(self._token())
                        if subject is not None and not console.viewer(subject):
                            return self._send(403, {"detail": f"{subject} may not look at the domain: no `view` on it"})
                    if u.path == "/api/cameras":
                        return self._send(200, console.view.list(q.get("q", ""), int(q.get("page", 1)),
                                                                 int(q.get("size", 50)), q.get("cluster")))
                    if u.path == "/api/causes":
                        return self._send(200, [c.__dict__ | {"sentence": c.sentence()} for c in console.view.causes()])
                    if u.path == "/api/topology" and console.topology is not None:
                        return self._send(200, console.topology.read())
                    if u.path == "/api/catalog" and console.crossings is not None:
                        from .scenario import catalog
                        return self._send(200, catalog(console.crossings))
                    if u.path == "/api/members" and console.members is not None:
                        doc = console.members.read()
                        if console.publish_to is None:
                            return self._send(200, {**doc, "knocking": []})
                        own = console.members.own_root()
                        pinned = {n: console.members.pinned(n, console.publish_to, own) for n in doc["members"]}
                        return self._send(200, {**doc, "pinned": pinned, "knocking": console.members.knocking(console.publish_to)})
                    if u.path.startswith("/api/where/"):
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
                if u.path == "/api/topology" and console.topology is not None:
                    return self._topology()
                if not u.path.startswith("/api/cameras/"):
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
                    resp = console.api.update_camera(u.path.rsplit("/", 1)[1], fields, key, self._token())
                    self._send(202 if resp.get("pending") else 200, resp)    # kept for a cluster that is off: accepted, not applied
                except ApiError as e:
                    self._send(e.status, {"detail": e.detail})

            def do_POST(self):
                u = urlsplit(self.path)
                if not (u.path == "/api/members" and console.members is not None):
                    return self._send(404, {"detail": "no such route"})
                if not read_body(self, self.MAX_BODY):
                    return
                body = self._body()
                if body is None:
                    return
                try:
                    subject = console.api._subject(self._token())
                    if console.admin is not None and subject is not None and not console.admin(subject):
                        raise ApiError(403, f"{subject} is not an admin of the domain holder: members are the domain's")
                    console.members.accept(str(body["name"]), by=subject, domain_objects=console.publish_to)
                    self._send(200, console.members.read())
                except KeyError:
                    self._send(400, {"detail": "name the cluster to accept"})
                except ApiError as e:
                    self._send(e.status, {"detail": e.detail})

            def do_DELETE(self):
                u = urlsplit(self.path)
                if not (u.path.startswith("/api/members/") and console.members is not None):
                    return self._send(404, {"detail": "no such route"})
                name = u.path.rsplit("/", 1)[1]
                try:
                    subject = console.api._subject(self._token())
                    if console.admin is not None and subject is not None and not console.admin(subject):
                        raise ApiError(403, f"{subject} is not an admin of the domain holder: members are the domain's")
                    if not console.members.remove(name, by=subject):
                        return self._send(404, {"detail": f"{name} is not a member of this domain"})
                    self._send(200, console.members.read())
                except ApiError as e:
                    self._send(e.status, {"detail": e.detail})

            def _topology(self):
                from cluster.variables import Conflict
                if not read_body(self, self.MAX_BODY):
                    return
                body = self._body()
                if body is None:
                    return
                try:
                    subject = console.api._subject(self._token())
                    if console.admin is not None and subject is not None and not console.admin(subject):
                        raise ApiError(403, f"{subject} is not an admin of the domain holder: the topology is the domain's")
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

    def serve(self, host: str = "127.0.0.1", port: int = 8090) -> ThreadingHTTPServer:
        threading.Thread(target=self._refresher, daemon=True, name="readview").start()
        return open_doors(host, port, self.handler(), unix_env="DOMAIN_CONSOLE_UNIX", say=False)

    def stop(self, srv: ThreadingHTTPServer) -> None:
        self._stop.set()
        srv.shutdown()
        srv.server_close()


def main() -> None:
    """python3 -m domain.console — the cluster (or domain) console."""
    import os
    import signal
    import threading

    from .runtime import federation_from_env
    from .tokens import verify
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
        return verify(token, ks, revoked, kind="person")["sub"]     # the domain's door is a person's (CE)

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
    from .crossing import Crossings
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
                      publish_to=fed.domain_holder.objects,
                      crossings=Crossings(fed.domain_holder.vars, view, topology=topology),
                      pending=pending, topology=topology, admin=admin, members=members, viewer=viewer)
    srv = console.serve(os.environ.get("CONSOLE_HOST", "0.0.0.0"), int(os.environ.get("CONSOLE_PORT", "8443")))
    stop = threading.Event()
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    stop.wait()
    console.stop(srv)


if __name__ == "__main__":
    main()
