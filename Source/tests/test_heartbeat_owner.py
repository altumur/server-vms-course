"""A heartbeat is its key's (the product's r30, defect A; `contract.parse_heartbeat`).

Readers key a heartbeat by the name in its body — `hb.worker`, a resource's `server` — and judge it fresh by the key of
that name. A file under one key whose body named another kept the other alive: a dead worker whose name was never
given back, a dead server whose units never moved. A heartbeat whose body names another than its key is no heartbeat
of either — skipped, and counted as garbled. A test of the platform alone, on testsub.
"""
from __future__ import annotations

import json

from w2cplatform.contract import GARBLED, HUNG_MOVE_AFTER, Heartbeat
from w2cplatform.resource import resources_seen
from w2cplatform.spec import SpecController, SubsystemSpec
from tests.test_boundary import TESTSUB, _counter_worker, _testsub_box


def test_a_heartbeat_under_another_workers_key_keeps_nobody_alive_and_the_dead_name_is_given_back_on_time():
    root, vars_, objects, clock, wall = _testsub_box()
    spec = SubsystemSpec.load(TESTSUB)
    a = _counter_worker(spec.sub, vars_, objects, clock, wall, "A", "srv-1")
    b = _counter_worker(spec.sub, vars_, objects, clock, wall, "B", "srv-2")
    a.reconcile_once(); b.reconcile_once()
    ctl = SpecController(spec, vars_, objects, wall=wall)
    assert set(ctl.workers_seen()) == {"w-1", "w-2"}
    was = GARBLED.get("testsub", 0)
    # w-2 is dead: its slot is not renewed and it writes nothing. A file under w-9's key says it is w-2, and changes.
    for _ in range(int((91 + HUNG_MOVE_AFTER) // 20) + 2):
        wall.advance(20); clock.advance(20)
        a.renew_slot(); a.reconcile_once()
        objects.put(spec.sub.heartbeat_key("w-9"), Heartbeat("w-2", wall(), [], {"server": "srv-2"}).to_bytes())
        ctl.look(); seen = ctl.workers_seen()
    assert set(seen) == {"w-1"}, set(seen)                                  # w-2 is not kept alive by w-9's file
    assert GARBLED["testsub"] > was                                         # …which is counted, as a garbled heartbeat
    rep = ctl.publish_names()
    assert "w-2" in rep["names_given"], rep                                 # and w-2's name is given back on time


def test_a_resource_heartbeat_under_another_servers_key_does_not_keep_that_server_alive():
    root, vars_, objects, clock, wall = _testsub_box()
    spec = SubsystemSpec.load(TESTSUB)
    ctl = SpecController(spec, vars_, objects, wall=wall)

    def beat(key_server, body_server):
        objects.put(f"platform/resources/{key_server}/heartbeat",
                    json.dumps({"server": body_server, "ts": wall(), "url": f"http://{body_server}", "mirrors": {}}).encode())
    beat("srv-2", "srv-2")
    assert ctl.resource_state("srv-2") == "live"
    for _ in range(4):                                                      # srv-2 is gone; a file under srv-3 says srv-2
        wall.advance(20); clock.advance(20)
        beat("srv-3", "srv-2")
        ctl.look()                                                          # a pass: what it saw change
        state = ctl.resource_state("srv-2")
    assert state == "silent", state
    assert set(resources_seen(objects)) == {"srv-2"} and resources_seen(objects)["srv-2"]["url"] == "http://srv-2"
    beat("srv-3", "srv-3")
    assert set(resources_seen(objects)) == {"srv-2", "srv-3"}               # its own body: its own key's
