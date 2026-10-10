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
rec_ctl.create({"name": "7", "cam": "7"})                      # дверь семейства требует, чтобы запись rec/7 стояла
ok = jobs._ask_recorder(rec_ctl, "7", now - 600, now - 540, now, "detjob/7-lpr-1-2")  # подпись после major 4: без cam
keys = [k for k in vars_.list(REC_SPEC.sub.request_key(""))]                 # ключ — как его дала дверь семейства
key = keys[0] if keys else None
row = vars_.get(key)[0] if key else None
print("filed:", ok, "| row =", row)
schema = REC_SPEC.requests["schema"]
stamped = {"by", "at"} | ({REC_SPEC.about_field} if REC_SPEC.about_field and "about" in (REC_SPEC.requests.get("stamp") or ()) else set())
body = {k: v for k, v in row.items() if k not in stamped}            # что дверь проверяет схемой (штампы — by, at и about-поле — ставит она сама)
try:
    check(schema, {**body, "from": float(body["from"]), "to": float(body["to"]),
                   **({"valid_until": float(body["valid_until"])} if "valid_until" in body else {})}, "the request")
    print("схема семейства rec: принята")
except Invalid as e:
    print("схема семейства rec отвергла бы такую строку:", e)
print("штамп спеки:", REC_SPEC.requests.get("stamp"), "| в строке:", sorted(k for k in row if k in ("by", "at", "about")))
print("journal семейства:", REC_SPEC.requests.get("journal"), "| per_person:", REC_SPEC.requests.get("per_person"),
      "— после major 4 подача идёт через file_as: схема, штампы и журнал семейства (jobs.py:_ask_recorder)")
