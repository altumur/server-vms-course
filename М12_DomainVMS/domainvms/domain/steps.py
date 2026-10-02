"""The steps of one pass, each in a try of its own — what one raises is SAID, counted, and stops only itself.

The domain console's loop learnt it first (М10's seventh review, part 2): five steps under one `except Exception:
pass`, and a member object that did not parse in the first froze the view of the whole domain with an empty log.
The signer's loop kept the same `pass` (the review's eighth pass, major): one torn relay bundle stopped the pass over
the books — sources, primaries, polls, upstream, asks — in silence, and the stream tokens in them are re-issued only
there, so within a day every pushing camera of the domain was refused at its ingest. The books' pass itself was one
step for five books, and the agent's pass one step for everything it carries and the report it leaves.

`Steps(who, every)` is that loop's bookkeeping, one per loop: `run((name, fn), …)` calls each `fn` in order; one that
raises is logged with its trace ONCE until it succeeds again (then a warning says it works again), counted in
`failures` (every time) and `by_step`, named in `failing`, and the steps after it run. `said()` is what a health
page shows of it. What a step that failed leaves is the step's own decision: a book not written this pass is the
last one written, which is the point of a book.
"""
from __future__ import annotations

import logging


class Steps:
    def __init__(self, who: str, every: float = 0.0, log: logging.Logger | None = None):
        self.who, self.every = who, every
        self.log = log or logging.getLogger("domain.steps")
        self.failures = 0                      # every step that raised, every time
        self.by_step: dict[str, int] = {}
        self.failing: set[str] = set()         # the steps whose last run raised

    def run(self, *steps) -> dict:
        """`steps`: (name, fn). Returns {name: what fn returned} for the steps that did not raise."""
        out = {}
        for what, step in steps:
            try:
                out[what] = step()
            except Exception:                  # noqa: BLE001 — a bad step is a stale part of the pass, not a dead loop
                self.failures += 1
                self.by_step[what] = self.by_step.get(what, 0) + 1
                if what not in self.failing:
                    self.failing.add(what)
                    self.log.exception("%s: %s failed; the other steps go on, and this one is tried again%s", self.who,
                                       what, f" every {self.every:.0f} s" if self.every else " on the next pass")
            else:
                if what in self.failing:
                    self.failing.discard(what)
                    self.log.warning("%s: %s works again", self.who, what)
        return out

    def said(self) -> dict:
        return {"step_failures": self.failures, "failing": sorted(self.failing)}
