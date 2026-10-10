"""П3. Просьба ресурса `free-<server>-<volume>` (ADR-0059: «держатель её не исполняет и не метит»): рекордер кладёт
её id в `fetched`, и жнец консоли (`requests.clear_requests`) удаляет строку ресурса."""
import _env  # noqa: F401
import tempfile
import time

from w2cplatform.cluster.variables import FakeVariables
from w2cplatform.requests import clear_requests
from w2cplatform.spec import SpecController
from vms.config import REC_SPEC
from vms.domainpart.device import Ram
from vms.recworker import RecWorker

vars_, objects = FakeVariables(), Ram()
rec = RecWorker("r-1", vars_, objects, wall=time.time, server="srv-1", resource_root=tempfile.mkdtemp(prefix="p3-"))
rec.volume = "vol"


class FakeStore:            # «том открыт»: archive_busy() == False, иначе requests() выходит сразу
    writer = object()
    quota, block_bytes, too_large, lost, lock_lost, name = 0, 0, 0, False, False, "vol"


rec.store = FakeStore()
key = REC_SPEC.sub.request_key("free-srv-1-vol")
vars_.put(key, {"free": "1000000", "volume": "vol", "server": "srv-1", "at": str(time.time())})   # строка ресурса
print("до прохода: строка ресурса стоит:", vars_.get(key)[0] is not None)
done = rec.requests()
print("recworker.requests() ->", done, "| fetched =", rec.fetched, "| freeing =", rec.freeing)
rec.heartbeat_once()
ctl = SpecController(REC_SPEC, vars_, objects)
gone = clear_requests(ctl, sweep=False)
print("clear_requests(sweep=False) удалил строк:", gone, "| строка ресурса стоит:", vars_.get(key)[0] is not None)
