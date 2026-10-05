"""The platform's own processes (the boundary's step 5, `w2cplatform/host.py`): `python3 -m w2cplatform` runs from a
directory of specs and from nothing else, and its loops are the ones every controller, console and resource runs. A
test of the platform alone — testsub's spec, no subsystem's package."""
from __future__ import annotations

import json
import logging
import os
import tempfile

from w2cplatform import host
from w2cplatform.resource import heartbeat_key, resources_seen, space_total

TESTDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata")


class _Lines(logging.Handler):
    def __init__(self):
        super().__init__(); self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


def test_the_platforms_entry_point_runs_from_the_specs_it_is_given_and_from_nothing_else():
    """No `SPEC_DIR`: nothing runs (2). A directory without a spec: refused at the start, in words. A verb it has not, or a
    subsystem the directory has no spec of: refused, in words."""
    root = tempfile.mkdtemp(prefix="host-")
    assert host.main(["resource"], {"PLATFORM_DIR": root}) == 2
    try:
        host.main(["resource"], {"PLATFORM_DIR": root, "SPEC_DIR": tempfile.mkdtemp(prefix="empty-")})
        raise AssertionError("ran from a directory with no spec in it")
    except ValueError as e:
        assert "no <sub>.subsystem.yaml there" in str(e)
    assert host.main(["nonsense"], {"PLATFORM_DIR": root, "SPEC_DIR": TESTDATA}) == 2
    try:
        host.main(["controller", "nobody"], {"PLATFORM_DIR": root, "SPEC_DIR": TESTDATA})
        raise AssertionError("ran the controller of a subsystem with no spec")
    except ValueError as e:
        assert "no subsystem 'nobody'" in str(e)


def test_the_platforms_resource_comes_up_heartbeats_and_says_its_tree_through_the_exported_readers():
    """`python3 -m w2cplatform resource` — the platform's resource and its life (`host.run_resource`): a heartbeat at the
    start, its door, restore; stopped, it shuts its door. What a subsystem reads of it goes through the exported readers
    (`resource.heartbeat_key`, `space_total`), never the store's layout spelt by hand."""
    root = tempfile.mkdtemp(prefix="host-")
    env = {"PLATFORM_DIR": root, "SPEC_DIR": TESTDATA, "SERVER_NAME": "srv-9", "RESOURCE_PORT": "0"}
    host.stop.set()                                      # one start, no loop: the door opens and is shut again
    try:
        assert host.main(["resource"], env) == 0
    finally:
        host.stop.clear()
    _, objects = host.stores(env)
    hb = json.loads(objects.get(heartbeat_key("srv-9")))
    assert hb["server"] == "srv-9"
    seen = resources_seen(objects)
    assert space_total(seen, "srv-9") == hb["space"]["total"] and space_total(seen, "nobody") == 0
    assert space_total({"srv-9": {"space": {"total": "a lot"}}}, "srv-9") == 0          # not said, not an error


def test_a_step_that_fails_every_pass_is_said_once_and_again_when_it_works():
    """`host.step`: a failure's trace the first time of a spell, nothing on the passes after, "works again" when it does
    — the spell is its owner's, so one controller's failing step does not silence another's."""
    class Owner:
        pass
    a, b, lines = Owner(), Owner(), _Lines()
    logging.getLogger("w2cplatform.host").addHandler(lines)
    try:
        def boom():
            raise RuntimeError("the store went away")
        for _ in range(3):
            assert not host.step(a, "a placement", "publish", boom, "a: publishing failed")
        assert not host.step(b, "b placement", "publish", boom, "b: publishing failed")
        assert host.step(a, "a placement", "publish", lambda: None)
    finally:
        logging.getLogger("w2cplatform.host").removeHandler(lines)
    assert lines.lines == ["a: publishing failed", "b: publishing failed", "a placement: publish works again"], lines.lines


def test_the_console_raises_the_schema_through_its_own_grants_on_a_box_and_in_a_cluster():
    """`PUT /schema` writes `platform/schema` through the CONSOLE's store handle — opened as `console` with the specs'
    `acl_console` (`host.build_console`) — and the cluster's rights file is generated from the same lists. It was granted
    neither: on an unrestricted test store it passed, a deployed console got 403. Run here under the console's real
    grants, on a box and in the generated rights."""
    from w2cplatform.cluster import rights
    from w2cplatform.contract import SCHEMA, SCHEMA_KEY
    from w2cplatform.spec import SubsystemSpec
    env = {"SPEC_DIR": TESTDATA, "PLATFORM_DIR": tempfile.mkdtemp(prefix="host-"), "CONSOLE_ROOT": "testsub"}
    m, ctls = host.build_console(env)
    status, body = m.schema_route("PUT", {"version": str(SCHEMA)}, user="anna")
    assert status == 200, (status, body)
    assert ctls["testsub"].vars.get(SCHEMA_KEY)[0]["version"] == str(SCHEMA)
    spec = SubsystemSpec.load(os.path.join(TESTDATA, "testsub.subsystem.yaml"))
    assert SCHEMA_KEY in rights.roles([spec], "probe")["console"]["write"]
