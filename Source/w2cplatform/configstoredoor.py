"""configstore -door — a door without a vote (ADR-0070 step 5): a store daemon on a server that holds no raft. Its
processes reach it as they reach a voter, on the socket of their role, with the same rights file; it checks what they
may, and passes what they ask to the group over the voters' mutual-TLS `-api` doors.

    python3 -m w2cplatform.configstore -door -id srv-d -voters srv-a@10.0.0.1:8300,srv-b@10.0.0.2:8300 \\
        -rights /etc/w2c/configstore-rights.json -tls /etc/w2c/tls        # a certificate: w2c-ca.sh issue srv-d configstore-door

It answers itself `/v1/status` (`state: door`, the voters and the leader as the voters last said them), `/metrics`
(`configstore_door_forwards_total{outcome=answered|unavailable|ambiguous}`, `configstore_door_voters_reachable`), on
every socket; everything else is checked here and passed on.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # configstoredoor.py — a door without a vote
#
# **Role.** A group stays three or five voters (`-group-size`, ADR-0070); a cluster has more servers than that, and the
# processes of every server want the store at a socket beside them — a socket near, not a quorum near. A door is that
# socket: a daemon with no raft and no journal, which takes its processes' requests on `<sockets>/<role>.sock` exactly as
# a voter does and passes them to the group. The group does not grow a vote heavier for it. This is the owner's step 5
# of ADR-0070 (2026-10-10), in the form «Архитектор» gave it on 2026-10-11 and the product built (`configstore/node/
# doormode.go`): the flags, the certificate kind, the row of the doors, the metrics and the refusals are the product's
# words. A REPLICA WITHOUT A VOTE — a raft log with no vote, reads from a local copy — is another thing, and stays behind
# the leader's ceiling measured in step 2: reads here are linearizable through the leader, and a replica alone would not
# unload it.
#
# ## What it does with a request
# - `/v1/status` and `/metrics`: answered here, on every socket, `admin.sock` included.
# - `get`, `list`, `write`: the rights first, here — `storemachine.answer` itself, with a store that is not reached:
#   whatever `answer` refuses (403, 400, 413) is answered here, and what it would hand to the store is passed on as it came
#   (`_PassOn`). The voter asks the SAME rights file again, as the role the door names (`X-Configstore-Role`, the socket's
#   role here): a door cannot widen a role, and a role socket's caller cannot say another (`configstore._who_asks`).
# - anything the operator asks on `admin.sock` but the status and the metrics: 403 — the operator asks the group at a
#   voter's `admin.sock`; a door holds nothing to back up, restore or join.
# - anything else: 404, not a door's.
#
# ## To whom, and when nobody answers
# The voters it knows, the leader first (`refresh`). The leader's `-api` door answers from its state machine; a follower's
# hands the command to the leader through the library (`pysyncobj` forwards over the raft port) — so the first voter that
# answers, answers for the group, and its answer goes back as it came. A voter that does not answer within its share of the
# caller's wait (`DOOR_TRY` at least, the caller's `X-Deadline` less `DOOR_MARGIN` split over the voters left) is passed
# over to the next — for a read, and for a write with an id (the handle's writes carry one: the machine answers a repeat
# from the first). A write without an id that went out and got no answer may have been made: 503 `ambiguous`, as at a
# voter. None reached: 503 `unavailable` with the reason, said before the caller's own wait runs out — never a hang. The
# handle reads that as a store that did not answer (`StoreUnavailable`): the processes behind the door go on by their last
# assignment, their leases silent, not fenced, to `unconfirmed_max` (`epoch.Lease`; `control-and-data-plane.mdc`) — as on a
# server cut off from the group.
#
# ## The group as it stands
# `-voters` is where it starts, not the group: every `FOLLOW` seconds the door asks each voter it knows for `/v1/status`
# and takes the members the first one names (their `-api` doors, the leader first). A join or a leave reaches the door
# by that; a seed that died after the door learned the others is no loss. How many answered the last ask is
# `configstore_door_voters_reachable`; nobody answered — the list it had stands.
#
# ## Seen by the operator, not counted as a voter
# A door is in no voter's `configstore_raft_voters` or `voters_expected`, nor in the members of `/v1/status`. It says it
# is alive in a row of its own, `platform/doors/configstore/<id>` `{seen_at}` (seconds since the epoch), every
# `DOOR_BEAT` — asked as `configstore-door`, which may write that one row and nothing else (`configstore._DoorRights`);
# every voter's `configstore_doors` counts the rows seen within three beats: a dead door leaves the count.
#
# ## Its certificate is a door's
# `w2c-ca.sh issue <server> configstore-door`: CN `configstore-door.<server>`, SAN URI `urn:w2c:role:configstore-door`
# alone, no `raft.secret` in the bundle (`tls.py`, A door's certificate). A voter lets it onto its `-api` door to forward
# `configstore.DOOR_PATHS` — never a join, a leave, the rights, never as the admin — and only under the name its
# certificate is for (`X-Configstore-Door`). A door started on a voter's certificate does not start, nor a voter on a
# door's. WITHOUT `-tls` NO DOOR (the course's own rule, not the product's): the course's `-api` door is mutual TLS only
# (`configstore.py`, Doors), so a door without a certificate has nobody to pass anything to. The product's door without
# TLS speaks to voters on loopback only; the course's voters open no plain door to speak to.
# ================================================================================================
from __future__ import annotations

import argparse
import http.client
import json
import os
import secrets
import sys
import threading
import time

from . import tls
from .configstore import (API_PER_ADDRESS, DOOR_BEAT, HEADER_DOOR, HEADER_ROLE, RIGHTS_FILE, SOCKETS, _door,
                          _PeerConnection, _SERVER_ID, _unix_server, socket_group)
from .storemachine import ADMIN, DOOR, DOORS_PREFIX, PEER, Rights, answer, parse_command

FOLLOW = 5.0            # seconds between two asks of the group (the product's)
DOOR_TRY = 2.0          # the least a door waits for one voter before it tries the next (the product's `doorTry`)
DOOR_MARGIN = 1.0       # what it keeps of the caller's wait for its own answer (the product's `doorMargin`)
REQUEST_WAIT = 30.0     # the longest it waits for the group when the caller does not say (the product's `requestWait`)
STATUS_WAIT = 2.0       # one voter's status, asked
MAX_ANSWER = 8 << 20    # what it reads of a voter's answer


class _PassOn(Exception):
    """`answer` reached for the store: the rights passed, and the request goes to the group as it came."""


class DoorDaemon:
    """A door without a vote: `voters` the voters' `-api` doors to start from (`server@host:port`), `sockets` the
    directory of its sockets, `rights` the rights file read, `tls_dir` a door's bundle. `beat` and `follow` are the
    product's periods (a test makes them short)."""

    def __init__(self, node_id: str, voters: list[str], *, sockets: str, rights: Rights | None, tls_dir: str | None,
                 beat: float = DOOR_BEAT, follow: float = FOLLOW, log=sys.stderr):
        if not node_id or not sockets:
            raise ValueError("a door needs an id and a socket directory (-id, -sockets)")
        if not voters:
            raise ValueError("a door needs the doors of the group's voters to start from (-voters name@host:port,…)")
        for v in voters:
            tls.split_address(v)                     # `ValueError` naming it
        if rights is None:
            raise ValueError("a socket per role needs the roles: a rights file (-rights)")
        if not tls_dir:
            raise ValueError("a door passes its processes' requests to the voters' -api doors, which are mutual TLS only: "
                             f"-tls <dir> with a door's certificate (w2c-ca.sh issue {node_id} configstore-door)")
        tls.client_context(tls_dir)                  # the bundle whole: one CA, its list, our certificate
        roles = tls.own_roles(tls_dir)
        if roles == {PEER}:
            raise ValueError(f"the certificate in {tls_dir} is a voter's: a door holds a door's (w2c-ca.sh issue "
                             f"{node_id} configstore-door), which no voter lets vote")
        if roles != {DOOR}:
            raise ValueError(f"the certificate in {tls_dir} is for {', '.join(sorted(roles)) or 'no role'}, not a door's "
                             f"(w2c-ca.sh issue {node_id} configstore-door)")
        if tls.own_server(tls_dir) != node_id:
            raise ValueError(f"-id is {node_id!r}, and the certificate in {tls_dir} is for {tls.own_server(tls_dir)!r}")
        self.node_id, self.rights, self.tls_dir = node_id, rights, tls_dir
        self.beat, self.follow, self.log = beat, min(follow, beat), log
        self.leader_wait = REQUEST_WAIT              # `_door`'s wait when the caller says none
        self.lock = threading.Lock()
        self.voters, self.leader, self.reachable = list(voters), "", 0
        self.counts = {"answered": 0, "unavailable": 0, "ambiguous": 0}
        self.conns: dict[str, threading.BoundedSemaphore] = {}   # connections to one voter at once (below)
        self.servers: list = []
        self.sockets = sockets
        self._stop = threading.Event()
        os.makedirs(sockets, exist_ok=True)
        self._listen(_unix_server(os.path.join(sockets, "admin.sock"), _door(self, lambda h: ADMIN), 0o600, None))
        for role in sorted(rights.roles):
            self._listen(_unix_server(os.path.join(sockets, f"{role}.sock"), _door(self, lambda h, role=role: role),
                                      0o660, socket_group(role, rights)))
        self.refresh()
        self._loop = threading.Thread(target=self._keep, daemon=True)
        self._loop.start()

    def _listen(self, srv) -> None:
        self.servers.append(srv)
        threading.Thread(target=srv.serve_forever, daemon=True).start()

    # The group followed, and the door's row written: at once, then every `follow` and every `beat`.
    def _keep(self) -> None:
        self.say_alive()
        next_follow, next_beat = time.monotonic() + self.follow, time.monotonic() + self.beat
        while not self._stop.wait(max(0.0, min(next_follow, next_beat) - time.monotonic())):
            now = time.monotonic()
            if now >= next_follow:
                self.refresh()
                next_follow = time.monotonic() + self.follow
            if now >= next_beat:
                self.say_alive()
                next_beat = time.monotonic() + self.beat

    # -- the door's own answers ------------------------------------------------------------------------
    def status(self) -> dict:
        with self.lock:
            voters, leader = list(self.voters), self.leader
        members = []
        for v in voters:
            name, _, _ = tls.split_address(v)
            members.append({"id": name, "api": v})
        lead = tls.split_address(leader)[0] if leader else ""
        return {"id": self.node_id, "state": "door", "tls": True, "voters": [m["id"] for m in members],
                "members": members, "leader_id": lead, "leader_api": leader, "api": ""}

    def metrics_text(self) -> str:
        with self.lock:
            counts, reachable = dict(self.counts), self.reachable
        out = ["# HELP configstore_door_forwards_total requests this door passed on, by what came of them\n"
               "# TYPE configstore_door_forwards_total counter\n"]
        out += [f'configstore_door_forwards_total{{outcome="{k}"}} {counts[k]}\n'
                for k in ("answered", "unavailable", "ambiguous")]
        out.append("# HELP configstore_door_voters_reachable voters that answered this door's last ask of the group\n"
                   f"# TYPE configstore_door_voters_reachable gauge\nconfigstore_door_voters_reachable {reachable}\n")
        return "".join(out)

    # -- a request on one of its sockets (`configstore._door` calls it, as it calls a voter's) -----------
    def serve(self, method: str, target: str, raw: bytes, role: str, deadline: float, peer: str = "") -> tuple[int, dict]:
        path = target.partition("?")[0]
        if method == "GET" and path == "/v1/status":
            return 200, self.status()
        if role == ADMIN:
            return 403, {"kind": "forbidden", "error": f"{self.node_id} is a door: what the operator asks of the group is "
                                                       f"asked at a voter's admin.sock"}
        if (method, path) not in (("GET", "/v1/get"), ("GET", "/v1/list"), ("POST", "/v1/write")):
            return 404, {"kind": "badrequest", "error": f"{method} {path} is not a door's: a door passes on reads and writes"}
        named = False
        if method == "POST":
            try:
                body = parse_command(raw)
                named = isinstance(body, dict) and bool(body.get("id"))
            except ValueError:
                pass                                 # `answer` says what is wrong with it
        try:
            return answer(method, target, raw, role, self.rights, self._reach)   # a refusal: said here, nothing passed on
        except _PassOn:
            return self.pass_on(method, target, raw, role, deadline, named)

    @staticmethod
    def _reach(cmd: dict) -> dict:
        raise _PassOn()

    # -- to the group ------------------------------------------------------------------------------------
    def _ask(self, voter: str, method: str, target: str, raw: bytes | None, headers: dict,
             timeout: float) -> tuple[bool, int, dict | None]:
        """One request to one voter's `-api`: (written, status, body). `body` None — no answer came, or not a whole one;
        `written` — the request went out before that, and a write may have been made.
        A voter's `-api` door serves `API_PER_ADDRESS` connections from one address and closes the next unanswered; so
        the door holds no more than that to one voter at once, and the next request waits its turn within its share
        (the product's `MaxConnsPerHost`) — a busy door is a queue here, not a voter that went away."""
        with self.lock:
            turn = self.conns.setdefault(voter, threading.BoundedSemaphore(API_PER_ADDRESS))
        start = time.monotonic()
        if not turn.acquire(timeout=timeout):
            return False, 0, None
        try:
            return self._ask_now(voter, method, target, raw, headers, max(0.1, timeout - (time.monotonic() - start)))
        finally:
            turn.release()

    def _ask_now(self, voter: str, method: str, target: str, raw: bytes | None, headers: dict,
                 timeout: float) -> tuple[bool, int, dict | None]:
        conn = _PeerConnection(voter, self.tls_dir, timeout)
        written = False
        try:
            conn.request(method, target, body=raw or None, headers={HEADER_DOOR: self.node_id, **headers})
            written = True
            r = conn.getresponse()
            got = r.read(MAX_ANSWER + 1)
            said = json.loads(got) if len(got) <= MAX_ANSWER else None
            return written, r.status, said if isinstance(said, dict) else None
        except (OSError, http.client.HTTPException, ValueError):
            return written, 0, None
        finally:
            conn.close()

    def pass_on(self, method: str, target: str, raw: bytes, role: str, deadline: float, named: bool) -> tuple[int, dict]:
        """The request to the leader's door, or — when that does not answer — to any voter's; the answer as it came."""
        with self.lock:
            voters = list(self.voters)
        again = method == "GET" or named
        until = time.monotonic() + min(max(0.0, deadline - DOOR_MARGIN), REQUEST_WAIT)
        for i, v in enumerate(voters):
            share = max((until - time.monotonic()) / (len(voters) - i), DOOR_TRY)
            headers = {"Content-Type": "application/json", "X-Deadline": f"{max(0.1, share - 0.5):.3f}"}
            if role and role != ADMIN:
                headers[HEADER_ROLE] = role
            written, code, said = self._ask(v, method, target, raw, headers, share)
            if said is None:
                if written and not again:
                    self._count("ambiguous")
                    return 503, {"kind": "ambiguous", "error": f"the door {self.node_id} passed the write to "
                                                               f"{tls.split_address(v)[0]}, and no answer came: it may have "
                                                               f"been made"}
                continue
            self._count("answered")
            return code, said
        self._count("unavailable")
        return 503, {"kind": "unavailable", "error": f"the door {self.node_id} reached none of the group's voters "
                                                     f"({', '.join(voters)}): the store has no leader within reach"}

    def _count(self, outcome: str) -> None:
        with self.lock:
            self.counts[outcome] += 1

    def refresh(self) -> None:
        """The group as it stands: each voter it knows asked for its status; the first that names the members gives the
        list, the leader first; how many answered is `configstore_door_voters_reachable`."""
        with self.lock:
            known = list(self.voters)
        got, reached = None, 0
        for v in known:
            _, code, said = self._ask(v, "GET", "/v1/status", None, {}, STATUS_WAIT)
            if code != 200 or said is None:
                continue
            reached += 1
            if got is None and said.get("members"):
                got = said
        with self.lock:
            self.reachable = reached
            if got is None:
                return                               # nobody answered: the list it had stands
            lead = got.get("leader_api") or ""
            voters = [m["api"] for m in got["members"] if isinstance(m, dict) and m.get("api")]
            if voters:
                self.voters = sorted(voters, key=lambda a: a != lead)   # the leader first
                self.leader = lead if lead in voters else ""

    def say_alive(self) -> None:
        """This door's row of the doors, written as the door itself (`DOOR`): when it was last seen."""
        key = DOORS_PREFIX + self.node_id
        raw = json.dumps({"op": "put", "key": key, "items": {"seen_at": f"{time.time():.3f}"}, "cas": None,
                          "id": secrets.token_hex(16)}).encode()
        code, said = self.pass_on("POST", "/v1/write", raw, DOOR, DOOR_TRY * 2 + DOOR_MARGIN, True)
        if code != 200:
            print(f"configstore {self.node_id}: the door's row ({key}) was not written: {code} {said.get('error', '')}",
                  file=self.log, flush=True)

    def stop(self) -> None:
        self._stop.set()
        for srv in self.servers:
            srv.shutdown()
            srv.server_close()
        for f in os.listdir(self.sockets):
            if f.endswith(".sock"):
                try:
                    os.unlink(os.path.join(self.sockets, f))
                except OSError:
                    pass


# -- the command line ----------------------------------------------------------------------------------
# What a voter is and a door is not: said by name, not left to «unrecognized arguments» (the product's refusal).
_MEMBER_FLAGS = ("-raft", "-dir", "-api", "-group-size", "-bootstrap", "-join", "-advertise", "-index-base", "-force",
                 "-tuning", "-leader-wait")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m w2cplatform.configstore -door",
                                 description="a door without a vote: no raft; its processes' requests checked here and "
                                             "passed on to the group (ADR-0070 step 5)")
    ap.add_argument("-door", action="store_true", required=True)
    ap.add_argument("-id", required=True, help="this server's name")
    ap.add_argument("-voters", required=True,
                    help="the doors of the group's voters to start from, name@host:port,… (the group as it stands is "
                         "asked of them)")
    ap.add_argument("-sockets", default=SOCKETS, help=f"the role sockets' directory (default {SOCKETS})")
    ap.add_argument("-rights", default=RIGHTS_FILE, help=f"the rights file (default {RIGHTS_FILE})")
    ap.add_argument("-tls", default=tls.TLS_DIR, help=f"the TLS directory, a door's certificate (default {tls.TLS_DIR})")
    for flag in _MEMBER_FLAGS:
        ap.add_argument(flag, nargs="?", const=True, default=None, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    given = [f for f in _MEMBER_FLAGS if getattr(a, f.lstrip("-").replace("-", "_")) is not None]
    if given:
        ap.error(f"-door holds no raft and is no member: no -raft, -dir, -api or -group-size ({' '.join(given)})")
    if not _SERVER_ID.match(a.id):
        ap.error(f"-id is a server's name, not {a.id!r}")
    voters = [v.strip() for v in a.voters.split(",") if v.strip()]
    try:
        door = DoorDaemon(a.id, voters, sockets=a.sockets, rights=Rights.load(a.rights), tls_dir=a.tls)
    except (ValueError, OSError) as e:
        print(f"configstore -door: {e}", file=sys.stderr, flush=True)
        return 1
    print(json.dumps({"door": a.id, "voters": door.status()["voters"], "serving": a.sockets}), flush=True)
    stop = threading.Event()
    try:
        import signal
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
    except (ImportError, ValueError):
        pass
    try:
        while not stop.wait(3600):
            pass
    except KeyboardInterrupt:
        pass
    door.stop()
    return 0
