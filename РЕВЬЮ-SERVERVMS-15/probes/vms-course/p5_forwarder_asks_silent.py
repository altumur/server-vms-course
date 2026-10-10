"""П5. `Forwarder.serve().asks`: `except Exception: pass` — ошибка `lift()` (хранилище не отвечает, книга просьб не
читается) не попадает ни в лог, ни в счётчик; просьбы между площадками не несутся молча."""
import _env  # noqa: F401
import json
import logging
import threading
import time

from w2cplatform.cluster.variables import FakeVariables
from vms.domainpart.ingest import Ingest
from vms.domainpart.keys import UPSTREAM_PATH
from vms.domainpart.chain import Forwarder


class Flaky(FakeVariables):
    """Хранилище, которое отвечает при постройке и отказывает потом."""
    broken = False
    raised = 0

    def get(self, path):
        if self.broken:
            self.raised += 1
            raise OSError("the store did not answer")
        return super().get(path)


vars_ = Flaky()
vars_.put(UPSTREAM_PATH, {"SN1": json.dumps({"urls": ["http://centre"], "mode": "push", "token_secret": "t",
                                            "until": time.time() + 86400})})
local = Ingest("relay", ["http://relay/ingest"], keys=lambda: None, wall=time.time)
records = []


class Catch(logging.Handler):
    def emit(self, r):
        records.append((r.name, r.levelname, r.getMessage()))


logging.getLogger().addHandler(Catch())
logging.getLogger().setLevel(logging.DEBUG)
fwd = Forwarder("relay", local, vars_, dial=lambda url: (_ for _ in ()).throw(__import__("w2cplatform.domain.federation", fromlist=["Unreachable"]).Unreachable(url)))
vars_.broken = True
stop = threading.Event()
fwd.serve(stop, period=0.05)
for _ in range(6):                      # шесть «событий» локального ingest: каждое будит `asks` → `lift()` → vars.get → OSError
    fwd.woken.set()
    time.sleep(0.05)
time.sleep(0.2)
stop.set()
chain = [r for r in records if r[0] == "chain"]
print("vars.get отказал раз:", vars_.raised)
print("строк лога логгера chain уровня WARNING+ о провале lift():",
      len([r for r in chain if r[1] in ("WARNING", "ERROR") and "lift" in r[2].lower()]))
print("все строки chain:", chain[:5])
print("счётчик провалов у форвардера:", {k: v for k, v in vars(fwd).items() if "fail" in k or "error" in k} or "нет")
