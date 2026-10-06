"""The domain's console — the process that serves the domain's door to browsers and tools, in the standard library.
Every route but `/healthz` is the platform's and the specs' (`declared`): what a subsystem's units are called, which of
its rows the door serves — never a route a subsystem wrote.

A DOOR WITH NO KEY (ADR-0032). The domain's keys are the signer's (`signer_service.py`), and so is everything of the
holder that writes on its own: the pass — the view, the kept edits closed, the week of alarms, the backup — runs there,
one writer for each of its outputs. This process READS: the members and their publications from the holder's stores,
and what only the signer knows (its term, its failing steps, the rows it could not read) from the view it publishes
(`domain/view`). It writes what a person decides and needs no key for: admitting a member, the topology, the grants, an
edit kept again — each a line of its own journal (`domainconsole`). What needs a key — the shared settings, a handover,
the people with their passwords, a move of the domain here — it hands to the signer as it came, with the person's token,
and answers what the signer said; the signer checks it whole. While a handover freezes the holder it refuses early
(`/api/holder`'s `frozen_for`), but the rule is the signer's.

ONE SET OF PATHS, LITERALLY (the contract of the console module, §10a; ADR-0003): every human route of the holder
lives under `/domain/*`, the same path a cluster console forwards without rewriting, and the page on either is the
platform's module. `/api/*` is the processes' (the signer's) — here only the login door, handed on.

    GET  /domain                                the domain's view, as the signer's pass left it, with its age
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
    GET  /domain/alarms?since=&until=           every member's alarms, newest first (Lesson 14) — read: the week is the
                                                signer's pass's to keep
    GET  /domain/members                        the domain's members: who, admitted how and when, which root each
                                                pinned (`pinned`), and who is knocking with the key it presents
    POST /domain/members                        {name, fingerprint?} — accept one that is knocking, by the key its
                                                report presents: an admin of the domain only
    DELETE /domain/members/<name>               a member leaves: an admin of the domain only
    GET  /domain/topology                       the domain's topology: centre, star relays, who reaches it via whom
    PUT  /domain/topology                       {base_rev, centre?, star?, via?} — CAS, checked; an admin of the
                                                domain only (`topology.py`)
    GET  /domain/grants                         every cluster's grants and the domain's own: {grants: {<c>: [lines]}}
    PUT  /domain/grants/<cluster>               {lines: [{subject, cap, scope, until?}]} — that cluster's, whole
    GET  /domain/backup                         who keeps the domain's backup, and whether each has taken the newest
    POST /domain/pending/<member>               {ref, fields} — an edit an old holder held, kept again here
    POST /domain/stranded/apply                 {path, key} — on a replaced holder: an edit it alone held, kept again
                                                on the domain console of the holder that replaced it
    GET  /domain/shared                         the shared settings: the document as signed, who holds it, what each
                                                spec declares shared (`{doc, delivery, declared}`), read with no key
    PUT  /domain/shared                         → the signer's `/api/shared`
    POST /domain/handover                       → the signer's `/api/handover`
    POST /domain/move                           {recovery, stolen?} → the signer's `/api/move`: the domain moved onto
                                                this cluster, the holder gone — checked by the recovery file there
    /domain/users[/<name>], /domain/break-glass[/<cluster>]   → the signer's `/api/people/…`
    POST /api/login                             → the signer's: a person's password goes there, a token comes back
    GET|POST|DELETE /session                    the door in, by the domain's key set (the platform's shapes)
    GET  /healthz

What a subsystem computes or streams on the domain — a catalogue of what one unit may ask another, its own numbers — is
its worker's door, which a page reaches by the address the shared view names; it is not this door's.

Stateless: kill it, start another, the first pass of its read view rebuilds what it shows.
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
# What a person's request is handed to at the signer: the operations that need the domain's keys (ADR-0032).
TO_SIGNER = {"/domain/shared": "/api/shared", "/domain/handover": "/api/handover", "/domain/move": "/api/move",
             "/domain/users": "/api/people/users", "/domain/break-glass": "/api/people/break-glass",
             "/api/login": "/api/login"}
LOGIN_URL = "/api/login"


class Console:
    def __init__(self, directory: DomainDirectory, view: ReadView, api: ConsoleAPI, refresh_interval: float = 5.0,
                 holder_objects=None, pending=None, topology=None, admin=None, members=None, viewer=None, holder_vars=None,
                 signer_url: str | None = None, alarms=None, journal=None, person=None):
        """`holder_objects`, `holder_vars`: the domain holder's stores, read — the view the signer's pass leaves
        (`domain/view`), the members' reports, the tables the specs serve (`domain.tables`). `signer_url`: the signer's
        door, where the operations that need the domain's keys are performed whole (ADR-0032) — this process has no
        key. `person(token) -> payload`: a person's token checked by the domain's key set, for the door in
        (`/session`); none, and the door is open as the earlier lessons left it."""
        self.directory, self.view, self.api, self.refresh_interval = directory, view, api, refresh_interval
        self.holder_objects, self.pending, self.holder_vars = holder_objects, pending, holder_vars
        # The operator's topology, and `admin(subject) -> bool`: who may edit it. Each pass also makes this console's
        # copy of every reporting member read where the topology says it reports.
        self.topology, self.admin, self.members = topology, admin, members
        # `viewer(subject) -> bool`: who may LOOK (feedback CA). Given, every `GET /domain*` asks for a token and a
        # `view` on the domain; not given, reading stays open as the earlier lessons left it.
        self.viewer = viewer
        self.signer_url, self.alarms, self.journal, self.person = signer_url, alarms, journal, person
        self._stop = threading.Event()

    # Its pass READS (ADR-0032): it follows the members and the topology and reads every member's report, in memory, for
    # the routes that list units and say where they are. It publishes nothing and closes nothing: the view, the kept
    # edits, the week of alarms and the backup are the signer's pass's outputs, one writer each. Each step in a try of
    # its own, and what one raises SAID (М10's seventh review, part 2; `domain.steps.Steps`); what is failing now is on
    # `/healthz`.
    def _refresher(self):
        while not self._stop.is_set():
            self._steps(
                ("following the members", self._follow_members),
                ("following the topology", self._follow_topology),
                ("the read view's pass", self.view.refresh))
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
        if self.members is not None and self.holder_objects is not None:
            from .members import apply as follow_members
            follow_members(self.view.fed, self.members, self.holder_objects, self.topology)

    def _follow_topology(self) -> None:
        if self.topology is not None and self.holder_objects is not None:
            from .topology import apply
            apply(self.view.fed, self.topology, self.holder_objects)

    def shared_view(self) -> dict:
        """`GET /domain/shared`: the document the signer signed last (read from the store, no key), which members hold
        it, and what each spec declares shared with the field's type — `{doc, delivery, declared}`; a document a spec
        declares (`{name, type: json, schema}`) with its schema, for a form to be built from."""
        from .shared import SharedSettings
        doc, _ = SharedSettings(self.view.fed.domain_holder.vars, self.view.fed.domain_holder.objects, None).current()
        shown = {k: v for k, v in doc.items() if k != "settings"}
        shown["shared"] = (doc.get("settings") or {}).get("shared") or {}
        try:
            delivery = SharedSettings(self.view.fed.domain_holder.vars, None, None).delivery(self.view.fed)
        except Exception as e:                                   # noqa: BLE001 — the document is shown all the same
            delivery = {"sentence": f"who holds it is not known: {e}"}
        def one(s, f: str) -> dict:
            d = s.domain.documents.get(f)
            if d is not None:
                return {"name": f, "type": "json", "schema": d.schema}
            return {"name": f, "type": s.fields[f].type}
        declared_ = {s.name: [one(s, f) for f in s.domain.shared] for s in declared.specs() if s.domain.shared}
        return {"doc": shown, "delivery": delivery, "declared": declared_}

    def view_doc(self) -> tuple[int, dict]:
        """`GET /domain`: the view the signer's last pass left, with its age — the one form on both doors, one writer of it."""
        if self.holder_objects is None:
            return 404, {"error": "no domain here", "detail": "this console reads no store of the domain holder's"}
        from w2cplatform.console import domain_view
        return domain_view(self.holder_objects, self.view.wall(), self.view.lost_after)

    def alarms_doc(self, q: dict) -> tuple[int, dict]:
        """`GET /domain/alarms?since=&until=`: the one list of Lesson 14, read — a day by default."""
        from .alarms import WINDOW
        if self.alarms is None:
            return 404, {"detail": "this domain keeps no list of alarms"}
        now = self.view.wall()
        try:
            since, until = float(q.get("since", now - WINDOW)), float(q.get("until", now + 1))
        except ValueError:
            return 400, {"detail": "since and until are times, in seconds"}
        return 200, self.alarms.list(since, until)

    def backup_doc(self) -> dict:
        """`GET /domain/backup`: for each member chosen to keep the domain's backup, the pointer the holder wrote for it
        and the one its last report says it took — and the term, as the signer says it."""
        from .term import BACKUP, BACKUP_TAKEN
        from .uplink import member_copy
        from .federation import Unreachable
        holders = {}
        for path in self.holder_vars.list(BACKUP + "/") if self.holder_vars is not None else []:
            name = path[len(BACKUP) + 1:]
            pointer, _ = self.holder_vars.get(path)
            try:
                taken = member_copy(name, self.holder_objects, wall=self.view.wall).vars.get(BACKUP_TAKEN)[0] \
                    if self.holder_objects is not None else None
            except Unreachable:
                taken = None
            holders[name] = {"pointer": pointer, "taken": taken}
        st, said = self.ask_signer("GET", "/api/holder") if self.signer_url else (404, {})
        return {"term": said.get("term") if st == 200 else None, "holders": holders}

    def grants_doc(self) -> dict:
        """`GET /domain/grants`: every cluster's grants and the domain's own, as lines `{subject, cap, scope, until}`."""
        from .agent import GRANTS_PATH
        from .grants import grants_from_items
        out = {}
        for path in self.holder_vars.list(GRANTS_PATH + "/") if self.holder_vars is not None else []:
            out[path[len(GRANTS_PATH) + 1:]] = [_line(g) for g in grants_from_items(self.holder_vars.get(path)[0], path)]
        return {"grants": out}

    def set_grants(self, cluster: str, body: dict, by: str | None) -> dict:
        """`PUT /domain/grants/<cluster> {lines}`: a cluster's grants, whole — or the domain's own (`domain`), which keep
        an admin. Plain rows, not sealed: this console writes them, and says so in its journal."""
        from .agent import DomainPublisher, GRANTS_PATH
        from .grants import DOMAIN_SCOPE, GRANT_LIFETIME, BadName, LastAdmin, grants_from_items, name_refused, set_domain_grants
        why = name_refused(cluster, "cluster's name", also="/")
        lines = body.get("lines")
        if why or not isinstance(lines, list):
            raise ApiError(400, why or "{lines: [{subject, cap, scope, until?}]}")
        now = self.view.wall()
        try:
            grants = [_grant_of(line, cluster == DOMAIN_SCOPE, now + GRANT_LIFETIME) for line in lines]
        except (TypeError, ValueError, KeyError) as e:
            raise ApiError(400, f"a line is {{subject, cap: view|edit|admin, scope: * | unit:<sub>/<id> | labels:a,b, "
                                f"until?}}: {e}") from None
        try:
            if cluster == DOMAIN_SCOPE:
                set_domain_grants(self.holder_vars, grants, now, journal=self.journal, by=by)
            else:
                path = f"{GRANTS_PATH}/{cluster}"
                was = {_item_line(g) for g in grants_from_items(self.holder_vars.get(path)[0], path)}
                DomainPublisher(self.holder_vars).publish_grants(cluster, grants)
                now_ = {_item_line(g) for g in grants}
                if self.journal is not None and was != now_:
                    self.journal.say("domain.grants.changed", user=by or "?", target=cluster,
                                     added=",".join(sorted(now_ - was)), removed=",".join(sorted(was - now_)))
        # THE CODE SAYS WHOSE THE FAULT IS (the architect's rule): 409 when the refusal depends on rows that exist — the
        # last admin, a name a person and a subject would share; 400 when the request is wrong by the spec on its own —
        # a grant wider than the family's declared `grant` (`domain.names`).
        except LastAdmin as e:
            raise ApiError(409, str(e)) from None
        except (BadName, declared.GrantTooWide) as e:
            raise ApiError(400, str(e)) from None
        except declared.Refused as e:
            raise ApiError(409, str(e)) from None
        return {"cluster": cluster, "lines": len(grants)}

    def keep_again(self, member: str, body: dict, by: str | None) -> dict:
        """`POST /domain/pending/<member> {ref, fields: {<field>: {old?, new}}}`: an edit an old holder held and the
        new term did not have, kept again here by a person (Lesson 15) — an ordinary kept edit from now on."""
        if self.pending is None:
            raise ApiError(404, "this domain keeps no edits for members that are off")
        ref, fields = body.get("ref"), body.get("fields")
        if not isinstance(ref, str) or not ref or not isinstance(fields, dict) or not fields or \
                not all(isinstance(v, dict) and "new" in v for v in fields.values()):
            raise ApiError(400, "an edit kept again: {ref, fields: {<field>: {old, new}}}")
        self.api._refuse_secrets({f: v["new"] for f, v in fields.items()})
        e = self.pending.add(member, ref, {f: v["new"] for f, v in fields.items()},
                             {f: v.get("old") for f, v in fields.items()}, by)
        if self.journal is not None:
            self.journal.say("domain.pending.kept", user=by or "?", target=f"{member}/{ref}", fields=",".join(sorted(fields)))
        return {"pending": True, "cluster": member, "ref": ref, "rev": e["rev"]}

    # What the signer says of the holder (`/api/holder`), asked by this process as a process. The console refuses
    # early with it; the signer checks again in each of its operations (ADR-0032).
    def ask_signer(self, method: str, route: str, body: bytes | None = None, token: str | None = None,
                   timeout: float = 10.0) -> tuple[int, dict]:
        import urllib.error
        import urllib.request
        headers = {"Content-Type": "application/json", "X-Operator": "domain-console"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(self.signer_url.rstrip("/") + route, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                status, out = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, out = e.code, e.read()
        except (OSError, ValueError) as e:
            return 502, {"detail": f"the signer did not answer: {e}"}
        try:
            got = json.loads(out or b"{}")
        except ValueError:
            return 502, {"detail": "the signer's answer does not parse"}
        return status, got if isinstance(got, dict) else {"detail": "the signer's answer is not an object"}

    def refused_early(self) -> tuple[int, dict] | None:
        """A write here, while the signer says a handover freezes the holder (503) or that it was replaced (409)."""
        if not self.signer_url:
            return None
        st, said = self.ask_signer("GET", "/api/holder")
        if st == 404:
            return None                                  # a domain that holds no term: no write waits for one
        if st != 200:
            return 503, {"detail": f"the domain's signer did not say whether it holds the domain: {said.get('detail')}"}
        by = said.get("deposed_by") or {}
        if said.get("deposed") or by:
            return 409, {"detail": f"this holder held the domain at term {said.get('term')}; {by.get('holder')} holds it "
                                   f"at term {by.get('term')} — edits go there", "holder": by.get("holder")}
        if said.get("frozen_for"):
            return 503, {"detail": f"the domain is being handed over to {said['frozen_for']}; edits are refused until it "
                                   f"has — seconds, not minutes — and then go there", "frozen_for": said["frozen_for"]}
        return None

    def stranded_apply(self, body: dict, token: str | None) -> tuple[int, dict]:
        """`POST /domain/stranded/apply {path, key}`: on a holder that was replaced, one item it alone held applied again
        by a person on the holder that replaced it. Only a kept edit can be — it is an ordinary edit there, kept and
        carried home (Lesson 9); anything else is made again there by hand. Where: the record that replaced this holder
        names its signer, and the signer says where its domain console is."""
        if not self.signer_url:
            return 503, {"detail": "this console knows no signer: what this holder alone held is the signer's to say"}
        st, said = self.ask_signer("GET", "/api/holder")
        if st != 200:
            return 503, {"detail": f"the domain's signer did not say what this holder holds: {said.get('detail')}"}
        by = said.get("deposed_by")
        if not by:
            return 409, {"detail": "this holder was not replaced: nothing is stranded here"}
        from .pending import PENDING_PATH
        item = next((s for s in said.get("stranded") or [] if s.get("path") == body.get("path")
                     and s.get("key") == body.get("key")), None)
        if item is None:
            return 404, {"detail": "no such stranded item"}
        if not str(item["path"]).startswith(PENDING_PATH + "/"):
            return 400, {"detail": f"{item['path']} is not an edit kept for a member: make the change again on {by.get('holder')}"}
        if not by.get("url"):
            return 502, {"detail": f"the record of term {by.get('term')} names no signer's door: make the edit again on "
                                   f"{by.get('holder')}"}
        import urllib.error
        import urllib.request
        try:
            with urllib.request.urlopen(by["url"].rstrip("/") + "/api/holder", timeout=5.0) as r:
                there = json.loads(r.read()).get("console")
        except (OSError, ValueError, AttributeError) as e:
            return 502, {"detail": f"{by.get('holder')} did not say where its domain console is: {e}"}
        if not there:
            return 502, {"detail": f"{by.get('holder')} did not say where its domain console is"}
        try:
            entry = json.loads(item["value"])
        except (TypeError, ValueError):
            return 400, {"detail": f"{item['path']}#{item['key']} does not read as a kept edit"}
        member = str(item["path"])[len(PENDING_PATH) + 1:]
        headers = {"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})}
        req = urllib.request.Request(f"{there.rstrip('/')}/domain/pending/{member}", method="POST", headers=headers,
                                     data=json.dumps({"ref": item["key"], "fields": entry.get("fields") or {}}).encode())
        try:
            with urllib.request.urlopen(req, timeout=5.0) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")
        except (OSError, ValueError) as e:
            return 502, {"detail": f"{by.get('holder')} did not answer: {e}"}

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
        # (`open_doors`). The door in is the signer's (`/api/login` is handed on), so a connection of the reserve is
        # answered on `/healthz` alone (`RESERVE`), and a listed monitor's on `/healthz`.
        class H(Deadlined, BaseHTTPRequestHandler):
            MAX_BODY = 1 << 20
            RESERVE = ("/healthz",)
            _extra_headers = ()

            def parse_request(self):
                return super().parse_request() and not self.busy_unless(self.RESERVE, urlsplit(self.path).path)

            def _send(self, status: int, body: dict | list):
                raw = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                for k, v in self._extra_headers:
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            # `Authorization: Bearer …`, or the cookie `/session` set (`access.token_of`)
            def _token(self):
                from w2cplatform.access import token_of
                return token_of(self.headers)

            def _who(self):
                """The person calling, checked by the domain's key set — None with no verifier (an open door)."""
                from w2cplatform.trust.tokens import TokenError
                try:
                    return console.api._subject(self._token())
                except TokenError as e:
                    raise ApiError(401, f"token refused: {e}") from None

            def _admin(self, what: str):
                subject = self._who()
                if console.admin is not None and subject is not None and not console.admin(subject):
                    raise ApiError(403, f"{subject} is not an admin of the domain: {what} the domain's")
                return subject

            # A request that ACTS, its proof in the cookie and an `Origin` that is not this door, is another site's page
            # steering the browser (`access.cross_site`): refused before anything is read.
            def _steered(self) -> bool:
                from w2cplatform.access import cross_site, from_cookie
                if from_cookie(self.headers) and cross_site(self.headers):
                    self._send(403, {"detail": "a request that changes the domain, carried by the cookie from another "
                                               "site's page: refused"})
                    return True
                return False

            # The body of a PUT or a POST, an object — or None, the 400 already sent (the ninth review's sweep): read bare,
            # a body that was not JSON, or JSON that was not an object, dropped the connection with no answer at all.
            def _body(self):
                from w2cplatform.canonical import parse_json
                from w2cplatform.rows import PARSE_ERRORS
                if not read_body(self, self.MAX_BODY):
                    return None
                try:
                    # the platform's one reading (`canonical.parse_json`): a body not UTF-8, a lone surrogate, `1e400`
                    # are 400 with the shared table's `fault` (the architect, 2026-10-06)
                    body = parse_json(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                except PARSE_ERRORS as e:
                    self._send(400, {"detail": f"the body does not parse: {e}", "fault": getattr(e, "fault", "") or "not_json"})
                    return None
                if not isinstance(body, dict):
                    self._send(400, {"detail": f"the body does not parse: the body is a JSON object, not {type(body).__name__}"})
                    return None
                return body

            def _early(self) -> bool:
                refused = console.refused_early()
                if refused:
                    self._send(*refused)
                    return True
                return False

            def do_GET(self):
                u = urlsplit(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                try:
                    if u.path == "/healthz":
                        return self._send(200, console.health())
                    if u.path == "/session":
                        return self._session("GET")
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
                        subject = self._who()
                        if subject is not None and not console.viewer(subject):
                            return self._send(403, {"detail": f"{subject} may not look at the domain: no `view` on it"})
                    route = console.signer_route(u.path, "GET")
                    if route is not None and route.startswith("/api/people/"):
                        return self._to_signer("GET", route)            # the people's rows are opened where the ring is
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
                    if u.path == "/domain/alarms":
                        return self._send(*console.alarms_doc(q))
                    if u.path == "/domain/backup":
                        return self._send(200, console.backup_doc())
                    if u.path == "/domain/grants":
                        return self._send(200, console.grants_doc())
                    if u.path == "/domain/shared":
                        return self._send(200, console.shared_view())
                    if u.path == "/domain/keys":
                        from .keysview import keys
                        return self._send(200, keys(console.holder_vars, console.holder_objects, console.view.wall()))
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
                        if console.holder_objects is None:
                            return self._send(200, {**doc, "knocking": []})
                        own = console.members.own_root()
                        pinned = {n: console.members.pinned(n, console.holder_objects, own) for n in doc["members"]}
                        return self._send(200, {**doc, "pinned": pinned,
                                                "knocking": console.members.knocking(console.holder_objects)})
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
                if self._steered():
                    return
                route = console.signer_route(u.path, "PUT")
                if route is not None:
                    return self._early() or self._to_signer("PUT", route)
                try:
                    if u.path == "/domain/topology" and console.topology is not None:
                        return self._topology()
                    if u.path.startswith("/domain/grants/") and console.holder_vars is not None:
                        subject = self._admin("the grants are")
                        if self._early():
                            return
                        body = self._body()
                        if body is not None:
                            self._send(200, console.set_grants(u.path[len("/domain/grants/"):], body, subject))
                        return
                except ApiError as e:
                    return self._send(e.status, {"detail": e.detail})
                parent, _, ref = u.path.rpartition("/")
                target = console.route(parent)
                if target is None or target[0] != "rows" or not ref:
                    return self._send(404, {"detail": "no such route"})
                key = self.headers.get("Idempotency-Key")
                if not key:
                    return self._send(400, {"detail": "Idempotency-Key header is required: a retried PUT must be the same PUT"})
                if self._early():
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
                if u.path in ("/session", "/session/break-glass"):
                    return self._session("POST")
                if self._steered():
                    return
                route = console.signer_route(u.path, "POST")
                if route is not None:
                    if u.path in ("/api/login", "/domain/handover", "/domain/move"):
                        return self._to_signer("POST", route)     # the door in; a handover, a move: the signer's
                    return self._early() or self._to_signer("POST", route)
                try:
                    if u.path == "/domain/stranded/apply":
                        self._admin("what a replaced holder held is")
                        body = self._body()
                        if body is not None:
                            self._send(*console.stranded_apply(body, self._token()))
                        return
                    if u.path.startswith("/domain/pending/") and len(u.path) > len("/domain/pending/"):
                        subject = self._admin("kept edits are")
                        if self._early():
                            return
                        body = self._body()
                        if body is not None:
                            self._send(202, console.keep_again(u.path[len("/domain/pending/"):], body, subject))
                        return
                    if not (u.path == "/domain/members" and console.members is not None):
                        return self._send(404, {"detail": "no such route"})
                    subject = self._admin("members are")
                    if self._early():
                        return
                    body = self._body()
                    if body is None:
                        return
                    fp = body.get("fingerprint")
                    console.members.accept(str(body["name"]), by=subject, domain_objects=console.holder_objects,
                                           fingerprint=fp if isinstance(fp, str) else None)
                    self._send(200, console.members.read())
                except KeyError:
                    self._send(400, {"detail": "name the cluster to accept"})
                except ApiError as e:
                    self._send(e.status, {"detail": e.detail})

            def do_DELETE(self):
                u = urlsplit(self.path)
                if u.path == "/session":
                    return self._session("DELETE")
                if self._steered():
                    return
                route = console.signer_route(u.path, "DELETE")
                if route is not None:
                    return self._early() or self._to_signer("DELETE", route)
                if not (u.path.startswith("/domain/members/") and console.members is not None):
                    return self._send(404, {"detail": "no such route"})
                name = u.path.rsplit("/", 1)[1]
                try:
                    subject = self._admin("members are")
                    if self._early():
                        return
                    if not console.members.remove(name, by=subject):
                        return self._send(404, {"detail": f"{name} is not a member of this domain"})
                    self._send(200, console.members.read())
                except ApiError as e:
                    self._send(e.status, {"detail": e.detail})

            # THE DOOR IN, AT THE HOLDER (the console module's contract, §10a): the platform's shapes (`console.session`) —
            # `GET {open, login_url, user?, until?}`, `POST {token}` checked by the domain's key set and set as a cookie
            # the page's script cannot read, `DELETE` the cookie gone. The password goes to the signer's login door
            # (`login_url`, handed on from here) and never to this process. No emergency entry: that is a cluster's, for
            # when the domain is away — and this door is the domain.
            def _session(self, method: str):
                from w2cplatform.access import session_cookie
                from w2cplatform.trust.tokens import TokenError
                u = urlsplit(self.path)
                if u.path == "/session/break-glass":
                    return self._send(404, {"detail": "the emergency entry is a cluster's, for when the domain is away: "
                                                      "this door is the domain"})
                if method == "DELETE":
                    self._extra_headers = (("Set-Cookie", session_cookie("", 0)),)
                    return self._send(200, {"out": True})
                if console.person is None:
                    if method == "GET":
                        return self._send(200, {"open": True, "login_url": LOGIN_URL})
                    return self._send(400, {"detail": "this door is open: there is nothing to log in to"})
                if method == "POST":
                    body = self._body()
                    if body is None:
                        return
                    token = body.get("token")
                    if not isinstance(token, str) or not token:
                        return self._send(400, {"detail": "the door in takes {\"token\": \"…\"}"})
                else:
                    token = self._token()
                try:
                    payload = console.person(token) if token else None
                except TokenError as e:
                    if method == "POST":
                        return self._send(401, {"detail": f"token refused: {e}"})
                    payload = None                       # a cookie that has expired: not logged in, and not an error
                except ApiError as e:                    # nobody can be checked here now: said, whoever asks
                    return self._send(e.status, {"detail": e.detail})
                if payload is None:
                    return self._send(200, {"open": False, "login_url": LOGIN_URL})
                if method == "POST":
                    secure = self.headers.get("X-Forwarded-Proto", "") == "https"
                    self._extra_headers = (("Set-Cookie", session_cookie(token, float(payload.get("exp", 0)) - time.time(),
                                                                         secure)),)
                    return self._send(200, {"user": payload.get("sub"), "until": payload.get("exp")})
                return self._send(200, {"open": False, "login_url": LOGIN_URL, "user": payload.get("sub"),
                                        "until": payload.get("exp")})

            # A PERSON'S REQUEST THAT NEEDS THE DOMAIN'S KEYS GOES TO THE PROCESS THAT HAS THEM (ADR-0032): the body as
            # it came, the person's token with it; the signer checks it whole, this door answers what it said. No key
            # here, and no «sign this» to ask for.
            def _to_signer(self, method: str, route: str):
                if not console.signer_url:
                    return self._send(503, {"detail": "this console knows no signer (SIGNER_HOST, SIGNER_PORT): the "
                                                      "domain's keys are the signer's, and so is this request"})
                raw = None
                if method in ("POST", "PUT"):
                    if not read_body(self, self.MAX_BODY):
                        return
                    raw = self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}"
                # a handover waits for its target's report and for the move, a move reads every member it reaches:
                # minutes are their own bound, not ten seconds
                timeout = 90.0 if route in ("/api/handover", "/api/move") else 10.0
                self._send(*console.ask_signer(method, route, raw, self._token(), timeout))

            def _topology(self):
                try:
                    subject = self._admin("the topology is")
                    if self._early():
                        return
                    body = self._body()
                    if body is None:
                        return
                    rev = console.topology.edit(lambda d: d.update({k: body[k] for k in ("centre", "star", "via") if k in body}),
                                                int(body.get("base_rev", 0)), known=set(console.view.fed.clusters), by=subject,
                                                domain=console.view.fed.domain_holder.name)
                    if console.journal is not None:
                        console.journal.say("domain.topology.changed", user=subject or "?", target="topology", rev=rev)
                    self._send(200, {"rev": rev, **console.topology.read()})
                except Conflict as e:
                    self._send(409, {"detail": str(e)})
                except ApiError as e:
                    self._send(e.status, {"detail": e.detail})

            def log_message(self, *a):
                pass

        return H

    @staticmethod
    def signer_route(path: str, method: str = "GET") -> str | None:
        """The signer's route a person's request at `path` is handed to — None for one of this door's own, or for a
        method the signer's operation does not take there (`PUT /domain/shared`, `POST /domain/handover`, `POST
        /domain/move`, `POST /api/login`; the people's routes with every method)."""
        one = {"/domain/shared": "PUT", "/domain/handover": "POST", "/domain/move": "POST", "/api/login": "POST"}
        for mine, theirs in TO_SIGNER.items():
            if path == mine:
                return theirs if one.get(mine, method) == method else None
            if path.startswith(mine + "/") and theirs.startswith("/api/people/"):
                return theirs + path[len(mine):]
        return None

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


# A grant as the page reads it (the product's line): `{subject, cap, scope, until}` — `scope` is `*` (every unit),
# `unit:<sub>/<id>` (one unit, the course's item) or `labels:a,b`.
def _line(g) -> dict:
    from .grants import UNIT_SCOPE
    scope = "labels:" + ",".join(sorted(g.labels)) if g.labels else "*" if g.unit is None else UNIT_SCOPE + g.unit
    return {"subject": g.subject, "cap": g.capability, "scope": scope, "until": g.valid_until}


def _item_line(g) -> str:
    line = _line(g)
    return f"{line['subject']} {line['cap']} {line['scope']}"


def _grant_of(line: dict, domain: bool, default_until: float):
    """A line of the page as a grant. The domain's own never lapse (`valid_until 0`); a cluster's lapse unless renewed
    — `until` when the line says it, else a grant's lifetime from now (Lesson 4)."""
    from .grants import UNIT_SCOPE, Grant
    if not isinstance(line, dict):
        raise TypeError("a line is an object")
    subject, cap, scope = line["subject"], line["cap"], line.get("scope") or "*"
    if cap not in ("view", "edit", "admin") or not isinstance(subject, str) or not isinstance(scope, str):
        raise ValueError(f"{subject!r} {cap!r} {scope!r}")
    until = 0.0 if domain else float(line.get("until") or default_until)
    if scope == "*":
        return Grant(subject, cap, None, until)
    if scope.startswith("labels:"):
        return Grant(subject, cap, None, until, tuple(x for x in scope[7:].split(",") if x))
    if scope.startswith(UNIT_SCOPE):
        return Grant(subject, cap, scope[len(UNIT_SCOPE):], until)
    raise ValueError(f"no such scope: {scope!r}")


def main() -> None:
    """python3 -m w2cplatform.domain.console — the domain's console."""
    import signal

    from w2cplatform import runtime
    from w2cplatform.journal import Journal
    from w2cplatform.trust.tokens import PERSON, verify
    from .runtime import federation_from_env
    from .agent import ClusterTrust

    fed = federation_from_env()
    directory = DomainDirectory(fed)
    lost_after = float(os.environ.get("LOST_AFTER", "45"))
    view = ReadView(fed, lost_after=lost_after)
    trust = ClusterTrust(fed.domain_holder.vars)

    def person(token: str) -> dict:
        from .agent import Untrusted
        try:
            ks, revoked = trust.keyset(), trust.revoked()
        except Untrusted as e:                                           # "I cannot check", not a 500 (the review's eighth pass)
            raise ApiError(503, f"nobody can be checked: {e}") from None
        if ks is None:
            raise ApiError(503, "no signer key set in this cluster yet (is the domain agent running?)")
        return verify(token, ks, revoked, kind=PERSON)                   # the domain's door is a person's (CE)

    def consoles(cluster: str):
        # Forwarding to a member's console needs a connection TO the member, and the domain opens none
        # (`domain/uplink.py`): the edit is kept, and the member's agent takes it home on its next pass.
        from .federation import Unreachable
        raise Unreachable(f"{cluster} is reached only by its own agent; the edit waits for its next pass")

    auth = os.environ.get("AUTH", "1") == "1"
    from .pending import PendingEdits
    pending = PendingEdits(fed.domain_holder.vars)
    api = ConsoleAPI(directory, consoles, verifier=(lambda t: person(t)["sub"]) if auth else None,
                     pending=pending, last_known=view.last_known)
    from .topology import Topology

    # The domain's own grants (`domain/grants/domain`, feedback CA) — not the carried grants of whichever cluster
    # holds the domain today, which a move would change.
    from .grants import domain_may

    def admin(subject: str) -> bool:
        return domain_may(fed.domain_holder.vars, subject, "admin", time.time())

    def viewer(subject: str) -> bool:
        return domain_may(fed.domain_holder.vars, subject, "view", time.time())

    from .alarms import AlarmHistory, DomainAlarms, ReportedDoor
    from .members import Members
    from .uplink import _CopyObjects
    # Its own lines of the journal (ADR-0032): who admitted a member, changed the topology or the grants, kept an edit
    # again — role `domainconsole`; the signer writes its own (`domain`).
    journal = Journal(runtime.events_said(os.environ), "domainconsole", time.time)
    ho = fed.domain_holder.objects
    configured = [n for n, c in fed.clusters.items() if isinstance(c.objects, _CopyObjects)]
    members = Members(fed.domain_holder.vars, configured=lambda: configured, domain=fed.domain_holder.name, journal=journal)
    alarms = DomainAlarms(fed, lambda m: ReportedDoor(m, ho, lost_after), lost_after=lost_after,
                          history=AlarmHistory(ho))                       # read: the week is kept by the signer's pass
    console = Console(directory, view, api, refresh_interval=float(os.environ.get("REFRESH_INTERVAL", "5")),
                      holder_objects=ho, holder_vars=fed.domain_holder.vars, pending=pending,
                      topology=Topology(fed.domain_holder.vars), admin=admin, members=members, viewer=viewer,
                      signer_url=f"http://{os.environ.get('SIGNER_HOST', '127.0.0.1')}:{os.environ.get('SIGNER_PORT', '8445')}",
                      alarms=alarms, journal=journal, person=person if auth else None)
    srv = console.serve(os.environ.get("CONSOLE_HOST", "0.0.0.0"), int(os.environ.get("CONSOLE_PORT", "8443")))
    stop = threading.Event()
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    stop.wait()
    console.stop(srv)


if __name__ == "__main__":
    main()
