"""Разбор `gate` формы stages.tsv (ADR-0126 доп. (1) п. 8, доп. (7) пп. 2, 3) — один для генераторов normgen.

`gate` — список проверок через «;», этап закрыт, когда держатся все. Проверка — `<вид>:<аргумент>[:<аргумент>]` без
пробелов (шапка формы): `tests:<глава>:<сценарии|*>[:seams]`, `accept:<глава>:<сценарии|*>`, `verdicts:<глава>:<случаи|*>`,
`puts:<глава>:<случаи|*>` (P/02, ADR-0125 доп. (5)), `vectors:<пакет>`, `build`; глава — NN.K или NN (урок одной главой).
Пустой элемент (`;;`, «;» в конце), пробел, неизвестный вид и повтор проверки — отказ (GateError), а не молчаливый
пропуск: элемент, которого генератор не понял, не должен выпасть из этапа (ревью Codex С4). Грамматика — та же, что у
`check_forms.gate_errors` (skills/lesson-spec): её сверяет test_gate.py.
"""
import re
from dataclasses import dataclass

CH = r"[0-9]+(?:\.[0-9]+)?"            # глава NN.K или урок одной главой NN (P/04; ADR-0125 доп. (5))
ITEM = re.compile(rf"tests:({CH}):(\*|[a-z0-9][a-z0-9-]*(?:,[a-z0-9][a-z0-9-]*)*)(:seams)?"
                  rf"|accept:({CH}):(\*|[a-z0-9][a-z0-9-]*(?:,[a-z0-9][a-z0-9-]*)*)"
                  r"|vectors:([a-z0-9][a-z0-9-]*)|build"
                  rf"|(verdicts|puts):({CH}):(\*|[a-z0-9][a-z0-9_-]*(?:,[a-z0-9][a-z0-9_-]*)*)")


class GateError(ValueError):
    pass


@dataclass(frozen=True)
class Check:
    kind: str                 # tests | accept | vectors | build | verdicts | puts
    text: str
    chapter: str = None       # tests, accept, verdicts, puts
    names: tuple = None       # tests, accept: имена сценариев; verdicts, puts: случаи (первая колонка); None — «*»
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
                            f"<scenarios|*>, verdicts:<chapter>:<cases|*>, puts:<chapter>:<cases|*>, vectors:<package> "
                            f"or build")
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
        elif m[7]:
            c = Check(m[7], text, m[8], None if m[9] == "*" else tuple(m[9].split(",")))
        else:
            c = Check("build", text)
        if c.names is not None and len(set(c.names)) != len(c.names):
            raise GateError(f"{where}: a scenario repeats in {text!r}")
        out.append(c)
    return out
