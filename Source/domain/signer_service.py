"""python3 -m domain.signer_service — the domain signer as a process.

Holds the keys (from domain/signer in the domain holder's store), publishes
the key set and the revocation list for the agents, publishes the identity
set object-first on a floor, and answers logins with tokens. The CA half
(issue, renew, rotate) is driven by the registrar and by renewal requests
over mTLS, which need the bench.

    POST /login          {"user","password"}         -> {"token"}
    POST /revoke         {"token"}                    -> revokes that token's jti
    GET  /keys           the key set (what agents copy)
    GET  /healthz        alive — what a monitor asks

Given CLUSTERS (the console's format), it also runs the domain's pass over the books every 5 s
(`domain/books.py`): sources, primaries, polls, upstream, asks. Those books carry tokens the signer mints —
stream tokens, tokens to ask — so the pass runs where the key is. The centre and the star relays come from
the operator's topology (`domain/topology`); CENTRE and STAR only stand where there is none.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from w2cplatform.cluster.objectstore import open_store

from .agent import KEYS_PATH, DomainPublisher
from .identity import AuthError, IdentityStore
from .signer import DomainRoot, Signer
from .tokens import RevocationList, TokenError, verify
from w2cplatform.console import Deadlined, open_doors, read_body
from w2cplatform.rows import PARSE_ERRORS
from w2cplatform.variables import open_vars, store_url

log = logging.getLogger("domain.signer")


def main() -> None:
    domain = os.environ.get("DOMAIN_ID", "domain")
    # The domain holder's store: its configstore by the domain's own socket, unless `PLATFORM_STORE` says otherwise;
    # the role `domain` is one of the two that may delete `domain/*` rows (`storemachine.DOMAIN_ROLES`).
    vars_ = open_vars(store_url(os.environ, "configstore:///run/configstore/domain.sock"))
    objects = open_store(os.environ.get("OBJECT_STORE_URL", "file:///data/domain"))
    pub = DomainPublisher(vars_)
    # Lesson 15, step 9: a domain whose root stays off the holder. The installer points RECOVERY_FILE at the root
    # for the FIRST start only: the holder's issuing certificate and the first key set are signed, and the file
    # goes back to the operator. From then on the signer holds its own keys, and the key set is the root's —
    # never overwritten here by one of its own, which members that pinned the root would refuse.
    recovery = os.environ.get("RECOVERY_FILE")
    if vars_.get("domain/signer")[0] is None and recovery:
        with open(recovery, "rb") as f:
            root = DomainRoot.restore(domain, f.read())
        signer = Signer(domain, vars_, root=root)
        pub.publish_keys(root.key_set(signer.tokens.keyset(), rev=1, issuing=[signer.root.cert.serial_number]))
    else:
        signer = Signer(domain, vars_)
        if not signer.chain:
            pub.publish_keys(signer.tokens.keyset())
    ids = IdentityStore(signer, vars_, objects, publish_floor=float(os.environ.get("IDENTITY_PUBLISH_FLOOR", "60")))
    revoked = revocations(vars_)
    books = None
    if os.environ.get("CLUSTERS"):
        from .books import Books
        from .crossing import Crossings
        from .readview import ReadView
        from .runtime import federation_from_env
        fed = federation_from_env()
        view = ReadView(fed, lost_after=float(os.environ.get("LOST_AFTER", "45")))
        from .members import Members
        from .topology import Topology
        from .uplink import _CopyObjects
        configured = [n for n, c in fed.clusters.items() if isinstance(c.objects, _CopyObjects)]
        star = frozenset(filter(None, os.environ.get("STAR", "").split(",")))
        books = Books(Crossings(fed.domain_holder.vars, view, issuer=signer.tokens,
                                centre=os.environ.get("CENTRE") or None, star=star,
                                topology=Topology(fed.domain_holder.vars)), fed.domain_holder.objects,
                      members=Members(fed.domain_holder.vars, configured=lambda: configured,
                                      domain=fed.domain_holder.name))

    # THE LOGIN DOOR IS ANYBODY'S, SO IT IS BOUNDED (М10's sixth review: "every HTTP door in the code base"). Whoever
    # reaches it has proved nothing yet — that is what it is for — and it was a thread for every connection, no
    # deadline on a request, and a body read to whatever `Content-Length` said. The platform's server and reading
    # (`ConsoleServer`, `Deadlined`, `read_body`): so many connections at once and so many to one address, the
    # request line and headers under a deadline, a body of a name and a password — `MAX_BODY`, no more.
    #
    # …AND WITH THE CONSOLE'S RESERVE AND THE BOX'S LANE (М10's seventh review, major). Four addresses took every
    # connection of it; its bounds are the console's now (`Bounds`), with the box's own door a unix socket when
    # `SIGNER_UNIX` names one (`open_doors`). The reserve is for the door in — `/login`, and its preflight — and a
    # listed monitor (`CONSOLE_MONITORS`) is answered on `/healthz`.
    class H(Deadlined, BaseHTTPRequestHandler):
        MAX_BODY = 16 << 10
        RESERVE = ("/login",)

        def parse_request(self):
            return super().parse_request() and not self.busy_unless(self.RESERVE, self.path.split("?", 1)[0])

        def _send(self, status, body):
            raw = json.dumps(body).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json")
            self._cors()
            self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

        # A cluster console's page logs a person in HERE, from its own origin (`w2cplatform/console.html`): the
        # password goes to the signer and only the token goes back to the console. So the login door answers a
        # page on another origin. Any origin: what the door gives is a token for credentials the person typed,
        # and it gives the same to `curl`; it sets no cookie and reads none, so there is nothing of this origin
        # for another site's page to ride on.
        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

        def do_OPTIONS(self):
            self.send_response(204); self._cors(); self.send_header("Content-Length", "0"); self.end_headers()

        def do_GET(self):
            if self.path == "/healthz":
                return self._send(200, {"ok": True, **loop.said()})       # what is failing in its loop, said (the eighth pass)
            if self.path == "/keys":
                return self._send(200, vars_.get(KEYS_PATH)[0] or signer.tokens.keyset().to_items())
            self._send(404, {"detail": "no such route"})

        def do_POST(self):
            if not read_body(self, self.MAX_BODY):
                return
            # The door in is anybody's, and so is its body (the ninth review's sweep of "a garbage token is 500, not
            # 401"): a body that is not an object, a name or a password that is not a string, a token that does not
            # verify were a 500 here — `/revoke` raised the token's own error, which nobody caught.
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if not isinstance(body, dict):
                    raise TypeError("not an object")
            except PARSE_ERRORS:
                return self._send(400, {"detail": "the body is a JSON object"})
            try:
                if self.path == "/login":
                    user, password = body.get("user"), body.get("password")
                    if not isinstance(user, str) or not isinstance(password, str):
                        return self._send(400, {"detail": "a login names a user and a password, both strings"})
                    return self._send(200, {"token": ids.login(user, password)})
                if self.path == "/revoke":
                    revoked.revoke(verify(body.get("token"), signer.tokens.keyset()))
                    pub.publish_revoked(revoked)
                    return self._send(200, {"revoked": True})
            except AuthError:
                return self._send(401, {"detail": "bad credentials"})
            except TokenError as e:
                return self._send(401, {"detail": f"token refused: {e}"})
            self._send(404, {"detail": "no such route"})

        def log_message(self, *a):
            pass

    from .steps import Steps
    loop = Steps("domain signer", 5.0, log)
    srv = open_doors(os.environ.get("SIGNER_HOST", "0.0.0.0"), int(os.environ.get("SIGNER_PORT", "8445")), H,
                     unix_env="SIGNER_UNIX", say=False)
    stop = threading.Event()
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    while not stop.is_set():
        loop.run(*signer_steps(ids, revoked, books))
        stop.wait(5)
    srv.shutdown()


# THE SIGNER'S LOOP, STEP BY STEP (the review's eighth pass, major). It was two `try` blocks with `except Exception: pass`
# — the same silence the domain console's loop had and lost in the seventh pass: one torn relay bundle stopped the pass
# over the books, and nobody saw it; and a failed publication of the identity set skipped the pruning of the
# revocation list behind it. Now each is a step of its own (`Steps`): what raises is logged with its trace once until
# it works again, counted, named on `/healthz`, and the steps after it run. The books are steps of their own inside
# `Books.pass_once`, so one book that cannot be written leaves the others written.
def signer_steps(ids, revoked, books) -> list:
    steps = [("publishing the identity set", ids.publish),        # object first, then the pointer, on a floor
             ("pruning the revocation list", lambda: revoked.prune(time.time()))]
    if books is not None:
        steps.append(("the pass over the books", books.pass_once))   # the books the agents carry home
    return steps


# The revocation list the signer starts from (the review's seventh pass left the signer's start open: one torn entry
# and it did not start — nobody logged in anywhere). Entry by entry: an entry whose expiry is not a number stays
# revoked, with no end (`RevocationList.from_items`). A row of another shape altogether is said, and the signer starts
# with an empty list — revocations last as long as the tokens they name, and a signer that does not start lets nobody in.
def revocations(vars_) -> RevocationList:
    try:
        return RevocationList.from_items(vars_.get("domain/revoked")[0])
    except PARSE_ERRORS as e:
        log.error("domain/revoked does not parse (%s): the signer starts with no revocations; tokens revoked before now "
                  "are honoured again until they expire — revoke them again", e)
        return RevocationList()


if __name__ == "__main__":
    main()
