"""The stand of the camera–office–centre notes: the platform's first MVP configuration, run on the course's code.

    srv        the centre: holds the domain — the signer (`signer_service`), the domain's console, the holder's own
               agent, the VMS's worker on the domain (`vms.domainpart`) with the signer's token socket — and a recorder
               of its own with an ingest (`r-srv-1`), for the copy of an important camera and for the viewer
    relay-a    office A: a recorder with an ingest and the forwarder (`r-relay-a-1`), the volume `disk`, the agent with
               the relay's door; behind it the cameras cam-a (SN-A) and cam-a2 (SN-A2)
    relay-b    office B: the same; behind it cam-b (SN-B)
    relay-b2   a backup office, only in one failure scene: SN-A as `when: offline` on its `backup` volume
    cam-*      a camera with the platform's firmware: a cluster of one (`DeviceCluster`) on its flash, its card a volume
               `card` of `kind: edge`, the recording `1-sd` on it, a pusher, an agent that reaches only its office

Names as the product's nightly stand has them (`vmssubsystem/scripts/nightly/stand.sh`). Each server cluster is the
cluster stand's `Cluster` (`tests/cluster/conftest.py`) — the configstore's state machine behind a door per role with
the committed rights file, a resource with its objects — of ONE server named as the cluster, on one wall clock, its
store's index from its own base (srv 1000, relay-a 2000, relay-b 3000, relay-b2 7000). A camera's flash is a
`FakeVariables` from its own base (cam-a 4000, cam-a2 5000, cam-b 6000).

Every process is built as its entry point builds it (`signer_service.main`, `console.main`, `agent.main`,
`vms.domainpart.worker.main`), with the stand's stores instead of the sockets the environment would name, and its doors
opened on loopback (`open_doors`) — real HTTP. Nothing runs in the background: each pass is called by the scenario, so a
trace reads the same on every run. Where the course has no wire — the camera and the office's ingest, the office's
forwarder and the centre's ingest, a member's report into the objects of the holder or of its relay — the call is made in
this process and printed as the product's request, marked (`tracing.TracedIngest`, `RemoteObjects`).
"""
from __future__ import annotations

from tests.member_console import device_console, admit_fixtures
import json
import os
import tempfile

from .tracing import Log, TracedIngest, TracedVars, Wall, XCall, deterministic, served_as, trace_http

DOMAIN = "acme"
CLUSTERS = {   # name: (labels = REACHES, index base)
    "srv": ("vlan:centre", 1000),
    "relay-a": ("vlan:site-a,vlan:uplink", 2000),
    "relay-b": ("vlan:site-b,vlan:uplink", 3000),
    "relay-b2": ("vlan:site-b,vlan:site-a,vlan:uplink", 7000),
}
CAMERAS = {    # name: (serial, office, REACHES, flash index base)
    "cam-a": ("SN-A", "relay-a", "vlan:site-a", 4000),
    "cam-a2": ("SN-A2", "relay-a", "vlan:site-a", 5000),
    "cam-b": ("SN-B", "relay-b", "lte:cam-b", 6000),
}
# What each camera raises and can be asked to do — `can` in its heartbeat (М10B Lesson 25; the firmware's own description
# in the product): cam-a2 at the gate sees vehicles, cam-b on site B turns to presets
CAN = {
    "cam-a": {"events": ["motion"]},
    "cam-a2": {"events": ["motion", "vehicle"]},
    "cam-b": {"events": ["motion"], "ptz": True, "presets": 8},
}
# The camera's ring, where it is smaller than the course's default (`card.RING_BYTES`): cam-a2 is a camera with little
# memory — its ring holds some twenty seconds of its stream, short of what its card needs (`card.prebuffer.short`)
RING_BYTES = {"cam-a2": 50_000}
TOPOLOGY = {"centre": "srv", "star": [], "via": {"cam-a": "relay-a", "cam-a2": "relay-a", "cam-b": "relay-b"}}
# the stand's ports, as the product's stand counts them before its OFFSET: what a trace prints instead of loopback's
PORTS = {"signer": 8071, "domain console": 8070, "console": 8080, "relay door": 8446, "recorder": 8091}


class Remote:
    """What a process reaches in ANOTHER box's objects with no wire in the course — a camera's report into its office's
    (`RELAY_OBJECTS_URL`; an office's report goes through the holder's door, `POST /api/member`): the store's own calls,
    made in this process, each recorded (kind `objects`) and marked with the product's request for the same thing."""

    def __init__(self, log: Log, inner, who: str, door: str, product: str, writes_only: bool = True, site=None,
                 box: str = ""):
        self.log, self.inner, self.who, self.door, self.product = log, inner, who, door, product
        self.writes_only, self.site, self.box = writes_only, site, box

    def _reach(self, method: str, key: str) -> None:
        """A box that is off, or a road that is cut, takes no call — as its wire, in the product, would not."""
        from w2cplatform.domain.federation import Unreachable
        here = Site.box_of(self.who)
        if self.site is None:
            return
        why = (f"{self.box} is off" if self.box in self.site.down else f"{here} is off" if here in self.site.down else
               f"the road {here} — {self.box} is cut" if (here, self.box) in self.site.cut else None)
        if why:
            self.log.add(XCall(self.who, self.door, method, f"/{key}", None, 0, f"no answer: {why}", kind="objects",
                               note=f"в курсе — запись в чужое хранилище объектов в процессе, провода нет; {self.product}"))
            raise Unreachable(f"{self.door}: {why}")

    def _rec(self, method, key, status, answer=None):
        if self.writes_only and method in ("GET", "LIST"):
            return
        self.log.add(XCall(self.who, self.door, method, f"/{key}", None, status, answer, kind="objects",
                           note=f"в курсе — запись в чужое хранилище объектов в процессе, провода нет; {self.product}"))

    def put(self, key, data):
        self._reach("PUT", key)
        self.inner.put(key, data)
        self._rec("PUT", key, 200, _object_shown(data))

    def get(self, key):
        self._reach("GET", key)
        got = self.inner.get(key)
        self._rec("GET", key, 200 if got is not None else 404)
        return got

    def list(self, prefix):
        self._reach("LIST", prefix)
        got = self.inner.list(prefix)
        self._rec("LIST", prefix, 200, got)
        return got

    def delete(self, key):
        self._reach("DELETE", key)
        got = self.inner.delete(key)
        self._rec("DELETE", key, 200)
        return got


def _object_shown(data: bytes):
    try:
        v = json.loads(data)
    except ValueError:
        return {"bytes": len(data)}
    return v


class Site:
    """The whole stand: the clusters, the cameras, the domain's processes, the offices, the people — built by the scenes
    in their order, each piece when its scene needs it."""

    def __init__(self, seed: int = 7):
        self.wall = deterministic(seed)
        from tests.cluster.conftest import Clock
        self.clock = Clock(1000.0)
        self.wall.followers.append(self.clock)              # the processes' monotonic clock moves with the wall
        self.tmp = tempfile.mkdtemp(prefix="coc-")
        self.log = Log(roots={self.tmp: "/data"})
        trace_http(self.log)
        self.clusters: dict = {}
        self.cams: dict = {}
        self.doors: dict[str, str] = {}             # what a door is called → its real base URL on loopback
        self.servers: dict = {}                     # …its server
        self.who_at: dict[str, str] = {}            # …and who its requests are made as
        self.agents: dict = {}
        self.auto_workers: dict = {}
        self.recorders: dict = {}
        self.consoles: dict = {}
        self.ingests: dict = {}                     # cluster → its recorder's Ingest
        self.down: set[str] = set()                 # clusters switched off (a failure scene)
        self.cut: set[tuple[str, str]] = set()      # roads cut: (from, to)
        for name in ("srv", "relay-a", "relay-b"):
            self.cluster(name)
        self.log.blocked = self.blocked

    # -- the server clusters -----------------------------------------------------------------------------------------
    def cluster(self, name: str):
        if name in self.clusters:
            return self.clusters[name]
        from .clusters import StandCluster
        labels, base = CLUSTERS[name]
        c = StandCluster(name, labels, self.log, base, self.clock, self.wall, os.path.join(self.tmp, name))
        self.clusters[name] = c
        with self.log.muted():
            c.resources_up()
        return c

    def url(self, door: str) -> str:
        return self.doors[door]

    def serve(self, door: str, shown: str, handler=None, who: str | None = None) -> str:
        """A door opened on loopback as the platform opens one (`open_doors`), its requests made as `who`, printed as
        `shown` (`srv:8071`); `handler` now, or later (`bind`) — a door's address is said in what its process is built
        with. Returns the base URL."""
        from http.server import BaseHTTPRequestHandler
        from w2cplatform.console import open_doors
        srv = open_doors("127.0.0.1", 0, BaseHTTPRequestHandler, unix_env="COC_NO_UNIX", say=False)
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        self.log.hosts[f"127.0.0.1:{srv.server_address[1]}"] = shown
        self.log.roots[base] = f"http://{shown}"
        self.doors[door], self.servers[door], self.who_at[door] = base, srv, who or door
        if handler is not None:
            self.bind(door, handler)
        return base

    def bind(self, door: str, handler) -> None:
        self.servers[door].RequestHandlerClass = served_as(self.log, self.who_at[door], handler)

    # -- failures: a box off, a road cut ----------------------------------------------------------------------------------
    @staticmethod
    def box_of(who: str) -> str:
        """The box a process runs on, by its trace name (`… on relay-a`, `pusher on cam-a`, `anna` — a person's own)."""
        if " on " in who:
            return who.rsplit(" on ", 1)[1].split(" ")[0]
        return who

    def blocked(self, who: str, url: str) -> str | None:
        """Why a request from `who` to `url` does not get through: the box at either end is off, or the road between is
        cut. People reach the domain's doors from anywhere the centre is up."""
        from urllib.parse import urlsplit
        shown = self.log.hosts.get(urlsplit(url).netloc, "")
        there = shown.split(":")[0]
        here = self.box_of(who)
        if there in self.down:
            return f"{there} is off"
        if here in self.down:
            return f"{here} is off"
        if (here, there) in self.cut or (there, here) in self.cut:
            return f"the road {here} — {there} is cut"
        return None

    def off(self, name: str) -> None:
        self.down.add(name)

    def on(self, name: str) -> None:
        self.down.discard(name)

    def cut_road(self, a: str, b: str) -> None:
        self.cut |= {(a, b), (b, a)}

    def mend_road(self, a: str, b: str) -> None:
        self.cut -= {(a, b), (b, a)}

    def tick(self, seconds: float, step: float = 5.0, cams=("cam-a", "cam-a2", "cam-b"), offices=("relay-a", "relay-b"),
             agents_every: float = 30.0, domain_every: float = 5.0) -> None:
        """Time passing on the whole stand, every process that is on doing its passes: the cameras every `step` (their
        sensor, pusher, card), the offices' recorders and forwarders, the agents every `agents_every`, the holder's
        passes every `domain_every`. What a scene shows of it is the scene's to choose: this is usually muted."""
        end = self.wall() + seconds
        while self.wall() < end - 1e-9:
            self.wall.advance(min(step, end - self.wall()))
            now = self.wall()
            for c in cams:
                if c in self.cams and c not in self.down and getattr(self.cams[c], "pusher", None) is not None:
                    self.camera_step(c)
            for o in offices:
                if o in self.recorders and o not in self.down:
                    self.rec_pass(o)
                    if self.recorders[o].forwarder is not None and "srv" in self.recorders:
                        self.forward(o)
            if "srv" in self.recorders and "srv" not in self.down:
                self.rec_pass("srv")
            if now - getattr(self, "_agents_at", -1e18) >= agents_every:
                self._agents_at = now
                for n in [a for a in self.agents if a not in self.down]:
                    if n.startswith("relay"):
                        self.sync(n)
                for n in [a for a in self.agents if a not in self.down and a.startswith("cam")]:
                    self.sync(n)
                for n in [a for a in self.agents if a not in self.down and not a.startswith("cam")]:
                    self.sync(n)
            if "srv" not in self.down and now - getattr(self, "_domain_at", -1e18) >= domain_every:
                self._domain_at = now
                self.domain_pass()

    # -- rings ----------------------------------------------------------------------------------------------------------
    def ring(self, name: str):
        """`SECRETS_KEY` of cluster `name`: its ring (`w2cctl secrets new`), made once, outside every store."""
        from w2cplatform.sealing import Sealer, new_key_file
        path = os.path.join(self.tmp, "secrets", f"{name}.key")
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            new_key_file(path)
        return Sealer.from_file(path)

    # -- the domain, scene 1 --------------------------------------------------------------------------------------------
    def clusters_line(self) -> str:
        """`CLUSTERS` as the units on srv read it: srv itself, the offices by their consoles — read from their reports. The
        cameras are not in it: they have no console anybody reaches, and they join by the list of members."""
        offices = [n for n in ("relay-a", "relay-b", "relay-b2") if n in self.clusters]
        return ",".join(["srv", *[f"{n}=http://{n}:{PORTS['console']}" for n in offices]])

    def federation(self, vars_, objects, box: str = "srv"):
        """`runtime.federation_from_env` over the stand: srv by the process's own store (guarded, as every domain process
        opens it), every other cluster read from its reports in the holder's objects (`member_copy`)."""
        from w2cplatform.domain.declared import guarded
        from w2cplatform.domain.federation import Cluster, Federation
        from w2cplatform.domain.uplink import member_copy
        fed = Federation()
        fed.add(Cluster(box, guarded(vars_), objects, is_domain_holder=True))
        for n in [n for n in ("srv", "relay-a", "relay-b", "relay-b2") if n in self.clusters and n != box]:
            fed.add(member_copy(n, objects, lost_after=45.0, wall=self.wall))
        return fed

    def install(self) -> None:
        """The installer on srv before the first start (Lesson 15, step 9): the domain's root made OFF the holder, its
        recovery file handed to the operator — the course has no command for it: `DomainRoot(...).recovery()`, as the
        product's `domain install --recovery` writes it. The signer's first start with `RECOVERY_FILE` founds the domain
        (`signer_service.first_signer`: the key set and the record of term 1, signed by the root)."""
        from w2cplatform.trust.signer import DomainRoot
        root = DomainRoot(DOMAIN, now=self.wall)
        self.recovery = os.path.join(self.tmp, "recovery", f"{DOMAIN}.recovery")
        os.makedirs(os.path.dirname(self.recovery), exist_ok=True)
        with open(self.recovery, "wb") as f:
            f.write(root.recovery())

    def first_admin(self, who: str = "anna", password: str = "anna-test-password") -> None:
        """The installer's first person and her grant on the domain: the people's door is the signer's and asks for an
        admin, so the first admin is the installer's (the product's `domain user add`, `domain grant`)."""
        from w2cplatform.domain.grants import Grant, set_domain_grants
        from w2cplatform.domain.identity import IdentityStore
        from w2cplatform.trust.signer import Signer
        srv = self.cluster("srv")
        v = srv.door("domain", "operator on srv")
        signer = Signer(DOMAIN, v, sealer=self.ring("srv"))
        # Name exclusivity needs an actual collected generation before the first
        # operator write. Configured but never reporting peers remain missing
        # through the ordinary report grace; no name index is seeded by the stand.
        from vms.config import SPEC
        from w2cplatform.spec import SpecController
        agent = self.holder_agent()
        SpecController(SPEC, agent.cluster_vars, agent.published,
                       wall=self.wall, cluster="srv").publish_snapshot()
        self.sync("srv")
        self.holder.run_pass()
        self.wall.advance(46)
        self.holder.run_pass()
        IdentityStore(signer, v, srv.objects_on("srv", v), sealer=self.ring("srv"), now=self.wall).create_local(
            who, password, [], by="operator")
        set_domain_grants(v, [Grant(who, "admin", None, 0.0)], self.wall(), by="operator")
        self.passwords = {who: password}

    def start_signer(self, box: str = "srv") -> None:
        """`signer_service.main` on srv: its store by the role `domain`, its secrets sealed at start, the identity set, the
        holder's pass given CLUSTERS (`holder_pass`), its door, and the token socket for the VMS's worker."""
        from w2cplatform.console import UnixConsoleServer
        from w2cplatform.domain import declared, tokendoor
        from w2cplatform.domain.agent import DomainPublisher
        from w2cplatform.domain.carry import HolderDoor
        from w2cplatform.domain.identity import IdentityStore
        from w2cplatform.domain.signer_service import Holder, first_signer, holder_pass, revocations
        from w2cplatform.journal import Journal
        from w2cplatform.trust.signer import Signer
        from w2cplatform.trust.tokens import DeclaredIssuer
        from w2cplatform.w2cctl import DOMAIN_PREFIXES, seal as seal_stored
        import threading
        srv = self.cluster(box)
        who = f"signer on {box}"
        vars_ = srv.door("domain", who)
        sealer = self.ring(box)
        seal_stored(vars_, sealer, DOMAIN_PREFIXES)
        objects = srv.objects_on(box, vars_, who)
        pub = DomainPublisher(vars_)
        env = {"CLUSTERS": self.clusters_line(), "CLUSTER": box,
               **({"RECOVERY_FILE": self.recovery, "DOMAIN_HOLDER": "srv"} if box == "srv" else {})}
        signer = first_signer(vars_, DOMAIN, sealer, pub, env)
        journal = Journal(srv.server.resource, "domain", self.wall)
        ids = IdentityStore(signer, vars_, objects, publish_floor=60.0, sealer=sealer, journal=journal, now=self.wall)
        # the door first: the holder's record says where the signer answers, and the agents carry through it
        sfx = "" if box == "srv" else f" {box}"            # a member that may take the domain runs them too (ADR-0066)
        signer_url = self.serve("signer" + sfx, f"{box}:{PORTS['signer']}", who=who)
        console_url = self.serve("domain console" + sfx, f"{box}:{PORTS['domain console']}", who=f"domain console on {box}")
        holder = Holder(vars_, objects, signer, sealer=sealer, ids=ids, revoked=revocations(vars_), pub=pub,
                        carry_door=HolderDoor(vars_, objects, sealer, wall=self.wall), journal=journal,
                        console_url=console_url, signer_url=signer_url, wall=self.wall)
        self._holder_pass(holder, signer, vars_, objects, box)
        self.bind("signer" + sfx, holder.handler())
        self.signers = {**getattr(self, "signers", {}), box: holder}
        if box != "srv":
            return holder
        self.holder, self.signer_url, self.domain_console_url = holder, signer_url, console_url
        path = os.path.join(tempfile.mkdtemp(prefix="sig-"), "tokens.sock")

        class Current:                                   # the key the holder signs with NOW: a move here changes it
            def __getattr__(self, name):
                return getattr(holder.signer.tokens, name)
        tokens_door = UnixConsoleServer(path, served_as(self.log, f"signer on {box}",
                                                         tokendoor.handler(DeclaredIssuer(Current(), declared.token_kinds()))),
                                        self.servers["signer"].bounds)
        threading.Thread(target=tokens_door.serve_forever, daemon=True).start()
        self.tokens_socket = path

    def _holder_pass(self, holder, signer, vars_, objects, box: str = "srv") -> None:
        """`signer_service.holder_pass`, with the stand's federation instead of `federation_from_env`."""
        from w2cplatform.domain.alarms import AlarmHistory, DomainAlarms, reported_doors
        from w2cplatform.domain.members import Members
        from w2cplatform.domain.pending import PendingEdits
        from w2cplatform.domain.readview import ReadView
        from w2cplatform.domain.signer_service import move_by_handover, term_of
        from w2cplatform.domain.topology import Topology
        from w2cplatform.domain.uplink import _CopyObjects
        fed = self.federation(vars_, objects, box)
        holder.consoles = {n: self.doors[f"console {n}"] for n in fed.clusters
                           if n != box and f"console {n}" in self.doors} or None      # CLUSTERS' consoles, where a move reads
        configured = [n for n, c in fed.clusters.items() if isinstance(c.objects, _CopyObjects)]
        hv, ho = fed.domain_holder.vars, fed.domain_holder.objects
        holder.fed, holder.view = fed, ReadView(fed, lost_after=45.0, wall=self.wall)
        holder.members = Members(hv, wall=self.wall, configured=lambda: configured, domain=box)
        holder.topology, holder.pending = Topology(hv), PendingEdits(hv, self.wall)
        holder.alarms = DomainAlarms(fed, reported_doors(fed, ho, 45.0), lost_after=45.0, history=AlarmHistory(ho))
        # The local agent owns its member key before the signer claims its term.
        # Settle configured external members first, so claim adds the holder as
        # how:holder rather than encountering an unkeyed configuration row.
        from w2cplatform.trust.memberkey import MemberKey
        own = self.cluster(box).door("domainagent", f"domainagent on {box}")
        MemberKey.load_or_make(own, self.ring(box))
        holder.members.settle()
        holder.term = term_of(fed, signer, ho, holder.signer_url)
        if holder.term is not None:
            assert holder.members.read()["members"][box]["how"] == "holder"
        if holder.term is not None and not signer.chain:
            holder.hand_to = lambda to: move_by_handover(holder, to, DOMAIN, signer)

    def start_domain_console(self, box: str = "srv") -> None:
        """`console.main` on srv: the people's door, no key; its store by the role `domainconsole`. Its read pass is not a
        thread here (`Console.serve` starts one): the scenario runs it (`console_pass`)."""
        from w2cplatform.domain.agent import ClusterTrust, Untrusted
        from w2cplatform.domain.alarms import AlarmHistory, DomainAlarms, reported_doors
        from w2cplatform.domain.api import ApiError, ConsoleAPI
        from w2cplatform.domain.console import Console
        from w2cplatform.domain.federation import DomainDirectory, Unreachable
        from w2cplatform.domain.grants import domain_may
        from w2cplatform.domain.members import Members
        from w2cplatform.domain.pending import PendingEdits
        from w2cplatform.domain.readview import ReadView
        from w2cplatform.domain.topology import Topology
        from w2cplatform.domain.uplink import _CopyObjects
        from w2cplatform.journal import Journal
        from w2cplatform.trust.tokens import PERSON, verify
        srv = self.cluster(box)
        who = f"domain console on {box}"
        v = srv.door("domainconsole", who)
        fed = self.federation(v, srv.objects_on(box, v, who), box)
        directory = DomainDirectory(fed, wall=self.wall)
        view = ReadView(fed, lost_after=45.0, wall=self.wall)
        trust = ClusterTrust(fed.domain_holder.vars)

        def person(token: str) -> dict:
            try:
                ks, revoked = trust.keyset(), trust.revoked()
            except Untrusted as e:
                raise ApiError(503, f"nobody can be checked: {e}") from None
            if ks is None:
                raise ApiError(503, "no signer key set in this cluster yet (is the domain agent running?)")
            return verify(token, ks, revoked, kind=PERSON)

        def consoles(cluster: str):
            raise Unreachable(f"{cluster} is reached only by its own agent; the edit waits for its next pass")
        pending = PendingEdits(fed.domain_holder.vars, self.wall)
        api = ConsoleAPI(directory, verifier=lambda t: person(t)["sub"], pending=pending,
                         last_known=view.last_known)
        hv, ho = fed.domain_holder.vars, fed.domain_holder.objects
        configured = [n for n, c in fed.clusters.items() if isinstance(c.objects, _CopyObjects)]
        journal = Journal(srv.server.resource, "domainconsole", self.wall)
        members = Members(hv, wall=self.wall, configured=lambda: configured, domain=box, journal=journal)
        alarms = DomainAlarms(fed, reported_doors(fed, ho, 45.0, wall=self.wall), lost_after=45.0,
                              history=AlarmHistory(ho, wall=self.wall), wall=self.wall)
        console = Console(directory, view, api, refresh_interval=5.0, holder_objects=ho, holder_vars=hv,
                               pending=pending, topology=Topology(hv), members=members,
                               admin=lambda s: domain_may(hv, s, "admin", self.wall()),
                               viewer=lambda s: domain_may(hv, s, "view", self.wall()),
                               signer_url=self.signers[box].signer_url, alarms=alarms, journal=journal, person=person)
        sfx = "" if box == "srv" else f" {box}"
        self.bind("domain console" + sfx, console.handler())
        self.domain_consoles = {**getattr(self, "domain_consoles", {}), box: console}
        if box == "srv":
            self.console = console

    def console_pass(self) -> None:
        """One pass of the domain console's reader (`Console._refresher`): the members, the topology, the read view."""
        c = self.console
        c._steps(("following the members", c._follow_members), ("following the topology", c._follow_topology),
                 ("the read view's pass", c.view.refresh))

    def start_domainpart(self) -> None:
        """`vms.domainpart.worker.main` on srv: the VMS's books, by the role `camdomain`, its tokens asked of the signer's
        socket (`TokenDoor`) — the key stays the signer's."""
        from w2cplatform.configstorevars import unix_transport
        from w2cplatform.domain.members import Members
        from w2cplatform.domain.readview import ReadView
        from w2cplatform.domain.topology import Topology
        from w2cplatform.domain.uplink import _CopyObjects
        from vms.domainpart.books import Books
        from vms.domainpart.inputs import BookInputs
        from vms.domainpart.worker import DomainPartWorker
        srv = self.cluster("srv")
        who = "camdomain on srv"
        v = srv.door("camdomain", who)
        fed = self.federation(v, srv.objects_on("srv", v, who))
        holder = fed.domain_holder
        view = ReadView(fed, lost_after=45.0, wall=self.wall)
        configured = [n for n, c in fed.clusters.items() if isinstance(c.objects, _CopyObjects)]
        self.inputs = BookInputs(holder.vars, view, wall=self.wall, topology=Topology(holder.vars),
                                   sealer=self.ring("srv"))
        books = Books(self.inputs, holder.objects,
                      members=Members(holder.vars, wall=self.wall, configured=lambda: configured, domain="srv"))
        self.domainpart = DomainPartWorker(books, holder.vars, holder.objects, instance="srv:1201:0004b1", wall=self.wall)

    def domain_pass(self) -> None:
        """The holder's passes, in the order the units run them: the signer's, the VMS's books, the console's reader."""
        self.holder.run_pass()
        if getattr(self, "domainpart", None) is not None:
            self.domainpart.pass_once()
        if getattr(self, "console", None) is not None:
            self.console_pass()

    # -- the agents ---------------------------------------------------------------------------------------------------------
    def holder_agent(self):
        """`agent.main` on srv: `DOMAIN_CONFIG_URL` — the holder's own agent reads its own store and sends the same signed report as every member — and
        `CLUSTERS` with the consoles it follows the holder by, as every member's agent (N12): the record of a larger term
        it carries home is how the holder learns it was replaced, and from then on it carries through the new door."""
        from w2cplatform.domain.agent import DomainAgent, HolderFollower, ask_held
        from w2cplatform.domain.carry import CarryClient
        from w2cplatform.domain.federation import Unreachable
        from w2cplatform.trust.memberkey import MemberKey
        srv = self.cluster("srv")
        who = "domainagent on srv"
        own = srv.door("domainagent", who)
        sealer = self.ring("srv")
        key = MemberKey.load_or_make(own, sealer)

        def ask(n):                                          # CLUSTERS names it now; its console is up when it is
            if f"console {n}" not in self.doors:
                raise Unreachable(f"{n}: its console is not up")
            return ask_held(self.doors[f"console {n}"])
        named = [e.split("=", 1)[0] for e in self.clusters_line().split(",") if "=" in e]   # `consoles_from_env`
        agent = DomainAgent("srv", srv.door("domainagent", who), own, now=self.wall,
                            domain_objects=srv.objects_on("srv", own, who),
                            published=srv.objects_on("srv", own, who),
                            reaches=lambda: CLUSTERS["srv"][0].split(","), own_objects=srv.objects_on("srv", own, who),
                            sealer=sealer, key=key, follow=HolderFollower({n: (lambda n=n: ask(n)) for n in named}),
                            open_door=lambda rec: (CarryClient(rec["url"], "srv", key, wall=self.wall), None)
                            if rec.get("url") else None)
        self.agents["srv"] = agent
        return agent

    # -- the clusters' own consoles (the platform's console, `/api/held` among its doors) -----------------------------------
    def cluster_console(self, name: str):
        """`w2c-console` on `name`: the VMS at `/`, the recorder's tables under `/rec`, the processes' door `/api/held`; its
        store by the role `console`. The gate opens once its agent has carried a key set (`access.py`)."""
        from vms.config import REC_SPEC
        from vms.console import make_console
        from vms.controller import VmsController
        from w2cplatform.spec import SpecController
        c = self.cluster(name)
        who = f"console on {name}"
        v = c.door("console", who)
        o = c.objects_on(name, v, who)
        m = make_console(VmsController(v, o, wall=self.wall, cluster=name), c.server.resource, self.wall,
                         mounts={"rec": SpecController(REC_SPEC, v, o, wall=self.wall, cluster=name)})
        self.consoles[name] = m
        self.serve(f"console {name}", f"{name}:{PORTS['console']}", m.handler(), who)
        return m

    def console_urls(self) -> dict[str, str]:
        """The consoles `CLUSTERS` names, as an agent that follows the holder asks them (`/api/held`)."""
        return {n: self.doors[f"console {n}"] for n in ("srv", "relay-a", "relay-b", "relay-b2") if f"console {n}" in self.doors}

    # -- an office: its agent, with the relay's door ------------------------------------------------------------------------
    def office_agent(self, name: str):
        """`agent.main` on an office: `DOMAIN_URL` (the signer's door — its report goes there too, `POST /api/member`,
        and its summary of the cameras, `POST /api/relay`), `RELAY=1` (it relays the members the topology puts behind
        it, and opens the relay's door), `REPORT=1`, `CLUSTERS` with the consoles it follows the holder by."""
        from w2cplatform.domain.agent import DomainAgent, HolderFollower, ask_held
        from w2cplatform.domain.carry import CarryClient
        from w2cplatform.domain.members import fingerprint
        from w2cplatform.domain.relay import RelayDoor, door_handler
        from w2cplatform.trust.memberkey import MemberKey
        c = self.cluster(name)
        who = f"domainagent on {name}"
        own = c.door("domainagent", who)
        sealer = self.ring(name)
        key = MemberKey.load_or_make(own, sealer)
        self.log.note(f"агент {name} печатает при первом старте: member key {key.pub}, fingerprint {fingerprint(key.pub)},\n"
                      f"sealing key {key.seal_pub}")
        own_objects = c.objects_on(name, own, who)
        consoles = self.console_urls()
        follow = HolderFollower({n: (lambda u=u: ask_held(u)) for n, u in consoles.items()})
        agent = DomainAgent(name, CarryClient(self.signer_url, name, key, wall=self.wall), own, now=self.wall,
                            published=own_objects, bundle_store=own_objects, cluster_objects=own_objects,
                            relay_members=lambda: agent.relays(), bundle_members=lambda: agent.relays(),
                            reaches=lambda: CLUSTERS[name][0].split(","), own_objects=own_objects, sealer=sealer, key=key,
                            follow=follow,
                            open_door=lambda rec: (CarryClient(rec["url"], name, key, wall=self.wall), None)
                            if rec.get("url") else None)
        self.agents[name] = agent
        self.serve(f"relay door {name}", f"{name}:{PORTS['relay door']}", door_handler(RelayDoor(agent)),
                   f"relay door on {name}")
        return agent

    # -- a camera: its flash, its agent -------------------------------------------------------------------------------------
    def camera(self, name: str):
        """A camera with the platform's firmware as the course builds one: a cluster of one on its flash
        (`DeviceCluster`, М12A Lesson 10) — not booted yet — and its agent, which reaches only its office: `RELAY_URL`
        (the office's relay door), `REPORT=1` into the office's objects (`RELAY_OBJECTS_URL`). The course has no camera
        process: the agent is built as Lesson 17's tests build a camera's (`console`, `current`, `seen_store`,
        `cluster_objects` — its durable objects, where it keeps the shared settings and a backup copy it was given)."""
        from w2cplatform.cluster.variables import FakeVariables
        from w2cplatform.domain.agent import DomainAgent
        from w2cplatform.domain.alarms import Card, pages
        from w2cplatform.domain.carry import CarryClient
        from w2cplatform.domain.members import fingerprint
        from w2cplatform.trust.memberkey import MemberKey
        from vms.camera_cluster import DeviceCluster
        serial, office, reaches, base = CAMERAS[name]
        flash = FakeVariables()
        flash._log = [base]
        door = f"the flash of {name}"
        cam = DeviceCluster(serial, TracedVars(self.log, flash, f"camera {name} (its console)", door), wall=self.wall,
                            name=name, reaches=reaches.split(","), pushes=True, can=CAN[name])
        cam.flash_store = flash
        cam.events = os.path.join(self.tmp, name, "archive")       # where its processes write their events: the card's
        os.makedirs(cam.events, exist_ok=True)
        self.cams[name] = cam
        who = f"domainagent on {name}"
        own = TracedVars(self.log, flash, who, door)
        sealer = self.ring(name)
        key = MemberKey.load_or_make(own, sealer)
        self.log.note(f"агент {name} печатает при первом старте: member key {key.pub}, fingerprint {fingerprint(key.pub)},\n"
                      f"sealing key {key.seal_pub}")
        o = self.cluster(office)
        relay_objects = Remote(self.log, o.objects_on(office, o.vars), who, f"the objects of {office}",
                               f"у продукта POST /api/member/{name} в дверь ретранслятора ({office}:{PORTS['relay door']})",
                               site=self, box=office)
        agent = DomainAgent(name, CarryClient(self.doors[f"relay door {office}"], name, key, wall=self.wall), own,
                            now=self.wall, console=device_console(cam, sealer),
                            domain_objects=relay_objects, published=cam.local_objects(), seen_store=cam.local_objects(),
                            cluster_objects=cam.disk, pages=lambda: pages(Card("rec", cam.events), self.wall()),
                            alarm_waiting=Card("rec", cam.events).waiting,
                            reaches=lambda: reaches.split(","), own_objects=cam.local_objects(), sealer=sealer, key=key)
        cam.agent, cam.key = agent, key
        self.agents[name] = agent
        return cam

    def sync(self, name: str) -> bool:
        """One pass of `name`'s agent — its requests made as it."""
        with self.log.acting(f"domainagent on {name}"):
            return self.agents[name].sync()

    def agents_pass(self, names=None) -> None:
        """The agents' passes in the order a member behind a relay needs: offices, cameras, offices again, the holder's."""
        names = names or list(self.agents)
        offices = [n for n in names if n.startswith("relay")]
        for n in offices + [n for n in names if n.startswith("cam")] + offices + [n for n in names if n == "srv"]:
            self.sync(n)

    # -- people ---------------------------------------------------------------------------------------------------------------
    def ask(self, who: str, method: str, door: str, path: str, body=None, headers: dict | None = None,
            token: bool = True) -> tuple[int, object]:
        """A person's request, as a page or `curl` would make it: real HTTP to `door`, the person's token with it."""
        import urllib.error
        import urllib.request
        h = {"Content-Type": "application/json", **(headers or {})}
        if token and who in getattr(self, "tokens", {}):
            h["Authorization"] = f"Bearer {self.tokens[who]}"
        req = urllib.request.Request(self.doors[door] + path, method=method, headers=h,
                                     data=json.dumps(body).encode() if body is not None else None)
        with self.log.acting(who):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    status, raw = r.status, r.read()
            except urllib.error.HTTPError as e:
                status, raw = e.code, e.read()
            except OSError as e:                         # the door closed the connection with no answer
                return 0, f"no answer: {type(e).__name__}: {e}"
        try:
            return status, json.loads(raw or b"{}")
        except ValueError:
            return status, raw.decode(errors="replace")

    def login(self, who: str) -> str:
        """`POST /api/login` at the domain's console, handed to the signer: the person's token."""
        st, got = self.ask(who, "POST", "domain console", "/api/login",
                           {"user": who, "password": self.passwords[who]}, token=False)
        if st != 200:
            raise RuntimeError(f"{who} could not log in: {st} {got}")
        self.tokens = {**getattr(self, "tokens", {}), who: got["token"]}
        return got["token"]

    def operator_key(self, member: str) -> str:
        """The operator on srv registers a member's key as its agent printed it: `python3 -m w2cplatform.domain.members key
        <member> <pub> <seal_pub>` — its store by the holder's socket of the role `domain`."""
        from w2cplatform.domain.members import Members
        from w2cplatform.domain.runtime import names_from_env
        key = self.agents[member].key
        self.log.note(f"оператор на srv: CLUSTERS=… PLATFORM_STORE=configstore:///run/configstore/domain.sock "
                      f"python3 -m w2cplatform.domain.members key {member} {key.pub} {key.seal_pub}")
        holder, reporting = names_from_env(env={"CLUSTERS": self.clusters_line(), "DOMAIN_HOLDER": "srv"})
        done = Members(self.cluster("srv").door("domain", "operator on srv"), configured=lambda: reporting,
                       domain=holder).set_key(
            member, key.pub, key.seal_pub, by="the holder's operator")
        said = f"{member}: {'key registered' if done else 'not registered — no such member, or it has a key'}"
        self.log.note(f"→ {said}")
        return said

    # -- the clusters' controllers: `w2c-controller@cam`, `w2c-controller@rec` on every server ------------------------------
    def controllers(self, name: str) -> list:
        """The platform's placement controllers of `name` for the VMS and the recorder (`host.placement_pass` each pass):
        on an office they place its recordings, and they publish the snapshots its agent reports — an office with no
        camera of its own publishes the empty `unplaced` shard, without which its agent does not report at all."""
        if name in getattr(self, "_ctls", {}):
            return self._ctls[name]
        from vms.config import REC_SPEC
        from vms.controller import VmsController
        from w2cplatform.spec import SpecController
        c = self.cluster(name)
        out = []
        for role, make in (("camcontroller", lambda v, o: VmsController(v, o, wall=self.wall, cluster=name)),
                           ("reccontroller", lambda v, o: SpecController(REC_SPEC, v, o, wall=self.wall, cluster=name))):
            who = f"{role} on {name}"
            v = c.door(role, who)
            ctl = make(v, c.objects_on(name, v, who))
            self.wall.watchers.append(ctl)
            out.append(ctl)
        self._ctls = {**getattr(self, "_ctls", {}), name: out}
        return out

    def place(self, name: str) -> None:
        from w2cplatform.host import placement_pass
        for ctl in self.controllers(name):
            placement_pass(ctl)

    # -- a recorder with the ingest (and, on an office, the forwarder) -----------------------------------------------------
    def ingest_url(self, name: str) -> str:
        """Where a cluster's recorder takes the streams cameras push: its door and `/ingest`, as the product's."""
        return f"http://{name}:{PORTS['recorder']}/ingest"

    def recorder(self, name: str):
        """`vms-recworker` on `name` (`r-<name>-1`) that hosts the ingest and the relay's forwarder (`RecWorker.host_ingest`,
        ADR-0065's addition of 2026-10-08) — what the course's recorder process does NOT do yet (`vms/__main__.recorder`:
        module-design.md, open point 5), done here as the tests do it (`tests/vmsconftest.ingest_recorder`). Its `dial` is
        the stand's network: an ingest of the centre answers an office while neither is off nor the road between cut."""
        from vms.forwarder import Forwarder
        c = self.cluster(name)
        rec = c.recorder(name)
        who = f"forwarder in r-{name}-1 on {name}"

        def dial(url):
            from w2cplatform.domain.federation import Unreachable
            for there, ing in self.ingests.items():
                if self.ingest_url(there) == url:
                    if there in self.down or name in self.down or (name, there) in self.cut:
                        raise Unreachable(f"{url} did not answer {name}")
                    return TracedIngest(self.log, ing, who, f"{there}:{PORTS['recorder']} (the ingest of r-{there}-1)")
            raise Unreachable(f"{url} did not answer {name}")
        rec.host_ingest(name, self.ingest_url(name), dial=dial)
        if rec.forwarder is not None:
            rec.forwarder.tokens.door = self.role_requests(name, "recworker")
        self.recorders[name], self.ingests[name] = rec, rec.ingest
        from vms.autoworker import AutoWorker
        auto_vars = c.door("autoworker", f"autoworker on {name}")
        self.auto_workers[name] = AutoWorker(f"a-{name}-1", auto_vars,
            c.objects_on(name, auto_vars, f"autoworker on {name}"),
            wall=self.wall, clock=self.clock, server=name, env={},
            ask_dial=dial, token_requests=self.role_requests(name, "autoworker"))
        return rec

    def rec_pass(self, name: str) -> None:
        """One pass of a recorder (`RecWorker.run`): its slot, its volume, the reconcile — which takes what cameras
        pushed into its ingest and writes it (`take_pushed`, `vms.ingestrec`) — and its heartbeat."""
        rec = self.recorders[name]
        with self.log.acting(f"recworker {rec.name} on {name}"):
            rec.lease_pass()
            rec.volume_pass()
            rec.reconcile_once()
            rec.heartbeat_once()
        auto = self.auto_workers[name]
        auto.renew_slot()
        auto.reconcile_once()
        auto.heartbeat_once()

    def say_heartbeat(self, name: str, fields=("ingest", "ingest_streams", "upstream", "volume")) -> None:
        """What a recorder says of itself in its heartbeat (an object on its server), as a line of the scenario's: the
        fields asked, and each recording's phase and why."""
        rec = self.recorders[name]
        raw = rec.objects.get(f"rec/heartbeats/{rec.name}")
        hb = json.loads(raw) if raw else {}
        shown = {k: hb.get(k) for k in fields if k in hb}
        shown["status"] = [{k: st.get(k) for k in ("id", "cam", "phase", "why", "source", "via", "written_through")
                            if k in st}
                           for st in hb.get("status", [])]
        self.log.note(f"heartbeat {rec.name} (rec/heartbeats/{rec.name}, объект на {name}):\n"
                      + json.dumps(shown, ensure_ascii=False, indent=1))

    def forward(self, name: str) -> dict:
        """One pass of the office's forwarder (`Forwarder.pass_once`; the product runs it as threads beside the recorder)."""
        with self.log.acting(f"forwarder in r-{name}-1 on {name}"):
            return self.recorders[name].forwarder.pass_once()

    def gateway(self):
        """The viewer's side in the centre: the course's MODEL of a live gateway over the centre's ingest
        (`domainpart.gateway.Gateway` + `ingest.IngestLiveEndpoint`) — the course's WHEP gateway (`vms/liveworker.py`)
        knows no ingest. It checks a person's token by the centre's own key set, as a cluster's endpoint does."""
        if getattr(self, "_gateway", None) is not None:
            return self._gateway
        from vms.gateway import Forbidden, Gateway
        from vms.ingest import IngestLiveEndpoint, audience
        from w2cplatform.domain.agent import ClusterTrust
        from w2cplatform.trust.tokens import PERSON, TokenError, verify
        srv = self.cluster("srv")
        who = "gateway gw-centre on srv"
        trust = ClusterTrust(srv.door("console", who))

        def authorise(token, camera):
            try:
                return verify(token, trust.keyset(), trust.revoked(), now=self.wall(), kind=PERSON)["sub"]
            except TokenError as e:
                raise Forbidden(str(e)) from None
        ing = TracedIngest(self.log, self.ingests["srv"], who, f"srv:{PORTS['recorder']} (the ingest of r-srv-1)")
        endpoint = IngestLiveEndpoint(ing, authorise)
        self._gateway = Gateway("gw-centre", where=lambda c: audience("srv"), endpoint=lambda w: endpoint)
        return self._gateway

    # -- a camera boots ------------------------------------------------------------------------------------------------------
    def role_requests(self, name, role="camworker"):
        """The worker's real private socket; the member key stays in the agent."""
        from w2cplatform.console import Bounds, UnixConsoleServer
        from w2cplatform.domain.tokenrequest import WorkerTokenDoor, local_handler
        key = (name, role)
        doors = getattr(self, "_role_token_doors", None)
        if doors is None:
            self._role_token_doors = doors = {}
        if key not in doors:
            import tempfile
            import threading
            path = os.path.join(tempfile.mkdtemp(prefix="role-token-"), "tokens.sock")
            server = UnixConsoleServer(path, local_handler(self.agents[name], role), Bounds())
            threading.Thread(target=server.serve_forever, daemon=True).start()
            doors[key] = WorkerTokenDoor(path)
        return doors[key]

    def boot(self, name: str, card_bytes: int = 64 << 20) -> None:
        """The camera's process at its start, as the course builds it (`tests/domainvms/test_lesson16_card._camera_process`;
        the product's `vmscam`): the boot (`DeviceCluster.boot`: epoch, row, publish, door), its card declared as a volume
        of the camera's own cluster (`card.declare_card`, `kind: edge`, `cam: 1`), the recording `1-sd` on it, the card's
        recorder over the camera's ring (`CardRecorder`, `r-1`), the camera's placement of it, and its pusher tied to it
        (`ingest.camera_process`)."""
        from vms.card import CamRing, CardActuator, CardRecorder, declare_card
        from vms.config import REC_SPEC
        from vms.ingest import camera_process
        from w2cplatform.spec import SpecController
        cam = self.cams[name]
        serial, office, _, _ = CAMERAS[name]
        door = f"the flash of {name}"
        flash = cam.flash_store
        cam.boot()
        card_dir = os.path.join(self.tmp, name, "card")
        os.makedirs(card_dir, exist_ok=True)
        proc = TracedVars(self.log, flash, f"camera {name} (its process)", door)
        self.log.note(f"процесс камеры {name} объявляет карту томом своего кластера (card.declare_card; у продукта vmscam при старте)")
        declare_card(proc, name, card_dir, card_bytes, cam="1")
        self.log.note(f"запись 1-sd на карте (в курсе — SpecController.create на флеше камеры; у продукта POST /rec/recordings "
                      f"консоли камеры, stand.sh setup)")
        SpecController(REC_SPEC, TracedVars(self.log, flash, f"console of {name}", door), cam.local_objects(),
                       wall=self.wall, cluster=name).create({"name": "1-sd", "cam": "1", "home": "card", "when": "offline"})
        ring = CamRing(clock=self.wall, steady=self.wall, **({"max_bytes": RING_BYTES[name]} if name in RING_BYTES else {}))
        act = CardActuator(ring, threaded=False, serial=serial)
        rec = CardRecorder("r-1", TracedVars(self.log, flash, f"recworker r-1 on {name}", door), cam.local_objects(), ring,
                           act, clock=self.wall, wall=self.wall, server=name,
                           resource_root=cam.events,
                           env={"SERVER_NAME": name, "INSTANCE_ID": f"{name}:{CAMERAS[name][3] + 101}:{CAMERAS[name][3] + 101:06x}"})
        rec.lease_pass()
        rec.heartbeat_once()
        SpecController(REC_SPEC, TracedVars(self.log, flash, f"reccontroller on {name}", door), cam.local_objects(),
                       wall=self.wall, cluster=name).ensure_placed()
        rec.reconcile_once()
        rec.heartbeat_once()
        if rec.card is not None:
            rec.card.segment_span = 10.0

        def dial(url):
            from w2cplatform.domain.federation import Unreachable
            for there, ing in self.ingests.items():
                if self.ingest_url(there) == url:
                    if there in self.down or name in self.down or (name, there) in self.cut:
                        raise Unreachable(f"{url} did not answer {name}")
                    return TracedIngest(self.log, ing, f"pusher on {name} ({serial})",
                                        f"{there}:{PORTS['recorder']} (the ingest of r-{there}-1)")
            raise Unreachable(f"{url} did not answer {name}")
        pusher = camera_process(serial, TracedVars(self.log, flash, f"pusher on {name}", door), dial, rec,
                                perform=cam.perform, token_requests=self.role_requests(name))
        pusher.sealer = self.ring(name)
        cam.ring, cam.act, cam.rec, cam.pusher, cam.frames, cam.started = ring, act, rec, pusher, 0, self.wall()

    def reboot(self, name: str) -> None:
        """The camera loses power and comes back: the boot (a new epoch by CAS on the flash, the row kept, a publish into
        a NEW RAM, the door after it) and its process started again — a new ring, the card's recorder, the pusher. The
        card and its recording are on the flash and the card already: declared once, not again."""
        from vms.card import CamRing, CardActuator, CardRecorder
        from vms.ingest import camera_process
        cam = self.cams[name]
        serial = CAMERAS[name][0]
        door = f"the flash of {name}"
        flash = cam.flash_store
        cam.boot()
        ring = CamRing(clock=self.wall, steady=self.wall, **({"max_bytes": RING_BYTES[name]} if name in RING_BYTES else {}))
        act = CardActuator(ring, threaded=False, serial=serial)
        base = CAMERAS[name][3] + 101 + cam.boots
        rec = CardRecorder("r-1", TracedVars(self.log, flash, f"recworker r-1 on {name}", door), cam.local_objects(), ring,
                           act, clock=self.wall, wall=self.wall, server=name, resource_root=cam.events,
                           env={"SERVER_NAME": name, "INSTANCE_ID": f"{name}:{base}:{base:06x}"})
        rec.lease_pass()
        rec.heartbeat_once()
        rec.reconcile_once()
        rec.heartbeat_once()
        old = cam.pusher
        dial = old.dial
        pusher = camera_process(serial, TracedVars(self.log, flash, f"pusher on {name}", door), dial, rec,
                                perform=cam.perform, token_requests=self.role_requests(name))
        pusher.sealer = self.ring(name)
        cam.ring, cam.act, cam.rec, cam.pusher, cam.frames, cam.started = ring, act, rec, pusher, 0, self.wall()

    def scenarios(self, name: str):
        """The camera's embedded executor reads verified settings and requests its role token."""
        cam = self.cams[name]
        serial = CAMERAS[name][0]
        door = f"the flash of {name}"

        def dial(url):
            from w2cplatform.domain.federation import Unreachable
            for there, ing in self.ingests.items():
                if self.ingest_url(there) == url:
                    if there in self.down or name in self.down or (name, there) in self.cut:
                        raise Unreachable(f"{url} did not answer {name}")
                    return TracedIngest(self.log, ing, f"asker on {name} ({serial})",
                                        f"{there}:{PORTS['recorder']} (the ingest of r-{there}-1)")
            raise Unreachable(f"{url} did not answer {name}")
        return cam.host_scenarios(self.agents[name], dial, steady=self.wall)

    def sense(self, name: str) -> None:
        """The camera's sensor up to now: ten frames a second into its ring, a key frame every two seconds, each stamped by
        the camera's clock where it was captured (`tests/domainvms/test_lesson16_card._sensor`; the firmware's frame
        socket in the product). In the course there is no firmware: these are fake frames."""
        from vms.obsd import archive_ms, video
        from vms.worker import FAKE_PPS, FAKE_SPS
        cam = self.cams[name]
        n, start = cam.frames, cam.started
        while start + n / 10 <= self.wall():
            t, key = start + n / 10, n % 20 == 0
            body = (FAKE_SPS + FAKE_PPS + b"\x00\x00\x00\x01\x65" if key else b"\x00\x00\x00\x01\x41") + \
                b"\x80" * 200 + n.to_bytes(8, "big")
            cam.ring.add(video(archive_ms(t), archive_ms(t + 0.1), body, key, 1280, 720))
            n += 1
        cam.frames = n

    def camera_step(self, name: str) -> dict:
        """One step of the camera's process: what the sensor gave since, the card's writer, the pusher's pass, the gate."""
        cam = self.cams[name]
        self.sense(name)
        if self.wall() - getattr(cam, "published_at", 0) >= 5:       # the camera's worker publishes every few seconds
            cam.publish()
            cam.published_at = self.wall()
        cam.act.drain()
        with self.log.acting(f"pusher on {name}"):
            out = cam.pusher.pass_once([])
        cam.rec.gate_pass()
        cam.act.drain()
        if self.wall() - getattr(cam, "beat_at", 0) >= 10:           # …and its recorder heartbeats every ten
            cam.rec.heartbeat_once()
            cam.beat_at = self.wall()
        return out
