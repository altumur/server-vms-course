# Checks (COURSE, ADR-0054) three paths of a request's mark, with the course's own test beds:
#  T1 timeout: a call not back after PERFORM_TIMEOUT is answered "did not answer"; the console clears the row (fetched),
#     the holder's sweep_marks deletes the mark. Expected by ADR-0054: an outcome in the mark. Measured: none, then gone.
#  T2 moved unit: holder A's call in flight, holder B now holds the unit -> B says `unknown`, A then `performed`.
#     Expected: the mark ends performed (holder wins); measured: one request counted in two outcomes (A and B).
#  T3 garbled mark, no holder: the reaper past deadline + REAP_AFTER. Expected: the row ends. Measured: stands for ever.
# Usage: python p_marks_holder_paths.py <course-tree-root>
import json, os, sys, threading, time

root = sys.argv[1]
src = os.path.join(root, "Source")
sys.path.insert(0, src)
os.chdir(src)
os.environ.setdefault("STORE_VOLATILE", "1")
os.environ.setdefault("WATERMARK_DEFAULT", "off")
threading.Timer(120, lambda: (print("DEADLINE", flush=True), os._exit(9))).start()

from tests.conftest import Box, testsub
from tests.test_holder_requests import Holder, _ask, _holder
from w2cplatform import requests
from w2cplatform.contract import Controller
from w2cplatform.spec import SpecController

defects = 0


def mark(box, spec, rid):
    raw = box.objects.get(spec.sub.command_key(rid))
    return None if raw is None else json.loads(raw)


# T1
box, spec = Box(), testsub()
gate = threading.Event()
w = _holder(box, spec, ["c1"], gate=gate)
_ask(box, spec, "r1", "c1", 4)
w.requests()
box.clock.advance(w.PERFORM_TIMEOUT)
done = w.requests()
m1 = mark(box, spec, "r1")
print("T1 answer:", done, "| mark after timeout:", m1, flush=True)
w.heartbeat_once()                                        # fetched=r1 in the heartbeat
con = SpecController(spec, box.vars, box.objects, wall=box.wall)
requests.clear_requests(con, sweep=False)                 # the console clears the answered row
box.clock.advance(w.MARK_SWEEP + 1)
w.requests()                                              # the holder sweeps marks of gone rows
m1b = mark(box, spec, "r1")
print("T1 row stands:", bool(box.vars.get(spec.sub.request_key("r1"))[0]), "| mark after clear+sweep:", m1b, flush=True)
if not (m1 and m1.get("outcome")):
    defects += 1
    print("T1 DEFECT: the request was answered (refused: did not answer) and its mark never had an outcome", flush=True)
gate.set()

# T2
box, spec = Box(), testsub()
gate = threading.Event()
a = _holder(box, spec, ["c1"], gate=gate)
_ask(box, spec, "r1", "c1", 1)
a.requests()                                              # A's call in flight: begun mark
b = Holder(box, spec)
b.server = "srv-2"
b.claim_slot("w-2")
Controller(spec.sub, box.vars, box.objects, wall=box.wall).assign("w-2", ["c1"])
b.assignment()
b.open = {"c1": {"id": "c1"}}
db = b.requests()
gate.set()
for _ in range(100):
    if not a._performing:
        break
    a.requests()
    time.sleep(0.02)
m2 = mark(box, spec, "r1")
print("T2 B answered:", [d.get("error", "")[:40] for d in db], "| A counts:", a.commands, "| B counts:", b.commands,
      "| final mark outcome:", m2.get("outcome"), flush=True)
total = sum(a.commands.values()) + sum(b.commands.values())
print(f"T2 one request counted {total} times across holders "
      f"({'DOUBLE' if total > 1 else 'once'}); calls into the target: A={len(a.calls)} B={len(b.calls)}", flush=True)

# T3
box, spec = Box(), testsub()
con = SpecController(spec, box.vars, box.objects, wall=box.wall)
late = box.wall() - requests.REAP_AFTER - 5
for rid in ("garbled", "parsed"):
    box.vars.put(spec.sub.request_key(rid), {"unit": "c1", "add": "1", "action": "add", "valid_until": str(late),
                                             "at": str(late - 10)})
box.objects.put(spec.sub.command_key("garbled"), b'{"instance":"I-old","slot":"w-1"')       # torn: does not parse
box.objects.put(spec.sub.command_key("parsed"), b'{"instance":"I-old","slot":"w-1"}')      # holder gone (no slot row)
for _ in range(5):
    box.wall.advance(3600)
    requests.clear_requests(con)
g = bool(box.vars.get(spec.sub.request_key("garbled"))[0])
pz = bool(box.vars.get(spec.sub.request_key("parsed"))[0])
print(f"T3 after 5 h of reaper turns: garbled row stands={g}, parsed (holder gone) row stands={pz}", flush=True)
if g:
    defects += 1
    print("T3 DEFECT: a request whose mark does not parse is never ended by the reaper (no holder of the unit)", flush=True)

print("RESULT", "DEFECT" if defects else "OK", flush=True)
os._exit(1 if defects else 0)
