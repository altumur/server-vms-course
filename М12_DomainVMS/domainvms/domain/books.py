"""The domain's pass over the books — one place that writes every per-cluster book, in the order they depend
on each other. The console's pass reads (the view, `domain/view`, kept edits); this one mints tokens, so it
runs where the signer's key is: `domain.signer_service`, when it is given CLUSTERS.

    sources      Lesson 13   for each recording cluster: where its cameras of other clusters were last seen
    primaries    Lesson 13   for each camera cluster: who records it, whether written, and where to push (16)
    poll         Lesson 16   for a pushing camera nobody records: the ingest it polls for asks
    upstream     Lesson 17   for each office: the centre's ingest, per camera, when there is a centre
    asks         Lesson 16   for each camera a scenario of the shared document makes a trigger: whom it may
                             ask, by which roads — built last, because it reads what the others decided
"""
from __future__ import annotations

from .chain import publish_upstream
from .ingest import publish_asks
from .scenario import pairs, refusals
from .shared import published


class Books:
    def __init__(self, crossings, domain_objects):
        self.crossings, self.objects = crossings, domain_objects

    def pass_once(self) -> dict[str, int]:
        c = self.crossings
        c.view.refresh()
        out = {"sources": len(c.publish()), "primaries": len(c.publish_primaries()), "poll": len(c.publish_polls())}
        if c.centre:
            out["upstream"] = len(publish_upstream(c, c.centre, star=c.star))
        settings = published(c.vars, self.objects)
        out["asks"] = len(publish_asks(c, pairs(settings)))
        # Checked at writing; a camera can still leave the domain afterwards. Such a scenario is SAID, every pass,
        # never skipped in silence.
        out["refused"] = refusals(settings, c)
        return out
