"""C2 reserve intent, observation grace and continuity without archive processes."""
import json
from types import SimpleNamespace

from vms.recworker import RecWorker


class _Vars:
    def __init__(self):
        self.rows = {
            "domain/member": {"cluster": "reserve"},
            "domain/placed/rec/cam": {"cluster": "main", "origin": "camera", "copies": '["reserve"]',
                                      "reason": "operator", "at": "1000", "rev": "1"},
        }

    def get(self, key):
        return self.rows.get(key), 1


def _book(*, enabled=True, running=True, missing=()):
    observation = {"member": "main", "item": "r1/recording", "value": {
        "ref": "cam", "to": ["camera", "main", "reserve"], "recording": "recording",
        "role": "primary", "enabled": enabled, "running": running}}
    return {"": json.dumps({"missing": list(missing)}),
            "cam": json.dumps({"entries": [observation], "missing": list(missing)})}


def _case(book):
    vars_ = _Vars()
    vars_.rows["domain/rec/primaries"] = book
    seen = {"raw": b'{"ts":1000}'}
    objects = SimpleNamespace(get=lambda key: seen["raw"] if key == "domain/seen" else None)
    rec = SimpleNamespace(vars=vars_, objects=objects, _not_written_since={},
                          CARRIED_LOST_AFTER=45.0, START_GRACE=20.0)
    return rec, seen


def _cover(rec, at):
    return RecWorker.carried_word(rec, {"id": "backup", "cam": "ref:cam"}, at)[0]


def _unobserved():
    return (None, {}, {"": '{"missing": []}'}, {"": "{"},
            {"": '{"missing": []}', "cam": '{"entries": ['},
            _book(missing=["main"]))


def test_cold_reserve_waits_the_same_grace_for_absent_incomplete_and_malformed_books():
    for book in _unobserved():
        rec, _ = _case(book)
        assert not _cover(rec, 1000)
        assert not _cover(rec, 1019.999)
        assert _cover(rec, 1020)


def test_changing_bad_envelopes_does_not_restart_the_absence_grace():
    rec, _ = _case(_unobserved()[0])
    for at, book in zip((1000, 1004, 1008, 1012, 1016, 1020), _unobserved()):
        rec.vars.rows["domain/rec/primaries"] = book
        assert _cover(rec, at) is (at == 1020)


def test_explicit_stop_remains_a_stop_after_stale_carry_and_invalid_seen_mark():
    rec, seen = _case(_book(enabled=False, running=False))
    assert not _cover(rec, 1000)
    assert not _cover(rec, 1046)
    for mark in (None, b"{", b'{"ts":NaN}'):
        seen["raw"] = mark
        assert not _cover(rec, 2000)


def test_confirmed_disabled_intent_survives_missing_or_broken_observations_until_confirmed_enabled():
    rec, seen = _case(_book(enabled=False, running=False))
    assert not _cover(rec, 1000)
    for book in _unobserved():
        rec.vars.rows["domain/rec/primaries"] = book
        assert not _cover(rec, 2000)
        assert not _cover(rec, 2100)
    rec.vars.rows["domain/rec/primaries"] = _book(enabled=True, running=False)
    seen["raw"] = b'{"ts":2101}'
    assert _cover(rec, 2101)
    rec.vars.rows["domain/rec/primaries"] = _book(enabled=True, running=True)
    assert not _cover(rec, 2102)


def test_covering_reserve_keeps_its_path_on_lost_observations_but_obeys_confirmed_recovery_or_stop():
    for book in _unobserved():
        rec, _ = _case(_book(running=False))
        assert _cover(rec, 1000)
        rec.vars.rows["domain/rec/primaries"] = book
        assert _cover(rec, 1001)
        rec.vars.rows["domain/rec/primaries"] = _book(running=True)
        assert not _cover(rec, 1002)
        rec.vars.rows["domain/rec/primaries"] = _book(running=False)
        assert _cover(rec, 1003)
        rec.vars.rows["domain/rec/primaries"] = _book(enabled=False, running=False)
        assert not _cover(rec, 1004)


def test_cover_started_after_grace_is_not_interrupted_by_another_lost_observation():
    rec, _ = _case(None)
    assert not _cover(rec, 1000)
    assert _cover(rec, 1020)
    rec.vars.rows["domain/rec/primaries"] = _unobserved()[4]
    assert _cover(rec, 1021)


def test_new_assignment_does_not_inherit_the_previous_disabled_intent_or_covering_decision():
    for first in (_book(enabled=False, running=False), _book(enabled=True, running=False)):
        rec, _ = _case(first)
        _cover(rec, 1000)
        rec.vars.rows["domain/placed/rec/cam"].update(rev="2", at="1001")
        rec.vars.rows["domain/rec/primaries"] = None
        assert not _cover(rec, 1001)
        assert not _cover(rec, 1020)
        assert _cover(rec, 1021)


def test_new_assignment_does_not_inherit_an_expired_absence_timer():
    rec, _ = _case(None)
    assert not _cover(rec, 1000)
    assert not _cover(rec, 1019)
    rec.vars.rows["domain/placed/rec/cam"].update(rev="2", at="1019")
    assert not _cover(rec, 1020)
    assert not _cover(rec, 1039)
    assert _cover(rec, 1040)
