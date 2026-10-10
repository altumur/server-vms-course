"""П1. Биение рекордера-ретранслятора: `upstream`/`ingest_streams` в словах продукта — какие счётчики всегда нули,
и видны ли потери форвардера/ingest хоть одной строкой `metrics:` спеки rec (ADR-0065, дополнение 08.10)."""
import _env  # noqa: F401
import json
import os
import sys
import time

import yaml

from w2cplatform.cluster.variables import FakeVariables
from vms.domainpart.device import Ram
from vms.domainpart.keys import UPSTREAM_PATH
from vms.domainpart.chain import FORWARD_FRAMES
from vms.recworker import RecWorker

REF = "SN7"
vars_, objects = FakeVariables(), Ram()
# книга upstream ретранслятора: одна камера, дорога к центру
vars_.put(UPSTREAM_PATH, {REF: json.dumps({"urls": ["http://centre/ingest"], "mode": "push", "token_secret": "t",
                                          "until": time.time() + 86400})})
import tempfile
rec = RecWorker("r-1", vars_, objects, wall=time.time, server="relay-a", resource_root=tempfile.mkdtemp(prefix="p1-"))
rec.host_ingest("relay", "http://relay-a/ingest")       # ingest и форвардер живут в RecWorker (ADR-0065 доп.)
fwd, ing = rec.forwarder, rec.ingest
# центр захотел поток: форвардер подписался (так делает `_push`); центр молчит — очередь переполняется
q = fwd.queues.setdefault(REF, ing.subscribe(REF, fwd.up, maxsize=FORWARD_FRAMES))
now = time.time()
frames = [{"t": now - 60 + i * 0.1, "key": i % 30 == 0} for i in range(FORWARD_FRAMES + 150)]
ing.inject(REF, frames)
hb = rec.ingest_fields()
up = hb["upstream"][REF]
zeros = sorted(k for k, v in up.items() if v in (0, 0.0) and k not in ("mode", "state"))
print("upstream[SN7] =", json.dumps(up, sort_keys=True))
print("нулей-констант в upstream (всегда 0 в курсе):", len(zeros), zeros)
print("реальная потеря форвардера: up_dropped =", up["up_dropped"], "(queue.dropped =", q.dropped, ")")
st = hb["ingest_streams"][REF]
print("ingest_streams[SN7].cut_for_full_queue =", st["cut_for_full_queue"], "| ingest.lost() =", json.dumps(ing.lost()))
# что из этого читает хоть одна строка metrics: рекордера
spec = yaml.safe_load(open(os.path.join(_env.SOURCE, "vms", "rec.subsystem.yaml")))
froms = [m.get("from", "") for m in spec.get("metrics", [])]
hits = [f for f in froms if "upstream" in f or "ingest" in f]
print("строк metrics: со словами upstream/ingest в rec.subsystem.yaml:", hits)
# и servers.status
stat = [s.get("field") for s in spec.get("servers", {}).get("status", [])]
print("servers.status rec:", stat)
sys.exit(0)
