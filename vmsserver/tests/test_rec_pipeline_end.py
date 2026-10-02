"""How a recorder's pipeline ends, without GStreamer (the review's third pass: Н-M14, B4, B5, "the last sequence
of a dead pipeline stays open").

`GstRecActuator` needs `gi`, and the test run has none; `FakeActuator` writes a released ring synchronously, so a
test through it is green whatever the real pipeline does. The order that decides what reaches the volume is in
`gstvms/ending.py`, and these tests hold it with a fake pipeline whose bus answers as GStreamer's would: what a
fake cannot prove — that `rtspsrc`/`shmsrc` put the EOS behind their last buffer, that ten seconds drain a
sixty-second ring — is the box's.
"""
from types import SimpleNamespace

from gstvms.ending import RecEnding, drain, poll

GST = SimpleNamespace(SECOND=1_000_000_000,
                      MessageType=SimpleNamespace(ERROR=1, EOS=2, ELEMENT=4),
                      State=SimpleNamespace(NULL="NULL"),
                      Event=SimpleNamespace(new_eos=lambda: "EOS"))


class Bus:
    """A bus: messages already posted (popped by `pop_filtered`), and whether an EOS sent in comes out."""
    def __init__(self, log, cid, drains=True, posted=()):
        self.log, self.cid, self.drains, self.posted = log, cid, drains, list(posted)

    def pop_filtered(self, mask):
        return self.posted.pop(0) if self.posted else None

    def timed_pop_filtered(self, ns, mask):
        self.log.append((self.cid, "wait", ns / GST.SECOND))
        return SimpleNamespace(type=GST.MessageType.EOS) if self.drains else None


class Pipeline:
    def __init__(self, log, cid, **bus):
        self.log, self.cid, self.bus = log, cid, Bus(log, cid, **bus)

    def send_event(self, ev):
        self.log.append((self.cid, ev))

    def get_bus(self):
        return self.bus

    def set_state(self, st):
        self.log.append((self.cid, st))


class Sink:
    def __init__(self, log, cid):
        self.log, self.cid = log, cid

    def finish(self):
        self.log.append((self.cid, "finish"))


class Recorder(RecEnding):
    gst = GST
    clock = staticmethod(lambda: 0.0)                         # a clock that stands: the budgets compare exactly

    def __init__(self, log, **pipes):
        self.pipelines = {c: Pipeline(log, c, **kw) for c, kw in pipes.items()}
        self.sinks = {c: Sink(log, c) for c in pipes}
        self.blocks, self.released, self.dead, self.posted = {}, set(), [], []

    def _posted(self, cid, msg):
        self.posted.append((cid, msg.kind))


def test_a_ring_released_and_stopped_at_once_is_drained_before_null_and_closed_after():
    """The recorder is told to stop during a break: `_release_if_broken` releases the ring and stops in the same
    breath. EOS and NULL back to back threw the ring away; now the stop waits for the EOS — which travels behind
    the ring's last buffer — with the drain's budget, then NULL, then the sink's open sequence is finished."""
    log = []
    r = Recorder(log, **{"7": {}})
    r.released.add("7")                                       # `_release` just removed the block probe
    r._end(["7"])
    assert log == [("7", "EOS"), ("7", "wait", r.DRAIN_BUDGET), ("7", "NULL"), ("7", "finish")]
    assert r.pipelines == {} and r.sinks == {} and r.released == set()


def test_a_live_recording_waits_a_little_and_a_ring_still_on_hold_is_dropped():
    """A running recording holds a fraction of a second in its queues: a short wait. A ring that was never released
    is not waited for at all — its EOS would sit behind the blocked pad for ever, and dropping it is what a hold
    nobody released means."""
    log = []
    r = Recorder(log, **{"7": {}, "8": {}})
    r.blocks["8"] = object()
    r._end(["7"]); r._end(["8"])
    assert ("7", "wait", r.EOS_BUDGET) in log and not any(e[0] == "8" and e[1] == "wait" for e in log)
    assert log[-2:] == [("8", "NULL"), ("8", "finish")] and r.blocks == {}


def test_a_pipeline_whose_eos_never_comes_is_stopped_at_its_budget_all_the_same():
    log = []
    p = Pipeline(log, "7", drains=False)
    assert drain([(p, 2.0)], GST) == [False] and log[-1] == ("7", "NULL")


def test_pipelines_stopped_together_drain_side_by_side():
    """A fence, an orderly stop: every pipeline gets its EOS before any is waited for, and the whole wait is bounded
    by the longest budget, not their sum."""
    log, now = [], [0.0]

    def clock():
        return now[0]

    class Slow(Bus):
        def timed_pop_filtered(self, ns, mask):
            now[0] += ns / GST.SECOND                       # the whole budget spent, and nothing came
            self.log.append((self.cid, "wait", ns / GST.SECOND))
            return None

    a, b = Pipeline(log, "a"), Pipeline(log, "b")
    a.bus, b.bus = Slow(log, "a"), Slow(log, "b")
    drain([(a, 10.0), (b, 10.0)], GST, clock=clock)
    assert log[:2] == [("a", "EOS"), ("b", "EOS")]
    assert [e for e in log if e[1] == "wait"] == [("a", "wait", 10.0)]   # b's ten seconds were a's: nothing left to wait
    assert log[-2:] == [("a", "NULL"), ("b", "NULL")]


def test_a_dead_pipeline_is_nulled_and_its_open_sequence_finished():
    """A cut cable: the watchdog posts an ERROR. The pipeline was set to NULL and forgotten, its sink's sequence
    left open — the last seconds before the cut invisible until the writer closed, and lost if the daemon fell. And
    a source that closed its stream posts an EOS nobody asked for, after which the watchdog is quiet: polled, it is
    a dead recording too (the review's first pass, B5: the EOS was not read at all)."""
    log = []
    err, eos, motion = (SimpleNamespace(type=t, kind=k) for t, k in ((1, "error"), (2, "eos"), (4, "motion")))
    r = Recorder(log, **{"7": {"posted": [motion, err]}, "8": {"posted": [eos]}, "9": {}})
    dead, posted = r.pump()
    assert sorted(dead) == ["7", "8"] and posted == [("7", "motion")]
    assert ("7", "NULL") in log and ("7", "finish") in log and ("8", "finish") in log
    assert log.index(("7", "NULL")) < log.index(("7", "finish"))
    assert list(r.pipelines) == ["9"] and list(r.sinks) == ["9"]


def test_the_bus_is_read_to_the_end_on_every_look():
    bus = Bus([], "7", posted=[SimpleNamespace(type=4), SimpleNamespace(type=4)])
    ended, elements = poll(bus, GST)
    assert not ended and len(elements) == 2 and poll(bus, GST) == (False, [])
