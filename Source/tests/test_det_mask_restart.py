"""A detector's mask, changed, restarts the detector: the VMS half of `test_blobs.py`'s revision test.

The platform's half — a new lump is a new digest is a new revision — is proved on testsub2 (`test_blobs.py`); this
one proves that the VMS's reconciler (`vms/reconciler.py`) restarts the unit by that revision.
"""
import base64

from vms.config import DET_SPEC
from w2cplatform.console import SpecConsole
from w2cplatform.spec import SpecController
from tests.conftest import Box
from tests.vmsconftest import FakeStore

MASK = base64.b64encode(bytes(1920 * 1080 // 8))       # 345 600 bytes: the real thing, not a stand-in


def _det(box, objects=None):
    ctl = SpecController(DET_SPEC, box.vars, objects or box.objects, wall=box.wall)
    return ctl, SpecConsole(ctl)


def test_changing_the_blob_moves_the_revision_and_the_reconciler_restarts():
    """The whole reason the digest is in the row. Nothing here is a new mechanism:
    the reconciler has always restarted a unit whose revision moved, and a different
    lump is a different digest is a different row.

    Put the bytes in the object store alone and this test is impossible to write —
    the object changes, the row does not, and the worker goes on with the old mask
    until something else restarts it."""
    from vms.reconciler import Reconciler
    box = Box()
    ctl, _ = _det(box)
    ctl.create({"name": "7-linecross", "cam": "7", "kind": "linecross"})
    r1 = ctl.update("7-linecross", {"mask": ctl.put_blob(MASK)})

    calls = []
    rows = FakeStore([{"id": 1, "revision": r1["revision"], "enabled": True}])
    rec = Reconciler(rows, lambda verb, cam: (calls.append(verb), True)[1])
    rec.reconcile(0.0)
    assert calls == ["start"]

    other = base64.b64encode(b"\xff" + bytes(1920 * 1080 // 8 - 1))
    r2 = ctl.update("7-linecross", {"mask": ctl.put_blob(other)})
    assert r2["mask"] != r1["mask"] and r2["revision"] == r1["revision"] + 1

    rows.rows = [{"id": 1, "revision": r2["revision"], "enabled": True}]
    rec.reconcile(1.0)
    assert calls == ["start", "restart"]                         # the new mask, by the mechanism that was there
