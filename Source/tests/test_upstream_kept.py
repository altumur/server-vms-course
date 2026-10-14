"""ADR-0074: a persisted delivery acknowledgement belongs to one centre."""
import json

from tests.test_upstream_runtime import fixture, placement, source, topology, upstream
from vms.forwarder import Forwarder, UP_KEPT_FOR, keep_ups, up_key
from vms.ingest import Ingest


def saved(box, **over):
    return {"v": 2, "centre": "centre", "heard": int(box.wall() * 1000), "have": 42125, **over}


def write(box, value):
    box.objects.put(up_key("serial"), json.dumps(value).encode())


def restart(box, old, door, *, objects=None):
    local = Ingest("relay", ["http://relay/ingest"], lambda: {}, wall=box.wall)
    return Forwarder("relay", local, box.vars, old.dial, token_requests=door,
                     objects=box.objects if objects is None else objects)


def writing_fixture():
    box, fwd, door, centre, _ = fixture()
    fwd.load_up, fwd.save_up, fwd.drop_up = keep_ups(box.objects)
    poll = centre.poll
    centre.poll = lambda *a, **kw: {**poll(*a, **kw), "have": 42.125}
    return box, fwd, door, centre


def test_saved_acknowledgement_names_its_centre_and_restores_without_a_token_request():
    box, fwd, door, _ = writing_fixture()
    fwd.pass_once()
    assert json.loads(box.objects.get(up_key("serial"))) == saved(box)
    calls = len(door.calls)
    upstream(box, urls=("http://centre/another-address",))
    again = restart(box, fwd, door)
    assert again.local.up_have["serial"] == 42.125
    assert len(door.calls) == calls and not again.tokens.cached


def test_restart_after_centre_change_rejects_old_have_and_fresh_reply_names_new_centre():
    box, fwd, door, _ = writing_fixture()
    write(box, saved(box))
    topology(box, rev=2, centre="new-centre")
    upstream(box, member="new-centre", urls=("http://new-centre/ingest",))
    again = restart(box, fwd, door)
    assert "serial" not in again.local.up_have
    assert box.objects.get(up_key("serial")) is None
    again.pass_once()
    assert json.loads(box.objects.get(up_key("serial"))) == saved(box, centre="new-centre")


def test_first_reply_of_a_changed_centre_is_persisted_before_the_usual_write_period():
    box, fwd, _, _ = writing_fixture()
    fwd.pass_once()
    topology(box, rev=2, centre="new-centre")
    upstream(box, member="new-centre", urls=("http://new-centre/ingest",))
    fwd.pass_once()
    assert json.loads(box.objects.get(up_key("serial")))["centre"] == "new-centre"
    assert fwd.up_writes["serial"] == 2


def test_previous_version_malformed_and_expired_acknowledgements_never_restore_have():
    for over in ({"v": 1}, {"v": True}, {"v": "2"}, {"centre": ""}, {"centre": "other"},
                 {"centre": []}, {"heard": "not-a-time"}, {"heard": True}, {"have": -1},
                 {"have": None}, {"extra": "unknown"}, {"heard": 1}):
        box, fwd, door, _, _ = fixture()
        write(box, saved(box, **over))
        again = restart(box, fwd, door)
        assert "serial" not in again.local.up_have, over
        assert box.objects.get(up_key("serial")) is None, over
    box, fwd, door, _, _ = fixture()
    write(box, saved(box, heard=int((box.wall() - UP_KEPT_FOR - 1) * 1000)))
    again = restart(box, fwd, door)
    assert again.up_expired == {"serial": 1}


def test_unconfirmed_topology_assignment_or_withdrawn_polls_cannot_restore_have():
    for withdraw in (lambda b: topology(b, rev=0),
                     lambda b: b.vars.put("domain/placed/rec/serial", {}),
                     lambda b: source(b, polls=False)):
        box, fwd, door, _, _ = fixture()
        write(box, saved(box))
        withdraw(box)
        again = restart(box, fwd, door)
        assert "serial" not in again.local.up_have and not door.calls
        topology(box); placement(box, "relay"); source(box)
        again.restore_up()
        assert again.local.up_have["serial"] == 42.125


class Flaky:
    def __init__(self, objects, failing):
        self.objects, self.failing, self.reads = objects, failing, 0

    def get(self, key):
        self.reads += 1
        if self.failing == "get":
            raise OSError("store unavailable")
        return self.objects.get(key)

    def put(self, key, value):
        if self.failing == "put":
            raise OSError("store unavailable")
        self.objects.put(key, value)

    def delete(self, key):
        if self.failing == "delete":
            raise OSError("store unavailable")
        self.objects.delete(key)


def test_store_read_or_discard_failure_is_retried_without_restoring_a_foreign_have():
    for operation in ("get", "delete"):
        box, fwd, door, _, _ = fixture()
        write(box, saved(box, centre="other") if operation == "delete" else saved(box))
        objects = Flaky(box.objects, operation)
        again = restart(box, fwd, door, objects=objects)
        assert "serial" not in again.local.up_have and "serial" not in again._up_read
        assert box.objects.get(up_key("serial")) is not None
        objects.failing = None
        again.restore_up()
        assert objects.reads == 2 and "serial" in again._up_read
        if operation == "get":
            assert again.local.up_have["serial"] == 42.125
        else:
            assert "serial" not in again.local.up_have
            assert box.objects.get(up_key("serial")) is None


def test_failed_persistence_does_not_mark_the_acknowledgement_as_durably_saved():
    box, fwd, _, _ = writing_fixture()
    objects = Flaky(box.objects, "put")
    fwd.load_up, fwd.save_up, fwd.drop_up = keep_ups(objects)
    try:
        fwd.pass_once()
    except OSError:
        pass
    else:
        raise AssertionError("failed persistence was accepted as a saved acknowledgement")
    assert box.objects.get(up_key("serial")) is None
    objects.failing = None
    fwd.pass_once()
    assert json.loads(box.objects.get(up_key("serial"))) == saved(box)


def test_a_held_store_read_cannot_restore_have_after_the_confirmed_centre_changed():
    box, fwd, door, _, _ = fixture()
    write(box, saved(box))
    original = box.objects.get

    def changed_during_read(ref):
        raw = original(up_key(ref))
        topology(box, rev=2, centre="new-centre")
        upstream(box, member="new-centre", urls=("http://new-centre/ingest",))
        return raw

    local = Ingest("relay", ["http://relay/ingest"], lambda: {}, wall=box.wall)
    again = Forwarder("relay", local, box.vars, fwd.dial, token_requests=door,
                      objects=box.objects, load_up=changed_during_read)
    assert "serial" not in local.up_have and "serial" not in again._up_read
    again.load_up = lambda ref: original(up_key(ref))
    again.restore_up()
    assert "serial" not in local.up_have and box.objects.get(up_key("serial")) is None
