"""П4. `jobs._ask_recorder` подаёт `rec/requests/*` мимо двери семейства: строка не по схеме спеки, без штампов и журнала
(`requests.journal: archive.backfill.asked` пишет только дверь консоли)."""
import _env  # noqa: F401
import time

from w2cplatform.cluster.variables import FakeVariables
from w2cplatform.schema import Invalid, check
from w2cplatform.spec import SpecController
from vms.config import REC_SPEC
from vms.domainpart.device import Ram
from vms import jobs

vars_, objects = FakeVariables(), Ram()
rec_ctl = SpecController(REC_SPEC, vars_, objects)
now = time.time()
ok = jobs._ask_recorder(rec_ctl, "7", "7", now - 600, now - 540, now, "detjob/7-lpr-1-2")
key = REC_SPEC.sub.request_key(f"7-{int(now - 600)}-{int(now - 540)}")
row = vars_.get(key)[0]
print("filed:", ok, "| row =", row)
schema = REC_SPEC.requests["schema"]
body = {k: v for k, v in row.items() if k not in ("by", "at")}     # что дверь проверяет схемой (штампы ставит она сама)
try:
    check(schema, {**body, "from": float(body["from"]), "to": float(body["to"]),
                   **({"valid_until": float(body["valid_until"])} if "valid_until" in body else {})}, "the request")
    print("схема семейства rec: принята")
except Invalid as e:
    print("схема семейства rec отвергла бы такую строку:", e)
print("штамп спеки:", REC_SPEC.requests.get("stamp"), "| в строке:", sorted(k for k in row if k in ("by", "at", "about")))
print("journal семейства:", REC_SPEC.requests.get("journal"), "| per_person:", REC_SPEC.requests.get("per_person"),
      "— в _ask_recorder ни журнала, ни счёта (см. jobs.py:522-532)")
