"""Volumes an operator declares, and the recorders that take them.

A volume used to be deployment — a directory, an `RESOURCE_ROOT` in a unit file, one
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
from tests.vmsconftest import Box, footage, recorder


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
                     ({"name": "s3", "kind": "network", "url": "s3://b/p", "quota_bytes": 1, "server": "srv-a"}, "may not have 'server'"),
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
    assert b.volume_pass() == ""                                       # past `until` by the wall — not by b's own watch
    box.clock.advance(a.slot_ttl + a.HOLD_SKEW)                        # the row stood still a whole term, by b's clock
    assert b.volume_pass() == "s3-main" and b.hold == "s3-main"

    # and the old holder learns it on its next pass: it is not fenced, it is a spare now
    assert a.volume_pass() == "" and a.hold is None and a.writing_allowed


def test_a_recorder_started_again_under_its_name_takes_its_volume_back_at_once():
    """Feedback CF. `r-1` is killed and systemd starts it again, under the same slot: it is the same worker. Its
    slot follows at once (`claim_slot(prefer=…)`), and now its volume does too — it used to wait out the hold's
    TTL, 45 s in which nothing on that volume was recorded. Anybody else still waits for the TTL, and the old
    instance learns on its next pass that the place is not its own any more.

    A DISK of its server, that is (the review's sixth pass, blocker 2): there the two instances are on one host, and
    the daemon keeps one writer per volume. A volume any box may serve is the next test: it follows the name only on
    its holder's own host."""
    box = Box()
    _disk(box, "disk-a")
    old, spare = _recorder(box, "r-1", "srv-a"), _recorder(box, "r-2", "srv-a")
    assert old.volume_pass() == "disk-a" and spare.volume_pass() == ""
    assert Slot.from_items("disk-a", box.vars.get("rec/holds/disk-a")[0]).by == "r-1"

    box.wall.advance(5)                                                # kill -9, and up again five seconds later
    again = _recorder(box, "r-1", "srv-a")
    assert spare.volume_pass() == ""                                   # not the spare's: the hold has not lapsed
    assert again.volume_pass() == "disk-a" and again.hold == "disk-a"
    assert old.volume_pass() == "" and old.hold is None                # the old instance is a spare now


def test_the_same_name_waits_out_a_network_volumes_hold_unless_it_was_let_go():
    """The review's sixth pass, blocker 2. The instance that takes a recorder's name may be on ANOTHER box, and the one
    it takes it from frozen, not dead, with its writer mounted — and the hold followed the name at once: no wait, which
    is the one thing the previous holder's write window is measured against. For a volume any box may serve the same
    name on another host waits like anybody: the row unchanged for `slot_ttl + HOLD_SKEW` by its own clock. A hold LET
    GO — the writer closed first — is still taken at once."""
    box = Box()
    _net(box, "s3-main")
    old = _recorder(box, "r-1", "srv-a", instance="box-a:10:aaaaaa")
    assert old.volume_pass() == "s3-main"
    box.wall.advance(5); box.clock.advance(5)
    # A live holder of another box keeps its name now (`NameOnAnotherBox`, the owner's decision of 4 Oct): the other
    # box's instance gets it once the controller gives it — the old one frozen, renewing nothing (the thirteenth pass).
    from tests.test_rec_volume import _name_given
    _name_given(box)
    again = _recorder(box, "r-1", "srv-b", instance="box-b:11:bbbbbb")   # the same slot, started on another box
    assert again.volume_pass() == "" and again.hold is None            # not at once: the old one may be writing
    assert old.store is not None and old._may_write_volume(old.store.row)
    box.wall.advance(again.slot_ttl); box.clock.advance(again.slot_ttl)
    assert again.volume_pass() == ""                                   # a term, and not yet the skew on top
    box.wall.advance(again.HOLD_SKEW); box.clock.advance(again.HOLD_SKEW)
    assert not old._may_write_volume(old.store.row)                    # the old one's window closed ten seconds ago
    assert again.volume_pass() == "s3-main" and again.hold == "s3-main"

    again.leave_volume("test: let go on purpose")                      # its writer closed, then the hold released
    third = _recorder(box, "r-3", "srv-c")
    assert third.volume_pass() == "s3-main"                            # a released hold: at once, whoever asks


def test_a_withdrawn_volume_stops_the_recordings_and_leaves_the_process_running():
    """The administrator deletes the archive. Whoever was writing into it has to
    stop — and keep its slot: this is a reassignment, not a zombie. The process
    is free to take another volume on the same pass it lost this one."""
    box = Box()
    for n in ("s3-cold", "s3-main"):
        _net(box, n)
    r = _recorder(box, "r-1", "srv-a")
    assert r.volume_pass() == "s3-cold"
    from w2cplatform.reconcile import Reconciler, Want
    r.reconciler = Reconciler(lambda k, w: True, lambda k: None)       # pretend it is recording one into it
    r.reconciler.once({"7-cold": Want(1)})

    volumes.delete(box.vars, "s3-cold")
    assert r.volume_pass() == "s3-main"                                # stopped there, took what was free
    assert r.reconciler.running() == {}                                   # and carries nothing of the old archive
    assert r.writing_allowed and r.name == "r-1"                     # still itself: not fenced, still its slot
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


def _route(rec):
    """The platform's console over the recorder's spec, as the page calls it: `route(method, path, body)` →
    `(status, reply)`. The tables are the spec's (`tables:`), served by the platform since the boundary's step 6."""
    import urllib.error
    import urllib.request
    from w2cplatform.console import SpecConsole
    srv = SpecConsole(rec, wall=rec.wall).serve("127.0.0.1", 0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def call(method, path, body=None):
        req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"null")
    call.server = srv
    return call


def test_the_console_declares_a_volume_and_says_who_holds_it():
    """The operator's side, over the route the page calls — the spec's table, served by the platform (the boundary's
    step 6: it was the VMS's route, `rec_routes`): declare an archive, see it unheld, see a recorder take it, and
    delete the declaration without deleting a byte of footage. The reply never carries the secret back."""
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    route = _route(rec)
    try:
        assert "rec/volumes/*" in REC_SPEC.acl_console()                   # `tables: {volumes}`, and nothing else granted
        status, body = route("POST", "/volumes", {"name": "s3-main", "kind": "network", "url": tempfile.mkdtemp(),
                                                  "quota_bytes": 64 << 20, "access_secret": "AKIA"})
        assert status == 201 and "access_secret" not in body["row"] and body["row"]["name"] == "s3-main"
        status, view = route("GET", "/volumes")
        assert status == 200 and [(v["name"], v["held_by"]) for v in view["volumes"]] == [("s3-main", None)]

        r = _recorder(box, "r-1", "srv-a"); r.volume_pass(); r.heartbeat_once()
        _, view = route("GET", "/volumes")
        assert view["volumes"][0]["held_by"] == r.instance                 # who holds the place: the platform's hold
        assert "access_secret" not in view["volumes"][0]

        status, body = route("DELETE", "/volumes/s3-main")
        assert status == 200 and body == {"deleted": "s3-main"}
        assert route("DELETE", "/volumes/s3-main")[0] == 404

        # a bad declaration is a 400 to the person who typed it, in the spec's words, not a 500 from the store
        status, body = route("POST", "/volumes", {"name": "s3-x", "kind": "network", "url": "s3://vms/y"})
        assert status == 400 and "quota_bytes" in body["detail"]
        status, body = route("POST", "/volumes", {"name": "vol-a", "kind": "local", "url": "/data/a", "quota_bytes": 1})
        assert status == 400 and "volumes needs 'server'" in body["detail"], body
    finally:
        route.server.shutdown()


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


def test_the_numbers_a_scaling_policy_reads():
    """`spare: 0` while something is declared and unserved is the one state that
    needs a person — so it has to be a number a machine can read too, or the
    person is the only mechanism there is.

    And the trap this test exists for: a spare reports zero capacity, which the
    load gauge would read as FULLY LOADED. Left in, one spare would demand the
    next one for ever."""
    from w2cplatform.console import SpecConsole
    from w2cplatform.metrics import text as spec_metrics

    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    for n in ("s3-main", "s3-cold"):
        _net(box, n)
    r, spare = _recorder(box, "r-1", "srv-a"), _recorder(box, "r-2", "srv-a")
    r.volume_pass(); r.heartbeat_once()
    spare.volume_pass(); spare.heartbeat_once()
    assert (r.volume, spare.volume) == ("s3-cold", "s3-main")

    con = SpecConsole(rec, wall=box.wall, )
    text = con.metrics_text()
    assert "rec_volumes_declared 2" in text and "rec_volumes_unserved 0" in text

    # both recorders hold an archive, so neither is spare and both are in the load gauge
    assert "rec_spare_workers 0" in text
    assert 'rec_worker_load{worker="r-1"}' in text and 'rec_worker_load{worker="r-2"}' in text

    _net(box, "s3-third")
    text = con.metrics_text()
    assert "rec_volumes_declared 3" in text and "rec_volumes_unserved 1" in text   # declared, and nobody free
    assert 'rec_workers_needed{labels=""} 1' in text               # …and no spare to take it: a process is missing

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
    assert 'rec_workers_needed{labels=""} 0' in text

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
    """The spec's table (`tables.volumes`) says it handles no credentials beyond the suffix rule — and
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
        assert ("url may not be stored as typed" in str(e) or "url is not an address" in str(e))

    for ok in ("/data/archive/cold", "file:///data/archive/cold", "s3://s3.example.com/vms/site-7",
               "https://s3.example.com/vms?region=eu-1"):
        volumes.write(Box().vars, {"name": "v", "kind": "network", "url": ok, "quota_bytes": 1})
    # …nor in its parameters (the eleventh review's sibling of a camera's `?pwd=`): refused, the value not repeated
    for bad in ("https://s3.example.com/vms?X-Amz-Credential=AKIAEXAMPLE", "s3://s3.example.com/vms?secret=wJalrXUtnFEMI"):
        try:
            volumes.write(Box().vars, {"name": "v", "kind": "network", "url": bad, "quota_bytes": 1})
            raise AssertionError(f"a url with credentials in its parameters was accepted: {bad}")
        except Refused as e:
            assert ("url may not be stored as typed" in str(e) or "url is not an address" in str(e)) and "AKIAEXAMPLE" not in str(e) and "wJalr" not in str(e), str(e)


# A bucket's key written into a volume's url every way the twelfth review (blocker 10) and the product's cross-check (7 of
# 7 spellings taken there) found it: a secret with `/`, `+`, `=`, `?`, `#` in it, no host at all, a secret that begins
# with digits, the signed and the named forms in the query and the path. The secret is `wJalr…`.
KEY_FORMS = [
    "s3://AKIAEXAMPLE:wJalr/XUtn@s3.example.com/eu-1/vms",
    "s3://AKIAEXAMPLE:wJalr+XUtn=@s3.example.com/eu-1/vms",
    "s3://AKIAEXAMPLE:wJalr?XUtn@s3.example.com/eu-1/vms",
    "s3://AKIAEXAMPLE:wJalr#XUtn@s3.example.com/eu-1/vms",
    "s3://AKIAEXAMPLE:wJalrXUtn@s3.example.com/eu-1/vms",
    "s3://AKIAEXAMPLE:wJalrXUtn",
    "s3://:wJalr/XUtn@s3.example.com/eu-1/vms",
    "s3://AKIAEXAMPLE:12/wJalr@s3.example.com/eu-1/vms",
    "s3://AKIAEXAMPLE:1234?wJalr@s3.example.com/eu-1/vms",
    "s3://s3.example.com/eu-1/vms?X-Amz-Credential=AKIAEXAMPLE%2F20261004&X-Amz-Signature=wJalr",
    "s3://s3.example.com/eu-1/vms?AWSAccessKeyId=AKIAEXAMPLE&Signature=wJalr",
    "s3://s3.example.com/eu-1/vms?aws_secret_access_key=wJalr",
    "s3://s3.example.com/eu-1/vms?secret=wJalr",
    "s3://s3.example.com/eu-1/vms?access_key=AKIAEXAMPLE&secret_key=wJalr",
    "s3://s3.example.com/eu-1/vms/access_key=AKIAEXAMPLE_secret_key=wJalr",
    "s3://s3.example.com/eu-1/vms;secret=wJalr",
    "https://s3.example.com/vms?x-amz-security-token=wJalr",
]


def test_a_key_in_a_volumes_url_is_refused_whatever_its_characters_and_an_old_row_is_said_nowhere():
    """The twelfth review, blocker 10 and major 15 — runs: the `@` was looked for before the first `/` only, and AWS
    secret keys hold `/`: `s3://AKIA:…/x@h/bucket` was taken and stood on `/volumes`; and a row declared before the rule
    (`?X-Amz-Credential=…`, `?secret=…`) stood there as stored, in the recorder's `volume_error`, its heartbeat and its log
    (`Port could not be cast … as '…'`). Now the url goes through the address rule (`secrets.address_refusal`): every
    form of `KEY_FORMS` is refused in words that never quote it; one put in the store as an older build would have is
    said by `volumes.served` (`GET /volumes`), and by a recorder that takes it — its heartbeat and its log — with the
    secret hidden (`hide_in_url`, `archive.volume_params`)."""
    import logging
    from vms.archive import volume_params
    box = Box()
    for url in KEY_FORMS:
        try:
            volumes.write(Box().vars, {"name": "v", "kind": "network", "url": url, "quota_bytes": 1})
            raise AssertionError(f"a key rode in on a volume's url: {url}")
        except Refused as e:
            assert ("url may not be stored as typed" in str(e) or "url is not an address" in str(e)) and "wJalr" not in str(e) and "XUtn" not in str(e), (url, str(e))
    said = []
    h = logging.Handler()
    h.emit = lambda r: said.append(r.getMessage())
    logging.getLogger().addHandler(h)
    try:
        for i, url in enumerate(KEY_FORMS[:3] + KEY_FORMS[9:10]):              # stored before the rule
            box.vars.put(volumes.key(f"old{i}"), volumes.Volume.from_items(
                f"old{i}", {"kind": "network", "url": url, "quota_bytes": str(64 << 20)}).to_items())
            r = _recorder(box, f"r-old{i}", "srv-a")
            r.volume_pass()
            hb = r.heartbeat_extra()
            assert "wJalr" not in json.dumps(hb, default=str) and "XUtn" not in json.dumps(hb, default=str), (url, hb)
            try:
                volume_params(url)
            except ValueError as e:
                assert "wJalr" not in str(e) and "XUtn" not in str(e), str(e)
        shown = volumes.served(box.vars, REC_SPEC.sub, box.wall())["volumes"]
        assert len(shown) == 4 and "wJalr" not in json.dumps(shown) and "XUtn" not in json.dumps(shown), shown
    finally:
        logging.getLogger().removeHandler(h)
    assert said and not [s for s in said if "wJalr" in s or "XUtn" in s]


def test_a_recorder_that_holds_an_archive_is_not_a_spare():
    """Taking a volume and opening it are two moments, and on a bucket whose
    previous writer is still letting go the gap is most of a minute. A process
    counted spare in that gap is a spare the operator is promised and the
    scaling policy will not ask to replace — and both numbers heal themselves,
    which is exactly when nobody notices."""
    from w2cplatform.console import heartbeats

    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    _net(box, "s3-main")
    spare_workers = lambda c: c.placeless_live(heartbeats(c.objects, "rec/"))   # the platform's: no place, no hold (`placement.places`)

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
    from tests.vmsconftest import OBSD_LINGER_MS
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
    from vms.obsd import ObsdError
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


def test_a_pinned_recorder_whose_volume_will_not_open_is_not_a_place_to_put_a_recording():
    """`$VOLUME` pins the volume: nothing to hand back, nowhere else to go. What the recorder CAN do is say so —
    the error in its heartbeat and no capacity, as a spare — so the controller places nothing on it."""
    box = Box()
    open(os.path.join(box.root, "nope"), "wb").write(b"")                  # a FILE where the disk's directory should be
    _disk(box, "bad", url=os.path.join(box.root, "nope", "deeper"))
    r = recorder(box, "r-1", "srv-a", acl=False, env={"VOLUME": "bad"})
    assert r.volume_pass() == "bad" and r.volume_error and r.capacity == 0
    volumes.write(box.vars, {"name": "bad", "kind": "local", "url": os.path.join(box.root, "good"), "server": "srv-a",
                             "quota_bytes": 64 << 20})                      # the administrator fixes the row
    r.engine_lost = True                                                   # (the pinned branch opens again when asked to)
    assert r.volume_pass() == "bad" and r.volume_error == "" and r.capacity == r.full_capacity


def test_a_volume_another_writer_still_holds_is_said_to_be_busy():
    """Busy is not away: the daemon answers, and it says somebody else's writer is in the volume — a recorder of
    the same volume in its grace. Kept and said as busy, so the operator reads "wait" and not "the network"."""
    import time
    from tests.vmsconftest import OBSD_LINGER_MS, store
    box = Box()
    url = _disk(box, "shared")
    other = store("shared", path=url.replace("file://", ""), owner="rec:somebody-else")
    r = recorder(box, "r-1", "srv-a", acl=False)
    assert r.volume_pass() == "shared" and r.store is None
    assert r.archive_failure == "busy" and r.heartbeat_extra()["archive_failure"] == "busy"
    other.close()
    time.sleep(OBSD_LINGER_MS / 1000 + 0.3)
    assert r.volume_pass() == "shared" and r.store is not None and r.archive_failure == ""


# -- the review's third pass ---------------------------------------------------------------------------------------

def test_a_network_volumes_secret_sealed_by_the_console_is_opened_by_the_recorder_with_the_key():
    """Blocker 3, end to end: the console seals `access_secret` to the row `rec/volumes/<name>`; the recorder opened it
    without the row — it never opened — and had no key in its unit either, so the bucket was handed the ciphertext.
    The recorder opens it with the key and the row now. And a recorder WITHOUT the key does not die of it: the
    volume is not written, its status says why, and the pass — the heartbeat with it — goes on."""
    from w2cplatform.sealing import is_sealed, new_key_file
    box = Box()
    key = os.path.join(tempfile.mkdtemp(), "platform.key")
    new_key_file(key)
    os.environ["SECRETS_KEY"] = key
    try:
        rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    finally:
        del os.environ["SECRETS_KEY"]
    route = _route(rec)
    try:
        status, _ = route("POST", "/volumes", {"name": "s3", "kind": "network", "url": tempfile.mkdtemp(),
                                               "quota_bytes": 64 << 20, "access_key": "AKIA", "access_secret": "wJalr"})
    finally:
        route.server.shutdown()
    assert status == 201 and is_sealed(box.vars.get("rec/volumes/s3")[0]["access_secret"])

    nokey = _recorder(box, "r-1", "srv-a")                             # `env={}`: no SECRETS_KEY
    nokey.lease_pass(); nokey.heartbeat_once()                         # neither raises
    hb = nokey.heartbeat_extra()
    assert nokey.store is None and nokey.capacity == 0 and "SECRETS_KEY" in hb["volume_error"]
    nokey.leave_volume("test: the operator gives it to a recorder with the key")

    r = _recorder(box, "r-2", "srv-b", env={"SECRETS_KEY": key})
    r.lease_pass()
    assert r.volume == "s3" and r.store is not None and r.volume_error == ""
    assert r.store.secret == "wJalr" and r.store.access_key == "AKIA"   # what the daemon is given among the parameters


def test_a_network_volume_is_mounted_only_on_a_hold_confirmed_at_the_mount():
    """The hold was stamped when the whole pass ended, and the mount did not look again: a remount whose old writer
    took a minute to close mounted a volume whose hold had lapsed and been taken — two writers in one ring, which
    the engine's lock on an s3 volume does not reliably stop (a lease without fencing, the engine's owner says). The
    hold is renewed at the moment of the mount now, and a mount the store does not confirm does not happen."""
    box = Box()
    _net(box, "net")
    r = _recorder(box, "r-1", "srv-a")
    r.lease_pass()
    assert r.volume == "net" and r.store is not None
    r2 = _recorder(box, "r-2", "srv-b")
    real_close = r._close_store

    def slow_close(quiet=False, wait=None):                            # the old writer's close takes a minute…
        real_close(quiet, wait)
        if r2.hold is None:
            assert r2.claim_hold(["net"]) is None                      # (r2 looks: renewed a moment ago, r-1's)
            box.wall.advance(60); box.clock.advance(60)
            assert r2.claim_hold(["net"]) == "net"                     # …the hold lapses, and another recorder takes it
    r._close_store = slow_close
    r._lost_engine()
    r.lease_pass()
    r._close_store = real_close
    assert r.store is None and r.hold is None and r.volume == ""       # not mounted on a hold that is not ours
    r2.lease_pass()
    assert r2.volume == "net" and r2.store is not None                 # one writer: the one whose hold it is


def test_the_boxs_own_volume_keeps_the_size_it_has_and_a_smaller_quota_waits_for_a_second_word():
    """The size of the box's own volume was recomputed at every start from the disk's free space, published as its
    size, and offered by the console to declare it at: a disk the ring had filled offered a gigabyte, and declaring
    it shrank a volume of terabytes — the oldest footage gone. The size is the volume's own now, and a quota below
    it is applied only when the row says `shrink_confirmed` with the same number; a larger one, at once."""
    box = Box()
    r = _recorder(box, "r-1", "srv-a", default_quota=64 << 20)
    r.lease_pass()
    assert r.store.formatted and r.heartbeat_extra()["archive_quota"] == 64 << 20
    r.after_stop()
    again = _recorder(box, "r-1", "srv-a", default_quota=16 << 20)    # the disk filled: the guess is smaller today
    again.lease_pass()
    assert not again.store.formatted and again.store.quota == 64 << 20
    assert again.heartbeat_extra()["archive_quota"] == 64 << 20        # what the console offers: the size it HAS

    row = {"name": "srv-a", "kind": "local", "url": again.default_url, "server": "srv-a", "quota_bytes": 32 << 20}
    volumes.write(box.vars, row)
    again.lease_pass()
    assert again.volume == "srv-a" and again.store.size() == 64 << 20  # not shrunk on one word…
    hb = again.heartbeat_extra()
    assert "shrink_confirmed" in hb["quota_note"]
    # …and the heartbeat says the size it HAS and the shrink that waits, for the console to show — not the declared
    # number as if it were done (the review's fourth pass)
    assert hb["volume_quota"] == 64 << 20 and hb["shrink_pending"] == 32 << 20
    volumes.write(box.vars, {**row, "shrink_confirmed": 32 << 20})
    again.lease_pass()
    hb = again.heartbeat_extra()
    assert again.store.size() == 32 << 20 and "quota_note" not in hb and "shrink_pending" not in hb   # …on two
    assert hb["volume_quota"] == 32 << 20
    from w2cplatform.eventdatabase import EventIndex                  # and the recorder says when the engine did it
    [shrunk] = [e for e in EventIndex(box.resource_root, "srv-a", wall=box.wall).query(0, box.wall() + 1, subsystem="rec")["events"]
                if e["kind"] == "archive.volume.shrunk"]
    assert shrunk["volume"] == "srv-a" and shrunk["was"] == 64 << 20 and shrunk["quota_bytes"] == 32 << 20

    def refused(size):
        from vms.obsd import ObsdError
        raise ObsdError(5, "WRITER_RESIZE", "the disk said no")
    real_resize, again.store.resize = again.store.resize, refused
    volumes.write(box.vars, {**row, "quota_bytes": 128 << 20})
    again.lease_pass()
    assert "refused" in again.heartbeat_extra()["resize_error"]       # said, and asked again on the next pass
    again.store.resize = real_resize
    volumes.write(box.vars, {**row, "quota_bytes": 128 << 20})
    again.lease_pass()
    assert again.store.size() == 128 << 20                             # a larger ring takes nothing away: at once

    # `shrink_pending` is said ONLY while a shrink waits for its second word: an int, the bytes declared — and gone with
    # the volume it was about when the recorder leaves it (it stayed, the name of a wait nobody had any more)
    volumes.write(box.vars, {**row, "quota_bytes": 64 << 20})
    again.lease_pass()
    hb = again.heartbeat_extra()
    assert hb["shrink_pending"] == 64 << 20 and type(hb["shrink_pending"]) is int and again.store.size() == 128 << 20
    again.leave_volume("the test leaves it")
    assert "shrink_pending" not in again.heartbeat_extra() and "quota_note" not in again.heartbeat_extra()


def test_a_new_volume_without_a_quota_is_sized_by_the_disk_the_daemon_writes_to():
    """The review's fourth pass. The box's own volume, with no `ARCHIVE_QUOTA_BYTES`, was formatted at a share of the
    disk the RECORDER measured — in its container, where `/data/volume` is not mounted: the container's system SSD, not
    the data disk, and that size stood from then on as the volume's own. The daemon opens the path, so the daemon is
    asked, before `FORMAT`: `VOLUME_SPACE` of the directory, or of the nearest one above it that exists.

    How FULL the disk is, is the test's own (the review's sixth pass): the size was compared with a share of the free
    space this machine happened to have, and on a disk three quarters full — a neighbour writing — the share is the
    floor of one gigabyte and the test failed. The daemon's answer stands for the path and the disk's size; what is
    free on it is said here: half."""
    import shutil
    from collections import namedtuple
    from vms.obsd import Volume
    from vms.recworker import RecWorker
    box = Box()
    real, real_share, real_space, given = shutil.disk_usage, RecWorker._share_of_space, Volume.space, []
    ssd = namedtuple("usage", "total used free")(200 << 30, 190 << 30, 10 << 30)
    shutil.disk_usage = lambda path: ssd                               # what a container would have measured
    RecWorker._share_of_space = staticmethod(lambda space, low=0.75: given.append(space) or real_share(space, low))

    def half_free(vol):                                                # the daemon's disk, half of it free
        got = real_space(vol)
        return {**got, "free": int(got["capacity"]) // 2, "available": int(got["capacity"]) // 2}
    Volume.space = half_free
    try:
        r = _recorder(box, "r-1", "srv-a", default_quota=0)
        r.lease_pass()
        assert r.store is not None and r.store.formatted
        space = r.store.space_where()                                  # the daemon's numbers for the volume's disk
        from vms.archive import Archive
        from tests.vmsconftest import obsd_session
        deep = Archive(f"file://{box.root}/a/b/volume", "deep", 0, "rec:deep", obsd_session("deep"))
        assert deep.space_where()["capacity"] == space["capacity"]    # not there yet: the nearest directory above it
    finally:
        shutil.disk_usage, RecWorker._share_of_space, Volume.space = real, staticmethod(real_share), real_space
    assert [g["capacity"] for g in given] == [space["capacity"]] != [ssd.total]
    assert space["capacity"] > 16 << 30, "the suite's temp directory is on a disk too small to tell a share from the floor"
    assert r.store.quota == real_share(given[0])
    assert abs(r.store.quota - space["capacity"] // 4) <= 1            # a quarter: up to the low mark of a disk half full
    assert r.heartbeat_extra()["archive_quota"] == r.store.quota       # what the console offers: the size it has


def test_a_hold_renewed_by_a_box_whose_clock_is_behind_is_not_taken_from_it():
    """The review's fourth pass, Т-M5. A hold was taken when the wall clock HERE passed the `until` the holder wrote by
    ITS wall clock: a holder a minute behind, renewing every pass, looked lapsed to the spare — two writers in one
    ring. A hold of somebody else's is stale when this process has watched its row stand still for a whole term, by
    its own monotonic clock: renewed, it is not taken whatever the clocks say; let go of, it is — a term later."""
    box = Box()
    _net(box, "net")
    behind, spare = _recorder(box, "r-1", "srv-a"), _recorder(box, "r-2", "srv-b")
    behind.wall = lambda: box.wall() - 60                              # its clock a minute behind everybody's
    assert behind.volume_pass() == "net" and spare.volume_pass() == ""
    for _ in range(6):                                                 # two minutes, a pass every twenty seconds
        box.wall.advance(20); box.clock.advance(20)
        assert behind.volume_pass() == "net"                           # it renews: `until` is in the past by the spare's wall
        assert spare.volume_pass() == "" and spare.hold is None        # …and the row moves: not stale
    for _ in range(2):                                                 # it stops renewing
        box.wall.advance(20); box.clock.advance(20)
        assert spare.volume_pass() == ""                               # forty seconds of a still row: not yet a term
    box.wall.advance(20); box.clock.advance(20)
    assert spare.volume_pass() == "net"                                # past a term and the skew, by the spare's own clock


def test_one_garbled_hold_row_is_that_volumes_trouble_and_nobody_elses():
    """The review's sixth pass, beside the garbled slot row. Every claim parsed every candidate's hold row bare: one
    with a word for a number — a hand edit — raised out of the claim, and a recorder took no volume at all; the
    console's list of volumes failed whole on the same row. It is that place's trouble now: no candidate until it is
    mended, counted in the heartbeat (`holds_garbled`), named on the volumes page. And the row of a volume this
    recorder HOLDS, garbled under it, is not a row naming somebody else: the renewal writes it whole again."""
    from w2cplatform.contract import Heartbeat
    garbled_row = {"holder": "somebody", "until": "soon", "released": "false", "gen": "1"}
    box = Box()
    _disk(box, "a-bad"); _disk(box, "b-good")
    box.vars.put("rec/holds/a-bad", garbled_row)
    r = _recorder(box, "r-1", "srv-a")
    counter = type(r).heartbeat.__globals__["HOLDS"].counts              # the module the workers run on (`test_portability`)
    before = counter.get("rec", 0)
    assert r.volume_pass() == "b-good" and r.store is not None           # it raised `ValueError` here
    assert box.vars.get("rec/holds/a-bad")[0] == garbled_row             # left for a person to mend
    assert counter.get("rec", 0) > before
    r.heartbeat_once()
    assert Heartbeat.from_bytes(box.objects.get(REC_SPEC.sub.heartbeat_key("r-1"))).extra["holds_garbled"] == counter["rec"]
    rows = {v["name"]: v for v in volumes.served(box.vars, REC_SPEC.sub, box.wall(), objects=box.objects)["volumes"]}
    assert rows["b-good"]["served_by"] and "rec/holds/a-bad) does not parse" in rows["a-bad"]["why"]
    assert set(volumes.holders(box.vars, REC_SPEC.sub)) == {"b-good"}

    box.vars.put("rec/holds/b-good", garbled_row)                        # …and its own, garbled under it
    box.wall.advance(8); box.clock.advance(8)
    with r.guarded("pass"):
        box.wall.advance(30); box.clock.advance(30)
        assert r.stand_in_once()                                         # the stand-in neither raises nor mends
        assert box.vars.get("rec/holds/b-good")[0] == garbled_row
    assert r.volume_pass() == "b-good" and r.hold == "b-good"            # not taken for somebody else's: kept
    mended = Slot.from_items("b-good", box.vars.get("rec/holds/b-good")[0])
    assert mended.holder == r.instance and mended.until == box.wall() + r.slot_ttl and mended.by == "r-1"
    box.vars.put("rec/holds/b-good", garbled_row)
    r.leave_volume("test: let go of it")
    assert Slot.from_items("b-good", box.vars.get("rec/holds/b-good")[0]).released   # a release writes it whole too


def test_a_renewal_that_lost_to_one_of_ours_keeps_the_hold():
    """The review's fourth pass, a minor. The pass and a keep's `seal` both renew the hold; the one that lost the CAS
    took the conflict for the hold taken — let go of a fresh hold of its own and waited out a term for it. A conflict
    is answered by the row now: still ours is ours."""
    from w2cplatform.variables import Conflict
    box = Box()
    _net(box, "net")
    r = _recorder(box, "r-1", "srv-a")
    assert r.volume_pass() == "net"
    real_put = r.vars.put

    def renewed_meanwhile(key, items, cas=None):
        if key == "rec/holds/net" and cas is not None:
            real_put(key, items)                                       # another thread of ours renewed it first…
            raise Conflict(key)                                        # …and this CAS lost to it
        return real_put(key, items, cas=cas)
    r.vars.put = renewed_meanwhile
    try:
        assert r.renew_hold() and r.hold == "net"
    finally:
        r.vars.put = real_put
    assert r.volume_pass() == "net" and r.store is not None


def test_a_volume_whose_directory_is_gone_is_not_made_again_empty_and_its_recordings_go_elsewhere():
    """The owner's decision of 4 Oct (the product's r24-names). A disk not mounted after a reboot leaves its mount point
    empty or gone, the engine answers "no volume there" — and the recorder FORMATTED a new, empty one in its place, on
    whatever disk the path now falls on, and recorded into it as if nothing had happened: weeks of footage invisible,
    the root disk filling. A volume ALREADY IN USE is one this subsystem has opened at that address before: the mark
    `rec/used/<volume>` `{url, at, by, instance, server}`, written at its first open. Missing now, it is not formatted:
    `volume.missing`, an alarm once an episode per recorder, the volume handed back with words, and the recordings go to
    another volume. Mounted back, it opens as it was. A volume never opened at this address — new, or declared again at
    another path — is formatted as before."""
    import time
    from w2cplatform.eventdatabase import EventIndex
    from tests.vmsconftest import OBSD_LINGER_MS
    box = Box()
    url = _disk(box, "disk-a")
    _disk(box, "disk-b")
    r = _recorder(box, "r-1", "srv-a")
    assert r.volume_pass() == "disk-a" and r.store.formatted
    mark = json.loads(box.objects.get(REC_SPEC.sub.used_key("disk-a")))
    assert mark["url"] == url and mark["by"] == "r-1" and mark["server"] == "srv-a", mark
    t = box.wall()
    footage(r.store, "7", 1, t - 60, t)
    r.session.vanish()                                                   # the box goes down
    time.sleep(OBSD_LINGER_MS / 1000 + 0.3)
    os.rename(url, url + ".unmounted")                                   # …and comes up without the disk

    box.wall.advance(5)
    again = _recorder(box, "r-1", "srv-a")                               # its unit starts it again
    assert again.volume_pass() == "disk-b", "a missing volume was formatted again in its place"
    assert not os.path.exists(url)                                       # nothing made where the disk was
    assert "volume_missing" not in again.heartbeat_extra()               # it writes into disk-b: nothing it cannot open
    spare = _recorder(box, "r-2", "srv-a")                               # a free recorder of this box asks for it too
    for _ in range(3):
        box.clock.advance(5); box.wall.advance(5)
        assert again.volume_pass() == "disk-b"
        assert spare.volume_pass() in ("", "disk-a") and spare.store is None and spare.capacity == 0
        assert not os.path.exists(url)
        # …and its heartbeat says WHICH, by name, a string: the rest — since when, why — is the journal's `volume.missing`
        assert spare.heartbeat_extra()["volume_missing"] == "disk-a"
        assert "volume_missing" not in again.heartbeat_extra()
    alarms = [e for e in EventIndex(box.resource_root, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="rec")["events"]
              if e["kind"] == "volume.missing"]
    assert len(alarms) == 2, alarms                                      # once each recorder that met it, not every pass
    assert all(a["class"] == "alarm" and a["volume"] == "disk-a" and a["url"] == url for a in alarms), alarms
    why = spare.volume_error
    assert "disk-a" in why and "not mounted" in why and "VOLUME_MISSING" not in why, why

    os.rename(url + ".unmounted", url)                                   # mounted back
    box.clock.advance(5); box.wall.advance(5)
    assert spare.volume_pass() == "disk-a" and spare.store is not None and not spare.store.formatted   # as it was
    assert spare.capacity == spare.full_capacity and spare.volume_error == ""
    assert "volume_missing" not in spare.heartbeat_extra()               # opened: not said any more
    assert spare.our_coverage("7") == [(t - 60, t)]

    _disk(box, "disk-a", url=url + "-new")                               # declared again at another address: a new volume
    assert spare.volume_pass() == "disk-a" and spare.store.formatted and spare.store.url == url + "-new"
    assert json.loads(box.objects.get(REC_SPEC.sub.used_key("disk-a")))["url"] == url + "-new"


def test_servers_carries_a_recorders_missing_volume_as_a_string_and_its_waiting_shrink_as_a_number():
    """`servers.status` over the recorder's heartbeat («Архитектор», the console by the specs' catalogue): a spec that
    declares `volume_missing` — a string, in `heartbeat.strings` — and `shrink_pending` — a number — gets each recorder's
    value on its row of `GET /servers` as the recorder said it: the volume's name, the bytes as an int; a recorder that
    says neither has neither. The spec is built here from the recorder's own, so the test does not wait on its bytes."""
    import yaml
    from w2cplatform.spec import SubsystemSpec
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vms", "rec.subsystem.yaml"),
              encoding="utf-8") as f:
        d = yaml.safe_load(f)
    declared = [{"field": "volume_missing", "title": "том не найден"},           # rec's spec as it is: its bytes
                {"field": "shrink_pending", "title": "уменьшение квоты не подтверждено"}]
    assert "volume_missing" in d["heartbeat"]["strings"] and d["servers"]["status"] == declared, d.get("servers")
    spec = SubsystemSpec.from_dict(d)
    box = Box()
    for w, server, extra in (("r-1", "srv-a", {"volume": "", "volume_missing": "disk-a"}),
                             ("r-2", "srv-a", {"volume": "disk-b", "shrink_pending": 32 << 20}),
                             ("r-3", "srv-b", {"volume": "disk-c"})):
        box.objects.put(spec.sub.heartbeat_key(w), Heartbeat(w, box.wall(), [], {"server": server, "capacity": 4,
                                                                                 "headroom": 4, **extra}).to_bytes())
    call = _route(SpecController(spec, box.vars, box.objects, wall=box.wall))
    try:
        st, out = call("GET", "/servers")
        assert st == 200 and out["status"] == declared, out
        rows = {w["worker"]: w["status"] for s in out["servers"].values() for w in s["workers"]}
        assert rows["r-1"] == {"volume_missing": "disk-a"}
        assert rows["r-2"] == {"shrink_pending": 32 << 20} and type(rows["r-2"]["shrink_pending"]) is int
        assert rows["r-3"] == {}                                           # nothing missing, nothing waiting: absent
    finally:
        call.server.shutdown()
