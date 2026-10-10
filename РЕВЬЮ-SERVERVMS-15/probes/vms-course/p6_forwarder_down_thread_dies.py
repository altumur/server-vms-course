"""П6. `Forwarder.serve().down(ref)`: один отказ хранилища (`vars.get` → OSError, у файлового хранилища `StoreBusy(OSError)`)
убивает поток камеры навсегда — поток вверх к центру для неё больше не несётся, пока рекордер не перезапустят;
`stats()` при этом говорит последнее слово."""
import _env  # noqa: F401
import json
import threading
import time

from w2cplatform.cluster.variables import FakeVariables
from w2cplatform.domain.federation import Unreachable
from vms.domainpart.ingest import Ingest
from vms.domainpart.keys import UPSTREAM_PATH
from vms.domainpart.chain import Forwarder


class Flaky(FakeVariables):
    broken, raised = False, 0

    def get(self, path):
        if self.broken:
            self.raised += 1
            raise OSError("StoreBusy: the store did not answer")
        return super().get(path)


vars_ = Flaky()
vars_.put(UPSTREAM_PATH, {"SN1": json.dumps({"urls": ["http://centre"], "mode": "push", "token_secret": "t",
                                            "until": time.time() + 86400})})
local = Ingest("relay", ["http://relay/ingest"], keys=lambda: None, wall=time.time)


class Centre:                       # центр, который хочет поток и берёт всё
    def __init__(self):
        self.pushed = 0

    def poll(self, token, ref, version=None, wait=0.0):
        return {"version": 1, "push": True, "ranges": {}, "asks": {}}

    def push(self, token, ref, frames):
        self.pushed += len(frames)

    def take_up(self):
        return []


centre = Centre()
fwd = Forwarder("relay", local, vars_, dial=lambda url: centre)
stop = threading.Event()
fwd.serve(stop, period=0.05, stream_every=0.01)
time.sleep(0.3)
alive = lambda: sorted(t.name for t in threading.enumerate() if t.name.startswith("fwd-"))
print("потоки форвардера до отказа хранилища:", alive())
local.inject("SN1", [{"t": time.time() - 1 + i * 0.01, "key": i == 0} for i in range(30)])
time.sleep(0.2)
print("дошло до центра до отказа:", centre.pushed)
vars_.broken = True                 # один отказ хранилища…
time.sleep(0.3)
vars_.broken = False                # …и оно снова отвечает
time.sleep(0.3)
print("потоки форвардера после одного отказа (хранилище давно отвечает):", alive(), "| отказов было:", vars_.raised)
before = centre.pushed
local.inject("SN1", [{"t": time.time() - 0.5 + i * 0.01, "key": i == 0} for i in range(30)])
time.sleep(0.4)
print("дошло до центра после отказа: +", centre.pushed - before)
print("stats() говорит:", json.dumps(fwd.stats().get("SN1", {}).get("state")))
stop.set()
