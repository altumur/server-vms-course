"""python3 -m vms.domainpart — the VMS's worker on the domain: the books' pass at the holder.

The books the VMS writes for each member — sources, primaries, poll, upstream, asks (`keys.py`, `domain.books` of
`vms.subsystem.yaml`) — were a pass of the platform's signer until the boundary's «no hooks»: the platform knew which
books, in which order, and what was in them. Now they are this process's: it runs at the holder, reads the members by
the platform's read view, writes `domain/vms/…` with its own role's rights, and asks the signer for the tokens the books
carry over the signer's own socket (`w2cplatform.domain.tokendoor`) — the key stays the signer's. The platform's agent
carries each member's books home as it carries any row a spec declares, without reading them.

    its slot        `domain/vms/worker` in the holder's store: {instance, at}, taken by CAS — one pass at a time; a
                    second instance waits until the first has been silent `SLOT_LOST` seconds
    its heartbeat   `domain/vms/heartbeat` in the holder's object store: {ts, instance, passes, failing, step_failures}

Environment: `CLUSTERS` and `DOMAIN_HOLDER` as the domain's console reads them (`w2cplatform.domain.runtime`);
`SIGNER_TOKENS_UNIX` — the signer's socket; `CENTRE`, `STAR` only where the operator's topology says nothing;
`BOOKS_EVERY` (5 s), `LOST_AFTER` (45 s).
"""
from __future__ import annotations

import json
import logging
import os
import signal
import socket
import threading
import time

from w2cplatform.variables import Conflict

from .keys import SPEC

log = logging.getLogger("vms.domainpart")

SLOT = SPEC.domain_prefix + "worker"
HEARTBEAT = SPEC.domain_prefix + "heartbeat"
SLOT_LOST = 45.0
# What others wrote that its passes read and could not, counted (`w2cplatform.rows`) and said in its heartbeat: the
# entries of the books and the scenarios of the shared settings (the eleventh review's sibling: counted and shown nowhere).
GARBLED_SHOWN = ("book_entry", "scenario")


class DomainPartWorker:
    def __init__(self, books, holder_vars, holder_objects, instance: str | None = None, wall=time.time):
        self.books, self.vars, self.objects, self.wall = books, holder_vars, holder_objects, wall
        self.instance = instance or f"{socket.gethostname()}-{os.getpid()}"
        self.passes = 0

    def claim(self) -> bool:
        """The slot: ours, or nobody's for `SLOT_LOST` seconds — then taken by CAS. False: another instance holds it."""
        items, idx = self.vars.get(SLOT)
        now = self.wall()
        if items and items.get("instance") != self.instance and now - float(items.get("at", 0)) < SLOT_LOST:
            return False
        try:
            self.vars.put(SLOT, {"instance": self.instance, "at": now}, cas=idx)
        except Conflict:
            return False
        return True

    def pass_once(self) -> dict | None:
        if not self.claim():
            return None
        out = self.books.pass_once()
        self.passes += 1
        from w2cplatform.rows import counts
        garbled = {n: sum(c.values()) for n, c in counts().items() if n in GARBLED_SHOWN and c}
        self.objects.put(HEARTBEAT, json.dumps({"ts": self.wall(), "instance": self.instance, "passes": self.passes,
                                                **self.books.steps.said(), **({"garbled": garbled} if garbled else {})}).encode())
        return out


# ITS DOOR (the boundary's «no hooks»: these were routes of the platform's domain console, `/metrics` and `/api/catalog`,
# whose content is the VMS's). What the VMS computes on the domain is the VMS worker's to serve, at an address the page
# takes from the shared view; the platform's door serves what the specs declare and nothing it would have to understand.
#
#   GET /metrics    what every member's ingests and forwarders did not hand on: frames lost by why, the camera clock's
#                   steps, a forwarder's drops and holes (`ingest.stream_metrics`)
#   GET /catalog    what a scenario between cameras may name: the actions one camera may ask another, and per camera
#                   what it said it raises and can do (`scenario.catalog`)
#
# `verifier(token) -> subject` and `viewer(subject) -> bool`: a person's token and a `view` on the domain, as the
# domain's own door asks them (`w2cplatform.domain.grants.domain_may`); not given, the door is open.
def door_handler(fed, crossings=None, verifier=None, viewer=None):
    from http.server import BaseHTTPRequestHandler
    from urllib.parse import urlsplit

    from w2cplatform.console import Deadlined
    from w2cplatform.domain.api import ApiError

    class H(Deadlined, BaseHTTPRequestHandler):
        def _send(self, status: int, body, text: bool = False):
            raw = (body if text else json.dumps(body)).encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; version=0.0.4" if text else "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            path = urlsplit(self.path).path
            if verifier is not None:
                auth = self.headers.get("Authorization", "")
                if not auth.startswith("Bearer "):
                    return self._send(401, {"detail": "a token is required"})
                try:
                    subject = verifier(auth[7:])
                except ApiError as e:
                    return self._send(e.status, {"detail": e.detail})
                if viewer is not None and not viewer(subject):
                    return self._send(403, {"detail": f"{subject} may not look at the domain: no `view` on it"})
            if path == "/metrics":
                from .ingest import stream_metrics
                return self._send(200, "\n".join(stream_metrics(fed)) + "\n", text=True)
            if path == "/catalog" and crossings is not None:
                from .scenario import catalog
                return self._send(200, catalog(crossings))
            self._send(404, {"detail": "no such route"})

        def log_message(self, *a):
            pass
    return H


def main() -> None:
    from w2cplatform.domain.members import Members
    from w2cplatform.domain.readview import ReadView
    from w2cplatform.domain.runtime import federation_from_env
    from w2cplatform.domain.tokendoor import TokenDoor
    from w2cplatform.domain.topology import Topology
    from w2cplatform.domain.uplink import _CopyObjects

    from .books import Books
    from .crossing import Crossings

    fed = federation_from_env()
    holder = fed.domain_holder
    view = ReadView(fed, lost_after=float(os.environ.get("LOST_AFTER", "45")))
    configured = [n for n, c in fed.clusters.items() if isinstance(c.objects, _CopyObjects)]
    star = frozenset(filter(None, os.environ.get("STAR", "").split(",")))
    issuer = TokenDoor(os.environ.get("SIGNER_TOKENS_UNIX", "/run/w2c/signer-tokens.sock"))
    books = Books(Crossings(holder.vars, view, issuer=issuer, centre=os.environ.get("CENTRE") or None, star=star,
                            topology=Topology(holder.vars)), holder.objects,
                  members=Members(holder.vars, configured=lambda: configured, domain=holder.name))
    worker = DomainPartWorker(books, holder.vars, holder.objects)

    def verifier(token: str) -> str:                       # a person's token, against the holder's own key set
        from w2cplatform.domain.agent import ClusterTrust, Untrusted
        from w2cplatform.domain.api import ApiError
        from w2cplatform.trust.tokens import PERSON, TokenError, verify
        try:
            trust = ClusterTrust(holder.vars)
            ks, revoked = trust.keyset(), trust.revoked()
        except Untrusted as e:
            raise ApiError(503, f"nobody can be checked: {e}") from None
        if ks is None:
            raise ApiError(503, "no key set in the holder's store yet")
        try:
            return verify(token, ks, revoked, kind=PERSON)["sub"]
        except TokenError as e:
            raise ApiError(401, f"token refused: {e}") from None

    def viewer(subject: str) -> bool:
        from w2cplatform.domain.grants import domain_may
        return domain_may(holder.vars, subject, "view", time.time())
    from w2cplatform.console import open_doors
    open_doors(os.environ.get("DOMAINPART_HOST", "0.0.0.0"), int(os.environ.get("DOMAINPART_PORT", "8096")),
               door_handler(fed, books.crossings, verifier if os.environ.get("AUTH", "1") == "1" else None, viewer),
               unix_env="DOMAINPART_UNIX", say=False)
    every = float(os.environ.get("BOOKS_EVERY", "5"))
    stop = threading.Event()
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    while not stop.is_set():
        try:
            worker.pass_once()
        except Exception:                                  # noqa: BLE001 — a bad pass: the books written last stand
            log.exception("the books' pass failed; tried again in %.0f s", every)
        stop.wait(every)


if __name__ == "__main__":
    main()
