"""Volumes an operator declares, and the recorders that take them.

A volume used to be deployment — a directory, an `ARCHIVE` in a unit file, one
instance per disk. A network archive cannot be that: it is created in the
console, and no unit file is edited for it. So it is a row (`rec/volumes/<name>`)
and a hold (`rec/holds/<name>`), and these tests are about the seam between the
two: a declaration is not a place until somebody is holding it."""
import io
import json
import os
import tempfile

from w2cplatform.contract import Heartbeat, Slot
from w2cplatform.spec import Refused, SpecController
from vms import volumes
from vms.config import REC_SPEC
from vms.console import rec_routes
from tests.conftest import Box, footage, recorder


def _recorder(box, name, server, **kw):
    """A recorder with nothing pinned: `env={}` is the box with no VOLUME set."""
    return recorder(box, name, server, acl=False, **kw)


def _net(box, name, **kw):
    """A network volume. An address any box may serve — here a directory, which `obsd` opens like a bucket."""
    volumes.write(box.vars, {"name": name, "kind": "network", "url": tempfile.mkdtemp(prefix=f"{name}-"),
                             "quota_bytes": 64 << 20, **kw})


def _disk(box, name, server="srv-a", url=None):
    url = url or os.path.join(box.root, name)
    volumes.write(box.vars, {"name": name, "kind": "local", "url": url, "server": server, "quota_bytes": 64 << 20})
    return url


def _resource(box, server, total=0):
    box.objects.put(f"platform/resources/{server}/heartbeat",
                    json.dumps({"server": server, "ts": box.wall(), "url": f"http://{server}", "units": {},
                                "space": {"total": total, "free": total}}).encode())


def test_a_network_volume_needs_a_quota_and_a_local_one_needs_a_server():
    """The two kinds differ in the one place it matters. A local volume is a
    disk, and a disk belongs to a machine. A network volume is an address any
    machine can reach — and every volume is formatted as a ring of its quota,
    which a bucket's `statvfs` could not tell anyway: the size is given, not read."""
    box = Box()
    for bad, why in (({"name": "vol-a", "kind": "local", "url": "/data/a", "quota_bytes": 1}, "server"),
                     ({"name": "s3", "kind": "network", "url": "s3://b/p"}, "quota_bytes"),
                     ({"name": "s3", "kind": "network", "url": "s3://b/p", "quota_bytes": 1, "server": "srv-a"}, "server"),
                     ({"name": "../etc", "kind": "local", "url": "/data/a", "server": "srv-a",
                       "quota_bytes": 1}, "not a path"),
                     ({"name": "vol-a", "kind": "local", "url": "/data/a", "server": "srv-a"}, "quota_bytes")):
        try:
            volumes.write(box.vars, bad)
            raise AssertionError(f"accepted {bad}")
        except Refused as e:
            assert why in str(e), (bad, e)

    volumes.write(box.vars, {"name": "vol-a", "kind": "local", "url": "/data/a", "server": "srv-a", "quota_bytes": 10 ** 11})
    volumes.write(box.vars, {"name": "s3-main", "kind": "network", "url": "s3://vms/site-7", "quota_bytes": 10 ** 12,
                             "access_secret": "AKIA-and-the-rest"})
    assert [v.name for v in volumes.declared(box.vars)] == ["s3-main", "vol-a"]

    # the secret is stored and never read back out by the console's view
    assert box.vars.get(volumes.key("s3-main"))[0]["access_secret"] == "AKIA-and-the-rest"
    shown = volumes.served(box.vars, REC_SPEC.sub, box.wall())
    assert all("access_secret" not in row for row in shown["volumes"])


def test_who_may_serve_what():
    """A local volume has exactly one machine that can write to it; a network
    volume has any. That asymmetry is the whole arithmetic of spares: one spare
    per box absorbs one network volume per box."""
    box = Box()
    volumes.write(box.vars, {"name": "vol-a", "kind": "local", "url": "/data/a", "server": "srv-a", "quota_bytes": 10 ** 11})
    volumes.write(box.vars, {"name": "vol-b", "kind": "local", "url": "/data/b", "server": "srv-b", "quota_bytes": 10 ** 11})
    volumes.write(box.vars, {"name": "s3-main", "kind": "network", "url": "s3://vms/x", "quota_bytes": 10 ** 12})
    volumes.write(box.vars, {"name": "s3-old", "kind": "network", "url": "s3://vms/y", "quota_bytes": 10 ** 12,
                             "enabled": "false"})
    vols = volumes.declared(box.vars)

    assert volumes.servable(vols, "srv-a") == ["vol-a", "s3-main"]     # its own disk first, then what anybody may take
    assert volumes.servable(vols, "srv-b") == ["vol-b", "s3-main"]
    assert volumes.servable(vols, "srv-c") == ["s3-main"]              # a box with no disk of its own is still a candidate
    assert "s3-old" not in volumes.servable(vols, "srv-a")             # disabled is nobody's


def test_nothing_declared_is_the_box_as_it_always_was():
    """The migration, stated as a test: a recorder that is told nothing, on a
    cluster where nobody declared anything, is on one place named after its
    server — exactly what it was before volumes were rows."""
    box = Box()
    r = _recorder(box, "r-1", "srv-a")
    assert r.volume_pass() == "srv-a" and r.hold is None and r.capacity == r.full_capacity


def test_a_declared_volume_is_taken_by_one_recorder_and_the_other_is_a_spare():
    """The point of the whole arrangement. Two recorders, one declared archive:
    one takes it and IS that archive's recorder; the other carries nothing and
    says so — a spare is a running process with no place, not a failure."""
    box = Box()
    _net(box, "s3-main")
    a, b = _recorder(box, "r-1", "srv-a"), _recorder(box, "r-2", "srv-a")

    assert a.volume_pass() == "s3-main" and a.hold == "s3-main"
    assert b.volume_pass() == "" and b.hold is None                    # taken: this one is spare
    assert b.capacity == 0 and a.capacity == a.full_capacity

    a.heartbeat_once(); b.heartbeat_once()
    ctl = SpecController(REC_SPEC, box.vars, box.objects, wall=box.wall)
    assert ctl.place_of("r-1") == "s3-main"
    assert ctl.place_of("r-2") == ""                                   # NOT "srv-a": a spare is not the box's place
    assert ctl.idle_by_policy(["r-1", "r-2"]) == []                    # two places, one of them empty: neither idles

    # and a recording homed there is placed on the holder, because that is where the place is
    _resource(box, "srv-a")
    ctl.create({"name": "7-cloud", "cam": "7", "home": "s3-main"})
    ctl.ensure_placed()
    assert ctl.where("7-cloud") == "r-1" and "at home on s3-main" in ctl.placement("7-cloud").reason


def test_a_spare_picks_up_a_volume_whose_recorder_went_silent():
    """Why the hold is a lease and not an assignment. The process that held
    `s3-main` stops answering; the hold lapses; the spare takes it and the
    archive is served again — with nobody deciding anything."""
    box = Box()
    _net(box, "s3-main")
    a, b = _recorder(box, "r-1", "srv-a"), _recorder(box, "r-2", "srv-b")
    assert a.volume_pass() == "s3-main" and b.volume_pass() == ""

    box.wall.advance(a.slot_ttl + 1)                                   # r-1 stops renewing: crashed, or the box went away
    assert b.volume_pass() == "s3-main" and b.hold == "s3-main"

    # and the old holder learns it on its next pass: it is not fenced, it is a spare now
    assert a.volume_pass() == "" and a.hold is None and a.recording_allowed


def test_a_recorder_started_again_under_its_name_takes_its_volume_back_at_once():
    """Feedback CF. `r-1` is killed and systemd starts it again, under the same slot: it is the same worker. Its
    slot follows at once (`claim_slot(prefer=…)`), and now its volume does too — it used to wait out the hold's
    TTL, 45 s in which nothing on that volume was recorded. Anybody else still waits for the TTL, and the old
    instance learns on its next pass that the place is not its own any more."""
    box = Box()
    _net(box, "s3-main")
    old, spare = _recorder(box, "r-1", "srv-a"), _recorder(box, "r-2", "srv-b")
    assert old.volume_pass() == "s3-main" and spare.volume_pass() == ""
    assert Slot.from_items("s3-main", box.vars.get("rec/holds/s3-main")[0]).by == "r-1"

    box.wall.advance(5)                                                # kill -9, and up again five seconds later
    again = _recorder(box, "r-1", "srv-a")
    assert spare.volume_pass() == ""                                   # not the spare's: the hold has not lapsed
    assert again.volume_pass() == "s3-main" and again.hold == "s3-main"
    assert old.volume_pass() == "" and old.hold is None                # the old instance is a spare now


def test_a_withdrawn_volume_stops_the_recordings_and_leaves_the_process_running():
    """The administrator deletes the archive. Whoever was writing into it has to
    stop — and keep its slot: this is a reassignment, not a zombie. The process
    is free to take another volume on the same pass it lost this one."""
    box = Box()
    for n in ("s3-cold", "s3-main"):
        _net(box, n)
    r = _recorder(box, "r-1", "srv-a")
    assert r.volume_pass() == "s3-cold"
    r.reconciler.actual["7-cold"] = {"id": "7-cold"}                   # pretend it is recording one into it

    volumes.delete(box.vars, "s3-cold")
    assert r.volume_pass() == "s3-main"                                # stopped there, took what was free
    assert r.reconciler.actual == {}                                   # and carries nothing of the old archive
    assert r.recording_allowed and r.name == "r-1"                     # still itself: not fenced, still its slot
    assert volumes.holders(box.vars, REC_SPEC.sub)["s3-cold"].released  # let go on purpose, so the row says so

    # and withdrawing the last one is the migration branch, not a dead process: the box's own archive
    volumes.delete(box.vars, "s3-main")
    assert r.volume_pass() == "srv-a" and r.capacity == r.full_capacity


def test_the_console_says_which_archives_nobody_is_writing_into():
    """The number an operator watches. A volume nobody took is not an error and
    not a silence: `home` is a preference, so the footage would go somewhere else
    without a word — the console has to say the word instead."""
    box = Box()
    _net(box, "s3-main"); _net(box, "s3-cold")
    r = _recorder(box, "r-1", "srv-a")
    assert r.volume_pass() == "s3-cold"                      # one recorder, two archives: it takes the first by name

    view = volumes.served(box.vars, REC_SPEC.sub, box.wall())
    assert view["wanted"] == 2 and view["serving"] == 1       # the number an operator watches: two declared, one served
    by = {v["name"]: v for v in view["volumes"]}
    assert by["s3-main"]["served_by"] is None and "no recorder has taken it" in by["s3-main"]["why"]
    assert by["s3-cold"]["served_by"] == r.instance and by["s3-cold"]["why"] is None

    # the second one is served the moment a process exists for it — no deploy, no assignment
    r2 = _recorder(box, "r-2", "srv-a")
    assert r2.volume_pass() == "s3-main"
    assert volumes.served(box.vars, REC_SPEC.sub, box.wall())["serving"] == 2


class _Body:
    """The two things the extra route reads off a handler: a length and a stream."""
    def __init__(self, payload: bytes):
        self.headers, self.rfile = {"Content-Length": str(len(payload))}, io.BytesIO(payload)


def test_the_console_declares_a_volume_and_says_who_serves_it():
    """The operator's side, over the route the page calls: declare an archive,
    see it unserved, see a recorder take it, and delete the declaration without
    deleting a byte of footage."""
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    route = rec_routes(rec)

    assert "rec/volumes/*" in REC_SPEC.acl_console()                   # `tables: [volumes]`, and nothing else granted

    status, body = route(_Body(json.dumps({"name": "s3-main", "kind": "network", "url": tempfile.mkdtemp(),
                                           "quota_bytes": 64 << 20, "access_secret": "AKIA"}).encode()),
                         "POST", "/volumes", {})
    assert status == 201 and "access_secret" not in body["volume"]     # the reply never carries it back

    status, view = route(None, "GET", "/volumes", {})
    assert status == 200 and view["wanted"] == 1 and view["serving"] == 0 and view["spare"] == 0

    r = _recorder(box, "r-1", "srv-a"); r.volume_pass(); r.heartbeat_once()
    _, view = route(None, "GET", "/volumes", {})
    assert view["serving"] == 1 and view["spare"] == 0

    s = _recorder(box, "r-2", "srv-a"); s.volume_pass(); s.heartbeat_once()
    _, view = route(None, "GET", "/volumes", {})
    assert view["spare"] == 1 and view["spares"] == ["r-2"]            # one process ready for the next archive declared

    status, body = route(None, "DELETE", "/volumes/s3-main", {})
    assert status == 200 and "footage already written is untouched" in body["detail"]
    assert route(None, "DELETE", "/volumes/s3-main", {})[0] == 404

    # a bad declaration is a 400 to the person who typed it, not a 500 from the store
    status, body = route(_Body(json.dumps({"name": "s3-x", "kind": "network", "url": "s3://vms/y"}).encode()),
                         "POST", "/volumes", {})
    assert status == 400 and "quota_bytes" in body["detail"]


def test_the_console_offers_the_disk_this_box_already_records_into():
    """The first volume an operator ever declares should not be typed out. The
    box already says where it records (the recorder's heartbeat) and how big
    that filesystem is (the resource's), so the console offers exactly that,
    with the partition's own size as the capacity — a number the operator can
    then make smaller to fit a second volume on the same disk beside it.

    It is an OFFER: nothing here writes configuration on a process's behalf."""
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    route = rec_routes(rec)
    _resource(box, "srv-a", total=4 * 10 ** 12)
    r = _recorder(box, "r-1", "srv-a"); r.volume_pass(); r.heartbeat_once()

    _, view = route(None, "GET", "/volumes", {})
    own = f"file://{box.root}/volume"                               # the volume it formatted for itself, beside the resource's tree
    assert view["wanted"] == 0 and view["suggested"] == [
        {"name": "srv-a", "kind": "local", "url": own, "server": "srv-a", "quota_bytes": 64 << 20,   # the size it has
         "why": "this box records here and the disk is not declared as a volume"}]

    offer = {k: v for k, v in view["suggested"][0].items() if k != "why"}   # `why` is for the operator, not the row
    assert route(_Body(json.dumps(offer).encode()), "POST", "/volumes", {})[0] == 201
    _, view = route(None, "GET", "/volumes", {})
    assert view["wanted"] == 1 and view["suggested"] == []          # declared: nothing left to offer
    # …and declaring it moved nothing: the same volume, under the same name, so the same owner — the recorder
    # takes the declared row and goes on writing where it wrote
    first = r.store
    assert r.volume_pass() == "srv-a" and r.hold == "srv-a" and r.store is first and first.url == own

    # and now the disk can be split: half of it to a second volume beside the first
    status, _ = route(_Body(json.dumps({"name": "cold", "kind": "local", "url": box.archive + "/cold",
                                        "server": "srv-a", "quota_bytes": 2 * 10 ** 12}).encode()),
                      "POST", "/volumes", {})
    assert status == 201
    assert [v["name"] for v in route(None, "GET", "/volumes", {})[1]["volumes"]] == ["cold", "srv-a"]


def test_a_quota_is_a_ceiling_and_not_a_reservation():
    """What lets one partition hold two volumes. Each has a number of its own,
    so neither reads the whole disk's free space and believes it is its own —
    and neither is promised anything either: a volume gets the smaller of what
    its quota leaves and what the disk actually has."""
    from w2cplatform.resource import Resource

    box = Box()
    a, b = os.path.join(box.root, "vol-a"), os.path.join(box.root, "vol-b")
    res = Resource(None, "srv-a", "http://srv-a", box.vars, box.objects, wall=box.wall,
                   volumes={"vol-a": a, "vol-b": b}, quotas={"vol-a": 1000, "vol-b": 4000})
    os.makedirs(os.path.join(a, "rec"), exist_ok=True)
    open(os.path.join(a, "rec", "x"), "wb").write(b"." * 400)

    assert res.space("vol-a") == {"total": 1000, "free": 600, "used": 400, "full": 0.4}
    assert res.space("vol-b")["free"] == 4000                      # same partition, and not the same number
    assert res.space()["total"] == 5000                            # the box is the sum of its volumes, once each

    # the ceiling never promises more than the disk has: a probe that says the filesystem is nearly full
    # wins over a generous quota, because a quota is not storage
    res.space_probe = lambda path: (10 ** 6, 250)
    assert res.space("vol-b")["free"] == 250


def test_the_console_writes_out_the_command_and_does_not_run_it():
    """The operator's knob, and the shape it is allowed to have.

    A button that started a recorder would need a token to the orchestrator in
    the console — the one thing the platform keeps out of itself. What the
    console can do instead is stop making the operator translate: it knows how
    many processes are missing and which orchestrator started IT, so it writes
    the line out in that orchestrator's words. Running it stays a person's act."""
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    route = rec_routes(rec)
    for n in ("s3-a", "s3-b"):
        _net(box, n)

    r = _recorder(box, "r-1", "srv-a"); r.volume_pass(); r.heartbeat_once()
    _, view = route(None, "GET", "/volumes", {})
    assert view["needed"] == 1 and view["how"] == "systemctl start recworker@r-2"   # the next slot nobody holds
    # `live` rides along so that whatever acts on `needed` — the timer on a box, the scaler on a cluster —
    # gets both numbers from one reply and never asks the orchestrator for a second opinion
    assert view["live"] == 1

    # a spare covers the gap, so nothing is needed and nothing is suggested
    s = _recorder(box, "r-2", "srv-a"); s.volume_pass(); s.heartbeat_once()
    _, view = route(None, "GET", "/volumes", {})
    assert view["needed"] == 0 and view["how"] is None

    # on a cluster the same number comes out in the scheduler's words
    _net(box, "s3-c")
    os.environ["NOMAD_ALLOC_ID"] = "alloc-1"
    try:
        _, view = route(None, "GET", "/volumes", {})
        assert view["needed"] == 1 and view["how"] == "nomad job scale recworker 3"
    finally:
        del os.environ["NOMAD_ALLOC_ID"]


def test_the_numbers_a_scaling_policy_reads():
    """`spare: 0` while something is declared and unserved is the one state that
    needs a person — so it has to be a number a machine can read too, or the
    person is the only mechanism there is.

    And the trap this test exists for: a spare reports zero capacity, which the
    load gauge would read as FULLY LOADED. Left in, one spare would demand the
    next one for ever."""
    from w2cplatform.console import SpecConsole
    from vms.console import rec_metrics

    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    for n in ("s3-main", "s3-cold"):
        _net(box, n)
    r, spare = _recorder(box, "r-1", "srv-a"), _recorder(box, "r-2", "srv-a")
    r.volume_pass(); r.heartbeat_once()
    spare.volume_pass(); spare.heartbeat_once()
    assert (r.volume, spare.volume) == ("s3-cold", "s3-main")

    con = SpecConsole(rec, wall=box.wall, metrics_extra=rec_metrics(rec))
    text = con.metrics_text()
    assert "rec_volumes_declared 2" in text and "rec_volumes_unserved 0" in text

    # both recorders hold an archive, so neither is spare and both are in the load gauge
    assert "rec_spare_workers 0" in text
    assert 'rec_worker_load{worker="r-1"}' in text and 'rec_worker_load{worker="r-2"}' in text

    _net(box, "s3-third")
    text = con.metrics_text()
    assert "rec_volumes_declared 3" in text and "rec_volumes_unserved 1" in text   # declared, and nobody free
    assert "rec_recorders_needed 1" in text                        # …and no spare to take it: a process is missing

    # A shortage a process cannot fix, which is the runaway this gauge exists to stop. `srv-b-disk` is a
    # disk on a box that runs no recorder: starting one HERE does not make it servable, and a policy
    # reading `unserved` would ask for a worker, and another, and another, to its ceiling — every one of
    # them a spare that cannot help. One spare is proof the shortage is not a shortage of processes.
    volumes.delete(box.vars, "s3-third")                           # everything a recorder here could take is taken
    _disk(box, "srv-b-disk", "srv-b")
    idle = _recorder(box, "r-3", "srv-a")
    assert idle.volume_pass() == ""                                # nothing here for it: a spare
    idle.heartbeat_once()
    text = con.metrics_text()
    assert "rec_volumes_unserved 1" in text and "rec_spare_workers 1" in text
    assert "rec_recorders_needed 0" in text

    # …and a spare is kept OUT of the load gauge, where zero capacity would read as fully loaded
    assert 'rec_worker_load{worker="r-3"}' not in text
    assert 'rec_worker_load{worker="r-1"}' in text


def test_the_recorder_writes_into_the_volume_it_took():
    """Taking a place means writing into its volume. The writer follows the hold — otherwise a spare that took
    the network archive would go on filling the local disk, and the declaration would be a label on nothing. And
    a volume withdrawn mid-run keeps what was written into it: the writer is closed — its flush puts the last
    minutes there — before the next volume is opened."""
    from vms.archive import Archive
    box = Box()
    a, b = _disk(box, "vol-a"), _disk(box, "vol-b")
    r = _recorder(box, "r-1", "srv-a")
    assert r.volume_pass() == "vol-a" and r.store.url == a
    t = box.wall()
    footage(r.store, "7", 1, t - 600, t, seal=False)                # written, its block still open

    volumes.delete(box.vars, "vol-a")
    assert r.volume_pass() == "vol-b" and r.store.url == b
    assert r.store.units() == []                                    # nothing of vol-a's in vol-b
    left = Archive(a, "vol-a", 0, "", r.session).open(write=False)
    assert left.coverage("7") == [(t - 600, t)]                     # in vol-a, readable: the close flushed it


def test_a_volume_held_and_unwritable_is_not_served():
    """The worst failure this subsystem has, because every number says it is fine.

    A hold is fresh, so the console counted the archive served; the recorder sat
    on it and wrote nothing; the screen was green. Only the process that opened
    the volume knows it did not open, so it says so — and what reads that must
    not count the volume as served, must not call the recorder a place to put
    new recordings, and must not let go of the archive when there is nowhere
    else to go: a box that stops recording because of diagnostics is worse."""
    box = Box()
    good, bad = os.path.join(box.root, "good"), os.path.join(box.root, "nope", "deeper")
    open(os.path.join(box.root, "nope"), "wb").write(b"")          # a FILE where a directory is declared
    _disk(box, "a-broken", url=bad); _disk(box, "b-good", url=good)

    # `a-broken` sorts first, so it is tried first — and handed back, because there IS somewhere to go
    r = _recorder(box, "r-1", "srv-a")
    assert r.volume_pass() == "b-good" and r.volume_error == ""
    assert r.store.url == good
    assert volumes.holders(box.vars, REC_SPEC.sub)["a-broken"].released    # let go at once, not sat on

    # the second recorder has nowhere else: it keeps the broken archive, reports why, and offers no room
    s = _recorder(box, "r-2", "srv-a")
    assert s.volume_pass() == "a-broken" and s.volume_error
    assert s.capacity == 0                                         # not a place to put a recording
    s.heartbeat_once(); r.heartbeat_once()

    view = volumes.served(box.vars, REC_SPEC.sub, box.wall(), objects=box.objects)
    by = {v["name"]: v for v in view["volumes"]}
    assert view["wanted"] == 2 and view["serving"] == 1            # NOT two: a held archive nobody can write to
    assert by["a-broken"]["served_by"] is None
    assert "cannot write there" in by["a-broken"]["why"] and s.instance in by["a-broken"]["why"]
    assert by["b-good"]["served_by"] == r.instance

    # and it heals by itself the moment the archive is there: nothing to press, nothing to restart
    os.remove(os.path.join(box.root, "nope"))
    assert s.volume_pass() == "a-broken" and s.volume_error == "" and s.capacity == s.full_capacity
    s.heartbeat_once()
    assert volumes.served(box.vars, REC_SPEC.sub, box.wall(), objects=box.objects)["serving"] == 2


def test_the_key_never_goes_into_the_address():
    """`volumes.py` says it handles no credentials beyond the suffix rule — and
    the one thing it can still do is refuse the obvious way to lose them. A url
    is printed on the page, published in the recorder's heartbeat as `archive`
    and written into the row; a key inside it is the same secret in three public
    places, and the `*_secret` rule cannot help, because the field it guards is
    not the one carrying it."""
    box = Box()
    try:
        volumes.write(box.vars, {"name": "s3", "kind": "network", "quota_bytes": 1,
                                 "url": "s3://AKIAEXAMPLE:wJalrXUtnFEMI@s3.example.com/vms"})
        raise AssertionError("a url with credentials in it was accepted")
    except Refused as e:
        assert "never the key to it" in str(e)

    for ok in ("/data/archive/cold", "file:///data/archive/cold", "s3://s3.example.com/vms/site-7"):
        volumes.refuse({"name": "v", "kind": "network", "url": ok, "quota_bytes": 1})


def test_a_recorder_that_holds_an_archive_is_not_a_spare():
    """Taking a volume and opening it are two moments, and on a bucket whose
    previous writer is still letting go the gap is most of a minute. A process
    counted spare in that gap is a spare the operator is promised and the
    scaling policy will not ask to replace — and both numbers heal themselves,
    which is exactly when nobody notices."""
    from vms.console import spare_workers

    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    _net(box, "s3-main")

    r, s = _recorder(box, "r-1", "srv-a"), _recorder(box, "r-2", "srv-a")
    r.volume_pass(); s.volume_pass()
    r.heartbeat_once(); s.heartbeat_once()
    assert spare_workers(rec) == ["r-2"]                               # r-1 holds it, r-2 has nothing

    # now the heartbeat of the holder says it is nowhere — the window between taking and opening
    r.volume = ""
    r.heartbeat_once()
    assert rec.place_of("r-1") == ""                                   # the heartbeat alone would say "spare"
    assert spare_workers(rec) == ["r-2"]                               # the hold says otherwise, and it wins


# -- a restart, and the writer it left ------------------------------------------------------------------------

def test_a_restart_takes_its_volumes_writer_back_and_never_opens_the_local_one():
    """A recorder writing into a declared volume is killed and started again under its name. Nothing it wrote
    can go anywhere else — there is no queue on this box any more, the frames went into the volume as they came —
    and the new process looks at the volumes before it opens anything: it takes the same hold, names the same
    owner, and the daemon hands back the very writer the dead one left. The box's own volume is never formatted."""
    import time
    from tests.conftest import OBSD_LINGER_MS
    box = Box()
    cloud = _disk(box, "cloud")
    r = _recorder(box, "r-1", "srv-a")
    assert r.volume_pass() == "cloud"
    t = box.wall()
    footage(r.store, "7", 1, t - 60, t, seal=False)
    r.session.vanish()                                              # kill -9
    time.sleep(OBSD_LINGER_MS / 1000 + 0.3)

    box.wall.advance(5)
    again = _recorder(box, "r-1", "srv-a")
    assert again.volume_pass() == "cloud" and again.store.url == cloud and again.store.reattached
    assert not os.path.exists(os.path.join(box.root, "volume"))     # the local default was never touched
    again.store.seal()
    assert again.our_coverage("7") == [(t - 60, t)]


# -- away, or wrong: a transient failure and a permanent one are answered differently -----------------------
#
# The rule "a volume that will not open is handed back, if there is somewhere else to go" is right for a wrong
# key or a path that is a file, and wrong for a daemon that is restarting or a link that dropped for a minute:
# the recorder gives the volume up, its recordings are reshuffled, and a minute later it is back. The engine's
# status says which it is — and for a disk on this box, the kind of volume says the rest (`_write_into`).

def _away_at_open(url):
    """Make opening the volume at `url` fail as a network volume does when its network is down."""
    import vms.recworker as rw
    from vms.archive import ArchiveError
    real = rw.Archive

    class Opening(real):
        def open(self, write=True):
            if self.url == url:
                raise ArchiveError("away", "VOLUME_MOUNT_RW: IO_ERROR — the network is unreachable", "IO_ERROR")
            return real.open(self, write)
    rw.Archive = Opening
    return lambda: setattr(rw, "Archive", real)


def test_an_archive_that_is_away_at_open_is_kept():
    """A recorder that restarts in the middle of an outage opens its network archive and gets an I/O error. That
    is "away", not "wrong": handing the volume back would reshuffle its recordings for a link that is back in a
    minute. So the recorder keeps it — as a place, at full capacity — and the next pass tries again. It says the
    archive is away; it does not say the volume is not a place."""
    box = Box()
    _net(box, "cloud")
    url = volumes.declared(box.vars)[0].url
    restore = _away_at_open(url)
    try:
        r = _recorder(box, "r-1", "srv-a")
        assert r.volume_pass() == "cloud", "a volume that was away at open was handed back"
        assert r.capacity == r.full_capacity and r.volume_error == ""   # still a place: nothing moves off it
        hb = r.heartbeat_extra()
        assert hb["archive_error"] and hb["archive_failure"] == "away" and r.store is None
    finally:
        restore()
    assert r.volume_pass() == "cloud" and r.store is not None and r.archive_error == ""   # back: it opens


def test_an_archive_that_refuses_writes_mid_run_is_handed_back():
    """The other way round. The recorder holds `vol-a`, and the engine starts refusing samples with "permission
    denied" — a key that was revoked, a volume made read-only. Nothing will fix that but a person, so recording
    into it is recording into nothing. The volume is handed back and its recordings are free to go somewhere
    that works.

    And it does not take `vol-a` straight back on the next pass: opening may well succeed and the first write
    fail again — a recorder flapping between taking and dropping the same broken archive. It is left alone for
    a while, long enough for somebody to fix it."""
    from w2cplatform.obsd import ObsdError
    from vms.recworker import RecSink
    from vms.worker import fake_samples
    box = Box()
    _disk(box, "vol-a")
    r = _recorder(box, "r-1", "srv-a")
    assert r.volume_pass() == "vol-a"
    _disk(box, "vol-b")

    def refused(*a, **k):
        raise ObsdError(2, "PUT_MEDIA", "permission denied")
    r.store.put = refused
    sink = RecSink(r.store, "7", 1, on_lost=r._lost_engine, on_wrong=r._volume_refuses)
    try:
        sink.put(fake_samples(0, 1)[0])
        raise AssertionError("a refused sample was taken")
    except ObsdError:
        pass
    assert r.heartbeat_extra()["archive_failure"] == "wrong"

    assert r.volume_pass() == "vol-b", "a volume that refuses writes was kept"
    assert "vol-a" in r.heartbeat_extra()["refused"]
    box.wall.advance(30)
    r.leave_volume("test: let go of vol-b")                         # free again, and vol-a sorts first…
    assert r.volume_pass() != "vol-a", "it took the broken archive straight back"


def test_a_bucket_names_its_key_in_a_field_and_its_secret_sealed_never_in_the_address():
    """The url names the archive and nothing else (`refuse`); which key opens it is `access_key`, shown like a
    camera's login, and the key itself is `access_secret`, sealed. Both reach the daemon as parameters."""
    from vms.archive import volume_params
    box = Box()
    v = volumes.write(box.vars, {"name": "s3", "kind": "network", "url": "s3://s3.example.com/eu-1/vms/site-7",
                                 "quota_bytes": 1 << 30, "access_key": "AKIAEXAMPLE", "access_secret": "wJalr"})
    assert volumes.declared(box.vars)[0].access_key == "AKIAEXAMPLE" and v.enabled
    p = volume_params(v.url, "wJalr", v.access_key)
    assert (p["access_key"], p["secret_key"], p["bucket"], p["path"]) == ("AKIAEXAMPLE", "wJalr", "vms", "site-7")
    shown = volumes.served(box.vars, REC_SPEC.sub, box.wall())["volumes"][0]
    assert shown["access_key"] == "AKIAEXAMPLE" and "access_secret" not in shown
