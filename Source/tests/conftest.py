"""The platform's test helpers: one box in a temp directory — the platform's two stores, the resource's tree, a clock —
the console served, the door's keys, and the two subsystems that exist only for the platform's own tests
(`testdata/testsub.subsystem.yaml`, `testdata/testsub2.subsystem.yaml`) with a worker for the first.

A test of the platform takes its helpers from here and from nowhere else: nothing here knows a subsystem of the
product (`test_boundary.py` holds this file to that). A subsystem's tests have helpers of their own beside these, in a
module of that subsystem's.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from w2cplatform.objects import FsObjectStore  # noqa: E402
from w2cplatform.reconcile import Reconciler, Want  # noqa: E402
from w2cplatform.variables import FileVariables  # noqa: E402
from w2cplatform.worker import Worker  # noqa: E402


class Clock:
    def __init__(self, t=1000.0): self.t = t
    def __call__(self): return self.t
    def advance(self, s): self.t += s


class Box:
    """The platform on one box: its two stores, the resource's tree (`resource_root`, the process's `RESOURCE_ROOT`), a
    monotonic clock and a wall clock."""
    def __init__(self, prefix: str = "w2c-"):
        self.root = tempfile.mkdtemp(prefix=prefix)
        self.vars = FileVariables(os.path.join(self.root, "config"))
        self.objects = FsObjectStore(os.path.join(self.root, "objects"))
        self.resource_root = os.path.join(self.root, "tree")
        self.clock, self.wall = Clock(), Clock(1_757_500_000.0)


class Served:
    """A console — a `SpecConsole` or a `Mount` — serving on a free port, and `call(method, path, body, headers)` →
    `(status, reply)`: the platform's routes as a page or a `curl` reach them. A POST carries an `Idempotency-Key` of
    its own unless one is given (`key`; `False` sends none). `with Served(con) as call: …` shuts it down after."""
    _n = 0

    def __init__(self, console):
        self.srv = console.serve("127.0.0.1", 0)
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def __call__(self, method, path, body=None, headers=None, key=None, raw=None):
        import urllib.error
        import urllib.request
        Served._n += 1
        h = {"Content-Type": "application/json", **(headers or {})}
        if method == "POST" and "Idempotency-Key" not in h and key is not False:   # `key=False`: sent without one
            h["Idempotency-Key"] = key or f"served-{Served._n}"
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.base + path, method=method, data=data, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            out = e.read()
            try:
                return e.code, json.loads(out or b"null")
            except ValueError:
                return e.code, out

    def close(self):
        self.srv.shutdown()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def stamped(log, of: str):
    """`log` with what its unit is about set as the base worker sets it (`Worker.event_log`, `EventLog._of`): the lines a
    test lays out for a query, as the worker holding the unit would have written them. A line does not say its own."""
    log._of = of
    return log


def as_kept(step):
    """A long step of a resource's pass, as the one step a test may give it since the boundary's step 6 took the
    subsystems' hooks out of the resource: `Resource.kept` — called once a pass, handed the pulse (`progressed`), and
    holding nothing. `step.pass_(now[, progressed])` is what a hook's pass was."""
    import inspect

    def kept(progressed=None):
        if "progressed" in inspect.signature(step.pass_).parameters:
            step.pass_(0, progressed or (lambda: None))
        else:
            step.pass_(0)
        return lambda *a: False
    return kept


def published_snapshot(objects, sub: str, rows: str) -> dict:
    """The snapshot as a READER sees it: list `<sub>/snapshot/`, get each shard, merge.
    One object per worker is the published shape, so a test that reads one key is
    testing a shape the platform no longer has."""
    out = []
    for key in objects.list(f"{sub}/snapshot/"):
        raw = objects.get(key)
        if raw:
            out.extend(json.loads(raw).get(rows, []))
    return {rows: out}


def key_ring() -> str:
    """A fresh key ring file for a test (`SECRETS_KEY`, `w2cplatform/sealing.py`): one 32-byte key, `k1`."""
    d = tempfile.mkdtemp(prefix="ring-")
    path = os.path.join(d, "platform.key")
    with open(path, "w") as f:
        f.write(f"k1 {os.urandom(32).hex()}\n")
    return path


class door_keys:
    """`with door_keys(vars_) as keys:` — the cluster's door key in the store for a test (`w2cplatform/door.py`):
    `SECRETS_KEY` a fresh key ring for the processes made inside (a console seals its door key with it), a door key made
    in `vars_` (`door.rotate`: `door/signer`, `door/keys`), `keys.signer` the console's half, `keys.ring` a holder's; the
    environment as it was after."""

    def __init__(self, vars_):
        self.vars = vars_

    def __enter__(self):
        from w2cplatform.door import Ring, Signer, rotate
        from w2cplatform.sealing import Sealer
        self.was = os.environ.get("SECRETS_KEY")
        os.environ["SECRETS_KEY"] = key_ring()
        sealer = Sealer.from_env()
        rotate(self.vars, sealer)
        self.signer, self.ring = Signer(self.vars, sealer), Ring(self.vars)
        return self

    def __exit__(self, *a):
        if self.was is None:
            os.environ.pop("SECRETS_KEY", None)
        else:
            os.environ["SECRETS_KEY"] = self.was


class ByName:
    """A door keeper for a test (`w2cplatform/door.py`'s `DoorKeeper` in the open mode, but naming the caller): lets
    everybody in, under the name the request gives (`X-User`), as a token names who it was given to (`sub`)."""

    def admit(self, handler, route, unit):
        return {"sub": (getattr(handler, "headers", None) or {}).get("X-User", "anybody")}

    def headers(self, handler):
        return []

    def preflight(self, handler):
        handler.send_response(204); handler.send_header("Content-Length", "0"); handler.end_headers()


# -- testsub and testsub2: the subsystems of the platform's own tests -------------------------------------------------
#
# testsub's unit is a named COUNTER a worker keeps (`testsub/counters/<name>`); testsub2's is a TALLY about one of them,
# kept on a shelf (`testsub2/tallies/<name>`, `testsub2/shelves/<name>`) — the second says every key the platform reads
# (`test_spec_rule.py`). A mechanism of the platform is proved on them: if it works here, it works without the product.
TESTDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata")
TESTSUB = os.path.join(TESTDATA, "testsub.subsystem.yaml")
TESTSUB2 = os.path.join(TESTDATA, "testsub2.subsystem.yaml")
_SPECS: dict = {}


def _read(path: str):
    """A spec read from its file and NOT put in this process's catalogue (`from_dict`, not `load`): the catalogue is
    what the process knows, and its derived rules — how an address hides a login (`catalog.secret_rules`), which
    objects are rows — are every loaded spec's together. A test of the platform that loaded testsub2 would change
    them for every test after it in the same run; a test that needs a spec in the catalogue registers it itself."""
    if path not in _SPECS:
        import yaml
        from w2cplatform.spec import SubsystemSpec
        with open(path, encoding="utf-8") as f:
            _SPECS[path] = SubsystemSpec.from_dict(yaml.safe_load(f))
    return _SPECS[path]


def testsub():
    """testsub's spec, read once (`_read`)."""
    return _read(TESTSUB)


def testsub2():
    """testsub2's spec, read once (`_read`) — and testsub's put in the catalogue: testsub2 follows it by its spec
    (`near.of`, `near.prefer`), and no controller is built for a spec whose neighbour its process did not load
    (`catalog.near_known`, ADR 0056). testsub says no secret and no object row: the derived rules stay as they were."""
    from w2cplatform import catalog
    if "testsub" not in [s.name for s in catalog.specs()]:
        catalog.register(testsub())
    return _read(TESTSUB2)


def spec_named(name: str):
    """The least spec a subsystem can say — a unit with a name, and what a worker that said nothing counts for — under a
    name of the test's own: what a test of the platform's bare mechanics (a slot, an epoch, a wait) runs a `Worker` by.
    A worker runs by its spec, always (`Worker.__init__`); this one says nothing a mechanism would read."""
    from w2cplatform.spec import SubsystemSpec
    return SubsystemSpec.from_dict({"name": name, "unit": {"rows": f"{name}s", "id": "name",
                                                           "fields": {"name": {"type": "string", "required": True}}},
                                    "placement": {"capacity": {"from": "capacity", "default": 4}}})


class in_catalogue:
    """`with in_catalogue(testsub2()):` — the specs in this process's catalogue for the block (what the resource reads
    holds and object rows from), and the catalogue as it was after it: the next test knows what it knew before."""

    def __init__(self, *specs):
        self.specs = specs

    def __enter__(self):
        from w2cplatform import catalog
        self.was = dict(catalog._loaded)
        for s in self.specs:
            catalog.register(s)
        return self

    def __exit__(self, *a):
        from w2cplatform import catalog
        with catalog._lock:
            catalog._loaded.clear()
            catalog._loaded.update(self.was)
            catalog.version += 1
            catalog._derived.clear()


def controller(box, vars_=None, spec=None, capacity=None, **kw):
    """testsub's controller from its spec (`SpecController`) over the box's stores — the store as it is (`vars_`), or
    a door with rights (`box.vars.as_writer("console", spec.acl_console())`)."""
    from w2cplatform.spec import SpecController
    spec = spec or testsub()
    return SpecController(spec, box.vars if vars_ is None else vars_, box.objects, capacity, wall=box.wall, **kw)


def console_ctl(box, spec=None, **kw):
    """The operator's controller: the console's rights over the spec's rows (`acl_console`)."""
    spec = spec or testsub()
    return controller(box, box.vars.as_writer("console", spec.acl_console()), spec, **kw)


def controller_ctl(box, spec=None, **kw):
    """The controller's own: its rights over placement and the assignments (`acl_controller`)."""
    spec = spec or testsub()
    return controller(box, box.vars.as_writer(f"{spec.name}controller", spec.acl_controller()), spec, **kw)


# A counter worker's incarnation, in the one form of an instance name, `box:pid:rnd` (`runtime.instance_on_box`; ADR 0003,
# the fourteenth review, minor 27): the server is the box, a running number the pid, the same in hex the tail.
_INSTANCES = iter(range(1, 1 << 30))


class CounterWorker(Worker):
    """testsub's worker: a counter it is assigned RUNS — `running[counter] = epoch` — from the pass that takes its epoch
    to the one that lets it go; a request adds to it (`counts`); `started` and `stopped` say what it did, in order, as a
    subsystem's own work would. Everything else — the slot, the leases, the fence, the stand-in, the heartbeat's own
    fields, the requests — is the platform's `Worker`, which is what a test of the platform proves here.

    Its pass is the platform's reconcile helper (`w2cplatform/reconcile.py`, ADR 0033): what runs is made equal to what
    is assigned, and a counter whose epoch could not be taken waits its backoff, spread by jitter, before it is tried
    again.

    Not knowing is not "no": a pass whose read does not answer goes on with the rows it read last; a row that does not
    parse is that counter's (`row_garbled`); a counter whose lease the lease step lost is stopped by the platform
    (`stop_unit`: dropped from the helper, no failure) and started again under a new epoch by the next pass, if it is
    still this worker's."""
    ROWS = "counters"

    def __init__(self, vars_, objects, name: str | None = None, clock=time.monotonic, wall=time.time,
                 server: str = "srv-1", capacity: int = 4, instance: str | None = None, labels=(),
                 resource_root: str | None = None, lease_ttl: float = 30.0, lease_margin: float = 5.0,
                 slot_ttl: float = 45.0, env: dict | None = None, spec=None):
        spec = spec or testsub()
        super().__init__(spec.sub, None, vars_, objects, lease_ttl, lease_margin, clock, wall,
                         instance or (lambda n: f"{server}:{n}:{n:06x}")(next(_INSTANCES)), slot_ttl, spec=spec)
        self.server, self.capacity, self.labels = server, capacity, list(labels)
        self.resource_root = resource_root
        self.rows: dict[str, dict] = {}
        self.row_errors: dict[str, str] = {}
        self.running: dict[str, int] = {}
        self.counts: dict[str, int] = {}
        self.started: list[str] = []
        self.stopped: list[str] = []
        # a counter's edit is ONE call: it keeps its epoch (`restart`), never a stop and a start
        self.reconciler = Reconciler(self._start, lambda unit: (self.stop_unit(unit), self.release(unit)),
                                     restart=lambda unit, want: unit in self.running)
        self.reconciler.now = clock
        self.claim_at_start(name, dict(env or {}))
        if resource_root:
            self.present(resource_root)

    def refresh(self) -> None:
        a = self.assignment()
        rows, errors = {}, {}
        for unit in a.units:
            try:
                items, _ = self.vars.get(self.sub.config(self.ROWS, unit))
                if not items or items.get("deleted") == "true":
                    continue
                rows[unit] = self.spec.row({"id": unit, **items})
                self.row_parsed(unit)
            except (ValueError, TypeError) as e:     # one row that does not parse is that counter's
                errors[unit] = self.row_garbled(unit, e)
                if unit in self.rows:
                    rows[unit] = self.rows[unit]
        self.rows, self.row_errors = rows, errors

    def reconcile_once(self, now=None) -> list[str]:
        try:
            self.refresh()
        except OSError:
            self.store_errors += 1                   # the rows read last stand
        for unit in [u for u in self.reconciler.running() if u in self.rows]:
            if not (unit in self.epochs and self.may_write(unit)):
                self.reconciler.drop(unit)           # running under no epoch it may write by: taken again below
        wants = {u: Want(int(r.get("revision") or 0), r) for u, r in self.rows.items()}
        if not self.writing_allowed:                 # fenced: nothing starts, and what is not its own any more stops
            wants = {u: w for u, w in wants.items() if u in self.reconciler.running()}
        self.reconciler.once(wants)
        self.passes += 1
        return sorted(self.running)

    # The helper's start: under the epoch it holds and may write by, else a new one. None now — the store, a step
    # abandoned, an assignment not read — is a failed start, retried after its backoff.
    def _start(self, unit: str, want: Want) -> bool:
        try:
            epoch = self.epochs[unit] if unit in self.epochs and self.may_write(unit) else self.take_epoch(unit)
        except Exception as e:                       # noqa: BLE001
            self.epoch_errors[unit] = str(e)
            return False
        self.epoch_errors.pop(unit, None)
        self.running[unit] = epoch
        self.counts.setdefault(unit, int(want.body.get("start") or 0))
        self.started.append(unit)
        return True

    def stop_unit(self, unit) -> None:
        self.reconciler.drop(str(unit))
        if self.running.pop(str(unit), None) is not None:
            self.stopped.append(str(unit))

    def stop_all_units(self) -> None:
        for unit in list(self.running):
            self.stop_unit(unit)

    def forget_units(self) -> None:
        self.rows, self.row_errors = {}, {}
        self.reconciler.clear()
        self.reconciler.reset_backoff()              # another name: what failed under the old one waits for nothing

    def unit_word(self, unit) -> str:
        return f"counter {unit}"

    def status(self) -> list[dict]:
        out = []
        for unit in sorted(set(self.rows) | set(self.running)):
            st = {"id": unit, "phase": "running" if unit in self.running else "waiting", "count": self.counts.get(unit, 0)}
            if unit in self.running:
                st["epoch"] = self.running[unit]
            if unit in self.row_errors:
                st["why"] = self.row_errors[unit]
            out.append(st)
        return out

    def held_rows(self) -> dict[str, dict]:
        return {u: self.rows[u] for u in self.running if u in self.rows}

    def perform(self, target, row, it):
        unit = str(row["id"])
        self.counts[unit] = self.counts.get(unit, 0) + int(it["add"])
        return {"added": int(it["add"])}


def counter_worker(box, name: str | None = None, server: str = "srv-1", **kw) -> CounterWorker:
    """testsub's worker on the box's stores and clocks."""
    kw.setdefault("clock", box.clock)
    kw.setdefault("wall", box.wall)
    return CounterWorker(kw.pop("vars_", box.vars), box.objects, name, server=server, **kw)
