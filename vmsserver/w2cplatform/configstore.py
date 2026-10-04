"""configstore — the cluster's config store daemon: one per server, a member of the raft group, a unix socket per
role for the processes of its server, a mutually authenticated door for the other daemons.

    python3 -m w2cplatform.configstore -id srv-a -dir /data/platform/configstore -raft 10.0.0.1:8301 \\
        -api 10.0.0.1:8300 -rights /etc/w2c/configstore-rights.json -tls /etc/w2c/tls -bootstrap
    python3 -m w2cplatform.configstore -id srv-b … -join srv-a@10.0.0.1:8300

and the operator's commands, through this server's `admin.sock` (the product's own `configstore …` command):

    python3 -m w2cplatform.configstore status
    python3 -m w2cplatform.configstore join <id> <raft host:port> [<api server@host:port>]
    python3 -m w2cplatform.configstore leave <id>
    python3 -m w2cplatform.configstore rights [<file>]          # what the daemon holds, or check a file
    python3 -m w2cplatform.configstore backup > rows.json
    python3 -m w2cplatform.configstore restore --from rows.json  # into a fresh group
    python3 -m w2cplatform.configstore import --from file:///data/platform/config   # a box's rows, once
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # configstore.py — the daemon
#
# **Role.** The cluster without an orchestrator (the owner's decision of 3 October) keeps its rows in our own
# store: `FileVariables`' semantics (`storemachine.py`) replicated over the servers by a real raft library —
# consensus is not something we write. The library is `pysyncobj` (pure Python, dynamic membership, a journal;
# `pip install pysyncobj`); the product's is `hashicorp/raft`, and what this daemon shows about the SHAPE —
# sockets per role, rights before forwarding, a retried write applied once, joins, faults — is the product's API
# by its own names. The library is imported inside `_library()` only: a process that opens `configstore://` never
# needs it, and the platform imports where it is not installed (`test_portability`).
#
# Why a daemon per server and not a raft node per process: a server runs a console, controllers and workers, and
# a group of fifteen voters that changes every time a worker restarts is not a group.
#
# ## Doors
# - `<sockets>/<role>.sock` — one per role of the rights file, 0660, group `socket_group(role)` (the role's `group` in
#   the file) when that group exists: a unit with that `SupplementaryGroups=` and
#   `PLATFORM_STORE=configstore:///run/configstore/<role>.sock` can open its own role's socket and no other. The
#   socket IS the caller's identity; the daemon asks the rights file (`storemachine.Rights`) BEFORE anything is
#   forwarded or applied — a 403 never costs a log entry.
# - `<sockets>/admin.sock` — 0600, root's: everything but what nobody does (an epoch deleted, `domain/*` deleted
#   by anyone but the domain's own roles, `storemachine.DOMAIN_ROLES`). The operator's commands (`status`, `join`, `leave`, `rights`, `backup`, `restore`,
#   `import` — the product's `configstore` command has the same verbs) and the contract suite use it.
# - `-api host:port` — the other daemons' door: `/v1/status`, and `/v1/join` / `/v1/leave` of the calling daemon's
#   OWN server (the id in the body is the server its certificate names). Mutual TLS, mandatory (`tls.py`): a client
#   certificate of the installation's CA with the role `configstore`, or the handshake fails (no certificate) or the
#   door answers 403 (another role's certificate). A certificate the CA has revoked fails the handshake (`tls.py`,
#   `crl.pem`; the review's thirteenth pass, major 5), and one that names no server is refused (minor). A daemon has
#   NO right on a row (the review's twelfth pass, major 3; `storemachine.Rights`), and no request on this door is
#   answered as anybody else's: a data request is 403, whatever it carries (the thirteenth pass, major 1 — below).
#   A join that would leave a voter nobody runs is refused: an id already in the group at another raft address, a
#   raft address another id holds — however it is spelled, compared as the addresses it resolves to — or one where
#   no raft member of this installation answers as that address (`RaftBackend.add`, `_raft_says`). A certificate that
#   carries `configstore` with another role is no daemon's, on either side of the door and as our own (`tls.py`).
# - the raft port (`-raft`) — the library's own, pickle on the wire: an open one is code execution for anyone
#   who reaches it. `password=` from `<tls>/raft.secret` encrypts and authenticates it (the product's
#   `hashicorp/raft` puts TLS there instead; `password=` needs the `cryptography` module). The library is told to
#   listen on the raft address it was given (`bindAddress`) — left to itself it listened on every interface
#   (the review's twelfth pass, blocker 1: `-raft 127.0.0.1:…` without `-tls` passed a check of the address's
#   TEXT, and the socket was on `0.0.0.0`). Without the secret a member is a group of one and its socket is on
#   loopback, proved by the socket — the address resolved and bound before the library is started, and the
#   library's own listening socket asked again after (`RaftBackend._open_only_to_this_box`); a partner, a join, an
#   operator's `join`, or a start from a journal that names partners, all refused.
#
# ## Every door is bounded (the review's twelfth pass, major 1)
# A role socket made a thread for every connection and waited on it for ever: 200 idle connections were 203
# threads, and `Content-Length: -1` was `read(-1)` — a read to the end of a connection the caller kept open. Each
# door now serves `ROLE_CONNECTIONS` (the `-api` door `API_CONNECTIONS`, `API_PER_ADDRESS` of them to one address)
# connections at once; the next is answered 503 `unavailable` on the spot, unread — not done, so a write may be sent
# again — (the `-api` door just closes it: there is no TLS yet to answer in). A request's line and headers arrive
# whole within `HEADERS_WAIT` and a body within its own deadline with a floor on its pace — the platform's
# `Deadlined` and `read_body` (`console.py`), the same as every other door's — and a length that is not a
# non-negative number is 400, one past `MAX_BODY` 413, unread. `MAX_BODY` is a row's ceiling (`storemachine.MAX_VALUE`)
# as JSON may spell it: six bytes for a character at worst.
# The names an installation sees — paths, the socket groups — are the constants below, each said once.
#
# ## Writes and reads, and what a follower does with them
# Every request is one command of the log — reads too: `get` and `list` are answered by the state machine at
# their entry, on the leader of that term, so a read is linearizable (pysyncobj has no ReadIndex and no leader
# lease; this is the one linearizable read it allows). A lease renewal is a READ (`Lease.renew` reads the epoch
# row): a follower cut off from the group must not go on confirming an epoch the others have moved.
# A command that arrives at a follower is carried to the leader by the library over the raft port — the daemon's
# forwarding is the library's (`appendEntriesUseBatch=False`: at once, not at the next tick — 150 ms a write
# otherwise). The rights were checked on the way in, by the daemon whose socket the caller opened.
# NO DAEMON FORWARDS A REQUEST OVER THE `-api` DOOR, AND THE DOOR TAKES NONE (the review's thirteenth pass, major 1;
# the author's decision). The door answered a data request marked `X-Configstore-Forwarded: <role>` with that role's
# rights — the product's `hashicorp/raft` carries no commands, so its daemon forwards them so — but this daemon
# never sent the mark, and any daemon's certificate made itself any role with it: srv-b's certificate deleted
# `vms/slots/*` as `vmsworker` and `domain/keys/*` as `domain` at srv-a's door. The path is gone: a data request on
# the `-api` door is 403, marked or not, until a daemon that forwards exists (mTLS, its second round).
#
# ## Faults — "not done" and "do not know" are different answers
# `commandsWaitLeader=False`: with no leader the library refuses a command at once instead of queueing it, so
# a write the daemon gave up on with only such refusals was NOT done — 503 `unavailable`. A write handed to a
# leader that went before answering ("leader changed", no answer in time) may yet commit — 503 `ambiguous`.
# Inside its wait (`-leader-wait`, 5 s; the handle's `X-Deadline` when shorter) the daemon retries both with the
# write's own id, so a write that did land is answered from the machine's memory, not applied twice.
#
# ## A group: one server, then three
# `-bootstrap` on an empty `-dir` starts a group of one: it elects itself, writes its `base` (`-index-base`) and its
# own member row, and only then opens its sockets. A new server starts its own daemon with `-join <a member's
# api>`: it asks the member who is in the group, starts with them as partners, and asks to be added — in that
# order, because a group that counts a voter which is not running has lost a vote. The member hands the change
# to the library, which carries it to the leader (AddVoter); the library takes one membership change at a time
# and refuses a second while the first is uncommitted, and the daemon retries that refusal.
# A daemon that was taken into a group (`member.json`) starts from its journal, with the members it saw last:
# `-bootstrap` and `-join` count only the first time, so a unit restarted by systemd with the same flags just comes
# back. A start that failed before its group took it leaves nothing it would start from.
# THE PARTNERS ARE WRITTEN WITH THE MEMBERSHIP, IN ONE FILE (the review's thirteenth pass, blocker 1). `member.json`
# was written as soon as the join was accepted and the partners (`peers.json`) half a second later, on the first
# tick: a member killed between the two came back with its journal and no partner — a leader of a group of one, its
# own rows, create-only handing out epoch «1» where the group's was 7. The journal does not name the member a group
# was bootstrapped on (its membership is no command of the log), so the journal cannot give it back. Now
# `member.json` carries the partners and how the daemon became a member (`how`: `bootstrap` or `join`), written
# atomically at once — a join's partners are the members the group named when it took it — and rewritten when the
# library's view changes (`_keep_peers`) or this daemon changes the group (`add`, `remove`). A member that JOINED
# and knows no partner never starts alone: it asks its `-join` door who the group is, or refuses to start
# (`start_member`); only a group that shrank to it, by the library's own word (`alone`), is a group of one.
# The operator's `join` / `leave` are the same change asked through `admin.sock`, for a member already running.
#
# ## The one-time import (a box becomes a cluster), and backup / restore
# A box keeps `file://`. `configstore import --from file:///data/platform/config` copies its rows, values untouched,
# through `admin.sock` into a FRESH group — no rows yet — whose base (`-index-base N`) is at least the file's
# counter: every new version is above every old one, so a version a process still remembers from the file matches
# nothing and its CAS conflicts. Online, through the daemon, because a write that goes through the log is on every
# member; and refused whole, before the first write, when the file holds a row that does not read or a row heavier
# than the store takes (`storemachine.MAX_VALUE`).
# `backup` writes every row and the highest version it saw; `restore` is the same import from that file, into a
# fresh group whose base is above that version. (The product's `recover` — a group rebuilt from one survivor's
# journal when the majority is gone for good — is not here.)
# AN IMPORT THAT STOPPED IS CONTINUED (the review's twelfth pass, minor: it could not be). The same `import` or
# `restore` again goes on where the last one stopped when every row the group holds is one it loaded — the same key,
# the same items; a row it did not load, or one changed since, refuses it as before: rows are loaded into a group
# nobody else has written to.
#
# ## What pysyncobj does not give (and the product's library does)
# - the journal is a memory-mapped file with no fsync before an entry is acknowledged: it survives a killed
#   process, not a power cut of a majority (`FileVariables` has its barriers for exactly that, feedback BD); the
#   product's `raft-boltdb` syncs every batch before it is acknowledged. Open here, and said in lesson 2.
# - no pre-vote and no leader lease; a leader cut off from the others steps down after `leaderFallbackTimeout`
#   (30 s by default) — harmless for correctness, because reads go through the log
# ================================================================================================
from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import os
import re
import socket
import socketserver
import ssl
import sys
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import runtime, tls
from .storemachine import ADMIN, MAX_VALUE, PEER, Ambiguous, Rights, StoreMachine, Unavailable, answer
from .variables import STORE_SCHEME, items_bytes

# What an installation sees, each said once (the product names them; a rename is a line here).
SOCKETS = "/run/configstore"                        # `<role>.sock` and `admin.sock`
DATA = runtime.DATA + "/configstore"                # journal, dump, member.json — the platform's state (`runtime.DATA`)
RIGHTS_FILE = runtime.ETC + "/configstore-rights.json"   # generated from the spec (М11: `python3 -m cluster rights`)
ADMIN_URL = f"{STORE_SCHEME}://{SOCKETS}/admin.sock"
PLATFORM_ROLES = frozenset({"resource"})            # the platform's own processes among the store's callers


# A role socket's group: what the rights file says for the role (`group`, the product's format), else `w2c-<role>` for
# the platform's own processes and `vms-<role>` for the subsystems' (the product's boundary: vms is a subsystem, not
# the platform).
def socket_group(role: str, rights: Rights | None = None) -> str:
    if rights is not None and role in rights.groups:
        return rights.groups[role]
    return ("w2c-" if role in PLATFORM_ROLES else "vms-") + role


LEADER_WAIT = 5.0          # how long a command may wait for a leader before the daemon answers 503
JOIN_WAIT = 30.0           # a membership change: one at a time, a log entry, a new member catching up
BIND_WAIT = 10.0           # how long the library may take to open the raft port
ANSWER_WAIT = 2.0          # how long a new voter's raft port may take over each step of its handshake, before it is added

# What every door bears (the review's twelfth pass, major 1; the notes above).
ROLE_CONNECTIONS = 64      # connections one socket (a role's, `admin.sock`) serves at once
API_CONNECTIONS = 32       # …the `-api` door: a few daemons, each with a join or a status at a time
API_PER_ADDRESS = 8        # …of which one address holds this many, so a stranger's handshakes do not fill it
HEADERS_WAIT = 5.0         # seconds a request's line and headers may take, whole
DOOR_TIMEOUT = 10.0        # seconds a door's socket waits on a caller that sends or reads nothing
MAX_BODY = 6 * MAX_VALUE + (64 << 10)   # a row at its ceiling, every character escaped (`\u00XX`), and its key

# Timings by name (`-tuning`). `default` is the library's own (election 0.4–1.4 s, heartbeat 0.1 s); `lan` is
# what a LAN of three can afford; `slow` is a loaded box or a WAN — the shape Consul ships (five times its LAN
# timings), kept for the measurement (`tests/configstore_election.py`): it is what leases do NOT survive.
TUNINGS = {
    "default": {},
    "lan": {"raftMinTimeout": 0.15, "raftMaxTimeout": 0.35, "appendEntriesPeriod": 0.03, "connectionTimeout": 1.0,
            "connectionRetryTime": 0.5},
    "slow": {"raftMinTimeout": 2.0, "raftMaxTimeout": 7.0, "appendEntriesPeriod": 0.5, "connectionTimeout": 10.0},
}


# -- backends: where a command is applied --------------------------------------------------------------
class LocalBackend:
    """The machine in this process, under a lock: no group, no raft. A test's daemon, and the shape of a stand's."""

    def __init__(self, node_id: str = "local", index_base: int = 0):
        self.node_id = node_id
        self.machine = StoreMachine(index_base)
        self.lock = threading.Lock()

    def submit(self, cmd: dict, deadline: float | None = None) -> dict:
        with self.lock:
            return self.machine.apply(cmd)

    def add(self, node_id: str, raft: str, api: str, deadline: float = JOIN_WAIT) -> None:
        raise Unavailable("this store is not a raft group: nothing to join")

    def remove(self, node_id: str, deadline: float = JOIN_WAIT) -> None:
        raise Unavailable("this store is not a raft group: nothing to leave")

    def status(self) -> dict:
        return {"id": self.node_id, "state": "leader", "leader": self.node_id, "members": [{"id": self.node_id}],
                "term": 0, "commit": self.machine.applied, "applied": self.machine.applied,
                "index_base": self.machine.base, "rows": len(self.machine.rows)}

    def stop(self) -> None:
        pass


_BUILT: dict = {}


def _library():
    """pysyncobj and the replicated wrapper of the machine, built on first use."""
    if _BUILT:
        return _BUILT
    from pysyncobj import FAIL_REASON, SyncObj, SyncObjConf, SyncObjConsumer, replicated

    class Replicated(SyncObjConsumer):
        # Everything set after `super().__init__()` is the replicated state, and what a dump carries.
        def __init__(self):
            super().__init__()
            self.m = StoreMachine()

        # The raft index of the entry being applied: the library moves its count after an entry, so the one in
        # hand is the next — the same number on every member, after a restart and after a dump.
        @replicated
        def command(self, cmd):
            return self.m.apply(cmd, self._syncObj.raftLastApplied + 1)

    _BUILT.update(FAIL_REASON=FAIL_REASON, SyncObj=SyncObj, SyncObjConf=SyncObjConf, Replicated=Replicated)
    return _BUILT


def have_library() -> bool:
    try:
        _library()
        return True
    except ImportError:
        return False


# The interface a raft address names, as the socket will be bound to it: `host:port` resolved once, so what is checked
# and what the library binds are one address (`bindAddress` takes it as it is; left out, the library binds `0.0.0.0`).
def _bind_address(raft: str) -> tuple[str, int]:
    host, sep, port = raft.rpartition(":")
    if not sep or not host or not port.isdigit():
        raise ValueError(f"not a raft address: {raft!r} (host:port)")
    try:
        info = socket.getaddrinfo(host.strip("[]"), int(port), type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ValueError(f"the raft address {raft} names no interface: {e}") from None
    return info[0][4][0], int(port)


# Where a raft address leads, as the set of (ip, port) it resolves to — `localhost:8301`, `127.0.0.1:8301`,
# `LOCALHOST.:8301` and `[::ffff:127.0.0.1]:8301` are one place (the review's thirteenth pass, major 3: a join compared
# the TEXT, and srv-d joined at `localhost:<srv-a's port>` beside srv-a — a voter nobody runs). Empty when it
# resolves to nothing.
def _places(raft: str) -> set[tuple[str, int]]:
    host, sep, port = raft.rpartition(":")
    if not sep or not host or not port.isdigit():
        return set()
    try:
        info = socket.getaddrinfo(host.strip("[]"), int(port), type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError, ValueError):
        return set()
    out = set()
    for *_, addr in info:
        ip = ipaddress.ip_address(addr[0].split("%", 1)[0])
        ip = getattr(ip, "ipv4_mapped", None) or ip
        out.add((str(ip), int(port)))
    return out


# The raft addresses of `addrs` that are not this member's own, however it is spelled there: a partner list that named
# this member under another spelling would make it a voter of its own group nobody runs.
def _others(addrs, raft: str) -> list[str]:
    mine = _places(raft)
    return sorted({a for a in addrs if a and a != raft and not (mine and mine & _places(a))})


def _loopback(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


# WHAT ANSWERS AT A NEW VOTER'S ADDRESS IS ASKED WHO IT IS (the product's cross-check of its hashicorp/raft store). A
# TCP answer was the proof, and every listener answers TCP: a join with `raft=<a member's -api>` was taken, and the
# group counted a voter that never speaks raft — a group of one became two with no majority. The listener must now
# go through the library's own handshake with this installation's secret — each side sends 32 random bytes under the
# password and the other echoes them back (pysyncobj 0.3, `TcpConnection`/`TcpTransport`) — and then answer the
# library's `status` utility with its own address (`self`), which must be the very address the group will dial:
# under another spelling the group's voter is not that daemon's own name, and the library drops its connections.
# What the listener sends is unpickled only after the password authenticated it, as the library itself does.
MAX_HANDSHAKE = 1 << 20      # a status frame is a few KiB; a length past this is no raft listener's


def _raft_says(where: tuple[str, int], encryptor, timeout: float) -> str:
    """The address the raft listener at `where` calls itself, or `PermissionError` when it is none of this
    installation's (no handshake, another secret, no status)."""
    import struct
    import zlib
    from pysyncobj import pickle as wire             # the library's own pickling of its messages

    def frame(message) -> bytes:
        data = encryptor.encrypt_at_time(zlib.compress(wire.dumps(message), 3), int(time.monotonic()))
        return struct.pack("i", len(data)) + data

    def exactly(s, n: int) -> bytes:
        got = b""
        while len(got) < n:
            more = s.recv(n - len(got))
            if not more:
                raise ConnectionError("closed")
            got += more
        return got

    def read(s, mine: bytes):
        n = struct.unpack("i", exactly(s, 4))[0]
        if not 0 < n <= MAX_HANDSHAKE:
            raise ValueError(f"a frame of {n} bytes")
        echo, message = wire.loads(zlib.decompress(encryptor.decrypt(exactly(s, n))))
        if echo != mine:
            raise ValueError("our bytes not echoed")
        return message

    try:
        with socket.create_connection(where, timeout=timeout) as s:
            s.settimeout(timeout)
            mine = os.urandom(32)
            s.sendall(frame(mine))                   # the first message goes unwrapped: the other has no key yet
            theirs = read(s, mine)
            s.sendall(frame((theirs, ["status"])))
            status = read(s, mine)
        said = getattr(status.get("self"), "address", None) if isinstance(status, dict) else None
        if not isinstance(said, str):
            raise ValueError("no address in its status")
        return said
    except Exception as e:                           # noqa: BLE001 — whatever it did, it did not prove it is raft
        raise PermissionError(f"{where[0]}:{where[1]} is no raft port of this installation — nothing went through "
                              f"the raft handshake with its secret ({type(e).__name__}): start its daemon, then "
                              f"join with its -raft address") from None


NO_SECRET = ("a raft port without its secret is a group of one on this box's loopback — pickle on that port is "
             "code execution for anyone who reaches it: -tls <dir> with raft.secret (deploy/w2c-ca.sh)")


class RaftBackend:
    """One member of the group. `raft` is this member's raft address, `partners` the others' ([] for a group of
    one), `data` the directory of its journal, dump and `member.json`. Without `password` it is a group of one,
    listening on loopback, or it is not at all (the notes: Doors)."""

    def __init__(self, node_id: str, raft: str, partners: list[str], data: str, tuning: str | dict = "default",
                 password: str | None = None, leader_wait: float = LEADER_WAIT):
        ip, port = _bind_address(raft)
        if not password:
            if partners:
                raise ValueError(f"{NO_SECRET}; this member was to start with {', '.join(partners)}")
            # The socket, not the address's text: bound to the address resolved, before the library is let near it.
            probe = socket.socket(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM)
            try:
                probe.bind((ip, 0))
                bound = probe.getsockname()[0]
            except OSError as e:
                raise ValueError(f"the raft address {raft} is not this box's: {e}") from None
            finally:
                probe.close()
            if not _loopback(bound):
                raise ValueError(f"{NO_SECRET}; {raft} is {bound}")
        lib = _library()                             # after the refusals: they need no raft library to be said
        os.makedirs(data, exist_ok=True)
        knobs = dict(TUNINGS[tuning]) if isinstance(tuning, str) else dict(tuning)
        # `useFork=False`: the dump is written by the tick thread, not by a forked child — a fork of a process with
        # an HTTP server's threads in it is what macOS refuses to promise anything about.
        conf = {"dynamicMembershipChange": True, "useFork": False, "appendEntriesUseBatch": False,
                "commandsWaitLeader": False, "journalFile": os.path.join(data, "journal"),
                "fullDumpFile": os.path.join(data, "dump"), "bindAddress": f"{ip}:{port}"}
        if password:
            try:
                import cryptography  # noqa: F401 — pysyncobj's `password=` is built on it
            except ImportError:
                raise ValueError("the raft port's secret needs the cryptography module: pip install cryptography") from None
            conf["password"] = password
        self.fail = lib["FAIL_REASON"]
        self.node_id, self.raft_addr, self.data, self.leader_wait = node_id, raft, data, leader_wait
        self.secret = bool(password)
        self.rep = lib["Replicated"]()
        self.raft = lib["SyncObj"](raft, list(partners), lib["SyncObjConf"](**{**conf, **knobs}), consumers=[self.rep])
        self._stop = threading.Event()
        self._member: dict | None = None             # what `member.json` says, once the group took this daemon
        self._member_lock = threading.Lock()
        if not password:
            self._open_only_to_this_box()
        threading.Thread(target=self._keep_peers, daemon=True).start()

    # The library's own listening socket, asked: what it bound, not what it was told. Its transport keeps the socket
    # private (pysyncobj 0.3: `SyncObj.__transport._server`), so a library that renamed it is refused too — a member
    # without its secret that cannot show where it listens does not run.
    def listening(self) -> tuple | None:
        end = time.monotonic() + BIND_WAIT
        while time.monotonic() < end:
            try:
                srv = getattr(self.raft, "_SyncObj__transport")._server
                sock = getattr(srv, "_TcpServer__socket")
                if sock is not None and getattr(self.raft, "_SyncObj__transport").ready:
                    return sock.getsockname()
            except (AttributeError, OSError):
                return None
            time.sleep(0.02)
        return None

    def _open_only_to_this_box(self) -> None:
        where = self.listening()
        if where is None or not _loopback(str(where[0])):
            self.raft.destroy_synchronous()
            raise ValueError(f"{NO_SECRET}; the library listens on {where[0] if where else 'an address it does not say'}")

    # A member is one once its group took it: `member.json` is written after the bootstrap's first commands or an
    # accepted join, never before, and with the partners in it (the notes: A group). A journal without it is what a
    # start that failed left behind — a daemon that took it for state would come back as a group of one of its own,
    # beside the real one.
    @staticmethod
    def has_state(data: str) -> bool:
        return os.path.exists(os.path.join(data, "member.json"))

    @staticmethod
    def member_doc(data: str) -> dict:
        with open(os.path.join(data, "member.json")) as f:
            doc = json.load(f)
        return doc if isinstance(doc, dict) else {}

    def _write_member(self, doc: dict) -> None:
        tmp = os.path.join(self.data, "member.json.tmp")
        with open(tmp, "w") as f:
            json.dump(doc, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, os.path.join(self.data, "member.json"))

    # `how` is `bootstrap` or `join`; `partners` the other members' raft addresses as the group named them.
    def became_member(self, how: str, partners: list[str]) -> None:
        with self._member_lock:
            self._member = {"id": self.node_id, "raft": self.raft_addr, "how": how,
                            "partners": _others(partners, self.raft_addr), "alone": False}
            self._write_member(self._member)

    # A member restarted on its journal: what its `member.json` said, with the partners it starts with.
    def resumed(self, doc: dict, partners: list[str]) -> None:
        with self._member_lock:
            self._member = {"id": self.node_id, "raft": self.raft_addr, "how": doc.get("how") or "join",
                            "partners": _others(partners, self.raft_addr), "alone": bool(doc.get("alone"))}
            self._write_member(self._member)

    # The library's view, or this daemon's own change of the group, into `member.json` at once. An empty view of a
    # member that joined is the group shrunk to it, by the library's word: `alone`, a group of one from now on.
    def _save_partners(self) -> None:
        with self._member_lock:
            if self._member is None:
                return                               # not a member yet: nothing it would start from
            peers = sorted(n.id for n in self.raft.otherNodes)
            if peers != self._member["partners"]:
                self._member = {**self._member, "partners": peers, "alone": not peers}
                self._write_member(self._member)

    @staticmethod
    def forget_failed_start(data: str) -> None:
        for f in ("journal", "journal.meta", "dump", "dump.tmp", "peers.json", "peers.json.tmp", "member.json.tmp"):
            try:
                os.remove(os.path.join(data, f))
            except FileNotFoundError:
                pass

    @staticmethod
    def saved_peers(data: str) -> list[str]:
        try:
            return list(RaftBackend.member_doc(data).get("partners") or [])
        except FileNotFoundError:
            return []

    # The members this daemon sees, kept in `member.json` beside the journal: what it starts with after a restart.
    def _keep_peers(self) -> None:
        while not self._stop.wait(0.5):
            self._save_partners()

    # A command, until it is applied or the wait is over. Refusals that mean "not appended" (no leader, the queue
    # full, a membership change in progress) and those that mean "appended, outcome unknown" (leader changed, no
    # answer in time) are both retried with the SAME command — the write's id among it — so a write that did land
    # is answered from the machine's memory. What the daemon answers when the wait is over depends on which kind
    # it saw: only the first kind is "not done".
    def _apply(self, method, *args, deadline: float, write: bool):
        end = time.monotonic() + deadline
        unknown = False
        while True:
            left = end - time.monotonic()
            if left <= 0:
                if write and unknown:
                    raise Ambiguous(f"a leader took the write and went before answering, within {deadline:g} s")
                raise Unavailable(f"no leader answered within {deadline:g} s: not done")
            done, box = threading.Event(), {}

            def cb(res, err, box=box, done=done):
                box["res"], box["err"] = res, err
                done.set()

            method(*args, callback=cb)
            if not done.wait(left):
                if write:
                    raise Ambiguous(f"no answer within {deadline:g} s: the write may yet be applied")
                raise Unavailable(f"no answer within {deadline:g} s")
            if box["err"] == self.fail.SUCCESS:
                return box["res"]
            if box["err"] in (self.fail.NOT_LEADER, self.fail.LEADER_CHANGED, self.fail.UNKNOWN_OUTCOME):
                unknown = True
            time.sleep(min(0.02, max(0.0, end - time.monotonic())))

    def submit(self, cmd: dict, deadline: float | None = None) -> dict:
        write = cmd.get("op") in ("put", "delete")
        if write and not cmd.get("id"):
            cmd = {**cmd, "id": uuid.uuid4().hex}          # so the daemon's own retries are safe
        wait = self.leader_wait if deadline is None else min(self.leader_wait, deadline)
        return self._apply(self.rep.command, cmd, deadline=wait, write=write)

    def members(self) -> list[dict]:
        known = self.rep.m.members_copy()
        by_raft = {v["raft"]: {"id": k, **v} for k, v in known.items()}
        addrs = sorted([self.raft_addr] + [n.id for n in self.raft.otherNodes])
        return [by_raft.get(a, {"id": "", "raft": a, "api": ""}) for a in addrs]

    # Membership, one change at a time: the library carries the change to the leader and refuses a second while the
    # first is uncommitted; both are retried inside the wait. Then the member's row: its id and its door.
    #
    # A JOIN NEVER LEAVES A VOTER NOBODY RUNS (the review's twelfth pass, major 3: a daemon's certificate added false
    # voters). The same id again at the same address is a retry and goes through; an id the group holds at another
    # raft address, or an address another id holds, is refused — the old address would stay a voter of the group
    # beside the new one, and a group that counts a voter nobody runs has lost a vote. A server that moved leaves
    # first. A member without the raft port's secret takes nobody: it is a group of one (`NO_SECRET`).
    # "THE SAME ADDRESS" IS THE SAME PLACE, NOT THE SAME TEXT (the review's thirteenth pass, major 3): every address is
    # compared as what it resolves to (`_places`) — the members' rows, this daemon's own, and the library's voters,
    # which a row may not name. A retry spelled another way is the retry, under the spelling the group holds. An
    # address that resolves to nothing, or to every interface (`0.0.0.0`), names no server; and a new voter must
    # answer on its raft port before it is added — its daemon starts before it asks to join (`start_member`) — as a
    # raft member of this installation that calls itself that very address, not merely as a listener (`_raft_says`).
    def add(self, node_id: str, raft: str, api: str, deadline: float = JOIN_WAIT) -> None:
        if not self.secret:
            raise PermissionError(NO_SECRET)
        here = _places(raft)
        if not here or any(ipaddress.ip_address(ip).is_unspecified for ip, _ in here):
            raise PermissionError(f"{raft} names no one server's raft port")
        known = self.rep.m.members_copy()
        if node_id in known and not here & _places(known[node_id]["raft"]):
            raise PermissionError(f"{node_id} is a member at {known[node_id]['raft']}, not {raft}: leave first")
        holder = next((k for k, v in known.items() if k != node_id and here & _places(v["raft"])), None)
        if holder is not None:
            raise PermissionError(f"{raft} is {holder}'s raft address")
        mine = known.get(node_id, {}).get("raft")
        voters = {self.raft_addr} | {n.id for n in self.raft.otherNodes}
        for v in voters:
            # Its own row's address, or the very text it asks for — a join that added the voter and went before
            # its row was written, asked again — is the retry; another spelling of a voter's address is not.
            if v not in (mine, raft) and here & _places(v):
                raise PermissionError(f"{raft} is the raft address of a voter of this group ({v})")
        raft = mine or raft                          # a retry keeps the spelling the group holds
        end = time.monotonic() + deadline
        if raft not in voters:
            said = _raft_says(sorted(here)[0], self.raft.encryptor, ANSWER_WAIT)
            if said != raft:
                raise PermissionError(f"the raft port at {raft} calls itself {said}: join it as {said}, the address "
                                      f"its daemon was started with (-raft)")
            self._apply(self.raft.addNodeToCluster, raft, deadline=deadline, write=True)
            self._save_partners()
        self.submit({"op": "member", "id": node_id, "raft": raft, "api": api}, max(1.0, end - time.monotonic()))

    def remove(self, node_id: str, deadline: float = JOIN_WAIT) -> None:
        row = self.rep.m.members_copy().get(node_id)
        raft = row["raft"] if row else node_id
        if raft in {n.id for n in self.raft.otherNodes}:
            self._apply(self.raft.removeNodeFromCluster, raft, deadline=deadline, write=True)
            self._save_partners()
        self.submit({"op": "unmember", "id": node_id}, deadline)

    def status(self) -> dict:
        s = self.raft.getStatus()
        leader = s.get("leader")
        leader = leader.id if leader is not None else None
        members = self.members()
        lead = next((m for m in members if m["raft"] == leader), {})
        return {"id": self.node_id, "raft": self.raft_addr,
                "state": {0: "follower", 1: "candidate", 2: "leader"}.get(s["state"], s["state"]),
                "leader": leader, "leader_id": lead.get("id", ""), "leader_api": lead.get("api", ""),
                "members": members, "term": s["raft_term"], "commit": s["commit_idx"], "applied": s["last_applied"],
                "leader_commit": s.get("leader_commit_idx"), "index_base": self.rep.m.base,
                "rows": len(self.rep.m.rows)}

    def stop(self) -> None:
        self._stop.set()
        self.raft.destroy_synchronous()


# -- doors -----------------------------------------------------------------------------------------------
def _door(daemon: "StoreDaemon", role_of):
    """The HTTP handler of one door. `role_of(handler)` says who is calling: the socket's role, or the role in the
    peer's certificate on the `-api` door (`PermissionError` when it is not a daemon's). Reads under the platform's
    deadlines (`Deadlined`, `read_body`: the notes, "Every door is bounded")."""
    from .console import Deadlined, read_body        # the platform's door; imported here, `console` imports much

    class Door(Deadlined, BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        timeout = DOOR_TIMEOUT
        header_timeout = HEADERS_WAIT
        peer = ""                                    # the server a daemon's certificate names (`-api` door)

        def log_message(self, *a):           # a request a second per worker is not a log line
            pass

        def _send(self, code: int, body: dict) -> None:
            if code >= 400 and "kind" not in body:   # `read_body`'s refusals say `error` and `detail`; the API, `kind`
                body = {"kind": {408: "timeout", 413: "toolarge"}.get(code, "badrequest"),
                        "error": str(body.get("detail") or body.get("error") or "")}
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            # ANSWERED IS LET GO (the product's cross-check, after the twelfth review). Kept alive, an answered
            # connection held its place at the socket until its next request's headers' deadline: a client pool of
            # sixteen idle per process, four processes of one role, and the fifth was refused `busy` for five
            # seconds. No caller of this door sends a second request on a connection (`unix_transport`, `peer_call`),
            # so none is kept — a caller that keeps its socket keeps nothing of the door's.
            self.send_header("Connection", "close")
            self.close_connection = True
            self.end_headers()
            self.wfile.write(raw)

        def _serve(self, method: str) -> None:
            try:
                # The body first, bounded and under its deadline: a 403 sent over a body left unread is a reset the
                # caller never reads the 403 from.
                if not read_body(self, MAX_BODY):
                    return                               # 400 / 413 / 408 sent, the connection closed
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n) if n else b""
                try:
                    role = role_of(self)
                except PermissionError as e:
                    return self._send(403, {"kind": "forbidden", "error": str(e)})
                try:
                    deadline = float(self.headers.get("X-Deadline") or daemon.leader_wait)
                except ValueError:
                    deadline = daemon.leader_wait
                code, body = daemon.serve(method, self.path, raw, role, deadline, peer=self.peer)
                return self._send(code, body)
            except Exception as e:                       # noqa: BLE001 — a door answers, whatever went wrong behind it
                return self._send(500, {"kind": "internal", "error": f"{type(e).__name__}: {e}"})

        def do_GET(self):
            self._serve("GET")

        def do_POST(self):
            self._serve("POST")

    return Door


# So many connections served at once, so many of them to one address; the next is refused on the spot (`busy`), and
# what it sent is not read. Mixed in before a threading server: the count is taken before a thread is made.
# The kernel's queue of connections not yet accepted is the door's bound too (`request_queue_size`, asked by `listen`
# in the server's `__init__`, so `bound` comes first): `socketserver`'s own is 5, and a unix socket whose queue is
# full refuses `connect` outright (macOS; a TCP one drops the SYN, a second's retry) — six callers at once, before
# the accepting thread woke, and the sixth was `ConnectionRefusedError`, never counted, never answered `busy`.
class _Bounded:
    daemon_threads = True
    per_address: int | None = None

    @property
    def request_queue_size(self) -> int:
        return self.limit

    def bound(self, limit: int, per_address: int | None = None) -> None:
        self.limit, self.per_address = limit, per_address
        self.count_lock = threading.Lock()
        self.serving, self.refused, self.by_addr, self.held = 0, 0, {}, {}

    def process_request(self, request, client_address):
        addr = str(client_address[0]) if isinstance(client_address, tuple) and client_address else ""
        with self.count_lock:
            room = self.serving < self.limit and (self.per_address is None
                                                  or self.by_addr.get(addr, 0) < self.per_address)
            if room:
                self.serving += 1
                self.by_addr[addr] = self.by_addr.get(addr, 0) + 1
                self.held[request] = addr
            else:
                self.refused += 1
        if not room:
            return self.busy(request)
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._give(request)
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._give(request)

    def _give(self, request) -> None:
        with self.count_lock:
            addr = self.held.pop(request, None)
            if addr is None:
                return
            self.serving -= 1
            if self.by_addr.get(addr, 1) > 1:
                self.by_addr[addr] -= 1
            else:
                self.by_addr.pop(addr, None)

    def busy(self, request) -> None:
        self.shutdown_request(request)

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], OSError):
            return                                   # a caller that hung up, or was let go at its deadline
        super().handle_error(request, client_address)


# A full role socket says so in the store's own words — `unavailable`: nothing was read, so nothing was done, and the
# handle's caller reads it as a store that did not answer (`StoreUnavailable`), never as an outcome unknown.
_BUSY_BODY = json.dumps({"kind": "unavailable", "error": f"busy: this socket serves {ROLE_CONNECTIONS} connections at "
                                                         f"once — not done, try again"}).encode()
BUSY = (b"HTTP/1.1 503 Service Unavailable\r\nContent-Type: application/json\r\nConnection: close\r\n"
        b"Content-Length: %d\r\n\r\n%s" % (len(_BUSY_BODY), _BUSY_BODY))


# The unix server class is asked for here, inside the call: `socketserver` has it only where `AF_UNIX` exists.
def _unix_server(path: str, handler, mode: int, group: str | None):
    class UnixDoor(_Bounded, socketserver.ThreadingUnixStreamServer):
        def busy(self, request) -> None:
            from .console import linger
            try:
                request.settimeout(1.0)
                request.sendall(BUSY)
            except OSError:
                return self.shutdown_request(request)
            linger.add(request)                      # its request unread: finished, not reset

        def __init__(self, path, handler):
            self.bound(ROLE_CONNECTIONS)             # before `listen`: the queue is as long as the bound
            super().__init__(path, handler)

    if os.path.exists(path):
        os.unlink(path)                              # a socket left by a daemon that was killed
    srv = UnixDoor(path, handler)
    os.chmod(path, mode)
    if group:
        try:
            import grp
            os.chown(path, -1, grp.getgrnam(group).gr_gid)
        except (ImportError, KeyError, PermissionError):
            pass                                     # a dev box without the group: the mode still holds
    return srv


class _TlsServer(_Bounded, ThreadingHTTPServer):
    """The `-api` door: the TLS handshake in the request's own thread, so one slow peer does not hold the door; so many
    connections at once, so many to one address (a full door closes the next: there is no TLS yet to answer in). Its
    context is made again when the revocation list changes (`tls.ServerContext`)."""

    def __init__(self, addr, handler, ctx: "tls.ServerContext"):
        self.ctx = ctx
        self.bound(API_CONNECTIONS, API_PER_ADDRESS)
        super().__init__(addr, handler)

    def finish_request(self, request, client_address):
        request.settimeout(DOOR_TIMEOUT)
        try:
            conn = self.ctx.get().wrap_socket(request, server_side=True)
        except (ssl.SSLError, OSError):
            return                                   # no certificate, not one of ours, revoked, or no list: no door
        try:
            self.RequestHandlerClass(conn, client_address, self)
        finally:
            try:
                conn.close()
            except OSError:
                pass


# A daemon's certificate, and the server it names — a certificate that names none (no «.» in its CN, no SAN DNS) is
# refused here, so `peer` is never "" behind this door (the review's thirteenth pass, minor: `join` with `id: ""`
# passed the check that the id is the caller's own).
def _peer_role(handler) -> str:
    handler.peer = tls.peer_server(tls.require_role(handler.connection, PEER))
    if not handler.peer:
        raise PermissionError("the peer's certificate names no server (CN <role>.<server>, or a SAN DNS)")
    return PEER


# What a join or a leave names, bounded before it is a command of the log or a voter (the review's thirteenth pass,
# major 2's sibling: `id`, `raft` and `api` went into the member rows as sent). A server's name as `w2c-ca.sh` puts it
# in a certificate; a raft address `host:port`; a leave may name a voter by its raft address (one with no row).
_SERVER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_ADDRESS = re.compile(r"^[A-Za-z0-9._:\[\]%-]{1,253}:[0-9]{1,5}$")
_API = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]{0,63}@)?[A-Za-z0-9._:\[\]%-]{1,253}:[0-9]{1,5}$")


def _membership(path: str, raw: bytes) -> tuple[str, tuple | None]:
    body = json.loads(raw or b"{}")
    if not isinstance(body, dict):
        raise ValueError("not an object")
    node_id = body.get("id")
    if path == "/v1/leave":
        if not isinstance(node_id, str) or not (_SERVER_ID.match(node_id) or _ADDRESS.match(node_id)):
            raise ValueError("id is a server's name or a voter's raft address")
        return node_id, None
    raft, api = body.get("raft"), body.get("api", "")
    if not isinstance(node_id, str) or not _SERVER_ID.match(node_id):
        raise ValueError("id is a server's name: up to 64 letters, digits, '.', '-' and '_'")
    if not isinstance(raft, str) or not _ADDRESS.match(raft):
        raise ValueError("raft is host:port")
    if not isinstance(api, str) or (api and not _API.match(api)):
        raise ValueError("api is server@host:port, or nothing")
    return node_id, (node_id, raft, api)


class StoreDaemon:
    """A backend and its doors. `sockets` is the directory of the role sockets (None: none), `api` the TCP door
    (`(host, port)`, mTLS from `tls_dir`), `rights` the rights file read."""

    def __init__(self, backend, *, node_id: str, sockets: str | None = None, rights: Rights | None = None,
                 api: tuple[str, int] | None = None, tls_dir: str | None = None, api_advertised: str = "",
                 leader_wait: float = LEADER_WAIT):
        self.backend, self.node_id = backend, node_id
        self.rights = rights or Rights()
        self.leader_wait = leader_wait
        self.servers = []
        self.sockets = sockets
        self.api_url = ""
        if sockets:
            os.makedirs(sockets, exist_ok=True)
            self._listen(_unix_server(os.path.join(sockets, "admin.sock"), _door(self, lambda h: ADMIN), 0o600, None))
            for role in sorted(self.rights.roles):
                door = _door(self, lambda h, role=role: role)
                self._listen(_unix_server(os.path.join(sockets, f"{role}.sock"), door, 0o660,
                                          socket_group(role, self.rights)))
        if api is not None:
            if not tls_dir:
                raise ValueError("the -api door is mutual TLS only: -tls <dir> (deploy/w2c-ca.sh)")
            srv = _TlsServer(api, _door(self, _peer_role), tls.ServerContext(tls_dir))
            self._listen(srv)
            host, port = srv.server_address[:2]
            self.api_url = api_advertised or f"{host}:{port}"

    def _listen(self, srv) -> None:
        self.servers.append(srv)
        threading.Thread(target=srv.serve_forever, daemon=True).start()

    def status(self) -> dict:
        return {**self.backend.status(), "api": self.api_url}

    # `role` is who the door says is calling; on the `-api` door that is `PEER`, with `peer` the server its certificate
    # names (the notes: Doors).
    def serve(self, method: str, target: str, raw: bytes, role: str, deadline: float, peer: str = "") -> tuple[int, dict]:
        path = urllib.parse.urlsplit(target).path
        if method == "GET" and path == "/v1/status":
            return 200, self.status()
        if method == "GET" and path == "/v1/rights":
            if role != ADMIN:
                return 403, {"kind": "forbidden", "error": f"{role} may not read the rights"}
            return 200, self.rights.doc()
        if method == "POST" and path in ("/v1/join", "/v1/leave"):
            if role not in (ADMIN, PEER):
                return 403, {"kind": "forbidden", "error": f"{role} may not change the group"}
            try:
                node_id, join = _membership(path, raw)
            except ValueError as e:
                return 400, {"kind": "badrequest", "error": f"{path} takes {{id, raft, api}}: {e}"}
            if role == PEER and (not peer or node_id != peer):
                return 403, {"kind": "forbidden", "error": f"the daemon of {peer or 'no server'} may change the group "
                                                           f"for its own server, not for {node_id}"}
            try:
                if join:
                    self.backend.add(*join)
                else:
                    self.backend.remove(node_id)
            except PermissionError as e:
                return 409, {"kind": "refused", "error": str(e)}
            except Unavailable as e:
                return 503, {"kind": "unavailable", "error": str(e)}
            return 200, self.status()
        if role == PEER:
            # A daemon has no right on a row, and speaks for nobody else (the notes: no daemon forwards).
            return 403, {"kind": "forbidden", "error": "a daemon may not read or write rows"}
        return answer(method, target, raw, role, self.rights,
                      lambda cmd: self.backend.submit(cmd, min(self.leader_wait, deadline)))

    def stop(self) -> None:
        for srv in self.servers:
            srv.shutdown()
            srv.server_close()
        if self.sockets:
            for f in os.listdir(self.sockets):
                if f.endswith(".sock"):
                    try:
                        os.unlink(os.path.join(self.sockets, f))
                    except OSError:
                        pass
        self.backend.stop()


# -- between daemons -------------------------------------------------------------------------------------
class _PeerConnection(http.client.HTTPSConnection):
    """HTTPS to another daemon's `-api`: its certificate checked against the CA, against the server we meant
    (`server@host:port`), and for the role `configstore`."""

    def __init__(self, address: str, tls_dir: str, timeout: float):
        self.peer_name, host, port = tls.split_address(address)
        super().__init__(host, port, timeout=timeout, context=tls.client_context(tls_dir))

    def connect(self):
        import socket
        raw = socket.create_connection((self.host, self.port), self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.peer_name)
        tls.require_role(self.sock, PEER)


def peer_call(address: str, tls_dir: str, method: str, route: str, body: dict | None = None,
              timeout: float = JOIN_WAIT + 5) -> dict:
    conn = _PeerConnection(address, tls_dir, timeout)
    try:
        conn.request(method, route, body=None if body is None else json.dumps(body).encode(),
                     headers={"Content-Type": "application/json"})
        r = conn.getresponse()
        said = json.loads(r.read() or b"{}")
        if r.status != 200:
            raise OSError(f"{address} {route}: {r.status} {said.get('kind', '')} {said.get('error', '')}".strip())
        return said
    finally:
        conn.close()


# -- starting a member -----------------------------------------------------------------------------------
def _wait_leader(backend: RaftBackend, within: float = 30.0) -> None:
    end = time.monotonic() + within
    while True:
        try:
            backend.submit({"op": "get", "key": "configstore/ready"}, 1.0)
            return
        except Unavailable:
            if time.monotonic() > end:
                raise


def start_member(node_id: str, data: str, raft: str, *, bootstrap: bool = False, join: str | None = None,
                 tls_dir: str | None = None, tuning: str | dict = "default", index_base: int = 0,
                 api_advertised: str = "", leader_wait: float = LEADER_WAIT) -> RaftBackend:
    """The backend of a member: from its journal when `data` holds one; else a new group of one (`bootstrap`) or a
    new member of the group a member's door (`join`) belongs to."""
    # Without `-tls` there is no secret, and `RaftBackend` takes no partner and listens on loopback only, by its socket
    # (the review's twelfth pass, blocker 1) — a join is refused here, before anything is asked of a member.
    password = tls.raft_secret(tls_dir) if tls_dir else None
    if tls_dir:
        # The bundle whole before the member runs: one CA, its list, our certificate — the store's role alone (the
        # product's cross-check: a certificate of configstore and another role does not start a daemon).
        tls.client_context(tls_dir)
    if password is None and join and not RaftBackend.has_state(data):
        raise ValueError(f"{NO_SECRET}; -join makes a group of more")
    if RaftBackend.has_state(data):
        doc = RaftBackend.member_doc(data)
        partners = list(doc.get("partners") or [])
        if not partners and doc.get("how") != "bootstrap" and not doc.get("alone"):
            partners = _rejoin(node_id, raft, data, join, tls_dir)
        b = RaftBackend(node_id, raft, partners, data, tuning, password, leader_wait)
        b.resumed(doc, partners)
        return b
    if bootstrap == bool(join):
        raise ValueError("an empty -dir needs -bootstrap (a new group of one) or -join <a member's api>")
    RaftBackend.forget_failed_start(data)
    if bootstrap:
        b = RaftBackend(node_id, raft, [], data, tuning, password, leader_wait)
        try:
            _wait_leader(b)
            got = b.submit({"op": "base", "base": index_base}, 10.0)
            if "refused" in got:
                raise ValueError(got["refused"])
            b.submit({"op": "member", "id": node_id, "raft": raft, "api": api_advertised}, 10.0)
        except BaseException:
            b.stop()
            raise
        b.became_member("bootstrap", [])
        return b
    if not tls_dir:
        raise ValueError("-join speaks to a member's -api door, which is mutual TLS: -tls <dir>")
    members = peer_call(join, tls_dir, "GET", "/v1/status", timeout=10.0)["members"]
    partners = _others((m["raft"] for m in members), raft)
    b = RaftBackend(node_id, raft, partners, data, tuning, password, leader_wait)
    end = time.monotonic() + JOIN_WAIT
    while True:
        try:
            said = peer_call(join, tls_dir, "POST", "/v1/join", {"id": node_id, "raft": raft, "api": api_advertised})
            # The members the group named when it took this daemon, with the partners it started with: written with
            # the membership itself (the notes: A group).
            b.became_member("join", partners + [m["raft"] for m in said.get("members", []) if m.get("raft")])
            return b
        except (OSError, http.client.HTTPException, ValueError):
            if time.monotonic() > end:
                b.stop()
                RaftBackend.forget_failed_start(data)
                raise
            time.sleep(0.2)


# A member that joined and knows no partner — a `member.json` from before the partners were kept with it — never
# starts as a group of one: its `-join` door says who the group is, and the group must still count this daemon;
# otherwise it does not start, and says what to do (systemd tries again: the daemon waits for its group).
def _rejoin(node_id: str, raft: str, data: str, join: str | None, tls_dir: str | None) -> list[str]:
    stay = (f"{node_id} was taken into a group and knows none of its members ({data}/member.json): it does not start "
            f"as a group of one beside it")
    if not join or not tls_dir:
        raise ValueError(f"{stay} — start it with -join <a member's api> to ask the group, or, if the group no "
                         f"longer counts it, empty {data} and join again")
    members = peer_call(join, tls_dir, "GET", "/v1/status", timeout=10.0)["members"]
    if not any(m.get("id") == node_id or m.get("raft") == raft for m in members):
        raise ValueError(f"{stay}, and the group at {join} does not count it: empty {data} and join again")
    return _others((m.get("raft") for m in members), raft)


# -- loading rows into a fresh group: import, restore ----------------------------------------------------
def _load_fresh(rows: list[tuple[str, dict]], highest: int, dst, what: str) -> dict:
    """Write `rows` into the group behind `dst` (an admin handle), each created with `cas=0`, values untouched.
    Refused whole, before the first write, when a row is heavier than the store takes, when the group's base is below
    `highest`, or when the group holds a row this load did not write — a row that is one of `rows`, the same, is one
    an earlier run of the same load wrote before it stopped, and the load goes on after it (twelfth pass, minor)."""
    heavy = [f"{k} ({items_bytes(v)} bytes)" for k, v in rows if items_bytes(v) > MAX_VALUE]
    if heavy:
        raise ValueError(f"rows heavier than the store takes ({MAX_VALUE} bytes) — move what makes them big into an "
                         f"object first: " + "; ".join(heavy))
    status = dst.status()
    base = int(status.get("index_base", 0))
    if base < highest:
        raise ValueError(f"the group's base is {base} and {what} handed out versions up to {highest}: start the group "
                         f"with -index-base {highest} or more, or a version remembered from {what} could match a new row")
    want = dict(rows)
    held = set(dst.list(""))
    alien = sorted(k for k in held if k not in want or dst.get(k)[0] != want[k])
    if alien:
        raise ValueError(f"the group holds rows this load did not write ({', '.join(alien[:5])}"
                         f"{', …' if len(alien) > 5 else ''}): rows are loaded into a fresh group only")
    for key, items in rows:
        if key not in held:
            dst.put(key, items, cas=0)
    return {"rows": len(rows), "highest_before": highest, "index_base": base, "there_before": len(held)}


def import_rows(src_url: str, dst) -> dict:
    """A box's `file://` rows into a fresh group (`configstore import`); a row of the file that does not read
    refuses the whole import — dropped, it would read as absent, and an absent epoch starts again from 1."""
    from .variables import FileVariables, Garbled, open_vars
    src = open_vars(src_url)
    if not isinstance(src, FileVariables):
        raise ValueError(f"import reads a box's file:// store, not {src_url}")
    try:
        with open(src.index_file) as f:
            counter = int(f.read().strip())
    except FileNotFoundError:
        counter = 0
    rows, torn = [], []
    for key in src.list(""):
        try:
            items, _ = src.get(key)
        except Garbled as e:
            torn.append(f"{key} ({e})")
            continue
        if items is not None:
            rows.append((key, items))
    if torn:
        raise ValueError("rows that do not read — fix or remove them first: " + "; ".join(torn))
    return _load_fresh(rows, counter, dst, "the file")


def backup_rows(src) -> dict:
    """Every row through an admin handle, and the highest version the group could have handed out by the end —
    not one moment's picture while processes write; a quiet group's whole state when they do not."""
    rows = {}
    for key in src.list(""):
        items, index = src.get(key)
        if items is not None:
            rows[key] = {"items": items, "index": index}
    s = src.status()
    highest = max([int(s.get("index_base", 0)) + int(s.get("applied", 0))] + [r["index"] for r in rows.values()])
    return {"configstore_backup": 1, "highest": highest, "rows": rows}


def restore_rows(backup: dict, dst) -> dict:
    """A backup into a fresh group (`configstore restore`), its base above the backup's highest version."""
    if not isinstance(backup, dict) or backup.get("configstore_backup") != 1:
        raise ValueError("not a configstore backup")
    rows = [(k, dict(r["items"])) for k, r in sorted(backup["rows"].items())]
    return _load_fresh(rows, int(backup["highest"]), dst, "the backup")


# -- the command line ------------------------------------------------------------------------------------
def _serve_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="python3 -m w2cplatform.configstore", description="the cluster's config store daemon")
    ap.add_argument("-id", required=True, help="this server's name")
    ap.add_argument("-dir", default=DATA, help=f"journal, dump, member.json (default {DATA})")
    ap.add_argument("-raft", required=True, help="this member's raft address, host:port")
    ap.add_argument("-api", help="the other daemons' door, host:port (mutual TLS)")
    ap.add_argument("-advertise", help="the -api address the others dial, server@host:port (default id@-api)")
    ap.add_argument("-sockets", default=SOCKETS, help=f"the role sockets' directory (default {SOCKETS})")
    ap.add_argument("-rights", help=f"the rights file ({RIGHTS_FILE}); none: admin.sock only")
    ap.add_argument("-tls", help=f"the TLS directory (default {tls.TLS_DIR} when -api or -join is given)")
    ap.add_argument("-tuning", default="default", choices=sorted(TUNINGS))
    ap.add_argument("-index-base", type=int, default=0, help="versions start above this (an import's highest)")
    ap.add_argument("-leader-wait", type=float, default=LEADER_WAIT, help="seconds a command waits for a leader")
    how = ap.add_mutually_exclusive_group()
    how.add_argument("-bootstrap", action="store_true", help="a new group of one")
    how.add_argument("-join", help="a member's -api, server@host:port: become a member of its group")
    return ap.parse_args(argv)


# The operator's commands: each one request to this server's `admin.sock` (root's), or a file read.
COMMANDS = ("status", "join", "leave", "rights", "backup", "restore", "import")


def _command(argv: list[str]) -> int:
    from .variables import open_vars
    verb = argv[0]
    ap = argparse.ArgumentParser(prog=f"python3 -m w2cplatform.configstore {verb}")
    ap.add_argument("--socket", "-socket", default=ADMIN_URL, help=f"this server's admin socket ({ADMIN_URL})")
    if verb == "join":
        ap.add_argument("id")
        ap.add_argument("raft", help="the new member's raft address, host:port — its daemon already running")
        ap.add_argument("api", nargs="?", default="", help="its -api, server@host:port")
    elif verb == "leave":
        ap.add_argument("id")
    elif verb == "rights":
        ap.add_argument("file", nargs="?", help="check this file instead of asking the daemon")
    elif verb in ("restore", "import"):
        ap.add_argument("--from", "-from", dest="src", required=True,
                        help="a backup's file" if verb == "restore" else "file:///data/platform/config")
    a = ap.parse_args(argv[1:])
    if verb == "rights" and a.file:
        out = Rights.load(a.file).doc()
    else:
        h = open_vars(a.socket)
        if verb == "status":
            out = h.status()
        elif verb == "join":
            out = h._call("POST", "/v1/join", {"id": a.id, "raft": a.raft, "api": a.api})
        elif verb == "leave":
            out = h._call("POST", "/v1/leave", {"id": a.id})
        elif verb == "rights":
            out = h._call("GET", "/v1/rights")
        elif verb == "backup":
            out = backup_rows(h)
        elif verb == "restore":
            with open(a.src, encoding="utf-8") as f:
                out = restore_rows(json.load(f), h)
        else:
            out = import_rows(a.src, h)
    print(json.dumps(out, indent=1 if verb in ("status", "rights", "backup") else None), flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] and argv[0] in COMMANDS:
        return _command(argv)
    a = _serve_args(argv)
    rights = Rights.load(a.rights) if a.rights else Rights()
    tls_dir = a.tls or (tls.TLS_DIR if a.api or a.join else None)
    api = None
    if a.api:
        host, port = a.api.rsplit(":", 1)
        api = (host, int(port))
    advertised = a.advertise or (f"{a.id}@{a.api}" if a.api else "")
    backend = start_member(a.id, a.dir, a.raft, bootstrap=a.bootstrap, join=a.join, tls_dir=tls_dir, tuning=a.tuning,
                           index_base=a.index_base, api_advertised=advertised, leader_wait=a.leader_wait)
    daemon = StoreDaemon(backend, node_id=a.id, sockets=a.sockets, rights=rights, api=api, tls_dir=tls_dir,
                         api_advertised=advertised, leader_wait=a.leader_wait)
    print(json.dumps({"serving": a.sockets, "raft": a.raft, "api": daemon.api_url}), flush=True)
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
    daemon.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
