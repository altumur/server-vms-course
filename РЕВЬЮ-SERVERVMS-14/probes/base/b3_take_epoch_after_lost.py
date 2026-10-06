# b3 (course): the base's take_epoch for a unit the lease step let go to a newer epoch, before the assignment is read
# again — refused (lost_to_epoch, ADR-0013 / 13th review M6); after a read that answers, allowed. Tree: course.
# Expected: REFUSED_BEFORE_READ True. Usage: python b3_take_epoch_after_lost.py <course Source>
import sys; sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
from tests.conftest import Box, testsub2
from w2cplatform.contract import Controller
from w2cplatform.worker import Worker
from w2cplatform.epoch import next_epoch
spec, box = testsub2(), Box()
w = Worker(spec.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance="box-a:1:w", spec=spec)
name = w.claim_slot()
Controller(spec.sub, box.vars, box.objects, wall=box.wall).assign(name, ["u1"])
w.assignment(); mine = w.take_epoch("u1")
theirs, _ = next_epoch(box.vars, spec.sub.epoch_key("u1"))
lost = w.lease_pass()
try:
    w.take_epoch("u1"); refused = False
except Exception as e:
    refused = True; why = str(e)
print("lost", lost, "mine", mine, "theirs", theirs, "REFUSED_BEFORE_READ", refused)
w.assignment(); print("after a read: epoch", w.take_epoch("u1"))
