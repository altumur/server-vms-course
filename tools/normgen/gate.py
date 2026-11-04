"""Разбор `gate` формы stages.tsv (ADR-0126 доп. (1) п. 8, доп. (7) пп. 2, 3) — один для генераторов normgen.

`gate` — список проверок через «;», этап закрыт, когда держатся все. Проверка — `<вид>:<аргумент>[:<аргумент>]` без
пробелов (шапка формы): `tests:<глава>:<сценарии|*>[:seams]`, `accept:<глава>:<сценарии|*>`, `vectors:<пакет>`, `build`.
Пустой элемент (`;;`, «;» в конце), пробел, неизвестный вид и повтор проверки — отказ (GateError), а не молчаливый
пропуск: элемент, которого генератор не понял, не должен выпасть из этапа (ревью Codex С4). Грамматика — та же, что у
`check_forms.gate_errors` (skills/lesson-spec): её сверяет test_gate.py.
"""
import re
from dataclasses import dataclass

ITEM = re.compile(r"tests:([0-9]+\.[0-9]+):(\*|[a-z0-9][a-z0-9-]*(?:,[a-z0-9][a-z0-9-]*)*)(:seams)?"
                  r"|accept:([0-9]+\.[0-9]+):(\*|[a-z0-9][a-z0-9-]*(?:,[a-z0-9][a-z0-9-]*)*)"
                  r"|vectors:([a-z0-9][a-z0-9-]*)|build")


class GateError(ValueError):
    pass


@dataclass(frozen=True)
class Check:
    kind: str                 # tests | accept | vectors | build
    text: str
    chapter: str = None       # tests, accept
    names: tuple = None       # tests, accept: имена сценариев; None — «*»
    seams: bool = False       # tests: seams.tsv
    package: str = None       # vectors


def parse(gate, where="gate"):
    """Ячейка gate → [Check] в порядке ячейки."""
    if gate == "":
        raise GateError(f"{where}: empty gate")
    out, seen = [], set()
    for text in gate.split(";"):
        m = ITEM.fullmatch(text)
        if not m:
            what = "an empty item" if text == "" else ("a space in an item" if re.search(r"\s", text)
                                                       else f"item {text!r}")
            raise GateError(f"{where}: {what} — not tests:<chapter>:<scenarios|*>[:seams], accept:<chapter>:"
                            f"<scenarios|*>, vectors:<package> or build")
        if text in seen:
            raise GateError(f"{where}: item {text!r} repeats")
        seen.add(text)
        if m[1]:
            names = None if m[2] == "*" else tuple(m[2].split(","))
            c = Check("tests", text, m[1], names, bool(m[3]))
        elif m[4]:
            c = Check("accept", text, m[4], None if m[5] == "*" else tuple(m[5].split(",")))
        elif m[6]:
            c = Check("vectors", text, package=m[6])
        else:
            c = Check("build", text)
        if c.names is not None and len(set(c.names)) != len(c.names):
            raise GateError(f"{where}: a scenario repeats in {text!r}")
        out.append(c)
    return out
