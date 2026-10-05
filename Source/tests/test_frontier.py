"""How far a reader of a unit's events has read (`w2cplatform.events.Frontier`; the boundary's §3 row 10, the product's
`Frontier`): one number beside the unit's events on the resource's tree, written after the work and atomically, and a
file that does not read as one is a frontier that is not there. A test of the platform alone."""
from __future__ import annotations

import os
import tempfile

from w2cplatform.events import Frontier, parse_bucket


def test_a_frontier_is_one_number_beside_the_units_events_and_a_torn_one_is_not_there():
    root = tempfile.mkdtemp(prefix="frontier-")
    fr = Frontier(root, "testsub", "c1")
    assert fr.path == os.path.join(root, "testsub", "c1", "frontier.json") and fr.read() is None   # never started
    fr.set(1_757_500_060.5)
    assert Frontier(root, "testsub", "c1").read() == 1_757_500_060.5 and not os.path.exists(fr.path + ".tmp")
    assert parse_bucket(fr.path, root) is None                       # beside the buckets, and no bucket of the walkers
    for raw in ("[1]", '{"watched_through": "soon"}', '{"watched_through": NaN}', "{"):
        with open(fr.path, "w") as f:
            f.write(raw)
        assert fr.read() is None, raw                                 # the reader decides where to begin
