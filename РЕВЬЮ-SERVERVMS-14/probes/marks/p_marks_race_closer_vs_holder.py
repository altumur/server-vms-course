# Checks (COURSE, ADR-0054): a closer's complete_mark (by index) racing a holder's unconditional answer (put) on the same
# mark — on M10 FsObjectStore, cluster FsObjectStore and VariablesObjectStore(MemVariables) — and two closers at once, and
# the reaper's create-only expired racing a holder's create-only begun. Expected: the holder's outcome always stands,
# a closer never writes over an outcome, exactly one of two closers writes, exactly one create-only wins; a mark the
# sweep deleted is not brought back by a closer (informational count).
# Usage: python p_marks_race_closer_vs_holder.py <course-tree-root>   (the dir holding Source/)
import json, os, sys, tempfile, threading

root = sys.argv[1]
sys.path.insert(0, os.path.join(root, "Source"))
os.environ.setdefault("STORE_VOLATILE", "1")
threading.Timer(240, lambda: (print("DEADLINE", flush=True), os._exit(9))).start()

from w2cplatform.canonical import canonical_json
from w2cplatform.objects import FsObjectStore as M10Fs
from w2cplatform.cluster.objectstore import FsObjectStore as ClusterFs, VariablesObjectStore
from w2cplatform.memvariables import MemVariables
from w2cplatform.requests import complete_mark

N = int(os.environ.get("N", "300"))
KEY = "testsub/commands/r1"
BEGUN = canonical_json({"instance": "A", "slot": "w-1", "unit": "c1", "at": 1.0}).encode()
ANSWER = canonical_json({"instance": "A", "slot": "w-1", "unit": "c1", "at": 1.0, "outcome": "performed",
                         "ended_at": 2.0}).encode()


def fresh(kind):
    if kind == "m10-fs":
        return M10Fs(tempfile.mkdtemp(prefix="rc-"))
    if kind == "cluster-fs":
        return ClusterFs(tempfile.mkdtemp(prefix="rc-"))
    return VariablesObjectStore(MemVariables())


NO_DELETE = set()


def delete(store, key):
    if not hasattr(store, "delete"):          # the cluster's bench FsObjectStore has none: a worker's sweep_marks raises there
        NO_DELETE.add(type(store).__module__ + "." + type(store).__name__)
        try:
            os.remove(os.path.join(store.root, key))
        except FileNotFoundError:
            pass
        return
    store.delete(key)


def race(fns):
    b = threading.Barrier(len(fns))
    out = [None] * len(fns)

    def run(i, f):
        b.wait()
        out[i] = f()
    th = [threading.Thread(target=run, args=(i, f)) for i, f in enumerate(fns)]
    [t.start() for t in th]
    [t.join() for t in th]
    return out


bad = 0
for kind in ("m10-fs", "cluster-fs", "mem-rows"):
    s = fresh(kind)
    lost_answer = closer_over_outcome = closer_wrote = 0
    two_closers = {0: 0, 1: 0, 2: 0}
    create_only_both = resurrected = 0
    for i in range(N):
        # 1) closer vs holder's answer
        delete(s, KEY); s.put(KEY, BEGUN) if kind != "mem-rows" else s.put_new(KEY, BEGUN)
        wrote, _ = race([lambda: complete_mark(s, KEY, "unknown", "gone", 3.0), lambda: s.put(KEY, ANSWER)])
        m = json.loads(s.get(KEY))
        if m.get("outcome") != "performed":
            lost_answer += 1
        closer_wrote += bool(wrote)
        # 2) a closer when an outcome stands: never written over
        if complete_mark(s, KEY, "unknown", "late", 4.0):
            closer_over_outcome += 1
        # 3) two closers (reaper + another holder's notKnown) on a begun mark: exactly one writes
        delete(s, KEY); s.put_new(KEY, BEGUN)
        r = race([lambda: complete_mark(s, KEY, "unknown", "reaper", 5.0),
                  lambda: complete_mark(s, KEY, "unknown", "holder-B", 5.0)])
        two_closers[sum(bool(x) for x in r)] += 1
        # 4) reaper's create-only expired vs a holder's create-only begun
        delete(s, KEY)
        r = race([lambda: s.put_new(KEY, b'{"outcome":"expired","ended_by":"reaper"}'), lambda: s.put_new(KEY, BEGUN)])
        if sum(bool(x) for x in r) != 1:
            create_only_both += 1
        # 5) the holder's sweep (delete: its row is gone) against a closer: a deleted mark stays deleted
        if not hasattr(s, "delete"):
            continue                                    # no delete on this store: no sweep to race
        delete(s, KEY); s.put_new(KEY, BEGUN)
        r = race([lambda: delete(s, KEY) or True, lambda: complete_mark(s, KEY, "unknown", "gone", 6.0)])
        if s.get(KEY) is not None and r[1]:
            resurrected += 1
    ok = lost_answer == 0 and closer_over_outcome == 0 and two_closers[0] == 0 and two_closers[2] == 0 and create_only_both == 0
    bad += not ok
    print(f"{kind:10} N={N}: holder answer lost={lost_answer}, closer wrote first (then overwritten)={closer_wrote}, "
          f"closer over an outcome={closer_over_outcome}, two closers wrote {two_closers}, create-only both/none={create_only_both}, "
          f"mark brought back after the sweep deleted it={resurrected}"
          f" -> {'OK' if ok else 'DEFECT'}", flush=True)
print("stores with no delete (Worker.sweep_marks -> AttributeError there):", sorted(NO_DELETE) or "none", flush=True)
print("RESULT", "OK" if not bad else "DEFECT", flush=True)
os._exit(0 if not bad else 1)
