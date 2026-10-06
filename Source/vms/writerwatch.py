"""Is the writer writing — what the recorder handed its sink, against what reached the volume.

The pipeline's watchdog (Lesson 10) sees frames ARRIVE. What happened to them after the sink, nothing checked.
The engine has a queue and a policy of its own — a sequence it lost, a group of pictures it cut — and between
"taken" and "on the volume" anything can happen. The product lost fifteen and twenty-seven minutes of recording that way, with every sign saying
"writing": the row running, the sink's counters growing, the heartbeat fresh (feedback, point U).

So the recorder compares two numbers it can see — bytes OFFERED to the writer, bytes LANDED on the volume —
and says what it finds in its heartbeat, as a state of its own and not as a guess from other fields:

    stalled  more than a few blocks offered, and the volume has not moved for a minute. Both are needed: a
             quiet camera takes a long time to fill a block, and that is not a fault
    losing   the volume moves, but over five minutes less than 90 % of what was offered landed. A watch
             on "the volume does not move" never sees this one, and on the product's box it was the case:
             66–69 % arrived
    ok       everything else — including nothing offered, which is a held backup or an idle camera

Three words, the same on both sides (the product's recorder says `ok`, `stalled`, `losing`; one name on both sides,
СЕССИИ.md §1). ADR-0063 closes the set in the spec — `values` on the metric `writer` — and a word outside it is then a
garbled field, not a new series.

The cure is one — reopen the writer — and not more often than every ten minutes: if the cause is not the
writer but what it is fed, reopening every minute only adds the time a writer takes to let go to what is
lost. The heartbeat goes on telling the truth either way.

This watch counts the VOLUME, and a volume can be `ok` while one of its recordings is never written: one camera
of thirty whose group of pictures is larger than a block, refused every sample, while the other twenty-nine land.
That is counted per recording, apart (the review's third pass): what the engine answered for each recording's
samples (`RecSink.tally` → `samples_refused` in the status, `rec_samples_refused_total{unit,status}` on
`/metrics`), and `last_frame_at` — the writer's last TAKE of that recording's frame, not the last frame offered.
"""
from __future__ import annotations

BLOCK = 1 << 20          # a megabyte — the unit "a few outstanding" is counted in before stalled is said (not the engine's block)
STALL_BLOCKS = 3
STALL_AFTER = 60.0       # seconds the volume may stand still with that much outstanding
WINDOW = 300.0           # the window "losing" is measured over
LOSING_SHARE = 0.9       # less than this landed, of what was offered, over the window
REOPEN_EVERY = 600.0     # the cure, at most this often


class WriterWatch:
    def __init__(self, block: int = BLOCK, stall_after: float = STALL_AFTER, window: float = WINDOW,
                 share: float = LOSING_SHARE, reopen_every: float = REOPEN_EVERY):
        self.block, self.stall_after, self.window, self.share, self.reopen_every = block, stall_after, window, share, reopen_every
        self.samples: list[tuple[float, int, int]] = []     # (t, offered, landed), cumulative
        self.moved_at: float | None = None                  # when `landed` last grew
        self.moved_offered = 0                              # what had been offered at that moment
        self.reopened_at: float | None = None
        self.state = {"state": "ok"}

    def observe(self, offered: int, landed: int, now: float) -> dict:
        if not self.samples or landed > self.samples[-1][2] or self.moved_at is None:
            self.moved_at, self.moved_offered = now, offered
        self.samples.append((now, offered, landed))
        while len(self.samples) > 2 and self.samples[1][0] <= now - self.window:
            self.samples.pop(0)                             # keep one sample at or before the window's start
        outstanding = offered - self.moved_offered
        still = now - self.moved_at
        t0, o0, l0 = self.samples[0]
        d_off, d_land = offered - o0, landed - l0
        if outstanding > STALL_BLOCKS * self.block and still >= self.stall_after:
            self.state = {"state": "stalled", "outstanding": outstanding, "still": round(still, 1)}
        elif now - t0 >= self.window and d_off > STALL_BLOCKS * self.block and d_land < self.share * d_off:
            self.state = {"state": "losing", "share": round(d_land / d_off, 2), "over": round(now - t0, 1)}
        else:
            self.state = {"state": "ok"}
        return self.state

    def reopen_due(self, now: float) -> bool:
        """The writer should be reopened now: something is wrong, and it was not reopened in the last ten
        minutes. Says yes once and then no until the interval has passed."""
        if self.state["state"] == "ok":
            return False
        if self.reopened_at is not None and now - self.reopened_at < self.reopen_every:
            return False
        self.reopened_at = now
        return True


def describe(state: dict) -> str | None:
    """What the console says on the volume, or None when there is nothing to say."""
    if state.get("state") == "stalled":
        return f"writing stalled: {state['outstanding'] / BLOCK:.0f} MB not landed for {state['still']:.0f} s"
    if state.get("state") == "losing":
        return f"losing writes: {state['share'] * 100:.0f} % landing over {state['over']:.0f} s"
    return None
