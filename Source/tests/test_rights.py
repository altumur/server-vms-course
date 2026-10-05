"""The platform's one evaluator of store rights (`w2cplatform/rights.py`): the configstore daemon's rights file and the
in-process ACL of every store a box can run on answer the same question the same way — a `!` denial first, wherever
it stands, then the grants. A deny that held in the daemon and not on a box with `file://` would hold nowhere."""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from w2cplatform.configstorevars import ConfigstoreVariables  # noqa: E402
from w2cplatform.memvariables import MemVariables  # noqa: E402
from w2cplatform.rights import DOMAIN_ROLES, allowed, valid  # noqa: E402
from w2cplatform.storemachine import Rights, StoreMachine, local_transport  # noqa: E402
from w2cplatform.variables import FileVariables, Forbidden  # noqa: E402

# The domain's agent in a member's store: every row of the domain but what only its holder writes.
AGENT = ["domain/*", "!domain/signer*", "relay/*", "!domain/users*"]
TABLE = [("domain/keys", True), ("domain/grants", True), ("domain/signer", False), ("domain/signer-pending", False),
         ("domain/users/anna", False), ("relay/m1/domain/keys", True), ("testsub/counters/c1", False)]


def test_a_denial_wins_wherever_it_stands_and_a_pattern_is_a_key_or_a_prefix():
    for key, want in TABLE:
        assert allowed(AGENT, key) is want, key
        assert allowed(list(reversed(AGENT)), key) is want, key           # the order of the list does not matter
    assert allowed(["a/b"], "a/b") and not allowed(["a/b"], "a/bc") and allowed(["a/b*"], "a/bc")
    assert not allowed([], "a") and not allowed(None, "a")
    assert all(valid(p) for p in AGENT) and not any(valid(p) for p in ("", "!", "a*b", "a!b", "!!a", 3))


def _stores():
    """Every store a process of the platform writes through, each as the agent with the ACL above."""
    acl = {"domainagent": AGENT}
    root = tempfile.mkdtemp(prefix="rights-")
    machine = StoreMachine()
    door = ConfigstoreVariables("/stand", transport=local_transport(machine.apply, Rights({"domainagent": {
        "read": AGENT, "write": AGENT, "delete": AGENT}}), "domainagent"))
    return {"file": FileVariables(root, "domainagent", acl, volatile=True),
            "memory": MemVariables(None, "domainagent", acl),
            "configstore as a writer": ConfigstoreVariables("/stand", "domainagent", acl,
                                                            transport=local_transport(machine.apply, Rights(), "admin")),
            "configstore by its rights file": door}


def test_every_store_asks_the_one_evaluator_for_a_write():
    for name, store in _stores().items():
        for key, want in TABLE:
            try:
                store.put(key, {"x": "1"})
                got = True
            except Forbidden:
                got = False
            assert got is want, (name, key)


def test_a_delete_is_a_write_and_the_domain_rows_are_deleted_by_the_domain_roles_alone():
    assert DOMAIN_ROLES == {"domain", "domainagent"}
    root = tempfile.mkdtemp(prefix="rights-")
    FileVariables(root, volatile=True).put("domain/keys", {"x": "1"})
    for writer, acl in (("console", {"console": ["domain/*"]}), (None, {})):
        try:
            FileVariables(root, writer, acl, volatile=True).delete("domain/keys")
            raise AssertionError(f"{writer} deleted a row of the domain")
        except Forbidden:
            pass
    agent = FileVariables(root, "domainagent", {"domainagent": AGENT}, volatile=True)
    agent.delete("domain/keys")
    agent.put("domain/grants", {"x": "1"})
    FileVariables(root, volatile=True).put("domain/signer", {"x": "1"})
    try:
        agent.delete("domain/signer")
        raise AssertionError("the agent deleted the signer's row past its denial")
    except Forbidden:
        pass
    m = Rights({"domainagent": {"read": AGENT, "write": AGENT, "delete": AGENT}, "console": {"delete": ["domain/*"]}})
    assert m.allows("domainagent", "delete", "domain/keys") and not m.allows("domainagent", "delete", "domain/signer")
    assert not m.allows("console", "delete", "domain/keys") and not m.allows("admin", "delete", "domain/keys")
    assert not m.allows("domainagent", "read", "domain/signer") and m.allows("domainagent", "read", "domain/keys")
