# Change 0083-p01-3-manifest-rows — the manifest rows of the stand of chapter 1.3 are written by the runner (ADR-0083 addendum (98))

change: 0083-p01-3-manifest-rows rev 1 · lesson P/01 (delta_base 725653954) · author «Спецификация» · state review

**Why.** ADR-0083 addendum (98): the stand of P/01.3 without the installer — the manifest rows `testsub`, `testsub2` by a write of the
store through `admin.sock`, without `manifest-put` of P/02. The runner does it (the series `runner/p01-daemon-manifest-rows` 23ab37f,
read by «Спецификация» — CLEAN); the README of the acceptance of chapter 1.3 still said «put by `manifest-put`». The chapter needs only the
rows that the copy `backup` carries (sc. 11 steps 9–10, a subset, `rev` `@any`); the form is that of the writer of P/02.3 Н1.5
(`manifest-row.schema.json`: required `yaml`, `sha256`, `rev`; `rev` — an integer, in `items` the decimal notation `"1"` of the first
installation; no extra fields).

## Manifest

| Artifact | Operation | Base | Result |
|---|---|---|---|
| `Platform/01-store/acceptance/3/README.md` | replace: «Stand» — the manifest rows by the runner | 08bb85699d5243afa060e9240f61d62a187e47e3 | af3f111fa74eab226d2b837ccbbaf1e57f46a128 |
| `Platform/01-store/ru/acceptance/3/README.md` | translation | deb833f05b691969ebb509c3050a7e531dacde09 | bdf8e3924c71abedd2dd6a70284ae679dbf19c05 |
| `decisions/adr-norms.tsv`, `decisions/changes/registry.tsv` | append the rows of the change | — | — |

## Change map

| Place | Mark |
|---|---|
| `acceptance/3/scenarios.tsv` sc. 11 steps 9–10 | agreed: unchanged |
| the common acceptance README «Manifests» (`manifest-put`) | not related: the other stands keep it |
| P/02.3 Н1.5 | agreed: the form of the writer |

## History

- rev 1, 2026-11-05 — «Спецификация»; applied in the branch `spec/p01-3-manifest-rows`.
