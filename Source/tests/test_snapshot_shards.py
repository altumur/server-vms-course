"""The snapshot's SHAPE: one object per worker, not one object per cluster.

Every other object the platform publishes is already sharded by its writer — a
heartbeat per worker, a resource heartbeat per server — and each one stays the
size of what that writer knows. The snapshot was the exception: one object
holding every unit in the cluster, published into a store with a ceiling. A
store may declare one (`limits.py`; the capped store here declares 64 KiB), and
the cluster's own design maximum is 600 units (12 workers x capacity 50). The
single object broke at about a third of that; a shard is what keeps the snapshot
inside whatever a store declares.

Sharded by the worker that holds the unit, it grows the way the cluster grows:
more units means more workers means more objects, each the size of one worker's
assignment. The arithmetic is measured below rather than asserted.
"""
import json

from w2cplatform.contract import Heartbeat
from tests.conftest import Box, controller, published_snapshot, testsub

CAP = 64 * 1024                       # a declared ceiling — 64 KiB, the one the shape was measured against
LABELS = ["vlan:north-a", "site:north", "floor:3"]
SPEC = testsub()                     # a unit is a named counter, `testsub/counters/<name>`


def _worker_alive(box, worker: str, server: str, capacity: int = 50):
    box.objects.put(SPEC.sub.heartbeat_key(worker),
                    Heartbeat(worker, box.wall(), [], {"server": server, "capacity": capacity,
                                                       "headroom": capacity, "labels": ",".join(LABELS)}).to_bytes())
    box.objects.put(f"platform/resources/{server}/heartbeat",
                    json.dumps({"server": server, "ts": box.wall(), "url": f"http://{server}", "units": {}}).encode())


def _cluster(box, counters: int, workers: int, capacity: int = 50):
    """A realistic cluster: counters named the way a person names them, with labels,
    on workers that heartbeat — so `server` in the snapshot is a real name and the
    bytes below are the bytes that would be published. Each name starts with its
    number, `c-0001-…` first — `_ids` reads it back."""
    ctl = controller(box, capacity=capacity)
    for i in range(workers):
        _worker_alive(box, f"w-{i}", f"srv-north-{i:02d}", capacity)
    for i in range(counters):
        ctl.create({"name": f"c-{i + 1:04d}-at-the-north-entrance-of-the-third-floor", "start": i, "labels": LABELS})
    return ctl


def _ids(rows) -> list[int]:
    return sorted(int(r["id"][2:6]) for r in rows)


def test_the_snapshot_is_one_object_per_worker():
    box = Box()
    ctl = _cluster(box, 6, workers=2, capacity=3)
    ctl.ensure_placed()
    ctl.publish_snapshot()
    keys = box.objects.list("testsub/snapshot/")
    assert keys == ["testsub/snapshot/w-0", "testsub/snapshot/w-1"]          # the workers, and nothing else
    # each shard holds that worker's assignment and says whose it is
    for key in keys:
        shard = json.loads(box.objects.get(key))
        assert shard["worker"] == key.rsplit("/", 1)[1]
        assert len(shard["counters"]) == 3 and all(r["worker"] == shard["worker"] for r in shard["counters"])
    # and merged, it is the same set of counters the cluster has
    merged = published_snapshot(box.objects, "testsub", "counters")
    assert _ids(merged["counters"]) == [1, 2, 3, 4, 5, 6]


def test_the_units_nobody_holds_have_a_shard_of_their_own():
    """They are not dropped and they are not mixed in with a worker's: a row with
    no worker is exactly what М12 must be able to see."""
    box = Box()
    ctl = _cluster(box, 4, workers=1, capacity=2)
    ctl.ensure_placed()                                               # capacity 2: two counters have nowhere to go
    ctl.publish_snapshot()
    assert box.objects.list("testsub/snapshot/") == ["testsub/snapshot/unplaced", "testsub/snapshot/w-0"]
    unplaced = json.loads(box.objects.get("testsub/snapshot/unplaced"))
    assert unplaced["worker"] is None and len(unplaced["counters"]) == 2
    assert all(r["worker"] is None for r in unplaced["counters"])


def test_a_worker_that_is_gone_stops_reporting_its_units():
    """Nothing in the platform deletes an object. A worker that is scaled in, or
    whose units moved away, would go on being reported to the domain out of the
    shard it left behind — so the pass writes it EMPTY instead."""
    box = Box()
    ctl = _cluster(box, 2, workers=2, capacity=1)
    ctl.ensure_placed()
    ctl.publish_snapshot()
    assert box.objects.list("testsub/snapshot/") == ["testsub/snapshot/w-0", "testsub/snapshot/w-1"]
    second = ctl.units()[1]["id"]
    ctl.move(second, "w-0", reason="w-1 scaled in")                   # w-1 now holds nothing
    ctl.publish_snapshot()
    assert box.objects.list("testsub/snapshot/") == ["testsub/snapshot/w-0", "testsub/snapshot/w-1"]   # the key stays…
    assert json.loads(box.objects.get("testsub/snapshot/w-1"))["counters"] == []                    # …empty
    merged = published_snapshot(box.objects, "testsub", "counters")
    assert _ids(merged["counters"]) == [1, 2]                         # each counter once, on w-0
    assert {r["worker"] for r in merged["counters"]} == {"w-0"}


def test_a_worker_may_not_be_called_unplaced():
    """`testsub/snapshot/` is the worker name space, and `unplaced` is reserved inside
    it. A reserved name needs a rule that reserves it, not a hope."""
    box = Box()
    ctl = _cluster(box, 1, workers=0)
    _worker_alive(box, "unplaced", "srv-north-00")
    ctl.ensure_placed()
    try:
        ctl.publish_snapshot()
        raise AssertionError("a worker shadowed the shard for the units nobody holds")
    except ValueError as e:
        assert "may not be called 'unplaced'" in str(e)


def test_the_shard_fits_where_the_one_object_did_not():
    """The measurement the shape exists for. Both numbers come from the real
    publisher, against a declared 64 KiB ceiling — nothing here is asserted from
    a table."""
    box = Box()
    ctl = _cluster(box, 600, workers=12, capacity=50)                 # 12 workers x 50: the design maximum
    ctl.ensure_placed()
    ctl.publish_snapshot()
    shards = box.objects.list("testsub/snapshot/")
    assert len(shards) == 12
    biggest = max(len(box.objects.get(k)) for k in shards)
    one_object = len(json.dumps(ctl.snapshot()).encode())             # what it used to publish
    assert one_object > CAP, f"the single object fits after all ({one_object} B) — this test proved nothing"
    assert biggest <= CAP // 3, f"a shard is {biggest} B: the margin the heartbeat has is gone"
    print(f"\n  600 счётчиков: один объект {one_object / 1024:.0f} КиБ (потолок {CAP // 1024}), "
          f"крупнейший шард {biggest / 1024:.1f} КиБ — запас x{CAP / biggest:.1f}")


# -- what an empty `snapshot:` means, and what it used to mean --------------------------------------
def _spec(**over):
    from w2cplatform.spec import SubsystemSpec
    d = {"name": "thing", "unit": {"rows": "things", "id": "name", "fields": {
        "name": {"type": "string", "required": True}, "note": {"type": "string"},
        "api_secret": {"type": "string"}, "mask": {"type": "blob"}}},
        "placement": {"capacity": {"from": "capacity", "default": 50}}}
    d.update(over)
    return SubsystemSpec.from_dict(d)


def test_declaring_no_fields_is_not_declaring_every_field():
    """The defect this pair exists for: an empty list is falsy, so `snapshot: []`
    used to fall through to the default and publish everything. A spec author who
    declared "publish nothing" would have found out from М12."""
    assert _spec(snapshot=[]).snapshot == []
    assert _spec().snapshot == ["name", "note"]                  # absent: every field that may go
    assert "api_secret" not in _spec().snapshot and "mask" not in _spec().snapshot


def test_an_empty_snapshot_still_says_where_the_unit_is():
    """`[]` is not an empty object. Which unit is where is the snapshot's other
    job and the layer above is built on it; what `[]` buys is that nothing an
    operator typed leaves the cluster."""
    from w2cplatform.spec import SpecController
    box = Box()
    spec = _spec(snapshot=[])
    ctl = SpecController(spec, box.vars, box.objects, wall=box.wall)
    box.objects.put(spec.sub.heartbeat_key("w-1"),
                    Heartbeat("w-1", box.wall(), [], {"server": "srv-1", "capacity": 50, "headroom": 50}).to_bytes())
    ctl.create({"name": "one", "note": "the operator typed this"})
    ctl.ensure_placed()

    rows = ctl.snapshot()["things"]
    assert len(rows) == 1
    assert rows[0]["id"] == "one" and rows[0]["worker"] == "w-1" and rows[0]["server"] == "srv-1"
    assert "note" not in rows[0]                                 # …and nothing the operator typed


def test_a_bare_snapshot_key_is_refused_rather_than_guessed():
    """`snapshot:` with nothing after it is neither of the two meanings. Guessing
    either one is how a spec says something its author did not."""
    try:
        _spec(snapshot=None)
        raise AssertionError("a bare `snapshot:` was accepted")
    except ValueError as e:
        assert "`snapshot: []`" in str(e) and "leave the key out" in str(e)
