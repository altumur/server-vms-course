"""П2. Слова строк журнала дверей подсистемы (ADR-0069: `target` и `addr`): что пишет `archive.read` двери записи,
`live.view.ended` шлюза и `archive.keep.verified` рекордера."""
import _env  # noqa: F401
import os
import re

from vms.footage import footage_routes

said = []


class J:
    def say(self, kind, **fields):
        said.append((kind, fields))


class H:
    client_address = ("10.0.0.9", 40000)


routes = footage_routes(objects=None, vars_=None, wall=lambda: 1_700_000_000.0, journal=J())
routes.note_read(H(), "operator", "rec/7/1700000000-1700000060", {"status": 200, "bytes": 2048, "whole": True, "data": b"x"})
kind, f = said[0]
print(kind, "fields =", sorted(f))
print("  target в archive.read:", "target" in f, "| addr:", "addr" in f)
src = {
    "liveworker.py live.view.ended": ("vms/liveworker.py", r'journal\.say\("live\.view\.ended".*?\)\n', re.S),
    "recworker.py archive.keep.verified": ("vms/recworker.py", r'journal\.say\("archive\.keep\.verified".*?\)\n', re.S),
    "liveworker.py live.view": ("vms/liveworker.py", r'journal\.say\("live\.view",.*?\)\n', re.S),
}
for name, (path, rx, flags) in src.items():
    text = open(os.path.join(_env.SOURCE, path)).read()
    m = re.search(rx, text, flags)
    line = text[:m.start()].count("\n") + 1
    words = sorted(set(re.findall(r"(\w+)=", m.group(0))))
    print(f"{name}: строка {line}: поля {words} | target: {'target' in words} | addr: {'addr' in words}")
