"""What the course's loader says of a spec, against the table the product reads too (`testdata/spec_verdicts.tsv`,
«Паритет»'s bytes; the cases of the fourteenth review's probes, the verdicts «Архитектор»'s, 2026-10-06; ADR-0012,
ADR-0019): every file of `testdata/spec_verdicts/` loaded alone, by the course's loading path (`SubsystemSpec.load`),
loads where the table says `ok` and is refused where it says `refused` — refused as a ValueError naming the file,
never a crash (an AttributeError, a RecursionError, PyYAML's own error out of a load)."""
from __future__ import annotations

import os

from w2cplatform import catalog
from w2cplatform.spec import SubsystemSpec

TESTDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata")


def _table() -> list[tuple[str, str]]:
    rows = []
    with open(os.path.join(TESTDATA, "spec_verdicts.tsv"), encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            case, verdict = line.split("\t")
            assert verdict in ("ok", "refused"), line
            rows.append((case, verdict))
    return rows


def test_every_case_of_the_table_is_loaded_or_refused_as_the_table_says_and_a_refusal_is_a_value_error():
    rows = _table()
    assert len(rows) == len({c for c, _ in rows}) and len(rows) >= 87, "a case said twice, or the table cut short"
    files = {f[:-len(".subsystem.yaml")] for f in os.listdir(os.path.join(TESTDATA, "spec_verdicts"))}
    assert files == {c for c, _ in rows}, f"files and rows differ: {sorted(files ^ {c for c, _ in rows})}"
    wrong = []
    saved = (dict(catalog._loaded), dict(catalog._files))        # a case that loads joins the catalogue: put it back
    try:
        for case, verdict in rows:
            path = os.path.join(TESTDATA, "spec_verdicts", f"{case}.subsystem.yaml")
            try:
                SubsystemSpec.load(path)
                got = "ok"
            except ValueError as e:
                got = "refused"
                if path not in str(e):
                    wrong.append(f"{case}: refused without naming the file: {str(e)[:120]}")
            except BaseException as e:  # noqa: BLE001 — a crash is the finding, whatever its kind
                got = f"crash {type(e).__name__}: {str(e)[:100]}"
            if got != verdict:
                wrong.append(f"{case}: the table says {verdict}, the course {got}")
    finally:
        with catalog._lock:
            catalog._loaded.clear(); catalog._loaded.update(saved[0])
            catalog._files.clear(); catalog._files.update(saved[1])
            catalog.version += 1
            catalog._derived.clear()
    assert not wrong, "\n".join(wrong)
