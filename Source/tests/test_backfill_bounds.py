"""Lesson 16, from the product — the three bounds backfill was missing.

Written after the course's recorder ran on a real box (ОБРАТНАЯ-СВЯЗЬ-ИЗ-ПРОДУКТА.md, points P, Q and S):

    P  what a clean fetch found nowhere is remembered, per source, and not planned again — a summary
       cannot say where a card's holes are, and without this the same empty range is fetched every pass
    Q  the upper bound is the end of what we can SEE — a reader sees closed blocks only — not a guess called
       `settle` that held only while `settle` was longer than the lag, an inequality written nowhere
    S  planned backfill fills holes INSIDE what a recording recorded — before its first second it was not
       recording by design, and filling that turns a recording on events into a recording always
"""
from vms.archive import subtract
from vms.config import REC_SPEC
from vms.worker import FakeActuator, FakeDevice
from w2cplatform.contract import Heartbeat
from w2cplatform.spec import SpecController
from tests.test_lesson11_edge import CARD, _backfilled, _box, _holder, _ours, _rec

NOW = 1_000_000.0


def _until_done(fetch, passes: int = 30) -> list:
    """Every pass of `fetch` until one plans nothing: a range is served `RANGE_CAP` a pass (the review's third pass,
    blocker 6), so a gap of an hour or more comes in turns."""
    done = []
    for _ in range(passes):
        got = fetch()
        if not got:
            return done
        done += got
    raise AssertionError("still fetching after every pass")


def _served(r, rid: str, passes: int = 30) -> None:
    """The ordinary pass, until the request is reported fetched — a request is served `RANGE_CAP` a pass."""
    for _ in range(passes):
        r.pump_once()
        r._backfiller.join(10.0)
        if rid in r.fetched:
            return
    raise AssertionError(f"{rid} never served whole")


def _recorder(act=None, settle=1000.0, card=(0.0, NOW)):
    box, ctl, con, con_vars = _box()
    w = _holder(box, lambda k: FakeDevice(k, channels=["1"], coverage={"1": (*card, 5)}))
    con.create_camera({"name": "front", "source": CARD})
    ctl.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
    con_rec = SpecController(REC_SPEC, con_vars, box.objects, wall=box.wall)
    con_rec.create({"name": "1", "cam": "1"})
    r = _rec(box, actuator=act or FakeActuator(), keep_days=1.0, settle=settle)
    return box, r, con_rec


def test_a_range_the_card_does_not_have_is_fetched_once_and_then_remembered():
    """We lost an hour; so did the card, for twenty minutes of it — both were down when the site lost
    power. The card's summary says it holds the whole day. The first pass fetches the hour, gets forty
    minutes, and remembers the twenty it found nowhere. The next pass plans nothing: before this it planned
    the same twenty minutes every pass, and each plan opened one of the camera's one or two sessions."""
    act = FakeActuator()
    hole = (NOW - 74000, NOW - 72800)
    act.available = lambda source, t0, t1: subtract((t0, t1), [hole])
    box, r, _ = _recorder(act)
    _ours(box, r, 1, ((NOW - 80000, NOW - 76400), (NOW - 70000, NOW - 66400)))

    done = _until_done(lambda: r.backfill(budget=1, now=NOW, force=True))
    assert sum(d["groups"] for d in done) > 0 and r.nowhere[("1", "device")] == [hole]
    asked = len(act.fetched)
    assert r.backfill(budget=1, now=NOW, force=True) == []                  # nothing left to plan
    assert len(act.fetched) == asked
    r.heartbeat_once()
    hb = Heartbeat.from_bytes(box.objects.get(REC_SPEC.sub.heartbeat_key("r-1")))
    assert hb.extra["nowhere_seconds"] == 1200                              # "of what we lost, 1200 s were not on the card either"


def test_a_fetch_that_failed_half_way_is_not_remembered_as_nowhere():
    """A pipeline that died says nothing about what the card holds. Remembering its range as nowhere would
    lose footage the card still has, silently, for good."""
    class Broken(FakeActuator):
        def record_range(self, *a, **kw):
            self.range_error = "the playback session was refused"
            return []
    act = Broken()
    box, r, _ = _recorder(act)
    _ours(box, r, 1, ((NOW - 80000, NOW - 76400), (NOW - 70000, NOW - 66400)))
    done = r.backfill(budget=1, now=NOW, force=True)
    assert done[0]["error"] == "the playback session was refused" and r.nowhere == {}
    assert r.backfill(budget=1, now=NOW, force=True)                         # asked again next pass


def test_backfill_stops_at_what_is_visible_not_at_a_guess():
    """`settle` of two minutes, and a block that closes every twenty at this bitrate. What is in the open
    block no reader sees, so by the old bound everything between the end of our visible footage and two
    minutes ago was a gap — the recorder fetched from the card what it was recording that minute, and the
    overlap check could not catch it: there was nothing visible to overlap. The end of what we can see is
    the lag, measured; nothing after it is planned."""
    box, r, _ = _recorder(settle=120.0)
    _ours(box, r, 1, ((NOW - 7200, NOW - 1200),))                           # the last visible second: 20 min ago
    assert r.gaps(1, {"from": 0.0, "to": NOW}, NOW) == []
    assert r.backfill(budget=1, now=NOW, force=True) == []


def test_planned_backfill_fills_holes_inside_what_was_recorded_and_not_before_it():
    """The recording was created an hour ago; the card holds the whole day. The day before the first second
    is not a hole — nothing was meant to record it — and filling it would make every recording on events a
    recording always, a night late. A hole after the first second is one. An operator who wants the morning
    anyway asks for it, and a request is not planned: it is fetched."""
    box, r, con_rec = _recorder()
    _ours(box, r, 1, ((NOW - 3600, NOW - 2400), (NOW - 1800, NOW - 1200)))
    assert r.gaps(1, {"from": 0.0, "to": NOW}, NOW) == [(NOW - 2400, NOW - 1800)]

    con_rec.vars.put(REC_SPEC.sub.request_key("1-morning"),
                     {"unit": "1", "cam": "1", "from": str(NOW - 30000), "to": str(NOW - 28000), "at": str(NOW), "by": "anna"})
    r.backfill_budget = 0
    _served(r, "1-morning")
    assert r.fetched == ["1-morning"]
    r.store.seal()
    assert any(s.start == NOW - 30000 for s in _backfilled(r))


def test_a_request_a_source_failed_to_serve_stays_for_the_next_pass():
    """A fetch that failed says nothing about the range. Reported as fetched, the console would delete the
    operator's request and the range would never arrive."""
    class Broken(FakeActuator):
        def record_range(self, *a, **kw):
            self.range_error = "the playback session was refused"
            return []
    box, r, con_rec = _recorder(Broken())
    _ours(box, r, 1, ((NOW - 3600, NOW - 2400),))
    con_rec.vars.put(REC_SPEC.sub.request_key("1-x"),
                     {"unit": "1", "cam": "1", "from": str(NOW - 30000), "to": str(NOW - 28000), "at": str(NOW), "by": "anna"})
    assert r.requests(now=NOW) == [] and r.fetched == []
    assert box.vars.list(REC_SPEC.sub.requests_prefix()) == ["rec/requests/1-x"]


def test_an_operators_request_is_served_off_the_loops_thread():
    """A request is an hour off the camera's card and takes minutes; it ran on the loop's thread, where the leases
    are renewed and the heartbeat goes out (the review's first pass, B3). It is served on the backfill thread now,
    and the pass waits `BACKFILL_WAIT` for it and no longer."""
    box, r, con_rec = _recorder()
    _ours(box, r, 1, ((NOW - 3600, NOW - 2400),))
    con_rec.vars.put(REC_SPEC.sub.request_key("1-x"),
                     {"unit": "1", "cam": "1", "from": str(NOW - 30000), "to": str(NOW - 28000), "at": str(NOW), "by": "anna"})
    r.pump_once()
    assert r._backfiller is not None
    r._backfiller.join(10.0)
    _served(r, "1-x")
    assert r.fetched == ["1-x"] and r.actuator.fetched


def test_a_long_request_is_fetched_in_pieces_over_several_passes_and_reported_once_whole():
    """The review's third pass, blocker 6. An operator's request for a day was one fetch, one list in memory — and
    `POST /backfill` put no ceiling on it. The recorder asks the device for about a minute at a time, lands each
    piece before the next, and serves `RANGE_CAP` of a request a pass: the request is reported fetched — and its
    row removed — only when the last piece of it has landed."""
    act = FakeActuator()
    box, r, con_rec = _recorder(act)
    _ours(box, r, 1, ((NOW - 3600, NOW - 2400),))
    con_rec.vars.put(REC_SPEC.sub.request_key("1-long"),
                     {"unit": "1", "cam": "1", "from": str(NOW - 30000), "to": str(NOW - 28200), "at": str(NOW), "by": "anna"})
    passes = 0
    while "1-long" not in r.fetched:
        got = r.requests(now=NOW)
        passes += 1
        assert got and passes <= 10
        assert all(d["to"] - d["from"] <= r.RANGE_CAP for d in got)        # a pass takes at most RANGE_CAP of it
    assert passes == 3                                                      # half an hour, ten minutes a pass
    asked = [(lo, hi) for _, lo, hi, _ in act.fetched]
    assert len(asked) >= 30 and all(hi - lo <= r.PIECE for lo, hi in asked)   # and the device a minute at a time
    r.store.seal()
    from vms.archive import stitch
    assert stitch((s.start, s.end) for s in _backfilled(r)) == [(NOW - 30000, NOW - 28200)]   # nothing between pieces


def test_a_request_served_in_part_goes_on_after_a_restart_from_where_the_volume_shows_it_got():
    """The review's fourth pass, Т-B6. How far a long request had got was in memory: a recorder started again read it
    from its first minute — the twenty minutes it had landed fetched again off the card, to be dropped as ours. The
    volume shows what landed, and the request goes on from the first moment it does not."""
    act = FakeActuator()
    box, r, con_rec = _recorder(act)
    _ours(box, r, 1, ((NOW - 3600, NOW - 2400),))
    con_rec.vars.put(REC_SPEC.sub.request_key("1-long"),
                     {"unit": "1", "cam": "1", "from": str(NOW - 30000), "to": str(NOW - 28200), "at": str(NOW), "by": "anna"})
    r.requests(now=NOW); r.requests(now=NOW)                                # two passes: twenty minutes of thirty
    assert "1-long" not in r.fetched
    r.after_stop()                                                          # the writer closed: what landed is visible

    again = _rec(box, actuator=FakeActuator(), keep_days=1.0, settle=1000.0)
    while "1-long" not in again.fetched:
        assert again.requests(now=NOW)
    asked = [(lo, hi) for _, lo, hi, _ in again.actuator.fetched]
    assert asked and min(lo for lo, _ in asked) >= NOW - 30000 + 2 * r.RANGE_CAP - r.PIECE   # not from the start
    again.store.seal()
    from vms.archive import stitch
    assert stitch((s.start, s.end) for s in _backfilled(again)) == [(NOW - 30000, NOW - 28200)]


def test_an_answered_request_is_not_fetched_again_and_is_forgotten_with_its_row():
    """The review's fourth pass, Т-m13. The recorder's own `requests` did not keep the base worker's rule: a request
    it had answered was fetched again from its start for as long as the console had not reaped the row, and
    `fetched` grew by one id per request for the life of the process."""
    act = FakeActuator()
    box, r, con_rec = _recorder(act)
    _ours(box, r, 1, ((NOW - 3600, NOW - 2400),))
    key = REC_SPEC.sub.request_key("1-x")
    con_rec.vars.put(key, {"unit": "1", "cam": "1", "from": str(NOW - 30000), "to": str(NOW - 29700), "at": str(NOW), "by": "anna"})
    assert r.requests(now=NOW) and r.fetched == ["1-x"]
    asked = len(act.fetched)
    assert r.requests(now=NOW) == [] and len(act.fetched) == asked          # the row stands: answered, not fetched again
    assert r.heartbeat_extra()["fetched"] == "1-x"
    con_rec.vars.delete(key)                                                # the console reaped it
    r.requests(now=NOW)
    assert r.fetched == []


BAD = (NOW - 76200, NOW - 76190)                                            # ten seconds of card the engine will not take


class Corrupt(FakeActuator):
    """A card with one group of pictures the engine cannot take — its key frame is larger than a block, so the
    daemon refuses it (`SEQUENCE_TOO_LARGE`) — the first `times` fetches of it (all of them, by default)."""
    def __init__(self, times: int | None = None):
        super().__init__()
        self.times = times

    def record_range(self, cam, source, t0, t1):
        import dataclasses
        from vms.obsd import FLAG_NEED_KEY_FRAME, unix_s
        out = super().record_range(cam, source, t0, t1)
        if not (t0 < BAD[1] and BAD[0] < t1) or self.times == 0:
            return out
        self.times = None if self.times is None else self.times - 1
        for i, s in enumerate(out):
            if unix_s(s.begin) == BAD[0]:
                out[i] = dataclasses.replace(s, flags=0, body=s.body + b"\x80" * (5 << 20))   # one group: its key is too large…
            elif BAD[0] < unix_s(s.begin) < BAD[1]:
                out[i] = dataclasses.replace(s, flags=FLAG_NEED_KEY_FRAME)                    # …and the rest of it hangs on it
        return out


def _asked_for_bad(act) -> int:
    return sum(1 for _, lo, hi, _ in act.fetched if lo < BAD[1] and BAD[0] < hi)


def test_a_piece_the_engine_always_refuses_is_fetched_three_times_and_then_given_up():
    """The review's fourth pass, an open item; the product's DD. What the engine refuses stays a hole and is asked for
    again — and a piece the engine refuses for its CONTENT is refused every time: the recorder fetched it off the
    card every pass, for ever. Counted per piece (recording, source, span rounded to the stitch tolerance), it is
    fetched three times, then given up: logged, no longer planned, and the heartbeat says how many seconds."""
    act = Corrupt()
    box, r, _ = _recorder(act)
    _ours(box, r, 1, ((NOW - 80000, NOW - 76400), (NOW - 76000, NOW - 72000)))
    _until_done(lambda: r.backfill(budget=1, now=NOW, force=True))
    assert _asked_for_bad(act) == 3                                         # the first fetch and two more; not a fourth
    assert r.given_up[("1", "device")] == [BAD] and r.refusals == {}
    assert r.backfill(budget=1, now=NOW, force=True) == [] and _asked_for_bad(act) == 3
    r.store.seal()
    assert subtract((NOW - 76400, NOW - 76000), r.our_coverage("1")) == [BAD]   # a hole on the timeline, not footage
    r.heartbeat_once()
    hb = Heartbeat.from_bytes(box.objects.get(REC_SPEC.sub.heartbeat_key("r-1")))
    assert hb.extra["backfill"] == {"refused_seconds": 10} and hb.extra["nowhere_seconds"] == 0


def test_a_piece_refused_once_and_then_taken_lands_and_is_forgotten():
    """A refusal that was not about the content — the engine refused it once — is not a piece given up: the next
    pass asks again, it lands, and its count is forgotten."""
    act = Corrupt(times=1)
    box, r, _ = _recorder(act)
    _ours(box, r, 1, ((NOW - 80000, NOW - 76400), (NOW - 76000, NOW - 72000)))
    r.backfill(budget=1, now=NOW, force=True)
    assert len(r.refusals) == 1 and BAD[0] not in [a for a, _ in r.landing["1"]]
    _until_done(lambda: r.backfill(budget=1, now=NOW, force=True))          # the next fetch of it is taken
    assert _asked_for_bad(act) == 2 and r.refusals == {} and r.given_up == {}
    r.store.seal()
    assert subtract((NOW - 76400, NOW - 76000), r.our_coverage("1")) == []
    assert r.heartbeat_extra()["backfill"] == {"refused_seconds": 0}
    # and however much is refused once, the counts are bounded: the oldest forgotten first
    many = [(NOW - 50000 + 10 * i, NOW - 49995 + 10 * i) for i in range(r.REFUSALS_KEPT + 50)]
    r._refused("1", "device", many)
    assert len(r.refusals) == r.REFUSALS_KEPT and (1, *many[-1]) in r.refusals.values()
    assert (1, *many[0]) not in r.refusals.values()


def test_a_recorder_reads_another_recorders_request_once_and_an_answered_one_never_again():
    """The review's seventh pass, M5 — the sibling of the holder's beat. The recorder's own `requests` read every row of
    `rec/requests/` on every pass of its backfill thread, another recorder's and its own answered ones alike. The unit a
    row names is remembered by its key now, as the holder does: another recorder's row is read once, when it appears,
    and an answered one not at all."""
    act = FakeActuator()
    box, r, con_rec = _recorder(act)
    _ours(box, r, 1, ((NOW - 3600, NOW - 2400),))
    for i in range(50):                                                     # other recorders' recordings
        con_rec.vars.put(REC_SPEC.sub.request_key(f"9-{i}"), {"unit": "9", "cam": "9", "from": str(NOW - 600), "to": str(NOW - 300)})
    con_rec.vars.put(REC_SPEC.sub.request_key("1-x"), {"unit": "1", "cam": "1", "from": str(NOW - 30000), "to": str(NOW - 29700),
                                                       "at": str(NOW), "by": "anna"})
    reads: list[str] = []
    get = r.vars.get
    r.vars.get = lambda key: (reads.append(key) if "/requests/" in key else None, get(key))[1]
    assert r.requests(now=NOW) and r.fetched == ["1-x"] and len(reads) == 51
    del reads[:]
    assert r.requests(now=NOW) == [] and reads == []                        # nothing read again
