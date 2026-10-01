"""Is the writer writing — what the recorder handed its sink, against what reached the volume.

The pipeline's watchdog (Lesson 10) sees frames ARRIVE. What happened to them after the sink, nothing checked.
The engine has a queue and a policy of its own — a sequence it lost, a group of pictures it cut — and between
"taken" and "on the volume" anything can happen. The product lost fifteen and twenty-seven minutes of recording that way, with every sign saying
"writing": the row running, the sink's counters growing, the heartbeat fresh (feedback, point U).

So the recorder compares two numbers it can see — bytes OFFERED to the writer, bytes LANDED on the volume —
and says what it finds in its heartbeat, as a state of its own and not as a guess from other fields:

    stuck    more than a few blocks offered, and the volume has not moved for a minute. Both are needed: a
             quiet camera takes a long time to fill a block, and that is not a fault
    losing   the volume moves, but over five minutes less than 90 % of what was offered landed. A watch
             on "the volume does not move" never sees this one, and on the product's box it was the case:
             66–69 % arrived
    ok       everything else — including nothing offered, which is a held backup or an idle camera

The cure is one — reopen the writer — and not more often than every ten minutes: if the cause is not the
writer but what it is fed, reopening every minute only adds the time a writer takes to let go to what is
lost. The heartbeat goes on telling the truth either way.
"""
from __future__ import annotations

BLOCK = 1 << 20          # a megabyte — the unit "a few outstanding" is counted in before stuck is said (not the engine's block)
STUCK_BLOCKS = 3
STUCK_AFTER = 60.0       # seconds the volume may stand still with that much outstanding
WINDOW = 300.0           # the window "losing" is measured over
LOSING_SHARE = 0.9       # less than this landed, of what was offered, over the window
REOPEN_EVERY = 600.0     # the cure, at most this often


class WriterWatch:
    def __init__(self, block: int = BLOCK, stuck_after: float = STUCK_AFTER, window: float = WINDOW,
                 share: float = LOSING_SHARE, reopen_every: float = REOPEN_EVERY):
        self.block, self.stuck_after, self.window, self.share, self.reopen_every = block, stuck_after, window, share, reopen_every
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
        if outstanding > STUCK_BLOCKS * self.block and still >= self.stuck_after:
            self.state = {"state": "stuck", "outstanding": outstanding, "still": round(still, 1)}
        elif now - t0 >= self.window and d_off > STUCK_BLOCKS * self.block and d_land < self.share * d_off:
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
    if state.get("state") == "stuck":
        return f"writing stuck: {state['outstanding'] / BLOCK:.0f} MB not landed for {state['still']:.0f} s"
    if state.get("state") == "losing":
        return f"losing writes: {state['share'] * 100:.0f} % landing over {state['over']:.0f} s"
    return None
