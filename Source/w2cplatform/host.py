"""The platform's own processes, for whatever subsystems the specs say (the boundary's step 5, ГРАНИЦА-ПЛАТФОРМЫ-И-
ПОДСИСТЕМЫ.md §2.3, §3.6): the loops a controller, a resource and a console's housekeeping run, and the entry point
that builds them from a directory of specs (`python3 -m w2cplatform`, `__main__.py`).

    python3 -m w2cplatform controller <sub>   the placement pass of <sub>, every five seconds, from its spec alone
    python3 -m w2cplatform resource           this server's resource: its door, its heartbeat, the policy pass, restore
    python3 -m w2cplatform console            the console: every spec's rows, tables, requests and doors, one process

    SPEC_DIR          the directory of `<sub>.subsystem.yaml` this process runs from (`catalog.py`) — required
    PLATFORM_DIR      the platform's state (`config/`, `objects/`, `events/`); `PLATFORM_STORE` the store as a URL
    (the events tree) `w2c.env`'s key for it (`runtime.events_said`): the resource's, and where a controller's journal goes
    HUNG_MOVE_AFTER   controller: how long a hung worker keeps its units (`Controller.hung_move_after`)
    REACH_BUDGET      controller: units one pass moves to a server that reaches them (`spec.reach_budget`)
    RESOURCE_HOST, RESOURCE_PORT, RESOURCE_URL   resource: what its door binds, and the address its heartbeat says
    CONSOLE_ROOT      console: the subsystem at `/` (the deployment's word); every other spec is mounted under its name
    CONSOLE_HOST, CONSOLE_PORT   console: what it binds (`CONSOLE_UNIX`, `SECRETS_KEY`: the console's own; the door key
                      is the store's, `door/signer`, made by the console the first time it is asked for a door)
    DOOR_ORIGINS      every holder: the consoles' origins a page may come from (`door.py`, CORS)

The loops were a subsystem's (its `__main__`: the controller's loop, the blob sweep's, the resource's; and again in
М11's own entry point), and the platform ran only as a library under its `__main__`. They are here, once, and the
controllers, the console and the resource run from the specs alone; a subsystem's own processes are its workers (and
what it runs beside them, its jobs), which build on `w2cplatform/worker.py` and take from here only the stores
(`stores`) and the pacing of a loop (`every`, `stop`).
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # host.py — the platform's processes and their loops
#
# - `stop` — the one flag every loop waits on; set by `__main__`'s SIGTERM/SIGINT handler (installed only when RUN — a
#   process that imports this module, the tests do, keeps its own signals: the review's fifth and sixth passes).
# - `step(owner, what, name, fn, failed)` — one step of a pass in a try of its own, the trace said ONCE per spell of
#   failing and "works again" when it does (the review's seventh pass, part 2; the eighth review's minor, closed in the
#   ninth — the trace every five seconds for days). The spell is the owner's: one controller's, one console's.
# - `placement_pass(ctl)` — one pass of a placement controller: `pass_once` (place, move, bring ONE unit home — each
#   step in a try of its own — and the report `/metrics` reads), then the snapshot, in a step of its own, and both in
#   ONE pass of reads (`contract.one_pass`; the scaling pass after the eighth review). Two jobs, two failures, two
#   sentences: a publish that failed was said as "placement pass failed", naming the one thing that had not failed.
# - `controller_loop(ctl)` — that pass every five seconds, with the journal (the events tree) and `HUNG_MOVE_AFTER`.
# - `sweep_turn(controllers)` / `sweep_loop` — the blob sweep the console owns BECAUSE THE ACL SAYS SO (`<sub>/blobs/*`
#   is the console's to write, so it is the console's to collect).
# - `every(turn, seconds)` — a turn of a console's housekeeping, run every so often, each turn in a try of its own.
# - `run_resource(res, srv)` — a resource's life: a heartbeat at the start, the beat on its own thread, restore, and the
#   loop — a heartbeat every 10 s, the policy pass every 600 s, what the restore left asked again.
# - `stores(env, writer, acl)` — a process's two stores: the store by `PLATFORM_STORE` (else the file store under
#   `PLATFORM_DIR`), the objects by `OBJECTS` (else files under it) — a box's and a cluster's alike.
# - `console(env)` — the console of every spec in `SPEC_DIR` (the boundary's step 6: it was a subsystem's verb, with
#   routes of its own): `CONSOLE_ROOT` at `/`, the others mounted by name, one token — every spec's console grant — one
#   journal, the rows sealed that were written before a key, and the blob sweep.
# - `main(argv, env)` — the verbs above, from `SPEC_DIR`.
# ================================================================================================
from __future__ import annotations

import logging
import os
import threading
import time

from . import catalog, runtime

log = logging.getLogger("w2cplatform.host")
stop = threading.Event()


def step(owner, what: str, name: str, fn, failed: str | None = None) -> bool:
    """One step: True when it went. A failure is said with its trace the first time of a spell, "works again" after."""
    failing = owner.__dict__.setdefault("_host_failing", set())
    try:
        fn()
    except Exception:                                    # noqa: BLE001
        if name not in failing:
            failing.add(name)
            log.exception("%s", failed or f"{what}: {name} failed; the other steps of the pass go on, this one is tried "
                                           f"on every pass and said again when it works")
        return False
    if name in failing:
        failing.discard(name)
        log.warning("%s: %s works again", what, name)
    return True


def placement_pass(ctl, what: str | None = None) -> None:
    what = what or f"{ctl.spec.name} placement"
    with ctl.one_pass():
        step(ctl, what, "pass", lambda: ctl.pass_once(1),
             f"{what}: the pass raised (its own steps say what they could not do) — tried again on every pass")
        # What the layer above loses when this fails: its copy stops ageing forward. The age itself is on `/metrics`
        # (`<sub>_snapshot_age_seconds`), read from the store, so it survives a restart and any console can answer it.
        step(ctl, what, "publish", ctl.publish_snapshot,
             f"{what}: publishing the snapshot failed — the layer above is now reading a stale copy")


def controller_loop(ctl, env: dict | None = None, every: float = 5.0, journal: bool = True) -> None:
    """One controller process per subsystem, the same loop: unplace what was deleted, place what is new onto the
    workers it sees, move what a released slot left, bring one unit home if its server came back, publish the
    snapshot. Nothing else, ever. No port, no state: restarted at any moment, two of them agree by CAS. `journal`:
    whether it writes its journal into the events tree the environment names (a process whose unit gives it no
    write there — М11's controllers — says False, and its decisions are in its log only, as they were)."""
    env = os.environ if env is None else env
    tree = runtime.events_said(env) if journal else None
    if tree:                                             # a slot it frees, and why, in this server's journal (`journal.py`)
        from .journal import Journal
        ctl.journal = Journal(tree, f"{ctl.sub.name}controller", ctl.wall)   # its identity's (ADR-0030)
    if env.get("HUNG_MOVE_AFTER"):                       # how long a hung worker keeps its units (`Controller.hung_move_after`)
        ctl.hung_move_after = float(env["HUNG_MOVE_AFTER"])
    while not stop.is_set():
        placement_pass(ctl)
        stop.wait(every)


def sweep_turn(controllers) -> None:
    for c in controllers:
        def sweep(c=c):
            r = c.sweep_blobs()
            if r["deleted"]:
                log.info("swept %d blob(s) nothing names in %s", r["deleted"], c.spec.name)
        step(c, "the blob sweep", "sweep", sweep, f"the blob sweep failed in {c.spec.name} — nothing is reclaiming its blobs")


def sweep_loop(controllers, every: float = 60.0) -> None:
    while not stop.is_set():
        sweep_turn(controllers)
        stop.wait(every)


# The request family's rows, cleared by the console (`requests.py`): the answered ones every `CLEAR_EVERY` — a listing and
# the heartbeats, no row read — and every `SWEEP_EVERY` the reaper's look at every standing row.
def requests_loop(controllers, clear: float | None = None, sweep: float | None = None) -> None:
    from . import requests
    clear, sweep = clear or requests.CLEAR_EVERY, sweep or requests.SWEEP_EVERY
    swept = -1e18
    while not stop.is_set():
        due = time.monotonic() - swept >= sweep
        if due:
            swept = time.monotonic()
        requests.turn(controllers, sweep=due)
        stop.wait(clear)


def every(turn, seconds: float) -> None:
    """`turn()` every `seconds` until `stop`: what a console's housekeeping loop is (each turn says its own failures)."""
    while not stop.is_set():
        try:
            turn()
        except Exception:                                # noqa: BLE001
            log.exception("a housekeeping turn failed; tried again in %s s", seconds)
        stop.wait(seconds)


def run_resource(res, srv, every: float = 10.0, policy_every: float = 600.0) -> None:
    """A resource's life, its door `srv` already serving. Two jobs, two tries (feedback BI): a pass that reads the store
    must not stop the heartbeat — with the store away the resource stopped heartbeating, was called silent, and the units
    were moved off a server that was perfectly well."""
    try:                                                 # a store away at the start does not end the process
        res.heartbeat()                                  # (the review's eighth pass)
    except Exception:                                    # noqa: BLE001
        log.exception("resource heartbeat failed")
    # The beat on a thread of its own (the review's thirteenth pass, blocker 5): that this resource is here and who runs
    # on it, whatever the loop below is doing — a pass or a restore that hangs on a disk no longer silences the server.
    res.start_beat(stop)
    try:                                                 # outside the loop, in a try of its own (the review's seventh pass)
        log.info("restore: %s", res.restore())
    except Exception:                                    # noqa: BLE001
        log.exception("restore failed — the buckets peers hold of this server stay with them; the process goes on")
    log.info("resource %s on %s", res.server, srv.server_address)
    last_policy = 0.0
    try:
        while not stop.is_set():
            try:
                res.heartbeat()
            except Exception:                            # noqa: BLE001
                log.exception("resource heartbeat failed")
            try:
                if time.time() - last_policy >= policy_every:
                    last_policy = time.time()            # a pass that raised is tried in ten minutes, not in ten seconds
                    log.info("policy: %s", res.pass_())
            except Exception:                            # noqa: BLE001
                log.exception("resource pass failed")
            # What the restore left with peers, asked for again, its pause doubling up to ten minutes (`restore_due`).
            try:
                if res.restore_due():
                    log.info("restore again: %s", res.restore())
            except Exception:                            # noqa: BLE001
                log.exception("restore failed again; asked again later")
            stop.wait(every)
    finally:
        srv.shutdown()


# A process's two stores: the store by URL (`PLATFORM_STORE`; the file store under `PLATFORM_DIR` when it says none), opened
# with the role's writer and its grant, and the objects by URL (`OBJECTS`: a cluster's `cluster://`, a rented one's
# `s3+http://`, `cluster.objectstore.open_store`) or, when it says none, as files under the same root — a box's.
def stores(env: dict, writer: str | None = None, acl: list | None = None):
    from .objects import FsObjectStore
    from .variables import open_vars, store_url
    root = runtime.platform_dir(env)
    url = store_url(env, "file://" + os.path.join(root, "config"))
    vars_ = open_vars(url, writer=writer, acl={writer: acl} if writer else None) if writer else open_vars(url)
    if env.get("OBJECTS"):
        from .cluster.objectstore import open_store
        return vars_, open_store(env["OBJECTS"], vars_=vars_)    # the create-only keys: rows in THIS store, its rights
    return vars_, FsObjectStore(os.path.join(root, "objects"))


def controller(name: str, env: dict, journal: bool = True) -> None:
    from .spec import SpecController
    spec = catalog.spec(name, env)
    vars_, objects = stores(env, f"{spec.name}controller", spec.acl_controller())
    log.info("controller of %s, from %s", spec.name, env.get(catalog.SPEC_DIR))
    controller_loop(SpecController(spec, vars_, objects), env, journal=journal)


def resource(env: dict) -> None:
    from .resource import platform_resource, serve
    vars_, objects = stores(env)
    host, port = env.get("RESOURCE_HOST", "127.0.0.1"), int(env.get("RESOURCE_PORT", "8090"))
    res = platform_resource(runtime.events_root(env), runtime.server(env), env.get("RESOURCE_URL", f"http://{host}:{port}"),
                            vars_, objects)
    run_resource(res, serve(res, host, port))


# THE CONSOLE, FROM THE SPECS ALONE (the boundary's step 6: it was a subsystem's verb, with its own routes and its own
# list of what it fronts). Which subsystem is at `/` is the deployment's word (`CONSOLE_ROOT`), every other spec of
# `SPEC_DIR` is mounted under its name; one store token — the console grant of every spec (`acl_console`) — one journal,
# one index (the resources', merged). Rows written before this console had a key are sealed now, not at their next write
# (feedback CD): every spec's rows, and its tables that keep a secret. The blob sweep is the console's (the ACL says so).
def spec_console(ctls: dict, root_name: str, marks_root: str | None = None, index=None, wall=None, worst_failover: float = 0.0):
    """The console's `Mount` over controllers already built (`{sub: SpecController}`): `root_name` at `/`, every other
    under its name; one journal (the root's), one index — the resources', merged — for every mount."""
    from .console import Mount, SpecConsole
    from .eventdatabase import MergedIndex
    root_ctl = ctls[root_name]
    index = index or MergedIndex(root_ctl.objects, wall=wall or root_ctl.wall)
    m = Mount(SpecConsole(root_ctl, marks_root=marks_root, index=index, wall=wall, worst_failover=worst_failover))
    for n, c in ctls.items():
        if n != root_name:
            m.mount(n, SpecConsole(c, index=index, wall=wall))
            m.mounts[n].journal = m.root.journal                  # one journal for the process
    return m


def build_console(env: dict):
    """The console's `Mount` and its controllers, from `SPEC_DIR` and `CONSOLE_ROOT` — not served yet."""
    from .sealing import Sealer, seal_stored
    from .secrets import is_secret_field
    from .spec import SpecController
    specs = {s.name: s for s in catalog.load_dir(env[catalog.SPEC_DIR])}   # the deployment's directory: what this console fronts
    root_name = env.get("CONSOLE_ROOT", "")
    if root_name not in specs:
        raise ValueError(f"CONSOLE_ROOT={root_name!r} names no spec of {env.get(catalog.SPEC_DIR)} "
                         f"({', '.join(sorted(specs))}): the subsystem at `/` is the deployment's to say")
    from .door import KEYS_KEY, SIGNER_KEY
    vars_, objects = stores(env, "console", [a for s in specs.values() for a in s.acl_console()] + [SIGNER_KEY, KEYS_KEY])
    ctls = {n: SpecController(s, vars_, objects) for n, s in specs.items()}
    m = spec_console(ctls, root_name, runtime.events_root(env))
    seal_stored(Sealer.from_env(env), vars_,
                [s.sub.config(s.rows, "") for s in specs.values()]
                + [s.sub.config(t, "") for s in specs.values() for t, ts in s.table_specs.items()
                   if any(is_secret_field(f) for f in ts.fields)])
    return m, ctls


def console(env: dict) -> None:
    m, ctls = build_console(env)
    srv = m.serve(env.get("CONSOLE_HOST", "127.0.0.1"), int(env.get("CONSOLE_PORT", "8080")))
    log.info("console of %s on %s, with %s", m.root.spec.name, srv.server_address,
             ", ".join(m.mounts) or "nothing else")
    threading.Thread(target=sweep_loop, args=(list(ctls.values()),), daemon=True).start()
    threading.Thread(target=requests_loop, args=(list(ctls.values()),), daemon=True).start()
    stop.wait()
    srv.shutdown()


USAGE = "python3 -m w2cplatform controller <sub> | resource | console   (SPEC_DIR: the directory of <sub>.subsystem.yaml)"


def main(argv: list[str], env: dict | None = None) -> int:
    env = dict(os.environ if env is None else env)
    if not env.get(catalog.SPEC_DIR):
        log.error("%s is not set: the platform runs from the specs it is given and from nothing else — %s",
                  catalog.SPEC_DIR, USAGE)
        return 2
    catalog.load_dir(env[catalog.SPEC_DIR])
    if argv[:1] == ["controller"] and len(argv) == 2:
        controller(argv[1], env)
        return 0
    if argv == ["resource"]:
        resource(env)
        return 0
    if argv == ["console"]:
        try:
            console(env)
        except ValueError as e:                          # what is at `/` the deployment did not say: said, not a trace
            log.error("%s", e)
            return 2
        return 0
    log.error("%s", USAGE)
    return 2
