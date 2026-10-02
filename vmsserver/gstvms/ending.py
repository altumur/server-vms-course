"""How a recorder's pipeline ENDS — stopped, or dead on its own — and how its bus is read, without GStreamer.

`actuator.py` needs `gi`, and the test run has none. What is here decides whether the last seconds of a
recording reach the volume, so it lives where a test can hold it with a fake pipeline — the way `observes.py`
holds which bus messages are observations. `gst` is the `Gst` namespace, or a fake with the same names:
`Event.new_eos`, `SECOND`, `MessageType.{EOS, ERROR, ELEMENT}`, `State.NULL`.

Three rules, each a finding of the reviews:

    stop      EOS, then WAIT for it on the bus, then NULL, then the sink's open sequence is finished. EOS and
              NULL back to back threw away what the queues held (the review's first pass, B4) — and a ring
              released a moment before the stop is thirty or sixty seconds of them: the release opens the
              ring's pad, and the stop that follows at once (`RecWorker._release_if_broken`) dropped the ring
              it had just let go (the review's third pass, Н-M14). EOS travels behind the last buffer, so its
              arrival at the sink IS the ring drained. A ring still ON HOLD is not waited for: its EOS waits
              behind the blocked pad for ever, and dropping it is what a hold that was never released means.
    dead      a pipeline the bus says is over — an ERROR (the watchdog's, a source that failed) or an EOS nobody
              asked for (the source closed its stream; the watchdog is quiet after an EOS, so nothing else
              would ever say so) — is set to NULL and its sink's open sequence finished. Left open, the last
              seconds before a cut cable were invisible until the writer closed, and lost if the daemon fell
              (the review's third pass).
    together  many pipelines stopping at once (`stop_all`: a fence, an orderly stop) get their EOS at once and
              drain side by side: the wait is the longest budget, not the sum of them.
"""
from __future__ import annotations

import time


def drain(items, gst, clock=time.monotonic) -> list[bool]:
    """`items`: `[(pipeline, budget seconds)]`. EOS into every pipeline, then each one's EOS awaited on its
    bus — at most its budget, and all of them within the longest — then every one NULL. Per pipeline: did
    its EOS come through."""
    for p, _ in items:
        p.send_event(gst.Event.new_eos())
    deadline = clock() + max((b for _, b in items), default=0.0)
    came = []
    for p, budget in items:
        left = min(budget, deadline - clock())
        msg = None
        if budget > 0 and left > 0:
            msg = p.get_bus().timed_pop_filtered(int(left * gst.SECOND), gst.MessageType.EOS | gst.MessageType.ERROR)
        came.append(msg is not None and msg.type == gst.MessageType.EOS)
    for p, _ in items:
        p.set_state(gst.State.NULL)
    return came


def poll(bus, gst) -> tuple[bool, list]:
    """Everything on one bus since the last look: `(ended, element messages)`. Ended: an ERROR, or an EOS."""
    ended, elements = False, []
    while True:
        msg = bus.pop_filtered(gst.MessageType.ERROR | gst.MessageType.EOS | gst.MessageType.ELEMENT)
        if msg is None:
            return ended, elements
        if msg.type == gst.MessageType.ELEMENT:
            elements.append(msg)
        else:
            ended = True


class RecEnding:
    """The recorder actuator's half that ends pipelines (`GstRecActuator` mixes it in). State it reads:
    `pipelines` `{cid: pipeline}`, `sinks` `{cid: RecSink}`, `blocks` `{cid: probe}` — rings on hold —,
    `released` — rings let go and not yet stopped —, `dead`, `posted`, and `gst`."""

    # How long a stop waits for its EOS. A live recording holds a fraction of a second in its queues; a ring
    # released just before the stop holds `PREBUFFER` seconds of frames, each one a call into the daemon
    # (a millisecond or so) — ten seconds is a margin over that, and a third of a lease: the pass that stops
    # is the pass that renews (`VmsWorker.run`).
    EOS_BUDGET = 2.0
    DRAIN_BUDGET = 10.0
    clock = staticmethod(time.monotonic)

    def _budget(self, cid) -> float:
        if self.blocks.pop(cid, None) is not None:
            return 0.0                                   # still on hold: its EOS waits behind the block, and dropping is what a hold means
        if cid in self.released:
            self.released.discard(cid)
            return self.DRAIN_BUDGET
        return self.EOS_BUDGET

    # Stop these pipelines: drained (see `drain`), NULL, and only THEN each sink's open sequence finished — a
    # key frame handed to the sink between `finish` and NULL would open a sequence nobody closes (the review's
    # first pass, blocker 4, in its obsd form).
    def _end(self, cids) -> None:
        items = [(cid, self.pipelines.pop(cid)) for cid in cids if cid in self.pipelines]
        drain([(p, self._budget(cid)) for cid, p in items], self.gst, self.clock)
        for cid, _ in items:
            self._finish(cid)

    def _finish(self, cid) -> None:
        self.blocks.pop(cid, None)
        self.released.discard(cid)
        sink = self.sinks.pop(cid, None)
        if sink is not None:
            sink.finish()

    # No GLib loop in the recorder: the buses are POLLED here (the review's first pass, B5). A dead pipeline is
    # set to NULL and its open sequence finished on the spot; the worker restarts it after its backoff.
    def pump(self):
        for cid, p in list(self.pipelines.items()):
            ended, elements = poll(p.get_bus(), self.gst)
            if ended and cid not in self.dead:
                self.dead.append(cid)
            for msg in elements:
                self._posted(cid, msg)
        dead, self.dead = self.dead, []
        posted, self.posted = self.posted, []
        for cid in dead:
            p = self.pipelines.pop(cid, None)
            if p is not None:
                p.set_state(self.gst.State.NULL)
            self._finish(cid)
        return dead, posted

    def stop_all(self) -> None:
        self._end(list(self.pipelines))
