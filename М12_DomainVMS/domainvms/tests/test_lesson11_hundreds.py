"""Lesson 11 — hundreds of small members.

The module stated its limit as "low hundreds of clusters' worth" and never measured it, because with server
rooms nobody reached it. Cameras as members reach it on the first site: three hundred clusters of one, a
tenth of them off. These tests are the measurement — calls counted, link time charged per call by `Meter`
— and the three changes it forced: one read of the snapshot per member, "where" from memory, and a pass
that neither waits for silent members in turn nor keeps asking them every five seconds.
"""
from cluster.variables import FakeVariables

from domain.api import ConsoleAPI
from domain.device import DeviceCluster
from domain.federation import DomainDirectory, Federation
from domain.pending import PendingEdits
from domain.readview import ReadView
from domain.scale import Meter
from tests.conftest import Clock, make_cluster

N, OFF = 300, 30


def _site(wall, n=N):
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    fed.add(north)
    devices = []
    for i in range(n):
        d = DeviceCluster(f"SN{i:04d}", FakeVariables(), wall=wall)
        d.boot()
        fed.add(d.cluster())
        devices.append(d)
    return fed, devices


def test_one_pass_asks_each_member_four_things_and_no_more():
    """A listing and a get for the heartbeats, a listing and a get for the snapshot shard. The pass used to
    read the snapshot twice — once for the rows, once for their age — which with three clusters nobody
    could see and with three hundred members is a third of the pass."""
    wall = Clock()
    fed, devices = _site(wall)
    meter = Meter()
    ReadView(meter.wrap_all(fed), wall=wall).refresh()
    per_member = {n: c for n, c in meter.calls.items() if n != "north"}
    assert set(per_member.values()) == {4} and len(per_member) == N
    assert meter.total_bytes < 350_000                   # the whole site, one pass: a few hundred kilobytes


def test_where_from_the_directory_scans_every_member_on_every_edit():
    """"Where is camera X" from the directory reads every member's snapshot — two calls a member, per
    camera. A bulk edit of fifty cameras on a site with thirty cameras off is thirty thousand calls and,
    with a two-second timeout per silent member, most of an hour. From the read view's memory it is none,
    and it is exactly as honest: found only where a member answered, the silent ones named."""
    wall = Clock()
    fed, devices = _site(wall)
    for d in devices[:OFF]:
        d.power_off()
    meter = Meter()
    metered = meter.wrap_all(fed)
    refs = [d.serial for d in devices[OFF:OFF + 50]]

    directory = DomainDirectory(metered, wall=wall)
    for ref in refs:
        assert directory.where(ref).found
    assert meter.total_calls == 50 * ((N - OFF) * 2 + OFF + 1)       # two per member that answers, one per silent one, one for north's empty listing
    assert meter.pass_time(1) > 3000                    # seconds: the edits wait for the scans, in turn

    view = ReadView(metered, wall=wall)
    view.refresh()
    meter.reset()
    answers = [view.where(ref) for ref in refs]
    assert meter.total_calls == 0
    assert all(a.found and not a.complete and len(a.unreachable) == OFF for a in answers)


def test_silent_members_are_waited_for_together_and_then_not_every_pass():
    """On a real link a member that is off costs the whole connect timeout. In turn, thirty of them are a
    minute, and a pass meant to run every five seconds takes a minute and a half. Read in lanes, they are
    waited for together. And a member that has been silent is asked again after a back-off, not every
    pass: it stays on the list — unreachable, with its last rows and their age — at no cost per pass."""
    wall = Clock()
    fed, devices = _site(wall)
    meter = Meter(latency=0.02, timeout=2.0)
    metered = meter.wrap_all(fed)
    view = ReadView(metered, wall=wall, lanes=16, backoff=5.0)
    view.refresh()                                       # everybody on: the view has seen them all
    for d in devices[:OFF]:
        d.power_off()

    meter.reset()
    ReadView(metered, wall=wall).refresh()
    assert meter.pass_time(lanes=1) > 80                # 270 × 4 × 20 ms + 30 × 2 s, one after another

    meter.reset()
    view.refresh()
    assert meter.pass_time(lanes=16) < 6                 # the timeouts overlap

    meter.reset()
    wall.advance(1)
    view.refresh()
    assert sum(meter.calls[d.name] for d in devices[:OFF]) == 0          # not asked: backing off
    assert meter.pass_time(lanes=16) < 2
    silent = [r for r in view.rows() if r.worker_state == "unreachable"]
    assert len(silent) == OFF                            # …and still listed, with their last known state


def test_reading_in_lanes_changes_the_time_and_nothing_else():
    wall = Clock()
    fed, devices = _site(wall, n=60)
    for d in devices[:6]:
        d.power_off()
    one, many = ReadView(fed, wall=wall), ReadView(fed, wall=wall, lanes=16)
    one.refresh(); many.refresh()
    key = lambda v: sorted((r.cluster, r.ref, r.worker_state) for r in v.rows())
    assert key(one) == key(many) and one.cluster_down_since.keys() == many.cluster_down_since.keys()


def test_a_member_that_comes_back_is_seen_within_the_back_off_ceiling():
    """The back-off doubles and stops at a ceiling, and the ceiling is the promise: a camera switched back
    on appears on the list no later than that. Without a ceiling, a camera off for a weekend would be
    asked about once an hour by Monday."""
    wall = Clock()
    fed, devices = _site(wall, n=10)
    d = devices[0]
    d.power_off()
    view = ReadView(fed, wall=wall, backoff=5.0, backoff_max=60.0)
    for _ in range(12):                                  # an hour of five-second passes, off throughout
        view.refresh()
        wall.advance(300)
    assert view.retry_at[d.name] - wall() <= 60.0
    d.boot()
    for _ in range(12):                                  # passes every 5 s for a minute
        view.refresh()
        wall.advance(5)
    assert d.name not in view.cluster_down_since


def test_a_bulk_edit_answered_from_memory_keeps_what_went_silent_since_the_pass():
    """Answering "where" from memory has one new case: a member that answered the last pass and is off by
    the time the edit is forwarded. That is Lesson 9's case with the order reversed, and it ends the same
    way — kept, 202 — not as an error from deep in the forward."""
    wall = Clock()
    fed, devices = _site(wall, n=20)
    view = ReadView(fed, wall=wall, lanes=8)
    view.refresh()
    by_name = {d.name: d for d in devices}
    pending = PendingEdits(fed.domain_holder.vars, wall)
    api = ConsoleAPI(view, lambda name: by_name[name], pending=pending, last_known=view.last_known)

    devices[3].power_off()                               # after the pass, before the edit
    results = [api.update_camera(d.serial, {"events_retention_days": 14}, idempotency_key=f"k{i}")
               for i, d in enumerate(devices)]
    kept = [r for r in results if r.get("pending")]
    assert [r["cluster"] for r in kept] == [devices[3].name]
    assert all(d.row().get("events_retention_days") == 14 for d in devices if d is not devices[3])


def test_lanes_are_real_threads_not_only_arithmetic():
    """`Meter` charges link time by arithmetic; this one waits for real. Forty members, each answering in
    twenty milliseconds: in turn that is most of a second, in sixteen lanes a small fraction of it."""
    import time as _time

    class Slow:
        def __init__(self, inner): self.inner = inner
        def get(self, *a): _time.sleep(0.005); return self.inner.get(*a)
        def list(self, *a): _time.sleep(0.005); return self.inner.list(*a)

    wall = Clock()
    fed, devices = _site(wall, n=40)
    slow = Federation()
    for c in fed.clusters.values():
        slow.add(type(c)(c.name, Slow(c.vars), Slow(c.objects), c.reaches, c.is_domain_holder))
    t0 = _time.monotonic(); ReadView(slow, wall=wall).refresh(); one = _time.monotonic() - t0
    t0 = _time.monotonic(); ReadView(slow, wall=wall, lanes=16).refresh(); many = _time.monotonic() - t0
    assert one > 0.7 and many < one / 3


class _CountingObjects:
    """The domain holder's object store, counting what members write into it."""

    def __init__(self, inner):
        self.inner, self.puts, self.bytes = inner, 0, 0

    def put(self, key, data):
        self.puts += 1; self.bytes += len(data); return self.inner.put(key, data)

    def get(self, key): return self.inner.get(key)
    def list(self, prefix): return self.inner.list(prefix)
    def delete(self, key): return self.inner.delete(key)


def test_when_members_report_the_pass_reads_one_store_and_the_cost_is_their_writes():
    """The uplink (`domain/uplink.py`), measured on the same site. Each member's agent leaves a report in the
    domain holder's store; the domain reads only that store. A member that is off costs the pass nothing —
    its copy is stale and says so at once, with no connection to wait on — and the pass is local calls. What
    the domain pays instead is writes: every report rewrites what changed — the heartbeat and the snapshot
    shard, both stamped with the time — and the `reported` mark."""
    from domain.agent import DomainAgent
    from domain.device import Ram
    from domain.uplink import member_copy
    wall = Clock()
    north, _ = make_cluster("north", domain=True)
    domain_store = Ram()                                 # the domain holder's objects; a prefix listing is the server's work
    store = _CountingObjects(domain_store)
    fed = Federation(); fed.add(north)
    agents, devices = [], []
    for i in range(N):
        d = DeviceCluster(f"SN{i:04d}", FakeVariables(), wall=wall)
        d.boot()
        fed.add(member_copy(d.name, domain_store, wall=wall))
        agents.append(DomainAgent(d.name, north.vars, d.flash, now=wall, domain_objects=store, published=d.local_objects()))
        devices.append(d)
    for a in agents:
        a.sync()
    meter = Meter(latency=0.001, timeout=0.001)          # the domain's own store: a local call, and no timeout to wait
    view = ReadView(meter.wrap_all(fed), wall=wall)
    view.refresh()                                       # the domain has seen every report once, by its clock
    wall.advance(60)
    for d in devices:
        d.publish()                                      # a minute later: new heartbeats, new shards
    store.puts = store.bytes = 0
    for a in agents[OFF:]:                               # a tenth of them are off and do not report
        a.sync()
    assert store.puts == 3 * (N - OFF)                   # heartbeat, shard, `reported` — per member, per report
    assert store.bytes < 400_000

    meter.reset()
    view.refresh()
    assert sum(meter.calls[d.name] for d in devices[:OFF]) == OFF        # one look at a stale mark each
    assert meter.pass_time(lanes=1) < 1.2                # 270 × 4 + 30 local calls, one after another
    assert meter.pass_time(lanes=16) < 0.1
    assert set(view.list(size=N)["clusters"][d.name] for d in devices[:OFF]) == {"unreachable"}
